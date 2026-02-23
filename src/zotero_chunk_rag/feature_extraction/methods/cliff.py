"""Cliff detection structure methods: global and per-row variants.

Both methods find "cliffs" (large relative jumps) in sorted gap distributions
to separate column gaps from intra-cell gaps.  The global variant pools all
gaps across all rows; the per-row variant analyzes each row independently
and clusters the resulting boundaries.
"""

from __future__ import annotations

import statistics
from typing import Any

from ..models import BoundaryHypothesis, BoundaryPoint, TableContext


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _find_cliff(sorted_gaps: list[float]) -> tuple[int, float] | None:
    """Find the cliff (largest ratio between consecutive sorted gaps).

    Args:
        sorted_gaps: Gaps sorted ascending.  Must have at least 2 elements.

    Returns:
        ``(cliff_index, ratio)`` where cliff_index is the index of the gap
        just *below* the cliff (i.e. gap[cliff_index+1]/gap[cliff_index]
        is the largest ratio).  Returns ``None`` if fewer than 2 gaps.
    """
    if len(sorted_gaps) < 2:
        return None

    best_index = 0
    best_ratio = 0.0

    for i in range(len(sorted_gaps) - 1):
        if sorted_gaps[i] > 0:
            ratio = sorted_gaps[i + 1] / sorted_gaps[i]
            if ratio > best_ratio:
                best_ratio = ratio
                best_index = i

    return (best_index, best_ratio)


def _boundary_confidence(gap: float, cliff_threshold: float) -> float:
    """Compute per-boundary confidence using ratio / (ratio + 1).

    Args:
        gap: The actual gap size for this boundary.
        cliff_threshold: The gap size just below the cliff.

    Returns:
        Confidence in [0, 1).
    """
    if cliff_threshold <= 0:
        return 0.5
    ratio = gap / cliff_threshold
    return ratio / (ratio + 1)


def _collect_all_gaps(
    data_word_rows: list[list[tuple]],
    min_gap: float,
) -> list[tuple[float, float]]:
    """Collect all inter-word gaps across all rows.

    Returns:
        List of ``(gap_size, x_midpoint)`` pairs, filtered by min_gap.
    """
    result: list[tuple[float, float]] = []
    for row in data_word_rows:
        if len(row) < 2:
            continue
        for i in range(len(row) - 1):
            gap = row[i + 1][0] - row[i][2]
            if gap >= min_gap:
                midpoint = (row[i][2] + row[i + 1][0]) / 2
                result.append((gap, midpoint))
    return result


def _median_word_width(data_word_rows: list[list[tuple]]) -> float:
    """Compute median word width from all words in data rows."""
    widths = [w[2] - w[0] for row in data_word_rows for w in row if (w[2] - w[0]) > 0]
    if not widths:
        return 10.0
    return statistics.median(widths)


def _cluster_boundaries(
    boundaries: list[tuple[float, float]],
    tolerance: float,
) -> list[dict[str, Any]]:
    """Cluster boundary candidates by x-position.

    Args:
        boundaries: List of ``(x_position, confidence)`` pairs.
        tolerance: Max distance for two boundaries to cluster.

    Returns:
        List of dicts with ``position``, ``confidences``, ``count``.
    """
    if not boundaries:
        return []

    sorted_b = sorted(boundaries, key=lambda b: b[0])
    clusters: list[dict[str, Any]] = []

    current_xs: list[float] = [sorted_b[0][0]]
    current_confs: list[float] = [sorted_b[0][1]]

    for x, conf in sorted_b[1:]:
        if x - statistics.median(current_xs) <= tolerance:
            current_xs.append(x)
            current_confs.append(conf)
        else:
            clusters.append({
                "position": statistics.median(current_xs),
                "confidences": list(current_confs),
                "count": len(current_xs),
            })
            current_xs = [x]
            current_confs = [conf]

    clusters.append({
        "position": statistics.median(current_xs),
        "confidences": list(current_confs),
        "count": len(current_xs),
    })

    return clusters


def _cluster_per_row_boundaries(
    boundaries: list[tuple[float, float, int]],
    tolerance: float,
) -> list[dict[str, Any]]:
    """Cluster per-row boundary candidates by x-position.

    Args:
        boundaries: List of ``(x_position, confidence, row_index)`` triples.
        tolerance: Max distance for two boundaries to cluster.

    Returns:
        List of dicts with ``position``, ``confidence``, ``row_indices``.
    """
    if not boundaries:
        return []

    sorted_b = sorted(boundaries, key=lambda b: b[0])
    clusters: list[dict[str, Any]] = []

    current_xs: list[float] = [sorted_b[0][0]]
    current_confs: list[float] = [sorted_b[0][1]]
    current_rows: set[int] = {sorted_b[0][2]}

    for x, conf, row_idx in sorted_b[1:]:
        if x - statistics.median(current_xs) <= tolerance:
            current_xs.append(x)
            current_confs.append(conf)
            current_rows.add(row_idx)
        else:
            clusters.append({
                "position": statistics.median(current_xs),
                "confidence": sum(current_confs) / len(current_confs),
                "row_indices": current_rows,
            })
            current_xs = [x]
            current_confs = [conf]
            current_rows = {row_idx}

    clusters.append({
        "position": statistics.median(current_xs),
        "confidence": sum(current_confs) / len(current_confs),
        "row_indices": current_rows,
    })

    return clusters


