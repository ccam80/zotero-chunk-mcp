"""Tests for the boundary combination engine in zotero_chunk_rag.feature_extraction.combination."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from zotero_chunk_rag.feature_extraction.combination import (
    _compute_spatial_precision,
    _expand_point_estimate,
    _merge_overlapping,
    _scale_point,
    combine_hypotheses,
)
from zotero_chunk_rag.feature_extraction.models import (
    AxisTrace,
    BoundaryHypothesis,
    BoundaryPoint,
    ClusterRecord,
    CombinationTrace,
    TableContext,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ctx(
    ruled_line_thickness: float | None = None,
    word_gap: float = 5.0,
) -> TableContext:
    """Create a TableContext with controlled properties via mock."""
    page = MagicMock()

    def get_text_side_effect(fmt: str, **kwargs):  # noqa: ANN001
        if fmt == "words":
            return []
        if fmt == "dict":
            return {"blocks": []}
        return ""

    page.get_text = MagicMock(side_effect=get_text_side_effect)
    page.get_drawings = MagicMock(return_value=[])
    rect = MagicMock()
    rect.height = 842.0
    rect.width = 595.0
    page.rect = rect

    ctx = TableContext(
        page=page,
        page_num=0,
        bbox=(0.0, 0.0, 595.0, 842.0),
        pdf_path=Path("/tmp/test.pdf"),
    )

    # Override cached_property values directly on the instance
    # (cached_property stores on instance __dict__, so we can set directly)
    ctx.__dict__["median_ruled_line_thickness"] = ruled_line_thickness
    ctx.__dict__["median_word_gap"] = word_gap
    ctx.__dict__["median_word_height"] = 10.0

    return ctx


def _bp(min_pos: float, max_pos: float, confidence: float = 0.8, provenance: str = "method_a") -> BoundaryPoint:
    """Shorthand BoundaryPoint constructor."""
    return BoundaryPoint(min_pos=min_pos, max_pos=max_pos, confidence=confidence, provenance=provenance)


# ---------------------------------------------------------------------------
# TestExpandPointEstimates
# ---------------------------------------------------------------------------


class TestExpandPointEstimates:
    def test_narrow_expanded(self) -> None:
        """Point (145.0, 145.5) with spatial_precision=3.0 is expanded."""
        point = _bp(145.0, 145.5)
        # spatial_precision=3.0 > span 0.5, so expansion triggers
        result = _expand_point_estimate(point, spatial_precision=3.0)
        # Midpoint = 145.25, expanded by spatial_precision 3.0 each side
        assert result.min_pos == 145.25 - 3.0  # 142.25
        assert result.max_pos == 145.25 + 3.0  # 148.25
        assert result.confidence == point.confidence
        assert result.provenance == point.provenance

    def test_wide_unchanged(self) -> None:
        """Point (140.0, 150.0) with spatial_precision=3.0 is unchanged (range >= precision)."""
        point = _bp(140.0, 150.0)
        result = _expand_point_estimate(point, spatial_precision=3.0)
        assert result.min_pos == 140.0
        assert result.max_pos == 150.0
        assert result is point  # same object returned


# ---------------------------------------------------------------------------
# TestOverlapMerge
# ---------------------------------------------------------------------------


class TestOverlapMerge:
    def test_overlapping_merged(self) -> None:
        """Points (143, 146) and (145, 148) overlap and merge into one cluster."""
        points = [_bp(143, 146), _bp(145, 148)]
        clusters = _merge_overlapping(points)
        assert len(clusters) == 1
        assert len(clusters[0]) == 2

    def test_nonoverlapping_separate(self) -> None:
        """Points (140, 143) and (146, 149) don't overlap -- two separate clusters."""
        points = [_bp(140, 143), _bp(146, 149)]
        clusters = _merge_overlapping(points)
        assert len(clusters) == 2
        assert len(clusters[0]) == 1
        assert len(clusters[1]) == 1

    def test_adjacent_not_merged(self) -> None:
        """Points (140, 145) and (145.1, 150) have a 0.1pt gap -- two clusters."""
        points = [_bp(140, 145), _bp(145.1, 150)]
        clusters = _merge_overlapping(points)
        assert len(clusters) == 2


