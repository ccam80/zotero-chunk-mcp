"""Ground truth loading and comparison utilities for table extraction evaluation."""
from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

GROUND_TRUTH_DB_PATH = Path(__file__).resolve().parents[3] / "tests" / "ground_truth.db"

_TABLE_ID_NUM_RE = re.compile(
    r"^(?:\*\*)?(?:Table|Tab\.?)\s+(\d+|[IVXLCDM]+|[A-Z]\.\d+|S\d+)",
    re.IGNORECASE,
)

_CONTINUATION_RE = re.compile(
    r"\b(?:continued|cont(?:inued)?\.?)\b",
    re.IGNORECASE,
)

SYNTHETIC_CAPTION_PREFIX = "Uncaptioned "

# ---------------------------------------------------------------------------
# Schema creation
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """\
CREATE TABLE IF NOT EXISTS ground_truth_tables (
    table_id    TEXT PRIMARY KEY,
    paper_key   TEXT NOT NULL,
    page_num    INTEGER NOT NULL,
    caption     TEXT,
    headers_json TEXT NOT NULL,
    rows_json   TEXT NOT NULL,
    num_rows    INTEGER NOT NULL,
    num_cols    INTEGER NOT NULL,
    notes       TEXT DEFAULT '',
    footnotes   TEXT DEFAULT '',
    created_at  TEXT NOT NULL,
    verified_by TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS ground_truth_meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


def create_ground_truth_db(db_path: Path) -> None:
    """Create the ground truth database with the required schema if it doesn't exist.

    Safe to call on existing databases — uses CREATE TABLE IF NOT EXISTS and
    adds the ``footnotes`` column via ALTER TABLE if not already present.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(_SCHEMA_SQL)
        # Ensure footnotes column exists
        cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(ground_truth_tables)").fetchall()
        }
        if "footnotes" not in cols:
            conn.execute(
                "ALTER TABLE ground_truth_tables ADD COLUMN footnotes TEXT DEFAULT ''"
            )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Table ID generation
# ---------------------------------------------------------------------------


def make_table_id(
    paper_key: str,
    caption: str | None,
    page_num: int,
    table_index: int,
) -> str:
    """Generate a stable table ID from caption text or fall back to orphan format.

    Captioned tables: ``{paper_key}_table_{N}`` where N is parsed from the caption.
    Continuation tables (caption contains "continued"): ``{paper_key}_table_{N}_p{page}``.
    Orphan tables (no caption or synthetic caption): ``{paper_key}_orphan_p{page}_t{index}``.
    """
    if caption is not None and not caption.startswith(SYNTHETIC_CAPTION_PREFIX):
        m = _TABLE_ID_NUM_RE.match(caption)
        if m:
            num = m.group(1)
            if _CONTINUATION_RE.search(caption):
                return f"{paper_key}_table_{num}_p{page_num}"
            return f"{paper_key}_table_{num}"
    return f"{paper_key}_orphan_p{page_num}_t{table_index}"


# ---------------------------------------------------------------------------
# Insert / query helpers
# ---------------------------------------------------------------------------