# ---------------------------------------------------------------------------
# StructureMethod implementations
# ---------------------------------------------------------------------------

class GlobalCliff:
    """Column boundary detection via global gap cliff analysis.

    Pools all inter-word gaps across all rows, sorts them, and finds the
    largest relative jump to separate column gaps from intra-cell gaps.
    """

    @property
    def name(self) -> str:
        return "global_cliff"

    def detect(self, ctx: TableContext) -> BoundaryHypothesis | None:
        rows = ctx.data_word_rows
        if not rows:
            return None

        min_gap = ctx.median_word_height * 0.25
        gap_data = _collect_all_gaps(rows, min_gap)

        if not gap_data:
            return None

        # Sort gaps by size for cliff detection
        sorted_sizes = sorted(g[0] for g in gap_data)

        cliff_result = _find_cliff(sorted_sizes)
        if cliff_result is None:
            return None

        cliff_index, _ = cliff_result
        cliff_threshold = sorted_sizes[cliff_index]

        # Gaps above the cliff are column gaps
        column_gap_threshold = cliff_threshold
        column_gaps = [(g, mid) for g, mid in gap_data if g > column_gap_threshold]

        if not column_gaps:
            return None

        # Build boundary points
        boundaries: list[tuple[float, float]] = []
        for gap_size, x_mid in column_gaps:
            conf = _boundary_confidence(gap_size, cliff_threshold)
            boundaries.append((x_mid, conf))

        # Cluster nearby boundaries
        tolerance = _median_word_width(rows)
        clusters = _cluster_boundaries(boundaries, tolerance)

        boundary_points: list[BoundaryPoint] = []
        for c in sorted(clusters, key=lambda c: c["position"]):
            mean_conf = sum(c["confidences"]) / len(c["confidences"])
            boundary_points.append(BoundaryPoint(
                min_pos=c["position"],
                max_pos=c["position"],
                confidence=mean_conf,
                provenance="global_cliff",
            ))

        return BoundaryHypothesis(
            col_boundaries=tuple(boundary_points),
            row_boundaries=(),
            method=self.name,
            metadata={
                "cliff_index": cliff_index,
                "cliff_threshold": cliff_threshold,
                "num_column_gaps": len(column_gaps),
            },
        )


class PerRowCliff:
    """Column boundary detection via per-row cliff analysis.

    Analyzes each row's gap distribution independently, finding the cliff
    within each row, then pools and clusters the resulting boundary candidates.
    """

    @property
    def name(self) -> str:
        return "per_row_cliff"

    def detect(self, ctx: TableContext) -> BoundaryHypothesis | None:
        rows = ctx.data_word_rows
        if not rows:
            return None

        min_gap = ctx.median_word_height * 0.25
        all_boundary_candidates: list[tuple[float, float, int]] = []

        for row_idx, row in enumerate(rows):
            if len(row) < 3:
                continue

            # Collect gaps for this row
            row_gaps: list[tuple[float, float]] = []
            for i in range(len(row) - 1):
                gap = row[i + 1][0] - row[i][2]
                if gap >= min_gap:
                    midpoint = (row[i][2] + row[i + 1][0]) / 2
                    row_gaps.append((gap, midpoint))

            if len(row_gaps) < 2:
                continue

            sorted_sizes = sorted(g[0] for g in row_gaps)
            cliff_result = _find_cliff(sorted_sizes)
            if cliff_result is None:
                continue

            cliff_index, _ = cliff_result
            cliff_threshold = sorted_sizes[cliff_index]

            # Gaps above the cliff are column boundaries
            for gap_size, x_mid in row_gaps:
                if gap_size > cliff_threshold:
                    conf = _boundary_confidence(gap_size, cliff_threshold)
                    all_boundary_candidates.append((x_mid, conf, row_idx))

        if not all_boundary_candidates:
            return None

        # Cluster across rows
        tolerance = _median_word_width(rows)
        clusters = _cluster_per_row_boundaries(all_boundary_candidates, tolerance)

        boundary_points: list[BoundaryPoint] = []
        for c in sorted(clusters, key=lambda c: c["position"]):
            boundary_points.append(BoundaryPoint(
                min_pos=c["position"],
                max_pos=c["position"],
                confidence=c["confidence"],
                provenance="per_row_cliff",
            ))

        return BoundaryHypothesis(
            col_boundaries=tuple(boundary_points),
            row_boundaries=(),
            method=self.name,
            metadata={
                "cluster_count": len(clusters),
                "row_support": [len(c["row_indices"]) for c in clusters],
            },
        )
