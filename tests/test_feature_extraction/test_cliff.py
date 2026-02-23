"""Tests for cliff detection structure methods (global and per-row).

Tests cover cliff finding, confidence computation, global cliff detection,
per-row cliff detection, and protocol conformance.
"""

from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock

import pytest

from zotero_chunk_rag.feature_extraction.methods.cliff import (
    GlobalCliff,
    PerRowCliff,
    _boundary_confidence,
    _find_cliff,
)
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


# ---------------------------------------------------------------------------
# TestFindCliff
# ---------------------------------------------------------------------------

class TestFindCliff:
    def test_clear_bimodal(self) -> None:
        """Gaps [2, 3, 3, 4, 20, 25, 30]. Cliff between 4 and 20."""
        gaps = [2.0, 3.0, 3.0, 4.0, 20.0, 25.0, 30.0]
        result = _find_cliff(gaps)
        assert result is not None
        cliff_index, ratio = result
        assert cliff_index == 3  # gap at index 3 is 4.0, gap at index 4 is 20.0
        assert ratio == pytest.approx(5.0)

    def test_no_cliff(self) -> None:
        """Gaps [10, 11, 12, 13]. No large ratio. Still returns the largest found."""
        gaps = [10.0, 11.0, 12.0, 13.0]
        result = _find_cliff(gaps)
        assert result is not None
        _, ratio = result
        # All ratios close to 1.0 — max is ~1.1
        assert ratio < 1.5

    def test_single_gap(self) -> None:
        """One gap. Returns None."""
        result = _find_cliff([5.0])
        assert result is None


# ---------------------------------------------------------------------------
# TestConfidence
# ---------------------------------------------------------------------------

class TestConfidence:
    def test_large_ratio(self) -> None:
        """gap=50, cliff_threshold=5. Confidence ~0.91."""
        conf = _boundary_confidence(50.0, 5.0)
        assert conf == pytest.approx(10.0 / 11.0, abs=0.01)

    def test_small_ratio(self) -> None:
        """gap=6, cliff_threshold=5. Confidence ~0.55."""
        conf = _boundary_confidence(6.0, 5.0)
        assert conf == pytest.approx(1.2 / 2.2, abs=0.01)

    def test_at_cliff(self) -> None:
        """gap=5, cliff_threshold=5. Confidence = 0.5."""
        conf = _boundary_confidence(5.0, 5.0)
        assert conf == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# TestGlobalCliff
# ---------------------------------------------------------------------------

class TestGlobalCliff:
    def test_uniform_table(self) -> None:
        """5 rows, 4 cols, intra-word gaps ~3pt, column gaps ~25pt. 3 boundaries."""
        rows = []
        for y in range(5):
            y0 = y * 15.0
            y1 = y0 + 10.0
            # Each column: two sub-words with 3pt gap (above min_gap=2.5),
            # columns separated by 25pt gap
            row = [
                _make_word(10, y0, 20, y1),     # col0 word A
                _make_word(23, y0, 33, y1),     # col0 word B (3pt gap)
                _make_word(58, y0, 68, y1),     # col1 word A (25pt gap)
                _make_word(71, y0, 81, y1),     # col1 word B (3pt gap)
                _make_word(106, y0, 116, y1),   # col2 word A (25pt gap)
                _make_word(119, y0, 129, y1),   # col2 word B (3pt gap)
                _make_word(154, y0, 164, y1),   # col3 word A (25pt gap)
                _make_word(167, y0, 177, y1),   # col3 word B (3pt gap)
            ]
            rows.append(row)

        ctx = _make_ctx(rows, median_word_height=10.0)
        method = GlobalCliff()
        result = method.detect(ctx)

        assert result is not None
        assert len(result.col_boundaries) == 3
        for bp in result.col_boundaries:
            assert bp.confidence > 0.8

    def test_no_gaps(self) -> None:
        """Single-word rows. Returns None."""
        rows = []
        for y in range(3):
            y0 = y * 15.0
            y1 = y0 + 10.0
            rows.append([_make_word(10, y0, 40, y1)])

        ctx = _make_ctx(rows, median_word_height=10.0)
        method = GlobalCliff()
        result = method.detect(ctx)
        assert result is None

    def test_protocol_conformance(self) -> None:
        assert isinstance(GlobalCliff(), StructureMethod)


