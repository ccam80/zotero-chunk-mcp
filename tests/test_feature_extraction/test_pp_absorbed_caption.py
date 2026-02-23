"""Tests for AbsorbedCaptionStrip post-processor."""
from __future__ import annotations

import inspect
from unittest.mock import MagicMock

import pytest

from zotero_chunk_rag.feature_extraction.models import CellGrid, TableContext
from zotero_chunk_rag.feature_extraction.postprocessors.absorbed_caption import (
    AbsorbedCaptionStrip,
)
from zotero_chunk_rag.feature_extraction.protocols import PostProcessor


def _make_ctx() -> TableContext:
    ctx = MagicMock(spec=TableContext)
    ctx.dict_blocks = []
    return ctx


def _make_grid(
    headers: tuple[str, ...] = (),
    rows: tuple[tuple[str, ...], ...] = (),
) -> CellGrid:
    return CellGrid(
        headers=headers,
        rows=rows,
        col_boundaries=(0.0, 100.0, 200.0),
        row_boundaries=(50.0,),
        method="test",
    )


class TestAbsorbedCaption:
    def test_removes_caption_row(self) -> None:
        """Grid where row 0 is 'Table 1. Results' in col 0, rest empty. Assert row removed."""
        grid = _make_grid(
            headers=("Col A", "Col B", "Col C"),
            rows=(
                ("Table 1. Results of the experiment", "", ""),
                ("data1", "data2", "data3"),
            ),
        )
        pp = AbsorbedCaptionStrip()
        result = pp.process(grid, _make_ctx())

        assert len(result.rows) == 1
        assert result.rows[0] == ("data1", "data2", "data3")
        assert result.headers == ("Col A", "Col B", "Col C")

    def test_removes_caption_in_headers(self) -> None:
        """Headers contain 'Table 1...' in first position. Assert headers cleared."""
        grid = _make_grid(
            headers=("Table 1. Summary statistics", "", ""),
            rows=(
                ("data1", "data2", "data3"),
            ),
        )
        pp = AbsorbedCaptionStrip()
        result = pp.process(grid, _make_ctx())

        # All headers were empty after clearing -> headers dropped
        assert result.headers == ()
        assert result.rows == (("data1", "data2", "data3"),)

    def test_no_early_exit(self) -> None:
        """Row 0 = equation, row 1 = caption, row 2 = data. Assert row 1 removed, rows 0 and 2 kept."""
        grid = _make_grid(
            headers=("Col A", "Col B"),
            rows=(
                ("y = mx + b", "equation text"),         # row 0: not a caption
                ("Table 2. Regression results", ""),       # row 1: caption
                ("0.95", "0.87"),                           # row 2: data
            ),
        )
        pp = AbsorbedCaptionStrip()
        result = pp.process(grid, _make_ctx())

        assert len(result.rows) == 2
        assert result.rows[0] == ("y = mx + b", "equation text")
        assert result.rows[1] == ("0.95", "0.87")

    def test_no_match_passthrough(self) -> None:
        """No caption patterns. Grid returned unchanged."""
        grid = _make_grid(
            headers=("Name", "Value"),
            rows=(
                ("Alice", "100"),
                ("Bob", "200"),
            ),
        )
        pp = AbsorbedCaptionStrip()
        result = pp.process(grid, _make_ctx())

        assert result is grid  # Same object returned

    def test_imports_from_captions(self) -> None:
        """Assert caption regex imported from captions.py, not defined locally."""
        import zotero_chunk_rag.feature_extraction.postprocessors.absorbed_caption as mod

        source = inspect.getsource(mod)
        assert "from ..captions import" in source or "from zotero_chunk_rag.feature_extraction.captions import" in source

    def test_protocol_conformance(self) -> None:
        """AbsorbedCaptionStrip satisfies PostProcessor protocol."""
        pp = AbsorbedCaptionStrip()
        assert isinstance(pp, PostProcessor)
        assert pp.name == "absorbed_caption_strip"
