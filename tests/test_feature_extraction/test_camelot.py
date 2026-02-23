"""Tests for Camelot structure methods."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zotero_chunk_rag.feature_extraction.methods.camelot_extraction import (
    CamelotHybrid,
    CamelotLattice,
    _bbox_to_camelot_area,
    _camelot_to_pymupdf_y,
    _has_ghostscript,
)
from zotero_chunk_rag.feature_extraction.models import TableContext
from zotero_chunk_rag.feature_extraction.protocols import StructureMethod


# ---------------------------------------------------------------------------
# Coordinate conversion
# ---------------------------------------------------------------------------

class TestCoordinateConversion:
    def test_bbox_to_area(self) -> None:
        """bbox (72, 200, 540, 600) on page height 792.

        pymupdf y0_top=200, y1_bottom=600
        Camelot y_top = 792-200 = 592, y_bottom = 792-600 = 192
        Result: "72,592,540,192"
        """
        result = _bbox_to_camelot_area((72, 200, 540, 600), 792)
        assert result == "72,592,540,192"

    def test_y_conversion(self) -> None:
        """_camelot_to_pymupdf_y(592, 792) -> 200.0."""
        assert _camelot_to_pymupdf_y(592, 792) == 200.0


# ---------------------------------------------------------------------------
# Ghostscript
# ---------------------------------------------------------------------------

class TestGhostscript:
    def test_ghostscript_available(self) -> None:
        """Assert Ghostscript is installed. FAILS (not skips) if missing."""
        available = _has_ghostscript()
        assert available, (
            "Ghostscript is NOT installed on this system. "
            "Install Ghostscript to enable Camelot lattice extraction. "
            "On Windows: choco install ghostscript. "
            "On Linux: apt install ghostscript."
        )


# ---------------------------------------------------------------------------
# CamelotLattice
# ---------------------------------------------------------------------------

class TestCamelotLattice:
    def test_protocol_conformance(self) -> None:
        assert isinstance(CamelotLattice(), StructureMethod)

    def test_name(self) -> None:
        assert CamelotLattice().name == "camelot_lattice"

    def test_confidence_from_accuracy(self) -> None:
        """Mock Camelot returning table with accuracy=85 -> confidence=0.85."""
        mock_table = MagicMock()
        mock_table.accuracy = 85.0
        # Cells in PDF coordinates: one 2x2 grid
        # PDF coords: (72, 592, 306, 392) and (306, 592, 540, 392)
        #             (72, 392, 306, 192) and (306, 392, 540, 192)
        mock_table.cells = [
            (72, 592, 306, 392),
            (306, 592, 540, 392),
            (72, 392, 306, 192),
            (306, 392, 540, 192),
        ]

        mock_tables = MagicMock()
        mock_tables.__len__ = lambda self: 1
        mock_tables.__iter__ = lambda self: iter([mock_table])
        mock_tables.__bool__ = lambda self: True

        mock_page = MagicMock()
        mock_page.get_text.return_value = []
        mock_page.get_drawings.return_value = []
        mock_page.rect = MagicMock()
        mock_page.rect.height = 792.0
        mock_page.rect.width = 612.0

        ctx = TableContext(
            page=mock_page,
            page_num=0,
            bbox=(72.0, 200.0, 540.0, 600.0),
            pdf_path=Path("test.pdf"),
        )

        with patch(
            "zotero_chunk_rag.feature_extraction.methods.camelot_extraction.camelot"
        ) as mock_camelot, patch(
            "zotero_chunk_rag.feature_extraction.methods.camelot_extraction._has_ghostscript",
            return_value=True,
        ):
            mock_camelot.read_pdf.return_value = mock_tables
            method = CamelotLattice()
            result = method.detect(ctx)

        assert result is not None
        assert result.col_boundaries[0].confidence == pytest.approx(0.85)


# ---------------------------------------------------------------------------
# CamelotHybrid
# ---------------------------------------------------------------------------

class TestCamelotHybrid:
    def test_protocol_conformance(self) -> None:
        assert isinstance(CamelotHybrid(), StructureMethod)

    def test_name(self) -> None:
        assert CamelotHybrid().name == "camelot_hybrid"