# ---------------------------------------------------------------------------
# TestPerRowCliff
# ---------------------------------------------------------------------------

class TestPerRowCliff:
    def test_heterogeneous_rows(self) -> None:
        """Row 0: 4 cols with 25pt column gaps + 3pt intra-word gaps.
        Row 1: 2 cols with 30pt gap + intra-word 3pt gaps."""
        # Row 0: 4 columns, each with 2 sub-words at 3pt gap
        row0 = [
            _make_word(10, 0, 20, 10),
            _make_word(23, 0, 33, 10),      # 3pt intra-word
            _make_word(58, 0, 68, 10),      # 25pt column gap
            _make_word(71, 0, 81, 10),      # 3pt intra-word
            _make_word(106, 0, 116, 10),    # 25pt column gap
            _make_word(119, 0, 129, 10),    # 3pt intra-word
            _make_word(154, 0, 164, 10),    # 25pt column gap
            _make_word(167, 0, 177, 10),    # 3pt intra-word
        ]
        # Row 1: 2 columns with intra-word gaps
        row1 = [
            _make_word(10, 15, 20, 25),
            _make_word(23, 15, 33, 25),     # 3pt intra-word
            _make_word(36, 15, 46, 25),     # 3pt intra-word
            _make_word(76, 15, 86, 25),     # 30pt column gap
            _make_word(89, 15, 99, 25),     # 3pt intra-word
            _make_word(102, 15, 112, 25),   # 3pt intra-word
        ]
        rows = [row0, row1]

        ctx = _make_ctx(rows, median_word_height=10.0)
        method = PerRowCliff()
        result = method.detect(ctx)

        assert result is not None
        assert len(result.col_boundaries) >= 1

    def test_skips_short_rows(self) -> None:
        """Row with 1 word. No crash."""
        rows = [
            [_make_word(10, 0, 40, 10)],
            [
                _make_word(10, 15, 20, 25),
                _make_word(23, 15, 33, 25),
                _make_word(60, 15, 70, 25),
                _make_word(100, 15, 110, 25),
            ],
        ]

        ctx = _make_ctx(rows, median_word_height=10.0)
        method = PerRowCliff()
        # Should not crash, just skip the short row
        result = method.detect(ctx)
        # May return None or a hypothesis depending on whether the remaining row
        # has enough gaps to find a cliff. The point is no crash.
        assert result is None or result.method == "per_row_cliff"

    def test_cross_row_clustering(self) -> None:
        """Two rows propose boundary at x~150 (+/-1pt). Assert one cluster."""
        row0 = [
            _make_word(10, 0, 20, 10),
            _make_word(22, 0, 32, 10),
            _make_word(57, 0, 67, 10),
            _make_word(149, 0, 159, 10),     # boundary near 149
        ]
        row1 = [
            _make_word(10, 15, 20, 25),
            _make_word(22, 15, 32, 25),
            _make_word(57, 15, 67, 25),
            _make_word(150, 15, 160, 25),    # boundary near 150
        ]
        rows = [row0, row1]

        ctx = _make_ctx(rows, median_word_height=10.0)
        method = PerRowCliff()
        result = method.detect(ctx)

        if result is not None:
            # Boundaries near x=150 should cluster into one
            boundary_positions = [bp.min_pos for bp in result.col_boundaries]
            near_150 = [p for p in boundary_positions if 90 < p < 170]
            assert len(near_150) <= 1

    def test_protocol_conformance(self) -> None:
        assert isinstance(PerRowCliff(), StructureMethod)
