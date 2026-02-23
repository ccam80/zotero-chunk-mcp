"""Quality scoring framework for cell grids.

Rank-based quality scoring: each grid is ranked across multiple metrics,
ranks are summed, and the grid with the lowest total rank wins.  No absolute
weights to calibrate.
"""

from __future__ import annotations

import re
import statistics
from typing import Callable

from .models import CellGrid, TableContext

# Greek/math character pattern -- cells with these are excluded from garbled
# text detection even if they have long tokens.
_MATH_GREEK_RE = re.compile(
    r"[\u0370-\u03FF\u2200-\u22FF\u2A00-\u2AFF\u00B1\u00D7\u00F7\u2260-\u226F]"
)

# Decimal displacement pattern: leading dot followed by digits (no leading zero).
_DECIMAL_DISPLACEMENT_RE = re.compile(r"^\.\d+")


# ---------------------------------------------------------------------------
# Individual metrics
# ---------------------------------------------------------------------------

def fill_rate(grid: CellGrid) -> float:
    """Fraction of non-empty cells.  Empty = empty string or whitespace-only.

    Range 0.0--1.0.  Returns 1.0 for grids with no cells (vacuous truth).
    """
    all_cells: list[str] = list(grid.headers)
    for row in grid.rows:
        all_cells.extend(row)

    if not all_cells:
        return 1.0

    non_empty = sum(1 for c in all_cells if c.strip())
    return non_empty / len(all_cells)


def decimal_displacement_count(grid: CellGrid) -> int:
    """Count of cells matching ``^\\.\\d+`` (leading dot without zero).

    Higher count = worse extraction quality (decimal displacement bug).
    """
    count = 0
    all_cells: list[str] = list(grid.headers)
    for row in grid.rows:
        all_cells.extend(row)

    for cell in all_cells:
        if _DECIMAL_DISPLACEMENT_RE.match(cell.strip()):
            count += 1
    return count


def garbled_text_score(grid: CellGrid) -> float:
    """Fraction of cells that are garbled (avg word length > 25).

    Cells containing Greek/math characters are excluded from the check.
    Range 0.0--1.0.  Higher = more garbled = worse.
    Returns 0.0 if no cells to check.
    """
    all_cells: list[str] = list(grid.headers)
    for row in grid.rows:
        all_cells.extend(row)

    if not all_cells:
        return 0.0

    garbled_count = 0
    checkable_count = 0

    for cell in all_cells:
        text = cell.strip()
        if not text:
            continue

        # Skip cells with Greek/math characters
        if _MATH_GREEK_RE.search(text):
            continue

        checkable_count += 1
        words = text.split()
        if not words:
            continue

        avg_word_len = sum(len(w) for w in words) / len(words)
        if avg_word_len > 25:
            garbled_count += 1

    if checkable_count == 0:
        return 0.0

    return garbled_count / checkable_count


def numeric_coherence(grid: CellGrid) -> float:
    """Coherence of predominantly numeric columns.

    For columns where >50% of data cells parse as numbers, check consistency:
    a coherent column is all-numeric or all-text, not mixed.

    Score = fraction of predominantly-numeric columns that are coherent.
    Range 0.0--1.0.  Higher = better.
    Returns 1.0 if no predominantly-numeric columns exist (vacuous truth).
    """
    if not grid.rows:
        return 1.0

    num_cols = len(grid.headers) if grid.headers else (len(grid.rows[0]) if grid.rows else 0)
    if num_cols == 0:
        return 1.0

    predominantly_numeric_cols = 0
    coherent_cols = 0

    for col_idx in range(num_cols):
        col_values: list[str] = []
        for row in grid.rows:
            if col_idx < len(row):
                val = row[col_idx].strip()
                if val:
                    col_values.append(val)

        if not col_values:
            continue

        numeric_count = sum(1 for v in col_values if _is_numeric(v))
        numeric_fraction = numeric_count / len(col_values)

        if numeric_fraction > 0.5:
            predominantly_numeric_cols += 1
            # Coherent if all numeric or all text (not mixed)
            if numeric_count == len(col_values) or numeric_count == 0:
                coherent_cols += 1

    if predominantly_numeric_cols == 0:
        return 1.0

    return coherent_cols / predominantly_numeric_cols


