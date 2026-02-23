"""Tests for hotspot structure methods (single-point and gap-span).

Tests cover gap candidate collection, clustering, single-point detection,
gap-span detection, and protocol conformance.
"""

from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock

import pytest

from zotero_chunk_rag.feature_extraction.methods.hotspot import (
    GapSpanHotspot,
    SinglePointHotspot,
    _cluster_candidates,
    _collect_gap_candidates,
    _compute_gap_spans,
    _credit_span_support,
)
from zotero_chunk_rag.feature_extraction.protocols import StructureMethod


def _make_word(x0: float, y0: float, x1: float, y1: float, text: str = "w") -> tuple:
    """Create a word tuple in pymupdf format: (x0, y0, x1, y1, text, block, line, word)."""
    return (x0, y0, x1, y1, text, 0, 0, 0)


def _make_ctx(
    data_word_rows: list[list[tuple]],
    median_word_height: float = 10.0,
) -> MagicMock:
    """Build a mock TableContext with the given data_word_rows."""
    ctx = MagicMock()
    type(ctx).data_word_rows = PropertyMock(return_value=data_word_rows)
    type(ctx).median_word_height = PropertyMock(return_value=median_word_height)
    # words property for internal helpers
    all_words = [w for row in data_word_rows for w in row]
    type(ctx).words = PropertyMock(return_value=all_words)
    return ctx


# ---------------------------------------------------------------------------
# TestGapCandidates
# ---------------------------------------------------------------------------

class TestGapCandidates:
    def test_filters_micro_gaps(self) -> None:
        """Words with 0.001pt gap and 20pt gap. Only the 20pt gap produces a candidate."""
        row = [
            _make_word(10, 0, 30, 10),   # word A
            _make_word(30.001, 0, 50, 10),  # micro-gap: 0.001pt
            _make_word(70, 0, 90, 10),    # real gap: 20pt from word B
        ]
        # min_gap = 10 * 0.25 = 2.5
        candidates = _collect_gap_candidates([row], min_gap=2.5)
        assert len(candidates) == 1
        # The surviving gap is between word at x1=50 and word at x0=70
        assert candidates[0][0] == pytest.approx(60.0)

    def test_candidate_position(self) -> None:
        """Two words at x=(50,80) and x=(120,150). Gap midpoint at 100."""
        row = [
            _make_word(50, 0, 80, 10),
            _make_word(120, 0, 150, 10),
        ]
        candidates = _collect_gap_candidates([row], min_gap=1.0)
        assert len(candidates) == 1
        assert candidates[0][0] == pytest.approx(100.0)
        assert candidates[0][1] == 0  # row index


# ---------------------------------------------------------------------------
# TestClustering
# ---------------------------------------------------------------------------

class TestClustering:
    def test_nearby_candidates_cluster(self) -> None:
        """Candidates at x=100.0, 100.5, 101.0 with tolerance=2.0. One cluster."""
        candidates = [(100.0, 0), (100.5, 1), (101.0, 2)]
        clusters = _cluster_candidates(candidates, tolerance=2.0)
        assert len(clusters) == 1
        assert clusters[0]["position"] == pytest.approx(100.5)

    def test_distant_candidates_separate(self) -> None:
        """Candidates at x=100 and x=250 with tolerance=2.0. Two clusters."""
        candidates = [(100.0, 0), (250.0, 1)]
        clusters = _cluster_candidates(candidates, tolerance=2.0)
        assert len(clusters) == 2


# ---------------------------------------------------------------------------
# TestSinglePoint
# ---------------------------------------------------------------------------

