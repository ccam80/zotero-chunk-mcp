"""Compare PaddleOCR engines (PP-StructureV3 vs PaddleOCR-VL-1.5) on the
stress test corpus and write results to a debug database.

Each engine runs independently — one failing does not block the other.

Usage:
    .venv/Scripts/python.exe tools/engine_compare.py

Output:
    _engine_compare.db  (SQLite — query by engine column to compare)
"""

from __future__ import annotations

import json
import logging
import sqlite3
import sys
import time
from pathlib import Path

# Ensure project root is on sys.path
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT / "tests"))

from stress_test_real_library import CORPUS, GROUND_TRUTH_DB_PATH

from zotero_chunk_rag.config import Config
from zotero_chunk_rag.feature_extraction.debug_db import create_extended_tables
from zotero_chunk_rag.feature_extraction.ground_truth import (
    compare_extraction,
    make_table_id,
)
from zotero_chunk_rag.zotero_client import ZoteroClient

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s %(name)s: %(message)s",
)

DB_PATH = _ROOT / "_engine_compare.db"

# Minimal schema (papers + tables + vision + paddle + GT diffs)
_SCHEMA = """
CREATE TABLE IF NOT EXISTS run_metadata (key TEXT PRIMARY KEY, value TEXT);

CREATE TABLE IF NOT EXISTS papers (
    item_key TEXT PRIMARY KEY,
    short_name TEXT,
    title TEXT,
    num_pages INTEGER,
    quality_grade TEXT,
    pdf_path TEXT
);

CREATE TABLE IF NOT EXISTS extracted_tables (
    item_key TEXT,
    table_index INTEGER,
    page_num INTEGER,
    caption TEXT,
    num_rows INTEGER,
    num_cols INTEGER,
    fill_rate REAL,
    headers_json TEXT,
    rows_json TEXT,
    markdown TEXT,
    bbox TEXT,
    extraction_strategy TEXT,
    table_id TEXT,
    engine TEXT DEFAULT 'vision'
);

CREATE TABLE IF NOT EXISTS ground_truth_diffs (
    table_id TEXT,
    run_id TEXT,
    engine TEXT DEFAULT 'vision',
    cell_accuracy_pct REAL,
    fuzzy_accuracy_pct REAL,
    structural_coverage_pct REAL,
    num_splits INTEGER,
    num_merges INTEGER,
    num_cell_diffs INTEGER,
    gt_shape TEXT,
    ext_shape TEXT,
    diff_json TEXT
);
"""


def _load_corpus() -> list[tuple]:
    """Load corpus items from Zotero, same as stress test Phase 1."""
    config = Config.load()
    zotero = ZoteroClient(config.zotero_data_dir)
    all_items = zotero.get_all_items_with_pdfs()
    items_by_key = {i.item_key: i for i in all_items}

    corpus_items: list[tuple] = []
    for item_key, short_name, _reason, gt in CORPUS:
        item = items_by_key.get(item_key)
        if item is None or not item.pdf_path or not item.pdf_path.exists():
            print(f"  SKIP {item_key} ({short_name}): not found or no PDF")
            continue
        corpus_items.append((item, short_name, gt))
        print(f"  [{short_name}] {item.title[:60]}")

    return corpus_items



def _precompute_captions(
    corpus_items: list[tuple],
) -> dict[str, tuple[dict[int, list], dict[int, tuple[float, float, float, float]]]]:
    """Pre-compute captions and page rects for all papers (shared across engines).

    Returns {item_key: (captions_by_page, page_rects)}.
    """
    from zotero_chunk_rag.feature_extraction.captions import find_all_captions
    import pymupdf

    cache: dict[str, tuple] = {}
    for item, short_name, _gt in corpus_items:
        doc = pymupdf.open(str(item.pdf_path))
        captions_by_page: dict[int, list] = {}
        page_rects: dict[int, tuple[float, float, float, float]] = {}
        for page_idx in range(len(doc)):
            page = doc[page_idx]
            captions_by_page[page_idx + 1] = find_all_captions(page)
            r = page.rect
            page_rects[page_idx + 1] = (r.x0, r.y0, r.x1, r.y1)
        doc.close()
        cache[item.item_key] = (captions_by_page, page_rects)
    return cache


def _run_paddle_engine(
    engine_name: str,
    corpus_items: list[tuple],
    captions_cache: dict[str, tuple],
) -> dict[str, list]:
    """Extract tables with a single PaddleOCR engine.

    Args:
        engine_name: Engine identifier (e.g. "pp_structure_v3", "paddleocr_vl_1.5").
        corpus_items: Corpus items from _load_corpus().
        captions_cache: Pre-computed captions from _precompute_captions().

    Returns {item_key: [MatchedPaddleTable]}.
    """
    from zotero_chunk_rag.feature_extraction.paddle_extract import (
        get_engine,
        match_tables_to_captions,
    )

    short_label = engine_name.replace("paddleocr_", "").replace("pp_structure_", "ppv")

    try:
        engine = get_engine(engine_name)
    except Exception as e:
        print(f"  {engine_name} init failed: {e}")
        return {}

    results: dict[str, list] = {}
    for item, short_name, _gt in corpus_items:
        print(f"  {short_label} [{short_name}]...", end=" ", flush=True)
        try:
            t0 = time.perf_counter()
            captions_by_page, page_rects = captions_cache[item.item_key]
            raw_tables = engine.extract_tables(item.pdf_path)
            matched = match_tables_to_captions(raw_tables, captions_by_page, page_rects)
            dt = time.perf_counter() - t0
            print(f"{dt:.1f}s | {len(matched)} tables")
            results[item.item_key] = matched
        except Exception as e:
            print(f"FAILED: {e}")
            results[item.item_key] = []

    return results


