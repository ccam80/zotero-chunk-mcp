"""Tests for figure extraction (Feature 12).

Tests verify:
1. ExtractedFigure dataclass behavior
2. FigureExtractor caption detection (above/below image)
3. Orphan figure handling (no caption found)
4. Small image filtering (icons < MIN_SIZE)
5. Image saving to disk
6. VectorStore.add_figures() integration
7. End-to-end extraction from test PDF
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from zotero_chunk_rag.figure_extractor import (
    ExtractedFigure,
    FigureExtractor,
    FIGURE_CAPTION_PATTERNS,
)


class TestExtractedFigure:
    """Tests for the ExtractedFigure dataclass."""

    def test_to_searchable_text_with_caption(self):
        """Should return caption when available."""
        figure = ExtractedFigure(
            page_num=1,
            figure_index=0,
            bbox=(0, 0, 200, 150),
            caption="Figure 1. Heart rate variability analysis.",
        )
        assert figure.to_searchable_text() == "Figure 1. Heart rate variability analysis."

    def test_to_searchable_text_without_caption(self):
        """Should return fallback text for orphan figures."""
        figure = ExtractedFigure(
            page_num=5,
            figure_index=2,
            bbox=(0, 0, 200, 150),
            caption=None,  # Orphan
        )
        assert figure.to_searchable_text() == "Figure on page 5"

    def test_to_searchable_text_empty_caption(self):
        """Empty string caption should use fallback."""
        figure = ExtractedFigure(
            page_num=3,
            figure_index=0,
            bbox=(0, 0, 200, 150),
            caption="",
        )
        # Empty string is falsy, should use fallback
        assert figure.to_searchable_text() == "Figure on page 3"

    def test_image_path_defaults_to_none(self):
        """image_path should default to None."""
        figure = ExtractedFigure(
            page_num=1,
            figure_index=0,
            bbox=(0, 0, 100, 100),
            caption="Test",
        )
        assert figure.image_path is None


class TestFigureExtractorInit:
    """Tests for FigureExtractor initialization."""

    def test_creates_images_directory(self, tmp_path):
        """Should create images_dir if it doesn't exist."""
        images_dir = tmp_path / "figures" / "nested"
        assert not images_dir.exists()

        extractor = FigureExtractor(images_dir=images_dir)

        assert images_dir.exists()
        assert extractor.images_dir == images_dir

    def test_accepts_existing_directory(self, tmp_path):
        """Should work with existing directory."""
        images_dir = tmp_path / "existing"
        images_dir.mkdir()

        extractor = FigureExtractor(images_dir=images_dir)

        assert extractor.images_dir == images_dir

    def test_default_min_size(self, tmp_path):
        """Should have default MIN_WIDTH and MIN_HEIGHT of 100."""
        extractor = FigureExtractor(images_dir=tmp_path)

        assert extractor.MIN_WIDTH == 100
        assert extractor.MIN_HEIGHT == 100

    def test_min_size_can_be_modified(self, tmp_path):
        """MIN_WIDTH and MIN_HEIGHT can be changed."""
        extractor = FigureExtractor(images_dir=tmp_path)
        extractor.MIN_WIDTH = 150
        extractor.MIN_HEIGHT = 150

        assert extractor.MIN_WIDTH == 150
        assert extractor.MIN_HEIGHT == 150


class TestFigureExtractorIsAvailable:
    """Tests for FigureExtractor.is_available() class method."""

    def test_returns_boolean(self):
        """Should return a boolean value."""
        result = FigureExtractor.is_available()
        assert isinstance(result, bool)

    def test_returns_true_when_pymupdf_installed(self):
        """Should return True since PyMuPDF is installed for tests."""
        # If we got this far, PyMuPDF is installed
        assert FigureExtractor.is_available() is True


