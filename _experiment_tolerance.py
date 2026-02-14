"""Experiment with text_x_tolerance and textpage flags on garbled tables.

The hypothesis: lowering text_x_tolerance from default 3 to smaller values
will cause WordExtractor to split concatenated words correctly.

We also try re-extracting cell text via page.get_text() with different flags.
"""
from __future__ import annotations
import sys
sys.path.insert(0, "src")

import pymupdf
from zotero_chunk_rag.pdf_processor import _detect_garbled_spacing, _merge_over_divided_rows
from zotero_chunk_rag.zotero_client import ZoteroClient
from zotero_chunk_rag.config import Config

# Focus on the garbled pages only for speed
TARGETS = [
    ("SCPXVBLY", "active-inference-tutorial", [0, 17, 18, 29, 53]),
    ("5SIZVS65", "laird-fick-polyps", [5]),
    ("Z9X4JVZ5", "roland-emg-filter", [4, 18]),
    ("DPYRZTFI", "yang-ppv-meta", [3, 5]),
    ("VP3NJ74M", "fortune-impedance", [5]),
]

TOLERANCE_VALUES = [3, 2, 1.5, 1, 0.5]

config = Config.load()
zotero = ZoteroClient(config.zotero_data_dir)
all_items = zotero.get_all_items_with_pdfs()
items_by_key = {i.item_key: i for i in all_items}

print("=" * 90)
print("EXPERIMENT 1: text_x_tolerance on find_tables()")
print("=" * 90)

for item_key, short_name, pages in TARGETS:
    item = items_by_key.get(item_key)
    if not item or not item.pdf_path:
        print(f"SKIP: {short_name}")
        continue

    doc = pymupdf.open(str(item.pdf_path))
    print(f"\n--- {short_name} ---")

    for tol in TOLERANCE_VALUES:
        total_garbled = 0
        total_cells = 0
        garbled_samples = []

        for page_num in pages:
            if page_num >= len(doc):
                continue
            page = doc[page_num]
            tab_finder = page.find_tables(text_x_tolerance=tol, text_y_tolerance=3)

            for ti, tab in enumerate(tab_finder.tables):
                raw_rows = tab.extract()
                rows = [[c if c else "" for c in r] for r in raw_rows]
                rows = _merge_over_divided_rows(rows)
                for ri, row in enumerate(rows):
                    for ci, cell in enumerate(row):
                        total_cells += 1
                        g, reason = _detect_garbled_spacing(cell)
                        if g:
                            total_garbled += 1
                            garbled_samples.append(
                                f"    p{page_num} t{ti}[{ri},{ci}]: {cell[:60]}"
                            )

        flag = " !!!" if total_garbled else ""
        print(f"  tol={tol:<4}  cells={total_cells:<5} garbled={total_garbled}{flag}")
        if garbled_samples and tol in (3, 1):  # Show detail for default and best candidate
            for s in garbled_samples[:5]:
                print(s)

    doc.close()

# ---- Experiment 2: Re-extract with page.get_text using different flags ----
print("\n\n" + "=" * 90)
print("EXPERIMENT 2: Re-extract cell text via page.get_text(clip=cell_bbox)")
print("Different flag combos on same cell regions")
print("=" * 90)

FLAG_COMBOS = {
    "default": pymupdf.TEXTFLAGS_TEXT,
    "no_preserve_ws": pymupdf.TEXTFLAGS_TEXT & ~pymupdf.TEXT_PRESERVE_WHITESPACE,
    "no_preserve_lig": pymupdf.TEXTFLAGS_TEXT & ~pymupdf.TEXT_PRESERVE_LIGATURES,
    "no_ws_no_lig": pymupdf.TEXTFLAGS_TEXT & ~pymupdf.TEXT_PRESERVE_WHITESPACE & ~pymupdf.TEXT_PRESERVE_LIGATURES,
    "inhibit_spaces": pymupdf.TEXTFLAGS_TEXT | pymupdf.TEXT_INHIBIT_SPACES,
    "dehyphenate": pymupdf.TEXTFLAGS_TEXT | pymupdf.TEXT_DEHYPHENATE,
}

# Pick a few known-garbled cells to test directly
GARBLED_CELLS = [
    ("Z9X4JVZ5", "roland-emg-filter", 18),  # page with Tables 5&6
    ("DPYRZTFI", "yang-ppv-meta", 3),        # page with Table 1
    ("VP3NJ74M", "fortune-impedance", 5),    # page with Table 5
]

for item_key, short_name, page_num in GARBLED_CELLS:
    item = items_by_key.get(item_key)
    if not item or not item.pdf_path:
        continue
    doc = pymupdf.open(str(item.pdf_path))
    page = doc[page_num]

    # Get table cell locations using default find_tables
    tab_finder = page.find_tables()
    if not tab_finder.tables:
        doc.close()
        continue

    print(f"\n--- {short_name} page {page_num} ({len(tab_finder.tables)} tables) ---")

    for ti, tab in enumerate(tab_finder.tables):
        raw_rows = tab.extract()
        rows_clean = [[c if c else "" for c in r] for r in raw_rows]
        # Check which cells are garbled
        for ri, row in enumerate(rows_clean):
            for ci, cell in enumerate(row):
                g, _ = _detect_garbled_spacing(cell)
                if not g:
                    continue

                # This cell is garbled. Now try extracting from the same bbox
                # with different flag combos
                table_rows = tab.rows
                if ri < len(table_rows) and ci < len(table_rows[ri].cells):
                    cell_bbox = table_rows[ri].cells[ci]
                    if cell_bbox is None:
                        continue
                    cell_rect = pymupdf.Rect(cell_bbox)

                    print(f"\n  Table {ti} [{ri},{ci}] original: «{cell[:70]}»")
                    for flag_name, flags in FLAG_COMBOS.items():
                        tp = page.get_textpage(flags=flags)
                        extracted = page.get_text("text", clip=cell_rect, textpage=tp)
                        extracted = extracted.strip().replace("\n", " | ")
                            print(f"    {flag_name:<16}: «{extracted[:70].encode('ascii', 'replace').decode()}»")

                    # Also try get_text("words") to see word-level extraction
                    words = page.get_text("words", clip=cell_rect)
                    word_texts = [w[4] for w in words]
                    print(f"    get_text(words): {[w.encode('ascii','replace').decode() for w in word_texts]}")

    doc.close()

print("\nDone.")
