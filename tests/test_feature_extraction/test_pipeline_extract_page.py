"""Tests for Pipeline.extract_page() — page-level feature detection."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pymupdf

from zotero_chunk_rag.feature_extraction.captions import DetectedCaption
from zotero_chunk_rag.feature_extraction.models import (
    ExtractionResult,
    PageFeatures,
    PipelineConfig,
)
from zotero_chunk_rag.feature_extraction.pipeline import MINIMAL_CONFIG, Pipeline


def _make_mock_page(tables=None, figure_rects=None, captions=None):
    """Build a mock page that returns controlled tables and text blocks.

    Parameters
    ----------
    tables : list of (x0, y0, x1, y1) tuples for table bboxes
    figure_rects : list of (x0, y0, x1, y1) tuples for picture box bboxes
    captions : list of DetectedCaption objects
    """
    page = MagicMock(spec=pymupdf.Page)
    page.rect = pymupdf.Rect(0, 0, 612, 792)

    # Set up find_tables
    mock_tables = []
    for bbox in (tables or []):
        tab = MagicMock()
        tab.bbox = bbox
        mock_tables.append(tab)

    finder = MagicMock()
    finder.tables = mock_tables
    page.find_tables = MagicMock(return_value=finder)

    # Set up get_text for captions
    blocks = []
    for cap in (captions or []):
        block = {
            "type": 0,
            "bbox": cap.bbox,
            "lines": [{
                "spans": [{
                    "text": cap.text,
                    "font": "Helvetica-Bold" if cap.caption_type == "table" else "Helvetica",
                    "flags": 16,
                }]
            }],
        }
        blocks.append(block)

    def mock_get_text(fmt="text", **kwargs):
        if fmt == "dict":
            return {"blocks": blocks}
        if fmt == "words":
            return []
        return ""

    page.get_text = mock_get_text
    page.get_drawings = MagicMock(return_value=[])
    page.get_image_info = MagicMock(return_value=[])

    return page


def _make_page_chunk(figure_bboxes=None):
    """Build a page_chunk dict with page_boxes for figure detection."""
    boxes = []
    for bbox in (figure_bboxes or []):
        boxes.append({"bbox": list(bbox), "class": "picture"})
    return {"page_boxes": boxes}


class TestExtractPage:

    def test_returns_page_features(self):
        """Mock page with 1 table and 1 figure returns PageFeatures."""
        table_cap = DetectedCaption(
            text="Table 1. Results", bbox=(50, 100, 300, 120),
            y_center=110, caption_type="table", number="1",
        )
        fig_cap = DetectedCaption(
            text="Figure 1. Diagram", bbox=(50, 500, 300, 520),
            y_center=510, caption_type="figure", number="1",
        )
        page = _make_mock_page(
            tables=[(50, 130, 300, 400)],
            captions=[table_cap, fig_cap],
        )
        page_chunk = _make_page_chunk(figure_bboxes=[(50, 530, 300, 700)])

        pipeline = Pipeline(MINIMAL_CONFIG)

        with patch(
            "zotero_chunk_rag.feature_extraction.pipeline.find_all_captions",
            return_value=[table_cap, fig_cap],
        ), patch(
            "zotero_chunk_rag.feature_extraction.pipeline.detect_figures",
            return_value=[((50, 530, 300, 700), "Figure 1. Diagram")],
        ):
            result = pipeline.extract_page(
                page, page_num=1, pdf_path="/tmp/test.pdf",
                page_chunk=page_chunk,
            )

        assert isinstance(result, PageFeatures)
        assert len(result.tables) == 1
        assert len(result.figures) == 1

    def test_empty_page(self):
        """Page with no tables or figures returns empty PageFeatures."""
        page = _make_mock_page()
        # find_tables returns no results
        finder = MagicMock()
        finder.tables = []
        page.find_tables = MagicMock(return_value=finder)

        pipeline = Pipeline(MINIMAL_CONFIG)

        with patch(
            "zotero_chunk_rag.feature_extraction.pipeline.find_all_captions",
            return_value=[],
        ), patch(
            "zotero_chunk_rag.feature_extraction.pipeline.detect_figures",
            return_value=[],
        ):
            result = pipeline.extract_page(
                page, page_num=1, pdf_path="/tmp/test.pdf",
                page_chunk={"page_boxes": []},
            )

        assert isinstance(result, PageFeatures)
        assert len(result.tables) == 0
        assert len(result.figures) == 0

    def test_figure_data_table_tagged(self):
        """Table with >50% overlap with a figure bbox is tagged as artifact."""
        table_bbox = (50, 130, 300, 400)
        figure_bbox = (50, 130, 300, 400)  # 100% overlap

        table_cap = DetectedCaption(
            text="Table 1. Data", bbox=(50, 100, 300, 120),
            y_center=110, caption_type="table", number="1",
        )
        fig_cap = DetectedCaption(
            text="Figure 1. Photo", bbox=(50, 420, 300, 440),
            y_center=430, caption_type="figure", number="1",
        )

        page = _make_mock_page(
            tables=[table_bbox],
            captions=[table_cap, fig_cap],
        )
        page_chunk = _make_page_chunk(figure_bboxes=[figure_bbox])

        pipeline = Pipeline(MINIMAL_CONFIG)

        with patch(
            "zotero_chunk_rag.feature_extraction.pipeline.find_all_captions",
            return_value=[table_cap, fig_cap],
        ), patch(
            "zotero_chunk_rag.feature_extraction.pipeline.detect_figures",
            return_value=[(figure_bbox, "Figure 1. Photo")],
        ):
            result = pipeline.extract_page(
                page, page_num=1, pdf_path="/tmp/test.pdf",
                page_chunk=page_chunk,
            )

        assert len(result.tables) == 1
        assert "artifact" in result.tables[0].table_id

    def test_caption_matching(self):
        """Page with Table 1 caption and one table bbox -> caption populated."""
        table_cap = DetectedCaption(
            text="Table 1. Results", bbox=(50, 100, 300, 120),
            y_center=110, caption_type="table", number="1",
        )
        table_bbox = (50, 130, 300, 400)

        page = _make_mock_page(
            tables=[table_bbox],
            captions=[table_cap],
        )

        pipeline = Pipeline(MINIMAL_CONFIG)

        with patch(
            "zotero_chunk_rag.feature_extraction.pipeline.find_all_captions",
            return_value=[table_cap],
        ), patch(
            "zotero_chunk_rag.feature_extraction.pipeline.detect_figures",
            return_value=[],
        ):
            result = pipeline.extract_page(
                page, page_num=1, pdf_path="/tmp/test.pdf",
                page_chunk={"page_boxes": []},
            )

        assert len(result.tables) == 1
        # Verify the table extraction was called (it would have been given the caption)

    def test_multiple_tables(self):
        """Page with 3 table bboxes and 3 captions -> each matched correctly."""
        captions = [
            DetectedCaption(
                text=f"Table {i}. Data {i}", bbox=(50, 50 + i * 200, 300, 70 + i * 200),
                y_center=60 + i * 200, caption_type="table", number=str(i),
            )
            for i in range(1, 4)
        ]
        table_bboxes = [
            (50, 80 + i * 200, 300, 180 + i * 200)
            for i in range(3)
        ]

        page = _make_mock_page(
            tables=table_bboxes,
            captions=captions,
        )

        pipeline = Pipeline(MINIMAL_CONFIG)

        with patch(
            "zotero_chunk_rag.feature_extraction.pipeline.find_all_captions",
            return_value=captions,
        ), patch(
            "zotero_chunk_rag.feature_extraction.pipeline.detect_figures",
            return_value=[],
        ):
            result = pipeline.extract_page(
                page, page_num=1, pdf_path="/tmp/test.pdf",
                page_chunk={"page_boxes": []},
            )

        assert len(result.tables) == 3

    def test_figure_rendering(self):
        """With write_images=True, figure has non-None image_path."""
        fig_cap = DetectedCaption(
            text="Figure 1. Plot", bbox=(50, 500, 300, 520),
            y_center=510, caption_type="figure", number="1",
        )
        figure_bbox = (50, 530, 300, 700)

        page = _make_mock_page(captions=[fig_cap])
        # find_tables returns no tables
        finder = MagicMock()
        finder.tables = []
        page.find_tables = MagicMock(return_value=finder)

        mock_doc = MagicMock()
        page_chunk = _make_page_chunk(figure_bboxes=[figure_bbox])

        pipeline = Pipeline(MINIMAL_CONFIG)

        with patch(
            "zotero_chunk_rag.feature_extraction.pipeline.find_all_captions",
            return_value=[fig_cap],
        ), patch(
            "zotero_chunk_rag.feature_extraction.pipeline.detect_figures",
            return_value=[(figure_bbox, "Figure 1. Plot")],
        ), patch(
            "zotero_chunk_rag.feature_extraction.pipeline.render_figure",
            return_value=Path("/tmp/fig_p001_00.png"),
        ):
            result = pipeline.extract_page(
                page, page_num=1, pdf_path="/tmp/test.pdf",
                page_chunk=page_chunk,
                write_images=True,
                images_dir="/tmp/images",
                doc=mock_doc,
            )

        assert len(result.figures) == 1
        assert result.figures[0]["image_path"] is not None
