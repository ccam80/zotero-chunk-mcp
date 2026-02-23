"""Ruled line detection structure method.

Uses ``page.get_drawings()`` to find horizontal and vertical lines within the
table bbox.  Lines are clipped to the bbox and converted to row/column
boundary positions.  Confidence is ``clipped_length / table_dimension``.
"""

from __future__ import annotations

import math
import statistics
from typing import Sequence

from ..models import BoundaryHypothesis, BoundaryPoint, TableContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_lines(
    drawings: list[dict],
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """Extract (start_point, end_point) line segments from drawing items.

    Each drawing dict contains an ``items`` list.  Line items are tuples of
    the form ``("l", Point, Point)``.
    """
    lines: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for d in drawings:
        for item in d.get("items", []):
            if len(item) >= 3 and item[0] == "l":
                p1 = item[1]
                p2 = item[2]
                lines.append(((p1.x, p1.y), (p2.x, p2.y)))
    return lines


def _classify_line(
    p1: tuple[float, float], p2: tuple[float, float],
) -> str | None:
    """Classify a line as 'horizontal', 'vertical', or None (diagonal).

    A line within 5 degrees of horizontal or vertical is classified accordingly.
    Diagonal lines return None.
    """
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    length = math.hypot(dx, dy)
    if length < 1e-9:
        return None

    angle_rad = math.atan2(abs(dy), abs(dx))
    angle_deg = math.degrees(angle_rad)

    if angle_deg < 5.0:
        return "horizontal"
    if angle_deg > 85.0:
        return "vertical"
    return None


def _clip_to_bbox(
    p1: tuple[float, float],
    p2: tuple[float, float],
    bbox: tuple[float, float, float, float],
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Clip a line segment to the bbox.

    Truncates endpoints to bbox edges.  For horizontal lines, x is clipped
    to [x0, x1].  For vertical lines, y is clipped to [y0, y1].
    """
    bx0, by0, bx1, by1 = bbox

    x1_c = max(bx0, min(bx1, p1[0]))
    y1_c = max(by0, min(by1, p1[1]))
    x2_c = max(bx0, min(bx1, p2[0]))
    y2_c = max(by0, min(by1, p2[1]))

    return ((x1_c, y1_c), (x2_c, y2_c))


def _cluster_boundaries(
    boundaries: list[tuple[float, float]],
    tolerance: float,
) -> list[tuple[float, float]]:
    """Cluster nearby boundary (position, confidence) pairs.

    Boundaries within ``tolerance`` of each other are merged.
    The merged position is a confidence-weighted average.
    The merged confidence is the maximum of the cluster.
    """
    if not boundaries:
        return []

    sorted_bounds = sorted(boundaries, key=lambda b: b[0])
    clusters: list[tuple[float, float]] = []

    cluster_positions: list[float] = [sorted_bounds[0][0]]
    cluster_confidences: list[float] = [sorted_bounds[0][1]]

    for pos, conf in sorted_bounds[1:]:
        if pos - cluster_positions[-1] <= tolerance:
            cluster_positions.append(pos)
            cluster_confidences.append(conf)
        else:
            # Finalize current cluster
            total_conf = sum(cluster_confidences)
            if total_conf > 0:
                weighted_pos = sum(
                    p * c for p, c in zip(cluster_positions, cluster_confidences)
                ) / total_conf
            else:
                weighted_pos = statistics.mean(cluster_positions)
            clusters.append((weighted_pos, max(cluster_confidences)))

            cluster_positions = [pos]
            cluster_confidences = [conf]

    # Finalize last cluster
    total_conf = sum(cluster_confidences)
    if total_conf > 0:
        weighted_pos = sum(
            p * c for p, c in zip(cluster_positions, cluster_confidences)
        ) / total_conf
    else:
        weighted_pos = statistics.mean(cluster_positions)
    clusters.append((weighted_pos, max(cluster_confidences)))

    return clusters


# ---------------------------------------------------------------------------
# StructureMethod implementation
# ---------------------------------------------------------------------------

class RuledLineDetection:
    """Detects table structure from ruled (drawn) horizontal/vertical lines."""

    @property
    def name(self) -> str:
        return "ruled_lines"

    def detect(self, ctx: TableContext) -> BoundaryHypothesis | None:
        """Detect boundaries from ruled lines within the table bbox."""
        raw_lines = _extract_lines(ctx.drawings)
        if not raw_lines:
            return None

        x0, y0, x1, y1 = ctx.bbox
        bbox_width = x1 - x0
        bbox_height = y1 - y0

        if bbox_width < 1e-9 or bbox_height < 1e-9:
            return None

        h_boundaries: list[tuple[float, float]] = []  # (y_pos, confidence)
        v_boundaries: list[tuple[float, float]] = []  # (x_pos, confidence)

        for p1, p2 in raw_lines:
            classification = _classify_line(p1, p2)
            if classification is None:
                continue

            clipped_p1, clipped_p2 = _clip_to_bbox(p1, p2, ctx.bbox)
            clipped_length = math.hypot(
                clipped_p2[0] - clipped_p1[0],
                clipped_p2[1] - clipped_p1[1],
            )

            if clipped_length < 1e-9:
                continue

            if classification == "horizontal":
                y_mid = (clipped_p1[1] + clipped_p2[1]) / 2.0
                confidence = clipped_length / bbox_width
                h_boundaries.append((y_mid, confidence))
            else:
                x_mid = (clipped_p1[0] + clipped_p2[0]) / 2.0
                confidence = clipped_length / bbox_height
                v_boundaries.append((x_mid, confidence))

        if not h_boundaries and not v_boundaries:
            return None

        # Cluster nearby boundaries
        tolerance = ctx.median_word_height * 0.5 if ctx.median_word_height > 0 else 1.0

        h_clustered = _cluster_boundaries(h_boundaries, tolerance)
        v_clustered = _cluster_boundaries(v_boundaries, tolerance)

        row_points = tuple(
            BoundaryPoint(
                min_pos=pos, max_pos=pos, confidence=conf, provenance=self.name,
            )
            for pos, conf in h_clustered
        )
        col_points = tuple(
            BoundaryPoint(
                min_pos=pos, max_pos=pos, confidence=conf, provenance=self.name,
            )
            for pos, conf in v_clustered
        )

        return BoundaryHypothesis(
            col_boundaries=col_points,
            row_boundaries=row_points,
            method=self.name,
            metadata={
                "raw_h_lines": len(h_boundaries),
                "raw_v_lines": len(v_boundaries),
                "clustered_h": len(h_clustered),
                "clustered_v": len(v_clustered),
            },
        )
