"""Post-processor: strip footnote rows from the bottom of a table.

Uses a two-signal rule (require 2+ of 3 signals) to avoid false positives.
All thresholds are adaptive, derived from the table's own cell-length
distribution.
"""
from __future__ import annotations

import re

from ..models import CellGrid, TableContext

# Footnote indicator patterns (anchored to start of cell text)
_FOOTNOTE_NOTE_RE = re.compile(r"^Notes?[\s.:]", re.IGNORECASE)
_FOOTNOTE_SOURCE_RE = re.compile(r"^Sources?[\s.:]", re.IGNORECASE)
_FOOTNOTE_MARKER_RE = re.compile(r"^[*\u2020\u2021\u00a7\u2016a-d]\s")


def _compute_length_threshold(all_lengths: list[int]) -> float:
    """Compute adaptive IQR-based outlier threshold for cell text lengths.

    Returns ``max(Q3 + 1.5 * IQR, 3 * median)`` so that tables with
    uniform cell lengths don't trigger over-sensitively.
    """
    all_lengths.sort()
    n = len(all_lengths)
    if n == 0:
        return float("inf")
    median_len = all_lengths[n // 2]
    q1 = all_lengths[n // 4]
    q3 = all_lengths[3 * n // 4]
    iqr = q3 - q1
    return max(q3 + 1.5 * iqr, median_len * 3)


def _is_footnote_row(
    row: tuple[str, ...],
    long_cell_threshold: float,
) -> tuple[bool, int]:
    """Check if *row* is a footnote row using the two-signal rule.

    Returns ``(is_footnote, signal_count)``.

    Signals:
    1. Text starts with a footnote pattern (Note, Source, dagger, etc.).
    2. Row has only 1 non-empty cell (spanning all columns).
    3. Longest cell exceeds the adaptive IQR threshold.
    """
    non_empty = [(j, c.strip()) for j, c in enumerate(row) if c.strip()]
    if not non_empty:
        return False, 0

    signals = 0

    # Signal 1: footnote pattern in first non-empty cell
    first_text = non_empty[0][1]
    if (
        _FOOTNOTE_NOTE_RE.match(first_text)
        or _FOOTNOTE_SOURCE_RE.match(first_text)
        or _FOOTNOTE_MARKER_RE.match(first_text)
    ):
        signals += 1

    # Signal 2: single non-empty cell (spanning row)
    if len(non_empty) == 1:
        signals += 1

    # Signal 3: cell text is an IQR outlier
    max_cell_len = max(len(c) for _, c in non_empty)
    if max_cell_len > long_cell_threshold:
        signals += 1

    return signals >= 2, signals


class FootnoteStrip:
    """Strip footnote rows from the bottom of the table using a two-signal rule."""

    @property
    def name(self) -> str:
        return "footnote_strip"

    def process(self, grid: CellGrid, ctx: TableContext) -> CellGrid:
        try:
            return self._process(grid, ctx)
        except Exception:
            return grid

    def _process(self, grid: CellGrid, ctx: TableContext) -> CellGrid:
        if not grid.rows:
            return grid

        # Collect all cell lengths for adaptive threshold
        all_lengths: list[int] = []
        for row in grid.rows:
            for c in row:
                stripped = c.strip()
                if stripped:
                    all_lengths.append(len(stripped))
        for h in grid.headers:
            stripped = h.strip()
            if stripped:
                all_lengths.append(len(stripped))

        if not all_lengths:
            return grid

        threshold = _compute_length_threshold(list(all_lengths))

        # Scan from bottom
        cut_idx = len(grid.rows)
        footnote_texts: list[str] = []

        for i in range(len(grid.rows) - 1, -1, -1):
            row = grid.rows[i]
            non_empty = [c.strip() for c in row if c.strip()]
            if not non_empty:
                continue  # skip empty rows

            is_fn, _ = _is_footnote_row(row, threshold)
            if is_fn:
                footnote_texts.append(" ".join(non_empty))
                cut_idx = i
            else:
                break  # stop at first non-footnote row

        if cut_idx >= len(grid.rows):
            return grid  # No footnotes found

        footnote_texts.reverse()  # restore top-to-bottom order

        return CellGrid(
            headers=grid.headers,
            rows=grid.rows[:cut_idx],
            col_boundaries=grid.col_boundaries,
            row_boundaries=grid.row_boundaries,
            method=grid.method,
        )