# ---------------------------------------------------------------------------
# TestCombineHypotheses
# ---------------------------------------------------------------------------


class TestCombineHypotheses:
    def test_two_methods_agree(self) -> None:
        """Two hypotheses with overlapping column boundaries merge into one consensus boundary."""
        ctx = _make_ctx(ruled_line_thickness=1.0)
        h1 = BoundaryHypothesis(
            col_boundaries=(_bp(145.0, 145.0, 0.9, "method_a"),),
            row_boundaries=(),
            method="method_a",
            metadata={},
        )
        h2 = BoundaryHypothesis(
            col_boundaries=(_bp(146.0, 146.0, 0.8, "method_b"),),
            row_boundaries=(),
            method="method_b",
            metadata={},
        )
        result = combine_hypotheses([h1, h2], ctx)
        assert len(result.col_boundaries) == 1
        # Mean confidence = (0.9 + 0.8) / 2 = 0.85
        assert result.col_boundaries[0].confidence == pytest.approx((0.9 + 0.8) / 2)
        assert result.method == "consensus"

    def test_three_methods_one_disagrees(self) -> None:
        """3 hypotheses: 2 agree at ~145, 1 at ~200. Outlier rejected by method count."""
        ctx = _make_ctx(ruled_line_thickness=1.0)
        h1 = BoundaryHypothesis(
            col_boundaries=(_bp(145.0, 145.0, 0.9, "method_a"),),
            row_boundaries=(),
            method="method_a",
            metadata={},
        )
        h2 = BoundaryHypothesis(
            col_boundaries=(_bp(146.0, 146.0, 0.8, "method_b"),),
            row_boundaries=(),
            method="method_b",
            metadata={},
        )
        h3 = BoundaryHypothesis(
            col_boundaries=(_bp(200.0, 200.0, 0.7, "method_c"),),
            row_boundaries=(),
            method="method_c",
            metadata={},
        )
        result = combine_hypotheses([h1, h2, h3], ctx)
        # Two clusters: ~145 (method_count=2), ~200 (method_count=1)
        # Median method count = 1.5. Only count >= 1.5 passes.
        assert len(result.col_boundaries) == 1

    def test_empty_hypotheses_list(self) -> None:
        """Empty input returns hypothesis with empty boundaries."""
        ctx = _make_ctx()
        result = combine_hypotheses([], ctx)
        assert result.col_boundaries == ()
        assert result.row_boundaries == ()
        assert result.method == "consensus"

    def test_single_hypothesis_passthrough(self) -> None:
        """One hypothesis: consensus equals input (single cluster accepted unconditionally)."""
        ctx = _make_ctx(ruled_line_thickness=1.0)
        boundary = _bp(145.0, 145.0, 0.9, "method_a")
        h1 = BoundaryHypothesis(
            col_boundaries=(boundary,),
            row_boundaries=(_bp(50.0, 50.0, 0.85, "method_a"),),
            method="method_a",
            metadata={},
        )
        result = combine_hypotheses([h1], ctx)
        assert len(result.col_boundaries) == 1
        assert len(result.row_boundaries) == 1
        # Single cluster is accepted unconditionally
        assert result.col_boundaries[0].confidence == 0.9
        assert result.row_boundaries[0].confidence == 0.85

    def test_row_and_col_independent(self) -> None:
        """Column combination doesn't affect row combination and vice versa."""
        ctx = _make_ctx(ruled_line_thickness=1.0)
        h1 = BoundaryHypothesis(
            col_boundaries=(_bp(100.0, 100.0, 0.9, "m1"),),
            row_boundaries=(_bp(200.0, 200.0, 0.9, "m1"),),
            method="m1",
            metadata={},
        )
        h2 = BoundaryHypothesis(
            col_boundaries=(_bp(300.0, 300.0, 0.9, "m2"),),
            row_boundaries=(_bp(400.0, 400.0, 0.9, "m2"),),
            method="m2",
            metadata={},
        )
        result = combine_hypotheses([h1, h2], ctx)
        # Each position has method_count=1, median=1, all pass.
        col_positions = sorted(b.min_pos for b in result.col_boundaries)
        row_positions = sorted(b.min_pos for b in result.row_boundaries)
        assert all(90 < p < 310 for p in col_positions)
        assert all(190 < p < 410 for p in row_positions)
        assert len(result.col_boundaries) == 2
        assert len(result.row_boundaries) == 2