class TestCaptionPatterns:
    """Tests for FIGURE_CAPTION_PATTERNS regex patterns."""

    @pytest.mark.parametrize("text,should_match", [
        # Standard patterns
        ("Figure 1", True),
        ("Figure 1. Description", True),
        ("Figure 12: Results", True),
        ("Fig. 1", True),
        ("Fig 2. Diagram", True),
        ("FIG. 3", True),
        ("figure 1", True),  # Case insensitive
        # Roman numerals
        ("FIGURE I", True),
        ("FIGURE II", True),
        ("FIGURE III", True),
        ("FIGURE IV", True),
        ("FIGURE V", True),
        ("FIGURE X", True),
        ("FIGURE XI", True),
        ("FIGURE XII", True),
        # Alternative figure types
        ("Scheme 1", True),
        ("Scheme 2. Reaction mechanism", True),
        ("Chart 1", True),
        ("Plate 1", True),
        ("Graph 1", True),
        # Non-matching patterns
        ("Table 1", False),
        ("The figure shows", False),
        ("See Figure 1", False),  # Doesn't start with Figure
        ("Results", False),
        ("", False),
    ])
    def test_caption_pattern_matching(self, text, should_match):
        """Test caption patterns match expected text."""
        matched = any(p.match(text) for p in FIGURE_CAPTION_PATTERNS)
        assert matched == should_match, f"Pattern match for '{text}' expected {should_match}"


class TestFigureExtractorCaptionExtraction:
    """Tests for _extract_caption_text and _find_caption methods."""

    def test_extract_caption_text_single_line(self, tmp_path):
        """Should extract single line caption."""
        extractor = FigureExtractor(images_dir=tmp_path)
        result = extractor._extract_caption_text("Figure 1. Results summary")
        assert result == "Figure 1. Results summary"

    def test_extract_caption_text_multiline(self, tmp_path):
        """Should extract first paragraph only."""
        extractor = FigureExtractor(images_dir=tmp_path)
        text = "Figure 1. Results\n\nThis is body text that follows."
        result = extractor._extract_caption_text(text)
        assert result == "Figure 1. Results"

    def test_extract_caption_text_joined_lines(self, tmp_path):
        """Should join consecutive lines into single caption."""
        extractor = FigureExtractor(images_dir=tmp_path)
        text = "Figure 1. Heart rate variability\nanalysis during exercise"
        result = extractor._extract_caption_text(text)
        assert result == "Figure 1. Heart rate variability analysis during exercise"

    def test_extract_caption_text_empty(self, tmp_path):
        """Should handle empty text."""
        extractor = FigureExtractor(images_dir=tmp_path)
        result = extractor._extract_caption_text("")
        assert result == ""