def _write_db(
    all_engine_results: dict[str, dict[str, list]],
) -> None:
    """Write all engines' results to the comparison database.

    Args:
        all_engine_results: {engine_name: {item_key: [MatchedPaddleTable]}}.
    """
    if DB_PATH.exists():
        DB_PATH.unlink()

    con = sqlite3.connect(str(DB_PATH))
    con.executescript(_SCHEMA)
    create_extended_tables(con)

    metadata = [("generated", time.strftime("%Y-%m-%d %H:%M:%S"))]
    for engine_name, results in all_engine_results.items():
        metadata.append((f"{engine_name}_papers", str(len(results))))
    con.executemany(
        "INSERT INTO run_metadata (key, value) VALUES (?, ?)", metadata,
    )

    has_gt = Path(GROUND_TRUTH_DB_PATH).exists()
    run_id = time.strftime("%Y-%m-%dT%H:%M:%S")

    for engine_name, engine_results in all_engine_results.items():
        for item_key, matched_tables in engine_results.items():
            for idx, mt in enumerate(matched_tables):
                table_id = make_table_id(
                    item_key, mt.caption or "", mt.page_num, idx,
                )
                non_empty = sum(1 for row in mt.rows for cell in row if cell.strip())
                total_cells = sum(len(row) for row in mt.rows)
                fill_rate = non_empty / total_cells if total_cells else 0.0

                con.execute(
                    "INSERT INTO extracted_tables "
                    "(item_key, table_index, page_num, caption, num_rows, num_cols, "
                    "fill_rate, headers_json, rows_json, markdown, bbox, "
                    "extraction_strategy, table_id, engine) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (item_key, idx, mt.page_num, mt.caption,
                     len(mt.rows), len(mt.headers) if mt.headers else 0, fill_rate,
                     json.dumps(mt.headers), json.dumps(mt.rows),
                     "", json.dumps(list(mt.bbox)) if mt.bbox else None,
                     engine_name, table_id, engine_name),
                )

                if has_gt:
                    try:
                        result = compare_extraction(
                            GROUND_TRUTH_DB_PATH, table_id, mt.headers, mt.rows,
                        )
                        con.execute(
                            "INSERT INTO ground_truth_diffs "
                            "(table_id, run_id, engine, cell_accuracy_pct, fuzzy_accuracy_pct, "
                            "structural_coverage_pct, num_splits, num_merges, "
                            "num_cell_diffs, gt_shape, ext_shape, diff_json) "
                            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                            (table_id, run_id, engine_name,
                             result.cell_accuracy_pct,
                             getattr(result, "fuzzy_accuracy_pct", None),
                             result.structural_coverage_pct,
                             len(result.column_splits) + len(result.row_splits),
                             len(result.column_merges) + len(result.row_merges),
                             len(result.cell_diffs),
                             json.dumps(result.gt_shape),
                             json.dumps(result.ext_shape),
                             json.dumps({"cell_diffs": [
                                 {"row": d.row, "col": d.col, "expected": d.expected, "actual": d.actual}
                                 for d in result.cell_diffs
                             ]})),
                        )
                    except KeyError:
                        pass

    con.commit()
    con.close()


ENGINES = ["pp_structure_v3", "paddleocr_vl_1.5"]


def main() -> None:
    print("=" * 70)
    print("  ENGINE COMPARISON: PP-StructureV3 vs PaddleOCR-VL-1.5")
    print("=" * 70)

    # Load corpus
    print("\n[1] Loading corpus from Zotero...")
    corpus_items = _load_corpus()
    corpus_items = corpus_items[2:4]  # TEMP: limit for faster iteration during development
    if not corpus_items:
        print("No corpus items found. Exiting.")
        return

    # Pre-compute captions (shared across engines)
    print("\n[2] Pre-computing captions...")
    captions_cache = _precompute_captions(corpus_items)
    print(f"  Cached captions for {len(captions_cache)} papers.")

    # Run each engine sequentially (both are GPU-bound)
    all_results: dict[str, dict[str, list]] = {}
    for engine_name in ENGINES:
        print(f"\n[3] Running {engine_name}...")
        results = _run_paddle_engine(engine_name, corpus_items, captions_cache)
        if results:
            all_results[engine_name] = results

    # Write DB
    print(f"\n[4] Writing comparison database...")
    _write_db(all_results)

    for engine_name, results in all_results.items():
        n = sum(len(v) for v in results.values())
        print(f"  {engine_name}: {n} tables")

    print(f"\n  Database: {DB_PATH}")

    # Print quick comparison
    print(f"\n[5] Quick comparison queries:")
    print(f'  sqlite3 {DB_PATH} "SELECT engine, COUNT(*), AVG(fill_rate) FROM extracted_tables GROUP BY engine"')
    print(f'  sqlite3 {DB_PATH} "SELECT engine, AVG(cell_accuracy_pct), COUNT(*) FROM ground_truth_diffs GROUP BY engine"')
    print(f'  sqlite3 {DB_PATH} "SELECT g.table_id, g.engine, g.cell_accuracy_pct FROM ground_truth_diffs g ORDER BY g.table_id, g.engine"')


if __name__ == "__main__":
    main()