# ---------------------------------------------------------------------------
# TestAcceptanceThreshold
# ---------------------------------------------------------------------------


class TestAcceptanceThreshold:
    def test_low_confidence_rejected(self) -> None:
        """Cluster with low method count is rejected by median method count threshold."""
        ctx = _make_ctx(ruled_line_thickness=1.0)
        h1 = BoundaryHypothesis(
            col_boundaries=(_bp(145.0, 145.0, 0.9, "m1"),),
            row_boundaries=(),
            method="m1",
            metadata={},
        )
        h2 = BoundaryHypothesis(
            col_boundaries=(_bp(146.0, 146.0, 0.9, "m2"),),
            row_boundaries=(),
            method="m2",
            metadata={},
        )
        h3 = BoundaryHypothesis(
            col_boundaries=(
                _bp(145.0, 145.0, 0.9, "m3"),
                _bp(500.0, 500.0, 0.01, "m3"),
            ),
            row_boundaries=(),
            method="m3",
            metadata={},
        )
        result = combine_hypotheses([h1, h2, h3], ctx)
        # Cluster at ~145: method_count=3 (m1, m2, m3), cluster at ~500: method_count=1 (m3)
        # Median method count = 2. Count 1 < 2 -> rejected.
        positions = [b.min_pos for b in result.col_boundaries]
        assert len(result.col_boundaries) == 1
        assert abs(positions[0] - 145.0) < 5.0

    def test_single_high_confidence_accepted(self) -> None:
        """One cluster from one method with confidence 0.95 is accepted (only cluster, unconditional)."""
        ctx = _make_ctx(ruled_line_thickness=1.0)
        h = BoundaryHypothesis(
            col_boundaries=(_bp(200.0, 200.0, 0.95, "solo_method"),),
            row_boundaries=(),
            method="solo_method",
            metadata={},
        )
        result = combine_hypotheses([h], ctx)
        assert len(result.col_boundaries) == 1
        assert result.col_boundaries[0].confidence == 0.95

    def test_equal_method_agreement_all_pass(self) -> None:
        """All clusters have method_count=2 (both methods contribute), median=2, all pass."""
        ctx = _make_ctx(ruled_line_thickness=2.0)
        h1 = BoundaryHypothesis(
            col_boundaries=(
                _bp(100.0, 100.0, 0.5, "m1"),
                _bp(200.0, 200.0, 1.0, "m1"),
                _bp(300.0, 300.0, 5.0, "m1"),
                _bp(400.0, 400.0, 5.0, "m1"),
                _bp(500.0, 500.0, 5.0, "m1"),
            ),
            row_boundaries=(),
            method="m1",
            metadata={},
        )
        h2 = BoundaryHypothesis(
            col_boundaries=(
                _bp(100.5, 100.5, 0.5, "m2"),
                _bp(200.5, 200.5, 1.0, "m2"),
                _bp(300.5, 300.5, 5.0, "m2"),
                _bp(400.5, 400.5, 5.0, "m2"),
                _bp(500.5, 500.5, 5.0, "m2"),
            ),
            row_boundaries=(),
            method="m2",
            metadata={},
        )
        result = combine_hypotheses([h1, h2], ctx)
        # All 5 clusters have method_count=2, median=2, all pass.
        assert len(result.col_boundaries) == 5

    def test_single_cluster_always_accepted(self) -> None:
        """When multiple hypotheses merge into a single cluster, it is accepted unconditionally."""
        ctx = _make_ctx(ruled_line_thickness=2.0)
        h1 = BoundaryHypothesis(
            col_boundaries=(_bp(100.0, 100.0, 0.1, "m1"),),
            row_boundaries=(),
            method="m1",
            metadata={},
        )
        h2 = BoundaryHypothesis(
            col_boundaries=(_bp(100.5, 100.5, 0.1, "m2"),),
            row_boundaries=(),
            method="m2",
            metadata={},
        )
        result = combine_hypotheses([h1, h2], ctx)
        assert len(result.col_boundaries) == 1


