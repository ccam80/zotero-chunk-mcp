"""Tests for header anchor structure method.

Tests cover header row detection, multi-row header, high confidence,
edge cases, and protocol conformance.
"""

from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock

import pytest

from zotero_chunk_rag.feature_extraction.methods.header_anchor import HeaderAnchor
from zotero_chunk_rag.feature_extraction.protocols import StructureMethod


def _make_word(x0: float, y0: float, x1: float, y1: float, text: str = "w") -> tuple:
    """Create a word tuple in pymupdf format."""
    return (x0, y0, x1, y1, text, 0, 0, 0)


def _make_ctx(
    data_word_rows: list[list[tuple]],
    median_word_height: float = 10.0,
) -> MagicMock:
    """Build a mock TableContext."""
    ctx = MagicMock()
    type(ctx).data_word_rows = PropertyMock(return_value=data_word_rows)
    type(ctx).median_word_height = PropertyMock(return_value=median_word_height)
    all_words = [w for row in data_word_rows for w in row]
    type(ctx).words = PropertyMock(return_value=all_words)
    return ctx


class TestHeaderAnchor:
    def test_finds_header_row(self) -> None:
        """First row has 5 gaps, data rows have 3 gaps. Assert 5 boundaries."""
        # Header row: 6 words = 5 gaps
        header = [
            _make_word(10, 0, 30, 10),
            _make_word(50, 0, 70, 10),
            _make_word(90, 0, 110, 10),
            _make_word(130, 0, 150, 10),
            _make_word(170, 0, 190, 10),
            _make_word(210, 0, 230, 10),
        ]
        # Data rows: 4 words = 3 gaps
        data_rows = []
        for y in range(1, 4):
            y0 = y * 15.0
            y1 = y0 + 10.0
            data_rows.append([
                _make_word(10, y0, 30, y1),
                _make_word(50, y0, 70, y1),
                _make_word(90, y0, 110, y1),
                _make_word(130, y0, 150, y1),
            ])

        rows = [header] + data_rows
        ctx = _make_ctx(rows, median_word_height=10.0)
        method = HeaderAnchor()
        result = method.detect(ctx)

        assert result is not None
        assert len(result.col_boundaries) == 5

    def test_high_confidence(self) -> None:
        """All boundary confidences >= 0.9."""
        header = [
            _make_word(10, 0, 30, 10),
            _make_word(50, 0, 70, 10),
            _make_word(90, 0, 110, 10),
        ]
        data = [
            [
                _make_word(10, 15, 30, 25),
                _make_word(50, 15, 70, 25),
            ],
        ]
        rows = [header] + data
        ctx = _make_ctx(rows, median_word_height=10.0)
        method = HeaderAnchor()
        result = method.detect(ctx)

        assert result is not None
        for bp in result.col_boundaries:
            assert bp.confidence >= 0.9

    def test_multi_row_header(self) -> None:
        """First two rows matching. Boundaries confirmed by both get 0.95."""
        row0 = [
            _make_word(10, 0, 30, 10),
            _make_word(50, 0, 70, 10),
            _make_word(90, 0, 110, 10),
            _make_word(130, 0, 150, 10),
        ]
        row1 = [
            _make_word(10, 15, 30, 25),
            _make_word(50, 15, 70, 25),
            _make_word(90, 15, 110, 25),
            _make_word(130, 15, 150, 25),
        ]
        data = [
            [
                _make_word(10, 30, 30, 40),
                _make_word(50, 30, 70, 40),
            ],
        ]
        rows = [row0, row1] + data
        ctx = _make_ctx(rows, median_word_height=10.0)
        method = HeaderAnchor()
        result = method.detect(ctx)

        assert result is not None
        assert result.metadata["multi_row_header"] is True
        for bp in result.col_boundaries:
            assert bp.confidence == pytest.approx(0.95)

    def test_no_header_detected(self) -> None:
        """All rows 0-1 gaps. Returns None."""
        rows = [
            [_make_word(10, 0, 40, 10)],
            [_make_word(10, 15, 40, 25)],
            [_make_word(10, 30, 40, 40), _make_word(50, 30, 80, 40)],
        ]
        ctx = _make_ctx(rows, median_word_height=10.0)
        method = HeaderAnchor()
        result = method.detect(ctx)
        assert result is None

    def test_takes_topmost_on_tie(self) -> None:
        """Rows 0 and 3 both have 4 gaps. Assert header is row 0."""
        row_template = [
            _make_word(10, 0, 30, 10),
            _make_word(50, 0, 70, 10),
            _make_word(90, 0, 110, 10),
            _make_word(130, 0, 150, 10),
            _make_word(170, 0, 190, 10),
        ]
        # Row 0: 4 gaps
        row0 = [_make_word(x0, 0, x1, 10) for x0, _, x1, *_ in row_template]
        # Rows 1-2: fewer gaps
        row1 = [_make_word(10, 15, 30, 25), _make_word(50, 15, 70, 25)]
        row2 = [_make_word(10, 30, 30, 40), _make_word(50, 30, 70, 40)]
        # Row 3: also 4 gaps
        row3 = [_make_word(x0, 45, x1, 55) for x0, _, x1, *_ in row_template]

        rows = [row0, row1, row2, row3]
        ctx = _make_ctx(rows, median_word_height=10.0)
        method = HeaderAnchor()
        result = method.detect(ctx)

        assert result is not None
        assert result.metadata["header_row_index"] == 0

    def test_protocol_conformance(self) -> None:
        assert isinstance(HeaderAnchor(), StructureMethod)
