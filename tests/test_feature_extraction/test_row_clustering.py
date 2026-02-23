"""Tests for row clustering utility."""
from __future__ import annotations

from zotero_chunk_rag.feature_extraction.methods._row_clustering import (
    adaptive_row_tolerance,
    cluster_words_into_rows,
)


# Word tuple format: (x0, y0, x1, y1, "text", block_no, line_no, word_no)
def _word(x0: float, y0: float, x1: float, y1: float, text: str = "w") -> tuple:
    return (x0, y0, x1, y1, text, 0, 0, 0)


class TestAdaptiveTolerance:
    def test_clear_row_gaps(self) -> None:
        """Words with y-positions at 100, 100.5, 120, 120.3, 140 (3 clear rows).
        Tolerance should be derived from the gap distribution, not a fixed value.
        """
        words = [
            _word(10, 100, 50, 110),
            _word(60, 100.5, 100, 110.5),
            _word(10, 120, 50, 130),
            _word(60, 120.3, 100, 130.3),
            _word(10, 140, 50, 150),
        ]
        tol = adaptive_row_tolerance(words)
        # The intra-row gaps (~0.3-0.5pt) are much smaller than inter-row gaps (~20pt).
        # The ratio break should find the small gap as the tolerance.
        # Tolerance should be small (intra-row) not large (inter-row).
        assert tol > 0
        assert tol < 10  # must be derived from small intra-row gaps, not inter-row

    def test_single_row_fallback(self) -> None:
        """All words at same y. Returns median_word_height * 0.3 fallback."""
        words = [
            _word(10, 100, 50, 112),
            _word(60, 100, 100, 112),
            _word(110, 100, 150, 112),
        ]
        tol = adaptive_row_tolerance(words)
        # All same y, fewer than 3 unique y-midpoints, fallback to median_h * 0.3
        # median_h = 12, fallback = 12 * 0.3 = 3.6
        assert tol == 12.0 * 0.3

    def test_empty_words(self) -> None:
        """Empty list. Returns a positive float (no crash)."""
        tol = adaptive_row_tolerance([])
        assert isinstance(tol, float)
        assert tol > 0


class TestCluster:
    def test_three_rows(self) -> None:
        """Words at y=100, 120, 140. Assert 3 rows returned with correct words."""
        words = [
            _word(10, 100, 50, 110, "a"),
            _word(60, 100, 100, 110, "b"),
            _word(10, 120, 50, 130, "c"),
            _word(10, 140, 50, 150, "d"),
        ]
        rows = cluster_words_into_rows(words)
        assert len(rows) == 3
        # Row 0: y=100 words
        assert len(rows[0]) == 2
        texts_row0 = {w[4] for w in rows[0]}
        assert texts_row0 == {"a", "b"}
        # Row 1: y=120
        assert len(rows[1]) == 1
        assert rows[1][0][4] == "c"
        # Row 2: y=140
        assert len(rows[2]) == 1
        assert rows[2][0][4] == "d"

    def test_words_sorted_by_x(self) -> None:
        """Within each row, words are sorted left-to-right by x0."""
        words = [
            _word(100, 50, 150, 60, "right"),
            _word(10, 50, 50, 60, "left"),
            _word(55, 50, 95, 60, "middle"),
        ]
        rows = cluster_words_into_rows(words)
        assert len(rows) == 1
        assert rows[0][0][4] == "left"
        assert rows[0][1][4] == "middle"
        assert rows[0][2][4] == "right"

    def test_rows_sorted_by_y(self) -> None:
        """Rows are sorted top-to-bottom."""
        words = [
            _word(10, 200, 50, 210, "bottom"),
            _word(10, 50, 50, 60, "top"),
            _word(10, 120, 50, 130, "middle"),
        ]
        rows = cluster_words_into_rows(words)
        assert len(rows) == 3
        assert rows[0][0][4] == "top"
        assert rows[1][0][4] == "middle"
        assert rows[2][0][4] == "bottom"

    def test_custom_tolerance(self) -> None:
        """Pass explicit tolerance=5.0, words within 5pt cluster together."""
        words = [
            _word(10, 100, 50, 110, "a"),
            _word(60, 103, 100, 113, "b"),  # y_mid=108, within 5pt of a's y_mid=105
            _word(10, 120, 50, 130, "c"),   # y_mid=125, far from 108
        ]
        rows = cluster_words_into_rows(words, tolerance=5.0)
        assert len(rows) == 2
        # Row 0: a and b clustered together
        texts_row0 = {w[4] for w in rows[0]}
        assert texts_row0 == {"a", "b"}
        # Row 1: c alone
        assert rows[1][0][4] == "c"

    def test_empty_words(self) -> None:
        """Empty list returns empty list."""
        rows = cluster_words_into_rows([])
        assert rows == []