# ---------------------------------------------------------------------------
# TestMethodCountRejection
# ---------------------------------------------------------------------------


class TestMethodCountRejection:
    def test_lone_divider_rejected(self) -> None:
        """3 methods: m1+m2 agree at ~150, m1+m3 agree at ~300, m2 alone at ~500. ~500 rejected."""
        ctx = _make_ctx(ruled_line_thickness=1.0)
        h1 = BoundaryHypothesis(
            col_boundaries=(
                _bp(150.0, 150.0, 0.9, "m1"),
                _bp(300.0, 300.0, 0.9, "m1"),
            ),
            row_boundaries=(),
            method="m1",
            metadata={},
        )
        h2 = BoundaryHypothesis(
            col_boundaries=(
                _bp(150.5, 150.5, 0.9, "m2"),
                _bp(500.0, 500.0, 0.9, "m2"),
            ),
            row_boundaries=(),
            method="m2",
            metadata={},
        )
        h3 = BoundaryHypothesis(
            col_boundaries=(_bp(300.5, 300.5, 0.9, "m3"),),
            row_boundaries=(),
            method="m3",
            metadata={},
        )
        result = combine_hypotheses([h1, h2, h3], ctx)
        # Clusters: ~150 (m1,m2 -> count=2), ~300 (m1,m3 -> count=2), ~500 (m2 -> count=1)
        # Median method count = 2. Count 1 < 2 -> ~500 rejected.
        assert len(result.col_boundaries) == 2
        positions = sorted(b.min_pos for b in result.col_boundaries)
        assert abs(positions[0] - 150.0) < 5.0
        assert abs(positions[1] - 300.0) < 5.0

    def test_single_method_all_pass(self) -> None:
        """1 method with 3 col boundaries: passthrough (single hypothesis), all accepted."""
        ctx = _make_ctx(ruled_line_thickness=1.0)
        h = BoundaryHypothesis(
            col_boundaries=(
                _bp(100.0, 100.0, 0.9, "m1"),
                _bp(200.0, 200.0, 0.8, "m1"),
                _bp(300.0, 300.0, 0.7, "m1"),
            ),
            row_boundaries=(),
            method="m1",
            metadata={},
        )
        result = combine_hypotheses([h], ctx)
        assert len(result.col_boundaries) == 3


# ---------------------------------------------------------------------------
# TestConfidenceMultipliers
# ---------------------------------------------------------------------------


class TestConfidenceMultipliers:
    def test_multipliers_scale_confidence(self) -> None:
        """Method multipliers scale confidence before combination. Mean of scaled confidences."""
        ctx = _make_ctx(ruled_line_thickness=1.0)
        h1 = BoundaryHypothesis(
            col_boundaries=(_bp(145.0, 145.0, 0.9, "m1"),),
            row_boundaries=(),
            method="m1",
            metadata={},
        )
        h2 = BoundaryHypothesis(
            col_boundaries=(_bp(146.0, 146.0, 0.9, "m2"),),
            row_boundaries=(),
            method="m2",
            metadata={},
        )
        result = combine_hypotheses(
            [h1, h2], ctx,
            confidence_multipliers={"m1": 2.0, "m2": 0.5},
        )
        assert len(result.col_boundaries) == 1
        # Scaled confidences: 0.9*2.0=1.8, 0.9*0.5=0.45. Mean = (1.8 + 0.45) / 2 = 1.125
        assert result.col_boundaries[0].confidence == pytest.approx(1.125)

    def test_no_multipliers_default(self) -> None:
        """Without confidence_multipliers parameter, behavior is unscaled."""
        ctx = _make_ctx(ruled_line_thickness=1.0)
        h1 = BoundaryHypothesis(
            col_boundaries=(_bp(145.0, 145.0, 0.9, "m1"),),
            row_boundaries=(),
            method="m1",
            metadata={},
        )
        h2 = BoundaryHypothesis(
            col_boundaries=(_bp(146.0, 146.0, 0.8, "m2"),),
            row_boundaries=(),
            method="m2",
            metadata={},
        )
        result = combine_hypotheses([h1, h2], ctx)
        # Without multipliers: mean confidence = (0.9 + 0.8) / 2 = 0.85
        assert result.col_boundaries[0].confidence == pytest.approx(0.85)


