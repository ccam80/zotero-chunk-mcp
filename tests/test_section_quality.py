"""Section detection quality tests against real papers."""
from pathlib import Path
from zotero_chunk_rag.pdf_processor import extract_document

FIXTURES = Path(__file__).parent / "fixtures" / "papers"

# Each tuple: (substring that must appear in heading_text, expected label)
# Order matters: these must appear in this order in the sections list.
NONAME1_LEVEL1_SECTIONS = [
    ("Introduction", "introduction"),
    ("Modeling the ECG of a Healthy Heart", "methods"),
    ("Modeling Diseases", "methods"),
    ("Options of Modeling", "methods"),
    ("Summary and Outlook", "conclusion"),
    ("References", "references"),
]

NONAME2_LEVEL1_SECTIONS = [
    ("Introduction", "introduction"),
    ("Code verification", "methods"),
    ("Virtual physiological human", "methods"),
    ("Benchmark definition", "methods"),
    ("Benchmark simulations", "methods"),
    ("Discussion", "discussion"),
    ("Conclusions", "conclusion"),
    ("References", "references"),
]

NONAME3_SECTIONS = [
    # noname3 has no TOC. After filtering page identifiers:
    ("METHODS", "methods"),
    ("RESULTS", "results"),
    ("DISCUSSION", "discussion"),  # "DISCUSSION, SUMMARY, AND SIGNIFICANCE" -> discussion or conclusion
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


def test_noname1_section_labels():
    ex = extract_document(FIXTURES / "noname1.pdf")
    for heading_sub, expected_label in NONAME1_LEVEL1_SECTIONS:
        s = _find_section(ex.sections, heading_sub)
        assert s is not None, f"Section with heading containing {heading_sub!r} not found. Sections: {[(s.heading_text[:40], s.label) for s in ex.sections]}"
        assert s.label == expected_label, f"Section {heading_sub!r} labelled {s.label!r}, expected {expected_label!r}"


def test_noname1_no_unknowns():
    ex = extract_document(FIXTURES / "noname1.pdf")
    unknowns = [s for s in ex.sections if s.label == "unknown"]
    assert len(unknowns) == 0, f"Unexpected unknown sections: {[(s.heading_text[:40], s.char_start) for s in unknowns]}"


def test_noname2_section_labels():
    ex = extract_document(FIXTURES / "noname2.pdf")
    for heading_sub, expected_label in NONAME2_LEVEL1_SECTIONS:
        s = _find_section(ex.sections, heading_sub)
        assert s is not None, f"Section with heading containing {heading_sub!r} not found. Sections: {[(s.heading_text[:40], s.label) for s in ex.sections]}"
        assert s.label == expected_label, f"Section {heading_sub!r} labelled {s.label!r}, expected {expected_label!r}"


def test_noname2_no_unknowns():
    ex = extract_document(FIXTURES / "noname2.pdf")
    unknowns = [s for s in ex.sections if s.label == "unknown"]
    # "Anatomical Model Database (AMDB) website" may remain unknown — it's genuinely ambiguous
    assert len(unknowns) <= 1, f"Unexpected unknown sections: {[(s.heading_text[:40], s.char_start) for s in unknowns]}"


def test_noname3_section_labels():
    ex = extract_document(FIXTURES / "noname3.pdf")
    for heading_sub, expected_label in NONAME3_SECTIONS:
        s = _find_section(ex.sections, heading_sub)
        assert s is not None, f"Section with heading containing {heading_sub!r} not found. Sections: {[(s.heading_text[:40], s.label) for s in ex.sections]}"
        assert s.label == expected_label, f"Section {heading_sub!r} labelled {s.label!r}, expected {expected_label!r}"


def test_noname3_page_ids_filtered():
    """Page identifiers like R1356, R1360, R1368 must not appear as section headings."""
    ex = extract_document(FIXTURES / "noname3.pdf")
    for s in ex.sections:
        cleaned = s.heading_text.strip().strip("#*_ ")
        assert not cleaned.startswith("R1"), f"Page identifier in sections: {s.heading_text!r}"


def test_all_papers_sections_cover_full_text():
    """Sections must cover the entire document with no gaps."""
    for pdf_name in ["noname1.pdf", "noname2.pdf", "noname3.pdf"]:
        ex = extract_document(FIXTURES / pdf_name)
        assert ex.sections, f"{pdf_name}: no sections detected"
        assert ex.sections[0].char_start == 0, f"{pdf_name}: first section starts at {ex.sections[0].char_start}, not 0"
        assert ex.sections[-1].char_end == len(ex.full_markdown), f"{pdf_name}: last section ends at {ex.sections[-1].char_end}, not {len(ex.full_markdown)}"
        for i in range(len(ex.sections) - 1):
            assert ex.sections[i].char_end == ex.sections[i + 1].char_start, (
                f"{pdf_name}: gap between sections {i} ({ex.sections[i].heading_text[:30]!r}) "
                f"and {i+1} ({ex.sections[i+1].heading_text[:30]!r})"
            )
