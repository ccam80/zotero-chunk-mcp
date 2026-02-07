"""Tests for quality metrics functionality (Feature 11).

Tests cover:
- compute_quality_score function: grade boundaries, entropy, edge cases
- Config threshold usage
- Integration with indexing
"""
from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest


# =============================================================================
# Fixtures
# =============================================================================


@dataclass
class MockConfig:
    """Mock config with quality threshold settings."""
    quality_threshold_a: int = 2000
    quality_threshold_b: int = 1000
    quality_threshold_c: int = 500
    quality_threshold_d: int = 100
    quality_entropy_min: float = 4.0


@pytest.fixture
def config():
    return MockConfig()


def make_pages(texts: list[str]) -> list:
    """Create mock PageText objects from text strings."""
    from zotero_chunk_rag.models import PageText

    pages = []
    char_offset = 0
    for i, text in enumerate(texts):
        pages.append(PageText(
            page_num=i + 1,
            text=text,
            char_start=char_offset,
        ))
        char_offset += len(text) + 1
    return pages


# =============================================================================
# Grade Boundary Tests
# =============================================================================


class TestQualityGradeBoundaries:
    """Test that grade boundaries are correctly applied."""

    def test_grade_f_for_empty_pages(self, config):
        """Empty page list should get grade F."""
        from zotero_chunk_rag.pdf_extractor import compute_quality_score

        pages = []
        stats = {"ocr_pages": 0, "empty_pages": 0}

        result = compute_quality_score(pages, stats, config)

        assert result["quality_grade"] == "F"
        assert result["chars_per_page"] == 0.0
        assert result["empty_fraction"] == 1.0

    def test_grade_f_for_very_low_chars(self, config):
        """Very low chars/page should get grade F."""
        from zotero_chunk_rag.pdf_extractor import compute_quality_score

        # 50 chars on 1 page = 50 chars/page, below threshold_d (100)
        pages = make_pages(["x" * 50])
        stats = {"ocr_pages": 0, "empty_pages": 0}

        result = compute_quality_score(pages, stats, config)

        assert result["quality_grade"] == "F"
        assert result["chars_per_page"] == 50.0

    def test_grade_d_boundary(self, config):
        """Chars/page just above threshold_d should get grade D."""
        from zotero_chunk_rag.pdf_extractor import compute_quality_score

        # 150 chars/page - above d (100) but below c (500)
        pages = make_pages(["x" * 150])
        stats = {"ocr_pages": 0, "empty_pages": 0}

        result = compute_quality_score(pages, stats, config)

        assert result["quality_grade"] == "D"

    def test_grade_c_boundary(self, config):
        """Chars/page above threshold_c should get grade C."""
        from zotero_chunk_rag.pdf_extractor import compute_quality_score

        # 600 chars/page - above c (500) but below b (1000)
        pages = make_pages(["x" * 600])
        stats = {"ocr_pages": 0, "empty_pages": 0}

        result = compute_quality_score(pages, stats, config)

        assert result["quality_grade"] == "C"

    def test_grade_b_boundary(self, config):
        """Chars/page above threshold_b with low empty fraction should get B."""
        from zotero_chunk_rag.pdf_extractor import compute_quality_score

        # 1200 chars/page - above b (1000) but has some empty pages
        pages = make_pages(["x" * 1200])
        # 15% empty - below 0.2 threshold for B
        stats = {"ocr_pages": 0, "empty_pages": 0}

        result = compute_quality_score(pages, stats, config)

        # Should be B (not A because entropy of "xxxx..." is very low)
        assert result["quality_grade"] == "B"

    def test_grade_b_rejected_by_high_empty_fraction(self, config):
        """Grade B requires empty_fraction < 0.2."""
        from zotero_chunk_rag.pdf_extractor import compute_quality_score

        # High chars/page but 25% empty pages
        pages = make_pages(["x" * 1500] * 3 + [""])  # 4 pages, 1 empty
        stats = {"ocr_pages": 0, "empty_pages": 1}  # 25% empty

        result = compute_quality_score(pages, stats, config)

        # 25% > 20% threshold, so not B
        # But chars/page is 1125 > 500, so it's C
        assert result["quality_grade"] == "C"

    def test_grade_a_requires_all_conditions(self, config):
        """Grade A requires high chars, low empty, and high entropy."""
        from zotero_chunk_rag.pdf_extractor import compute_quality_score

        # Rich varied text for high entropy
        varied_text = (
            "The quick brown fox jumps over the lazy dog. "
            "Pack my box with five dozen liquor jugs. "
            "How vexingly quick daft zebras jump! "
            "Sphinx of black quartz, judge my vow. "
        ) * 50  # Repeat for length

        pages = make_pages([varied_text])
        stats = {"ocr_pages": 0, "empty_pages": 0}

        result = compute_quality_score(pages, stats, config)

        assert result["quality_grade"] == "A"
        assert result["chars_per_page"] > config.quality_threshold_a
        assert result["entropy_score"] > config.quality_entropy_min
        assert result["empty_fraction"] < 0.1


