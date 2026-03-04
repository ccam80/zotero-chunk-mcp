"""Diagnostic: probe PaddleOCR-VL-1.5 predict() output format.

Usage:
    .venv/Scripts/python.exe tools/diag_vl.py
"""
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT / "tests"))

# Apply Paddle int() fix before any PaddleOCR imports
import numpy as np
import paddle

_orig_int = paddle.Tensor.__int__
print(f"  Original __int__: {_orig_int}")

def _safe_int(var):
    numel = np.prod(var.shape)
    assert numel == 1, "only one element variable can be converted to int."
    assert var._is_initialized(), "variable's tensor is not initialized"
    return int(np.array(var).item())

paddle.Tensor.__int__ = _safe_int
print(f"  Patched __int__: {paddle.Tensor.__int__}")

# Quick sanity check
t = paddle.to_tensor([42])
print(f"  int(paddle.to_tensor([42])) = {int(t)}  (shape={t.shape})")

from stress_test_real_library import CORPUS
from zotero_chunk_rag.config import Config
from zotero_chunk_rag.zotero_client import ZoteroClient


def main():
    # Pick first corpus PDF
    config = Config.load()
    zotero = ZoteroClient(config.zotero_data_dir)
    all_items = zotero.get_all_items_with_pdfs()
    items_by_key = {i.item_key: i for i in all_items}

    item_key, short_name, _reason, _gt = CORPUS[2]  # hallett-tms-primer
    item = items_by_key[item_key]
    pdf_path = str(item.pdf_path)
    print(f"PDF: {pdf_path}")
    print(f"Paper: {short_name}\n")

    from paddleocr import PaddleOCRVL

    # -- Test 1: use_queues=False (synchronous) --
    print("=" * 60)
    print("TEST 1: use_queues=False (synchronous)")
    print("=" * 60)
    try:
        pipeline = PaddleOCRVL(pipeline_version="v1.5", device="gpu:0", use_queues=False)
        results = pipeline.predict(pdf_path)
        print(f"  predict() returned: {type(results).__name__}, len={len(results)}")
        if results:
            r0 = results[0]
            print(f"  results[0] type: {type(r0).__name__}")
            if isinstance(r0, dict):
                print(f"  results[0] keys: {list(r0.keys())}")
            elif hasattr(r0, '__dict__'):
                print(f"  results[0] attrs: {list(vars(r0).keys())[:20]}")
            # Check if it has dict-like access
            if hasattr(r0, 'get'):
                print(f"  .get('page_num'): {r0.get('page_num', 'MISSING')}")
                print(f"  .get('page_index'): {r0.get('page_index', 'MISSING')}")
                print(f"  .get('parsing_res_list'): type={type(r0.get('parsing_res_list', 'MISSING'))}")
            if hasattr(r0, '__getitem__'):
                try:
                    print(f"  ['page_index']: {r0['page_index']}")
                except (KeyError, TypeError) as e:
                    print(f"  ['page_index'] error: {e}")
            # Probe the actual structure
            print(f"\n  dir(results[0]): {[a for a in dir(r0) if not a.startswith('_')]}")

            # Try to iterate the result object to see what it contains
            if hasattr(r0, 'keys'):
                for key in r0.keys():
                    val = r0[key]
                    desc = f"type={type(val).__name__}"
                    if isinstance(val, (list, tuple)):
                        desc += f", len={len(val)}"
                        if val:
                            desc += f", [0].type={type(val[0]).__name__}"
                    elif isinstance(val, (int, float, str)):
                        desc += f", val={val!r}"
                    print(f"    {key}: {desc}")
    except Exception as e:
        print(f"  FAILED: {e}")
        traceback.print_exc()

    # -- Test 2: restructure_pages --
    print("\n" + "=" * 60)
    print("TEST 2: restructure_pages output")
    print("=" * 60)
    try:
        restructured = pipeline.restructure_pages(results, merge_tables=True)
        print(f"  restructure_pages() returned: {type(restructured).__name__}, len={len(restructured)}")
        if restructured:
            rs0 = restructured[0]
            print(f"  restructured[0] type: {type(rs0).__name__}")
            if isinstance(rs0, dict):
                print(f"  restructured[0] keys: {list(rs0.keys())}")
                for key, val in rs0.items():
                    desc = f"type={type(val).__name__}"
                    if isinstance(val, (list, tuple)):
                        desc += f", len={len(val)}"
                        if val:
                            desc += f", [0].type={type(val[0]).__name__}"
                    elif isinstance(val, (int, float, str)):
                        desc += f", val={val!r}"
                    print(f"    {key}: {desc}")

                # Probe parsing_res_list blocks
                prl = rs0.get("parsing_res_list", [])
                if prl:
                    print(f"\n  First parsing_res_list block:")
                    b0 = prl[0]
                    print(f"    type: {type(b0).__name__}")
                    if isinstance(b0, dict):
                        for k, v in b0.items():
                            vdesc = f"type={type(v).__name__}"
                            if isinstance(v, str):
                                vdesc += f", len={len(v)}, preview={v[:80]!r}"
                            elif isinstance(v, (int, float)):
                                vdesc += f", val={v!r}"
                            elif isinstance(v, (list, tuple)):
                                vdesc += f", len={len(v)}"
                            print(f"      {k}: {vdesc}")
                    elif hasattr(b0, '__dict__'):
                        for k, v in vars(b0).items():
                            print(f"      {k}: {type(v).__name__} = {v!r}"[:120])

                # Find first table block
                table_blocks = [b for b in prl if isinstance(b, dict) and "table" in b.get("block_label", "").lower()]
                if not table_blocks and prl:
                    table_blocks = [b for b in prl if hasattr(b, 'label') and "table" in getattr(b, 'label', '').lower()]
                if table_blocks:
                    print(f"\n  First TABLE block:")
                    tb = table_blocks[0]
                    if isinstance(tb, dict):
                        for k, v in tb.items():
                            vdesc = f"type={type(v).__name__}"
                            if isinstance(v, str):
                                vdesc += f", len={len(v)}"
                                if len(v) < 500:
                                    vdesc += f"\n        {v!r}"
                            print(f"      {k}: {vdesc}")
                    elif hasattr(tb, '__dict__'):
                        for k, v in vars(tb).items():
                            print(f"      {k}: {type(v).__name__} = {str(v)[:200]!r}")
                else:
                    print("\n  No table blocks found in parsing_res_list")
                    # Show all labels
                    labels = set()
                    for b in prl:
                        if isinstance(b, dict):
                            labels.add(b.get("block_label", "???"))
                        elif hasattr(b, 'label'):
                            labels.add(b.label)
                    print(f"  Labels found: {labels}")
    except Exception as e:
        print(f"  FAILED: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