class TestSinglePoint:
    def test_uniform_table(self) -> None:
        """5 rows, 4 columns, consistent gaps. 3 column boundaries detected."""
        rows = []
        for y in range(5):
            y0 = y * 15.0
            y1 = y0 + 10.0
            row = [
                _make_word(10, y0, 40, y1),
                _make_word(60, y0, 90, y1),
                _make_word(110, y0, 140, y1),
                _make_word(160, y0, 190, y1),
            ]
            rows.append(row)

        ctx = _make_ctx(rows, median_word_height=10.0)
        method = SinglePointHotspot()
        result = method.detect(ctx)

        assert result is not None
        assert len(result.col_boundaries) == 3
        for bp in result.col_boundaries:
            assert bp.confidence > 0.5

    def test_continuation_rows(self) -> None:
        """3 full rows + 2 continuation rows. Boundaries from full rows only."""
        rows = []
        # 3 full rows with 3 gaps each
        for y in range(3):
            y0 = y * 15.0
            y1 = y0 + 10.0
            row = [
                _make_word(10, y0, 40, y1),
                _make_word(60, y0, 90, y1),
                _make_word(110, y0, 140, y1),
                _make_word(160, y0, 190, y1),
            ]
            rows.append(row)

        # 2 continuation rows with content in only 1 column
        for y in range(3, 5):
            y0 = y * 15.0
            y1 = y0 + 10.0
            row = [_make_word(10, y0, 40, y1)]
            rows.append(row)

        ctx = _make_ctx(rows, median_word_height=10.0)
        method = SinglePointHotspot()
        result = method.detect(ctx)

        assert result is not None
        assert len(result.col_boundaries) == 3

    def test_returns_none_no_words(self) -> None:
        """Empty data_word_rows. Returns None."""
        ctx = _make_ctx([], median_word_height=10.0)
        method = SinglePointHotspot()
        result = method.detect(ctx)
        assert result is None

    def test_single_column(self) -> None:
        """All words in one column, no gaps. Empty col_boundaries."""
        rows = []
        for y in range(5):
            y0 = y * 15.0
            y1 = y0 + 10.0
            row = [_make_word(10, y0, 40, y1)]
            rows.append(row)

        ctx = _make_ctx(rows, median_word_height=10.0)
        method = SinglePointHotspot()
        result = method.detect(ctx)

        assert result is not None
        assert len(result.col_boundaries) == 0

    def test_pruning(self) -> None:
        """Low-support boundary (1 row) among high-support (5 rows). Pruned."""
        rows = []
        # 5 rows with consistent gaps at x=50 and x=100
        for y in range(5):
            y0 = y * 15.0
            y1 = y0 + 10.0
            row = [
                _make_word(10, y0, 40, y1),
                _make_word(60, y0, 90, y1),
                _make_word(110, y0, 140, y1),
            ]
            rows.append(row)

        # 1 row with an additional gap at x=200
        rows[0] = rows[0] + [_make_word(260, 0, 290, 10)]

        ctx = _make_ctx(rows, median_word_height=10.0)
        method = SinglePointHotspot()
        result = method.detect(ctx)

        assert result is not None
        # The x=200 boundary has support=1, below the 2-row floor
        # Only the 2 high-support boundaries should survive
        assert len(result.col_boundaries) == 2

    def test_protocol_conformance(self) -> None:
        assert isinstance(SinglePointHotspot(), StructureMethod)


# ---------------------------------------------------------------------------
# TestGapSpan
# ---------------------------------------------------------------------------

class TestGapSpan:
    def test_span_support(self) -> None:
        """3 full rows + 2 rows with cols 0 and 3 only.
        Wide gap spans boundaries 1 and 2."""
        rows = []
        # 3 full rows: 4 columns, gaps at x~50, x~100, x~150
        for y in range(3):
            y0 = y * 15.0
            y1 = y0 + 10.0
            row = [
                _make_word(10, y0, 40, y1),
                _make_word(60, y0, 90, y1),
                _make_word(110, y0, 140, y1),
                _make_word(160, y0, 190, y1),
            ]
            rows.append(row)

        # 2 rows with content in cols 0 and 3 only (wide gap spanning boundaries 1,2)
        for y in range(3, 5):
            y0 = y * 15.0
            y1 = y0 + 10.0
            row = [
                _make_word(10, y0, 40, y1),
                _make_word(160, y0, 190, y1),
            ]
            rows.append(row)

        ctx = _make_ctx(rows, median_word_height=10.0)
        method = GapSpanHotspot()
        result = method.detect(ctx)

        assert result is not None
        # All 3 boundaries should receive support from the wide-gap rows
        assert len(result.col_boundaries) == 3
        for bp in result.col_boundaries:
            assert bp.confidence > 0.5

    def test_higher_support_than_single_point(self) -> None:
        """Same input as test_span_support. Gap-span >= single-point support."""
        rows = []
        for y in range(3):
            y0 = y * 15.0
            y1 = y0 + 10.0
            row = [
                _make_word(10, y0, 40, y1),
                _make_word(60, y0, 90, y1),
                _make_word(110, y0, 140, y1),
                _make_word(160, y0, 190, y1),
            ]
            rows.append(row)

        for y in range(3, 5):
            y0 = y * 15.0
            y1 = y0 + 10.0
            row = [
                _make_word(10, y0, 40, y1),
                _make_word(160, y0, 190, y1),
            ]
            rows.append(row)

        ctx = _make_ctx(rows, median_word_height=10.0)

        sp_result = SinglePointHotspot().detect(ctx)
        gs_result = GapSpanHotspot().detect(ctx)

        assert sp_result is not None
        assert gs_result is not None

        # Map boundaries by approximate position for comparison
        sp_confs = sorted(
            [(bp.min_pos, bp.confidence) for bp in sp_result.col_boundaries],
            key=lambda t: t[0],
        )
        gs_confs = sorted(
            [(bp.min_pos, bp.confidence) for bp in gs_result.col_boundaries],
            key=lambda t: t[0],
        )

        assert len(gs_confs) >= len(sp_confs)
        for i in range(min(len(sp_confs), len(gs_confs))):
            assert gs_confs[i][1] >= sp_confs[i][1] - 0.01  # small tolerance

    def test_protocol_conformance(self) -> None:
        assert isinstance(GapSpanHotspot(), StructureMethod)
