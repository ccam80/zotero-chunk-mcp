"""Tests for PyMuPDF find_tables structure methods."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zotero_chunk_rag.feature_extraction.methods.pymupdf_tables import (
    PyMuPDFLines,
    PyMuPDFLinesStrict,
    PyMuPDFText,
    _boundaries_from_cells,
    _grid_regularity,
)
from zotero_chunk_rag.feature_extraction.models import TableContext
from zotero_chunk_rag.feature_extraction.protocols import StructureMethod


# ---------------------------------------------------------------------------
# _boundaries_from_cells
# ---------------------------------------------------------------------------

class TestBoundariesFromCells:
    def test_regular_grid(self) -> None:
        """3x4 grid of cell bboxes: 4 columns, 3 rows.

        Cells arranged as:
        Row 0: (0,0,10,10) (10,0,20,10) (20,0,30,10) (30,0,40,10)
        Row 1: (0,10,10,20) (10,10,20,20) (20,10,30,20) (30,10,40,20)
        Row 2: (0,20,10,30) (10,20,20,30) (20,20,30,30) (30,20,40,30)

        x0 unique values: 0, 10, 20, 30 -> col boundaries: 10, 20, 30 (excluding 0)
        y0 unique values: 0, 10, 20 -> row boundaries: 10, 20 (excluding 0)
        """
        cells = []
        for row in range(3):
            for col in range(4):
                cells.append((col * 10.0, row * 10.0, (col + 1) * 10.0, (row + 1) * 10.0))

        col_b, row_b = _boundaries_from_cells(cells)
        assert col_b == (10.0, 20.0, 30.0)
        assert row_b == (10.0, 20.0)

    def test_single_cell(self) -> None:
        """One cell should produce empty boundaries (no internal boundaries)."""
        cells = [(50.0, 100.0, 200.0, 300.0)]
        col_b, row_b = _boundaries_from_cells(cells)
        assert col_b == ()
        assert row_b == ()


# ---------------------------------------------------------------------------
# _grid_regularity
# ---------------------------------------------------------------------------

class TestGridRegularity:
    def test_all_same(self) -> None:
        """All rows have 4 cols -> regularity = 1.0."""
        cells = []
        for row in range(5):
            for col in range(4):
                cells.append((col * 10.0, row * 10.0, (col + 1) * 10.0, (row + 1) * 10.0))

        assert _grid_regularity(cells) == 1.0

    def test_mixed(self) -> None:
        """3 rows with 4 cols, 2 rows with 3 cols -> regularity = 0.6."""
        cells = []
        # 3 rows with 4 cols
        for row in range(3):
            for col in range(4):
                cells.append((col * 10.0, row * 10.0, (col + 1) * 10.0, (row + 1) * 10.0))
        # 2 rows with 3 cols
        for row in range(3, 5):
            for col in range(3):
                cells.append((col * 10.0, row * 10.0, (col + 1) * 10.0, (row + 1) * 10.0))

        assert _grid_regularity(cells) == pytest.approx(0.6)


# ---------------------------------------------------------------------------
# PyMuPDFLines
# ---------------------------------------------------------------------------

class TestPyMuPDFLines:
    def test_protocol_conformance(self) -> None:
        """PyMuPDFLines satisfies StructureMethod protocol."""
        assert isinstance(PyMuPDFLines(), StructureMethod)

    def test_name(self) -> None:
        assert PyMuPDFLines().name == "pymupdf_lines"

    def test_returns_none_no_tables(self) -> None:
        """When find_tables returns empty list, detect() returns None."""
        mock_page = MagicMock()
        mock_result = MagicMock()
        mock_result.tables = []
        mock_page.find_tables.return_value = mock_result
        mock_page.get_text.return_value = []
        mock_page.get_drawings.return_value = []
        mock_page.rect = MagicMock()
        mock_page.rect.height = 792.0
        mock_page.rect.width = 612.0

        ctx = TableContext(
            page=mock_page,
            page_num=0,
            bbox=(72.0, 100.0, 540.0, 400.0),
            pdf_path=Path("test.pdf"),
        )

        method = PyMuPDFLines()
        result = method.detect(ctx)
        assert result is None


# ---------------------------------------------------------------------------
# PyMuPDFLinesStrict
# ---------------------------------------------------------------------------

class TestPyMuPDFLinesStrict:
    def test_name(self) -> None:
        assert PyMuPDFLinesStrict().name == "pymupdf_lines_strict"

    def test_protocol_conformance(self) -> None:
        assert isinstance(PyMuPDFLinesStrict(), StructureMethod)


# ---------------------------------------------------------------------------
# PyMuPDFText
# ---------------------------------------------------------------------------

class TestPyMuPDFText:
    def test_name(self) -> None:
        assert PyMuPDFText().name == "pymupdf_text"

    def test_protocol_conformance(self) -> None:
        assert isinstance(PyMuPDFText(), StructureMethod)
