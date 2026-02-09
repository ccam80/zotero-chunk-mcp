"""Unit tests for pdf_processor module."""


def test_layout_import_order():
    """pymupdf.layout must be importable."""
    import pymupdf.layout


def test_noname1_page_count(extracted_papers):
    ex = extracted_papers["noname1.pdf"]
    assert len(ex.pages) == 19


def test_noname1_quality(extracted_papers):
    ex = extracted_papers["noname1.pdf"]
    assert ex.quality_grade == "A"
    assert ex.stats["empty_pages"] == 0
    assert len(ex.full_markdown) > 50000


def test_noname2_page_count(extracted_papers):
    ex = extracted_papers["noname2.pdf"]
    assert len(ex.pages) == 21


def test_noname2_quality(extracted_papers):
    ex = extracted_papers["noname2.pdf"]
    assert ex.quality_grade == "A"
    assert ex.stats["empty_pages"] == 0
    assert len(ex.full_markdown) > 50000


def test_noname3_page_count(extracted_papers):
    ex = extracted_papers["noname3.pdf"]
    assert len(ex.pages) == 14


def test_noname3_quality(extracted_papers):
    ex = extracted_papers["noname3.pdf"]
    assert ex.quality_grade == "A"
    assert ex.stats["empty_pages"] == 0
    assert len(ex.full_markdown) > 50000