# ---------------------------------------------------------------------------
# TestRuledLineOverride
# ---------------------------------------------------------------------------


class TestRuledLineOverride:
    def test_ruled_line_always_accepted(self) -> None:
        """Ruled line boundary accepted even with method_count below threshold."""
        ctx = _make_ctx(ruled_line_thickness=1.0)
        h1 = BoundaryHypothesis(
            col_boundaries=(_bp(150.0, 150.0, 0.9, "m1"),),
            row_boundaries=(),
            method="m1",
            metadata={},
        )
        h2 = BoundaryHypothesis(
            col_boundaries=(_bp(150.5, 150.5, 0.9, "m2"),),
            row_boundaries=(),
            method="m2",
            metadata={},
        )
        h3 = BoundaryHypothesis(
            col_boundaries=(_bp(300.0, 300.0, 0.9, "ruled_lines"),),
            row_boundaries=(),
            method="ruled_lines",
            metadata={},
        )
        result = combine_hypotheses([h1, h2, h3], ctx)
        # Clusters: ~150 (m1,m2 -> count=2), ~300 (ruled_lines -> count=1)
        # Median method count = 1.5. Count 1 < 1.5 for ~300, but ruled_lines override -> accepted.
        assert len(result.col_boundaries) == 2
        positions = sorted(b.min_pos for b in result.col_boundaries)
        assert abs(positions[0] - 150.0) < 5.0
        assert abs(positions[1] - 300.0) < 5.0

    def test_non_ruled_line_still_rejected(self) -> None:
        """Non-ruled-line boundary with low method count is still rejected."""
        ctx = _make_ctx(ruled_line_thickness=1.0)
        h1 = BoundaryHypothesis(
            col_boundaries=(_bp(150.0, 150.0, 0.9, "m1"),),
            row_boundaries=(),
            method="m1",
            metadata={},
        )
        h2 = BoundaryHypothesis(
            col_boundaries=(_bp(150.5, 150.5, 0.9, "m2"),),
            row_boundaries=(),
            method="m2",
            metadata={},
        )
        h3 = BoundaryHypothesis(
            col_boundaries=(_bp(300.0, 300.0, 0.9, "hotspot"),),
            row_boundaries=(),
            method="hotspot",
            metadata={},
        )
        result = combine_hypotheses([h1, h2, h3], ctx)
        # Clusters: ~150 (m1,m2 -> count=2), ~300 (hotspot -> count=1)
        # Median method count = 1.5. Count 1 < 1.5 for ~300, no override -> rejected.
        assert len(result.col_boundaries) == 1
        assert abs(result.col_boundaries[0].min_pos - 150.0) < 5.0


# ---------------------------------------------------------------------------
# TestCombinationTrace
# ---------------------------------------------------------------------------


