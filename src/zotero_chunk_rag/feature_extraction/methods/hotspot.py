"""Hotspot structure methods: single-point and gap-span variants.

Both methods detect column boundaries by finding x-positions where inter-word
gaps cluster across multiple rows.  The single-point variant counts only rows
with a gap at exactly that position; the gap-span variant also credits rows
whose gap spans include the boundary position.
"""

from __future__ import annotations

import statistics
from typing import Any

from ..models import BoundaryHypothesis, BoundaryPoint, TableContext


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _collect_gap_candidates(
    data_word_rows: list[list[tuple]],
    min_gap: float,
) -> list[tuple[float, int]]:
    """Collect gap midpoint candidates from all rows.

    For each row, computes inter-word gaps (word[i+1].x0 - word[i].x1),
    filters out gaps smaller than *min_gap*, and records the midpoint of
    each surviving gap together with the row index.

    Returns:
        List of ``(x_midpoint, row_index)`` pairs.
    """
    candidates: list[tuple[float, int]] = []
    for row_idx, row in enumerate(data_word_rows):
        if len(row) < 2:
            continue
        for i in range(len(row) - 1):
            gap = row[i + 1][0] - row[i][2]
            if gap >= min_gap:
                midpoint = (row[i][2] + row[i + 1][0]) / 2
                candidates.append((midpoint, row_idx))
    return candidates


def _cluster_candidates(
    candidates: list[tuple[float, int]],
    tolerance: float,
) -> list[dict[str, Any]]:
    """Cluster gap candidates by x-position.

    Candidates whose x-positions are within *tolerance* of each other are
    grouped together.  For each cluster, the representative position is the
    median of its member x-positions.

    Returns:
        List of dicts, each with keys:
          - ``position``: median x of the cluster
          - ``row_indices``: set of contributing row indices
          - ``candidate_count``: number of candidates in the cluster
    """
    if not candidates:
        return []

    sorted_candidates = sorted(candidates, key=lambda c: c[0])

    clusters: list[dict[str, Any]] = []
    current_xs: list[float] = [sorted_candidates[0][0]]
    current_rows: set[int] = {sorted_candidates[0][1]}

    for x, row_idx in sorted_candidates[1:]:
        if x - statistics.median(current_xs) <= tolerance:
            current_xs.append(x)
            current_rows.add(row_idx)
        else:
            clusters.append({
                "position": statistics.median(current_xs),
                "row_indices": current_rows,
                "candidate_count": len(current_xs),
            })
            current_xs = [x]
            current_rows = {row_idx}

    clusters.append({
        "position": statistics.median(current_xs),
        "row_indices": current_rows,
        "candidate_count": len(current_xs),
    })

    return clusters


def _compute_gap_spans(
    data_word_rows: list[list[tuple]],
    min_gap: float,
) -> list[tuple[float, float, int]]:
    """Compute gap spans (left edge, right edge) for each qualifying gap.

    Returns:
        List of ``(gap_left, gap_right, row_index)`` triples.
    """
    spans: list[tuple[float, float, int]] = []
    for row_idx, row in enumerate(data_word_rows):
        if len(row) < 2:
            continue
        for i in range(len(row) - 1):
            gap_left = row[i][2]
            gap_right = row[i + 1][0]
            if gap_right - gap_left >= min_gap:
                spans.append((gap_left, gap_right, row_idx))
    return spans


def _credit_span_support(
    clusters: list[dict[str, Any]],
    gap_spans: list[tuple[float, float, int]],
) -> None:
    """Mutate *clusters* to add span-credited row indices.

    For each gap span, every cluster whose position falls within the span's
    x-range has the span's row index added to its ``row_indices`` set.
    """
    for gap_left, gap_right, row_idx in gap_spans:
        for cluster in clusters:
            if gap_left <= cluster["position"] <= gap_right:
                cluster["row_indices"].add(row_idx)


def _median_word_width(data_word_rows: list[list[tuple]]) -> float:
    """Compute median word width from all words in data rows."""
    widths = [w[2] - w[0] for row in data_word_rows for w in row if (w[2] - w[0]) > 0]
    if not widths:
        return 10.0
    return statistics.median(widths)