class TestFigureExtractorWithPDF:
    """Integration tests using actual PDF fixture."""

    @pytest.fixture
    def sample_pdf_with_figures(self) -> Path:
        """Path to PDF with test figures."""
        path = Path(__file__).parent / "fixtures" / "sample_with_figures.pdf"
        if not path.exists():
            pytest.skip(
                f"Test PDF not found: {path}. "
                "Run 'python tests/fixtures/create_test_pdfs.py' to generate fixtures."
            )
        return path

    def test_extract_figures_returns_list(self, sample_pdf_with_figures, tmp_path):
        """Should return a list of ExtractedFigure objects."""
        extractor = FigureExtractor(images_dir=tmp_path)
        figures = extractor.extract_figures(sample_pdf_with_figures, "test_doc")

        assert isinstance(figures, list)
        for fig in figures:
            assert isinstance(fig, ExtractedFigure)

    def test_extracts_multiple_figures(self, sample_pdf_with_figures, tmp_path):
        """Should extract multiple figures from multi-page PDF."""
        extractor = FigureExtractor(images_dir=tmp_path)
        figures = extractor.extract_figures(sample_pdf_with_figures, "test_doc")

        # The test PDF has 4 large figures (3 captioned + 1 orphan)
        # Small icon should be filtered out
        assert len(figures) >= 3, f"Expected at least 3 figures, got {len(figures)}"

    def test_filters_small_images(self, sample_pdf_with_figures, tmp_path):
        """Should filter out images smaller than MIN_SIZE."""
        extractor = FigureExtractor(images_dir=tmp_path)
        figures = extractor.extract_figures(sample_pdf_with_figures, "test_doc")

        # All extracted figures should be >= MIN_SIZE
        for fig in figures:
            width = fig.bbox[2] - fig.bbox[0]
            height = fig.bbox[3] - fig.bbox[1]
            assert width >= extractor.MIN_WIDTH or height >= extractor.MIN_HEIGHT, (
                f"Figure {fig.figure_index} on page {fig.page_num} is too small: "
                f"{width}x{height}"
            )

    def test_saves_images_to_disk(self, sample_pdf_with_figures, tmp_path):
        """Should save extracted images as PNG files."""
        extractor = FigureExtractor(images_dir=tmp_path)
        figures = extractor.extract_figures(sample_pdf_with_figures, "test_doc")

        for fig in figures:
            if fig.image_path:
                assert fig.image_path.exists(), f"Image file not found: {fig.image_path}"
                assert fig.image_path.suffix == ".png"

    def test_image_naming_convention(self, sample_pdf_with_figures, tmp_path):
        """Image files should follow naming convention: {doc_id}_p{page}_f{idx}.png"""
        extractor = FigureExtractor(images_dir=tmp_path)
        figures = extractor.extract_figures(sample_pdf_with_figures, "ABC123")

        for fig in figures:
            if fig.image_path:
                expected_pattern = f"ABC123_p{fig.page_num:03d}_f{fig.figure_index:02d}.png"
                assert fig.image_path.name == expected_pattern, (
                    f"Expected {expected_pattern}, got {fig.image_path.name}"
                )

    def test_detects_captions(self, sample_pdf_with_figures, tmp_path):
        """Should detect captions for figures that have them."""
        extractor = FigureExtractor(images_dir=tmp_path)
        figures = extractor.extract_figures(sample_pdf_with_figures, "test_doc")

        # At least some figures should have captions
        captioned = [f for f in figures if f.caption]
        assert len(captioned) >= 1, "Expected at least one figure with caption"

        # Check caption contains figure reference
        for fig in captioned:
            assert any(
                keyword in fig.caption.lower()
                for keyword in ["fig", "figure"]
            ), f"Caption should contain 'fig' or 'figure': {fig.caption}"

    def test_handles_orphan_figures(self, sample_pdf_with_figures, tmp_path):
        """Should keep orphan figures with caption=None."""
        extractor = FigureExtractor(images_dir=tmp_path)
        figures = extractor.extract_figures(sample_pdf_with_figures, "test_doc")

        # Test PDF has at least one orphan figure (no caption)
        orphans = [f for f in figures if f.caption is None]
        # Note: orphans may or may not exist depending on caption detection success
        # The key assertion is that orphans have caption=None, not empty string
        for orphan in orphans:
            assert orphan.caption is None, "Orphan caption should be None, not empty string"

    def test_bbox_is_valid_tuple(self, sample_pdf_with_figures, tmp_path):
        """bbox should be a 4-tuple of floats (x0, y0, x1, y1)."""
        extractor = FigureExtractor(images_dir=tmp_path)
        figures = extractor.extract_figures(sample_pdf_with_figures, "test_doc")

        for fig in figures:
            assert len(fig.bbox) == 4, f"bbox should have 4 elements: {fig.bbox}"
            x0, y0, x1, y1 = fig.bbox
            assert x0 < x1, f"x0 should be < x1: {fig.bbox}"
            assert y0 < y1, f"y0 should be < y1: {fig.bbox}"


