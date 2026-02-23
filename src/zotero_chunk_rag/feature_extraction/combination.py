"""Boundary combination engine -- per-divider voting across structure methods.

Merges ``BoundaryHypothesis`` objects from multiple structure methods into a
single consensus hypothesis. Each boundary position is voted on independently:
a divider that many methods independently detect (high method agreement) is
more trustworthy than one only a single method reports. Ruled line boundaries
get unconditional acceptance (physical features, not statistical).

Confidence multipliers (from ``pipeline_weights.json``) scale each method's
influence before voting.
"""

from __future__ import annotations

import statistics

from .models import (
    AxisTrace,
    BoundaryHypothesis,
    BoundaryPoint,
    ClusterRecord,
    CombinationTrace,
    PointExpansion,
    TableContext,
)


def _scale_point(
    point: BoundaryPoint,
    multipliers: dict[str, float] | None,
) -> BoundaryPoint:
    """Scale a boundary point's confidence by its method's multiplier.

    Returns the point unchanged if *multipliers* is ``None`` or the method's
    multiplier is 1.0. Otherwise returns a new ``BoundaryPoint`` with
    ``confidence * multiplier``.
    """
    if multipliers is None:
        return point
    mult = multipliers.get(point.provenance, 1.0)
    if mult == 1.0:
        return point
    return BoundaryPoint(
        min_pos=point.min_pos,
        max_pos=point.max_pos,
        confidence=point.confidence * mult,
        provenance=point.provenance,
    )


def combine_hypotheses(
    hypotheses: list[BoundaryHypothesis],
    ctx: TableContext,
    *,
    confidence_multipliers: dict[str, float] | None = None,
    trace: bool = False,
) -> BoundaryHypothesis | tuple[BoundaryHypothesis, CombinationTrace]:
    """Combine multiple boundary hypotheses into a single consensus.

    All boundary points from all hypotheses are pooled and voted on
    independently per divider position. Acceptance is based on the number
    of distinct methods that agree on each cluster (median method count
    threshold). Ruled line boundaries are unconditionally accepted.

    Parameters
    ----------
    hypotheses:
        Zero or more boundary hypotheses from different structure methods.
    ctx:
        Table context (used for adaptive thresholds).
    confidence_multipliers:
        Optional dict mapping method name to a scaling factor for its
        boundary point confidences. When ``None``, no scaling is applied.
    trace:
        If True, return ``(hypothesis, trace)`` with diagnostic data.

    Returns
    -------
    BoundaryHypothesis
        Consensus hypothesis.
    CombinationTrace (only when trace=True)
        Diagnostic trace of the combination process.
    """
    if not hypotheses:
        result = BoundaryHypothesis(
            col_boundaries=(),
            row_boundaries=(),
            method="consensus",
            metadata={},
        )
        if trace:
            empty_axis = AxisTrace(
                input_points=[],
                expansions=[],
                clusters=[],
                median_confidence=0.0,
                acceptance_threshold=0.0,
                accepted_positions=[],
            )
            return result, CombinationTrace(
                col_trace=empty_axis,
                row_trace=empty_axis,
                spatial_precision=0.0,
                source_methods=[],
            )
        return result

    # Single hypothesis: pass through
    if len(hypotheses) == 1:
        hyp = hypotheses[0]
        result = BoundaryHypothesis(
            col_boundaries=hyp.col_boundaries,
            row_boundaries=hyp.row_boundaries,
            method="consensus",
            metadata={"source_methods": [hyp.method], "passthrough": True},
        )
        if trace:
            col_trace = _make_passthrough_trace(list(hyp.col_boundaries))
            row_trace = _make_passthrough_trace(list(hyp.row_boundaries))
            return result, CombinationTrace(
                col_trace=col_trace,
                row_trace=row_trace,
                spatial_precision=0.0,
                source_methods=[hyp.method],
            )
        return result

    # Multi-hypothesis: per-divider voting
    spatial_precision = _compute_spatial_precision(ctx)
    source_methods = list(dict.fromkeys(h.method for h in hypotheses))

    # Pool ALL col and row boundary points from ALL hypotheses, scaling confidence
    all_col_points: list[BoundaryPoint] = []
    all_row_points: list[BoundaryPoint] = []
    for hyp in hypotheses:
        for pt in hyp.col_boundaries:
            all_col_points.append(_scale_point(pt, confidence_multipliers))
        for pt in hyp.row_boundaries:
            all_row_points.append(_scale_point(pt, confidence_multipliers))

    col_accepted, col_trace_obj = _combine_axis(
        all_col_points, spatial_precision, collect_trace=trace,
    )
    row_accepted, row_trace_obj = _combine_axis(
        all_row_points, spatial_precision, collect_trace=trace,
    )

    result = BoundaryHypothesis(
        col_boundaries=tuple(col_accepted),
        row_boundaries=tuple(row_accepted),
        method="consensus",
        metadata={"source_methods": source_methods},
    )

    if trace:
        return result, CombinationTrace(
            col_trace=col_trace_obj,
            row_trace=row_trace_obj,
            spatial_precision=spatial_precision,
            source_methods=source_methods,
        )
    return result


