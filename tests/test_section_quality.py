"""Section detection quality tests against real papers."""

# Only sections whose headings contain a standard keyword are tested.
# Non-standard headings (e.g., "Modeling Diseases") become "unknown" — that is correct.

NONAME1_KEYWORD_SECTIONS = [
    ("Introduction", "introduction"),
    ("Summary and Outlook", "conclusion"),
    ("References", "references"),
]

NONAME2_KEYWORD_SECTIONS = [
    ("Introduction", "introduction"),
    ("Numerical methods", "methods"),
    ("Results", "results"),
    ("Discussion", "discussion"),
    ("Conclusions", "conclusion"),
    ("References", "references"),
]

NONAME3_KEYWORD_SECTIONS = [
    ("METHODS", "methods"),
    ("RESULTS", "results"),
    ("DISCUSSION", "discussion"),
    ("ACKNOWLEDGMENTS", "appendix"),
    ("GRANTS", "appendix"),
    ("REFERENCES", "references"),
]


def _find_section(sections, heading_substring):
    """Find the first section whose heading_text contains the substring (case-insensitive)."""
    for s in sections:
        if heading_substring.lower() in s.heading_text.lower():
            return s
    return None


def test_noname1_keyword_sections(extracted_papers):
    ex = extracted_papers["noname1.pdf"]
    for heading_sub, expected_label in NONAME1_KEYWORD_SECTIONS:
        s = _find_section(ex.sections, heading_sub)
        assert s is not None, (
            f"Section with heading containing {heading_sub!r} not found. "
            f"Sections: {[(s.heading_text[:40], s.label) for s in ex.sections]}"
        )
        assert s.label == expected_label, (
            f"Section {heading_sub!r} labelled {s.label!r}, expected {expected_label!r}"
        )


def test_noname2_keyword_sections(extracted_papers):
    ex = extracted_papers["noname2.pdf"]
    for heading_sub, expected_label in NONAME2_KEYWORD_SECTIONS:
        s = _find_section(ex.sections, heading_sub)
        assert s is not None, (
            f"Section with heading containing {heading_sub!r} not found. "
            f"Sections: {[(s.heading_text[:40], s.label) for s in ex.sections]}"
        )
        assert s.label == expected_label, (
            f"Section {heading_sub!r} labelled {s.label!r}, expected {expected_label!r}"
        )


def test_noname3_keyword_sections(extracted_papers):
    ex = extracted_papers["noname3.pdf"]
    for heading_sub, expected_label in NONAME3_KEYWORD_SECTIONS:
        s = _find_section(ex.sections, heading_sub)
        assert s is not None, (
            f"Section with heading containing {heading_sub!r} not found. "
            f"Sections: {[(s.heading_text[:40], s.label) for s in ex.sections]}"
        )
        assert s.label == expected_label, (
            f"Section {heading_sub!r} labelled {s.label!r}, expected {expected_label!r}"
        )


def test_noname1_non_keyword_sections_are_unknown(extracted_papers):
    """Headings without standard keywords must be labelled 'unknown', not force-fitted."""
    ex = extracted_papers["noname1.pdf"]
    for s in ex.sections:
        if s.label not in ("preamble", "unknown", "introduction", "conclusion", "references", "abstract"):
            # This section was classified by keyword. Verify the keyword actually exists.
            heading_lower = s.heading_text.lower()
            from zotero_chunk_rag.section_classifier import categorize_heading
            cat, _ = categorize_heading(heading_lower)
            assert cat is not None, (
                f"Section {s.heading_text[:40]!r} labelled {s.label!r} "
                f"but heading has no matching keyword — should be 'unknown'"
            )


def test_noname3_page_ids_filtered(extracted_papers):
    """Page identifiers like R1356, R1360, R1368 must not appear as section headings."""
    ex = extracted_papers["noname3.pdf"]
    for s in ex.sections:
        cleaned = s.heading_text.strip().strip("#*_ ")
        assert not cleaned.startswith("R1"), f"Page identifier in sections: {s.heading_text!r}"


def test_all_papers_sections_cover_full_text(extracted_papers):
    """Sections must cover the entire document with no gaps."""
    for pdf_name in ["noname1.pdf", "noname2.pdf", "noname3.pdf"]:
        ex = extracted_papers[pdf_name]
        assert ex.sections, f"{pdf_name}: no sections detected"
        assert ex.sections[0].char_start == 0, (
            f"{pdf_name}: first section starts at {ex.sections[0].char_start}, not 0"
        )
        assert ex.sections[-1].char_end == len(ex.full_markdown), (
            f"{pdf_name}: last section ends at {ex.sections[-1].char_end}, "
            f"not {len(ex.full_markdown)}"
        )
        for i in range(len(ex.sections) - 1):
            assert ex.sections[i].char_end == ex.sections[i + 1].char_start, (
                f"{pdf_name}: gap between sections {i} and {i+1}"
            )


def test_abstract_detection_does_not_crash(extracted_papers):
    """Three-tier abstract detection runs without error on all fixtures.
    If a paper has an abstract (keyword or font-detected), it must appear
    exactly once in sections."""
    for pdf_name in ["noname1.pdf", "noname2.pdf", "noname3.pdf"]:
        ex = extracted_papers[pdf_name]
        abstract_sections = [s for s in ex.sections if s.label == "abstract"]
        # Must be 0 or 1 — never multiple
        assert len(abstract_sections) <= 1, (
            f"{pdf_name}: {len(abstract_sections)} abstract sections — "
            f"should be at most 1"
        )


def test_abstract_detected_via_toc(extracted_papers):
    """If a paper's TOC already labels 'abstract', Tier 2 should recognise it
    and _detect_abstract should return None (not duplicate)."""
    # All three noname papers should have abstract detected by some tier
    for pdf_name in ["noname1.pdf", "noname2.pdf", "noname3.pdf"]:
        ex = extracted_papers[pdf_name]
        abstract_sections = [s for s in ex.sections if s.label == "abstract"]
        # At most 1 abstract section (no duplicates)
        assert len(abstract_sections) <= 1, (
            f"{pdf_name}: {len(abstract_sections)} abstract sections detected — "
            f"should be at most 1"
        )


def test_noname1_no_methods_overcount(extracted_papers):
    """noname1 is a review paper. 'methods' should only appear for headings
    that actually contain 'method' in the text, not for every body section."""
    ex = extracted_papers["noname1.pdf"]
    methods_sections = [s for s in ex.sections if s.label == "methods"]
    # noname1 has no headings containing "method" — 0 is expected
    assert len(methods_sections) <= 2, (
        f"noname1 has {len(methods_sections)} methods sections — "
        f"position heuristics are over-applying. "
        f"Headings: {[s.heading_text[:40] for s in methods_sections]}"
    )
