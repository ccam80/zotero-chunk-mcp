"""Tests for HeaderDataSplit post-processor."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from zotero_chunk_rag.feature_extraction.models import CellGrid, TableContext
from zotero_chunk_rag.feature_extraction.postprocessors.header_data_split import (
    HeaderDataSplit,
)
from zotero_chunk_rag.feature_extraction.protocols import PostProcessor


def _make_ctx() -> MagicMock:
    ctx = MagicMock(spec=TableContext)
    ctx.dict_blocks = []
    return ctx


def _make_grid(
    headers: tuple[str, ...],
    rows: tuple[tuple[str, ...], ...] = (),
) -> CellGrid:
    return CellGrid(
        headers=headers,
        rows=rows,
        col_boundaries=(0.0, 100.0, 200.0),
        row_boundaries=(50.0,),
        method="test",
    )


class TestHeaderDataSplit:
    def test_fused_headers_split(self) -> None:
        """Headers 'Col A 0.5', 'Col B 0.3', 'Col C text'. Assert split."""
        grid = _make_grid(
            headers=("Col A 0.5", "Col B 0.3", "Col C text"),
            rows=(("1", "2", "3"),),
        )
        pp = HeaderDataSplit()
        result = pp.process(grid, _make_ctx())

        # 2 of 3 headers fused (66%) > 30% trigger
        assert result.headers[0] == "Col A"
        assert result.headers[1] == "Col B"
        # "Col C text" — "text" is not numeric, so not split
        assert result.headers[2] == "Col C text"
        # New data row inserted at position 0
        assert result.rows[0][0] == "0.5"
        assert result.rows[0][1] == "0.3"
        assert result.rows[0][2] == ""
        # Original data row at position 1
        assert result.rows[1] == ("1", "2", "3")

    def test_skip_model_numbers(self) -> None:
        """'Model 1' not split despite ending with a number."""
        grid = _make_grid(
            headers=("Model 1", "Model 2", "Estimate 0.5"),
            rows=(("a", "b", "c"),),
        )
        pp = HeaderDataSplit()
        result = pp.process(grid, _make_ctx())

        # Only 1 of 3 headers is truly fused (33%), "Model N" skipped
        # 1/3 = 33% >= 30%, so it triggers but only Estimate is split
        assert result.headers[0] == "Model 1"
        assert result.headers[1] == "Model 2"
        assert result.headers[2] == "Estimate"

    def test_below_trigger_fraction(self) -> None:
        """1 of 5 headers fused (20%). No split."""
        grid = _make_grid(
            headers=("A", "B", "C", "D", "E 0.5"),
            rows=(("1", "2", "3", "4", "5"),),
        )
        pp = HeaderDataSplit()
        result = pp.process(grid, _make_ctx())

        # 1/5 = 20% < 30% — no split
        assert result is grid

    def test_preserves_newlines(self) -> None:
        r"""``\n`` in header text is preserved in the split data portion."""
        grid = _make_grid(
            headers=("ZTA R1(Ohm)\n9982.", "Col B\n0.5"),
            rows=(("x", "y"),),
        )
        pp = HeaderDataSplit()
        result = pp.process(grid, _make_ctx())

        # Both fused (100%) > 30%
        assert result.headers[0] == "ZTA R1(Ohm)"
        # The data portion should contain the \n character from the original
        assert "9982." in result.rows[0][0]

    def test_no_fused_headers(self) -> None:
        """All text-only headers. Unchanged."""
        grid = _make_grid(
            headers=("Name", "Category", "Description"),
            rows=(("Alice", "A", "test"),),
        )
        pp = HeaderDataSplit()
        result = pp.process(grid, _make_ctx())

        assert result is grid

    def test_protocol_conformance(self) -> None:
        """HeaderDataSplit satisfies PostProcessor protocol."""
        pp = HeaderDataSplit()
        assert isinstance(pp, PostProcessor)
        assert pp.name == "header_data_split"
