"""Tests for ruled line detection structure method."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, PropertyMock

import pymupdf
import pytest

from zotero_chunk_rag.feature_extraction.methods.ruled_lines import (
    RuledLineDetection,
    _classify_line,
    _clip_to_bbox,
    _extract_lines,
)
from zotero_chunk_rag.feature_extraction.models import TableContext
from zotero_chunk_rag.feature_extraction.protocols import StructureMethod


# ---------------------------------------------------------------------------
# _classify_line
# ---------------------------------------------------------------------------

class TestClassifyLine:
    def test_horizontal(self) -> None:
        assert _classify_line((50, 100), (500, 100)) == "horizontal"

    def test_vertical(self) -> None:
        assert _classify_line((200, 50), (200, 400)) == "vertical"

    def test_diagonal(self) -> None:
        assert _classify_line((50, 50), (500, 400)) is None

    def test_near_horizontal(self) -> None:
        """Line from (50,100) to (500,104) — < 5 degrees from horizontal."""
        result = _classify_line((50, 100), (500, 104))
        assert result == "horizontal"


# ---------------------------------------------------------------------------
# _clip_to_bbox
# ---------------------------------------------------------------------------

class TestClipToBbox:
    def test_line_extends_beyond(self) -> None:
        """Line from (30,100) to (600,100), bbox (50,50,550,400).
        Should clip to (50,100)-(550,100)."""
        clipped = _clip_to_bbox((30, 100), (600, 100), (50, 50, 550, 400))
        assert clipped == ((50, 100), (550, 100))

    def test_line_within_bbox(self) -> None:
        """Line entirely within bbox should be unchanged."""
        clipped = _clip_to_bbox((100, 100), (400, 100), (50, 50, 550, 400))
        assert clipped == ((100, 100), (400, 100))


# ---------------------------------------------------------------------------
# RuledLineDetection
# ---------------------------------------------------------------------------

def _make_ctx_with_drawings(
    drawings: list[dict],
    bbox: tuple[float, float, float, float] = (50.0, 50.0, 550.0, 400.0),
    median_word_height: float = 12.0,
) -> TableContext:
    """Create a TableContext with mocked drawings and word height."""
    mock_page = MagicMock()
    mock_page.get_drawings.return_value = []
    mock_page.get_text.return_value = []
    mock_page.rect = MagicMock()
    mock_page.rect.height = 792.0
    mock_page.rect.width = 612.0

    ctx = TableContext(
        page=mock_page,
        page_num=0,
        bbox=bbox,
        pdf_path=Path("test.pdf"),
    )

    # Override cached properties
    ctx.__dict__["drawings"] = drawings
    ctx.__dict__["median_word_height"] = median_word_height
    return ctx


def _make_drawing_with_line(
    p1: tuple[float, float], p2: tuple[float, float],
) -> dict:
    """Create a drawing dict containing a single line item."""
    return {
        "items": [
            ("l", pymupdf.Point(p1[0], p1[1]), pymupdf.Point(p2[0], p2[1])),
        ],
        "rect": (
            min(p1[0], p2[0]),
            min(p1[1], p2[1]),
            max(p1[0], p2[0]),
            max(p1[1], p2[1]),
        ),
    }


class TestRuledLines:
    def test_full_width_line(self) -> None:
        """Horizontal line spanning full bbox width -> confidence ~ 1.0."""
        bbox = (50.0, 50.0, 550.0, 400.0)
        drawings = [_make_drawing_with_line((50.0, 200.0), (550.0, 200.0))]
        ctx = _make_ctx_with_drawings(drawings, bbox=bbox)

        method = RuledLineDetection()
        result = method.detect(ctx)

        assert result is not None
        assert len(result.row_boundaries) == 1
        assert result.row_boundaries[0].confidence == pytest.approx(1.0, abs=0.01)

    def test_partial_line(self) -> None:
        """Horizontal line spanning 50% of bbox width -> confidence ~ 0.5."""
        bbox = (50.0, 50.0, 550.0, 400.0)
        # Line from 175 to 425 = 250pt out of 500pt width
        drawings = [_make_drawing_with_line((175.0, 200.0), (425.0, 200.0))]
        ctx = _make_ctx_with_drawings(drawings, bbox=bbox)

        method = RuledLineDetection()
        result = method.detect(ctx)

        assert result is not None
        assert len(result.row_boundaries) == 1
        assert result.row_boundaries[0].confidence == pytest.approx(0.5, abs=0.01)

    def test_no_lines(self) -> None:
        """No drawings -> returns None."""
        ctx = _make_ctx_with_drawings([])
        method = RuledLineDetection()
        result = method.detect(ctx)
        assert result is None

    def test_both_axes(self) -> None:
        """Horizontal + vertical lines -> both row and column boundaries."""
        bbox = (50.0, 50.0, 550.0, 400.0)
        drawings = [
            _make_drawing_with_line((50.0, 200.0), (550.0, 200.0)),  # horizontal
            _make_drawing_with_line((300.0, 50.0), (300.0, 400.0)),  # vertical
        ]
        ctx = _make_ctx_with_drawings(drawings, bbox=bbox)

        method = RuledLineDetection()
        result = method.detect(ctx)

        assert result is not None
        assert len(result.row_boundaries) >= 1
        assert len(result.col_boundaries) >= 1

    def test_nearby_lines_clustered(self) -> None:
        """Two horizontal lines at y=200.0 and y=200.5 -> one merged boundary."""
        bbox = (50.0, 50.0, 550.0, 400.0)
        drawings = [
            _make_drawing_with_line((50.0, 200.0), (550.0, 200.0)),
            _make_drawing_with_line((50.0, 200.5), (550.0, 200.5)),
        ]
        # median_word_height=12 -> tolerance=6.0, well above 0.5 difference
        ctx = _make_ctx_with_drawings(drawings, bbox=bbox, median_word_height=12.0)

        method = RuledLineDetection()
        result = method.detect(ctx)

        assert result is not None
        assert len(result.row_boundaries) == 1

    def test_protocol_conformance(self) -> None:
        """RuledLineDetection satisfies StructureMethod protocol."""
        assert isinstance(RuledLineDetection(), StructureMethod)
