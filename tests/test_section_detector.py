"""Tests for section detection."""
import pytest
from zotero_chunk_rag.models import PageText
from zotero_chunk_rag.section_detector import (
    detect_sections,
    assign_section,
    _categorize_heading,
)


class TestCategorizeHeading:
    """Test keyword-to-category mapping."""

    def test_simple_keywords(self):
        assert _categorize_heading("Introduction")[0] == "introduction"
        assert _categorize_heading("Methods")[0] == "methods"
        assert _categorize_heading("Results")[0] == "results"
        assert _categorize_heading("Discussion")[0] == "discussion"
        assert _categorize_heading("Conclusion")[0] == "conclusion"
        assert _categorize_heading("Abstract")[0] == "abstract"
        assert _categorize_heading("References")[0] == "references"

    def test_case_insensitive(self):
        assert _categorize_heading("INTRODUCTION")[0] == "introduction"
        assert _categorize_heading("METHODS")[0] == "methods"
        assert _categorize_heading("RESULTS")[0] == "results"

    def test_compound_headings_highest_weight_wins(self):
        # "Results and Discussion" -> results (weight 1.0) not discussion (0.65)
        assert _categorize_heading("Results and Discussion")[0] == "results"
        assert _categorize_heading("III. RESULTS AND DISCUSSION")[0] == "results"

    def test_summary_disambiguation(self):
        # "Summary" alone -> conclusion
        assert _categorize_heading("Summary")[0] == "conclusion"
        # "Summary statistics" -> results
        assert _categorize_heading("Summary Statistics")[0] == "results"
        assert _categorize_heading("Results Summary")[0] == "results"

    def test_methods_variants(self):
        assert _categorize_heading("Materials and Methods")[0] == "methods"
        assert _categorize_heading("Experimental Procedure")[0] == "methods"
        assert _categorize_heading("Study Design")[0] == "methods"
        assert _categorize_heading("Participants")[0] == "methods"

    def test_no_match_returns_none(self):
        assert _categorize_heading("Figure 1")[0] is None
        assert _categorize_heading("Table 2")[0] is None
        assert _categorize_heading("Random Title")[0] is None


class TestDetectSections:
    """Test full section detection pipeline."""

    def test_roman_numeral_headings(self):
        text = """
Title of Paper

I. INTRODUCTION

Some introduction text here.

II. METHODS

Methodology description.

III. RESULTS

The findings.

IV. CONCLUSION

Final thoughts.
"""
        pages = [PageText(page_num=1, text=text, char_start=0)]
        spans = detect_sections(pages)

        labels = [s.label for s in spans]
        assert "preamble" in labels
        assert "introduction" in labels
        assert "methods" in labels
        assert "results" in labels
        assert "conclusion" in labels

    def test_numbered_headings(self):
        text = """
Title

1. Introduction

Intro text.

2. Methods

Methods text.

3. Results

Results text.
"""
        pages = [PageText(page_num=1, text=text, char_start=0)]
        spans = detect_sections(pages)

        labels = [s.label for s in spans]
        assert "introduction" in labels
        assert "methods" in labels
        assert "results" in labels

    def test_bare_caps_headings(self):
        text = """
ABSTRACT

Abstract text here.

INTRODUCTION

Introduction text.

METHODS

Methods text.
"""
        pages = [PageText(page_num=1, text=text, char_start=0)]
        spans = detect_sections(pages)

        labels = [s.label for s in spans]
        # bare_caps should match
        assert "abstract" in labels or "introduction" in labels

    def test_empty_pages_returns_empty(self):
        assert detect_sections([]) == []

    def test_no_headings_returns_unknown(self):
        text = "Just some text without any section headings at all."
        pages = [PageText(page_num=1, text=text, char_start=0)]
        spans = detect_sections(pages)

        assert len(spans) == 1
        assert spans[0].label == "unknown"

    def test_spans_cover_entire_document(self):
        text = """
Title

I. INTRODUCTION

Some text.

II. METHODS

More text.
"""
        pages = [PageText(page_num=1, text=text, char_start=0)]
        spans = detect_sections(pages)

        # Verify no gaps
        total_len = len(text)
        assert spans[0].char_start == 0
        assert spans[-1].char_end == total_len

        for i in range(len(spans) - 1):
            assert spans[i].char_end == spans[i + 1].char_start


class TestAssignSection:
    """Test chunk-to-section assignment."""

    def test_assign_section_basic(self):
        text = """
Title

I. INTRODUCTION

Some intro text here.

II. METHODS

Methods text here.
"""
        pages = [PageText(page_num=1, text=text, char_start=0)]
        spans = detect_sections(pages)

        # Position 0 should be preamble
        assert assign_section(0, spans) == "preamble"

        # Find introduction span and test a position within it
        intro_span = next(s for s in spans if s.label == "introduction")
        mid_intro = (intro_span.char_start + intro_span.char_end) // 2
        assert assign_section(mid_intro, spans) == "introduction"

    def test_assign_section_boundary(self):
        text = """
Title

I. INTRODUCTION

Intro.

II. METHODS

Methods.
"""
        pages = [PageText(page_num=1, text=text, char_start=0)]
        spans = detect_sections(pages)

        # At exact boundary, should return the new section
        methods_span = next(s for s in spans if s.label == "methods")
        assert assign_section(methods_span.char_start, spans) == "methods"
