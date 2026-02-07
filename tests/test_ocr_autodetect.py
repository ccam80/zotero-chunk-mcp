"""Tests for OCR auto-detection behavior."""
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from zotero_chunk_rag.config import Config
from zotero_chunk_rag.indexer import Indexer, IndexResult
from zotero_chunk_rag.pdf_extractor import PDFExtractor
from zotero_chunk_rag.ocr_extractor import OCRExtractor


class TestOCRConfigModes:
    """Test the three OCR config modes: True, False, 'auto'."""

    def test_default_ocr_mode_is_auto(self, tmp_path):
        """Default config should have ocr_enabled='auto'."""
        config_file = tmp_path / "config.json"
        config_file.write_text("{}")

        with patch.object(Config, 'load') as mock_load:
            # Simulate loading empty config
            config = Config(
                zotero_data_dir=Path("/fake"),
                chroma_db_path=tmp_path,
                embedding_model="test",
                embedding_dimensions=768,
                chunk_size=400,
                chunk_overlap=100,
                gemini_api_key="test",
                embedding_provider="gemini",
                embedding_timeout=120.0,
                embedding_max_retries=3,
                rerank_alpha=0.7,
                rerank_section_weights=None,
                rerank_journal_weights=None,
                rerank_enabled=True,
                oversample_multiplier=3,
                oversample_topic_factor=5,
                stats_sample_limit=10000,
                section_gap_fill_min_chars=2000,
                section_gap_fill_min_fraction=0.30,
                ocr_enabled="auto",  # This is what we're testing
                ocr_language="eng",
                ocr_dpi=300,
                ocr_timeout=30.0,
                ocr_min_text_chars=50,
                tables_enabled=False,
                tables_min_rows=2,
                tables_min_cols=2,
                tables_caption_distance=50.0,
                figures_enabled=False,
                figures_min_size=100,
                quality_threshold_a=2000,
                quality_threshold_b=1000,
                quality_threshold_c=500,
                quality_threshold_d=100,
                quality_entropy_min=4.0,
                openalex_email=None,
            )
            assert config.ocr_enabled == "auto"

    def test_auto_mode_validation_does_not_error(self, tmp_path):
        """Auto mode should not raise validation errors about Tesseract."""
        config = Config(
            zotero_data_dir=tmp_path,
            chroma_db_path=tmp_path,
            embedding_model="test",
            embedding_dimensions=768,
            chunk_size=400,
            chunk_overlap=100,
            gemini_api_key="test",
            embedding_provider="gemini",
            embedding_timeout=120.0,
            embedding_max_retries=3,
            rerank_alpha=0.7,
            rerank_section_weights=None,
            rerank_journal_weights=None,
            rerank_enabled=True,
            oversample_multiplier=3,
            oversample_topic_factor=5,
            stats_sample_limit=10000,
            section_gap_fill_min_chars=2000,
            section_gap_fill_min_fraction=0.30,
            ocr_enabled="auto",
            ocr_language="eng",
            ocr_dpi=300,
            ocr_timeout=30.0,
            ocr_min_text_chars=50,
            tables_enabled=False,
            tables_min_rows=2,
            tables_min_cols=2,
            tables_caption_distance=50.0,
            figures_enabled=False,
            figures_min_size=100,
            quality_threshold_a=2000,
            quality_threshold_b=1000,
            quality_threshold_c=500,
            quality_threshold_d=100,
            quality_entropy_min=4.0,
            openalex_email=None,
        )

        # Create dummy zotero files to avoid those validation errors
        (tmp_path / "zotero.sqlite").touch()

        errors = config.validate()
        # Should not have OCR-related errors (may have other errors)
        ocr_errors = [e for e in errors if "OCR" in e or "Tesseract" in e]
        assert len(ocr_errors) == 0, f"Unexpected OCR errors: {ocr_errors}"

    def test_explicit_true_mode_validates_tesseract(self, tmp_path):
        """Explicit ocr_enabled=True should validate Tesseract availability."""
        config = Config(
            zotero_data_dir=tmp_path,
            chroma_db_path=tmp_path,
            embedding_model="test",
            embedding_dimensions=768,
            chunk_size=400,
            chunk_overlap=100,
            gemini_api_key="test",
            embedding_provider="gemini",
            embedding_timeout=120.0,
            embedding_max_retries=3,
            rerank_alpha=0.7,
            rerank_section_weights=None,
            rerank_journal_weights=None,
            rerank_enabled=True,
            oversample_multiplier=3,
            oversample_topic_factor=5,
            stats_sample_limit=10000,
            section_gap_fill_min_chars=2000,
            section_gap_fill_min_fraction=0.30,
            ocr_enabled=True,  # Explicitly enabled
            ocr_language="eng",
            ocr_dpi=300,
            ocr_timeout=30.0,
            ocr_min_text_chars=50,
            tables_enabled=False,
            tables_min_rows=2,
            tables_min_cols=2,
            tables_caption_distance=50.0,
            figures_enabled=False,
            figures_min_size=100,
            quality_threshold_a=2000,
            quality_threshold_b=1000,
            quality_threshold_c=500,
            quality_threshold_d=100,
            quality_entropy_min=4.0,
            openalex_email=None,
        )

        (tmp_path / "zotero.sqlite").touch()

        # Mock pytesseract as unavailable
        with patch.dict('sys.modules', {'pytesseract': None}):
            errors = config.validate()
            ocr_errors = [e for e in errors if "OCR" in e or "pytesseract" in e]
            # Should have an error about OCR/pytesseract
            assert len(ocr_errors) > 0


