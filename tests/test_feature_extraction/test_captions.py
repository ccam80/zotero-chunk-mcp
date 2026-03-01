"""Tests for unified captions module."""
from __future__ import annotations

import dataclasses
from unittest.mock import MagicMock

import pytest

from zotero_chunk_rag.feature_extraction.captions import (
    DetectedCaption,
    _FIG_CAPTION_RE,
    _FIG_CAPTION_RE_RELAXED,
    _FIG_LABEL_ONLY_RE,
    _NUM_GROUP,
    _SUPP_PREFIX_RE,
    _TABLE_CAPTION_RE,
    _TABLE_CAPTION_RE_RELAXED,
    _TABLE_LABEL_ONLY_RE,
    _block_has_label_font_change,
    _block_is_bold,
    _block_label_on_own_line,
    _font_name_is_bold,
    _parse_caption_number,
    find_all_captions,
    is_in_references,
)


# ---------------------------------------------------------------------------
# TestDetectedCaption
# ---------------------------------------------------------------------------


class TestDetectedCaption:
    def test_frozen(self) -> None:
        """Assert mutation raises error."""
        cap = DetectedCaption(
            text="Table 1. Results",
            bbox=(10.0, 20.0, 300.0, 40.0),
            y_center=30.0,
            caption_type="table",
            number="1",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            cap.text = "modified"  # type: ignore[misc]

    def test_fields(self) -> None:
        """Construct with known values, assert all fields accessible."""
        cap = DetectedCaption(
            text="Figure 3: Comparison of methods",
            bbox=(50.0, 100.0, 400.0, 120.0),
            y_center=110.0,
            caption_type="figure",
            number="3",
        )
        assert cap.text == "Figure 3: Comparison of methods"
        assert cap.bbox == (50.0, 100.0, 400.0, 120.0)
        assert cap.y_center == 110.0
        assert cap.caption_type == "figure"
        assert cap.number == "3"


# ---------------------------------------------------------------------------
# TestCaptionRegex
# ---------------------------------------------------------------------------


class TestCaptionRegex:
    def test_table_caption(self) -> None:
        """'Table 1. Results' matches table caption pattern, parses number '1'."""
        assert _TABLE_CAPTION_RE.match("Table 1. Results")
        assert _parse_caption_number("Table 1. Results") == "1"

    def test_figure_caption(self) -> None:
        """'Figure 3: Comparison' matches figure caption pattern, parses number '3'."""
        assert _FIG_CAPTION_RE.match("Figure 3: Comparison")
        assert _parse_caption_number("Figure 3: Comparison") == "3"

    def test_appendix_number(self) -> None:
        """'Table A.1' parses number 'A.1'."""
        assert _TABLE_CAPTION_RE_RELAXED.match("Table A.1 Results")
        assert _parse_caption_number("Table A.1 Results") == "A.1"

    def test_supplementary_number(self) -> None:
        """'Figure S2' parses number 'S2'."""
        # S2 followed by delimiter matches strict pattern
        assert _FIG_CAPTION_RE.match("Figure S2. Supplementary analysis")
        assert _parse_caption_number("Figure S2. Supplementary analysis") == "S2"

    def test_roman_numeral(self) -> None:
        """'Table IV' parses number 'IV'."""
        assert _TABLE_CAPTION_RE_RELAXED.match("Table IV Results summary")
        assert _parse_caption_number("Table IV Results summary") == "IV"


# ---------------------------------------------------------------------------
# TestFontHelpers
# ---------------------------------------------------------------------------


class TestFontHelpers:
    def test_bold_detection(self) -> None:
        """Font names containing .B, -Bold, -bd detected as bold."""
        assert _font_name_is_bold("TimesNewRoman.B")
        assert _font_name_is_bold("Helvetica-Bold")
        assert _font_name_is_bold("Arial-bd")

    def test_non_bold(self) -> None:
        """Font names like 'TimesNewRoman' not detected as bold."""
        assert not _font_name_is_bold("TimesNewRoman")
        assert not _font_name_is_bold("Helvetica")
        assert not _font_name_is_bold("Courier-Oblique")


# ---------------------------------------------------------------------------
# Helpers for mock pages
# ---------------------------------------------------------------------------


def _make_block(text: str, bbox: tuple = (10, 100, 400, 120), font: str = "Regular", bold: bool = False) -> dict:
    """Create a mock text block dict for page.get_text('dict')."""
    flags = 16 if bold else 0
    return {
        "type": 0,
        "bbox": bbox,
        "lines": [
            {
                "spans": [
                    {
                        "text": text,
                        "font": font,
                        "flags": flags,
                    }
                ]
            }
        ],
    }


def _make_font_change_block(label: str, body: str, bbox: tuple = (10, 100, 400, 120)) -> dict:
    """Create a block where label has different font from body (font change signal)."""
    return {
        "type": 0,
        "bbox": bbox,
        "lines": [
            {
                "spans": [
                    {"text": label, "font": "Helvetica-Bold", "flags": 16},
                    {"text": body, "font": "TimesNewRoman", "flags": 0},
                ]
            }
        ],
    }


def _make_mock_page(blocks: list[dict]) -> MagicMock:
    """Create a mock pymupdf Page returning specific text blocks."""
    page = MagicMock()
    page.get_text.return_value = {"blocks": blocks}
    return page


def _make_multiline_block(lines: list[str], bbox: tuple = (10, 100, 400, 160), font: str = "Regular") -> dict:
    """Create a mock text block with multiple lines, each containing one span."""
    return {
        "type": 0,
        "bbox": bbox,
        "lines": [
            {
                "spans": [
                    {"text": line_text, "font": font, "flags": 0}
                ]
            }
            for line_text in lines
        ],
    }


# ---------------------------------------------------------------------------
# TestFindAllCaptions
# ---------------------------------------------------------------------------


class TestFindAllCaptions:
    def test_finds_table_and_figure(self) -> None:
        """Mock page with blocks containing 'Table 1...' and 'Figure 2...', assert both found."""
        blocks = [
            _make_block("Table 1. Baseline demographics", bbox=(10, 100, 400, 120)),
            _make_block("Figure 2: Results comparison", bbox=(10, 300, 400, 320)),
        ]
        page = _make_mock_page(blocks)

        captions = find_all_captions(page)
        assert len(captions) == 2
        types = {c.caption_type for c in captions}
        assert types == {"table", "figure"}

        table_cap = [c for c in captions if c.caption_type == "table"][0]
        assert table_cap.number == "1"
        fig_cap = [c for c in captions if c.caption_type == "figure"][0]
        assert fig_cap.number == "2"

    def test_filter_by_type(self) -> None:
        """include_figures=False returns only table captions."""
        blocks = [
            _make_block("Table 1. Results", bbox=(10, 100, 400, 120)),
            _make_block("Figure 2: Graph", bbox=(10, 300, 400, 320)),
        ]
        page = _make_mock_page(blocks)

        captions = find_all_captions(page, include_figures=False)
        assert len(captions) == 1
        assert captions[0].caption_type == "table"

    def test_sorted_by_y(self) -> None:
        """Multiple captions returned in top-to-bottom order."""
        blocks = [
            _make_block("Figure 2: Bottom", bbox=(10, 500, 400, 520)),
            _make_block("Table 1. Top", bbox=(10, 100, 400, 120)),
            _make_block("Figure 1: Middle", bbox=(10, 300, 400, 320)),
        ]
        page = _make_mock_page(blocks)

        captions = find_all_captions(page)
        assert len(captions) == 3
        y_centers = [c.y_center for c in captions]
        assert y_centers == sorted(y_centers)

    def test_relaxed_with_font_change(self) -> None:
        """Caption matching relaxed regex is accepted only with font-change structural signal."""
        # Relaxed match: "Figure 1 something" (no delimiter after number)
        # WITH font change -- should match
        block_with_change = _make_font_change_block("Figure 1 ", "Results of the analysis", bbox=(10, 100, 400, 120))
        # WITHOUT font change -- should NOT match
        block_no_change = _make_block("Figure 3 results of something", bbox=(10, 200, 400, 220), font="Regular")

        page = _make_mock_page([block_with_change, block_no_change])
        captions = find_all_captions(page)

        # Only the font-change block should be detected
        assert len(captions) == 1
        assert captions[0].number == "1"

    def test_label_only_table(self) -> None:
        """Standalone 'Table 1' block detected as table caption with number '1'."""
        blocks = [_make_block("Table 1", bbox=(10, 100, 400, 120))]
        page = _make_mock_page(blocks)

        captions = find_all_captions(page)

        assert len(captions) == 1
        assert captions[0].caption_type == "table"
        assert captions[0].number == "1"
        assert captions[0].text == "Table 1"

    def test_label_only_figure(self) -> None:
        """Standalone 'Figure 3' block detected as figure caption with number '3'."""
        blocks = [_make_block("Figure 3", bbox=(10, 200, 400, 220))]
        page = _make_mock_page(blocks)

        captions = find_all_captions(page)

        assert len(captions) == 1
        assert captions[0].caption_type == "figure"
        assert captions[0].number == "3"

    def test_label_only_with_supplementary_prefix(self) -> None:
        """'Supplementary Table S2' (prefix stripped) detected with number 'S2'."""
        blocks = [_make_block("Supplementary Table S2", bbox=(10, 100, 400, 120))]
        page = _make_mock_page(blocks)

        captions = find_all_captions(page)

        assert len(captions) == 1
        assert captions[0].caption_type == "table"
        assert captions[0].number == "S2"

    def test_label_only_does_not_match_body_text(self) -> None:
        """'Table 1 shows the results of our analysis' does NOT match via label-only path."""
        blocks = [
            _make_block("Table 1 shows the results of our analysis", bbox=(10, 100, 400, 120), font="Regular")
        ]
        page = _make_mock_page(blocks)

        # No font-change signal, no bold — relaxed path requires structural confirmation.
        # The label-only path requires \s*$ so trailing text prevents it from matching.
        captions = find_all_captions(page)
        assert len(captions) == 0

    def test_label_only_line_scan(self) -> None:
        """'Table 2' on line 1 of a 3-line block is detected; text includes subsequent lines."""
        block = _make_multiline_block(
            ["Y-axis label", "Table 2", "Patient demographics by age group"],
            bbox=(10, 100, 400, 160),
        )
        page = _make_mock_page([block])

        captions = find_all_captions(page)

        assert len(captions) == 1
        assert captions[0].caption_type == "table"
        assert captions[0].number == "2"
        assert "Table 2" in captions[0].text
        assert "Patient demographics" in captions[0].text

    def test_label_only_line_scan_figure(self) -> None:
        """'Figure 5' on line 1 of a multi-line block is detected as figure caption."""
        block = _make_multiline_block(
            ["X-axis label", "Figure 5", "Scatter plot of activation vs response"],
            bbox=(10, 200, 400, 260),
        )
        page = _make_mock_page([block])

        captions = find_all_captions(page)

        assert len(captions) == 1
        assert captions[0].caption_type == "figure"
        assert captions[0].number == "5"
        assert "Figure 5" in captions[0].text


# ---------------------------------------------------------------------------
# TestIsInReferences
# ---------------------------------------------------------------------------


class TestIsInReferences:
    def test_in_references(self) -> None:
        """Page within references section returns True."""
        from zotero_chunk_rag.models import SectionSpan, PageExtraction

        sections = [
            SectionSpan(label="introduction", char_start=0, char_end=1000, heading_text="Introduction", confidence=1.0),
            SectionSpan(label="references", char_start=1000, char_end=2000, heading_text="References", confidence=1.0),
        ]
        pages = [
            PageExtraction(page_num=1, markdown="intro text", char_start=0),
            PageExtraction(page_num=2, markdown="ref text", char_start=1200),
        ]
        assert is_in_references(2, sections, pages) is True

    def test_not_in_references(self) -> None:
        """Page before references returns False."""
        from zotero_chunk_rag.models import SectionSpan, PageExtraction

        sections = [
            SectionSpan(label="introduction", char_start=0, char_end=1000, heading_text="Introduction", confidence=1.0),
            SectionSpan(label="references", char_start=1000, char_end=2000, heading_text="References", confidence=1.0),
        ]
        pages = [
            PageExtraction(page_num=1, markdown="intro text", char_start=0),
            PageExtraction(page_num=2, markdown="ref text", char_start=1200),
        ]
        assert is_in_references(1, sections, pages) is False


class TestCanonicalImports:
    def test_captions_module_exports(self) -> None:
        """Verify all caption functions are importable from the canonical location."""
        from zotero_chunk_rag.feature_extraction.captions import (
            _FIG_CAPTION_RE,
            _FIG_CAPTION_RE_RELAXED,
            _FIG_LABEL_ONLY_RE,
            _block_has_label_font_change,
            _block_is_bold,
            _block_label_on_own_line,
            _font_name_is_bold,
            is_in_references,
            _scan_lines_for_caption,
            _text_from_line_onward,
            find_all_captions,
        )
        exported = dir(
            __import__(
                "zotero_chunk_rag.feature_extraction.captions",
                fromlist=["captions"],
            )
        )
        for name in [
            "_FIG_CAPTION_RE",
            "_FIG_CAPTION_RE_RELAXED",
            "_FIG_LABEL_ONLY_RE",
            "_block_has_label_font_change",
            "_block_is_bold",
            "_block_label_on_own_line",
            "_font_name_is_bold",
            "is_in_references",
            "_scan_lines_for_caption",
            "_text_from_line_onward",
            "find_all_captions",
        ]:
            assert name in exported, f"{name!r} missing from captions module"
