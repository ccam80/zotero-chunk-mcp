"""Tests for rawdict cell extraction method."""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from zotero_chunk_rag.feature_extraction.methods.cell_rawdict import (
    RawdictExtraction,
    _build_cell_bboxes,
)
from zotero_chunk_rag.feature_extraction.models import CellGrid, TableContext
from zotero_chunk_rag.feature_extraction.protocols import CellExtractionMethod


class TestBuildCellBboxes:
    """Tests for _build_cell_bboxes helper."""

    def test_2x3_grid(self) -> None:
        """2 rows, 3 cols: 6 cell bboxes with correct coordinates."""
        col_bounds = (100.0, 200.0)  # 2 internal boundaries -> 3 columns
        row_bounds = (50.0,)  # 1 internal boundary -> 2 rows
        table_bbox = (0.0, 0.0, 300.0, 100.0)

        bboxes = _build_cell_bboxes(col_bounds, row_bounds, table_bbox)

        assert len(bboxes) == 6

        # Row 0: y from 0 to 50
        assert bboxes[0] == (0.0, 0.0, 100.0, 50.0)    # col 0
        assert bboxes[1] == (100.0, 0.0, 200.0, 50.0)   # col 1
        assert bboxes[2] == (200.0, 0.0, 300.0, 50.0)   # col 2

        # Row 1: y from 50 to 100
        assert bboxes[3] == (0.0, 50.0, 100.0, 100.0)   # col 0
        assert bboxes[4] == (100.0, 50.0, 200.0, 100.0)  # col 1
        assert bboxes[5] == (200.0, 50.0, 300.0, 100.0)  # col 2

    def test_uses_table_bbox_edges(self) -> None:
        """Leftmost cells use table bbox x0, rightmost use x1."""
        col_bounds = (150.0,)  # 1 internal boundary -> 2 columns
        row_bounds = (60.0,)   # 1 internal boundary -> 2 rows
        table_bbox = (10.0, 20.0, 300.0, 120.0)

        bboxes = _build_cell_bboxes(col_bounds, row_bounds, table_bbox)

        assert len(bboxes) == 4

        # Leftmost cells start at table bbox x0 (10.0)
        assert bboxes[0][0] == 10.0   # row 0, col 0 -> x0 = table x0
        assert bboxes[2][0] == 10.0   # row 1, col 0 -> x0 = table x0

        # Rightmost cells end at table bbox x1 (300.0)
        assert bboxes[1][2] == 300.0  # row 0, col 1 -> x1 = table x1
        assert bboxes[3][2] == 300.0  # row 1, col 1 -> x1 = table x1

        # Top row starts at table bbox y0 (20.0)
        assert bboxes[0][1] == 20.0
        assert bboxes[1][1] == 20.0

        # Bottom row ends at table bbox y1 (120.0)
        assert bboxes[2][3] == 120.0
        assert bboxes[3][3] == 120.0


def _mock_extract(method: RawdictExtraction, ctx, col_boundaries, row_boundaries, mock_table_mod):
    """Run extract with pymupdf.table mocked at the sys.modules level."""
    real_mod = sys.modules.get("pymupdf.table")
    sys.modules["pymupdf.table"] = mock_table_mod
    try:
        return method.extract(ctx, col_boundaries, row_boundaries)
    finally:
        if real_mod is not None:
            sys.modules["pymupdf.table"] = real_mod
        else:
            sys.modules.pop("pymupdf.table", None)


class TestRawdict:
    """Tests for RawdictExtraction class."""

    def test_protocol_conformance(self) -> None:
        """RawdictExtraction satisfies CellExtractionMethod protocol."""
        method = RawdictExtraction()
        assert isinstance(method, CellExtractionMethod)

    def test_returns_cellgrid(self) -> None:
        """Mock textpage extraction returns CellGrid with correct method name."""
        method = RawdictExtraction()

        ctx = MagicMock(spec=TableContext)
        ctx.bbox = (0.0, 0.0, 200.0, 100.0)

        mock_table_mod = MagicMock()
        mock_table_mod.TEXTPAGE = MagicMock()
        cell_texts = ["H1", "H2", "A", "B"]
        mock_table_mod.extract_cells = MagicMock(side_effect=cell_texts)

        result = _mock_extract(
            method, ctx,
            col_boundaries=(100.0,),
            row_boundaries=(50.0,),
            mock_table_mod=mock_table_mod,
        )

        assert result is not None
        assert isinstance(result, CellGrid)
        assert result.method == "rawdict"
        assert result.headers == ("H1", "H2")
        assert result.rows == (("A", "B"),)

    def test_returns_none_no_textpage(self) -> None:
        """No TEXTPAGE available -> returns None."""
        method = RawdictExtraction()
        ctx = MagicMock(spec=TableContext)
        ctx.bbox = (0.0, 0.0, 200.0, 100.0)

        mock_table_mod = MagicMock()
        mock_table_mod.TEXTPAGE = None

        result = _mock_extract(
            method, ctx,
            col_boundaries=(100.0,),
            row_boundaries=(50.0,),
            mock_table_mod=mock_table_mod,
        )

        assert result is None

    def test_first_row_is_headers(self) -> None:
        """grid.headers comes from the first row of extracted data."""
        method = RawdictExtraction()

        ctx = MagicMock(spec=TableContext)
        ctx.bbox = (0.0, 0.0, 300.0, 150.0)

        mock_table_mod = MagicMock()
        mock_table_mod.TEXTPAGE = MagicMock()
        texts = ["Name", "Age", "City",
                 "Alice", "30", "NYC",
                 "Bob", "25", "LA"]
        mock_table_mod.extract_cells = MagicMock(side_effect=texts)

        result = _mock_extract(
            method, ctx,
            col_boundaries=(100.0, 200.0),
            row_boundaries=(50.0, 100.0),
            mock_table_mod=mock_table_mod,
        )

        assert result is not None
        assert result.headers == ("Name", "Age", "City")
        assert result.rows == (
            ("Alice", "30", "NYC"),
            ("Bob", "25", "LA"),
        )

    def test_name_property(self) -> None:
        """The name property returns 'rawdict'."""
        method = RawdictExtraction()
        assert method.name == "rawdict"

    def test_empty_cells_become_empty_strings(self) -> None:
        """Cells where extract_cells returns empty/None become empty strings."""
        method = RawdictExtraction()
        ctx = MagicMock(spec=TableContext)
        ctx.bbox = (0.0, 0.0, 200.0, 100.0)

        mock_table_mod = MagicMock()
        mock_table_mod.TEXTPAGE = MagicMock()
        mock_table_mod.extract_cells = MagicMock(side_effect=["H1", None, "val", ""])

        result = _mock_extract(
            method, ctx,
            col_boundaries=(100.0,),
            row_boundaries=(50.0,),
            mock_table_mod=mock_table_mod,
        )

        assert result is not None
        assert result.headers == ("H1", "")
        assert result.rows == (("val", ""),)
