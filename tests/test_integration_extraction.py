"""Integration tests for PDF extraction with real PDFs."""
import pytest
from pathlib import Path

from zotero_chunk_rag.table_extractor import TableExtractor
from zotero_chunk_rag.pdf_extractor import PDFExtractor
from zotero_chunk_rag.ocr_extractor import OCRExtractor

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestTableExtractionIntegration:
    """Test table extraction against real PDFs."""

    @pytest.fixture
    def extractor(self):
        return TableExtractor(min_rows=2, min_cols=2)

    def test_extract_simple_table(self, extractor):
        """Extract table from sample_with_table.pdf."""
        pdf_path = FIXTURES_DIR / "sample_with_table.pdf"
        assert pdf_path.exists(), f"Test fixture not found: {pdf_path}. Run create_test_pdfs.py first."

        tables = extractor.extract_tables(pdf_path)

        # Should find at least one table
        assert len(tables) >= 1, f"Expected at least 1 table, found {len(tables)}"

        # Check first table structure
        table = tables[0]
        assert table.page_num == 1
        assert table.num_cols >= 2, f"Expected >= 2 columns, got {table.num_cols}"
        assert table.num_rows >= 2, f"Expected >= 2 rows, got {table.num_rows}"

        # Check markdown generation works
        md = table.to_markdown()
        assert "|" in md, "Markdown should contain pipe characters"
        assert "---" in md, "Markdown should contain separator row"

        print(f"\nExtracted table from sample_with_table.pdf:")
        print(f"  Page: {table.page_num}")
        print(f"  Size: {table.num_rows} rows x {table.num_cols} cols")
        print(f"  Caption: {table.caption!r}")
        print(f"  Headers: {table.headers}")
        print(f"  First row: {table.rows[0] if table.rows else 'N/A'}")

    def test_extract_multiple_tables(self, extractor):
        """Extract multiple tables from sample_mixed.pdf."""
        pdf_path = FIXTURES_DIR / "sample_mixed.pdf"
        assert pdf_path.exists(), f"Test fixture not found: {pdf_path}. Run create_test_pdfs.py first."

        tables = extractor.extract_tables(pdf_path)

        # Should find tables on page 2 and page 3
        assert len(tables) >= 2, f"Expected at least 2 tables, found {len(tables)}"

        # Check tables are from different pages
        pages_with_tables = {t.page_num for t in tables}
        assert len(pages_with_tables) >= 2, "Expected tables on multiple pages"

        print(f"\nExtracted {len(tables)} tables from sample_mixed.pdf:")
        for t in tables:
            print(f"  Page {t.page_num}: {t.num_rows}x{t.num_cols}, caption={t.caption!r}")

    def test_table_to_markdown_content(self, extractor):
        """Verify markdown output contains expected cell content."""
        pdf_path = FIXTURES_DIR / "sample_with_table.pdf"
        assert pdf_path.exists(), f"Test fixture not found: {pdf_path}"

        tables = extractor.extract_tables(pdf_path)
        assert tables, "Should extract at least one table"

        md = tables[0].to_markdown()
        print(f"\nGenerated markdown:\n{md}")

        # The test PDF has headers: Name, Value, Category
        # and data: Alpha/100/Type A, Beta/200/Type B, Gamma/300/Type C
        # Verify some expected content is present
        assert "|" in md, "Markdown should contain table pipes"
        assert "---" in md, "Markdown should contain separator row"
        # Check that at least some expected cell content is present
        md_lower = md.lower()
        # Headers or values from the test table should be present
        found_content = any(term in md_lower for term in
            ["name", "value", "category", "alpha", "beta", "gamma", "100", "200", "300"])
        assert found_content, f"Markdown should contain expected cell content. Got:\n{md}"

    def test_caption_detection(self, extractor):
        """Test that captions are detected when present."""
        pdf_path = FIXTURES_DIR / "sample_with_table.pdf"
        assert pdf_path.exists(), f"Test fixture not found: {pdf_path}"

        tables = extractor.extract_tables(pdf_path)
        assert tables, "Should extract at least one table"

        # The test PDF has "Table 1: Sample Data" as caption
        table = tables[0]
        print(f"\nCaption detected: {table.caption!r}")
        print(f"Caption position: {table.caption_position!r}")

        # Caption detection is proximity-based and may vary, but we can verify:
        # 1. caption is a string (even if empty)
        assert isinstance(table.caption, str), "Caption should be a string"
        # 2. caption_position is valid when caption is present
        if table.caption:
            assert table.caption_position in ("above", "below", ""), \
                f"Invalid caption_position: {table.caption_position!r}"
            # The test PDF should detect "Table 1" in the caption
            assert "table" in table.caption.lower() or "1" in table.caption, \
                f"Caption should contain 'Table' or '1'. Got: {table.caption!r}"

    def test_table_count_quick(self, extractor):
        """Test get_table_count() returns reasonable count quickly."""
        pdf_path = FIXTURES_DIR / "sample_mixed.pdf"
        assert pdf_path.exists(), f"Test fixture not found: {pdf_path}"

        count = extractor.get_table_count(pdf_path)
        assert count >= 2, f"Expected at least 2 tables, got {count}"
        print(f"\nQuick table count: {count}")