def _make_passthrough_trace(points: list[BoundaryPoint]) -> AxisTrace:
    """Create a trace for a single-hypothesis passthrough."""
    return AxisTrace(
        input_points=points,
        expansions=[
            PointExpansion(
                original=pt,
                expanded_min=pt.min_pos,
                expanded_max=pt.max_pos,
                was_expanded=False,
            )
            for pt in points
        ],
        clusters=[
            ClusterRecord(
                points=[pt],
                total_confidence=pt.confidence,
                distinct_methods=1,
                weighted_position=(pt.min_pos + pt.max_pos) / 2,
                accepted=True,
                acceptance_threshold=0.0,
            )
            for pt in points
        ],
        median_confidence=statistics.median([pt.confidence for pt in points]) if points else 0.0,
        acceptance_threshold=0.0,
        accepted_positions=[(pt.min_pos + pt.max_pos) / 2 for pt in points],
    )


def _compute_spatial_precision(ctx: TableContext) -> float:
    """Single adaptive precision value for boundary expansion and tolerance.

    Priority chain (no multiplier constants):
    1. Median ruled line thickness (if ruled lines present)
    2. Median inter-word gap (if measurable)
    3. Median word height (always available from words in the table)

    The returned value is used directly as both the expansion threshold
    (ranges narrower than this get expanded) and the tolerance (how much
    to expand by).
    """
    ruled = ctx.median_ruled_line_thickness
    if ruled is not None:
        return ruled
    word_gap = ctx.median_word_gap
    if word_gap > 0:
        return word_gap
    return ctx.median_word_height


def _expand_point_estimate(
    point: BoundaryPoint,
    spatial_precision: float,
) -> BoundaryPoint:
    """Expand a narrow boundary range to at least *spatial_precision* width.

    Wide ranges (``max_pos - min_pos >= spatial_precision``) are returned
    unchanged.  Narrow ranges are expanded symmetrically around their midpoint
    by *spatial_precision*.
    """
    span = point.max_pos - point.min_pos
    if span >= spatial_precision:
        return point

    midpoint = (point.min_pos + point.max_pos) / 2
    return BoundaryPoint(
        min_pos=midpoint - spatial_precision,
        max_pos=midpoint + spatial_precision,
        confidence=point.confidence,
        provenance=point.provenance,
    )


def _merge_overlapping(
    points: list[BoundaryPoint],
) -> list[list[BoundaryPoint]]:
    """Greedy strict-overlap merge of sorted boundary points.

    Points must already be sorted by ``min_pos``.  Two points overlap if the
    next point's ``min_pos <= current cluster's max_pos``.  No tolerance is
    added -- only actual overlaps merge.

    Returns a list of clusters, where each cluster is a list of contributing
    ``BoundaryPoint`` objects.
    """
    if not points:
        return []

    clusters: list[list[BoundaryPoint]] = [[points[0]]]
    cluster_max = points[0].max_pos

    for pt in points[1:]:
        if pt.min_pos <= cluster_max:
            clusters[-1].append(pt)
            cluster_max = max(cluster_max, pt.max_pos)
        else:
            clusters.append([pt])
            cluster_max = pt.max_pos

    return clusters


