"""Row clustering utility — shared by all structure methods.

Provides adaptive tolerance computation and word-to-row clustering based
on actual word geometry from the PDF page.
"""
from __future__ import annotations

_ASSUMED_WORD_HEIGHT = 12.0  # typical body-text height in pts


def adaptive_row_tolerance(words: list[tuple]) -> float:
    """Compute row-clustering tolerance from the y-gap distribution.

    Sorts word y-midpoints, computes consecutive gaps, and finds the
    natural break between intra-row gaps (small) and inter-row gaps
    (large) using a ratio-break method.  Falls back to median word
    height * 0.3 when the gap distribution lacks a clear break.

    Args:
        words: List of word tuples from page.get_text("words").
            Each tuple has at least (x0, y0, x1, y1, ...).

    Returns:
        A positive float tolerance value for row clustering.
    """
    if not words:
        return _ASSUMED_WORD_HEIGHT * 0.3

    heights = [w[3] - w[1] for w in words if (w[3] - w[1]) > 0]
    if not heights:
        return _ASSUMED_WORD_HEIGHT * 0.3

    heights.sort()
    median_h = heights[len(heights) // 2]

    # Compute y-gaps between consecutive unique word midpoints
    y_mids = sorted(set(round((w[1] + w[3]) / 2, 1) for w in words))
    if len(y_mids) < 3:
        return median_h * 0.3

    gaps = sorted(
        y_mids[i + 1] - y_mids[i]
        for i in range(len(y_mids) - 1)
        if y_mids[i + 1] - y_mids[i] > 0
    )
    if len(gaps) < 2:
        return median_h * 0.3

    # Ratio-break: first gap pair where the jump exceeds 2x
    for i in range(len(gaps) - 1):
        if gaps[i] > 0 and gaps[i + 1] / gaps[i] > 2.0:
            return gaps[i]

    # No clear break — fall back to word-height-based
    return median_h * 0.3


def cluster_words_into_rows(
    words: list[tuple],
    *,
    tolerance: float | None = None,
) -> list[list[tuple]]:
    """Cluster words into rows by y-midpoint proximity.

    Args:
        words: List of word tuples from page.get_text("words").
            Each tuple has at least (x0, y0, x1, y1, ...).
        tolerance: Maximum y-midpoint distance for two words to be in the
            same row. If None, computed via adaptive_row_tolerance().

    Returns:
        List of rows, each row a list of word tuples sorted by x-position
        (left to right). Rows sorted by y-position (top to bottom).
    """
    if not words:
        return []

    if tolerance is None:
        tolerance = adaptive_row_tolerance(words)

    # Sort words by y-midpoint for clustering
    sorted_words = sorted(words, key=lambda w: (w[1] + w[3]) / 2)

    rows: list[list[tuple]] = []
    current_row: list[tuple] = [sorted_words[0]]
    current_y = (sorted_words[0][1] + sorted_words[0][3]) / 2

    for w in sorted_words[1:]:
        y_mid = (w[1] + w[3]) / 2
        if abs(y_mid - current_y) <= tolerance:
            current_row.append(w)
        else:
            rows.append(current_row)
            current_row = [w]
            current_y = y_mid
    rows.append(current_row)

    # Sort words within each row by x-position (left to right)
    for row in rows:
        row.sort(key=lambda w: w[0])

    # Rows are already sorted by y-position due to initial sort
    return rows