class TestCombinationTrace:
    def test_trace_false_returns_hypothesis_only(self) -> None:
        """combine_hypotheses with trace=False returns BoundaryHypothesis, not a tuple."""
        ctx = _make_ctx(ruled_line_thickness=1.0)
        h = BoundaryHypothesis(
            col_boundaries=(_bp(100.0, 100.0, 0.9, "m1"),),
            row_boundaries=(),
            method="m1",
            metadata={},
        )
        result = combine_hypotheses([h], ctx, trace=False)
        assert isinstance(result, BoundaryHypothesis)
        assert not isinstance(result, tuple)

    def test_trace_true_returns_tuple(self) -> None:
        """combine_hypotheses with trace=True returns (BoundaryHypothesis, CombinationTrace)."""
        ctx = _make_ctx(ruled_line_thickness=1.0)
        h = BoundaryHypothesis(
            col_boundaries=(_bp(100.0, 100.0, 0.9, "m1"),),
            row_boundaries=(),
            method="m1",
            metadata={},
        )
        result = combine_hypotheses([h], ctx, trace=True)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], BoundaryHypothesis)
        assert isinstance(result[1], CombinationTrace)

    def test_empty_hypotheses_trace(self) -> None:
        """Empty hypothesis list with trace=True produces empty axis traces."""
        ctx = _make_ctx()
        result, trace = combine_hypotheses([], ctx, trace=True)
        assert trace.col_trace.input_points == []
        assert trace.row_trace.input_points == []
        assert trace.col_trace.accepted_positions == []
        assert trace.row_trace.accepted_positions == []
        assert trace.source_methods == []

    def test_single_hypothesis_passthrough_trace(self) -> None:
        """Single hypothesis with trace=True: source_methods has 1 entry, positions preserved."""
        ctx = _make_ctx(ruled_line_thickness=1.0)
        h = BoundaryHypothesis(
            col_boundaries=(_bp(100.0, 100.0, 0.9, "m1"), _bp(200.0, 200.0, 0.8, "m1")),
            row_boundaries=(_bp(50.0, 50.0, 0.7, "m1"),),
            method="m1",
            metadata={},
        )
        result, trace = combine_hypotheses([h], ctx, trace=True)
        assert trace.source_methods == ["m1"]
        assert len(trace.col_trace.accepted_positions) == 2
        assert len(trace.row_trace.accepted_positions) == 1

    def test_multi_hypothesis_trace_structure(self) -> None:
        """3 hypotheses with trace=True: source_methods has 3, clusters have method_names and acceptance_reason."""
        ctx = _make_ctx(ruled_line_thickness=1.0)
        h1 = BoundaryHypothesis(
            col_boundaries=(_bp(100.0, 100.0, 0.9, "m1"),),
            row_boundaries=(),
            method="m1",
            metadata={},
        )
        h2 = BoundaryHypothesis(
            col_boundaries=(_bp(101.0, 101.0, 0.8, "m2"),),
            row_boundaries=(),
            method="m2",
            metadata={},
        )
        h3 = BoundaryHypothesis(
            col_boundaries=(_bp(300.0, 300.0, 0.7, "m3"),),
            row_boundaries=(),
            method="m3",
            metadata={},
        )
        _, trace = combine_hypotheses([h1, h2, h3], ctx, trace=True)
        assert len(trace.source_methods) == 3
        assert len(trace.col_trace.clusters) == 2
        for cluster in trace.col_trace.clusters:
            assert isinstance(cluster, ClusterRecord)
            assert cluster.total_confidence > 0
            assert cluster.distinct_methods >= 1
            assert cluster.acceptance_threshold >= 0
            assert isinstance(cluster.method_names, list)
            assert set(cluster.method_names) <= {"m1", "m2", "m3"}
            assert cluster.acceptance_reason in ("above_threshold", "ruled_line_override", "rejected")

    def test_axis_trace_input_points_match(self) -> None:
        """Input points in col_trace contain all methods' boundary points."""
        ctx = _make_ctx(ruled_line_thickness=1.0)
        bp1 = _bp(100.0, 100.0, 0.9, "m1")
        bp2 = _bp(200.0, 200.0, 0.8, "m2")
        h1 = BoundaryHypothesis(
            col_boundaries=(bp1,),
            row_boundaries=(),
            method="m1",
            metadata={},
        )
        h2 = BoundaryHypothesis(
            col_boundaries=(bp2,),
            row_boundaries=(),
            method="m2",
            metadata={},
        )
        _, trace = combine_hypotheses([h1, h2], ctx, trace=True)
        input_provenances = {pt.provenance for pt in trace.col_trace.input_points}
        assert "m1" in input_provenances
        assert "m2" in input_provenances

    def test_trace_cluster_has_method_names(self) -> None:
        """Single cluster from m1+m2 has both method names."""
        ctx = _make_ctx(ruled_line_thickness=1.0)
        h1 = BoundaryHypothesis(
            col_boundaries=(_bp(100.0, 100.0, 0.9, "m1"),),
            row_boundaries=(),
            method="m1",
            metadata={},
        )
        h2 = BoundaryHypothesis(
            col_boundaries=(_bp(101.0, 101.0, 0.8, "m2"),),
            row_boundaries=(),
            method="m2",
            metadata={},
        )
        _, trace = combine_hypotheses([h1, h2], ctx, trace=True)
        assert len(trace.col_trace.clusters) == 1
        cluster = trace.col_trace.clusters[0]
        assert set(cluster.method_names) == {"m1", "m2"}

    def test_trace_has_median_method_count(self) -> None:
        """Two methods at same position: single cluster with median_method_count == 2.0."""
        ctx = _make_ctx(ruled_line_thickness=1.0)
        h1 = BoundaryHypothesis(
            col_boundaries=(_bp(100.0, 100.0, 0.9, "m1"),),
            row_boundaries=(),
            method="m1",
            metadata={},
        )
        h2 = BoundaryHypothesis(
            col_boundaries=(_bp(101.0, 101.0, 0.8, "m2"),),
            row_boundaries=(),
            method="m2",
            metadata={},
        )
        _, trace = combine_hypotheses([h1, h2], ctx, trace=True)
        assert trace.col_trace.median_method_count == 2.0

    def test_acceptance_reason_values(self) -> None:
        """3 hypotheses where one cluster is rejected: both acceptance reasons present."""
        ctx = _make_ctx(ruled_line_thickness=1.0)
        h1 = BoundaryHypothesis(
            col_boundaries=(_bp(150.0, 150.0, 0.9, "m1"),),
            row_boundaries=(),
            method="m1",
            metadata={},
        )
        h2 = BoundaryHypothesis(
            col_boundaries=(_bp(150.5, 150.5, 0.9, "m2"),),
            row_boundaries=(),
            method="m2",
            metadata={},
        )
        h3 = BoundaryHypothesis(
            col_boundaries=(_bp(500.0, 500.0, 0.9, "m3"),),
            row_boundaries=(),
            method="m3",
            metadata={},
        )
        _, trace = combine_hypotheses([h1, h2, h3], ctx, trace=True)
        reasons = {c.acceptance_reason for c in trace.col_trace.clusters}
        assert "rejected" in reasons
        assert "above_threshold" in reasons