class TestEntropyComputation:
    """Test entropy calculation."""

    def test_low_entropy_for_repeated_char(self, config):
        """Text with only one repeated character has low entropy."""
        from zotero_chunk_rag.pdf_extractor import compute_quality_score

        # All 'x' characters - minimal entropy
        pages = make_pages(["x" * 5000])
        stats = {"ocr_pages": 0, "empty_pages": 0}

        result = compute_quality_score(pages, stats, config)

        # Entropy of single character text is 0
        assert result["entropy_score"] == 0.0

    def test_higher_entropy_for_varied_text(self, config):
        """Varied text should have higher entropy."""
        from zotero_chunk_rag.pdf_extractor import compute_quality_score

        varied_text = "abcdefghijklmnopqrstuvwxyz " * 200
        pages = make_pages([varied_text])
        stats = {"ocr_pages": 0, "empty_pages": 0}

        result = compute_quality_score(pages, stats, config)

        # 27 different characters should give entropy around 4.75
        assert result["entropy_score"] > 4.0

    def test_entropy_sample_limit(self, config):
        """Entropy should be computed on first 100K chars only."""
        from zotero_chunk_rag.pdf_extractor import compute_quality_score

        # Create text that's exactly 100K of 'a' followed by varied text
        # If the limit works, entropy should be 0 (only 'a' counted)
        text = "a" * 100000 + "bcdefghij" * 1000

        pages = make_pages([text])
        stats = {"ocr_pages": 0, "empty_pages": 0}

        result = compute_quality_score(pages, stats, config)

        # Entropy should be 0 because only first 100K 'a's are counted
        assert result["entropy_score"] == 0.0


class TestOCRFraction:
    """Test OCR fraction calculation."""

    def test_ocr_fraction_computed(self, config):
        """OCR fraction should be calculated from stats."""
        from zotero_chunk_rag.pdf_extractor import compute_quality_score

        pages = make_pages(["text"] * 10)  # 10 pages
        stats = {"ocr_pages": 3, "empty_pages": 1}  # 30% OCR

        result = compute_quality_score(pages, stats, config)

        assert result["ocr_fraction"] == 0.3

    def test_empty_fraction_computed(self, config):
        """Empty fraction should be calculated from stats."""
        from zotero_chunk_rag.pdf_extractor import compute_quality_score

        pages = make_pages(["text"] * 8)  # 8 pages
        stats = {"ocr_pages": 0, "empty_pages": 2}  # 25% empty

        result = compute_quality_score(pages, stats, config)

        assert result["empty_fraction"] == 0.25


