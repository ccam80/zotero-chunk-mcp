"""End-to-end vision pipeline integration test.

Tests VisionAPI on real papers from the Zotero library, measuring:
- Extraction success rate
- Cache hit rates (breakpoint 1: system, breakpoint 2: image)
- Total cost
- Per-table quality (headers, rows, fill rate)

Usage:
    .venv/Scripts/python.exe tests/test_vision_indexer_integration.py
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path

# Add project root to path
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

# Use the stress test corpus (10 papers with known tables)
CORPUS_KEYS = [
    "SCPXVBLY",  # active-inference-tutorial
    "XIAINRVS",  # huang-emd-1998
    "C626CYVT",  # hallett-tms-primer
    "5SIZVS65",  # laird-fick-polyps
    "9GKLLJH9",  # helm-coregulation
    "Z9X4JVZ5",  # roland-emg-filter
    "YMWV46JA",  # friston-life
    "DPYRZTFI",  # yang-ppv-meta
    "VP3NJ74M",  # fortune-impedance
    "AQ3D94VC",  # reyes-lf-hrv
]

# Add 10 more papers for broader coverage
EXTRA_KEYS = [
    "UHSPFNS3",  # vagal tone preterm
    "5LY5DK3R",  # PPG variability
    "E2PC978X",  # improved HRV method
    "8QZ8IQFC",  # surgeon stress HRV
    "GMVKXTRD",  # peak detection HRV
    "HGHR7F4P",  # premature beats fractal
    "JL2AFCL6",  # cardiac regulation
    "QRN8G52V",  # subjective stress cortisol
    "XHS29V4K",  # infant emotion regulation
    "EGXBPFLE",  # editing R-R intervals
]


@dataclass
class TableResult:
    table_id: str
    paper_key: str
    caption: str | None
    page_num: int
    success: bool
    n_headers: int
    n_rows: int
    fill_rate: float
    error: str | None
    timing_ms: float


def main():
    cfg = Config.load()
    zc = ZoteroClient(cfg.zotero_data_dir)
    all_items = zc.get_all_items_with_pdfs()
    items_by_key = {i.item_key: i for i in all_items}

    # Resolve papers
    use_keys = CORPUS_KEYS + EXTRA_KEYS
    papers = []
    for key in use_keys:
        item = items_by_key.get(key)
        if item and item.pdf_path and item.pdf_path.exists():
            papers.append(item)
        else:
            logger.warning("Skipping %s: not found or no PDF", key)

    print(f"\n{'='*70}")
    print(f"Vision Pipeline Integration Test")
    print(f"{'='*70}")
    print(f"Papers: {len(papers)}")

    # Phase 1: Extract tables from each paper
    print(f"\n--- Phase 1: Table extraction ---")
    import pymupdf

    specs: list[TableVisionSpec] = []
    spec_meta: list[dict] = []
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
                spec_meta.append({
                    "paper_key": item.item_key,
                    "caption": tab.caption,
                    "page_num": tab.page_num,
                    "pipeline_headers": tab.headers,
                    "pipeline_rows": len(tab.rows),
                    "pipeline_fill": _fill_rate(tab.headers, tab.rows),
                })
        finally:
            doc.close()

    extraction_time = time.time() - t0
    print(f"Extracted {len(specs)} tables from {len(papers)} papers in {extraction_time:.1f}s")

    if not specs:
        print("No tables found — aborting.")
        return

    # Show cost estimate before proceeding
    est_calls = len(specs) * 4  # 4 agents per table
    est_cost_no_cache = len(specs) * 0.026  # ~$0.026 per table uncached
    est_cost_cached = len(specs) * 0.014  # ~$0.014 per table with caching
    print(f"\nEstimated API calls: {est_calls}")
    print(f"Estimated cost: ${est_cost_cached:.2f} - ${est_cost_no_cache:.2f}")

    # Phase 2: Vision extraction
    print(f"\n--- Phase 2: Vision extraction ---")
    api_key = cfg.anthropic_api_key
    if not api_key:
        import os
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("ERROR: No ANTHROPIC_API_KEY set")
        return

    cost_log = Path("_vision_integration_costs.json")
    api = VisionAPI(
        api_key=api_key,
        model=cfg.vision_model,
        cost_log_path=cost_log,
        cache=True,
        dpi=cfg.vision_dpi,
        padding_px=cfg.vision_padding_px,
    )

    t1 = time.time()
    results = api.extract_tables_sync(specs, batch=False)
    vision_time = time.time() - t1

    # Phase 3: Analyze results
    print(f"\n--- Phase 3: Results ---")
    table_results: list[TableResult] = []
    for (spec, vision_res), meta in zip(results, spec_meta):
        success = (
            vision_res.error is None
            and vision_res.consensus is not None
            and len(vision_res.consensus.headers) > 0
        )
        if success:
            c = vision_res.consensus
            n_h = len(c.headers)
            n_r = len(c.rows)
            fill = _fill_rate(c.headers, c.rows)
        else:
            n_h = n_r = 0
            fill = 0.0

        table_results.append(TableResult(
            table_id=spec.table_id,
            paper_key=meta["paper_key"],
            caption=meta["caption"],
            page_num=meta["page_num"],
            success=success,
            n_headers=n_h,
            n_rows=n_r,
            fill_rate=fill,
            error=vision_res.error,
            timing_ms=vision_res.timing_ms,
        ))

    # Summary
    total = len(table_results)
    succeeded = sum(1 for r in table_results if r.success)
    failed = total - succeeded
    total_cost = api.session_cost

    print(f"\n{'='*70}")
    print(f"SUMMARY")
    print(f"{'='*70}")
    print(f"Papers:           {len(papers)}")
    print(f"Tables:           {total}")
    print(f"Succeeded:        {succeeded} ({100*succeeded/total:.1f}%)")
    print(f"Failed:           {failed}")
    print(f"Extraction time:  {extraction_time:.1f}s")
    print(f"Vision time:      {vision_time:.1f}s ({vision_time/total:.1f}s/table)")
    print(f"Total cost:       ${total_cost:.4f} (${total_cost/total:.4f}/table)")

    # Cache analysis from cost log
    if cost_log.exists():
        with open(cost_log, encoding="utf-8") as f:
            entries = json.load(f)
        total_cache_write = sum(e.get("cache_write_tokens", 0) for e in entries)
        total_cache_read = sum(e.get("cache_read_tokens", 0) for e in entries)
        total_input = sum(e.get("input_tokens", 0) for e in entries)
        total_output = sum(e.get("output_tokens", 0) for e in entries)

        # Per-role cache analysis
        roles = ["transcriber", "y_verifier", "x_verifier", "synthesizer"]
        print(f"\n--- Cache Analysis ---")
        print(f"{'Role':<15} {'Calls':>6} {'CacheWrite':>12} {'CacheRead':>12} {'Input':>10} {'Output':>10}")
        for role in roles:
            role_entries = [e for e in entries if e.get("agent_role") == role]
            cw = sum(e.get("cache_write_tokens", 0) for e in role_entries)
            cr = sum(e.get("cache_read_tokens", 0) for e in role_entries)
            inp = sum(e.get("input_tokens", 0) for e in role_entries)
            out = sum(e.get("output_tokens", 0) for e in role_entries)
            print(f"{role:<15} {len(role_entries):>6} {cw:>12} {cr:>12} {inp:>10} {out:>10}")

        print(f"\nTotal tokens: input={total_input}, output={total_output}, "
              f"cache_write={total_cache_write}, cache_read={total_cache_read}")

        if total_cache_write + total_cache_read + total_input > 0:
            cache_hit_rate = total_cache_read / (total_cache_write + total_cache_read + total_input)
            print(f"Cache hit rate: {100*cache_hit_rate:.1f}%")

        # Compute theoretical no-cache cost for comparison
        # All tokens at full input price instead of cache_read discount
        prices = {"input": 1.0, "output": 5.0, "cache_write": 1.25, "cache_read": 0.10}
        actual_cost = sum(
            (e.get("input_tokens", 0) * prices["input"]
             + e.get("output_tokens", 0) * prices["output"]
             + e.get("cache_write_tokens", 0) * prices["cache_write"]
             + e.get("cache_read_tokens", 0) * prices["cache_read"])
            / 1_000_000
            for e in entries
        )
        no_cache_cost = sum(
            ((e.get("input_tokens", 0)
              + e.get("cache_write_tokens", 0)
              + e.get("cache_read_tokens", 0)) * prices["input"]
             + e.get("output_tokens", 0) * prices["output"])
            / 1_000_000
            for e in entries
        )
        print(f"\nActual cost:    ${actual_cost:.4f}")
        print(f"No-cache cost:  ${no_cache_cost:.4f}")
        if no_cache_cost > 0:
            savings = (no_cache_cost - actual_cost) / no_cache_cost
            print(f"Cache savings:  {100*savings:.1f}%")

    # Per-table details
    print(f"\n--- Per-Table Results ---")
    print(f"{'Table ID':<35} {'OK':>3} {'Hdrs':>5} {'Rows':>5} {'Fill':>6} {'Time':>8} {'Error'}")
    for r in table_results:
        ok = "YES" if r.success else "NO"
        err = (r.error or "")[:40]
        print(f"{r.table_id:<35} {ok:>3} {r.n_headers:>5} {r.n_rows:>5} "
              f"{r.fill_rate:>5.1f}% {r.timing_ms:>7.0f}ms {err}")

    # Failures detail
    failures = [r for r in table_results if not r.success]
    if failures:
        print(f"\n--- Failures ({len(failures)}) ---")
        for r in failures:
            print(f"  {r.table_id}: {r.error}")

    # Pipeline vs Vision comparison
    print(f"\n--- Pipeline vs Vision Quality ---")
    print(f"{'Table ID':<35} {'P.Hdrs':>7} {'V.Hdrs':>7} {'P.Rows':>7} {'V.Rows':>7} {'P.Fill':>7} {'V.Fill':>7}")
    for (spec, vision_res), meta, tr in zip(results, spec_meta, table_results):
        if not tr.success:
            continue
        p_h = len(meta["pipeline_headers"]) if meta["pipeline_headers"] else 0
        p_r = meta["pipeline_rows"]
        p_f = meta["pipeline_fill"]
        print(f"{tr.table_id:<35} {p_h:>7} {tr.n_headers:>7} {p_r:>7} {tr.n_rows:>7} "
              f"{p_f:>6.1f}% {tr.fill_rate:>6.1f}%")

    print(f"\nCost log written to: {cost_log.resolve()}")
    print(f"Done.")


def _fill_rate(headers, rows) -> float:
    """Compute fill rate as % of non-empty cells."""
    if not headers or not rows:
        return 0.0
    total = len(headers) * len(rows)
    if total == 0:
        return 0.0
    filled = sum(1 for row in rows for cell in row if str(cell).strip())
    # Add header fill
    total += len(headers)
    filled += sum(1 for h in headers if str(h).strip())
    return 100.0 * filled / total


if __name__ == "__main__":
    main()
