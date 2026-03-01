"""Tests for zotero_chunk_rag.models dataclasses."""
import pytest
from zotero_chunk_rag.models import (
    DocumentExtraction,
    PageExtraction,
    ExtractedTable,
    ExtractedFigure,
    SectionSpan,
)


class TestDocumentExtraction:
    """Tests for DocumentExtraction dataclass."""

    def test_vision_details_default_none(self):
        """Construct DocumentExtraction without vision_details. Assert it's None."""
        extraction = DocumentExtraction(
            pages=[],
            full_markdown="",
            sections=[],
            tables=[],
            figures=[],
            stats={},
            quality_grade="A",
        )
        assert extraction.vision_details is None

    def test_vision_details_accepts_list(self):
        """Construct with vision_details list. Assert len == 1."""
        vision_details = [{"text_layer_caption": "Table 1"}]
        extraction = DocumentExtraction(
            pages=[],
            full_markdown="",
            sections=[],
            tables=[],
            figures=[],
            stats={},
            quality_grade="A",
            vision_details=vision_details,
        )
        assert extraction.vision_details == vision_details
        assert len(extraction.vision_details) == 1
        assert extraction.vision_details[0]["text_layer_caption"] == "Table 1"
