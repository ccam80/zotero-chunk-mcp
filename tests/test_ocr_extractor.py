"""Tests for OCR extraction."""
import pytest
from unittest.mock import MagicMock, patch


class TestOCRExtractorAvailability:
    """Test OCR availability detection without requiring Tesseract."""

    def test_is_available_returns_bool(self):
        """is_available() should return a boolean."""
        from zotero_chunk_rag.ocr_extractor import OCRExtractor
        result = OCRExtractor.is_available()
        assert isinstance(result, bool)


class TestOCRExtractorInit:
    """Test OCRExtractor initialization."""

    def test_init_defaults(self):
        """Should initialize with default values."""
        from zotero_chunk_rag.ocr_extractor import OCRExtractor
        ocr = OCRExtractor()
        assert ocr.language == "eng"
        assert ocr.dpi == 300
        assert ocr.timeout == 30.0
        assert ocr.min_text_chars == 50

    def test_init_custom_values(self):
        """Should accept custom values."""
        from zotero_chunk_rag.ocr_extractor import OCRExtractor
        ocr = OCRExtractor(
            language="deu",
            dpi=150,
            timeout=60.0,
            min_text_chars=100
        )
        assert ocr.language == "deu"
        assert ocr.dpi == 150
        assert ocr.timeout == 60.0
        assert ocr.min_text_chars == 100


class TestOCRExtractorPageDetection:
    """Test page detection logic with mocked PyMuPDF."""

    def test_is_image_only_page_with_sufficient_text(self):
        """Page with sufficient text should not be flagged."""
        from zotero_chunk_rag.ocr_extractor import OCRExtractor
        ocr = OCRExtractor(min_text_chars=50)

        mock_page = MagicMock()
        mock_page.get_text.return_value = "A" * 100
        mock_page.get_images.return_value = []

        assert not ocr.is_image_only_page(mock_page)

    def test_is_image_only_page_with_little_text_and_images(self):
        """Page with little text but images should be flagged."""
        from zotero_chunk_rag.ocr_extractor import OCRExtractor
        ocr = OCRExtractor(min_text_chars=50)

        mock_page = MagicMock()
        mock_page.get_text.return_value = "Short"
        mock_page.get_images.return_value = [(1, 2, 3, 4, 5, 6, 7)]

        assert ocr.is_image_only_page(mock_page)

    def test_is_image_only_page_empty_no_images(self):
        """Empty page without images should not be flagged for OCR."""
        from zotero_chunk_rag.ocr_extractor import OCRExtractor
        ocr = OCRExtractor(min_text_chars=50)

        mock_page = MagicMock()
        mock_page.get_text.return_value = ""
        mock_page.get_images.return_value = []

        assert not ocr.is_image_only_page(mock_page)

    def test_is_image_only_page_whitespace_only(self):
        """Page with only whitespace should check for images."""
        from zotero_chunk_rag.ocr_extractor import OCRExtractor
        ocr = OCRExtractor(min_text_chars=50)

        mock_page = MagicMock()
        mock_page.get_text.return_value = "   \n\t  "
        mock_page.get_images.return_value = [(1, 2, 3)]

        assert ocr.is_image_only_page(mock_page)