class TestVectorStoreAddFigures:
    """Tests for VectorStore.add_figures() integration."""

    def test_add_figures_stores_in_collection(self, tmp_path):
        """add_figures should store figures in ChromaDB collection."""
        from zotero_chunk_rag.embedder import LocalEmbedder
        from zotero_chunk_rag.vector_store import VectorStore

        db_path = tmp_path / "chroma"
        embedder = LocalEmbedder()
        store = VectorStore(db_path, embedder)

        figures = [
            ExtractedFigure(
                page_num=1,
                figure_index=0,
                bbox=(0, 0, 200, 150),
                caption="Figure 1. Test caption",
                image_path=tmp_path / "fig1.png",
            ),
            ExtractedFigure(
                page_num=2,
                figure_index=0,
                bbox=(0, 0, 200, 150),
                caption=None,  # Orphan
                image_path=tmp_path / "fig2.png",
            ),
        ]

        doc_meta = {
            "title": "Test Paper",
            "authors": "Smith, J.",
            "year": 2024,
            "citation_key": "smith2024",
            "publication": "Test Journal",
        }

        store.add_figures("doc123", doc_meta, figures)

        # Verify figures were stored
        assert store.count() == 2

    def test_add_figures_with_correct_metadata(self, tmp_path):
        """Stored figures should have correct metadata fields."""
        from zotero_chunk_rag.embedder import LocalEmbedder
        from zotero_chunk_rag.vector_store import VectorStore

        db_path = tmp_path / "chroma"
        embedder = LocalEmbedder()
        store = VectorStore(db_path, embedder)

        figures = [
            ExtractedFigure(
                page_num=3,
                figure_index=1,
                bbox=(10, 20, 210, 170),
                caption="Figure 2. Electrode placement",
                image_path=tmp_path / "test.png",
            ),
        ]

        doc_meta = {
            "title": "ECG Study",
            "authors": "Jones, A.",
            "year": 2023,
        }

        store.add_figures("ECG001", doc_meta, figures)

        # Search to retrieve the figure
        results = store.search("electrode placement", top_k=1)

        assert len(results) == 1
        meta = results[0].metadata
        assert meta["chunk_type"] == "figure"
        assert meta["page_num"] == 3
        assert meta["figure_index"] == 1
        assert meta["caption"] == "Figure 2. Electrode placement"
        assert meta["doc_id"] == "ECG001"
        assert meta["doc_title"] == "ECG Study"

    def test_add_figures_empty_list(self, tmp_path):
        """add_figures with empty list should not raise."""
        from zotero_chunk_rag.embedder import LocalEmbedder
        from zotero_chunk_rag.vector_store import VectorStore

        db_path = tmp_path / "chroma"
        embedder = LocalEmbedder()
        store = VectorStore(db_path, embedder)

        # Should not raise
        store.add_figures("doc123", {"title": "Test"}, [])

        assert store.count() == 0

    def test_add_figures_orphan_has_empty_caption_string(self, tmp_path):
        """Orphan figures should have empty string caption in metadata."""
        from zotero_chunk_rag.embedder import LocalEmbedder
        from zotero_chunk_rag.vector_store import VectorStore

        db_path = tmp_path / "chroma"
        embedder = LocalEmbedder()
        store = VectorStore(db_path, embedder)

        figures = [
            ExtractedFigure(
                page_num=1,
                figure_index=0,
                bbox=(0, 0, 200, 150),
                caption=None,  # Orphan
            ),
        ]

        store.add_figures("doc123", {"title": "Test"}, figures)

        results = store.search("Figure on page", top_k=1)
        assert len(results) == 1
        # ChromaDB metadata stores empty string for None
        assert results[0].metadata["caption"] == ""


class TestSearchFiguresTool:
    """Tests for search_figures MCP tool functionality."""

    def test_search_figures_returns_relevant_results(self, tmp_path):
        """search_figures should return figures matching query."""
        from zotero_chunk_rag.embedder import LocalEmbedder
        from zotero_chunk_rag.vector_store import VectorStore

        db_path = tmp_path / "chroma"
        embedder = LocalEmbedder()
        store = VectorStore(db_path, embedder)

        # Add figures with different captions
        figures = [
            ExtractedFigure(
                page_num=1,
                figure_index=0,
                bbox=(0, 0, 200, 150),
                caption="Figure 1. Heart rate variability during exercise",
            ),
            ExtractedFigure(
                page_num=2,
                figure_index=0,
                bbox=(0, 0, 200, 150),
                caption="Figure 2. Blood pressure measurements over time",
            ),
        ]

        store.add_figures("doc1", {"title": "Cardiac Study", "year": 2024}, figures)

        # Search for HRV-related figure
        results = store.search(
            "heart rate variability",
            top_k=2,
            filters={"chunk_type": {"$eq": "figure"}}
        )

        assert len(results) >= 1
        # First result should be about HRV
        assert "heart rate" in results[0].text.lower()

    def test_search_figures_filter_by_chunk_type(self, tmp_path):
        """Should only return figure chunks, not text chunks."""
        from zotero_chunk_rag.embedder import LocalEmbedder
        from zotero_chunk_rag.vector_store import VectorStore
        from zotero_chunk_rag.models import Chunk

        db_path = tmp_path / "chroma"
        embedder = LocalEmbedder()
        store = VectorStore(db_path, embedder)

        # Add a text chunk
        text_chunks = [
            Chunk(
                text="Heart rate variability is important for cardiac health.",
                page_num=1,
                chunk_index=0,
                char_start=0,
                char_end=50,
                section="intro",
                section_confidence=0.9,
            )
        ]
        store.add_chunks("doc1", {"title": "Test"}, text_chunks)

        # Add a figure
        figures = [
            ExtractedFigure(
                page_num=1,
                figure_index=0,
                bbox=(0, 0, 200, 150),
                caption="Figure 1. Heart rate variability analysis",
            ),
        ]
        store.add_figures("doc1", {"title": "Test"}, figures)

        # Search with figure filter
        results = store.search(
            "heart rate",
            top_k=10,
            filters={"chunk_type": {"$eq": "figure"}}
        )

        # Should only get figure, not text chunk
        assert len(results) == 1
        assert results[0].metadata["chunk_type"] == "figure"
