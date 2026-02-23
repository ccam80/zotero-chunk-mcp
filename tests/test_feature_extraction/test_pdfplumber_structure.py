"""Tests for pdfplumber structure methods."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zotero_chunk_rag.feature_extraction.methods.pdfplumber_structure import (
    PdfplumberLines,
    PdfplumberText,
    _detect_with_strategy,
)
from zotero_chunk_rag.feature_extraction.models import TableContext
from zotero_chunk_rag.feature_extraction.protocols import StructureMethod


def _make_ctx(
    page_num: int = 0,
    bbox: tuple[float, float, float, float] = (72.0, 200.0, 540.0, 600.0),
) -> TableContext:
    """Create a TableContext with a mock pymupdf page."""
    mock_page = MagicMock()
    mock_page.get_text.return_value = []
    mock_page.get_drawings.return_value = []
    mock_page.rect = MagicMock()
    mock_page.rect.height = 792.0
    mock_page.rect.width = 612.0

    return TableContext(
        page=mock_page,
        page_num=page_num,
        bbox=bbox,
        pdf_path=Path("test.pdf"),
    )


# ---------------------------------------------------------------------------
# PdfplumberLines
# ---------------------------------------------------------------------------

class TestPdfplumberLines:
    def test_protocol_conformance(self) -> None:
        assert isinstance(PdfplumberLines(), StructureMethod)

    def test_name(self) -> None:
        assert PdfplumberLines().name == "pdfplumber_lines"

    def test_returns_none_no_tables(self) -> None:
        """When pdfplumber finds no tables, detect() returns None."""
        mock_cropped = MagicMock()
        mock_cropped.find_tables.return_value = []

        mock_plumber_page = MagicMock()
        mock_plumber_page.within_bbox.return_value = mock_cropped

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_plumber_page]
        mock_pdf.__enter__ = lambda self: self
        mock_pdf.__exit__ = MagicMock(return_value=False)

        ctx = _make_ctx()

        with patch(
            "zotero_chunk_rag.feature_extraction.methods.pdfplumber_structure.pdfplumber"
        ) as mock_pdfplumber:
            mock_pdfplumber.open.return_value = mock_pdf
            method = PdfplumberLines()
            result = method.detect(ctx)

        assert result is None


# ---------------------------------------------------------------------------
# PdfplumberText
# ---------------------------------------------------------------------------

class TestPdfplumberText:
    def test_protocol_conformance(self) -> None:
        assert isinstance(PdfplumberText(), StructureMethod)

    def test_name(self) -> None:
        assert PdfplumberText().name == "pdfplumber_text"


# ---------------------------------------------------------------------------
# No coordinate conversion
# ---------------------------------------------------------------------------

class TestPdfplumber:
    def test_no_coordinate_conversion(self) -> None:
        """Verify that pdfplumber cell bboxes are used directly without conversion.

        Create mock pdfplumber table with known cell bboxes and verify the
        resulting boundary positions match the raw values.
        """
        mock_table = MagicMock()
        # 2x2 grid: cells at known positions
        mock_table.cells = [
            (72.0, 200.0, 306.0, 400.0),
            (306.0, 200.0, 540.0, 400.0),
            (72.0, 400.0, 306.0, 600.0),
            (306.0, 400.0, 540.0, 600.0),
        ]

        mock_cropped = MagicMock()
        mock_cropped.find_tables.return_value = [mock_table]

        mock_plumber_page = MagicMock()
        mock_plumber_page.within_bbox.return_value = mock_cropped

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_plumber_page]

        ctx = _make_ctx()

        with patch(
            "zotero_chunk_rag.feature_extraction.methods.pdfplumber_structure.pdfplumber"
        ) as mock_pdfplumber:
            mock_pdfplumber.open.return_value = mock_pdf
            method = PdfplumberLines()
            result = method.detect(ctx)

        assert result is not None
        # Column boundary: 306.0 (the only internal x0)
        assert len(result.col_boundaries) == 1
        assert result.col_boundaries[0].min_pos == 306.0
        # Row boundary: 400.0 (the only internal y0)
        assert len(result.row_boundaries) == 1
        assert result.row_boundaries[0].min_pos == 400.0
