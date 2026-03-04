"""Test PaddleOCR-VL-1.5 CC-gated backend on a single PDF.

Validates:
  1. CC detection and backend selection
  2. Docker auto-start (if CC < 8.0)
  3. Engine init via get_engine()
  4. Single-PDF extraction + caption matching
  5. Timing and basic quality checks

Usage:
    .venv/Scripts/python.exe tools/test_vl_backend.py [item_key]

    item_key: Zotero item key (default: C626CYVT = hallett-tms-primer, has tables)

Environment variables:
    PADDLEOCR_VL_BACKEND     - Force "native" or "server"
    PADDLEOCR_VL_SERVER_URL  - Override server URL (default http://localhost:8118/v1)
"""
from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT / "tests"))

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
)

DEFAULT_ITEM_KEY = "C626CYVT"  # hallett-tms-primer (has tables)


def main() -> None:
    item_key = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ITEM_KEY

    # ── Step 1: CC detection ──────────────────────────────────────────
    print("=" * 60)
    print("Step 1: GPU compute capability")
    print("=" * 60)
    from zotero_chunk_rag.feature_extraction.paddle_engines.paddleocr_vl import (
        _get_compute_capability,
    )

    cc = _get_compute_capability()
    if cc is None:
        print("  No CUDA GPU detected. Cannot proceed.")
        sys.exit(1)
    print(f"  CC {cc[0]}.{cc[1]}")

    backend_override = os.environ.get("PADDLEOCR_VL_BACKEND")
    server_url = os.environ.get("PADDLEOCR_VL_SERVER_URL", "http://localhost:8118/v1")
    if backend_override:
        print(f"  PADDLEOCR_VL_BACKEND override: {backend_override}")
    if os.environ.get("PADDLEOCR_VL_SERVER_URL"):
        print(f"  PADDLEOCR_VL_SERVER_URL override: {server_url}")

    expected_backend = "native" if (cc[0] >= 8 or backend_override == "native") and backend_override != "server" else "server"
    print(f"  Expected backend: {expected_backend}")

    # ── Step 2: Locate PDF ────────────────────────────────────────────
    print()
    print("=" * 60)
    print("Step 2: Locate PDF")
    print("=" * 60)
    from zotero_chunk_rag.config import Config
    from zotero_chunk_rag.zotero_client import ZoteroClient

    config = Config.load()
    zotero = ZoteroClient(config.zotero_data_dir)
    all_items = zotero.get_all_items_with_pdfs()
    items_by_key = {i.item_key: i for i in all_items}

    item = items_by_key.get(item_key)
    if item is None:
        print(f"  Item {item_key} not found in Zotero library.")
        print(f"  Available keys (first 10): {list(items_by_key.keys())[:10]}")
        sys.exit(1)
    if not item.pdf_path or not item.pdf_path.exists():
        print(f"  PDF not found for {item_key}: {item.pdf_path}")
        sys.exit(1)

    print(f"  Title: {item.title}")
    print(f"  PDF:   {item.pdf_path}")
    pdf_size_mb = item.pdf_path.stat().st_size / (1024 * 1024)
    print(f"  Size:  {pdf_size_mb:.1f} MB")

    # ── Step 3: Engine init (triggers CC-gated backend selection) ─────
    print()
    print("=" * 60)
    print("Step 3: Engine init (CC-gated backend selection)")
    print("=" * 60)
    from zotero_chunk_rag.feature_extraction.paddle_extract import get_engine

    t0 = time.perf_counter()
    try:
        engine = get_engine("paddleocr_vl_1.5")
        dt_init = time.perf_counter() - t0
        print(f"  Engine initialised in {dt_init:.1f}s")
    except RuntimeError as e:
        dt_init = time.perf_counter() - t0
        print(f"  Engine init FAILED after {dt_init:.1f}s:")
        print(f"  {e}")
        sys.exit(1)

    # ── Step 4: Extract tables ────────────────────────────────────────
    print()
    print("=" * 60)
    print("Step 4: Extract tables")
    print("=" * 60)
    t0 = time.perf_counter()
    raw_tables = engine.extract_tables(item.pdf_path)
    dt_extract = time.perf_counter() - t0
    print(f"  Extracted {len(raw_tables)} raw tables in {dt_extract:.1f}s")

    for i, rt in enumerate(raw_tables):
        ncols = len(rt.headers) if rt.headers else (len(rt.rows[0]) if rt.rows else 0)
        print(f"    [{i}] page {rt.page_num} | {len(rt.rows)} rows x {ncols} cols | bbox={rt.bbox}")

    # ── Step 5: Caption matching ──────────────────────────────────────
    print()
    print("=" * 60)
    print("Step 5: Caption matching")
    print("=" * 60)
    import pymupdf

    from zotero_chunk_rag.feature_extraction.captions import find_all_captions
    from zotero_chunk_rag.feature_extraction.paddle_extract import match_tables_to_captions

    doc = pymupdf.open(str(item.pdf_path))
    captions_by_page: dict[int, list] = {}
    page_rects: dict[int, tuple[float, float, float, float]] = {}
    for page_idx in range(len(doc)):
        page = doc[page_idx]
        captions_by_page[page_idx + 1] = find_all_captions(page)
        r = page.rect
        page_rects[page_idx + 1] = (r.x0, r.y0, r.x1, r.y1)
    doc.close()

    total_captions = sum(len(v) for v in captions_by_page.values())
    print(f"  Found {total_captions} captions across {len(captions_by_page)} pages")

    matched = match_tables_to_captions(raw_tables, captions_by_page, page_rects)
    print(f"  Matched {len(matched)} tables")

    for i, mt in enumerate(matched):
        ncols = len(mt.headers) if mt.headers else (len(mt.rows[0]) if mt.rows else 0)
        total_cells = len(mt.rows) * max(ncols, 1)
        filled = sum(1 for row in mt.rows for c in row if c.strip()) if total_cells else 0
        fill = filled / total_cells if total_cells else 0.0
        cap = (mt.caption or "")[:60]
        print(f"    [{i}] \"{cap}\" | {len(mt.rows)}r x {ncols}c | fill={fill:.0%}")

    # ── Step 6: Quality summary ───────────────────────────────────────
    print()
    print("=" * 60)
    print("Step 6: Quality summary")
    print("=" * 60)

    if not raw_tables:
        print("  No tables extracted — check PDF or engine output.")
    else:
        avg_fill = sum(
            (sum(1 for c in row if c.strip()) / max(len(row), 1))
            for rt in raw_tables
            for row in rt.rows
        ) / max(sum(len(rt.rows) for rt in raw_tables), 1)
        print(f"  Avg row fill rate: {avg_fill:.0%}")

    total_time = dt_init + dt_extract
    per_page = dt_extract / max(len(captions_by_page), 1)
    print(f"  Init time:       {dt_init:.1f}s")
    print(f"  Extract time:    {dt_extract:.1f}s ({per_page:.2f}s/page)")
    print(f"  Total time:      {total_time:.1f}s")

    if expected_backend == "server" and dt_extract > 300:
        print("  WARNING: extraction took >5min — server may not be accelerating")
    elif expected_backend == "native" and dt_extract > 60:
        print("  WARNING: extraction took >60s — native vLLM may not have FA2")

    print()
    print("DONE")


if __name__ == "__main__":
    main()
