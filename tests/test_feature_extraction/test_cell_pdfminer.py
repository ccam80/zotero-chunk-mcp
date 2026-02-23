"""Tests for PDFMiner (pdfplumber) cell extraction method."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zotero_chunk_rag.feature_extraction.methods.cell_pdfminer import PdfMinerExtraction
from zotero_chunk_rag.feature_extraction.models import CellGrid, TableContext
from zotero_chunk_rag.feature_extraction.protocols import CellExtractionMethod


def _make_mock_ctx(page_num: int = 0) -> MagicMock:
    """Create a mock TableContext for testing."""
    ctx = MagicMock(spec=TableContext)
    ctx.bbox = (0.0, 0.0, 200.0, 100.0)
    ctx.pdf_path = Path("/fake/path.pdf")
    ctx.page_num = page_num
    return ctx


def _mock_extract(method, ctx, col_boundaries, row_boundaries, mock_pdfplumber_mod):
    """Run extract with pdfplumber mocked at the sys.modules level."""
    real_mod = sys.modules.get("pdfplumber")
    sys.modules["pdfplumber"] = mock_pdfplumber_mod
    try:
        return method.extract(ctx, col_boundaries, row_boundaries)
    finally:
        if real_mod is not None:
            sys.modules["pdfplumber"] = real_mod
        else:
            sys.modules.pop("pdfplumber", None)


class TestPdfMiner:
    """Tests for PdfMinerExtraction class."""

    def test_protocol_conformance(self) -> None:
        """PdfMinerExtraction satisfies CellExtractionMethod protocol."""
        method = PdfMinerExtraction()
        assert isinstance(method, CellExtractionMethod)

    def test_returns_cellgrid(self) -> None:
        """Mock pdfplumber page returns CellGrid with method='pdfminer'."""
        method = PdfMinerExtraction()
        ctx = _make_mock_ctx()

        mock_cropped = MagicMock()
        mock_page = MagicMock()
        mock_page.crop.return_value = mock_cropped

        # 2x2 grid: 4 cells with text
        texts = iter(["H1", "H2", "A", "B"])
        mock_cropped.extract_text.side_effect = lambda: next(texts)

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]

        mock_pdfplumber_mod = MagicMock()
        mock_pdfplumber_mod.open.return_value = mock_pdf

        result = _mock_extract(
            method, ctx,
            col_boundaries=(100.0,),
            row_boundaries=(50.0,),
            mock_pdfplumber_mod=mock_pdfplumber_mod,
        )

        assert result is not None
        assert isinstance(result, CellGrid)
        assert result.method == "pdfminer"
        assert result.headers == ("H1", "H2")
        assert result.rows == (("A", "B"),)

    def test_empty_cell_handling(self) -> None:
        """pdfplumber returns None for empty region -> empty string in grid."""
        method = PdfMinerExtraction()
        ctx = _make_mock_ctx()

        mock_cropped = MagicMock()
        mock_page = MagicMock()
        mock_page.crop.return_value = mock_cropped

        # 2x2 grid, second and fourth cells return None (empty)
        texts = iter(["Header", None, "Data", None])
        mock_cropped.extract_text.side_effect = lambda: next(texts)

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]

        mock_pdfplumber_mod = MagicMock()
        mock_pdfplumber_mod.open.return_value = mock_pdf

        result = _mock_extract(
            method, ctx,
            col_boundaries=(100.0,),
            row_boundaries=(50.0,),
            mock_pdfplumber_mod=mock_pdfplumber_mod,
        )

        assert result is not None
        assert result.headers == ("Header", "")
        assert result.rows == (("Data", ""),)

    def test_pdf_opened_once(self) -> None:
        """pdfplumber.open called once per extract() call, not once per cell."""
        method = PdfMinerExtraction()
        ctx = _make_mock_ctx()

        mock_cropped = MagicMock()
        mock_cropped.extract_text.return_value = "text"
        mock_page = MagicMock()
        mock_page.crop.return_value = mock_cropped

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]

        mock_pdfplumber_mod = MagicMock()
        mock_pdfplumber_mod.open.return_value = mock_pdf

        result = _mock_extract(
            method, ctx,
            col_boundaries=(70.0, 140.0),
            row_boundaries=(33.0, 66.0),
            mock_pdfplumber_mod=mock_pdfplumber_mod,
        )

        # PDF opened exactly once despite 9 cells
        mock_pdfplumber_mod.open.assert_called_once_with(str(ctx.pdf_path))

        # Page crop called 9 times (once per cell)
        assert mock_page.crop.call_count == 9

    def test_returns_none_on_error(self) -> None:
        """pdfplumber.open raises -> returns None."""
        method = PdfMinerExtraction()
        ctx = _make_mock_ctx()

        mock_pdfplumber_mod = MagicMock()
        mock_pdfplumber_mod.open.side_effect = FileNotFoundError("no such file")

        result = _mock_extract(
            method, ctx,
            col_boundaries=(100.0,),
            row_boundaries=(50.0,),
            mock_pdfplumber_mod=mock_pdfplumber_mod,
        )

        assert result is None

    def test_name_property(self) -> None:
        """The name property returns 'pdfminer'."""
        method = PdfMinerExtraction()
        assert method.name == "pdfminer"