def _is_numeric(text: str) -> bool:
    """Check if text represents a number (int, float, negative, percentage, scientific)."""
    cleaned = text.strip().rstrip("%")
    if not cleaned:
        return False
    try:
        float(cleaned)
        return True
    except ValueError:
        pass
    # Try scientific notation variants
    cleaned = cleaned.replace("×10", "e").replace("\u00d710", "e")
    try:
        float(cleaned)
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Ranking utilities
# ---------------------------------------------------------------------------

def _rank_values(values: list[float], higher_is_better: bool) -> list[float]:
    """Assign ordinal ranks to values.  Ties get averaged rank.

    Parameters
    ----------
    values:
        Raw metric values, one per grid.
    higher_is_better:
        If True, highest value gets rank 1.  If False, lowest gets rank 1.

    Returns
    -------
    list[float]
        Ranks (1-based), same order as input.
    """
    n = len(values)
    if n == 0:
        return []

    # Create (value, original_index) pairs
    indexed = list(enumerate(values))

    # Sort: for higher_is_better, sort descending; otherwise ascending
    if higher_is_better:
        indexed.sort(key=lambda x: x[1], reverse=True)
    else:
        indexed.sort(key=lambda x: x[1])

    # Assign ranks with tie averaging
    ranks = [0.0] * n
    i = 0
    while i < n:
        # Find group of ties
        j = i + 1
        while j < n and indexed[j][1] == indexed[i][1]:
            j += 1

        # Average rank for this tie group
        avg_rank = sum(range(i + 1, j + 1)) / (j - i)
        for k in range(i, j):
            orig_idx = indexed[k][0]
            ranks[orig_idx] = avg_rank

        i = j

    return ranks


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def rank_and_select(
    grids: list[CellGrid],
    ctx: TableContext,
    ground_truth_fn: Callable | None = None,
) -> tuple[CellGrid | None, dict[str, float]]:
    """Score and rank cell grids, returning the best one.

    Parameters
    ----------
    grids:
        Zero or more cell grids from different extraction methods.
    ctx:
        Table context (used for adaptive scoring thresholds).
    ground_truth_fn:
        Optional function ``(headers, rows) -> float`` returning cell accuracy
        (0.0--1.0).  When provided, cell accuracy becomes an additional
        ranking metric (higher = better).

    Returns
    -------
    tuple[CellGrid | None, dict[str, float]]
        ``(winning_grid, scores_dict)`` where ``scores_dict`` maps
        ``grid.method`` to the grid's rank sum (lower = better).
        Returns ``(None, {})`` if *grids* is empty.
    """
    if not grids:
        return None, {}

    if len(grids) == 1:
        key = f"{grids[0].structure_method}:{grids[0].method}"
        return grids[0], {key: 0.0}

    # Compute metrics for each grid
    fill_rates = [fill_rate(g) for g in grids]
    displacement_counts = [decimal_displacement_count(g) for g in grids]
    garbled_scores = [garbled_text_score(g) for g in grids]
    coherence_scores = [numeric_coherence(g) for g in grids]

    # Rank each metric
    fill_ranks = _rank_values(fill_rates, higher_is_better=True)
    displacement_ranks = _rank_values(
        [float(c) for c in displacement_counts], higher_is_better=False
    )
    garbled_ranks = _rank_values(garbled_scores, higher_is_better=False)
    coherence_ranks = _rank_values(coherence_scores, higher_is_better=True)

    # Sum ranks per grid
    rank_sums = [
        fill_ranks[i] + displacement_ranks[i] + garbled_ranks[i] + coherence_ranks[i]
        for i in range(len(grids))
    ]

    # Ground truth mode: add cell accuracy as an additional ranking metric
    if ground_truth_fn is not None:
        gt_scores = [ground_truth_fn(g.headers, g.rows) for g in grids]
        gt_ranks = _rank_values(gt_scores, higher_is_better=True)
        for i in range(len(grids)):
            rank_sums[i] += gt_ranks[i]

    # Build scores_dict with composite keys to avoid collisions
    scores_dict: dict[str, float] = {}
    for i, grid in enumerate(grids):
        key = f"{grid.structure_method}:{grid.method}"
        scores_dict[key] = rank_sums[i]

    # Select winner (lowest rank sum)
    best_idx = min(range(len(grids)), key=lambda i: rank_sums[i])

    return grids[best_idx], scores_dict
