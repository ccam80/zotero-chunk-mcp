"""Batch API integration test — compare against async path.

Runs the same extraction pipeline but using batch=True (Anthropic Batch API).
Use a smaller corpus to keep cost down while verifying the path works.

Usage:
    .venv/Scripts/python.exe tests/test_vision_batch_integration.py
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.zotero_chunk_rag.config import Config
from src.zotero_chunk_rag.zotero_client import ZoteroClient
from src.zotero_chunk_rag.pdf_processor import extract_document
from src.zotero_chunk_rag.feature_extraction.vision_api import (
    VisionAPI,
    TableVisionSpec,
)
from src.zotero_chunk_rag.feature_extraction.ground_truth import make_table_id

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Smaller corpus: 5 papers with known tables
BATCH_CORPUS = [
    "5SIZVS65",  # laird-fick-polyps (1 table)
    "9GKLLJH9",  # helm-coregulation (tables)
    "DPYRZTFI",  # yang-ppv-meta (tables)
    "VP3NJ74M",  # fortune-impedance (tables)
    "AQ3D94VC",  # reyes-lf-hrv (tables)
]


def main():
    cfg = Config.load()
    zc = ZoteroClient(cfg.zotero_data_dir)
    all_items = zc.get_all_items_with_pdfs()
    items_by_key = {i.item_key: i for i in all_items}

    papers = []
    for key in BATCH_CORPUS:
        item = items_by_key.get(key)
        if item and item.pdf_path and item.pdf_path.exists():
            papers.append(item)
        else:
            logger.warning("Skipping %s: not found or no PDF", key)

    print(f"\n{'='*70}")
    print(f"Batch API Integration Test")
    print(f"{'='*70}")
    print(f"Papers: {len(papers)}")

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
        if not real_tables:
            continue

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
    print(f"Extracted {len(specs)} tables from {len(papers)} papers in {extraction_time:.1f}s")

    if not specs:
        print("No tables found — aborting.")
        return

    # Phase 2: Batch vision extraction
    print(f"\n--- Phase 2: Batch API vision extraction ---")
    api_key = cfg.anthropic_api_key
    if not api_key:
        import os
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("ERROR: No ANTHROPIC_API_KEY set")
        return

    cost_log = Path("_vision_batch_costs.json")
    api = VisionAPI(
        api_key=api_key,
        model=cfg.vision_model,
        cost_log_path=cost_log,
        cache=True,
        dpi=cfg.vision_dpi,
        padding_px=cfg.vision_padding_px,
    )

    t1 = time.time()
    print(f"Submitting {len(specs)} tables via Batch API (3 stages)...")
    print(f"This may take several minutes — Batch API processes asynchronously.")
    results = api.extract_tables_sync(specs, batch=True)
    vision_time = time.time() - t1

    # Phase 3: Results
    print(f"\n--- Phase 3: Results ---")
    total = len(results)
    succeeded = sum(1 for _, vr in results if vr.error is None and vr.consensus is not None)
    failed = total - succeeded
    total_cost = api.session_cost

    print(f"\n{'='*70}")
    print(f"BATCH API SUMMARY")
    print(f"{'='*70}")
    print(f"Papers:           {len(papers)}")
    print(f"Tables:           {total}")
    print(f"Succeeded:        {succeeded} ({100*succeeded/total:.1f}%)" if total else "")
    print(f"Failed:           {failed}")
    print(f"Extraction time:  {extraction_time:.1f}s")
    print(f"Vision time:      {vision_time:.1f}s ({vision_time/total:.1f}s/table)" if total else "")
    print(f"Total cost:       ${total_cost:.4f} (${total_cost/total:.4f}/table)" if total else "")

    # Cache analysis
    if cost_log.exists():
        with open(cost_log, encoding="utf-8") as f:
            entries = json.load(f)

        roles = ["transcriber", "y_verifier", "x_verifier", "synthesizer"]
        print(f"\n--- Cache Analysis ---")
        print(f"{'Role':<15} {'Calls':>6} {'CacheWrite':>12} {'CacheRead':>12} {'Input':>10} {'Output':>10}")
        for role in roles:
            re = [e for e in entries if e.get("agent_role") == role]
            cw = sum(e.get("cache_write_tokens", 0) for e in re)
            cr = sum(e.get("cache_read_tokens", 0) for e in re)
            inp = sum(e.get("input_tokens", 0) for e in re)
            out = sum(e.get("output_tokens", 0) for e in re)
            print(f"{role:<15} {len(re):>6} {cw:>12} {cr:>12} {inp:>10} {out:>10}")

        prices = {"input": 1.0, "output": 5.0, "cache_write": 1.25, "cache_read": 0.10}
        actual = sum(
            (e.get("input_tokens", 0) * prices["input"]
             + e.get("output_tokens", 0) * prices["output"]
             + e.get("cache_write_tokens", 0) * prices["cache_write"]
             + e.get("cache_read_tokens", 0) * prices["cache_read"])
            / 1_000_000 for e in entries
        )
        # Batch API gets 50% discount on base price
        batch_no_cache = sum(
            ((e.get("input_tokens", 0) + e.get("cache_write_tokens", 0) + e.get("cache_read_tokens", 0))
             * prices["input"] * 0.5
             + e.get("output_tokens", 0) * prices["output"] * 0.5)
            / 1_000_000 for e in entries
        )
        async_no_cache = sum(
            ((e.get("input_tokens", 0) + e.get("cache_write_tokens", 0) + e.get("cache_read_tokens", 0))
             * prices["input"]
             + e.get("output_tokens", 0) * prices["output"])
            / 1_000_000 for e in entries
        )

        print(f"\nBatch cost (with cache):    ${actual:.4f}")
        print(f"Batch cost (no cache):      ${batch_no_cache:.4f}")
        print(f"Async cost (no cache):      ${async_no_cache:.4f}")

    # Per-table results
    print(f"\n--- Per-Table Results ---")
    for spec, vr in results:
        ok = "OK" if vr.error is None and vr.consensus else "FAIL"
        hdrs = len(vr.consensus.headers) if vr.consensus else 0
        rows = len(vr.consensus.rows) if vr.consensus else 0
        err = (vr.error or "")[:50]
        print(f"  {spec.table_id:<35} {ok:<5} {hdrs}h x {rows}r  {err}")

    failures = [(s, vr) for s, vr in results if vr.error or vr.consensus is None]
    if failures:
        print(f"\n--- Failures ({len(failures)}) ---")
        for s, vr in failures:
            print(f"  {s.table_id}: {vr.error}")

    print(f"\nCost log: {cost_log.resolve()}")
    print(f"Done.")


if __name__ == "__main__":
    main()