# ---------------------------------------------------------------------------
# TestScalePoint
# ---------------------------------------------------------------------------


class TestScalePoint:
    def test_no_multipliers(self) -> None:
        """None multipliers returns point unchanged."""
        pt = _bp(100.0, 100.0, 0.9, "m1")
        result = _scale_point(pt, None)
        assert result is pt

    def test_multiplier_1_0_unchanged(self) -> None:
        """Multiplier of 1.0 returns point unchanged."""
        pt = _bp(100.0, 100.0, 0.9, "m1")
        result = _scale_point(pt, {"m1": 1.0})
        assert result is pt

    def test_multiplier_scales(self) -> None:
        """Multiplier of 2.0 doubles confidence."""
        pt = _bp(100.0, 100.0, 0.9, "m1")
        result = _scale_point(pt, {"m1": 2.0})
        assert result.confidence == pytest.approx(1.8)
        assert result.min_pos == 100.0
        assert result.max_pos == 100.0
        assert result.provenance == "m1"

    def test_missing_method_default_1_0(self) -> None:
        """Method not in multipliers dict gets default 1.0 (unchanged)."""
        pt = _bp(100.0, 100.0, 0.9, "m1")
        result = _scale_point(pt, {"m2": 2.0})
        assert result is pt


# ---------------------------------------------------------------------------
# TestSpatialPrecision
# ---------------------------------------------------------------------------


class TestSpatialPrecision:
    def test_ruled_lines_take_priority(self) -> None:
        """Spatial precision equals median ruled line thickness when ruled lines exist."""
        ctx = _make_ctx(ruled_line_thickness=2.0, word_gap=5.0)
        assert _compute_spatial_precision(ctx) == 2.0

    def test_word_gap_fallback(self) -> None:
        """Without ruled lines, spatial precision falls back to median word gap."""
        ctx = _make_ctx(ruled_line_thickness=None, word_gap=5.0)
        assert _compute_spatial_precision(ctx) == 5.0

    def test_word_height_fallback(self) -> None:
        """Without ruled lines or word gaps, spatial precision equals median word height."""
        ctx = _make_ctx(ruled_line_thickness=None, word_gap=0.0)
        assert _compute_spatial_precision(ctx) == 10.0

    def test_varies_with_context(self) -> None:
        """Different contexts produce different spatial precision values."""
        ctx1 = _make_ctx(ruled_line_thickness=2.0)
        ctx2 = _make_ctx(ruled_line_thickness=4.0)
        assert _compute_spatial_precision(ctx1) != _compute_spatial_precision(ctx2)
