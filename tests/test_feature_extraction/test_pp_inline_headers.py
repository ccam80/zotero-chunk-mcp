"""Tests for InlineHeaderFill post-processor."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from zotero_chunk_rag.feature_extraction.models import CellGrid, TableContext
from zotero_chunk_rag.feature_extraction.postprocessors.inline_headers import (
    InlineHeaderFill,
    _find_exclusive_or_column,
)
from zotero_chunk_rag.feature_extraction.protocols import PostProcessor


def _make_ctx() -> MagicMock:
    ctx = MagicMock(spec=TableContext)
    ctx.dict_blocks = []
    return ctx


def _make_grid(
    rows: tuple[tuple[str, ...], ...],
    headers: tuple[str, ...] = ("Group", "Metric", "Value"),
) -> CellGrid:
    return CellGrid(
        headers=headers,
        rows=rows,
        col_boundaries=(0.0, 100.0, 200.0),
        row_boundaries=(50.0,),
        method="test",
    )


class TestInlineHeaders:
    def test_forward_fill(self) -> None:
        """'Baseline'/'Convers.' forward-filled. Header rows removed."""
        grid = _make_grid(
            rows=(
                ("Baseline", "", ""),           # inline header
                ("", "Accuracy", "0.95"),        # data row
                ("", "F1", "0.90"),              # data row
                ("Conversational", "", ""),       # inline header
                ("", "Accuracy", "0.88"),        # data row
                ("", "F1", "0.85"),              # data row
            ),
        )
        pp = InlineHeaderFill()
        result = pp.process(grid, _make_ctx())

        # Header rows removed, 4 data rows remain
        assert len(result.rows) == 4
        assert result.rows[0] == ("Baseline", "Accuracy", "0.95")
        assert result.rows[1] == ("Baseline", "F1", "0.90")
        assert result.rows[2] == ("Conversational", "Accuracy", "0.88")
        assert result.rows[3] == ("Conversational", "F1", "0.85")

    def test_no_exclusive_or_column(self) -> None:
        """All columns populated in every row. Unchanged."""
        grid = _make_grid(
            rows=(
                ("A", "B", "C"),
                ("D", "E", "F"),
                ("G", "H", "I"),
            ),
        )
        pp = InlineHeaderFill()
        result = pp.process(grid, _make_ctx())

        assert result is grid

    def test_multiple_groups(self) -> None:
        """Two header groups with correct boundaries."""
        grid = _make_grid(
            rows=(
                ("Males", "", ""),
                ("", "Height", "175"),
                ("", "Weight", "80"),
                ("Females", "", ""),
                ("", "Height", "165"),
                ("", "Weight", "60"),
            ),
        )
        pp = InlineHeaderFill()
        result = pp.process(grid, _make_ctx())

        assert len(result.rows) == 4
        assert result.rows[0][0] == "Males"
        assert result.rows[1][0] == "Males"
        assert result.rows[2][0] == "Females"
        assert result.rows[3][0] == "Females"

    def test_protocol_conformance(self) -> None:
        """InlineHeaderFill satisfies PostProcessor protocol."""
        pp = InlineHeaderFill()
        assert isinstance(pp, PostProcessor)
        assert pp.name == "inline_header_fill"
