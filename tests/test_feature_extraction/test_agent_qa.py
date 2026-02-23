"""Tests for the agent QA workspace preparation, prompt builder, and design doc."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from zotero_chunk_rag.feature_extraction.ground_truth import make_table_id


# ---------------------------------------------------------------------------
# Helpers — mock debug DB creation (reused from test_ground_truth_workspace.py)
# ---------------------------------------------------------------------------

_DEBUG_SCHEMA = """\
CREATE TABLE papers (
    item_key TEXT PRIMARY KEY,
    short_name TEXT,
    title TEXT,
    num_pages INTEGER,
    num_chunks INTEGER,
    quality_grade TEXT,
    figures_found INTEGER,
    figures_with_captions INTEGER,
    figures_missing INTEGER,
    figure_captions_found INTEGER,
    tables_found INTEGER,
    tables_with_captions INTEGER,
    tables_missing INTEGER,
    table_captions_found INTEGER,
    tables_1x1 INTEGER,
    encoding_artifact_captions INTEGER,
    duplicate_captions INTEGER,
    figure_number_gaps TEXT,
    table_number_gaps TEXT,
    unmatched_figure_captions TEXT,
    unmatched_table_captions TEXT,
    completeness_grade TEXT,
    full_markdown TEXT
);

CREATE TABLE extracted_tables (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_key TEXT,
    table_index INTEGER,
    page_num INTEGER,
    caption TEXT,
    caption_position TEXT,
    num_rows INTEGER,
    num_cols INTEGER,
    non_empty_cells INTEGER,
    total_cells INTEGER,
    fill_rate REAL,
    headers_json TEXT,
    rows_json TEXT,
    markdown TEXT,
    reference_context TEXT,
    bbox TEXT,
    artifact_type TEXT,
    extraction_strategy TEXT
);
"""


def _create_mock_db(
    db_path: Path,
    papers: list[dict],
    tables: list[dict],
) -> None:
    """Create a mock debug database with the given papers and tables."""
    conn = sqlite3.connect(str(db_path))
    conn.executescript(_DEBUG_SCHEMA)
    for p in papers:
        conn.execute(
            """INSERT INTO papers (item_key, short_name, title, num_pages,
               num_chunks, quality_grade, figures_found, figures_with_captions,
               figures_missing, figure_captions_found, tables_found,
               tables_with_captions, tables_missing, table_captions_found,
               tables_1x1, encoding_artifact_captions, duplicate_captions,
               figure_number_gaps, table_number_gaps,
               unmatched_figure_captions, unmatched_table_captions,
               completeness_grade, full_markdown)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                p["item_key"], p["short_name"], p.get("title", "Test Paper"),
                p.get("num_pages", 10), 0, "A", 0, 0, 0, 0,
                0, 0, 0, 0, 0, 0, 0, "[]", "[]", "[]", "[]", "A", "",
            ),
        )
    for t in tables:
        conn.execute(
            """INSERT INTO extracted_tables
               (item_key, table_index, page_num, caption, caption_position,
                num_rows, num_cols, non_empty_cells, total_cells, fill_rate,
                headers_json, rows_json, markdown, reference_context, bbox,
                artifact_type, extraction_strategy)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                t["item_key"], t["table_index"], t["page_num"],
                t.get("caption", "Table 1"),
                t.get("caption_position", "above"),
                t.get("num_rows", 2), t.get("num_cols", 3),
                t.get("non_empty_cells", 6), t.get("total_cells", 6),
                t.get("fill_rate", 1.0),
                json.dumps(t.get("headers", ["A", "B", "C"])),
                json.dumps(t.get("rows", [["1", "2", "3"], ["4", "5", "6"]])),
                t.get("markdown", "| A | B | C |"),
                t.get("reference_context", ""),
                json.dumps(t.get("bbox", [72.0, 200.0, 540.0, 400.0])),
                t.get("artifact_type", None),
                t.get("extraction_strategy", "rawdict"),
            ),
        )
    conn.commit()
    conn.close()


def _mock_render(pdf_path, page_num, bbox, output_path, **kwargs):
    """Write a minimal valid PNG file instead of rendering from a PDF."""
    import struct
    import zlib

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0)
    ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF
    ihdr = struct.pack(">I", 13) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)
    raw = zlib.compress(b"\x00\xff")
    idat_crc = zlib.crc32(b"IDAT" + raw) & 0xFFFFFFFF
    idat = struct.pack(">I", len(raw)) + b"IDAT" + raw + struct.pack(">I", idat_crc)
    iend_crc = zlib.crc32(b"IEND") & 0xFFFFFFFF
    iend = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", iend_crc)

    output_path.write_bytes(sig + ihdr + idat + iend)
    return output_path


@pytest.fixture()
def mock_db(tmp_path: Path) -> Path:
    """Create a mock debug DB with 2 papers, 1 non-artifact table each."""
    db_path = tmp_path / "debug.db"
    papers = [
        {"item_key": "KEY1", "short_name": "paper-alpha"},
        {"item_key": "KEY2", "short_name": "paper-beta"},
    ]
    tables = [
        {
            "item_key": "KEY1",
            "table_index": 0,
            "page_num": 3,
            "caption": "Table 1. Demographics",
            "headers": ["Variable", "Value"],
            "rows": [["Age", "55"]],
            "num_rows": 2,
            "num_cols": 2,
            "fill_rate": 1.0,
            "bbox": [72.0, 200.0, 540.0, 400.0],
        },
        {
            "item_key": "KEY2",
            "table_index": 0,
            "page_num": 5,
            "caption": "Table 1. Results",
            "headers": ["Metric", "Score", "p"],
            "rows": [["Test", "0.95", "0.01"]],
            "num_rows": 2,
            "num_cols": 3,
            "fill_rate": 1.0,
            "bbox": [50.0, 100.0, 500.0, 300.0],
        },
    ]
    _create_mock_db(db_path, papers, tables)
    return db_path


@pytest.fixture()
def mock_db_with_artifact(tmp_path: Path) -> Path:
    """Create a mock debug DB with 1 regular table + 1 artifact table."""
    db_path = tmp_path / "debug_artifact.db"
    papers = [
        {"item_key": "KEY1", "short_name": "paper-alpha"},
    ]
    tables = [
        {
            "item_key": "KEY1",
            "table_index": 0,
            "page_num": 3,
            "caption": "Table 1. Demographics",
            "headers": ["Variable", "Value"],
            "rows": [["Age", "55"]],
            "num_rows": 2,
            "num_cols": 2,
            "fill_rate": 1.0,
            "bbox": [72.0, 200.0, 540.0, 400.0],
        },
        {
            "item_key": "KEY1",
            "table_index": 1,
            "page_num": 4,
            "caption": "Figure 2 data",
            "headers": ["X", "Y"],
            "rows": [["1", "2"]],
            "num_rows": 2,
            "num_cols": 2,
            "fill_rate": 1.0,
            "bbox": [72.0, 200.0, 540.0, 350.0],
            "artifact_type": "figure_data_table",
        },
    ]
    _create_mock_db(db_path, papers, tables)
    return db_path


# ---------------------------------------------------------------------------
# Helper to run prepare_qa_workspace with mocking
# ---------------------------------------------------------------------------


def _run_prepare(mock_db_path: Path, output_dir: Path) -> Path:
    """Run prepare_qa_workspace with mocked rendering and PDF paths."""
    from tests.agent_qa.prepare_qa import prepare_qa_workspace

    fake_pdf_paths = {
        "KEY1": Path(__file__).resolve().parent.parent / "fixtures" / "papers" / "noname1.pdf",
        "KEY2": Path(__file__).resolve().parent.parent / "fixtures" / "papers" / "noname1.pdf",
    }

    with patch(
        "tests.agent_qa.prepare_qa.render_table_image",
        side_effect=_mock_render,
    ):
        return prepare_qa_workspace(
            mock_db_path,
            output_dir,
            pdf_paths=fake_pdf_paths,
        )


# ===========================================================================
# Task 4.1.1 Tests — TestPrepareQA
# ===========================================================================


class TestPrepareQA:
    """Tests for prepare_qa_workspace()."""

    def test_creates_paper_directories(self, mock_db: Path, tmp_path: Path) -> None:
        output_dir = tmp_path / "workspace"
        _run_prepare(mock_db, output_dir)
        assert (output_dir / "paper-alpha").is_dir()
        assert (output_dir / "paper-beta").is_dir()

    def test_renders_images(self, mock_db: Path, tmp_path: Path) -> None:
        output_dir = tmp_path / "workspace"
        _run_prepare(mock_db, output_dir)
        png_alpha = output_dir / "paper-alpha" / "table_0.png"
        png_beta = output_dir / "paper-beta" / "table_0.png"
        assert png_alpha.exists()
        assert png_beta.exists()
        assert png_alpha.read_bytes()[:4] == b"\x89PNG"
        assert png_beta.read_bytes()[:4] == b"\x89PNG"

    def test_writes_extraction_json(self, mock_db: Path, tmp_path: Path) -> None:
        output_dir = tmp_path / "workspace"
        _run_prepare(mock_db, output_dir)
        ext_path = output_dir / "paper-alpha" / "table_0_extraction.json"
        assert ext_path.exists()
        data = json.loads(ext_path.read_text(encoding="utf-8"))
        required_fields = {
            "table_id", "headers", "rows", "page_num", "bbox",
            "fill_rate", "extraction_strategy",
        }
        assert required_fields.issubset(data.keys())
        assert data["headers"] == ["Variable", "Value"]
        assert data["rows"] == [["Age", "55"]]
        assert data["fill_rate"] == 1.0
        assert data["extraction_strategy"] == "rawdict"

    def test_writes_manifest(self, mock_db: Path, tmp_path: Path) -> None:
        output_dir = tmp_path / "workspace"
        _run_prepare(mock_db, output_dir)
        manifest_path = output_dir / "manifest.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert isinstance(manifest, list)
        assert len(manifest) == 2
        for entry in manifest:
            required_fields = {"table_id", "image_path", "extraction_path"}
            assert required_fields.issubset(entry.keys())

    def test_skips_artifacts(self, mock_db_with_artifact: Path, tmp_path: Path) -> None:
        output_dir = tmp_path / "workspace"
        fake_pdf_paths = {
            "KEY1": Path(__file__).resolve().parent.parent / "fixtures" / "papers" / "noname1.pdf",
        }
        from tests.agent_qa.prepare_qa import prepare_qa_workspace

        with patch(
            "tests.agent_qa.prepare_qa.render_table_image",
            side_effect=_mock_render,
        ):
            prepare_qa_workspace(
                mock_db_with_artifact,
                output_dir,
                pdf_paths=fake_pdf_paths,
            )

        manifest = json.loads(
            (output_dir / "manifest.json").read_text(encoding="utf-8")
        )
        assert len(manifest) == 1
        assert manifest[0]["table_id"] == make_table_id(
            "KEY1", "Table 1. Demographics", 3, 0
        )

        # Artifact table files should NOT exist
        assert not (output_dir / "paper-alpha" / "table_1.png").exists()
        assert not (output_dir / "paper-alpha" / "table_1_extraction.json").exists()

    def test_requires_debug_db(self, tmp_path: Path) -> None:
        from tests.agent_qa.prepare_qa import prepare_qa_workspace

        nonexistent = tmp_path / "does_not_exist.db"
        with pytest.raises(FileNotFoundError):
            prepare_qa_workspace(nonexistent, tmp_path / "output")


# ===========================================================================
# Task 4.1.2 Tests — TestPromptBuilder
# ===========================================================================


class TestPromptBuilder:
    """Tests for build_agent_prompt()."""

    def test_substitutes_variables(self) -> None:
        from tests.agent_qa.run_qa import build_agent_prompt

        result = build_agent_prompt(
            "path/to/img.png",
            "path/to/ext.json",
            "ABC_table_1",
        )
        assert "path/to/img.png" in result
        assert "path/to/ext.json" in result
        assert "ABC_table_1" in result
        # No unsubstituted template markers
        assert "{IMAGE_PATH}" not in result
        assert "{EXTRACTION_JSON_PATH}" not in result
        assert "{TABLE_ID}" not in result

    def test_reads_template(self) -> None:
        from tests.agent_qa.run_qa import build_agent_prompt

        result = build_agent_prompt("img.png", "ext.json", "T1")
        assert "visually read" in result.lower()
        assert "cell-by-cell" in result.lower()


# ===========================================================================
# Task 4.1.2 Tests — TestResponseParser
# ===========================================================================


class TestResponseParser:
    """Tests for parse_agent_response()."""

    _CLEAN_JSON = json.dumps({
        "table_id": "ABC_table_1",
        "matches": False,
        "visual_rows": 8,
        "visual_cols": 5,
        "extraction_rows": 8,
        "extraction_cols": 5,
        "structural_errors": [],
        "errors": [
            {"row": 2, "col": 3, "visual": "0.047", "extracted": ".047"},
        ],
    })

    def test_parses_clean_json(self) -> None:
        from tests.agent_qa.run_qa import parse_agent_response

        result = parse_agent_response(self._CLEAN_JSON)
        assert result["table_id"] == "ABC_table_1"
        assert result["matches"] is False
        assert len(result["errors"]) == 1

    def test_parses_fenced_json(self) -> None:
        from tests.agent_qa.run_qa import parse_agent_response

        fenced = f"```json\n{self._CLEAN_JSON}\n```"
        result = parse_agent_response(fenced)
        assert result["table_id"] == "ABC_table_1"
        assert result["matches"] is False

    def test_parses_json_with_preamble(self) -> None:
        from tests.agent_qa.run_qa import parse_agent_response

        with_preamble = f"Here are the results:\n{self._CLEAN_JSON}"
        result = parse_agent_response(with_preamble)
        assert result["table_id"] == "ABC_table_1"

    def test_rejects_no_json(self) -> None:
        from tests.agent_qa.run_qa import parse_agent_response

        with pytest.raises(ValueError):
            parse_agent_response("I couldn't read the image")


# ===========================================================================
# Task 4.1.2 Tests — TestAggregation
# ===========================================================================


class TestAggregation:
    """Tests for aggregate_results()."""

    def test_all_matching(self) -> None:
        from tests.agent_qa.run_qa import aggregate_results

        results = [
            {"table_id": f"T{i}", "matches": True, "errors": [], "structural_errors": []}
            for i in range(3)
        ]
        qa_results, qa_report = aggregate_results(results)
        assert qa_results["tables_with_errors"] == 0
        assert qa_results["total_errors"] == 0
        assert "3/3 tables match" in qa_report

    def test_with_errors(self) -> None:
        from tests.agent_qa.run_qa import aggregate_results

        results = [
            {"table_id": "T0", "matches": True, "errors": [], "structural_errors": []},
            {
                "table_id": "T1",
                "matches": False,
                "errors": [
                    {"row": 0, "col": 0, "visual": "a", "extracted": "b"},
                    {"row": 1, "col": 0, "visual": "c", "extracted": "d"},
                    {"row": 2, "col": 0, "visual": "e", "extracted": "f"},
                ],
                "structural_errors": [],
            },
        ]
        qa_results, qa_report = aggregate_results(results)
        assert qa_results["tables_with_errors"] == 1
        assert qa_results["total_errors"] == 3

    def test_structural_errors_counted(self) -> None:
        from tests.agent_qa.run_qa import aggregate_results

        results = [
            {
                "table_id": "T0",
                "matches": False,
                "errors": [
                    {"row": 0, "col": 0, "visual": "x", "extracted": "y"},
                ],
                "structural_errors": [
                    "Missing column 3",
                    "Extra column 5",
                ],
            },
        ]
        qa_results, _report = aggregate_results(results)
        assert qa_results["total_errors"] == 3  # 2 structural + 1 cell


# ===========================================================================
# Task 4.1.2 Tests — TestOutputWriter
# ===========================================================================


class TestOutputWriter:
    """Tests for write_outputs()."""

    def test_writes_json_and_markdown(self, tmp_path: Path) -> None:
        from tests.agent_qa.run_qa import write_outputs

        qa_results = {
            "run_timestamp": "2026-02-20T00:00:00+00:00",
            "total_tables": 2,
            "tables_matching": 1,
            "tables_with_errors": 1,
            "total_errors": 2,
            "results": [],
        }
        qa_report = "# Test Report\n\nSome content."

        results_path, report_path = write_outputs(qa_results, qa_report, tmp_path / "out")

        assert results_path.exists()
        assert report_path.exists()

        loaded = json.loads(results_path.read_text(encoding="utf-8"))
        assert loaded["total_tables"] == 2

        md = report_path.read_text(encoding="utf-8")
        assert "Test Report" in md


# ===========================================================================
# Task 4.1.3 Tests — TestDesignDoc
# ===========================================================================


class TestDesignDoc:
    """Tests for the production QA pathway design document."""

    _DOC_PATH = Path(__file__).resolve().parents[2] / "spec" / "agent_qa_design.md"

    def test_design_doc_exists(self) -> None:
        assert self._DOC_PATH.exists(), f"Design doc not found: {self._DOC_PATH}"
        content = self._DOC_PATH.read_text(encoding="utf-8")
        assert len(content) > 500, f"Design doc too short: {len(content)} chars"

    def test_design_doc_sections(self) -> None:
        content = self._DOC_PATH.read_text(encoding="utf-8").lower()
        assert "cost" in content, "Design doc missing 'Cost' section"
        assert "latency" in content, "Design doc missing 'Latency' section"
        assert "failure" in content, "Design doc missing 'Failure' section"
        assert "confidence" in content, "Design doc missing 'Confidence' section"
