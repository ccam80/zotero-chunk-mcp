"""Dump the actual garbled cells from stress-test flagged tables."""
from __future__ import annotations
import sys, re
sys.path.insert(0, "src")

from zotero_chunk_rag.pdf_processor import extract_document, _detect_garbled_spacing, _check_content_readability
from zotero_chunk_rag.zotero_client import ZoteroClient

# Papers + table indices flagged as garbled in stress test report
FLAGGED = {
    "SCPXVBLY": ("active-inference-tutorial", [0, 3, 4]),
    "5SIZVS65": ("laird-fick-polyps", [4]),
    "Z9X4JVZ5": ("roland-emg-filter", [0, 5, 6]),
    "DPYRZTFI": ("yang-ppv-meta", [0, 2]),
    "VP3NJ74M": ("fortune-impedance", [5]),
}

from zotero_chunk_rag.config import Config
config = Config.load()
zotero = ZoteroClient(config.zotero_data_dir)
all_items = zotero.get_all_items_with_pdfs()
items_by_key = {i.item_key: i for i in all_items}

for item_key, (short_name, table_indices) in FLAGGED.items():
    item = items_by_key.get(item_key)
    if not item or not item.pdf_path:
        print(f"SKIP: {short_name} — item not found")
        continue

    print(f"\n{'='*80}")
    print(f"PAPER: {short_name} ({item_key})")
    print(f"{'='*80}")

    extraction = extract_document(item.pdf_path, write_images=False)

    for ti in table_indices:
        if ti >= len(extraction.tables):
            print(f"  Table {ti}: index out of range (only {len(extraction.tables)} tables)")
            continue

        tab = extraction.tables[ti]
        caption = tab.caption or "(no caption)"
        print(f"\n  TABLE {ti}: {caption[:80]}")
        print(f"  Dimensions: {len(tab.rows)} rows x {max(len(r) for r in tab.rows) if tab.rows else 0} cols")

        rpt = _check_content_readability(tab)
        print(f"  Readability: garbled={rpt['garbled_cells']}, interleaved={rpt['interleaved_cells']}")

        # Show every garbled cell
        for ri, row in enumerate(tab.rows):
            for ci, cell in enumerate(row):
                is_garbled, reason = _detect_garbled_spacing(cell)
                if is_garbled:
                    truncated = cell[:200] + "..." if len(cell) > 200 else cell
                    print(f"\n    GARBLED [{ri},{ci}]: {reason}")
                    print(f"    Content: «{truncated}»")
                    # Show word lengths for diagnosis
                    words = cell.split()
                    if words:
                        lengths = [len(w) for w in words]
                        print(f"    Word count: {len(words)}, avg len: {sum(lengths)/len(lengths):.1f}, max: {max(lengths)}")
                        # Show the longest words
                        long_words = sorted(words, key=len, reverse=True)[:3]
                        for w in long_words:
                            print(f"      Long word ({len(w)} chars): «{w[:100]}»")

print("\nDone.")
