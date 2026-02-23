"""Tests for FootnoteStrip post-processor."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from zotero_chunk_rag.feature_extraction.models import CellGrid, TableContext
from zotero_chunk_rag.feature_extraction.postprocessors.footnote_strip import (
    FootnoteStrip,
    _is_footnote_row,
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


class TestFootnoteStrip:
    def test_strips_note_row(self) -> None:
        """'Note: * p < 0.05' stripped (2 signals: pattern + single cell)."""
        grid = _make_grid(
            rows=(
                ("data1", "data2", "data3"),
                ("data4", "data5", "data6"),
                ("Note: * p < 0.05, ** p < 0.01. Standard errors in parentheses.", "", ""),
            ),
        )
        pp = FootnoteStrip()
        result = pp.process(grid, _make_ctx())

        assert len(result.rows) == 2
        assert result.rows[0] == ("data1", "data2", "data3")
        assert result.rows[1] == ("data4", "data5", "data6")

    def test_strips_dagger_row(self) -> None:
        """'\\u2020 Adjusted...' stripped (2 signals: marker + single cell)."""
        grid = _make_grid(
            rows=(
                ("data1", "data2", "data3"),
                ("\u2020 Adjusted for baseline characteristics and demographic covariates.", "", ""),
            ),
        )
        pp = FootnoteStrip()
        result = pp.process(grid, _make_ctx())

        assert len(result.rows) == 1
        assert result.rows[0] == ("data1", "data2", "data3")

    def test_single_signal_not_stripped(self) -> None:
        """'Note' with all cols populated fires only 1 signal. NOT stripped."""
        grid = _make_grid(
            rows=(
                ("data1", "data2", "data3"),
                ("Note: a", "Note: b", "Note: c"),  # 3 non-empty cells, not spanning
            ),
        )
        pp = FootnoteStrip()
        result = pp.process(grid, _make_ctx())

        # Single signal (footnote pattern) but NOT single-cell AND cell length
        # not an outlier (short text) -> only 1 signal, not stripped
        assert len(result.rows) == 2

    def test_stops_at_data_row(self) -> None:
        """Only bottom consecutive footnotes stripped, not ones above data."""
        grid = _make_grid(
            rows=(
                ("data1", "data2", "data3"),
                ("data4", "data5", "data6"),
                ("Note: First footnote about methodology and statistical approach used.", "", ""),
                ("Source: National statistical database of health outcomes 2023.", "", ""),
            ),
        )
        pp = FootnoteStrip()
        result = pp.process(grid, _make_ctx())

        assert len(result.rows) == 2
        assert result.rows[1] == ("data4", "data5", "data6")

    def test_no_footnotes(self) -> None:
        """No footnotes present. Unchanged."""
        grid = _make_grid(
            rows=(
                ("A", "B", "C"),
                ("D", "E", "F"),
            ),
        )
        pp = FootnoteStrip()
        result = pp.process(grid, _make_ctx())

        assert result is grid

    def test_protocol_conformance(self) -> None:
        """FootnoteStrip satisfies PostProcessor protocol."""
        pp = FootnoteStrip()
        assert isinstance(pp, PostProcessor)
        assert pp.name == "footnote_strip"
