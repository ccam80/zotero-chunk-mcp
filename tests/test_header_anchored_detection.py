"""
Prototype: Header-anchored column detection with per-column row merging.

Step 1: Find columns from first ~3 rows using large x-gaps (>2× caption word gap)
Step 2: Detect and remove inline headers (col0 exclusive-or pattern)
Step 3: Per-column y-gap analysis to find row boundaries (dual of column detection)

Usage:
    .venv/Scripts/python.exe tests/test_header_anchored_detection.py
"""
from __future__ import annotations

import sys
from statistics import median

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import pymupdf
import pymupdf.layout  # required for find_tables to work on some PDFs


# ---------------------------------------------------------------------------
# Step 0: Line clustering (tight y-tolerance, just character height)
# ---------------------------------------------------------------------------

def cluster_into_lines(words: list, bbox: tuple) -> list[list]:
    """Cluster words into text lines using tight y-tolerance."""
    clip = pymupdf.Rect(bbox)
    clipped = [w for w in words if clip.intersects(pymupdf.Rect(w[:4]))]
    if not clipped:
        return []

    heights = sorted(w[3] - w[1] for w in clipped if w[3] - w[1] > 0)
    if not heights:
        return []
    med_h = heights[len(heights) // 2]
    line_tol = med_h * 0.4

    clipped.sort(key=lambda w: (w[1], w[0]))
    lines: list[list] = []
    current = [clipped[0]]
    for w in clipped[1:]:
        if w[1] - current[-1][1] > line_tol:
            lines.append(sorted(current, key=lambda w: w[0]))
            current = [w]
        else:
            current.append(w)
    lines.append(sorted(current, key=lambda w: w[0]))
    return lines


def line_y_mid(line: list) -> float:
    """Y-midpoint of a line of words."""
    return sum((w[1] + w[3]) / 2 for w in line) / len(line)


# ---------------------------------------------------------------------------
# Step 0b: Caption word gap (body-text reference)
# ---------------------------------------------------------------------------

def compute_body_text_word_gap(page: pymupdf.Page, bbox: tuple) -> float:
    """Compute median inter-word gap from body text outside the table."""
    all_words = page.get_text("words")
    if not all_words:
        return 3.0

    clip = pymupdf.Rect(bbox)
    outside = [w for w in all_words if not clip.intersects(pymupdf.Rect(w[:4]))]
    if len(outside) < 10:
        # Fall back to all words
        outside = all_words

    heights = sorted(w[3] - w[1] for w in outside if w[3] - w[1] > 0)
    if not heights:
        return 3.0
    med_h = heights[len(heights) // 2]
    line_tol = med_h * 0.4

    outside.sort(key=lambda w: (w[1], w[0]))
    rows: list[list] = []
    current = [outside[0]]
    for w in outside[1:]:
        if w[1] - current[-1][1] > line_tol:
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
# Step 1: Columns from first ~3 rows
# ---------------------------------------------------------------------------

def find_large_gap_positions(line: list, min_gap: float) -> list[float]:
    """Find x-midpoints of gaps larger than min_gap in a line of words."""
    positions = []
    for i in range(1, len(line)):
        gap = line[i][0] - line[i - 1][2]
        if gap >= min_gap:
            positions.append((line[i - 1][2] + line[i][0]) / 2)
    return positions


def find_shared_gap_positions(
    lines: list[list],
    min_gap: float,
    cluster_tol: float,
) -> list[float]:
    """Find column boundary x-positions from the best header line.

    The line among the first N with the most large gaps is the primary
    header — the most-granular row defining column structure. Its gap
    positions are accepted as column boundaries without requiring
    confirmation from other lines, which may be continuations, inline
    headers, or partial data rows with fewer column divisions.
    """
    if not lines:
        return []

    all_positions: list[list[float]] = []
    for line in lines:
        positions = find_large_gap_positions(line, min_gap)
        all_positions.append(positions)

    # Primary = line with most large gaps (the most-granular header row)
    ref_idx = max(range(len(all_positions)), key=lambda i: len(all_positions[i]))
    return list(all_positions[ref_idx])


def detect_columns_from_headers(
    lines: list[list],
    body_word_gap: float,
    n_header_lines: int = 3,
) -> list[float]:
    """Step 1: Detect column boundary x-positions from first N lines.

    Column boundaries = x-positions where gaps > 2× body word gap
    appear in ALL of the first N lines (or all lines if fewer).
    """
    header_lines = lines[:min(n_header_lines, len(lines))]
    min_gap = body_word_gap * 2.0

    # Cluster tolerance: use median word width from header lines
    all_widths = []
    for line in header_lines:
        for w in line:
            all_widths.append(w[2] - w[0])
    cluster_tol = median(all_widths) if all_widths else 10.0

    return find_shared_gap_positions(header_lines, min_gap, cluster_tol)


# ---------------------------------------------------------------------------
# Step 1b: Assign words to columns
# ---------------------------------------------------------------------------

def assign_word_to_column(word, boundaries: list[float]) -> int:
    """Assign a word to a column index based on its x-midpoint."""
    x_mid = (word[0] + word[2]) / 2
    for i, bx in enumerate(boundaries):
        if x_mid < bx:
            return i
    return len(boundaries)


def assign_line_to_columns(
    line: list, boundaries: list[float], n_cols: int,
) -> list[str]:
    """Assign words in a line to column cells."""
    cells = [""] * n_cols
    for w in line:
        col = assign_word_to_column(w, boundaries)
        if col < n_cols:
            if cells[col]:
                cells[col] += " " + w[4]
            else:
                cells[col] = w[4]
    return cells


# ---------------------------------------------------------------------------
# Step 2: Inline header detection
# ---------------------------------------------------------------------------

def detect_inline_headers(
    lines: list[list],
    boundaries: list[float],
    n_cols: int,
) -> list[tuple[int, str]]:
    """Detect inline header rows (col0 exclusive-or pattern).

    Returns list of (line_index, header_text) for inline header lines.
    """
    inline_headers = []

    for li, line in enumerate(lines):
        cells = assign_line_to_columns(line, boundaries, n_cols)
        col0 = cells[0].strip()
        others = [c.strip() for c in cells[1:]]
        any_others = any(others)

        if col0 and not any_others:
            # Col0 has content, no other columns — candidate inline header
            inline_headers.append((li, col0))

    return inline_headers


# ---------------------------------------------------------------------------
# Step 3: Per-column y-gap row boundary detection
# ---------------------------------------------------------------------------

def find_row_boundaries_per_column(
    lines: list[list],
    boundaries: list[float],
    n_cols: int,
    exclude_lines: set[int],
) -> list[float]:
    """Step 3: Find row boundary y-positions via per-column y-gap analysis.

    For each column, collect y-midpoints of words, compute gaps,
    find the larger gaps. Row boundaries = y-positions where larger
    gaps appear across most columns.
    """
    # Collect per-column y-midpoints (one per line)
    col_line_ys: dict[int, list[tuple[float, int]]] = {c: [] for c in range(n_cols)}

    for li, line in enumerate(lines):
        if li in exclude_lines:
            continue
        for w in line:
            col = assign_word_to_column(w, boundaries)
            if col < n_cols:
                y_mid = (w[1] + w[3]) / 2
                col_line_ys[col].append((y_mid, li))

    # For each column, cluster word y-midpoints into line-level entries,
    # then compute gaps between consecutive lines
    col_gaps: dict[int, list[tuple[float, float]]] = {}  # col -> [(gap_size, gap_y_mid)]

    for col in range(n_cols):
        entries = col_line_ys[col]
        if len(entries) < 2:
            continue

        # Sort by y, deduplicate to line-level (one y per line)
        entries.sort(key=lambda e: e[0])
        # Group by line index to get one y per line
        line_ys: dict[int, float] = {}
        for y, li in entries:
            if li not in line_ys:
                line_ys[li] = y
            else:
                line_ys[li] = (line_ys[li] + y) / 2  # average if multiple words

        sorted_ys = [line_ys[li] for li in sorted(line_ys.keys())]
        if len(sorted_ys) < 2:
            continue

        gaps = []
        for i in range(1, len(sorted_ys)):
            g = sorted_ys[i] - sorted_ys[i - 1]
            if g > 0.1:
                gaps.append((g, (sorted_ys[i - 1] + sorted_ys[i]) / 2))
        col_gaps[col] = gaps

    if not col_gaps:
        return []

    # Find the gap threshold per column: largest absolute jump in sorted gaps
    col_thresholds: dict[int, float] = {}
    for col, gaps in col_gaps.items():
        if len(gaps) < 2:
            continue
        sorted_g = sorted(g for g, _ in gaps)
        max_jump = 0
        max_jump_idx = 0
        for i in range(len(sorted_g) - 1):
            jump = sorted_g[i + 1] - sorted_g[i]
            if jump > max_jump:
                max_jump = jump
                max_jump_idx = i
        if max_jump > 0:
            col_thresholds[col] = (sorted_g[max_jump_idx] + sorted_g[max_jump_idx + 1]) / 2

    if not col_thresholds:
        return []

    # Collect "large gap" y-positions from each column
    # A large gap in a column = gap_size > that column's threshold
    boundary_votes: list[tuple[float, int]] = []  # (y_mid, col)
    for col, gaps in col_gaps.items():
        if col not in col_thresholds:
            continue
        threshold = col_thresholds[col]
        for g_size, g_y in gaps:
            if g_size > threshold:
                boundary_votes.append((g_y, col))

    if not boundary_votes:
        return []

    # Cluster y-positions across columns
    boundary_votes.sort(key=lambda v: v[0])

    # Use median line height as clustering tolerance
    all_heights = []
    for line in lines:
        for w in line:
            h = w[3] - w[1]
            if h > 0:
                all_heights.append(h)
    cluster_tol = median(all_heights) if all_heights else 8.0

    clusters: list[list[tuple[float, int]]] = []
    current_cluster = [boundary_votes[0]]
    for v in boundary_votes[1:]:
        if v[0] - current_cluster[-1][0] > cluster_tol:
            clusters.append(current_cluster)
            current_cluster = [v]
        else:
            current_cluster.append(v)
    clusters.append(current_cluster)

    # A row boundary must have votes from multiple distinct columns
    min_col_votes = max(2, len(col_thresholds) // 2)
    row_boundaries = []
    for cluster in clusters:
        distinct_cols = len(set(col for _, col in cluster))
        if distinct_cols >= min_col_votes:
            y_avg = sum(y for y, _ in cluster) / len(cluster)
            row_boundaries.append(y_avg)

    return sorted(row_boundaries)


# ---------------------------------------------------------------------------
# Grid assembly
# ---------------------------------------------------------------------------

def build_grid(
    lines: list[list],
    col_boundaries: list[float],
    row_boundaries: list[float],
    inline_header_lines: set[int],
) -> tuple[list[str], list[list[str]]]:
    """Assemble final grid from lines, column and row boundaries.

    Lines between consecutive row boundaries are merged into one logical row.
    Inline header lines are excluded (handled separately).
    """
    n_cols = len(col_boundaries) + 1

    # Map each line to a logical row based on row boundaries
    line_to_logical: dict[int, int] = {}
    for li, line in enumerate(lines):
        if li in inline_header_lines:
            continue
        y = line_y_mid(line)
        logical_row = 0
        for ri, rb in enumerate(row_boundaries):
            if y > rb:
                logical_row = ri + 1
            else:
                break
        line_to_logical[li] = logical_row

    if not line_to_logical:
        return [], []

    n_logical_rows = max(line_to_logical.values()) + 1

    # Build grid: merge all lines in each logical row
    grid: list[list[str]] = [[""] * n_cols for _ in range(n_logical_rows)]

    for li, line in enumerate(lines):
        if li in inline_header_lines:
            continue
        lr = line_to_logical[li]
        cells = assign_line_to_columns(line, col_boundaries, n_cols)
        for ci in range(n_cols):
            if cells[ci]:
                if grid[lr][ci]:
                    grid[lr][ci] += " " + cells[ci]
                else:
                    grid[lr][ci] = cells[ci]

    if not grid:
        return [], []

    return grid[0], grid[1:]


def compute_fill_rate(headers: list[str], rows: list[list[str]]) -> float:
    """Fraction of non-empty cells."""
    all_cells = list(headers)
    for r in rows:
        all_cells.extend(r)
    if not all_cells:
        return 0.0
    return sum(1 for c in all_cells if c.strip()) / len(all_cells)


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------

def extract_table_header_anchored(
    page: pymupdf.Page,
    bbox: tuple,
    caption_text: str = "",
    verbose: bool = False,
) -> dict:
    """Run the full header-anchored extraction pipeline."""
    result = {"cols": 0, "rows": 0, "fill": 0.0, "boundaries": [],
              "row_boundaries": [], "inline_headers": [], "headers": [],
              "data_rows": [], "debug": {}}

    words = page.get_text("words", clip=pymupdf.Rect(bbox))
    lines = cluster_into_lines(words, bbox)
    result["debug"]["n_lines"] = len(lines)

    if len(lines) < 2:
        return result

    # Body text word gap
    body_gap = compute_body_text_word_gap(page, bbox)
    result["debug"]["body_gap"] = body_gap

    # Step 1: Columns from first 3 rows
    col_boundaries = detect_columns_from_headers(lines, body_gap, n_header_lines=3)
    n_cols = len(col_boundaries) + 1
    result["boundaries"] = col_boundaries
    result["cols"] = n_cols
    result["debug"]["step1_cols"] = n_cols

    if verbose:
        print(f"    Step 1: {n_cols} columns from {min(3, len(lines))} header lines")
        print(f"      body_gap={body_gap:.2f}, min_gap={body_gap*2:.2f}")
        for i, bx in enumerate(col_boundaries):
            print(f"      boundary {i}: x={bx:.1f}")

    if n_cols < 2:
        # No column structure found — return single-column
        result["headers"] = [" ".join(w[4] for w in lines[0])]
        result["data_rows"] = [[" ".join(w[4] for w in line)] for line in lines[1:]]
        result["rows"] = len(lines) - 1
        result["fill"] = 1.0
        return result

    # Step 2: Inline header detection
    inline_headers = detect_inline_headers(lines, col_boundaries, n_cols)
    inline_header_set = set(li for li, _ in inline_headers)
    result["inline_headers"] = inline_headers
    result["debug"]["n_inline_headers"] = len(inline_headers)

    if verbose and inline_headers:
        print(f"    Step 2: {len(inline_headers)} inline headers")
        for li, text in inline_headers:
            print(f"      line {li}: \"{text[:40]}\"")

    # Step 3: Per-column row boundary detection
    row_boundaries = find_row_boundaries_per_column(
        lines, col_boundaries, n_cols, inline_header_set,
    )
    result["row_boundaries"] = row_boundaries
    result["debug"]["n_row_boundaries"] = len(row_boundaries)

    if verbose:
        n_logical = len(row_boundaries) + 1
        print(f"    Step 3: {len(row_boundaries)} row boundaries → {n_logical} logical rows")

    # Build final grid
    headers, data_rows = build_grid(
        lines, col_boundaries, row_boundaries, inline_header_set,
    )
    result["headers"] = headers
    result["data_rows"] = data_rows
    result["rows"] = len(data_rows)
    result["fill"] = compute_fill_rate(headers, data_rows)

    return result


# ---------------------------------------------------------------------------
# Test harness
# ---------------------------------------------------------------------------

TEST_TABLES = [
    ("SCPXVBLY", "active-inference", 17, "Table 2", 4,
     "Table 2 Matrix formulation of equations used for inference.",
     [37.616, 91.8, 552.255, 713.655]),  # caption-clipped bbox
    ("SCPXVBLY", "active-inference", 18, "Table 2 cont", 4,
     "Table 2 (continued).",
     [37.616, 61.9, 553.127, 473.353]),  # caption-clipped
    ("SCPXVBLY", "active-inference", 30, "Table 3 cont", 4,
     "Table 3 (continued).",
     [42.149, 66.117, 551.209, 248.650]),
    ("9GKLLJH9", "helm", 5, "Table 2", 6,
     "Table 2 Coefficients From Best-Fitting Cross-Lagged Panel Model (Model 6)",
     [48.000, 118.408, 288.024, 292.236]),
    ("Z9X4JVZ5", "roland", 9, "Table 2", 7,
     "Table 2. Floating-point highpass filter coefficients.",
     [104.721, 180.6, 484.687, 566.462]),  # caption-clipped
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
    sys.path.insert(0, "src")
    from zotero_chunk_rag.zotero_client import ZoteroClient
    from zotero_chunk_rag.config import Config

    config = Config.load()
    zotero = ZoteroClient(config.zotero_data_dir)
    all_items = zotero.get_all_items_with_pdfs()
    items_by_key = {i.item_key: i for i in all_items}

    print("=" * 80)
    print("HEADER-ANCHORED COLUMN DETECTION — PROTOTYPE")
    print("=" * 80)

    results = []

    for item_key, short_name, page_idx, label, expected_cols, caption_text, db_bbox in TEST_TABLES:
        item = items_by_key.get(item_key)
        if not item or not item.pdf_path or not item.pdf_path.exists():
            print(f"\n[SKIP] {short_name} {label}: PDF not found")
            continue

        doc = pymupdf.open(str(item.pdf_path))
        if page_idx >= len(doc):
            doc.close()
            continue

        page = doc[page_idx]
        bbox = tuple(db_bbox)

        print(f"\n{'=' * 70}")
        print(f"  {short_name} — {label} (expected {expected_cols} cols)")
        print(f"{'=' * 70}")

        r = extract_table_header_anchored(page, bbox, caption_text, verbose=True)

        status = "OK" if r["cols"] == expected_cols else "MISS"
        results.append((short_name, label, expected_cols, r["cols"], r["rows"], r["fill"], status))

        print(f"  [{status}] {r['cols']} cols, {r['rows']} data rows, fill={r['fill']:.1%}")

        if r["headers"]:
            print(f"  Header: {[h[:25] for h in r['headers'][:10]]}")
        for ri, row in enumerate(r["data_rows"][:3]):
            print(f"  Row {ri}: {[c[:25] if c else '' for c in row[:10]]}")
        if len(r["data_rows"]) > 3:
            print(f"  ... ({len(r['data_rows']) - 3} more rows)")

        doc.close()

    # Summary
    print(f"\n{'=' * 80}")
    print("SUMMARY")
    print(f"{'=' * 80}")
    ok = sum(1 for r in results if r[6] == "OK")
    total = len(results)
    print(f"  {ok}/{total} tables detected correct column count\n")
    print(f"  {'':2s} {'paper':25s} {'label':20s} {'exp':>4s} {'det':>4s} {'rows':>5s} {'fill':>6s}")
    for short_name, label, expected, detected, rows, fill, status in results:
        marker = "  " if status == "OK" else ">>"
        print(f"  {marker} {short_name:25s} {label:20s} {expected:4d} {detected:4d} {rows:5d} {fill:6.1%}")


if __name__ == "__main__":
    run_tests()
