"""
Isolated test of iterative column boundary detection.

Loads specific problem tables from the Zotero library and tests the
new column detection algorithm against known expected column counts.

Usage:
    .venv/Scripts/python.exe tests/test_column_detection_isolated.py
"""
from __future__ import annotations

import sys
from collections import Counter
from itertools import groupby
from pathlib import Path
from statistics import median

# Force UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import pymupdf

# ---------------------------------------------------------------------------
# Row clustering (unchanged from previous version)
# ---------------------------------------------------------------------------


def adaptive_row_tolerance(words: list) -> float:
    """Compute row-clustering tolerance from y-gap distribution."""
    _ASSUMED = 12.0
    if not words:
        return _ASSUMED * 0.3
    heights = [w[3] - w[1] for w in words if (w[3] - w[1]) > 0]
    if not heights:
        return _ASSUMED * 0.3
    heights.sort()
    median_h = heights[len(heights) // 2]

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

    for i in range(len(gaps) - 1):
        if gaps[i] > 0 and gaps[i + 1] / gaps[i] > 2.0:
            return gaps[i]

    return median_h * 0.3


def cluster_words_into_rows(words: list, bbox: tuple) -> list[list]:
    """Cluster words into rows by y-position, return list of rows sorted by x."""
    clip = pymupdf.Rect(bbox)
    clipped = [w for w in words if clip.intersects(pymupdf.Rect(w[:4]))]
    if len(clipped) < 2:
        return [clipped] if clipped else []

    clipped.sort(key=lambda w: (w[1], w[0]))
    row_tol = adaptive_row_tolerance(clipped)

    rows: list[list] = []
    current = [clipped[0]]
    for w in clipped[1:]:
        if w[1] - current[-1][1] > row_tol:
            rows.append(sorted(current, key=lambda w: w[0]))
            current = [w]
        else:
            current.append(w)
    rows.append(sorted(current, key=lambda w: w[0]))
    return rows


# ---------------------------------------------------------------------------
# Caption word gap (unchanged)
# ---------------------------------------------------------------------------


def compute_caption_word_gap(page: pymupdf.Page, bbox: tuple, caption_text: str) -> float:
    """Compute median word gap from caption text on the page.

    Searches the full page for the caption row, measures inter-word gaps.
    Falls back to page body text outside the table bbox.
    """
    all_page_words = page.get_text("words")
    if not all_page_words:
        return 3.0

    caption_words_list = caption_text.split()
    if len(caption_words_list) < 3:
        return _body_text_word_gap(all_page_words, bbox)

    all_page_words.sort(key=lambda w: (w[1], w[0]))
    row_tol = adaptive_row_tolerance(all_page_words) if len(all_page_words) >= 3 else 8.0
    rows: list[list] = []
    current = [all_page_words[0]]
    for w in all_page_words[1:]:
        if w[1] - current[-1][1] > row_tol:
            rows.append(sorted(current, key=lambda w: w[0]))
            current = [w]
        else:
            current.append(w)
    rows.append(sorted(current, key=lambda w: w[0]))

    target = [cw.lower().rstrip(".,:-()") for cw in caption_words_list[:6]]
    best_row = None
    best_score = 0
    for row in rows:
        row_text = [w[4].lower().rstrip(".,:-()") for w in row]
        score = sum(1 for t in target if t in row_text)
        if score > best_score and len(row) >= 3:
            best_score = score
            best_row = row

    if best_row and best_score >= 2:
        gaps = []
        for i in range(1, len(best_row)):
            g = best_row[i][0] - best_row[i - 1][2]
            if g > 0.01:
                gaps.append(g)
        if gaps:
            return median(gaps)

    return _body_text_word_gap(all_page_words, bbox)


def _body_text_word_gap(all_words: list, bbox: tuple) -> float:
    """Compute median word gap from page text outside the table bbox."""
    clip = pymupdf.Rect(bbox)
    outside = [w for w in all_words if not clip.intersects(pymupdf.Rect(w[:4]))]
    if len(outside) < 5:
        heights = [w[3] - w[1] for w in all_words if (w[3] - w[1]) > 0]
        return median(heights) * 0.3 if heights else 3.0

    outside.sort(key=lambda w: (w[1], w[0]))
    row_tol = adaptive_row_tolerance(outside)
    rows: list[list] = []
    current = [outside[0]]
    for w in outside[1:]:
        if w[1] - current[-1][1] > row_tol:
            rows.append(sorted(current, key=lambda w: w[0]))
            current = [w]
        else:
            current.append(w)
    rows.append(sorted(current, key=lambda w: w[0]))

    gaps = []
    for row in rows:
        for i in range(1, len(row)):
            g = row[i][0] - row[i - 1][2]
            if g > 0.01:
                gaps.append(g)
    return median(gaps) if gaps else 3.0


# ---------------------------------------------------------------------------
# Core: gap intervals, candidates, support matrix
# ---------------------------------------------------------------------------


def compute_row_gaps(row_words: list, bbox: tuple) -> list[tuple[float, float]]:
    """Compute gap intervals for a single row, including bbox-edge margins."""
    gaps = []
    bbox_x0, bbox_x1 = bbox[0], bbox[2]

    # Left margin
    if row_words[0][0] > bbox_x0 + 0.5:
        gaps.append((bbox_x0, row_words[0][0]))

    # Inter-word gaps
    for i in range(1, len(row_words)):
        gl = row_words[i - 1][2]
        gr = row_words[i][0]
        if gr > gl + 0.01:
            gaps.append((gl, gr))

    # Right margin
    if row_words[-1][2] < bbox_x1 - 0.5:
        gaps.append((row_words[-1][2], bbox_x1))

    return gaps


def find_candidate_boundaries(
    all_row_gaps: list[list[tuple[float, float]]],
    bbox: tuple,
    min_width: float,
) -> list[tuple[float, float]]:
    """Find column boundary candidates via local peak detection in sweep-line.

    Margins are included — single-word and continuation rows support all
    boundaries via margin gaps. The count profile has peaks at column
    boundaries (count ≈ N, all rows have gaps) and valleys at column
    interiors (count ≈ K, only wide-gap rows have gaps).

    Peak detection: find the valley level K and peak level N from interior
    segments (excluding edge transitions), then extract contiguous regions
    where count > (K + N) / 2. This adapts to the table's actual gap
    structure without a fixed threshold.
    """
    n_rows = len(all_row_gaps)
    if n_rows < 2:
        return []

    # Build sweep-line events (all gaps including margins)
    events: list[tuple[float, int]] = []
    for row_gaps in all_row_gaps:
        for gl, gr in row_gaps:
            events.append((gl, 1))
            events.append((gr, -1))

    if not events:
        return []

    events.sort(key=lambda e: (e[0], e[1]))

    # Group events at same x
    grouped: list[tuple[float, int]] = []
    for x, grp in groupby(events, key=lambda e: e[0]):
        net_delta = sum(d for _, d in grp)
        grouped.append((x, net_delta))

    # Build piecewise-constant count profile
    segments: list[tuple[float, float, int]] = []
    count = 0
    for i, (x, nd) in enumerate(grouped):
        count += nd
        if i + 1 < len(grouped):
            next_x = grouped[i + 1][0]
            if next_x > x:
                segments.append((x, next_x, count))

    if not segments:
        return []

    # Merge adjacent segments with same count
    merged: list[list] = [list(segments[0])]
    for seg in segments[1:]:
        if seg[2] == merged[-1][2]:
            merged[-1][1] = seg[1]  # extend x_end
        else:
            merged.append(list(seg))

    # Find valley (K) and peak (N) levels from interior segments.
    # Use a margin proportional to bbox width to exclude edge transitions
    # where the count ramps from 0 to the interior baseline.
    bbox_x0, bbox_x1 = bbox[0], bbox[2]
    bbox_width = bbox_x1 - bbox_x0
    interior_margin = bbox_width * 0.05
    edge_tol = 1.0  # for final candidate filtering

    interior_counts = [
        seg[2] for seg in merged
        if seg[0] >= bbox_x0 + interior_margin
        and seg[1] <= bbox_x1 - interior_margin
    ]

    if len(interior_counts) < 2:
        return []

    min_count = min(interior_counts)  # valley level K
    max_count = max(interior_counts)  # peak level N

    if min_count == max_count:
        return []  # flat profile — no column structure detectable

    # Adaptive threshold: midpoint between valley and peak levels
    threshold = (min_count + max_count) / 2

    # Extract contiguous regions above threshold as peak candidates
    peaks: list[tuple[float, float]] = []
    in_peak = False
    peak_start = 0.0

    for seg in merged:
        x0, x1, c = seg[0], seg[1], seg[2]
        if c > threshold and not in_peak:
            peak_start = x0
            in_peak = True
        elif c <= threshold and in_peak:
            peaks.append((peak_start, x0))
            in_peak = False

    if in_peak:
        peaks.append((peak_start, merged[-1][1]))

    # Filter: min width + edge exclusion
    candidates = [
        (l, r) for l, r in peaks
        if r - l >= min_width
        and l > bbox_x0 + edge_tol
        and r < bbox_x1 - edge_tol
    ]

    return candidates


def build_support_matrix(
    all_row_gaps: list[list[tuple[float, float]]],
    candidates: list[tuple[float, float]],
) -> tuple[list[list[int]], list[int], list[int]]:
    """Build binary support matrix: rows x candidates.

    matrix[i][j] = 1 if row i has a gap overlapping candidate j.
    Returns (matrix, row_sums, col_sums).
    """
    n_cands = len(candidates)

    matrix = []
    for row_gaps in all_row_gaps:
        row = []
        for cl, cr in candidates:
            supported = any(gl < cr and gr > cl for gl, gr in row_gaps)
            row.append(1 if supported else 0)
        matrix.append(row)

    row_sums = [sum(r) for r in matrix]
    col_sums = [0] * n_cands
    for i in range(len(matrix)):
        for j in range(n_cands):
            col_sums[j] += matrix[i][j]

    return matrix, row_sums, col_sums


# ---------------------------------------------------------------------------
# Trimming
# ---------------------------------------------------------------------------


def trim_caption_rows(
    rows_of_words: list[list],
    caption_text: str,
) -> list[list]:
    """Remove rows at top of table that match known caption text."""
    if not caption_text or not rows_of_words:
        return rows_of_words

    caption_words = set(
        w.lower().rstrip(".,:-()") for w in caption_text.split() if len(w) > 1
    )

    trim_count = 0
    for row in rows_of_words:
        row_words_set = set(w[4].lower().rstrip(".,:-()") for w in row)
        if not row_words_set:
            trim_count += 1
            continue
        overlap = row_words_set & caption_words
        if len(overlap) >= len(row_words_set) * 0.5:
            trim_count += 1
        else:
            break  # Stop at first non-caption row

    return rows_of_words[trim_count:]


def trim_low_sum_rows(
    rows_of_words: list[list],
    all_row_gaps: list[list[tuple[float, float]]],
    row_sums: list[int],
) -> tuple[list[list], list[list[tuple[float, float]]], int, int]:
    """Trim rows from top and bottom with low row sums.

    Finds the natural break in the row-sum distribution (largest gap
    in sorted unique sums). Rows below the break are trimmed from
    top and bottom only.

    Returns (trimmed_rows, trimmed_gaps, top_trimmed, bottom_trimmed).
    """
    if not row_sums or len(row_sums) < 3:
        return rows_of_words, all_row_gaps, 0, 0

    sorted_unique = sorted(set(row_sums))
    if len(sorted_unique) < 2:
        return rows_of_words, all_row_gaps, 0, 0

    # Find largest gap in sorted unique sums
    max_gap = 0
    gap_threshold = sorted_unique[0]
    for i in range(len(sorted_unique) - 1):
        gap = sorted_unique[i + 1] - sorted_unique[i]
        if gap > max_gap:
            max_gap = gap
            gap_threshold = sorted_unique[i]

    # Only trim if the gap is meaningful (> 1 unit)
    if max_gap <= 1:
        return rows_of_words, all_row_gaps, 0, 0

    # Trim from top while sum <= gap_threshold
    top = 0
    for i in range(len(row_sums)):
        if row_sums[i] > gap_threshold:
            top = i
            break
    else:
        return rows_of_words, all_row_gaps, 0, 0

    # Trim from bottom while sum <= gap_threshold
    bottom = len(row_sums) - 1
    for i in range(len(row_sums) - 1, -1, -1):
        if row_sums[i] > gap_threshold:
            bottom = i
            break

    return (
        rows_of_words[top:bottom + 1],
        all_row_gaps[top:bottom + 1],
        top,
        len(row_sums) - 1 - bottom,
    )


# ---------------------------------------------------------------------------
# Continuation detection
# ---------------------------------------------------------------------------


def get_populated_columns(row_words: list, boundary_mids: list[float]) -> set[int]:
    """Get set of column indices populated by words in this row."""
    populated = set()
    for w in row_words:
        word_mid_x = (w[0] + w[2]) / 2
        col = 0
        for bi, bm in enumerate(boundary_mids):
            if word_mid_x > bm:
                col = bi + 1
            else:
                break
        populated.add(col)
    return populated


def detect_continuations(
    rows_of_words: list[list],
    candidates: list[tuple[float, float]],
) -> list[bool]:
    """Detect which rows are continuations.

    A continuation row has populated columns that are a strict subset
    of the previous primary row's populated columns. Continuations
    never cross column boundaries — they wrap within a single column.

    Returns list of booleans: True = primary row, False = continuation.
    """
    if not rows_of_words or not candidates:
        return [True] * len(rows_of_words)

    boundary_mids = [(l + r) / 2 for l, r in candidates]

    is_primary = [True] * len(rows_of_words)
    prev_primary_cols: set[int] | None = None

    for i, row in enumerate(rows_of_words):
        cols = get_populated_columns(row, boundary_mids)

        if prev_primary_cols is not None and cols and cols < prev_primary_cols:
            is_primary[i] = False
        else:
            prev_primary_cols = cols

    return is_primary


# ---------------------------------------------------------------------------
# Outlier boundary detection
# ---------------------------------------------------------------------------


def drop_outlier_boundaries(
    candidates: list[tuple[float, float]],
    col_sums: list[int],
) -> list[tuple[float, float]]:
    """Drop boundaries with strictly less than max column sum.

    Known limitation: spanning header cells create real boundaries
    with column sum = max - 1. These would be incorrectly dropped.
    For now, this is accepted; spanning header detection is deferred.
    """
    if not col_sums:
        return candidates

    max_sum = max(col_sums)
    return [c for c, s in zip(candidates, col_sums) if s >= max_sum]


# ---------------------------------------------------------------------------
# Main iterative algorithm
# ---------------------------------------------------------------------------


def detect_columns_iterative(
    page: pymupdf.Page,
    bbox: tuple,
    caption_text: str,
    max_iterations: int = 5,
    verbose: bool = False,
) -> tuple[list[tuple[float, float]], dict]:
    """Iterative column boundary detection.

    1. Caption trim (deterministic, known text)
    2. Build matrix with all sweep-line candidates (low floor)
    3. Low-sum row trim (top/bottom, natural-break detection)
    4. Iterate: assign columns → detect continuations → merge →
       rebuild dense matrix → drop outlier boundaries → repeat

    Returns (boundaries, debug_info).
    """
    debug: dict = {}

    # Get words and cluster into rows
    words = page.get_text("words", clip=pymupdf.Rect(bbox))
    rows_of_words = cluster_words_into_rows(words, bbox)
    debug["initial_rows"] = len(rows_of_words)

    if len(rows_of_words) < 2:
        return [], debug

    # Caption trim
    rows_of_words = trim_caption_rows(rows_of_words, caption_text)
    debug["rows_after_caption_trim"] = len(rows_of_words)

    if len(rows_of_words) < 2:
        return [], debug

    # Compute caption word gap for min_width
    caption_gap = compute_caption_word_gap(page, bbox, caption_text)
    min_width = 2.0 * caption_gap
    debug["caption_gap"] = caption_gap
    debug["min_width"] = min_width

    # Compute row gaps (including margins for both sweep-line and matrix)
    all_row_gaps = [compute_row_gaps(row, bbox) for row in rows_of_words]

    # Find candidate boundaries via peak detection in sweep-line
    candidates = find_candidate_boundaries(all_row_gaps, bbox, min_width)
    debug["initial_candidates"] = len(candidates)

    if not candidates:
        return [], debug

    # Build initial support matrix
    matrix, row_sums, col_sums = build_support_matrix(all_row_gaps, candidates)
    debug["initial_row_sums"] = list(row_sums)
    debug["initial_col_sums"] = list(col_sums)

    if verbose:
        print(f"    Initial matrix: {len(rows_of_words)}r x {len(candidates)}c")
        print(f"    Row sums: {row_sums}")
        print(f"    Col sums: {col_sums}")

    # Low-sum row trim (top/bottom)
    rows_of_words, all_row_gaps, top_trim, bot_trim = trim_low_sum_rows(
        rows_of_words, all_row_gaps, row_sums
    )
    debug["top_trimmed"] = top_trim
    debug["bottom_trimmed"] = bot_trim
    debug["rows_after_sum_trim"] = len(rows_of_words)

    if verbose and (top_trim or bot_trim):
        print(f"    Trimmed: {top_trim} top, {bot_trim} bottom → {len(rows_of_words)} rows")

    if len(rows_of_words) < 2:
        return [], debug

    # Iterative loop
    for iteration in range(max_iterations):
        # Detect continuations
        is_primary = detect_continuations(rows_of_words, candidates)
        n_primary = sum(is_primary)
        debug[f"iter{iteration}_n_primary"] = n_primary
        debug[f"iter{iteration}_n_candidates"] = len(candidates)

        if verbose:
            n_cont = len(is_primary) - n_primary
            print(f"    Iter {iteration}: {n_primary} primary, {n_cont} continuations, {len(candidates)} candidates")

        if n_primary < 2:
            break

        # Build dense matrix (primary rows only)
        primary_gaps = [g for g, p in zip(all_row_gaps, is_primary) if p]
        dense_matrix, dense_row_sums, dense_col_sums = build_support_matrix(
            primary_gaps, candidates
        )
        debug[f"iter{iteration}_dense_col_sums"] = list(dense_col_sums)

        if verbose:
            print(f"    Dense col sums: {dense_col_sums}")

        # Drop outlier boundaries (strictly less than max)
        new_candidates = drop_outlier_boundaries(candidates, dense_col_sums)
        n_dropped = len(candidates) - len(new_candidates)
        debug[f"iter{iteration}_dropped"] = n_dropped

        if verbose and n_dropped:
            dropped = [c for c, s in zip(candidates, dense_col_sums) if s < max(dense_col_sums)]
            for c, s in zip(candidates, dense_col_sums):
                if s < max(dense_col_sums):
                    print(f"    Dropped: x=[{c[0]:.1f}, {c[1]:.1f}] support={s}/{n_primary}")

        if len(new_candidates) == len(candidates):
            break  # Converged

        candidates = new_candidates
        if not candidates:
            break

    debug["final_candidates"] = len(candidates)
    debug["final_boundaries"] = [(round(l, 1), round(r, 1)) for l, r in candidates]
    return candidates, debug


# ---------------------------------------------------------------------------
# Word-to-column assignment and fill rate (for reporting)
# ---------------------------------------------------------------------------


def assign_words_to_columns(
    rows_of_words: list[list],
    boundaries: list[tuple[float, float]],
) -> tuple[list[str], list[list[str]]]:
    """Assign words to columns, return (headers, data_rows)."""
    if not boundaries:
        result = []
        for row in rows_of_words:
            result.append([" ".join(w[4] for w in row)])
        if not result:
            return [], []
        return result[0], result[1:]

    n_cols = len(boundaries) + 1
    boundary_mids = [(l + r) / 2 for l, r in boundaries]

    all_rows: list[list[str]] = []
    for row_words in rows_of_words:
        cells = [""] * n_cols
        for w in row_words:
            word_mid_x = (w[0] + w[2]) / 2
            col = 0
            for bi, bm in enumerate(boundary_mids):
                if word_mid_x > bm:
                    col = bi + 1
                else:
                    break
            if cells[col]:
                cells[col] += " " + w[4]
            else:
                cells[col] = w[4]
        all_rows.append(cells)

    if not all_rows:
        return [], []
    return all_rows[0], all_rows[1:]


def compute_fill_rate(headers: list[str], rows: list[list[str]]) -> float:
    """Compute fill rate: fraction of non-empty cells."""
    all_cells = list(headers)
    for r in rows:
        all_cells.extend(r)
    if not all_cells:
        return 0.0
    return sum(1 for c in all_cells if c.strip()) / len(all_cells)


# ---------------------------------------------------------------------------
# Test harness
# ---------------------------------------------------------------------------

# (item_key, short_name, page_0idx, label, expected_cols, full_caption, db_bbox)
TEST_TABLES = [
    ("SCPXVBLY", "active-inference", 17, "Table 2", 4,
     "Table 2 Matrix formulation of equations used for inference.",
     [37.616, 76.646, 552.255, 713.655]),
    ("SCPXVBLY", "active-inference", 18, "Table 2 cont", 4,
     "Table 2 (continued).",
     [37.616, 55.326, 553.127, 473.353]),
    ("SCPXVBLY", "active-inference", 30, "Table 3 cont", 4,
     "Table 3 (continued).",
     [42.149, 66.117, 551.209, 248.650]),
    ("9GKLLJH9", "helm", 5, "Table 2", 6,
     "Table 2 Coefficients From Best-Fitting Cross-Lagged Panel Model (Model 6)",
     [48.000, 118.408, 288.024, 292.236]),
    ("Z9X4JVZ5", "roland", 9, "Table 2", 7,
     "Table 2. Floating-point highpass filter coefficients.",
     [104.721, 124.008, 484.687, 566.462]),
    ("Z9X4JVZ5", "roland", 15, "Table 3", 5,
     "Table 3. Poles of comb filters with quantized coefficients.",
     [128.892, 431.893, 472.622, 492.141]),
    ("AQ3D94VC", "reyes", 6, "Table 5", 9,
     "Table 5. Hypothetical Database Displaying HRV Indices Together with a Dependent Variable (DV) for 10 Subjects",
     [314.311, 92.579, 553.452, 195.679]),
    ("AQ3D94VC", "reyes", 3, "Table 2", 6,
     "Table 2. Means and Standard Deviations (in Parentheses) of HRV Parameters of Physically Active (A) and Sedentary (S) Participants",
     [313.744, 113.629, 552.879, 235.591]),
    ("DPYRZTFI", "yang", 4, "Table 2", 15,
     "Table 2 Selected methodological characteristics of included studies",
     [60.943, 119.377, 703.707, 469.898]),
    ("DPYRZTFI", "yang", 5, "Table 3", 11,
     "Table 3 Diagnostic performance of pulse pressure variation from included studies",
     [56.689, 102.281, 538.607, 535.491]),
]


def run_tests():
    """Run column detection tests against known problem tables."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    from zotero_chunk_rag.zotero_client import ZoteroClient
    from zotero_chunk_rag.config import Config

    config = Config.load()
    zotero = ZoteroClient(config.zotero_data_dir)
    all_items = zotero.get_all_items_with_pdfs()
    items_by_key = {i.item_key: i for i in all_items}

    print("=" * 80)
    print("ITERATIVE COLUMN DETECTION — ISOLATED TEST")
    print("=" * 80)

    results = []

    for item_key, short_name, page_idx, label, expected_cols, caption_text, db_bbox in TEST_TABLES:
        item = items_by_key.get(item_key)
        if not item or not item.pdf_path or not item.pdf_path.exists():
            print(f"\n[SKIP] {short_name} {label}: PDF not found")
            continue

        doc = pymupdf.open(str(item.pdf_path))
        if page_idx >= len(doc):
            print(f"\n[SKIP] {short_name} {label}: page {page_idx} out of range")
            doc.close()
            continue

        page = doc[page_idx]
        bbox = tuple(db_bbox)

        # Run iterative detection
        boundaries, debug = detect_columns_iterative(
            page, bbox, caption_text, verbose=True
        )
        detected_cols = len(boundaries) + 1

        # Assign words for fill rate reporting
        words = page.get_text("words", clip=pymupdf.Rect(bbox))
        rows_of_words = cluster_words_into_rows(words, bbox)
        # Apply same trims for consistent reporting
        rows_of_words = trim_caption_rows(rows_of_words, caption_text)
        headers, data_rows = assign_words_to_columns(rows_of_words, boundaries)
        fill = compute_fill_rate(headers, data_rows)

        status = "OK" if detected_cols == expected_cols else "MISS"
        results.append((short_name, label, expected_cols, detected_cols, status))

        print(f"\n{'=' * 70}")
        print(f"[{status}] {short_name} — {label}")
        print(f"  Expected: {expected_cols} cols")
        print(f"  Detected: {detected_cols} cols (boundaries: {len(boundaries)})")
        print(f"  Fill: {fill:.1%}")
        print(f"  Caption gap: {debug.get('caption_gap', 0):.2f}pt, min width: {debug.get('min_width', 0):.2f}pt")
        print(f"  Rows: {debug.get('initial_rows', 0)} initial"
              f" → {debug.get('rows_after_caption_trim', 0)} after caption trim"
              f" → {debug.get('rows_after_sum_trim', 0)} after sum trim"
              f" (top={debug.get('top_trimmed', 0)}, bot={debug.get('bottom_trimmed', 0)})")
        print(f"  Candidates: {debug.get('initial_candidates', 0)} initial"
              f" → {debug.get('final_candidates', 0)} final")

        if boundaries:
            print(f"  Final boundaries:")
            for i, (bl, br) in enumerate(boundaries):
                print(f"    {i}: x=[{bl:.1f}, {br:.1f}] width={br - bl:.1f}pt")

        # Show iteration details
        for it in range(5):
            key_p = f"iter{it}_n_primary"
            key_c = f"iter{it}_n_candidates"
            key_d = f"iter{it}_dropped"
            if key_p not in debug:
                break
            dcs = debug.get(f"iter{it}_dense_col_sums", [])
            print(f"  Iteration {it}: primary={debug[key_p]}, "
                  f"candidates={debug[key_c]}, dropped={debug[key_d]}, "
                  f"dense_col_sums={dcs}")

        # Show first rows
        if headers:
            print(f"  Header: {[h[:30] for h in headers[:10]]}")
        for ri, row in enumerate(data_rows[:3]):
            print(f"  Row {ri}: {[c[:30] if c else '' for c in row[:10]]}")
        if len(data_rows) > 3:
            print(f"  ... ({len(data_rows) - 3} more rows)")

        doc.close()

    # Summary
    print(f"\n{'=' * 80}")
    print("SUMMARY")
    print(f"{'=' * 80}")
    ok = sum(1 for r in results if r[4] == "OK")
    total = len(results)
    print(f"  {ok}/{total} tables detected correct column count")
    print()
    for short_name, label, expected, detected, status in results:
        marker = "  " if status == "OK" else ">>"
        print(f"  {marker} {short_name:25s} {label:20s} expected={expected:2d}  detected={detected:2d}  {status}")


if __name__ == "__main__":
    run_tests()
