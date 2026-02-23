"""Tests for ContinuationMerge post-processor."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from zotero_chunk_rag.feature_extraction.models import CellGrid, TableContext
from zotero_chunk_rag.feature_extraction.postprocessors.continuation_merge import (
    ContinuationMerge,
    _is_continuation,
)
from zotero_chunk_rag.feature_extraction.protocols import PostProcessor


def _make_ctx() -> MagicMock:
    ctx = MagicMock(spec=TableContext)
    ctx.dict_blocks = []
    return ctx


def _make_grid(
    rows: tuple[tuple[str, ...], ...],
    headers: tuple[str, ...] = ("Col A", "Col B", "Col C"),
) -> CellGrid:
    return CellGrid(
        headers=headers,
        rows=rows,
        col_boundaries=(0.0, 100.0, 200.0),
        row_boundaries=(50.0,),
        method="test",
    )


class TestContinuationMerge:
    def test_simple_continuation(self) -> None:
        """Anchor ['A', 'long text', 'C'], continuation ['', 'continued', '']. Merged."""
        grid = _make_grid(
            rows=(
                ("A", "long text", "C"),
                ("", "continued", ""),
            ),
        )
        pp = ContinuationMerge()
        result = pp.process(grid, _make_ctx())

        assert len(result.rows) == 1
        assert result.rows[0] == ("A", "long text continued", "C")

    def test_non_adjacent_not_merged(self) -> None:
        """Cols 0, 2 populated (gap at col 1). NOT merged."""
        grid = _make_grid(
            rows=(
                ("A", "B", "C"),
                ("extra", "", "extra"),
            ),
        )
        pp = ContinuationMerge()
        result = pp.process(grid, _make_ctx())

        # Cols {0, 2} are not adjacent — not a continuation
        assert len(result.rows) == 2

    def test_not_subset_not_merged(self) -> None:
        """Col 2 populated in candidate but anchor only has 0, 1. NOT merged."""
        grid = _make_grid(
            rows=(
                ("A", "B", ""),
                ("", "", "extra"),
            ),
        )
        pp = ContinuationMerge()
        result = pp.process(grid, _make_ctx())

        # {2} is not subset of {0, 1}
        assert len(result.rows) == 2

    def test_multiple_continuations(self) -> None:
        """Anchor + 3 continuations. All merged."""
        grid = _make_grid(
            rows=(
                ("Name", "A very long description", "Value"),
                ("", "that continues here", ""),
                ("", "and here too", ""),
                ("", "final part", ""),
            ),
        )
        pp = ContinuationMerge()
        result = pp.process(grid, _make_ctx())

        assert len(result.rows) == 1
        assert "A very long description that continues here and here too final part" == result.rows[0][1]
        assert result.rows[0][0] == "Name"
        assert result.rows[0][2] == "Value"

    def test_new_anchor_after_data(self) -> None:
        """Correct anchor switching: row 0 is anchor, row 1 is continuation, row 2 is new anchor."""
        grid = _make_grid(
            rows=(
                ("A", "text1", "C"),
                ("", "cont1", ""),
                ("B", "text2", "D"),
                ("", "cont2", ""),
            ),
        )
        pp = ContinuationMerge()
        result = pp.process(grid, _make_ctx())

        assert len(result.rows) == 2
        assert result.rows[0] == ("A", "text1 cont1", "C")
        assert result.rows[1] == ("B", "text2 cont2", "D")

    def test_no_continuations(self) -> None:
        """All rows are full data — unchanged."""
        grid = _make_grid(
            rows=(
                ("A", "B", "C"),
                ("D", "E", "F"),
                ("G", "H", "I"),
            ),
        )
        pp = ContinuationMerge()
        result = pp.process(grid, _make_ctx())

        assert result is grid

    def test_protocol_conformance(self) -> None:
        """ContinuationMerge satisfies PostProcessor protocol."""
        pp = ContinuationMerge()
        assert isinstance(pp, PostProcessor)
        assert pp.name == "continuation_merge"
