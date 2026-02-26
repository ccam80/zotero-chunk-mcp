"""Integration tests for the adversarial vision extraction pipeline.

LOCAL TESTS (run by default when Zotero PDFs are available):
  - TestFallback: client=None returns error result (no API calls)
  - TestPNGRendering: PNG rendering produces valid images (no API calls)

VISION API TESTS (disabled by default, run with: pytest -m vision_api):
  - TestAPIConnectivity, TestConsensusQuality, TestGroundTruthAccuracy,
    TestCellGridConversion
  These make real Anthropic API calls (~12 Haiku calls per session:
  3 tables × 4 agents each: Transcriber, Y-Verifier, X-Verifier, Synthesizer).
  Requires ANTHROPIC_API_KEY environment variable.
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
from pathlib import Path

import pymupdf
import pytest

from zotero_chunk_rag.feature_extraction.ground_truth import (
    GROUND_TRUTH_DB_PATH,
    compare_extraction,
)
from zotero_chunk_rag.feature_extraction.pipeline import FAST_CONFIG, Pipeline
from zotero_chunk_rag.feature_extraction.vision_extract import (
    VisionExtractionResult,
    _render_table_png,
    extract_table_vision,
    vision_result_to_cell_grid,
)

_GT_DB = GROUND_TRUTH_DB_PATH
_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# PDF path cache — populated once per session.
_PDF_CACHE: dict[str, Path] = {}


def _resolve_pdf_path(paper_key: str) -> Path | None:
    """Resolve a paper_key to a PDF path via the Zotero client."""
    if paper_key in _PDF_CACHE:
        return _PDF_CACHE[paper_key]
    try:
        from zotero_chunk_rag.config import Config
        from zotero_chunk_rag.zotero_client import ZoteroClient

        config = Config.load()
        zotero = ZoteroClient(config.zotero_data_dir)
        for item in zotero.get_all_items_with_pdfs():
            _PDF_CACHE[item.item_key] = item.pdf_path
    except Exception:
        return None
    return _PDF_CACHE.get(paper_key)


def _get_gt(table_id: str) -> tuple[int, str | None, list[str], list[list[str]]]:
    """Fetch ground truth. Returns (page_num, caption, headers, rows)."""
    conn = sqlite3.connect(str(_GT_DB))
    try:
        row = conn.execute(
            "SELECT page_num, caption, headers_json, rows_json "
            "FROM ground_truth_tables WHERE table_id = ?",
            (table_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise KeyError(f"No ground truth for {table_id}")
    return row[0], row[1], json.loads(row[2]), json.loads(row[3])


def _discover_bbox(
    pdf_path: Path, page_num: int, table_num: int | None = None,
) -> tuple[float, float, float, float] | None:
    """Use Pipeline.extract_page() for table bbox discovery.

    Runs the pipeline's 3-strategy find_tables with overlap dedup and
    number-ordered caption matching — identical to production extraction.

    Parameters
    ----------
    pdf_path:
        Path to the PDF.
    page_num:
        1-indexed page number.
    table_num:
        If given, return bbox for the table whose pipeline-matched
        caption contains "Table {table_num}". If None, return first.
    """
    pipeline = Pipeline(FAST_CONFIG)
    doc = pymupdf.open(str(pdf_path))
    try:
        page = doc[page_num - 1]
        features = pipeline.extract_page(page, page_num, str(pdf_path))
        if not features.tables:
            return None
        if table_num is None:
            return features.tables[0].bbox
        for result in features.tables:
            if result.caption and f"Table {table_num}" in result.caption:
                return result.bbox
    finally:
        doc.close()
    return None


def _get_raw_text(pdf_path: Path, page_num: int, bbox: tuple) -> str:
    """Extract raw text from a bbox region."""
    doc = pymupdf.open(str(pdf_path))
    try:
        return doc[page_num - 1].get_text("text", clip=pymupdf.Rect(*bbox))
    finally:
        doc.close()


async def _run_vision(
    pdf_path: Path,
    page_num: int,
    bbox: tuple[float, float, float, float],
    raw_text: str,
    caption: str | None,
) -> VisionExtractionResult:
    """Run adversarial 4-agent vision extraction on a single table."""
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=_API_KEY)
    return await extract_table_vision(
        pdf_path=pdf_path,
        page_num=page_num,
        bbox=bbox,
        raw_text=raw_text,
        caption=caption,
        client=client,
        model="claude-haiku-4-5-20251001",
        dpi=300,
        padding_px=20,
    )


# ---------------------------------------------------------------------------
# Test table specs
# ---------------------------------------------------------------------------

TEST_TABLES = [
    # (table_id, paper_key, table_num_in_caption)
    ("Z9X4JVZ5_table_5", "Z9X4JVZ5", 5),
    ("9GKLLJH9_table_2", "9GKLLJH9", 2),
    ("DPYRZTFI_table_3", "DPYRZTFI", 3),
]


# ---------------------------------------------------------------------------
# Session-scoped fixture: run API calls once, share across all tests
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def vision_results() -> dict[str, tuple[VisionExtractionResult, dict]]:
    """Run vision extraction on all test tables once.

    Uses Pipeline.extract_page() for bbox discovery (3-strategy dedup
    with caption matching) — identical to production.
    Returns dict of table_id -> (VisionExtractionResult, gt_info).
    """
    if not _API_KEY:
        pytest.skip("ANTHROPIC_API_KEY not set")

    results: dict[str, tuple[VisionExtractionResult, dict]] = {}

    for table_id, paper_key, table_num in TEST_TABLES:
        pdf_path = _resolve_pdf_path(paper_key)
        if pdf_path is None or not pdf_path.exists():
            continue

        page_num, caption, gt_headers, gt_rows = _get_gt(table_id)
        bbox = _discover_bbox(pdf_path, page_num, table_num=table_num)
        if bbox is None:
            continue

        raw_text = _get_raw_text(pdf_path, page_num, bbox)
        result = asyncio.run(
            _run_vision(pdf_path, page_num, bbox, raw_text, caption)
        )

        results[table_id] = (result, {
            "page_num": page_num,
            "caption": caption,
            "headers": gt_headers,
            "rows": gt_rows,
        })

    if not results:
        pytest.skip("No test PDFs found in Zotero library")

    return results


def _require(vision_results: dict, table_id: str):
    """Get result for a table or skip the test if unavailable."""
    if table_id not in vision_results:
        pytest.skip(f"{table_id} not available (PDF missing)")
    return vision_results[table_id]


# ---------------------------------------------------------------------------
# LOCAL TESTS — no API calls, always run
# ---------------------------------------------------------------------------


class TestFallback:
    """Verify traditional fallback works when vision is disabled."""

    def test_no_client_returns_error(self) -> None:
        """extract_table_vision with client=None returns error result."""
        pdf_path = _resolve_pdf_path("Z9X4JVZ5")
        if pdf_path is None:
            pytest.skip("PDF not found")

        page_num, caption, _, _ = _get_gt("Z9X4JVZ5_table_5")
        bbox = _discover_bbox(pdf_path, page_num, table_num=5)
        if bbox is None:
            pytest.skip("Pipeline found no table on page")

        result = asyncio.run(
            extract_table_vision(
                pdf_path=pdf_path,
                page_num=page_num,
                bbox=bbox,
                raw_text="test",
                caption=caption,
                client=None,
            )
        )

        assert result.consensus is None
        assert result.error is not None
        assert "No Anthropic client" in result.error


class TestPNGRendering:
    """Verify PNG rendering produces valid images."""

    def test_render_produces_png(self) -> None:
        """_render_table_png returns valid PNG bytes."""
        pdf_path = _resolve_pdf_path("Z9X4JVZ5")
        if pdf_path is None:
            pytest.skip("PDF not found")

        page_num = 19
        bbox = _discover_bbox(pdf_path, page_num, table_num=5)
        if bbox is None:
            pytest.skip("Pipeline found no table on page")

        png_bytes, media_type = _render_table_png(
            pdf_path, page_num, bbox, dpi=300, padding_px=20,
        )

        assert media_type == "image/png"
        assert len(png_bytes) > 100
        assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"


# ---------------------------------------------------------------------------
# VISION API TESTS — disabled by default
# Run with: pytest -m vision_api
# ---------------------------------------------------------------------------


@pytest.mark.vision_api
class TestAPIConnectivity:
    """Verify that all 4 adversarial agents respond and parse."""

    def test_all_agents_parse_successfully(self, vision_results) -> None:
        """At least 3 of 4 agents must return parseable JSON for each table.

        The 4 agents are: Transcriber, Y-Verifier, X-Verifier, Synthesizer.
        """
        for table_id, (result, _gt) in vision_results.items():
            succeeded = sum(1 for r in result.agent_responses if r.parse_success)
            assert succeeded >= 3, (
                f"{table_id}: only {succeeded}/4 agents parsed; "
                f"errors: {[r.raw_response[:200] for r in result.agent_responses if not r.parse_success]}"
            )

    def test_consensus_built(self, vision_results) -> None:
        """Consensus must be built for all test tables."""
        for table_id, (result, _gt) in vision_results.items():
            assert result.consensus is not None, (
                f"{table_id}: consensus is None despite "
                f"{sum(1 for r in result.agent_responses if r.parse_success)} successful agents"
            )

    def test_no_api_error(self, vision_results) -> None:
        """No VisionExtractionResult should have an error set."""
        for table_id, (result, _gt) in vision_results.items():
            assert result.error is None, f"{table_id}: {result.error}"


@pytest.mark.vision_api
class TestConsensusQuality:
    """Verify that consensus output meets minimum quality thresholds."""

    def test_shape_agreement(self, vision_results) -> None:
        """At least 2 agents should agree on shape for each table."""
        for table_id, (result, _gt) in vision_results.items():
            assert result.consensus is not None
            assert result.consensus.shape_agreement, (
                f"{table_id}: no shape agreement; winning={result.consensus.winning_shape}"
            )

    def test_agreement_rate_above_threshold(self, vision_results) -> None:
        """Cell agreement rate should be >= 60% for all tables."""
        for table_id, (result, _gt) in vision_results.items():
            assert result.consensus is not None
            rate = result.consensus.agent_agreement_rate
            assert rate >= 0.6, (
                f"{table_id}: agreement rate {rate:.1%} below 60% threshold; "
                f"{len(result.consensus.disputed_cells)} disputed cells"
            )

    def test_table_label_detected(self, vision_results) -> None:
        """Agents should detect a table label for all captioned tables."""
        for table_id, (result, gt) in vision_results.items():
            assert result.consensus is not None
            caption = gt["caption"]
            if caption and "Table" in caption:
                assert result.consensus.table_label is not None, (
                    f"{table_id}: no label detected despite caption '{caption[:60]}'"
                )


@pytest.mark.vision_api
class TestGroundTruthAccuracy:
    """Compare vision consensus against verified ground truth."""

    def test_simple_table_accuracy(self, vision_results) -> None:
        """Z9X4JVZ5_table_5 (5x2): small table, pipeline bbox."""
        self._check_accuracy("Z9X4JVZ5_table_5", vision_results, min_accuracy=50.0)

    def test_medium_table_accuracy(self, vision_results) -> None:
        """9GKLLJH9_table_2 (14x6): cross-lagged coefficients."""
        self._check_accuracy("9GKLLJH9_table_2", vision_results, min_accuracy=70.0)

    def test_complex_table_accuracy(self, vision_results) -> None:
        """DPYRZTFI_table_3 (22x11): full-page meta-analysis table."""
        self._check_accuracy("DPYRZTFI_table_3", vision_results, min_accuracy=80.0)

    def _check_accuracy(
        self,
        table_id: str,
        vision_results: dict,
        min_accuracy: float,
    ) -> None:
        result, gt = _require(vision_results, table_id)
        assert result.consensus is not None

        grid = vision_result_to_cell_grid(result)
        assert grid is not None

        comparison = compare_extraction(
            _GT_DB,
            table_id,
            list(grid.headers),
            [list(row) for row in grid.rows],
        )

        assert comparison.cell_accuracy_pct >= min_accuracy, (
            f"{table_id}: cell accuracy {comparison.cell_accuracy_pct:.1f}% "
            f"< {min_accuracy}% threshold. "
            f"Shape: GT={comparison.gt_shape} ext={comparison.ext_shape}, "
            f"splits={len(comparison.column_splits)}, merges={len(comparison.column_merges)}, "
            f"cell_diffs={len(comparison.cell_diffs)}"
        )

        print(f"\n  {table_id}: accuracy={comparison.cell_accuracy_pct:.1f}%, "
              f"shape GT={comparison.gt_shape} ext={comparison.ext_shape}, "
              f"agreement={result.consensus.agent_agreement_rate:.1%}, "
              f"disputed={len(result.consensus.disputed_cells)}")


@pytest.mark.vision_api
class TestCellGridConversion:
    """Verify the CellGrid output is pipeline-compatible."""

    def test_cell_grid_has_headers_and_rows(self, vision_results) -> None:
        """All successful extractions convert to non-empty CellGrids."""
        for table_id, (result, _gt) in vision_results.items():
            if result.consensus is None:
                continue
            grid = vision_result_to_cell_grid(result)
            assert grid is not None
            assert len(grid.headers) > 0, f"{table_id}: empty headers"
            assert len(grid.rows) > 0, f"{table_id}: empty rows"
            assert grid.method == "vision_consensus"
            assert grid.structure_method == "vision_haiku_consensus"

    def test_cell_grid_shape_matches_consensus(self, vision_results) -> None:
        """CellGrid dimensions must match consensus winning_shape."""
        for table_id, (result, _gt) in vision_results.items():
            if result.consensus is None:
                continue
            grid = vision_result_to_cell_grid(result)
            assert grid is not None
            expected_rows, expected_cols = result.consensus.winning_shape
            assert len(grid.headers) == expected_cols, (
                f"{table_id}: headers len={len(grid.headers)} != expected {expected_cols}"
            )
            assert len(grid.rows) == expected_rows, (
                f"{table_id}: rows len={len(grid.rows)} != expected {expected_rows}"
            )
