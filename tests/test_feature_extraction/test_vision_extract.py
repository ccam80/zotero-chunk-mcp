"""Tests for vision_extract.py — geometry functions (Tasks 2.1.1–2.1.4) and
prompt/parsing (Tasks 2.2.1–2.2.4)."""

from __future__ import annotations

import json
import re
from unittest.mock import MagicMock

import pymupdf
import pytest

from zotero_chunk_rag.feature_extraction.captions import DetectedCaption
from zotero_chunk_rag.feature_extraction.vision_extract import (
    EXTRACTION_EXAMPLES,
    VISION_FIRST_SYSTEM,
    AgentResponse,
    _split_into_strips,
    compute_all_crops,
    compute_recrop_bbox,
    parse_agent_response,
    render_table_region,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_caption(
    y: float,
    caption_type: str = "table",
    x0: float = 100.0,
    x1: float = 400.0,
) -> DetectedCaption:
    """Create a DetectedCaption at the given y position."""
    return DetectedCaption(
        text=f"{caption_type.capitalize()} 1.",
        bbox=(x0, y, x1, y + 12.0),
        y_center=y + 6.0,
        caption_type=caption_type,
        number="1",
    )


def _make_page(x0: float, y0: float, x1: float, y1: float) -> MagicMock:
    """Create a mock PyMuPDF page with the given rect."""
    page = MagicMock()
    rect = MagicMock()
    rect.x0 = x0
    rect.y0 = y0
    rect.x1 = x1
    rect.y1 = y1
    page.rect = rect
    return page


def _make_real_page() -> pymupdf.Page:
    """Create a real in-memory PyMuPDF page (A4 size)."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    return page


# ---------------------------------------------------------------------------
# Task 2.1.1: compute_all_crops
# ---------------------------------------------------------------------------


class TestComputeAllCrops:
    def test_single_table_caption(self):
        page = _make_page(0.0, 0.0, 595.0, 842.0)
        captions = [_make_caption(200.0, "table")]
        result = compute_all_crops(page, captions)
        assert len(result) == 1
        cap, bbox = result[0]
        assert bbox == (0.0, 200.0, 595.0, 842.0)

    def test_two_table_captions(self):
        page = _make_page(0.0, 0.0, 595.0, 842.0)
        captions = [
            _make_caption(200.0, "table"),
            _make_caption(500.0, "table"),
        ]
        result = compute_all_crops(page, captions)
        assert len(result) == 2
        _, bbox_a = result[0]
        _, bbox_b = result[1]
        assert bbox_a == (0.0, 200.0, 595.0, 500.0)
        assert bbox_b == (0.0, 500.0, 595.0, 842.0)

    def test_table_then_figure_boundary(self):
        page = _make_page(0.0, 0.0, 595.0, 842.0)
        captions = [
            _make_caption(200.0, "table"),
            _make_caption(400.0, "figure"),
        ]
        result = compute_all_crops(page, captions, caption_type="table")
        assert len(result) == 1
        _, bbox = result[0]
        assert bbox == (0.0, 200.0, 595.0, 400.0)

    def test_no_matching_captions(self):
        page = _make_page(0.0, 0.0, 595.0, 842.0)
        captions = [
            _make_caption(200.0, "figure"),
            _make_caption(400.0, "figure"),
        ]
        result = compute_all_crops(page, captions, caption_type="table")
        assert result == []

    def test_full_page_width(self):
        page = _make_page(0.0, 0.0, 595.0, 842.0)
        # Caption has different x-coordinates than the page
        cap = DetectedCaption(
            text="Table 1.",
            bbox=(150.0, 300.0, 450.0, 312.0),
            y_center=306.0,
            caption_type="table",
            number="1",
        )
        result = compute_all_crops(page, [cap])
        assert len(result) == 1
        _, bbox = result[0]
        assert bbox[0] == page.rect.x0   # x0 == page left
        assert bbox[2] == page.rect.x1   # x1 == page right


# ---------------------------------------------------------------------------
# Task 2.1.2: render_table_region and _split_into_strips
# ---------------------------------------------------------------------------


class TestRenderTableRegion:
    def test_single_image_short_crop(self):
        page = _make_real_page()
        # Crop 595×300pt: width > height → single image
        bbox = (0.0, 0.0, 595.0, 300.0)
        result = render_table_region(page, bbox)
        assert len(result) == 1
        png_bytes, media_type = result[0]
        assert media_type == "image/png"
        assert png_bytes[:4] == b"\x89PNG"

    def test_multi_strip_tall_crop(self):
        page = _make_real_page()
        # Full A4 page: 595×842pt. height > width.
        # effective_dpi = 1568 / (842/72) = 1568 / 11.694 ≈ 134 < 200
        bbox = (0.0, 0.0, 595.0, 842.0)
        result = render_table_region(page, bbox)
        assert len(result) >= 2
        for png_bytes, media_type in result:
            assert media_type == "image/png"
            assert png_bytes[:4] == b"\x89PNG"

    def test_custom_strip_threshold(self):
        page = _make_real_page()
        # Crop 595×700pt.
        # effective_dpi = 1568 / (700/72) = 1568 / 9.722 ≈ 161
        bbox = (0.0, 0.0, 595.0, 700.0)

        # With threshold=250: 161 < 250 → multi-strip
        result_multi = render_table_region(page, bbox, strip_dpi_threshold=250)
        assert len(result_multi) >= 2

        # With threshold=150: 161 > 150 → single image
        result_single = render_table_region(page, bbox, strip_dpi_threshold=150)
        assert len(result_single) == 1


class TestSplitIntoStrips:
    def test_strip_dimensions(self):
        bbox = (0.0, 0.0, 595.0, 842.0)
        strips = _split_into_strips(bbox)
        strip_height = 595.0  # width of crop
        for x0, y0, x1, y1 in strips:
            assert (y1 - y0) <= strip_height + 1e-6  # each strip height <= width
        # Last strip must reach page bottom
        assert strips[-1][3] == 842.0
        # Strips must cover the full height (first starts at y0, last ends at y1)
        assert strips[0][1] == 0.0

    def test_strip_overlap(self):
        bbox = (0.0, 0.0, 595.0, 842.0)
        strips = _split_into_strips(bbox)
        assert len(strips) >= 2
        strip_height = 595.0
        expected_overlap = strip_height * 0.15
        for i in range(len(strips) - 1):
            overlap = strips[i][3] - strips[i + 1][1]
            # Overlap must be positive
            assert overlap > 0
            # Overlap must be approximately strip_height * 0.15
            assert abs(overlap - expected_overlap) < 1.0

    def test_short_crop_no_split(self):
        # Height (300) < strip_height (595 = width) → single strip
        bbox = (0.0, 0.0, 595.0, 300.0)
        strips = _split_into_strips(bbox)
        assert len(strips) == 1
        assert strips[0] == bbox


# ---------------------------------------------------------------------------
# Task 2.1.3: compute_recrop_bbox
# ---------------------------------------------------------------------------


class TestComputeRecropBbox:
    def test_full_region(self):
        original = (100.0, 200.0, 700.0, 1000.0)
        result = compute_recrop_bbox(original, [0.0, 0.0, 100.0, 100.0])
        assert result == (100.0, 200.0, 700.0, 1000.0)

    def test_center_quarter(self):
        original = (0.0, 0.0, 600.0, 800.0)
        result = compute_recrop_bbox(original, [25.0, 25.0, 75.0, 75.0])
        assert result == (150.0, 200.0, 450.0, 600.0)

    def test_clamped(self):
        original = (100.0, 200.0, 700.0, 1000.0)
        result = compute_recrop_bbox(original, [-10.0, 0.0, 110.0, 100.0])
        # x0 clamped to original x0 (pct 0 → x0 + 0 = 100)
        assert result[0] == 100.0
        # x1 clamped to original x1 (pct 100 → x0 + 1.0 * w = 700)
        assert result[2] == 700.0


# ---------------------------------------------------------------------------
# Task 2.1.4: render_table_png deleted
# ---------------------------------------------------------------------------


class TestDeletedRenderTablePng:
    def test_not_importable(self):
        with pytest.raises(ImportError):
            from zotero_chunk_rag.feature_extraction.vision_extract import (  # noqa: F401
                render_table_png,
            )


# ---------------------------------------------------------------------------
# Task 2.2.2: AgentResponse new fields
# ---------------------------------------------------------------------------


class TestAgentResponse:
    def test_new_fields_exist(self):
        response = AgentResponse(
            headers=["A", "B"],
            rows=[["1", "2"]],
            footnotes="",
            table_label="Table 1",
            caption="Table 1. Demographics",
            is_incomplete=False,
            incomplete_reason="",
            raw_shape=(1, 2),
            parse_success=True,
            raw_response="{}",
            recrop_needed=True,
            recrop_bbox_pct=[10, 5, 90, 95],
        )
        assert response.caption == "Table 1. Demographics"
        assert response.recrop_needed is True
        assert response.recrop_bbox_pct == [10, 5, 90, 95]


# ---------------------------------------------------------------------------
# Task 2.2.3: parse_agent_response
# ---------------------------------------------------------------------------


class TestParseAgentResponse:
    def test_full_new_schema(self):
        raw = json.dumps({
            "table_label": "Table 3",
            "caption": "Table 3. Results by sex",
            "is_incomplete": False,
            "incomplete_reason": "",
            "headers": ["Variable", "OR", "p"],
            "rows": [["Age", "1.42", "0.004"]],
            "footnotes": "",
            "recrop": {"needed": False, "bbox_pct": [0, 0, 100, 100]},
        })
        response = parse_agent_response(raw, "test")
        assert response.parse_success is True
        assert response.caption == "Table 3. Results by sex"
        assert response.recrop_needed is False

    def test_recrop_needed(self):
        raw = json.dumps({
            "table_label": "Table 1",
            "caption": "Table 1.",
            "is_incomplete": True,
            "incomplete_reason": "bottom edge cut off",
            "headers": ["A"],
            "rows": [["1"]],
            "footnotes": "",
            "recrop": {"needed": True, "bbox_pct": [10, 5, 95, 90]},
        })
        response = parse_agent_response(raw, "test")
        assert response.recrop_needed is True
        assert response.recrop_bbox_pct == [10, 5, 95, 90]

    def test_missing_new_fields(self):
        raw = json.dumps({
            "table_label": "Table 2",
            "headers": ["A", "B"],
            "rows": [["x", "y"]],
        })
        response = parse_agent_response(raw, "test")
        assert response.parse_success is True
        assert response.caption == ""
        assert response.recrop_needed is False
        assert response.recrop_bbox_pct is None

    def test_parse_failure(self):
        response = parse_agent_response("not valid json at all }{", "test")
        assert response.parse_success is False
        assert response.caption == ""
        assert response.recrop_needed is False

    def test_corrections_field_ignored(self):
        raw = json.dumps({
            "table_label": "Table 1",
            "caption": "",
            "headers": ["A"],
            "rows": [["1"]],
            "footnotes": "",
            "corrections": ["some correction"],
        })
        response = parse_agent_response(raw, "test")
        assert response.parse_success is True
        assert not hasattr(response, "corrections")

    def test_invalid_recrop_bbox(self):
        raw = json.dumps({
            "table_label": "Table 1",
            "caption": "",
            "headers": ["A"],
            "rows": [["1"]],
            "footnotes": "",
            "recrop": {"needed": True, "bbox_pct": "bad"},
        })
        response = parse_agent_response(raw, "test")
        assert response.recrop_needed is True
        assert response.recrop_bbox_pct is None


# ---------------------------------------------------------------------------
# Task 2.2.1: VISION_FIRST_SYSTEM prompt
# ---------------------------------------------------------------------------


class TestVisionFirstSystem:
    def test_prompt_is_string(self):
        assert isinstance(VISION_FIRST_SYSTEM, str)

    def test_contains_key_sections(self):
        prompt = VISION_FIRST_SYSTEM
        assert "table transcription" in prompt
        assert any(phrase in prompt for phrase in ["Raw extracted text", "raw text"])
        assert any(phrase in prompt for phrase in ["re-crop", "recrop", "Re-Crop", "Re-crop"])
        assert "bbox_pct" in prompt
        assert "table_label" in prompt
        assert "caption" in prompt
        assert "footnotes" in prompt
        assert "Worked Examples" in prompt
        assert "Example A" in prompt

    def test_no_multi_agent_references(self):
        prompt = VISION_FIRST_SYSTEM
        assert "VERIFIER" not in prompt
        assert "SYNTHESIZER" not in prompt
        assert "corrections" not in prompt
        assert "Y_VERIFIER" not in prompt
        assert "X_VERIFIER" not in prompt

    def test_minimum_length(self):
        assert len(VISION_FIRST_SYSTEM) > 8000


# ---------------------------------------------------------------------------
# Task 2.2.4: EXTRACTION_EXAMPLES caption field
# ---------------------------------------------------------------------------


class TestExtractionExamples:
    def test_all_examples_have_caption(self):
        decoder = json.JSONDecoder()
        parsed_blocks = []
        text = EXTRACTION_EXAMPLES
        pos = 0
        while pos < len(text):
            brace = text.find("{", pos)
            if brace == -1:
                break
            try:
                obj, end = decoder.raw_decode(text, brace)
                if isinstance(obj, dict) and "headers" in obj:
                    parsed_blocks.append(obj)
                pos = end
            except json.JSONDecodeError:
                pos = brace + 1
        assert len(parsed_blocks) == 6, (
            f"Expected exactly 6 parseable example JSON blocks (A-F), got {len(parsed_blocks)}"
        )
        for obj in parsed_blocks:
            assert "caption" in obj, f"Example JSON missing 'caption' field: {obj}"
