"""Vision pipeline stage-by-stage evaluation.

Runs the 4-agent vision pipeline on the stress test corpus, captures each
agent's output, compares against ground truth at every stage, and stores
everything in a SQLite database for analysis.

Usage:
    .venv/Scripts/python.exe tests/test_vision_stage_eval.py

Output:
    _vision_stage_eval.db   — SQLite with all agent outputs and GT comparisons
    _vision_stage_costs.json — per-call cost log
"""
from __future__ import annotations

import json
import logging
import sqlite3
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.zotero_chunk_rag.config import Config
from src.zotero_chunk_rag.zotero_client import ZoteroClient
from src.zotero_chunk_rag.pdf_processor import extract_document
from src.zotero_chunk_rag.feature_extraction.vision_api import (
    VisionAPI,
    TableVisionSpec,
)
from src.zotero_chunk_rag.feature_extraction.vision_extract import (
    AgentResponse,
    _parse_agent_json,
)
from src.zotero_chunk_rag.feature_extraction.ground_truth import (
    compare_extraction,
    make_table_id,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Stress test corpus (10 papers, 44 GT tables)
CORPUS_KEYS = [
    "SCPXVBLY", "XIAINRVS", "C626CYVT", "5SIZVS65", "9GKLLJH9",
    "Z9X4JVZ5", "YMWV46JA", "DPYRZTFI", "VP3NJ74M", "AQ3D94VC",
]

GT_DB = Path("tests/ground_truth.db")
EVAL_DB = Path("_vision_stage_eval.db")
COST_LOG = Path("_vision_stage_costs.json")
ROLE_NAMES = ["transcriber", "y_verifier", "x_verifier", "synthesizer"]


def _init_db(db_path: Path) -> sqlite3.Connection:
    """Create evaluation database with schema."""
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            timestamp TEXT,
            num_papers INTEGER,
            num_tables INTEGER,
            total_cost_usd REAL,
            vision_time_s REAL
        );

        CREATE TABLE IF NOT EXISTS agent_outputs (
            run_id TEXT,
            table_id TEXT,
            agent_role TEXT,
            headers_json TEXT,
            rows_json TEXT,
            footnotes TEXT,
            corrections_json TEXT,
            shape TEXT,
            parse_success INTEGER,
            num_corrections INTEGER,
            raw_response TEXT,
            PRIMARY KEY (run_id, table_id, agent_role)
        );

        CREATE TABLE IF NOT EXISTS gt_comparisons (
            run_id TEXT,
            table_id TEXT,
            agent_role TEXT,
            cell_accuracy_pct REAL,
            structural_coverage_pct REAL,
            gt_shape TEXT,
            ext_shape TEXT,
            num_matched_cols INTEGER,
            num_extra_cols INTEGER,
            num_missing_cols INTEGER,
            num_col_splits INTEGER,
            num_col_merges INTEGER,
            num_matched_rows INTEGER,
            num_extra_rows INTEGER,
            num_missing_rows INTEGER,
            num_row_splits INTEGER,
            num_row_merges INTEGER,
            num_cell_diffs INTEGER,
            PRIMARY KEY (run_id, table_id, agent_role)
        );

        CREATE TABLE IF NOT EXISTS stage_diffs (
            run_id TEXT,
            table_id TEXT,
            from_role TEXT,
            to_role TEXT,
            shape_changed INTEGER,
            num_header_diffs INTEGER,
            num_cell_diffs INTEGER,
            cells_added INTEGER,
            cells_removed INTEGER,
            accuracy_delta REAL,
            PRIMARY KEY (run_id, table_id, from_role, to_role)
        );

        CREATE TABLE IF NOT EXISTS correction_log (
            run_id TEXT,
            table_id TEXT,
            agent_role TEXT,
            correction_index INTEGER,
            correction_text TEXT
        );
    """)
    return conn


def _extract_corrections(resp: AgentResponse) -> list[str]:
    """Extract corrections list from agent response."""
    if not resp.parse_success or not resp.raw_response:
        return []
    parsed = _parse_agent_json(resp.raw_response)
    if parsed and isinstance(parsed.get("corrections"), list):
        return [str(c) for c in parsed["corrections"]]
    return []


def _cell_diff_count(a: AgentResponse, b: AgentResponse) -> dict:
    """Compare two agent outputs cell-by-cell."""
    if not a.parse_success or not b.parse_success:
        return {"shape_changed": 1, "num_header_diffs": 0, "num_cell_diffs": 0,
                "cells_added": 0, "cells_removed": 0}

    shape_changed = int(a.raw_shape != b.raw_shape)

    # Header diffs
    h_diffs = 0
    for i in range(min(len(a.headers), len(b.headers))):
        if a.headers[i].strip() != b.headers[i].strip():
            h_diffs += 1
    h_diffs += abs(len(a.headers) - len(b.headers))

    # Cell diffs
    cell_diffs = 0
    cells_added = 0
    cells_removed = 0
    min_rows = min(len(a.rows), len(b.rows))
    for r in range(min_rows):
        min_cols = min(len(a.rows[r]), len(b.rows[r]))
        for c in range(min_cols):
            if a.rows[r][c].strip() != b.rows[r][c].strip():
                cell_diffs += 1
        # Extra/missing cols in this row
        if len(b.rows[r]) > len(a.rows[r]):
            cells_added += len(b.rows[r]) - len(a.rows[r])
        elif len(a.rows[r]) > len(b.rows[r]):
            cells_removed += len(a.rows[r]) - len(b.rows[r])

    # Extra/missing rows
    if len(b.rows) > len(a.rows):
        for r in range(min_rows, len(b.rows)):
            cells_added += len(b.rows[r])
    elif len(a.rows) > len(b.rows):
        for r in range(min_rows, len(a.rows)):
            cells_removed += len(a.rows[r])

    return {
        "shape_changed": shape_changed,
        "num_header_diffs": h_diffs,
        "num_cell_diffs": cell_diffs,
        "cells_added": cells_added,
        "cells_removed": cells_removed,
    }


def main():
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    print(f"\n{'='*70}")
    print(f"Vision Stage Evaluation — run {run_id}")
    print(f"{'='*70}")

    cfg = Config.load()
    zc = ZoteroClient(cfg.zotero_data_dir)
    all_items = zc.get_all_items_with_pdfs()
    items_by_key = {i.item_key: i for i in all_items}

    papers = []
    for key in CORPUS_KEYS:
        item = items_by_key.get(key)
        if item and item.pdf_path and item.pdf_path.exists():
            papers.append(item)
        else:
            logger.warning("Skipping %s", key)

    print(f"Papers: {len(papers)}, GT tables: 44")

    # Phase 1: Extract tables
    print(f"\n--- Phase 1: Table extraction ---")
    import pymupdf

    specs: list[TableVisionSpec] = []
    t0 = time.time()

    for item in papers:
        try:
            extraction = extract_document(
                item.pdf_path, write_images=False,
                ocr_language=cfg.ocr_language,
            )
        except Exception as e:
            logger.warning("Extraction failed for %s: %s", item.item_key, e)
            continue

        real_tables = [t for t in extraction.tables if not t.artifact_type]
        doc = pymupdf.open(str(item.pdf_path))
        try:
            for tab in real_tables:
                page_idx = tab.page_num - 1
                if page_idx < 0 or page_idx >= len(doc):
                    continue
                page = doc[page_idx]
                raw_text = page.get_text("text", clip=pymupdf.Rect(*tab.bbox))
                table_id = make_table_id(
                    item.item_key, tab.caption, tab.page_num, tab.table_index,
                )
                specs.append(TableVisionSpec(
                    table_id=table_id,
                    pdf_path=item.pdf_path,
                    page_num=tab.page_num,
                    bbox=tab.bbox,
                    raw_text=raw_text,
                    caption=tab.caption,
                ))
        finally:
            doc.close()

    extraction_time = time.time() - t0
    print(f"Tables: {len(specs)} in {extraction_time:.1f}s")

    # Phase 2: Vision pipeline
    print(f"\n--- Phase 2: Vision extraction ---")
    api_key = cfg.anthropic_api_key
    if not api_key:
        import os
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if COST_LOG.exists():
        COST_LOG.unlink()

    api = VisionAPI(
        api_key=api_key,
        model=cfg.vision_model,
        cost_log_path=COST_LOG,
        cache=True,
        dpi=cfg.vision_dpi,
        padding_px=cfg.vision_padding_px,
    )

    t1 = time.time()
    results = api.extract_tables_sync(specs, batch=True)
    vision_time = time.time() - t1
    total_cost = api.session_cost

    print(f"Done: {vision_time:.1f}s, ${total_cost:.4f}")

    # Phase 3: Store results and evaluate
    print(f"\n--- Phase 3: Evaluation ---")
    conn = _init_db(EVAL_DB)

    conn.execute(
        "INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?)",
        (run_id, datetime.now(timezone.utc).isoformat(),
         len(papers), len(specs), total_cost, vision_time),
    )

    gt_tables = set()
    if GT_DB.exists():
        gt_conn = sqlite3.connect(str(GT_DB))
        gt_tables = {r[0] for r in gt_conn.execute(
            "SELECT table_id FROM ground_truth_tables"
        ).fetchall()}
        gt_conn.close()

    succeeded = 0
    failed = 0

    for spec, vision_result in results:
        if vision_result.error or not vision_result.agent_responses:
            failed += 1
            continue

        responses = vision_result.agent_responses
        # Pad to 4 if fewer (e.g., early failure)
        while len(responses) < 4:
            responses.append(AgentResponse(
                headers=[], rows=[], footnotes="",
                table_label=None, is_incomplete=False,
                incomplete_reason="", raw_shape=(0, 0),
                parse_success=False, raw_response="",
            ))

        succeeded += 1

        # Store each agent's output
        for i, role in enumerate(ROLE_NAMES):
            resp = responses[i]
            corrections = _extract_corrections(resp)

            conn.execute(
                "INSERT OR REPLACE INTO agent_outputs VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (run_id, spec.table_id, role,
                 json.dumps(resp.headers, ensure_ascii=False),
                 json.dumps(resp.rows, ensure_ascii=False),
                 resp.footnotes,
                 json.dumps(corrections, ensure_ascii=False),
                 f"{resp.raw_shape[0]}x{resp.raw_shape[1]}",
                 int(resp.parse_success),
                 len(corrections),
                 resp.raw_response),
            )

            # Log individual corrections
            for ci, ct in enumerate(corrections):
                conn.execute(
                    "INSERT INTO correction_log VALUES (?,?,?,?,?)",
                    (run_id, spec.table_id, role, ci, ct),
                )

            # GT comparison
            if spec.table_id in gt_tables and resp.parse_success and resp.headers:
                try:
                    cmp = compare_extraction(
                        GT_DB, spec.table_id,
                        resp.headers, resp.rows, resp.footnotes,
                    )
                    conn.execute(
                        "INSERT OR REPLACE INTO gt_comparisons VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (run_id, spec.table_id, role,
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
                except (KeyError, Exception) as e:
                    logger.debug("GT comparison failed for %s/%s: %s",
                                 spec.table_id, role, e)

        # Stage-to-stage diffs
        transcriber = responses[0]
        pairs = [
            ("transcriber", "y_verifier", 0, 1),
            ("transcriber", "x_verifier", 0, 2),
            ("transcriber", "synthesizer", 0, 3),
            ("y_verifier", "synthesizer", 1, 3),
            ("x_verifier", "synthesizer", 2, 3),
        ]
        for from_role, to_role, fi, ti in pairs:
            diff = _cell_diff_count(responses[fi], responses[ti])
            # Get accuracy delta if both have GT comparisons
            acc_delta = None
            if spec.table_id in gt_tables:
                row_from = conn.execute(
                    "SELECT cell_accuracy_pct FROM gt_comparisons WHERE run_id=? AND table_id=? AND agent_role=?",
                    (run_id, spec.table_id, from_role),
                ).fetchone()
                row_to = conn.execute(
                    "SELECT cell_accuracy_pct FROM gt_comparisons WHERE run_id=? AND table_id=? AND agent_role=?",
                    (run_id, spec.table_id, to_role),
                ).fetchone()
                if row_from and row_to and row_from[0] is not None and row_to[0] is not None:
                    acc_delta = row_to[0] - row_from[0]

            conn.execute(
                "INSERT OR REPLACE INTO stage_diffs VALUES (?,?,?,?,?,?,?,?,?,?)",
                (run_id, spec.table_id, from_role, to_role,
                 diff["shape_changed"], diff["num_header_diffs"],
                 diff["num_cell_diffs"], diff["cells_added"],
                 diff["cells_removed"], acc_delta),
            )

    conn.commit()

    # Phase 4: Report
    print(f"\n{'='*70}")
    print(f"RESULTS — run {run_id}")
    print(f"{'='*70}")
    print(f"Tables: {len(specs)} ({succeeded} ok, {failed} failed)")
    print(f"Vision time: {vision_time:.1f}s, Cost: ${total_cost:.4f}")

    # Per-role correction rates
    print(f"\n--- Correction Rates ---")
    for role in ROLE_NAMES[1:]:  # skip transcriber
        row = conn.execute("""
            SELECT COUNT(*), SUM(CASE WHEN num_corrections > 0 THEN 1 ELSE 0 END),
                   SUM(num_corrections)
            FROM agent_outputs WHERE run_id = ? AND agent_role = ?
        """, (run_id, role)).fetchone()
        total, corrected, total_corr = row
        pct = 100 * corrected / total if total else 0
        print(f"  {role:<15} {corrected:>3}/{total} tables corrected ({pct:.0f}%), {total_corr} total corrections")

    # GT accuracy per stage
    print(f"\n--- GT Accuracy by Stage ---")
    print(f"  {'Role':<15} {'Tables':>7} {'Mean Acc':>10} {'Median':>8} {'Min':>8} {'Max':>8}")
    for role in ROLE_NAMES:
        rows = conn.execute("""
            SELECT cell_accuracy_pct FROM gt_comparisons
            WHERE run_id = ? AND agent_role = ? AND cell_accuracy_pct IS NOT NULL
            ORDER BY cell_accuracy_pct
        """, (run_id, role)).fetchall()
        if rows:
            accs = [r[0] for r in rows]
            mean = sum(accs) / len(accs)
            median = accs[len(accs) // 2]
            print(f"  {role:<15} {len(accs):>7} {mean:>9.1f}% {median:>7.1f}% {min(accs):>7.1f}% {max(accs):>7.1f}%")
        else:
            print(f"  {role:<15}       0         -        -        -        -")

    # Stage-to-stage accuracy deltas
    print(f"\n--- Stage Accuracy Deltas (positive = improvement) ---")
    for from_r, to_r in [("transcriber", "y_verifier"), ("transcriber", "x_verifier"),
                          ("transcriber", "synthesizer")]:
        rows = conn.execute("""
            SELECT accuracy_delta FROM stage_diffs
            WHERE run_id = ? AND from_role = ? AND to_role = ? AND accuracy_delta IS NOT NULL
        """, (run_id, from_r, to_r)).fetchall()
        if rows:
            deltas = [r[0] for r in rows]
            improved = sum(1 for d in deltas if d > 0.5)
            hurt = sum(1 for d in deltas if d < -0.5)
            unchanged = len(deltas) - improved - hurt
            mean_d = sum(deltas) / len(deltas)
            print(f"  {from_r} -> {to_r}:")
            print(f"    {improved} improved, {unchanged} unchanged, {hurt} hurt (mean delta: {mean_d:+.1f}%)")

    # Synthesizer agreement
    print(f"\n--- Synthesizer Agreement with Verifiers ---")
    for v_role in ["y_verifier", "x_verifier"]:
        rows = conn.execute("""
            SELECT sd.table_id, sd.shape_changed, sd.num_cell_diffs, sd.num_header_diffs
            FROM stage_diffs sd
            WHERE sd.run_id = ? AND sd.from_role = ? AND sd.to_role = 'synthesizer'
        """, (run_id, v_role)).fetchall()
        agreed = sum(1 for r in rows if r[1] == 0 and r[2] == 0 and r[3] == 0)
        disagreed = len(rows) - agreed
        print(f"  {v_role} vs synthesizer: {agreed} agree, {disagreed} disagree ({100*agreed/len(rows):.0f}% agreement)" if rows else f"  {v_role}: no data")

    # Tables where synthesizer diverged from verifier AND was closer to GT
    print(f"\n--- Did Synthesizer Improve Over Best Verifier? ---")
    rows = conn.execute("""
        SELECT
            g_t.table_id,
            g_y.cell_accuracy_pct AS y_acc,
            g_x.cell_accuracy_pct AS x_acc,
            g_s.cell_accuracy_pct AS synth_acc
        FROM gt_comparisons g_s
        JOIN gt_comparisons g_y ON g_y.run_id = g_s.run_id AND g_y.table_id = g_s.table_id AND g_y.agent_role = 'y_verifier'
        JOIN gt_comparisons g_x ON g_x.run_id = g_s.run_id AND g_x.table_id = g_s.table_id AND g_x.agent_role = 'x_verifier'
        JOIN gt_comparisons g_t ON g_t.run_id = g_s.run_id AND g_t.table_id = g_s.table_id AND g_t.agent_role = 'transcriber'
        WHERE g_s.run_id = ? AND g_s.agent_role = 'synthesizer'
    """, (run_id,)).fetchall()

    synth_better = 0
    synth_worse = 0
    synth_same = 0
    for tid, y_acc, x_acc, s_acc in rows:
        best_v = max(y_acc or 0, x_acc or 0)
        if s_acc > best_v + 0.5:
            synth_better += 1
        elif s_acc < best_v - 0.5:
            synth_worse += 1
        else:
            synth_same += 1

    print(f"  Synth > best verifier: {synth_better}")
    print(f"  Synth = best verifier: {synth_same}")
    print(f"  Synth < best verifier: {synth_worse}")

    conn.close()
    print(f"\nDatabase: {EVAL_DB.resolve()}")
    print(f"Cost log: {COST_LOG.resolve()}")
    print(f"Done.")


if __name__ == "__main__":
    main()