def _prune_low_support(
    clusters: list[dict[str, Any]],
    num_data_rows: int,
) -> tuple[tuple[BoundaryPoint, ...], dict[str, Any]]:
    """Apply two-tier threshold and build BoundaryPoints.

    Tier 1: accept clusters with support >= 2.
    Tier 2: among survivors, prune clusters with support < median_support * 0.3.

    Returns:
        Tuple of (boundary_points, metadata_dict).
    """
    # Tier 1: initial floor
    surviving = [c for c in clusters if len(c["row_indices"]) >= 2]

    if not surviving:
        return (), {"pruned_all": True}

    # Tier 2: prune by median support
    supports = [len(c["row_indices"]) for c in surviving]
    median_support = statistics.median(supports)
    threshold = median_support * 0.3
    final = [c for c in surviving if len(c["row_indices"]) >= threshold]

    if not final:
        return (), {"pruned_all": True, "median_support": median_support}

    # Build BoundaryPoints
    boundary_points: list[BoundaryPoint] = []
    for c in sorted(final, key=lambda c: c["position"]):
        support = len(c["row_indices"])
        confidence = support / num_data_rows if num_data_rows > 0 else 0.0
        boundary_points.append(BoundaryPoint(
            min_pos=c["position"],
            max_pos=c["position"],
            confidence=confidence,
            provenance="hotspot",
        ))

    metadata = {
        "cluster_count": len(final),
        "median_support": median_support,
        "supports": [len(c["row_indices"]) for c in final],
    }

    return tuple(boundary_points), metadata


# ---------------------------------------------------------------------------
# StructureMethod implementations
# ---------------------------------------------------------------------------

class SinglePointHotspot:
    """Column boundary detection via single-point gap hotspots.

    Counts only rows with a gap at exactly the cluster's x-position.
    """

    @property
    def name(self) -> str:
        return "single_point_hotspot"

    def detect(self, ctx: TableContext) -> BoundaryHypothesis | None:
        rows = ctx.data_word_rows
        if not rows:
            return None

        all_words = [w for row in rows for w in row]
        if not all_words:
            return None

        min_gap = ctx.median_word_height * 0.25
        tolerance = _median_word_width(rows)

        candidates = _collect_gap_candidates(rows, min_gap)
        if not candidates:
            return BoundaryHypothesis(
                col_boundaries=(),
                row_boundaries=(),
                method=self.name,
                metadata={"reason": "no_gaps_found"},
            )

        clusters = _cluster_candidates(candidates, tolerance)
        boundary_points, metadata = _prune_low_support(clusters, len(rows))

        return BoundaryHypothesis(
            col_boundaries=boundary_points,
            row_boundaries=(),
            method=self.name,
            metadata=metadata,
        )


class GapSpanHotspot:
    """Column boundary detection via gap-span hotspots.

    Like single-point, but additionally credits boundaries that fall within
    a row's gap span even if the gap midpoint is not at the boundary position.
    """

    @property
    def name(self) -> str:
        return "gap_span_hotspot"

    def detect(self, ctx: TableContext) -> BoundaryHypothesis | None:
        rows = ctx.data_word_rows
        if not rows:
            return None

        all_words = [w for row in rows for w in row]
        if not all_words:
            return None

        min_gap = ctx.median_word_height * 0.25
        tolerance = _median_word_width(rows)

        # Pass 1: same as single-point
        candidates = _collect_gap_candidates(rows, min_gap)
        if not candidates:
            return BoundaryHypothesis(
                col_boundaries=(),
                row_boundaries=(),
                method=self.name,
                metadata={"reason": "no_gaps_found"},
            )

        clusters = _cluster_candidates(candidates, tolerance)

        # Pass 2: credit span support
        gap_spans = _compute_gap_spans(rows, min_gap)
        _credit_span_support(clusters, gap_spans)

        boundary_points, metadata = _prune_low_support(clusters, len(rows))

        return BoundaryHypothesis(
            col_boundaries=boundary_points,
            row_boundaries=(),
            method=self.name,
            metadata=metadata,
        )
