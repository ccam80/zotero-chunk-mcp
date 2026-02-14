"""Compare find_tables() strategies across the full stress-test corpus.

For each paper × strategy, count:
- tables found
- total cells / non-empty cells
- garbled cells
- table dimensions

This tells us whether a different strategy eliminates garbling
and whether it changes table detection for better or worse.
"""
from __future__ import annotations
import sys, time
sys.path.insert(0, "src")

import pymupdf
from zotero_chunk_rag.pdf_processor import (
    _detect_garbled_spacing,
    _merge_over_divided_rows,
)
from zotero_chunk_rag.zotero_client import ZoteroClient
from zotero_chunk_rag.config import Config

CORPUS = [
    ("SCPXVBLY", "active-inference-tutorial"),
    ("XIAINRVS", "huang-emd-1998"),
    ("C626CYVT", "hallett-tms-primer"),
    ("5SIZVS65", "laird-fick-polyps"),
    ("9GKLLJH9", "helm-coregulation"),
    ("Z9X4JVZ5", "roland-emg-filter"),
    ("YMWV46JA", "friston-life"),
    ("DPYRZTFI", "yang-ppv-meta"),
    ("VP3NJ74M", "fortune-impedance"),
    ("AQ3D94VC", "reyes-lf-hrv"),
]

STRATEGIES = [
    ("lines", {}),
    ("lines_strict", {"strategy": "lines_strict"}),
    ("text", {"strategy": "text"}),
    # Mixed: lines for columns, text for rows
    ("lines+text", {"vertical_strategy": "lines", "horizontal_strategy": "text"}),
]

config = Config.load()
zotero = ZoteroClient(config.zotero_data_dir)
all_items = zotero.get_all_items_with_pdfs()
items_by_key = {i.item_key: i for i in all_items}


def extract_tables_with_strategy(doc, strategy_kwargs):
    """Run find_tables with given strategy on all pages, return raw table data."""
    results = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        try:
            tab_finder = page.find_tables(**strategy_kwargs)
        except Exception as e:
            results.append({"page": page_num, "error": str(e)})
            continue
        for tab in tab_finder.tables:
            raw_rows = tab.extract()
            # Clean None -> ""
            rows = [[cell if cell else "" for cell in row] for row in raw_rows]
            rows = _merge_over_divided_rows(rows)
            try:
                bbox = tab.bbox
            except (ValueError, Exception):
                bbox = None
            results.append({
                "page": page_num,
                "rows": rows,
                "n_rows": len(rows),
                "n_cols": max(len(r) for r in rows) if rows else 0,
                "bbox": bbox,
            })
    return results


def analyze_tables(tables):
    """Compute quality metrics for a list of extracted tables."""
    total_cells = 0
    non_empty = 0
    garbled = 0
    garbled_details = []
    n_1x1 = 0

    for ti, tab in enumerate(tables):
        if "error" in tab:
            continue
        rows = tab["rows"]
        if tab["n_rows"] == 1 and tab["n_cols"] == 1:
            n_1x1 += 1
        for ri, row in enumerate(rows):
            for ci, cell in enumerate(row):
                total_cells += 1
                if cell.strip():
                    non_empty += 1
                g, reason = _detect_garbled_spacing(cell)
                if g:
                    garbled += 1
                    garbled_details.append(
                        f"  t{ti}[{ri},{ci}] p{tab['page']}: "
                        f"{cell[:60]}{'...' if len(cell) > 60 else ''}"
                    )
    return {
        "n_tables": len([t for t in tables if "error" not in t]),
        "total_cells": total_cells,
        "non_empty": non_empty,
        "garbled": garbled,
        "garbled_details": garbled_details,
        "n_1x1": n_1x1,
    }


# ---- Run experiment ----
print(f"{'Paper':<28} {'Strategy':<14} {'Tables':>6} {'Cells':>6} "
      f"{'Non-empty':>9} {'Garbled':>7} {'1x1':>4} {'Time':>6}")
print("-" * 90)

all_results = {}

for item_key, short_name in CORPUS:
    item = items_by_key.get(item_key)
    if not item or not item.pdf_path:
        print(f"{short_name:<28} SKIP — not found")
        continue

    doc = pymupdf.open(str(item.pdf_path))
    paper_results = {}

    for strat_name, strat_kwargs in STRATEGIES:
        t0 = time.perf_counter()
        tables = extract_tables_with_strategy(doc, strat_kwargs)
        elapsed = time.perf_counter() - t0
        metrics = analyze_tables(tables)
        paper_results[strat_name] = {**metrics, "time": elapsed, "tables_raw": tables}

        pct = (metrics["non_empty"] / metrics["total_cells"] * 100
               if metrics["total_cells"] else 0)
        garbled_flag = f" !!!" if metrics["garbled"] > 0 else ""
        print(f"{short_name:<28} {strat_name:<14} {metrics['n_tables']:>6} "
              f"{metrics['total_cells']:>6} {metrics['non_empty']:>5} ({pct:4.0f}%) "
              f"{metrics['garbled']:>5}{garbled_flag}  {metrics['n_1x1']:>3} "
              f"{elapsed:>5.1f}s")

    doc.close()
    all_results[short_name] = paper_results
    print()

# ---- Summary: garbled cells by strategy ----
print("\n" + "=" * 70)
print("GARBLED CELL SUMMARY BY STRATEGY")
print("=" * 70)
for strat_name, _ in STRATEGIES:
    total_garbled = sum(
        r[strat_name]["garbled"] for r in all_results.values()
        if strat_name in r
    )
    total_tables = sum(
        r[strat_name]["n_tables"] for r in all_results.values()
        if strat_name in r
    )
    total_cells = sum(
        r[strat_name]["total_cells"] for r in all_results.values()
        if strat_name in r
    )
    print(f"  {strat_name:<14}: {total_garbled:>3} garbled cells across "
          f"{total_tables} tables ({total_cells} cells)")

# ---- Show garbled details per strategy ----
print("\n" + "=" * 70)
print("GARBLED CELL DETAILS")
print("=" * 70)
for strat_name, _ in STRATEGIES:
    details = []
    for paper_name, paper_res in all_results.items():
        if strat_name in paper_res and paper_res[strat_name]["garbled_details"]:
            for d in paper_res[strat_name]["garbled_details"]:
                details.append(f"  [{paper_name}] {d}")
    if details:
        print(f"\n--- {strat_name} ({len(details)} garbled) ---")
        for d in details:
            print(d)
    else:
        print(f"\n--- {strat_name}: NO garbled cells ---")

# ---- Per-paper strategy winner ----
print("\n" + "=" * 70)
print("BEST STRATEGY PER PAPER (fewest garbled, then most non-empty)")
print("=" * 70)
for paper_name, paper_res in all_results.items():
    best = min(
        paper_res.items(),
        key=lambda kv: (kv[1]["garbled"], -kv[1]["non_empty"])
    )
    current = paper_res.get("lines", {})
    print(f"  {paper_name:<28} best={best[0]:<14} "
          f"garbled={best[1]['garbled']} tables={best[1]['n_tables']} "
          f"(current: garbled={current.get('garbled', '?')} "
          f"tables={current.get('n_tables', '?')})")