def insert_ground_truth(
    db_path: Path,
    table_id: str,
    paper_key: str,
    page_num: int,
    caption: str,
    headers: list[str],
    rows: list[list[str]],
    notes: str = "",
    footnotes: str = "",
) -> None:
    """Insert or replace a ground truth entry in the database."""
    headers_json = json.dumps(headers, ensure_ascii=False)
    rows_json = json.dumps(rows, ensure_ascii=False)
    num_rows = len(rows)
    num_cols = len(headers) if headers else (max((len(r) for r in rows), default=0) if rows else 0)
    created_at = datetime.now(timezone.utc).isoformat()

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """INSERT OR REPLACE INTO ground_truth_tables
               (table_id, paper_key, page_num, caption, headers_json, rows_json,
                num_rows, num_cols, notes, footnotes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (table_id, paper_key, page_num, caption, headers_json, rows_json,
             num_rows, num_cols, notes, footnotes, created_at),
        )
        conn.commit()
    finally:
        conn.close()


def get_table_ids(db_path: Path, paper_key: str | None = None) -> list[str]:
    """List all table IDs, optionally filtered by paper key."""
    conn = sqlite3.connect(str(db_path))
    try:
        if paper_key is not None:
            cursor = conn.execute(
                "SELECT table_id FROM ground_truth_tables WHERE paper_key = ? ORDER BY table_id",
                (paper_key,),
            )
        else:
            cursor = conn.execute(
                "SELECT table_id FROM ground_truth_tables ORDER BY table_id",
            )
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Comparison dataclasses
# ---------------------------------------------------------------------------

_LIGATURE_MAP = {
    "\ufb00": "ff",
    "\ufb01": "fi",
    "\ufb02": "fl",
    "\ufb03": "ffi",
    "\ufb04": "ffl",
}


@dataclass
class CellDiff:
    """A single cell mismatch between ground truth and extraction."""
    row: int
    col: int
    expected: str
    actual: str


@dataclass
class SplitInfo:
    """One GT row/col split into multiple extraction rows/cols."""
    gt_index: int
    ext_indices: list[int]


@dataclass
class MergeInfo:
    """Multiple GT rows/cols merged into one extraction row/col."""
    gt_indices: list[int]
    ext_index: int


@dataclass
class ComparisonResult:
    """Structured diff between a ground truth table and an extraction attempt."""
    table_id: str
    gt_shape: tuple[int, int]
    ext_shape: tuple[int, int]
    matched_columns: list[tuple[int, int]]
    extra_columns: list[int]
    missing_columns: list[int]
    column_splits: list[SplitInfo]
    column_merges: list[MergeInfo]
    matched_rows: list[tuple[int, int]]
    extra_rows: list[int]
    missing_rows: list[int]
    row_splits: list[SplitInfo]
    row_merges: list[MergeInfo]
    cell_diffs: list[CellDiff]
    cell_accuracy_pct: float
    header_diffs: list[CellDiff]
    # Coverage: fraction of GT cells that were comparable (not in affected rows/cols)
    comparable_cells: int = 0
    total_gt_cells: int = 0
    structural_coverage_pct: float = 100.0
    # Artifact detection
    gt_is_artifact: bool = False
    # Footnote comparison
    footnote_match: bool | None = None
    gt_footnotes: str = ""
    # Fuzzy (alignment-free) accuracy
    fuzzy_accuracy_pct: float = 0.0
    fuzzy_precision_pct: float = 0.0
    fuzzy_recall_pct: float = 0.0


# ---------------------------------------------------------------------------
# Cell normalization
# ---------------------------------------------------------------------------


def _normalize_cell(text: str) -> str:
    """Normalize a cell value for comparison.

    Steps:
    1. Strip leading/trailing whitespace
    2. Collapse internal whitespace to single space
    3. Dash/hyphen normalization (unicode minus, en-dash, em-dash, etc.)
    4. Ligature normalization
    """
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    # Normalize all dash-like characters to ASCII hyphen
    for ch in "\u2212\u2013\u2014\u2010\u2011\ufe63\uff0d":
        text = text.replace(ch, "-")
    for lig, replacement in _LIGATURE_MAP.items():
        text = text.replace(lig, replacement)
    return text


# ---------------------------------------------------------------------------
# Fuzzy cell scoring
# ---------------------------------------------------------------------------


def _is_numeric_cell(text: str) -> bool:
    """Return True if *text* represents a numeric value.

    Strips whitespace and a trailing ``%`` before attempting ``float()`` parse.
    """
    s = text.strip()
    if s.endswith("%"):
        s = s[:-1]
    try:
        float(s)
        return True
    except (ValueError, TypeError):
        return False


def _fuzzy_cell_score(a: str, b: str) -> float:
    """Score the similarity of two cell values after normalization.

    Returns a float in [0.0, 1.0]:
    - 1.0 for exact match (after normalization) or both empty.
    - 0.0 when one cell is empty and the other is not.
    - 0.0 when either cell is numeric and they don't match exactly (numeric
      mismatch is always a complete failure).
    - For text cells: longest-common-substring length divided by the length
      of the longer string.
    """
    na = _normalize_cell(a)
    nb = _normalize_cell(b)

    if na == nb:
        return 1.0

    if not na or not nb:
        return 0.0

    if _is_numeric_cell(na) or _is_numeric_cell(nb):
        return 0.0

    lcs = _longest_common_substring_len(na, nb)
    return lcs / max(len(na), len(nb))


def _compute_fuzzy_accuracy(
    gt_headers: list[str],
    gt_rows: list[list[str]],
    ext_headers: list[str],
    ext_rows: list[list[str]],
) -> tuple[float, float, float]:
    """Compute alignment-free fuzzy accuracy as (precision, recall, F1).

    Collects all non-empty cells from each side (headers + rows), then uses
    best-first greedy assignment with ``_fuzzy_cell_score`` to compute
    precision (from extraction's perspective) and recall (from GT's
    perspective) independently.
    """
    gt_cells = [_normalize_cell(c) for c in gt_headers if _normalize_cell(c)]
    for row in gt_rows:
        for c in row:
            nc = _normalize_cell(c)
            if nc:
                gt_cells.append(nc)

    ext_cells = [_normalize_cell(c) for c in ext_headers if _normalize_cell(c)]
    for row in ext_rows:
        for c in row:
            nc = _normalize_cell(c)
            if nc:
                ext_cells.append(nc)

    if not gt_cells and not ext_cells:
        return (1.0, 1.0, 1.0)

    if not gt_cells or not ext_cells:
        return (0.0, 0.0, 0.0)

    def _greedy_assign(
        source: list[str], target: list[str]
    ) -> float:
        """Score source against target via best-first greedy matching."""
        triples: list[tuple[float, int, int]] = []
        for si, sv in enumerate(source):
            for ti, tv in enumerate(target):
                score = _fuzzy_cell_score(sv, tv)
                if score > 0.0:
                    triples.append((score, si, ti))
        triples.sort(key=lambda t: t[0], reverse=True)
        used_source: set[int] = set()
        used_target: set[int] = set()
        total = 0.0
        for score, si, ti in triples:
            if si in used_source or ti in used_target:
                continue
            used_source.add(si)
            used_target.add(ti)
            total += score
        return total / len(source) if source else 0.0

    precision = _greedy_assign(ext_cells, gt_cells)
    recall = _greedy_assign(gt_cells, ext_cells)

    if precision + recall > 0.0:
        f1 = 2.0 * precision * recall / (precision + recall)
    else:
        f1 = 0.0

    return (precision, recall, f1)


# ---------------------------------------------------------------------------
# Column alignment
# ---------------------------------------------------------------------------


def _longest_common_substring_len(a: str, b: str) -> int:
    """Return the length of the longest common substring between a and b."""
    if not a or not b:
        return 0
    m, n = len(a), len(b)
    prev = [0] * (n + 1)
    best = 0
    for i in range(1, m + 1):
        curr = [0] * (n + 1)
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                curr[j] = prev[j - 1] + 1
                if curr[j] > best:
                    best = curr[j]
        prev = curr
    return best


def _align_columns(
    gt_headers: list[str],
    ext_headers: list[str],
) -> tuple[
    list[tuple[int, int]],  # matched (gt_idx, ext_idx)
    list[int],              # extra ext indices
    list[int],              # missing gt indices
    list[SplitInfo],        # column splits
    list[MergeInfo],        # column merges
]:
    """Align extraction columns to GT columns by normalized header text."""
    gt_norm = [_normalize_cell(h) for h in gt_headers]
    ext_norm = [_normalize_cell(h) for h in ext_headers]

    matched: list[tuple[int, int]] = []
    used_ext: set[int] = set()
    used_gt: set[int] = set()

    # Pass 1: exact match
    for gi, gh in enumerate(gt_norm):
        for ei, eh in enumerate(ext_norm):
            if ei in used_ext:
                continue
            if gh == eh:
                matched.append((gi, ei))
                used_ext.add(ei)
                used_gt.add(gi)
                break

    # Pass 2: LCS fallback for unmatched
    unmatched_gt = [i for i in range(len(gt_norm)) if i not in used_gt]
    unmatched_ext = [i for i in range(len(ext_norm)) if i not in used_ext]

    for gi in list(unmatched_gt):
        best_ei = -1
        best_score = 0.0
        gh = gt_norm[gi]
        if not gh:
            continue
        for ei in unmatched_ext:
            eh = ext_norm[ei]
            if not eh:
                continue
            lcs = _longest_common_substring_len(gh, eh)
            score = lcs / max(len(gh), len(eh))
            if score > best_score:
                best_score = score
                best_ei = ei
        if best_ei >= 0 and best_score >= 0.8:
            matched.append((gi, best_ei))
            used_ext.add(best_ei)
            used_gt.add(gi)
            unmatched_gt.remove(gi)
            unmatched_ext.remove(best_ei)

    # Detect column splits: one GT col whose header appears spread across
    # multiple adjacent ext columns
    column_splits: list[SplitInfo] = []
    still_missing_gt = [i for i in range(len(gt_norm)) if i not in used_gt]
    still_extra_ext = sorted(i for i in range(len(ext_norm)) if i not in used_ext)

    for gi in list(still_missing_gt):
        gh = gt_norm[gi]
        if not gh:
            continue
        # Try concatenating adjacent unmatched ext columns
        for start_pos in range(len(still_extra_ext)):
            for end_pos in range(start_pos + 1, len(still_extra_ext)):
                indices = still_extra_ext[start_pos:end_pos + 1]
                # Check adjacency
                if any(indices[k + 1] - indices[k] != 1 for k in range(len(indices) - 1)):
                    continue
                concat = "".join(ext_norm[ei] for ei in indices)
                if concat == gh:
                    column_splits.append(SplitInfo(gt_index=gi, ext_indices=list(indices)))
                    for ei in indices:
                        used_ext.add(ei)
                        if ei in still_extra_ext:
                            still_extra_ext.remove(ei)
                    used_gt.add(gi)
                    still_missing_gt.remove(gi)
                    break
            else:
                continue
            break

    # Detect column merges: multiple GT cols whose headers concatenate to
    # one ext col
    column_merges: list[MergeInfo] = []
    still_missing_gt = [i for i in range(len(gt_norm)) if i not in used_gt]
    still_extra_ext = sorted(i for i in range(len(ext_norm)) if i not in used_ext)

    for ei in list(still_extra_ext):
        eh = ext_norm[ei]
        if not eh:
            continue
        for start_pos in range(len(still_missing_gt)):
            for end_pos in range(start_pos + 1, len(still_missing_gt)):
                indices = still_missing_gt[start_pos:end_pos + 1]
                # Require GT columns to be adjacent in the original table
                if any(indices[k + 1] - indices[k] != 1 for k in range(len(indices) - 1)):
                    continue
                concat = "".join(gt_norm[gi] for gi in indices)
                if concat == eh:
                    column_merges.append(MergeInfo(gt_indices=list(indices), ext_index=ei))
                    for gi in indices:
                        used_gt.add(gi)
                    used_ext.add(ei)
                    still_extra_ext.remove(ei)
                    for gi in indices:
                        still_missing_gt.remove(gi)
                    break
            else:
                continue
            break

    # Pass 3: positional matching for remaining empty-string headers
    final_missing_gt = sorted(i for i in range(len(gt_norm)) if i not in used_gt)
    final_extra_ext = sorted(i for i in range(len(ext_norm)) if i not in used_ext)
    empty_gt = [i for i in final_missing_gt if not gt_norm[i]]
    empty_ext = [i for i in final_extra_ext if not ext_norm[i]]
    for gidx, eidx in zip(empty_gt, empty_ext):
        matched.append((gidx, eidx))
        used_gt.add(gidx)
        used_ext.add(eidx)

    extra_columns = sorted(i for i in range(len(ext_norm)) if i not in used_ext)
    missing_columns = sorted(i for i in range(len(gt_norm)) if i not in used_gt)

    return matched, extra_columns, missing_columns, column_splits, column_merges


# ---------------------------------------------------------------------------
# Row alignment
# ---------------------------------------------------------------------------


def _row_cells_match(gt_row: list[str], ext_row: list[str], col_map: dict[int, int]) -> bool:
    """Check if all mapped cells in a row match after normalization."""
    for gt_ci, ext_ci in col_map.items():
        gt_val = _normalize_cell(gt_row[gt_ci]) if gt_ci < len(gt_row) else ""
        ext_val = _normalize_cell(ext_row[ext_ci]) if ext_ci < len(ext_row) else ""
        if gt_val != ext_val:
            return False
    return True


def _row_partial_match(gt_row: list[str], ext_row: list[str], col_map: dict[int, int]) -> float:
    """Return the fraction of mapped cells that match."""
    if not col_map:
        return 0.0
    matches = 0
    for gt_ci, ext_ci in col_map.items():
        gt_val = _normalize_cell(gt_row[gt_ci]) if gt_ci < len(gt_row) else ""
        ext_val = _normalize_cell(ext_row[ext_ci]) if ext_ci < len(ext_row) else ""
        if gt_val == ext_val:
            matches += 1
    return matches / len(col_map)


def _concat_rows(rows: list[list[str]], col_count: int) -> list[str]:
    """Concatenate multiple rows cell-by-cell (space-separated, stripped)."""
    result = [""] * col_count
    for row in rows:
        for ci in range(min(len(row), col_count)):
            val = _normalize_cell(row[ci])
            if val:
                if result[ci]:
                    result[ci] += " " + val
                else:
                    result[ci] = val
    return result


def _align_rows(
    gt_rows: list[list[str]],
    ext_rows: list[list[str]],
    col_map: dict[int, int],
    gt_ncols: int,
    ext_ncols: int,
) -> tuple[
    list[tuple[int, int]],  # matched (gt_idx, ext_idx)
    list[int],              # extra ext indices
    list[int],              # missing gt indices
    list[SplitInfo],        # row splits
    list[MergeInfo],        # row merges
]:
    """Align extraction rows to GT rows sequentially with split/merge detection."""
    matched: list[tuple[int, int]] = []
    row_splits: list[SplitInfo] = []
    row_merges: list[MergeInfo] = []
    used_gt: set[int] = set()
    used_ext: set[int] = set()

    gi = 0
    ei = 0

    while gi < len(gt_rows) and ei < len(ext_rows):
        if _row_cells_match(gt_rows[gi], ext_rows[ei], col_map):
            matched.append((gi, ei))
            used_gt.add(gi)
            used_ext.add(ei)
            gi += 1
            ei += 1
            continue

        # Check for split: one GT row -> multiple ext rows
        split_found = False
        for span in range(2, min(4, len(ext_rows) - ei + 1)):
            ext_slice = ext_rows[ei:ei + span]
            concat = _concat_rows(ext_slice, ext_ncols)
            gt_concat = [_normalize_cell(gt_rows[gi][c]) if c < len(gt_rows[gi]) else "" for c in range(gt_ncols)]
            # Compare via col_map
            match = True
            for gt_ci, ext_ci in col_map.items():
                gt_val = gt_concat[gt_ci] if gt_ci < len(gt_concat) else ""
                ext_val = concat[ext_ci] if ext_ci < len(concat) else ""
                if gt_val != ext_val:
                    match = False
                    break
            if match:
                ext_indices = list(range(ei, ei + span))
                row_splits.append(SplitInfo(gt_index=gi, ext_indices=ext_indices))
                used_gt.add(gi)
                for idx in ext_indices:
                    used_ext.add(idx)
                gi += 1
                ei += span
                split_found = True
                break

        if split_found:
            continue

        # Check for merge: multiple GT rows -> one ext row
        merge_found = False
        for span in range(2, min(4, len(gt_rows) - gi + 1)):
            gt_slice = gt_rows[gi:gi + span]
            concat = _concat_rows(gt_slice, gt_ncols)
            # Compare via col_map
            match = True
            for gt_ci, ext_ci in col_map.items():
                gt_val = concat[gt_ci] if gt_ci < len(concat) else ""
                ext_val = _normalize_cell(ext_rows[ei][ext_ci]) if ext_ci < len(ext_rows[ei]) else ""
                if gt_val != ext_val:
                    match = False
                    break
            if match:
                gt_indices = list(range(gi, gi + span))
                row_merges.append(MergeInfo(gt_indices=gt_indices, ext_index=ei))
                for idx in gt_indices:
                    used_gt.add(idx)
                used_ext.add(ei)
                gi += span
                ei += 1
                merge_found = True
                break

        if merge_found:
            continue

        # Skip-ahead: try skipping 1-2 ext rows (spurious footnote/caption/blank)
        skip_found = False
        for skip in range(1, min(3, len(ext_rows) - ei)):
            if _row_cells_match(gt_rows[gi], ext_rows[ei + skip], col_map):
                # Skipped ext rows left out of used_ext → appear in extra_rows
                matched.append((gi, ei + skip))
                used_gt.add(gi)
                used_ext.add(ei + skip)
                gi += 1
                ei += skip + 1
                skip_found = True
                break

        if skip_found:
            continue

        # Skip-ahead: try skipping 1-2 GT rows (extraction missed rows)
        for skip in range(1, min(3, len(gt_rows) - gi)):
            if _row_cells_match(gt_rows[gi + skip], ext_rows[ei], col_map):
                # Skipped GT rows left out of used_gt → appear in missing_rows
                matched.append((gi + skip, ei))
                used_gt.add(gi + skip)
                used_ext.add(ei)
                gi += skip + 1
                ei += 1
                skip_found = True
                break

        if skip_found:
            continue

        # No exact match, split, merge, or skip -- pair rows anyway
        # (cell-level diffs will be captured during comparison)
        matched.append((gi, ei))
        used_gt.add(gi)
        used_ext.add(ei)
        gi += 1
        ei += 1

    extra_rows = sorted(i for i in range(len(ext_rows)) if i not in used_ext)
    missing_rows = sorted(i for i in range(len(gt_rows)) if i not in used_gt)

    return matched, extra_rows, missing_rows, row_splits, row_merges


# ---------------------------------------------------------------------------
# Main comparison function
# ---------------------------------------------------------------------------


def compare_extraction(
    db_path: Path,
    table_id: str,
    headers: list[str],
    rows: list[list[str]],
    footnotes: str = "",
) -> ComparisonResult:
    """Compare an extraction attempt against a ground truth table.

    Raises ``KeyError`` if *table_id* is not found in the database.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT headers_json, rows_json, footnotes FROM ground_truth_tables WHERE table_id = ?",
            (table_id,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        raise KeyError(f"table_id {table_id!r} not found in ground truth database")

    gt_headers: list[str] = json.loads(row[0])
    gt_rows: list[list[str]] = json.loads(row[1])
    gt_footnotes: str = row[2] or ""

    # Artifact detection: GT with no data
    gt_is_artifact = (
        not gt_rows
        and all(h.strip() == "" for h in gt_headers)
    ) if gt_headers else not gt_rows

    gt_shape = (len(gt_rows), len(gt_headers))
    ext_shape = (len(rows), len(headers))

    # --- Column alignment ---
    (
        matched_columns,
        extra_columns,
        missing_columns,
        column_splits,
        column_merges,
    ) = _align_columns(gt_headers, headers)

    # Build column map: gt_col_idx -> ext_col_idx (1:1 matched only)
    col_map: dict[int, int] = {g: e for g, e in matched_columns}

    # Columns involved in splits or merges
    split_gt_cols: set[int] = set()
    for s in column_splits:
        split_gt_cols.add(s.gt_index)
    merge_gt_cols: set[int] = set()
    for m in column_merges:
        for gi in m.gt_indices:
            merge_gt_cols.add(gi)
    affected_gt_cols = split_gt_cols | merge_gt_cols | set(missing_columns)

    # --- Row alignment ---
    gt_ncols = len(gt_headers)
    ext_ncols = len(headers)

    (
        matched_rows,
        extra_rows,
        missing_rows,
        row_splits,
        row_merges,
    ) = _align_rows(gt_rows, rows, col_map, gt_ncols, ext_ncols)

    # Rows involved in splits or merges
    split_gt_rows: set[int] = set()
    for s in row_splits:
        split_gt_rows.add(s.gt_index)
    merge_gt_rows: set[int] = set()
    for m in row_merges:
        for gi in m.gt_indices:
            merge_gt_rows.add(gi)
    affected_gt_rows = split_gt_rows | merge_gt_rows | set(missing_rows)

    # --- Cell comparison ---
    total_gt_cells = len(gt_rows) * len(gt_headers) if gt_headers else 0
    comparable_cols = {gc for gc in col_map if gc not in affected_gt_cols}
    comparable_rows = {gr for gr, _ in matched_rows if gr not in affected_gt_rows}
    comparable_cells = len(comparable_rows) * len(comparable_cols)
    correct_cells = 0
    cell_diffs: list[CellDiff] = []

    for gt_ri, ext_ri in matched_rows:
        if gt_ri in affected_gt_rows:
            continue
        for gt_ci, ext_ci in col_map.items():
            if gt_ci in affected_gt_cols:
                continue
            gt_val = _normalize_cell(gt_rows[gt_ri][gt_ci]) if gt_ci < len(gt_rows[gt_ri]) else ""
            ext_val = _normalize_cell(rows[ext_ri][ext_ci]) if ext_ci < len(rows[ext_ri]) else ""
            if gt_val == ext_val:
                correct_cells += 1
            else:
                cell_diffs.append(CellDiff(row=gt_ri, col=gt_ci, expected=gt_val, actual=ext_val))

    # Accuracy over comparable cells only (not penalized for structural issues)
    cell_accuracy_pct = (correct_cells / comparable_cells * 100.0) if comparable_cells > 0 else 0.0
    structural_coverage_pct = (comparable_cells / total_gt_cells * 100.0) if total_gt_cells > 0 else 100.0

    # --- Header comparison ---
    header_diffs: list[CellDiff] = []
    for gt_ci, ext_ci in matched_columns:
        gt_h = _normalize_cell(gt_headers[gt_ci])
        ext_h = _normalize_cell(headers[ext_ci])
        if gt_h != ext_h:
            header_diffs.append(CellDiff(row=-1, col=gt_ci, expected=gt_h, actual=ext_h))

    # --- Footnote comparison ---
    footnote_match: bool | None = None
    if gt_footnotes:
        footnote_match = _normalize_cell(footnotes) == _normalize_cell(gt_footnotes)

    # --- Fuzzy accuracy ---
    fuzzy_precision, fuzzy_recall, fuzzy_f1 = _compute_fuzzy_accuracy(
        gt_headers, gt_rows, headers, rows,
    )

    return ComparisonResult(
        table_id=table_id,
        gt_shape=gt_shape,
        ext_shape=ext_shape,
        matched_columns=matched_columns,
        extra_columns=extra_columns,
        missing_columns=missing_columns,
        column_splits=column_splits,
        column_merges=column_merges,
        matched_rows=matched_rows,
        extra_rows=extra_rows,
        missing_rows=missing_rows,
        row_splits=row_splits,
        row_merges=row_merges,
        cell_diffs=cell_diffs,
        cell_accuracy_pct=cell_accuracy_pct,
        header_diffs=header_diffs,
        comparable_cells=comparable_cells,
        total_gt_cells=total_gt_cells,
        structural_coverage_pct=structural_coverage_pct,
        gt_is_artifact=gt_is_artifact,
        footnote_match=footnote_match,
        gt_footnotes=gt_footnotes,
        fuzzy_accuracy_pct=fuzzy_f1 * 100.0,
        fuzzy_precision_pct=fuzzy_precision * 100.0,
        fuzzy_recall_pct=fuzzy_recall * 100.0,
    )