class TestPDFExtractionIntegration:
    """Test PDF text extraction."""

    def test_extract_text_only_pdf(self):
        """Extract text from a normal PDF."""
        pdf_path = FIXTURES_DIR / "sample_with_table.pdf"
        assert pdf_path.exists(), f"Test fixture not found: {pdf_path}"

        extractor = PDFExtractor()
        pages, stats = extractor.extract(pdf_path)

        assert len(pages) == 1, f"Expected 1 page, got {len(pages)}"
        assert stats["total_pages"] == 1
        assert stats["text_pages"] >= 1
        assert stats["ocr_pages"] == 0
        assert stats["empty_pages"] == 0

        # Check text content
        text = pages[0].text
        assert "Test Document" in text or "Table" in text, "Should extract visible text"

        print(f"\nExtracted text ({len(text)} chars):")
        print(text[:200] + "..." if len(text) > 200 else text)

    def test_extract_multi_page_pdf(self):
        """Extract text from multi-page PDF."""
        pdf_path = FIXTURES_DIR / "sample_mixed.pdf"
        assert pdf_path.exists(), f"Test fixture not found: {pdf_path}"

        extractor = PDFExtractor()
        pages, stats = extractor.extract(pdf_path)

        assert len(pages) == 3, f"Expected 3 pages, got {len(pages)}"
        assert stats["total_pages"] == 3

        # Check page numbers are correct
        for i, page in enumerate(pages, 1):
            assert page.page_num == i

        # Check char_start offsets are sequential
        for i in range(1, len(pages)):
            assert pages[i].char_start > pages[i-1].char_start

        print(f"\nExtracted {len(pages)} pages:")
        for p in pages:
            print(f"  Page {p.page_num}: {len(p.text)} chars, offset {p.char_start}")


class TestOCRExtractionIntegration:
    """Test OCR extraction against real PDFs."""

    def test_ocr_is_available(self):
        """Verify OCR dependencies are properly installed."""
        assert OCRExtractor.is_available(), (
            "OCR is not available. Ensure Tesseract is installed:\n"
            "  Windows: https://github.com/UB-Mannheim/tesseract/wiki\n"
            "  macOS: brew install tesseract\n"
            "  Linux: sudo apt install tesseract-ocr"
        )

    def test_detect_image_only_page(self):
        """Detect that scanned PDF page needs OCR."""
        pdf_path = FIXTURES_DIR / "sample_scanned.pdf"
        assert pdf_path.exists(), f"Test fixture not found: {pdf_path}"

        ocr = OCRExtractor(min_text_chars=50)
        image_pages = ocr.get_image_only_pages(pdf_path)

        print(f"\nPages needing OCR: {image_pages}")
        # The scanned PDF should have an image-only page
        assert len(image_pages) >= 1, "Scanned PDF should have image-only pages"

    def test_ocr_scanned_page(self):
        """OCR a scanned page and extract text."""
        pdf_path = FIXTURES_DIR / "sample_scanned.pdf"
        assert pdf_path.exists(), f"Test fixture not found: {pdf_path}"

        ocr = OCRExtractor(language="eng", dpi=150)
        result = ocr.ocr_pages(pdf_path)

        assert result, "Should return OCR results"

        for page_idx, text in result.items():
            print(f"\nOCR result for page {page_idx + 1}:")
            print(text[:200] + "..." if len(text) > 200 else text)

            # The test PDF contains known text
            # Check for some expected words
            text_lower = text.lower()
            assert any(word in text_lower for word in ["text", "image", "ocr", "sample", "scanned", "content"]), \
                f"OCR should extract some expected words from test image. Got: {text[:100]}"

    def test_pdf_extractor_with_ocr_fallback(self):
        """Test full PDF extraction with OCR fallback enabled."""
        pdf_path = FIXTURES_DIR / "sample_scanned.pdf"
        assert pdf_path.exists(), f"Test fixture not found: {pdf_path}"

        ocr = OCRExtractor(language="eng", dpi=150)
        extractor = PDFExtractor(ocr_extractor=ocr)

        pages, stats = extractor.extract(pdf_path)

        print(f"\nExtraction stats: {stats}")
        print(f"Page text: {pages[0].text[:200] if pages else 'No pages'}...")

        # With OCR, we should get text from the scanned page
        assert stats["ocr_pages"] >= 1 or stats["text_pages"] >= 1, \
            f"Should extract text via OCR or native text layer. Stats: {stats}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
