"""Recompute gt_comparisons and stage_diffs.accuracy_delta in _vision_stage_eval.db.

Uses stored agent_outputs (headers_json, rows_json) and the current
compare_extraction() logic — no API calls needed.

Usage:
    .venv/Scripts/python.exe tools/recompute_gt.py
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

# Ensure src is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from zotero_chunk_rag.feature_extraction.ground_truth import (
    GROUND_TRUTH_DB_PATH,
    compare_extraction,
    get_table_ids,
)

EVAL_DB = Path(__file__).resolve().parents[1] / "_vision_stage_eval.db"
ROLE_NAMES = ["transcriber", "y_verifier", "x_verifier", "synthesizer"]
TRANSITIONS = [
    ("transcriber", "y_verifier"),
    ("transcriber", "x_verifier"),
    ("transcriber", "synthesizer"),
    ("y_verifier", "synthesizer"),
    ("x_verifier", "synthesizer"),
]


def main() -> None:
    if not EVAL_DB.exists():
        print(f"ERROR: {EVAL_DB} not found")
        sys.exit(1)

    gt_tables = set(get_table_ids(GROUND_TRUTH_DB_PATH))
    conn = sqlite3.connect(str(EVAL_DB))
    conn.row_factory = sqlite3.Row

    # Get the run_id
    run_id = conn.execute("SELECT run_id FROM runs ORDER BY timestamp DESC LIMIT 1").fetchone()["run_id"]
    print(f"Run: {run_id}")

    # Recompute gt_comparisons
    rows = conn.execute(
        "SELECT table_id, agent_role, headers_json, rows_json, footnotes "
        "FROM agent_outputs WHERE run_id = ? AND parse_success = 1",
        (run_id,),
    ).fetchall()

    updated = 0
    for row in rows:
        table_id = row["table_id"]
        if table_id not in gt_tables:
            continue
        role = row["agent_role"]
        headers = json.loads(row["headers_json"])
        data_rows = json.loads(row["rows_json"])
        footnotes = row["footnotes"] or ""

        try:
            cmp = compare_extraction(GROUND_TRUTH_DB_PATH, table_id, headers, data_rows, footnotes)
        except (KeyError, Exception) as e:
            print(f"  SKIP {table_id}/{role}: {e}")
            continue

        conn.execute(
            "INSERT OR REPLACE INTO gt_comparisons VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (run_id, table_id, role,
             cmp.cell_accuracy_pct,
             cmp.structural_coverage_pct,
             f"{cmp.gt_shape[0]}x{cmp.gt_shape[1]}",
             f"{cmp.ext_shape[0]}x{cmp.ext_shape[1]}",
             len(cmp.matched_columns),
             len(cmp.extra_columns),
             len(cmp.missing_columns),
             len(cmp.column_splits),
             len(cmp.column_merges),
             len(cmp.matched_rows),
             len(cmp.extra_rows),
             len(cmp.missing_rows),
             len(cmp.row_splits),
             len(cmp.row_merges),
             len(cmp.cell_diffs)),
        )
        updated += 1

    conn.commit()
    print(f"Updated {updated} gt_comparisons rows")

    # Recompute stage_diffs.accuracy_delta
    delta_updated = 0
    for from_role, to_role in TRANSITIONS:
        pairs = conn.execute(
            "SELECT table_id FROM stage_diffs WHERE run_id = ? AND from_role = ? AND to_role = ?",
            (run_id, from_role, to_role),
        ).fetchall()
        for p in pairs:
            tid = p["table_id"]
            if tid not in gt_tables:
                continue
            row_from = conn.execute(
                "SELECT cell_accuracy_pct FROM gt_comparisons WHERE run_id=? AND table_id=? AND agent_role=?",
                (run_id, tid, from_role),
            ).fetchone()
            row_to = conn.execute(
                "SELECT cell_accuracy_pct FROM gt_comparisons WHERE run_id=? AND table_id=? AND agent_role=?",
                (run_id, tid, to_role),
            ).fetchone()
            if row_from and row_to and row_from[0] is not None and row_to[0] is not None:
                delta = row_to[0] - row_from[0]
                conn.execute(
                    "UPDATE stage_diffs SET accuracy_delta = ? WHERE run_id=? AND table_id=? AND from_role=? AND to_role=?",
                    (delta, run_id, tid, from_role, to_role),
                )
                delta_updated += 1

    conn.commit()
    print(f"Updated {delta_updated} stage_diffs accuracy_delta values")

    # Quick summary
    print(f"\n--- Per-stage accuracy (updated) ---")
    print(f"  {'Role':<15} {'Tables':>7} {'Mean Acc':>10} {'Median':>8}")
    for role in ROLE_NAMES:
        accs = conn.execute(
            "SELECT cell_accuracy_pct FROM gt_comparisons "
            "WHERE run_id = ? AND agent_role = ? AND cell_accuracy_pct IS NOT NULL "
            "ORDER BY cell_accuracy_pct",
            (run_id, role),
        ).fetchall()
        if accs:
            vals = [r[0] for r in accs]
            mean = sum(vals) / len(vals)
            mid = len(vals) // 2
            median = vals[mid] if len(vals) % 2 else (vals[mid - 1] + vals[mid]) / 2
            print(f"  {role:<15} {len(vals):>7} {mean:>9.1f}% {median:>7.1f}%")

    conn.close()
    print(f"\nDone. Open vision_viewer to see results.")


if __name__ == "__main__":
    main()
