"""Tests for figure detection module."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pymupdf
import pytest

from zotero_chunk_rag.feature_extraction.captions import DetectedCaption
from zotero_chunk_rag.feature_extraction.methods.figure_detection import (
    detect_figures,
    render_figure,
)


def _make_caption(
    text: str,
    bbox: tuple = (50, 300, 400, 320),
    number: str | None = "1",
) -> DetectedCaption:
    """Create a DetectedCaption for testing."""
    return DetectedCaption(
        text=text,
        bbox=bbox,
        y_center=(bbox[1] + bbox[3]) / 2,
        caption_type="figure",
        number=number,
    )


def _make_page_chunk(
    page_number: int = 1,
    boxes: list[dict] | None = None,
) -> dict:
    """Create a mock page chunk dict."""
    return {
        "metadata": {"page_number": page_number},
        "page_boxes": boxes or [],
    }


def _make_mock_page(
    width: float = 595.0,
    height: float = 842.0,
    image_infos: list[dict] | None = None,
) -> MagicMock:
    """Create a mock pymupdf page."""
    page = MagicMock()
    rect = pymupdf.Rect(0, 0, width, height)
    page.rect = rect
    page.get_image_info = MagicMock(return_value=image_infos or [])
    return page


class TestDetectFigures:
    def test_with_picture_boxes(self) -> None:
        """Mock page_chunk with picture boxes, assert correct bboxes returned."""
        page = _make_mock_page()
        chunk = _make_page_chunk(boxes=[
            {"class": "picture", "bbox": [50, 100, 400, 280]},
        ])
        captions = [_make_caption("Figure 1: Example", bbox=(50, 290, 400, 310))]

        results = detect_figures(page, chunk, captions)

        assert len(results) == 1
        bbox, caption_text = results[0]
        assert bbox[0] == pytest.approx(50, abs=1)
        assert bbox[1] == pytest.approx(100, abs=1)
        assert caption_text == "Figure 1: Example"

    def test_image_info_fallback(self) -> None:
        """No picture boxes, mock page.get_image_info() returns images."""
        page = _make_mock_page(image_infos=[
            {"bbox": (50, 100, 400, 280)},
        ])
        chunk = _make_page_chunk(boxes=[])
        captions = [_make_caption("Figure 1: Fallback", bbox=(50, 290, 400, 310))]

        results = detect_figures(page, chunk, captions)

        assert len(results) == 1
        bbox, caption_text = results[0]
        assert caption_text == "Figure 1: Fallback"

    def test_caption_matching(self) -> None:
        """2 figure bboxes and 2 figure captions, assert correct caption matched."""
        page = _make_mock_page()
        chunk = _make_page_chunk(boxes=[
            {"class": "picture", "bbox": [50, 100, 400, 250]},
            {"class": "picture", "bbox": [50, 400, 400, 550]},
        ])
        captions = [
            _make_caption("Figure 1: First", bbox=(50, 260, 400, 280), number="1"),
            _make_caption("Figure 2: Second", bbox=(50, 560, 400, 580), number="2"),
        ]

        results = detect_figures(page, chunk, captions)

        assert len(results) == 2
        # Sorted by y, first figure should get Figure 1
        texts = [r[1] for r in results]
        assert "Figure 1: First" in texts
        assert "Figure 2: Second" in texts

    def test_box_merging(self) -> None:
        """Overlapping image rects merged into single bbox."""
        page = _make_mock_page()
        # Two overlapping picture boxes should merge into one
        chunk = _make_page_chunk(boxes=[
            {"class": "picture", "bbox": [50, 100, 400, 250]},
            {"class": "picture", "bbox": [50, 230, 400, 380]},  # overlaps with first
        ])
        captions = [_make_caption("Figure 1: Merged", bbox=(50, 390, 400, 410))]

        results = detect_figures(page, chunk, captions)

        assert len(results) == 1
        bbox = results[0][0]
        # Merged bbox should span both originals
        assert bbox[1] == pytest.approx(100, abs=1)
        assert bbox[3] == pytest.approx(380, abs=1)

    def test_box_splitting(self) -> None:
        """1 large bbox with 2 captions, assert split into 2 bboxes."""
        page = _make_mock_page()
        # One large picture box
        chunk = _make_page_chunk(boxes=[
            {"class": "picture", "bbox": [50, 100, 400, 700]},
        ])
        # Two captions inside the box's y-range
        captions = [
            _make_caption("Figure 1: Top", bbox=(50, 350, 400, 370), number="1"),
            _make_caption("Figure 2: Bottom", bbox=(50, 550, 400, 570), number="2"),
        ]

        results = detect_figures(page, chunk, captions)

        assert len(results) >= 2


class TestRenderFigure:
    def test_renders_png(self, tmp_path: Path) -> None:
        """Mock doc, assert PNG file created at expected path."""
        doc = MagicMock()
        mock_page = MagicMock()
        doc.__getitem__ = MagicMock(return_value=mock_page)
        mock_pix = MagicMock()
        mock_page.get_pixmap.return_value = mock_pix

        result = render_figure(doc, 1, (50, 100, 400, 280), tmp_path, 0)

        assert result is not None
        assert result.name == "fig_p001_00.png"
        mock_pix.save.assert_called_once()

    def test_returns_none_on_failure(self, tmp_path: Path) -> None:
        """Mock doc that raises, assert None returned."""
        doc = MagicMock()
        mock_page = MagicMock()
        doc.__getitem__ = MagicMock(return_value=mock_page)
        mock_page.get_pixmap.side_effect = RuntimeError("render failed")

        result = render_figure(doc, 1, (50, 100, 400, 280), tmp_path, 0)

        assert result is None


class TestCanonicalImports:
    def test_figure_detection_exports(self) -> None:
        """Verify all figure detection functions are importable from the canonical location."""
        from zotero_chunk_rag.feature_extraction.methods.figure_detection import (
            _euclidean_match,
            _has_side_by_side,
            _match_by_proximity,
            _merge_rects,
            detect_figures,
            render_figure,
        )
        assert callable(_euclidean_match)
        assert callable(_has_side_by_side)
        assert callable(_match_by_proximity)
        assert callable(_merge_rects)
        assert callable(detect_figures)
        assert callable(render_figure)