def _combine_axis(
    points: list[BoundaryPoint],
    spatial_precision: float,
    *,
    collect_trace: bool = False,
) -> tuple[list[BoundaryPoint], AxisTrace | None]:
    """Full combination pipeline for one axis (column or row).

    1. Expand point estimates (ranges narrower than *spatial_precision*).
    2. Sort by min_pos.
    3. Strict overlap merge into clusters.
    4. Compute cluster properties (confidence-weighted position, distinct methods).
    5. Accept/reject via median method count threshold + ruled line override.

    Returns
    -------
    tuple[list[BoundaryPoint], AxisTrace | None]
        Accepted boundary points and optional trace (None when collect_trace=False).
    """
    if not points:
        if collect_trace:
            return [], AxisTrace(
                input_points=[],
                expansions=[],
                clusters=[],
                median_confidence=0.0,
                acceptance_threshold=0.0,
                accepted_positions=[],
            )
        return [], None

    # Step 1: expand narrow ranges
    expansions: list[PointExpansion] = []
    expanded: list[BoundaryPoint] = []
    for pt in points:
        exp = _expand_point_estimate(pt, spatial_precision)
        expanded.append(exp)
        if collect_trace:
            expansions.append(PointExpansion(
                original=pt,
                expanded_min=exp.min_pos,
                expanded_max=exp.max_pos,
                was_expanded=(exp is not pt),
            ))

    # Step 2: sort by min_pos
    expanded.sort(key=lambda p: p.min_pos)

    # Step 3: strict overlap merge
    clusters = _merge_overlapping(expanded)

    # Step 4: compute cluster properties
    cluster_props: list[tuple[float, float, int, str, list[BoundaryPoint], bool]] = []
    for cluster in clusters:
        total_confidence = sum(pt.confidence for pt in cluster)
        mean_confidence = total_confidence / len(cluster)
        # Confidence-weighted average of midpoints
        weighted_sum = sum(
            ((pt.min_pos + pt.max_pos) / 2) * pt.confidence for pt in cluster
        )
        if total_confidence > 0:
            position = weighted_sum / total_confidence
        else:
            position = sum((pt.min_pos + pt.max_pos) / 2 for pt in cluster) / len(cluster)

        distinct_methods = len(set(pt.provenance for pt in cluster))
        combined_provenance = ",".join(
            dict.fromkeys(pt.provenance for pt in cluster)
        )
        has_ruled_line = any(pt.provenance == "ruled_lines" for pt in cluster)

        cluster_props.append((
            position, mean_confidence, distinct_methods,
            combined_provenance, list(cluster), has_ruled_line,
        ))

    # Step 5: accept/reject via median method count + ruled line override
    if len(cluster_props) == 1:
        pos, mean_conf, _support, prov, raw_cluster, _has_ruled = cluster_props[0]
        accepted = [BoundaryPoint(
            min_pos=pos,
            max_pos=pos,
            confidence=mean_conf,
            provenance=prov,
        )]
        if collect_trace:
            trace_obj = AxisTrace(
                input_points=list(points),
                expansions=expansions,
                clusters=[ClusterRecord(
                    points=raw_cluster,
                    total_confidence=sum(pt.confidence for pt in raw_cluster),
                    distinct_methods=_support,
                    weighted_position=pos,
                    accepted=True,
                    acceptance_threshold=0.0,
                )],
                median_confidence=mean_conf,
                acceptance_threshold=0.0,
                accepted_positions=[pos],
            )
            return accepted, trace_obj
        return accepted, None

    all_method_counts = [cp[2] for cp in cluster_props]
    median_method_count = statistics.median(all_method_counts)

    accepted: list[BoundaryPoint] = []
    cluster_records: list[ClusterRecord] = []

    for pos, mean_conf, support, prov, raw_cluster, has_ruled in cluster_props:
        is_accepted = support >= median_method_count or has_ruled
        if is_accepted:
            accepted.append(BoundaryPoint(
                min_pos=pos,
                max_pos=pos,
                confidence=mean_conf,
                provenance=prov,
            ))
        if collect_trace:
            cluster_records.append(ClusterRecord(
                points=raw_cluster,
                total_confidence=sum(pt.confidence for pt in raw_cluster),
                distinct_methods=support,
                weighted_position=pos,
                accepted=is_accepted,
                acceptance_threshold=median_method_count,
            ))

    all_mean_confs = [cp[1] for cp in cluster_props]
    median_confidence = statistics.median(all_mean_confs) if all_mean_confs else 0.0

    if collect_trace:
        trace_obj = AxisTrace(
            input_points=list(points),
            expansions=expansions,
            clusters=cluster_records,
            median_confidence=median_confidence,
            acceptance_threshold=median_method_count,
            accepted_positions=[bp.min_pos for bp in accepted],
        )
        return accepted, trace_obj

    return accepted, None
