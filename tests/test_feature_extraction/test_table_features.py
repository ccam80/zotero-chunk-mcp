"""Tests for table feature detection predicates."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, PropertyMock

from zotero_chunk_rag.feature_extraction.models import (
    BoundaryHypothesis,
    BoundaryPoint,
    CellGrid,
    PipelineConfig,
    TableContext,
)
from zotero_chunk_rag.feature_extraction.pipeline import DEFAULT_CONFIG, Pipeline
from zotero_chunk_rag.feature_extraction.table_features import (
    has_complex_headers,
    has_ruled_lines,
    has_sparse_content,
    is_dense_numeric,
    is_wide_table,
)


def _make_ctx(
    *,
    words=None,
    drawings=None,
    dict_blocks=None,
    page_width=600.0,
    page_height=800.0,
    bbox=(50.0, 50.0, 550.0, 750.0),
    all_page_words=None,
) -> TableContext:
    """Build a mocked TableContext with specified data."""
    mock_page = MagicMock()

    # Default return values
    if words is None:
        words = []
    if drawings is None:
        drawings = []
    if dict_blocks is None:
        dict_blocks = []
    if all_page_words is None:
        all_page_words = words

    # Configure page.get_text to return different things based on args
    def _get_text(mode, **kwargs):
        if mode == "words" and "clip" in kwargs:
            return words
        if mode == "words":
            return all_page_words
        if mode == "dict" and "clip" in kwargs:
            return {"blocks": dict_blocks}
        return []

    mock_page.get_text = _get_text
    mock_page.get_drawings.return_value = drawings
    mock_page.rect = MagicMock()
    mock_page.rect.height = page_height
    mock_page.rect.width = page_width

    ctx = TableContext(
        page=mock_page,
        page_num=1,
        bbox=bbox,
        pdf_path=Path("test.pdf"),
    )
    return ctx


class TestHasRuledLines:
    """Tests for has_ruled_lines() predicate."""

    def test_with_lines(self):
        """Table with drawings that have width > 0 should detect ruled lines."""
        drawings = [
            {"rect": (50, 100, 550, 100), "width": 1.0, "items": []},
            {"rect": (50, 200, 550, 200), "width": 0.5, "items": []},
        ]
        ctx = _make_ctx(drawings=drawings)
        assert has_ruled_lines(ctx) is True

    def test_without_lines(self):
        """Table with no drawings should not detect ruled lines."""
        ctx = _make_ctx(drawings=[])
        assert has_ruled_lines(ctx) is False


class TestIsDenseNumeric:
    """Tests for is_dense_numeric() predicate."""

    def test_numeric_table(self):
        """Table where >50% of words are numbers."""
        # Word tuple: (x0, y0, x1, y1, text, block_no, line_no, word_no)
        words = [
            (100, 100, 130, 110, "12.5", 0, 0, 0),
            (140, 100, 170, 110, "3.14", 0, 0, 1),
            (180, 100, 210, 110, "0.99", 0, 0, 2),
            (220, 100, 260, 110, "-7.2", 0, 0, 3),
            (270, 100, 310, 110, "text", 0, 0, 4),
        ]
        ctx = _make_ctx(words=words)
        assert is_dense_numeric(ctx) is True

    def test_text_table(self):
        """Table where <50% of words are numbers."""
        words = [
            (100, 100, 180, 110, "method", 0, 0, 0),
            (190, 100, 260, 110, "result", 0, 0, 1),
            (270, 100, 340, 110, "analysis", 0, 0, 2),
            (350, 100, 400, 110, "12.5", 0, 0, 3),
        ]
        ctx = _make_ctx(words=words)
        assert is_dense_numeric(ctx) is False


class TestHasSparseContent:
    """Tests for has_sparse_content() predicate."""

    def test_sparse_table(self):
        """Large bbox with few words relative to page density."""
        # A few words in a big table bbox
        table_words = [
            (100, 100, 130, 110, "hello", 0, 0, 0),
            (200, 200, 230, 210, "world", 0, 0, 1),
        ]
        # Many words on the full page
        page_words = [
            (50 + i * 10, 50, 60 + i * 10, 60, f"w{i}", 0, 0, i)
            for i in range(100)
        ]
        ctx = _make_ctx(
            words=table_words,
            all_page_words=page_words,
            bbox=(50.0, 50.0, 550.0, 750.0),
        )
        assert has_sparse_content(ctx) is True

    def test_dense_table(self):
        """Table with word density comparable to or higher than page."""
        # Many words in the table bbox
        table_words = [
            (50 + i * 5, 50 + j * 10, 55 + i * 5, 60 + j * 10, f"w{i}{j}", 0, 0, 0)
            for i in range(20)
            for j in range(10)
        ]
        ctx = _make_ctx(
            words=table_words,
            all_page_words=table_words,
            bbox=(50.0, 50.0, 200.0, 200.0),
        )
        assert has_sparse_content(ctx) is False


class TestIsWideTable:
    """Tests for is_wide_table() predicate."""

    def test_wide(self):
        """Table spanning 90% of page width."""
        ctx = _make_ctx(
            bbox=(30.0, 100.0, 570.0, 700.0),
            page_width=600.0,
        )
        assert is_wide_table(ctx) is True

    def test_narrow(self):
        """Table spanning 40% of page width."""
        ctx = _make_ctx(
            bbox=(30.0, 100.0, 270.0, 700.0),
            page_width=600.0,
        )
        assert is_wide_table(ctx) is False


class TestHasComplexHeaders:
    """Tests for has_complex_headers() predicate."""

    def test_bold_headers(self):
        """Headers are bold, data is not."""
        dict_blocks = [
            {
                "type": 0,
                "lines": [
                    {
                        "spans": [
                            {
                                "bbox": (50, 50, 200, 60),
                                "size": 10.0,
                                "font": "Helvetica-Bold",
                            },
                        ],
                    },
                    {
                        "spans": [
                            {
                                "bbox": (50, 65, 200, 75),
                                "size": 10.0,
                                "font": "Helvetica-Bold",
                            },
                        ],
                    },
                ],
            },
            {
                "type": 0,
                "lines": [
                    {"spans": [{"bbox": (50, 100 + i * 15, 200, 110 + i * 15), "size": 10.0, "font": "Helvetica"}]}
                    for i in range(10)
                ],
            },
        ]
        ctx = _make_ctx(dict_blocks=dict_blocks)
        assert has_complex_headers(ctx) is True

    def test_no_font_difference(self):
        """All rows have the same font properties."""
        dict_blocks = [
            {
                "type": 0,
                "lines": [
                    {"spans": [{"bbox": (50, 50 + i * 15, 200, 60 + i * 15), "size": 10.0, "font": "Helvetica"}]}
                    for i in range(10)
                ],
            },
        ]
        ctx = _make_ctx(dict_blocks=dict_blocks)
        assert has_complex_headers(ctx) is False


class TestActivation:
    """Tests for activation rules in DEFAULT_CONFIG."""

    def test_camelot_skipped_without_lines(self):
        """Camelot methods should be skipped when table has no ruled lines."""
        ctx = _make_ctx(drawings=[])

        # Check activation rules directly
        camelot_lattice_rule = DEFAULT_CONFIG.activation_rules.get("camelot_lattice")
        camelot_hybrid_rule = DEFAULT_CONFIG.activation_rules.get("camelot_hybrid")

        assert camelot_lattice_rule is not None
        assert camelot_hybrid_rule is not None
        assert camelot_lattice_rule(ctx) is False
        assert camelot_hybrid_rule(ctx) is False

    def test_cliff_skipped_with_lines(self):
        """Cliff methods should be skipped when table has ruled lines."""
        drawings = [
            {"rect": (50, 100, 550, 100), "width": 1.0, "items": []},
        ]
        ctx = _make_ctx(drawings=drawings)

        global_cliff_rule = DEFAULT_CONFIG.activation_rules.get("global_cliff")
        per_row_cliff_rule = DEFAULT_CONFIG.activation_rules.get("per_row_cliff")

        assert global_cliff_rule is not None
        assert per_row_cliff_rule is not None
        assert global_cliff_rule(ctx) is False
        assert per_row_cliff_rule(ctx) is False

    def test_camelot_active_with_lines(self):
        """Camelot methods should be active when table has ruled lines."""
        drawings = [
            {"rect": (50, 100, 550, 100), "width": 1.0, "items": []},
        ]
        ctx = _make_ctx(drawings=drawings)

        camelot_lattice_rule = DEFAULT_CONFIG.activation_rules.get("camelot_lattice")
        assert camelot_lattice_rule(ctx) is True

    def test_cliff_active_without_lines(self):
        """Cliff methods should be active when table has no ruled lines."""
        ctx = _make_ctx(drawings=[])

        global_cliff_rule = DEFAULT_CONFIG.activation_rules.get("global_cliff")
        assert global_cliff_rule(ctx) is True
