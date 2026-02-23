"""Tests for core data models in zotero_chunk_rag.feature_extraction.models."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock

import pytest

from zotero_chunk_rag.feature_extraction.models import (
    BoundaryHypothesis,
    BoundaryPoint,
    CellGrid,
    ExtractionResult,
    PipelineConfig,
    TableContext,
)


# ---------------------------------------------------------------------------
# TestBoundaryPoint
# ---------------------------------------------------------------------------


class TestBoundaryPoint:
    def test_frozen(self) -> None:
        bp = BoundaryPoint(145.0, 145.0, 0.9, "ruled_lines")
        with pytest.raises(dataclasses.FrozenInstanceError):
            bp.min_pos = 200.0  # type: ignore[misc]

    def test_point_estimate(self) -> None:
        bp = BoundaryPoint(145.0, 145.0, 0.9, "ruled_lines")
        assert bp.min_pos == bp.max_pos
        assert bp.min_pos == 145.0
        assert bp.confidence == 0.9
        assert bp.provenance == "ruled_lines"

    def test_range(self) -> None:
        bp = BoundaryPoint(143.0, 148.0, 0.7, "word_gap")
        assert bp.min_pos == 143.0
        assert bp.max_pos == 148.0
        assert bp.confidence == 0.7
        assert bp.provenance == "word_gap"


# ---------------------------------------------------------------------------
# TestBoundaryHypothesis
# ---------------------------------------------------------------------------


class TestBoundaryHypothesis:
    def test_empty_axis(self) -> None:
        hyp = BoundaryHypothesis(
            col_boundaries=(
                BoundaryPoint(100.0, 100.0, 0.9, "ruled_lines"),
            ),
            row_boundaries=(),
            method="ruled_lines",
            metadata={"note": "rows not detected"},
        )
        assert len(hyp.col_boundaries) == 1
        assert len(hyp.row_boundaries) == 0
        assert hyp.method == "ruled_lines"

    def test_serialization(self) -> None:
        bp1 = BoundaryPoint(100.0, 100.0, 0.9, "ruled_lines")
        bp2 = BoundaryPoint(200.0, 205.0, 0.7, "word_gap")
        hyp = BoundaryHypothesis(
            col_boundaries=(bp1, bp2),
            row_boundaries=(BoundaryPoint(50.0, 50.0, 0.85, "ruled_lines"),),
            method="combined",
            metadata={"confidence_score": 0.88},
        )
        d = hyp.to_dict()
        # Round-trip through JSON
        json_str = json.dumps(d)
        loaded = json.loads(json_str)
        assert loaded["method"] == "combined"
        assert len(loaded["col_boundaries"]) == 2
        assert len(loaded["row_boundaries"]) == 1
        assert loaded["col_boundaries"][0]["min_pos"] == 100.0
        assert loaded["col_boundaries"][1]["max_pos"] == 205.0
        assert loaded["metadata"]["confidence_score"] == 0.88


# ---------------------------------------------------------------------------
# TestCellGrid
# ---------------------------------------------------------------------------


class TestCellGrid:
    def test_frozen(self) -> None:
        grid = CellGrid(
            headers=("A", "B"),
            rows=(("1", "2"), ("3", "4")),
            col_boundaries=(0.0, 100.0, 200.0),
            row_boundaries=(0.0, 50.0, 100.0),
            method="rawdict",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            grid.headers = ("X",)  # type: ignore[misc]

    def test_includes_boundaries(self) -> None:
        grid = CellGrid(
            headers=("A", "B"),
            rows=(("1", "2"),),
            col_boundaries=(0.0, 100.0, 200.0),
            row_boundaries=(0.0, 50.0),
            method="rawdict",
        )
        assert grid.col_boundaries == (0.0, 100.0, 200.0)
        assert grid.row_boundaries == (0.0, 50.0)

    def test_no_quality_score(self) -> None:
        grid = CellGrid(
            headers=("A",),
            rows=(("1",),),
            col_boundaries=(0.0, 100.0),
            row_boundaries=(0.0, 50.0),
            method="rawdict",
        )
        assert not hasattr(grid, "quality_score")


# ---------------------------------------------------------------------------
# TestExtractionResult
# ---------------------------------------------------------------------------


class TestExtractionResult:
    def test_grid_scores(self) -> None:
        result = ExtractionResult(
            table_id="paper1_p3_t0",
            bbox=(0.0, 0.0, 500.0, 300.0),
        )
        result.grid_scores = {"rawdict": 3.5, "words": 5.0, "midpoint": 7.5}
        assert result.grid_scores["rawdict"] == 3.5
        assert result.grid_scores["words"] == 5.0
        assert result.grid_scores["midpoint"] == 7.5

    def test_accumulate_hypotheses(self) -> None:
        result = ExtractionResult(
            table_id="paper1_p3_t0",
            bbox=(0.0, 0.0, 500.0, 300.0),
        )
        assert len(result.boundary_hypotheses) == 0

        hyp1 = BoundaryHypothesis(
            col_boundaries=(BoundaryPoint(100.0, 100.0, 0.9, "ruled"),),
            row_boundaries=(),
            method="ruled_lines",
            metadata={},
        )
        result.boundary_hypotheses.append(hyp1)
        assert len(result.boundary_hypotheses) == 1

        hyp2 = BoundaryHypothesis(
            col_boundaries=(BoundaryPoint(200.0, 205.0, 0.7, "gap"),),
            row_boundaries=(),
            method="word_gap",
            metadata={},
        )
        result.boundary_hypotheses.append(hyp2)
        assert len(result.boundary_hypotheses) == 2

    def test_snapshots(self) -> None:
        result = ExtractionResult(
            table_id="paper1_p3_t0",
            bbox=(0.0, 0.0, 500.0, 300.0),
        )
        grid1 = CellGrid(
            headers=("A",), rows=(("1",),),
            col_boundaries=(0.0, 100.0), row_boundaries=(0.0, 50.0),
            method="rawdict",
        )
        grid2 = CellGrid(
            headers=("A",), rows=(("cleaned",),),
            col_boundaries=(0.0, 100.0), row_boundaries=(0.0, 50.0),
            method="rawdict",
        )
        grid3 = CellGrid(
            headers=("A",), rows=(("final",),),
            col_boundaries=(0.0, 100.0), row_boundaries=(0.0, 50.0),
            method="rawdict",
        )
        result.snapshots.append(("step_clean", grid1))
        result.snapshots.append(("step_merge", grid2))
        result.snapshots.append(("step_final", grid3))

        assert len(result.snapshots) == 3
        assert result.snapshots[0][0] == "step_clean"
        assert result.snapshots[1][0] == "step_merge"
        assert result.snapshots[2][0] == "step_final"
        assert result.snapshots[0][1] is grid1
        assert result.snapshots[2][1] is grid3


# ---------------------------------------------------------------------------
# TestTableContext
# ---------------------------------------------------------------------------


def _make_mock_page(
    words: list[tuple] | None = None,
    drawings: list[dict] | None = None,
    dict_blocks: list[dict] | None = None,
    height: float = 842.0,
    width: float = 595.0,
) -> MagicMock:
    """Create a mock pymupdf Page with controlled return values."""
    page = MagicMock()

    # Configure get_text to return words or dict blocks based on the format arg
    if words is None:
        words = []
    if dict_blocks is None:
        dict_blocks = []

    def get_text_side_effect(fmt: str, **kwargs: Any) -> Any:
        if fmt == "words":
            return words
        if fmt == "dict":
            return {"blocks": dict_blocks}
        return ""

    page.get_text = MagicMock(side_effect=get_text_side_effect)

    # Configure get_drawings
    if drawings is None:
        drawings = []
    page.get_drawings = MagicMock(return_value=drawings)

    # Configure rect
    rect = MagicMock()
    rect.height = height
    rect.width = width
    page.rect = rect

    return page


class TestTableContext:
    def test_lazy_words(self) -> None:
        words = [
            (10.0, 20.0, 50.0, 30.0, "hello", 0, 0, 0),
            (60.0, 20.0, 100.0, 30.0, "world", 0, 0, 0),
        ]
        page = _make_mock_page(words=words)
        ctx = TableContext(
            page=page,
            page_num=1,
            bbox=(0.0, 0.0, 500.0, 300.0),
            pdf_path=Path("/tmp/test.pdf"),
        )

        # First access
        result1 = ctx.words
        assert result1 == words

        # Second access — should not call get_text again
        result2 = ctx.words
        assert result2 == words

        # get_text("words", ...) should have been called exactly once
        calls = [c for c in page.get_text.call_args_list if c[0][0] == "words"]
        assert len(calls) == 1

    def test_lazy_drawings(self) -> None:
        drawings = [
            {"rect": (10.0, 10.0, 200.0, 200.0), "width": 1.0},
            {"rect": (10.0, 10.0, 200.0, 200.0), "width": 0.5},
        ]
        page = _make_mock_page(drawings=drawings)
        ctx = TableContext(
            page=page,
            page_num=1,
            bbox=(0.0, 0.0, 500.0, 300.0),
            pdf_path=Path("/tmp/test.pdf"),
        )

        # First access
        result1 = ctx.drawings
        assert len(result1) == 2

        # Second access
        result2 = ctx.drawings
        assert len(result2) == 2

        # get_drawings should have been called exactly once
        assert page.get_drawings.call_count == 1

    def test_median_word_height(self) -> None:
        # Words with heights: 10, 12, 11, 10, 12 -> sorted: 10, 10, 11, 12, 12 -> median = 11
        words = [
            (10.0, 20.0, 50.0, 30.0, "a", 0, 0, 0),   # height = 10
            (60.0, 20.0, 100.0, 32.0, "b", 0, 0, 0),   # height = 12
            (10.0, 40.0, 50.0, 51.0, "c", 0, 0, 0),    # height = 11
            (60.0, 40.0, 100.0, 50.0, "d", 0, 0, 0),   # height = 10
            (10.0, 60.0, 50.0, 72.0, "e", 0, 0, 0),    # height = 12
        ]
        page = _make_mock_page(words=words)
        ctx = TableContext(
            page=page,
            page_num=1,
            bbox=(0.0, 0.0, 500.0, 300.0),
            pdf_path=Path("/tmp/test.pdf"),
        )
        assert ctx.median_word_height == 11.0

    def test_word_rows_cached(self) -> None:
        """Access .word_rows twice, assert clustering called once."""
        words = [
            (10.0, 100.0, 50.0, 110.0, "a", 0, 0, 0),
            (60.0, 100.0, 100.0, 110.0, "b", 0, 0, 0),
            (10.0, 200.0, 50.0, 210.0, "c", 0, 0, 0),
        ]
        page = _make_mock_page(words=words)
        ctx = TableContext(
            page=page,
            page_num=1,
            bbox=(0.0, 0.0, 500.0, 300.0),
            pdf_path=Path("/tmp/test.pdf"),
        )

        # First access
        rows1 = ctx.word_rows
        assert len(rows1) == 2  # Two distinct y-positions

        # Second access — cached, same object
        rows2 = ctx.word_rows
        assert rows2 is rows1

        # get_text("words") should have been called exactly once
        word_calls = [c for c in page.get_text.call_args_list if c[0][0] == "words"]
        assert len(word_calls) == 1

    def test_data_word_rows_excludes_caption(self) -> None:
        """Caption at y=100-120, word at y=110 (caption row), word at y=200 (data row).
        data_word_rows should only contain the y=200 row.
        """
        from zotero_chunk_rag.feature_extraction.captions import DetectedCaption

        words = [
            (10.0, 105.0, 50.0, 115.0, "caption_word", 0, 0, 0),  # y_mid=110
            (10.0, 195.0, 50.0, 205.0, "data_word", 0, 0, 0),     # y_mid=200
        ]
        page = _make_mock_page(words=words)
        caption = DetectedCaption(
            text="Table 1. Results",
            bbox=(0.0, 100.0, 500.0, 120.0),
            y_center=110.0,
            caption_type="table",
            number="1",
        )
        ctx = TableContext(
            page=page,
            page_num=1,
            bbox=(0.0, 0.0, 500.0, 300.0),
            pdf_path=Path("/tmp/test.pdf"),
            caption=caption,
        )

        data_rows = ctx.data_word_rows
        assert len(data_rows) == 1
        assert data_rows[0][0][4] == "data_word"

    def test_data_word_rows_no_caption(self) -> None:
        """No caption set. data_word_rows should equal word_rows."""
        words = [
            (10.0, 100.0, 50.0, 110.0, "a", 0, 0, 0),
            (10.0, 200.0, 50.0, 210.0, "b", 0, 0, 0),
        ]
        page = _make_mock_page(words=words)
        ctx = TableContext(
            page=page,
            page_num=1,
            bbox=(0.0, 0.0, 500.0, 300.0),
            pdf_path=Path("/tmp/test.pdf"),
        )

        assert ctx.data_word_rows == ctx.word_rows

    def test_caption_field(self) -> None:
        """Construct with a DetectedCaption, assert ctx.caption returns it."""
        from zotero_chunk_rag.feature_extraction.captions import DetectedCaption

        caption = DetectedCaption(
            text="Table 2. Demographics",
            bbox=(10.0, 50.0, 400.0, 70.0),
            y_center=60.0,
            caption_type="table",
            number="2",
        )
        page = _make_mock_page()
        ctx = TableContext(
            page=page,
            page_num=1,
            bbox=(0.0, 0.0, 500.0, 300.0),
            pdf_path=Path("/tmp/test.pdf"),
            caption=caption,
        )

        assert ctx.caption is caption
        assert ctx.caption.text == "Table 2. Demographics"
        assert ctx.caption.number == "2"


# ---------------------------------------------------------------------------
# TestPipelineConfig
# ---------------------------------------------------------------------------


class TestPipelineConfig:
    def test_with_overrides(self) -> None:
        # Create mock methods with name properties
        sm = MagicMock()
        sm.name = "struct1"
        cm = MagicMock()
        cm.name = "cell1"
        pp = MagicMock()
        pp.name = "post1"

        original = PipelineConfig(
            structure_methods=(sm,),
            cell_methods=(cm,),
            postprocessors=(pp,),
            activation_rules={},
            combination_strategy="expand_overlap",
            selection_strategy="rank_based",
        )

        overridden = original.with_overrides(selection_strategy="different")

        # New config has the changed field
        assert overridden.selection_strategy == "different"
        # New config preserves unchanged fields
        assert overridden.combination_strategy == "expand_overlap"
        assert overridden.structure_methods == (sm,)
        # Original is unchanged (frozen, but verify explicitly)
        assert original.selection_strategy == "rank_based"
        # Different instances
        assert original is not overridden
