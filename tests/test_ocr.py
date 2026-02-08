"""OCR extraction tests — verify pymupdf-layout OCR works on image-only pages."""
from pathlib import Path
import pymupdf
from zotero_chunk_rag.pdf_processor import extract_document


def _create_scanned_pdf(output_path: Path) -> Path:
    """Create a PDF with one image-only page (text rendered as image).

    This simulates a scanned document page. The text 'The quick brown fox
    jumps over the lazy dog' is rendered as a raster image and embedded.
    """
    doc = pymupdf.open()

    # Page 1: normal text (control)
    page1 = doc.new_page(width=612, height=792)
    page1.insert_text((72, 100), "This is a normal text page.", fontsize=12)

    # Page 2: text rendered as image (simulates scan)
    page2 = doc.new_page(width=612, height=792)
    # Create a temporary doc with text, render to pixmap, insert as image
    tmp = pymupdf.open()
    tmp_page = tmp.new_page(width=400, height=100)
    tmp_page.insert_text(
        (20, 50),
        "The quick brown fox jumps over the lazy dog",
        fontsize=14,
    )
    pix = tmp_page.get_pixmap(dpi=200)
    tmp.close()
    # Insert the pixmap as an image on page 2
    img_rect = pymupdf.Rect(72, 100, 472, 300)
    page2.insert_image(img_rect, pixmap=pix)

    doc.save(str(output_path))
    doc.close()
    return output_path


def test_ocr_extracts_text_from_image_page(tmp_path):
    """The image-only page must produce some text via OCR."""
    pdf_path = _create_scanned_pdf(tmp_path / "scanned.pdf")
    ex = extract_document(pdf_path)

    assert len(ex.pages) == 2

    # Page 1 (normal text) should have text
    assert len(ex.pages[0].markdown.strip()) > 10, (
        "Page 1 (normal text) has no content"
    )

    # Page 2 (image-only) — if OCR is working, it should extract some text.
    # At minimum, some words from "The quick brown fox..." should appear.
    page2_text = ex.pages[1].markdown.lower()
    # We check for at least 2 words from the phrase to account for OCR errors
    ocr_words_found = sum(
        1 for w in ["quick", "brown", "fox", "jumps", "lazy", "dog"]
        if w in page2_text
    )
    assert ocr_words_found >= 2, (
        f"OCR failed: only {ocr_words_found}/6 expected words found in page 2. "
        f"Page 2 text: {ex.pages[1].markdown[:200]!r}"
    )


def test_ocr_pages_counted_in_stats(tmp_path):
    """Stats must report ocr_pages > 0 when OCR was used."""
    pdf_path = _create_scanned_pdf(tmp_path / "scanned.pdf")
    ex = extract_document(pdf_path)

    # OCR must work — Tesseract is a required dependency.
    # If this fails, the environment is misconfigured, not the code.
    assert ex.stats["ocr_pages"] >= 1, (
        f"OCR page not counted in stats. ocr_pages={ex.stats['ocr_pages']}. "
        f"Page 2 text: {ex.pages[1].markdown[:200]!r}. "
        f"Stats: {ex.stats}"
    )