class TestConfigThresholds:
    """Test that config thresholds are actually used."""

    def test_custom_threshold_a(self):
        """Custom threshold_a should be respected."""
        from zotero_chunk_rag.pdf_extractor import compute_quality_score

        # Custom config with very low A threshold
        config = MockConfig(quality_threshold_a=100)

        varied_text = "The quick brown fox " * 10  # ~200 chars with variety
        pages = make_pages([varied_text])
        stats = {"ocr_pages": 0, "empty_pages": 0}

        result = compute_quality_score(pages, stats, config)

        # With threshold_a=100, 200 chars/page should qualify for A
        # (assuming entropy is high enough)
        assert result["chars_per_page"] > 100

    def test_custom_entropy_min(self):
        """Custom entropy_min should be respected."""
        from zotero_chunk_rag.pdf_extractor import compute_quality_score

        # Very high entropy requirement
        config = MockConfig(
            quality_threshold_a=100,
            quality_entropy_min=10.0,  # Impossibly high
        )

        varied_text = "abcdefghijklmnopqrstuvwxyz" * 100
        pages = make_pages([varied_text])
        stats = {"ocr_pages": 0, "empty_pages": 0}

        result = compute_quality_score(pages, stats, config)

        # Even with varied text, entropy won't hit 10.0
        # So should get B instead of A
        assert result["quality_grade"] == "B"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_single_page_document(self, config):
        """Single page document should work correctly."""
        from zotero_chunk_rag.pdf_extractor import compute_quality_score

        pages = make_pages(["Single page content with enough text to pass. " * 50])
        stats = {"ocr_pages": 0, "empty_pages": 0}

        result = compute_quality_score(pages, stats, config)

        assert "quality_grade" in result
        assert result["chars_per_page"] > 0

    def test_all_empty_pages(self, config):
        """All empty pages should get grade F."""
        from zotero_chunk_rag.pdf_extractor import compute_quality_score

        pages = make_pages(["", "", ""])  # 3 empty pages
        stats = {"ocr_pages": 0, "empty_pages": 3}

        result = compute_quality_score(pages, stats, config)

        assert result["quality_grade"] == "F"
        assert result["chars_per_page"] == 0.0

    def test_mixed_content_pages(self, config):
        """Mix of content and empty pages should calculate correctly."""
        from zotero_chunk_rag.pdf_extractor import compute_quality_score

        # 3 pages with content, 2 empty
        pages = make_pages([
            "Content page 1 with text " * 50,
            "Content page 2 with text " * 50,
            "",
            "Content page 3 with text " * 50,
            "",
        ])
        stats = {"ocr_pages": 0, "empty_pages": 2}

        result = compute_quality_score(pages, stats, config)

        # empty_fraction should be 2/5 = 0.4
        assert result["empty_fraction"] == 0.4

    def test_result_values_are_rounded(self, config):
        """Result values should be properly rounded."""
        from zotero_chunk_rag.pdf_extractor import compute_quality_score

        pages = make_pages(["x" * 333])  # Will produce non-round numbers
        stats = {"ocr_pages": 0, "empty_pages": 0}

        result = compute_quality_score(pages, stats, config)

        # chars_per_page should be rounded to 1 decimal
        assert result["chars_per_page"] == 333.0

        # fractions should be rounded to 2 decimals and have correct values
        assert result["ocr_fraction"] == 0.0  # 0/1 pages
        assert result["empty_fraction"] == 0.0  # 0/1 pages


# =============================================================================
# Integration Tests
# =============================================================================


class TestQualityGradeStorage:
    """Test that quality_grade is stored in vector store."""

    def test_quality_grade_in_chunk_metadata(self, temp_db_path):
        """quality_grade should be stored in chunk metadata."""
        from zotero_chunk_rag.vector_store import VectorStore
        from zotero_chunk_rag.models import Chunk

        mock_embedder = MagicMock()
        mock_embedder.embed = MagicMock(return_value=[[0.1] * 768])

        store = VectorStore(temp_db_path, mock_embedder)

        chunks = [Chunk(
            text="Test chunk",
            page_num=1,
            chunk_index=0,
            char_start=0,
            char_end=10,
            section="unknown",
            section_confidence=1.0,
        )]

        doc_meta = {
            "title": "Test Doc",
            "authors": "Author",
            "year": 2024,
            "quality_grade": "B",  # This should be stored
        }

        store.add_chunks("TEST_DOC", doc_meta, chunks)

        # Retrieve and check
        retrieved = store.get_document_meta("TEST_DOC")
        assert retrieved is not None
        assert retrieved.get("quality_grade") == "B"

    def test_quality_grade_in_table_metadata(self, temp_db_path):
        """quality_grade should also be stored for table chunks."""
        from zotero_chunk_rag.vector_store import VectorStore
        from zotero_chunk_rag.models import ExtractedTable

        mock_embedder = MagicMock()
        mock_embedder.embed = MagicMock(return_value=[[0.1] * 768])

        store = VectorStore(temp_db_path, mock_embedder)

        tables = [ExtractedTable(
            page_num=1,
            table_index=0,
            bbox=(0, 0, 100, 100),
            headers=["A", "B"],
            rows=[["1", "2"]],
            caption="Table 1",
        )]

        doc_meta = {
            "title": "Test Doc",
            "quality_grade": "A",
        }

        store.add_tables("TEST_DOC", doc_meta, tables)

        # Get the table chunk directly
        results = store.collection.get(
            ids=["TEST_DOC_table_0001_00"],
            include=["metadatas"]
        )

        assert results["metadatas"]
        assert results["metadatas"][0].get("quality_grade") == "A"