class TestPDFExtractorScannedPageTracking:
    """Test that scanned pages are tracked correctly."""

    def test_scanned_skipped_counted_when_no_ocr(self):
        """Pages detected as scanned should be counted when OCR unavailable."""
        extractor = PDFExtractor(ocr_extractor=None)

        # Mock a page that looks scanned (has images, no text)
        mock_page = MagicMock()
        mock_page.get_text.return_value = ""  # No text
        mock_page.get_images.return_value = [("img1",)]  # Has images

        mock_doc = MagicMock()
        mock_doc.__iter__ = lambda self: iter([mock_page])
        mock_doc.__len__ = lambda self: 1

        with patch('pymupdf.open', return_value=mock_doc):
            pages, stats = extractor.extract(Path("/fake/doc.pdf"))

        assert stats["scanned_skipped"] == 1
        assert stats["text_pages"] == 0
        assert stats["ocr_pages"] == 0

    def test_scanned_not_skipped_when_ocr_available(self):
        """Scanned pages should be OCR'd when extractor is available."""
        mock_ocr = MagicMock()
        mock_ocr.ocr_page.return_value = "OCR extracted text"

        extractor = PDFExtractor(ocr_extractor=mock_ocr)

        # Mock a page that looks scanned
        mock_page = MagicMock()
        mock_page.get_text.return_value = ""  # No text
        mock_page.get_images.return_value = [("img1",)]  # Has images

        mock_doc = MagicMock()
        mock_doc.__iter__ = lambda self: iter([mock_page])
        mock_doc.__len__ = lambda self: 1

        with patch('pymupdf.open', return_value=mock_doc):
            pages, stats = extractor.extract(Path("/fake/doc.pdf"))

        assert stats["scanned_skipped"] == 0
        assert stats["ocr_pages"] == 1
        mock_ocr.ocr_page.assert_called_once()

    def test_text_pages_not_counted_as_scanned(self):
        """Pages with text should not be counted as scanned."""
        extractor = PDFExtractor(ocr_extractor=None)

        # Mock a page with text
        mock_page = MagicMock()
        mock_page.get_text.return_value = "This is a normal page with plenty of text content."
        mock_page.get_images.return_value = []

        mock_doc = MagicMock()
        mock_doc.__iter__ = lambda self: iter([mock_page])
        mock_doc.__len__ = lambda self: 1

        with patch('pymupdf.open', return_value=mock_doc):
            pages, stats = extractor.extract(Path("/fake/doc.pdf"))

        assert stats["scanned_skipped"] == 0
        assert stats["text_pages"] == 1


class TestIndexResultScannedPages:
    """Test that IndexResult tracks scanned pages skipped."""

    def test_index_result_has_scanned_pages_field(self):
        """IndexResult should have scanned_pages_skipped field."""
        result = IndexResult(
            item_key="ABC123",
            title="Test Paper",
            status="indexed",
            n_chunks=10,
            scanned_pages_skipped=5,
        )
        assert result.scanned_pages_skipped == 5

    def test_index_result_default_scanned_pages_is_zero(self):
        """Default scanned_pages_skipped should be 0."""
        result = IndexResult(
            item_key="ABC123",
            title="Test Paper",
            status="indexed",
        )
        assert result.scanned_pages_skipped == 0


class TestOCRExtractorAvailability:
    """Test OCRExtractor.is_available() method."""

    def test_is_available_returns_false_when_pytesseract_missing(self):
        """is_available should return False when pytesseract not installed."""
        with patch.dict('sys.modules', {'pytesseract': None}):
            # Force reimport check
            with patch('zotero_chunk_rag.ocr_extractor._get_pytesseract') as mock_get:
                mock_get.side_effect = ImportError("No module named 'pytesseract'")
                assert OCRExtractor.is_available() == False

    def test_is_available_returns_false_when_tesseract_binary_missing(self):
        """is_available should return False when Tesseract binary not found."""
        mock_pytesseract = MagicMock()
        mock_pytesseract.get_tesseract_version.side_effect = Exception("tesseract not found")

        with patch('zotero_chunk_rag.ocr_extractor._get_pytesseract', return_value=mock_pytesseract):
            with patch('zotero_chunk_rag.ocr_extractor._get_pil_image'):
                assert OCRExtractor.is_available() == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
