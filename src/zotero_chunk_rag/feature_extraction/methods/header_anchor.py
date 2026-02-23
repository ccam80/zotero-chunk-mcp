"""Header anchor structure method.

Detects the header row(s) and proposes column boundaries from those rows
only, with high confidence.  Headers are identified as the topmost row with
the most inter-word gaps (indicating the most column separations).
"""

from __future__ import annotations

import statistics

from ..models import BoundaryHypothesis, BoundaryPoint, TableContext


def _median_word_width(data_word_rows: list[list[tuple]]) -> float:
    """Compute median word width from all words in data rows."""
    widths = [w[2] - w[0] for row in data_word_rows for w in row if (w[2] - w[0]) > 0]
    if not widths:
        return 10.0
    return statistics.median(widths)


def _row_gaps(row: list[tuple], min_gap: float) -> list[tuple[float, float, float]]:
    """Compute inter-word gaps for a row.

    Returns:
        List of ``(gap_midpoint, gap_left, gap_right)`` for gaps >= min_gap.
    """
    result: list[tuple[float, float, float]] = []
    for i in range(len(row) - 1):
        gap_left = row[i][2]
        gap_right = row[i + 1][0]
        gap_size = gap_right - gap_left
        if gap_size >= min_gap:
            result.append(((gap_left + gap_right) / 2, gap_left, gap_right))
    return result


def _gaps_match(
    gaps_a: list[tuple[float, float, float]],
    gaps_b: list[tuple[float, float, float]],
    tolerance: float,
) -> bool:
    """Check if two rows have similar gap structure.

    Similar means: same count (+/-1) and gap midpoints within tolerance.
    """
    if abs(len(gaps_a) - len(gaps_b)) > 1:
        return False

    # Match gaps by closest midpoint
    matched = 0
    used_b = set()
    for ga in gaps_a:
        for j, gb in enumerate(gaps_b):
            if j in used_b:
                continue
            if abs(ga[0] - gb[0]) <= tolerance:
                matched += 1
                used_b.add(j)
                break

    # At least half of the larger set must match
    max_gaps = max(len(gaps_a), len(gaps_b))
    return matched >= max_gaps / 2


class HeaderAnchor:
    """Column boundary detection anchored to the header row.

    Identifies the header row as the topmost row with the most inter-word
    gaps, then uses that row's gap positions as high-confidence column
    boundary proposals.
    """

    @property
    def name(self) -> str:
        return "header_anchor"

    def detect(self, ctx: TableContext) -> BoundaryHypothesis | None:
        rows = ctx.data_word_rows
        if not rows:
            return None

        min_gap = ctx.median_word_height * 0.25
        tolerance = _median_word_width(rows)

        # Find row with most gaps (topmost on tie)
        best_row_idx = -1
        best_gap_count = -1
        row_gaps_cache: dict[int, list[tuple[float, float, float]]] = {}

        for idx, row in enumerate(rows):
            if len(row) < 2:
                row_gaps_cache[idx] = []
                continue
            gaps = _row_gaps(row, min_gap)
            row_gaps_cache[idx] = gaps
            if len(gaps) > best_gap_count:
                best_gap_count = len(gaps)
                best_row_idx = idx

        if best_gap_count < 2:
            return None

        header_gaps = row_gaps_cache[best_row_idx]

        # Check for multi-row header: does the row below have similar structure?
        multi_row = False
        next_row_idx = best_row_idx + 1
        if next_row_idx < len(rows):
            next_gaps = row_gaps_cache.get(next_row_idx)
            if next_gaps is None:
                next_gaps = _row_gaps(rows[next_row_idx], min_gap)
            if _gaps_match(header_gaps, next_gaps, tolerance):
                multi_row = True

        # Build boundary points
        base_confidence = 0.95 if multi_row else 0.9
        boundary_points: list[BoundaryPoint] = []
        for midpoint, _, _ in sorted(header_gaps, key=lambda g: g[0]):
            boundary_points.append(BoundaryPoint(
                min_pos=midpoint,
                max_pos=midpoint,
                confidence=base_confidence,
                provenance="header_anchor",
            ))

        return BoundaryHypothesis(
            col_boundaries=tuple(boundary_points),
            row_boundaries=(),
            method=self.name,
            metadata={
                "header_row_index": best_row_idx,
                "multi_row_header": multi_row,
                "gap_count": best_gap_count,
            },
        )
