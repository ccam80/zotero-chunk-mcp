"""Investigate over-divided table problem in active-inference-tutorial paper."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"C:\local_working_projects\zotero_citation_mcp\src")

import pymupdf

PDF_PATH = r"C:\Users\cca79\Zotero\storage\5Y3E4PJP\Smith et al. - 2022 - A step-by-step tutorial on active inference and it.pdf"

doc = pymupdf.open(PDF_PATH)
print(f"Opened: {PDF_PATH}")
print(f"Pages: {doc.page_count}\n")

# == PHASE 1: Check what our pipeline extracts ==
print("=" * 80)
print("PHASE 1: Our pipeline's table extraction")
print("=" * 80)

from zotero_chunk_rag.pdf_processor import extract_document

result = extract_document(PDF_PATH)
print(f"\nPipeline found {len(result.tables)} tables:")
for i, tbl in enumerate(result.tables):
    caption = (tbl.caption or "")[:100]
    page = tbl.page if hasattr(tbl, 'page') else '?'
    print(f"\n  Table {i}: page={page}")
    print(f"    caption: {caption!r}")
    md = tbl.markdown if hasattr(tbl, 'markdown') else None
    if md:
        md_lines = md.split("\n")
        data_rows = [l for l in md_lines if l.strip().startswith("|") and "---" not in l]
        print(f"    markdown total lines: {len(md_lines)}, data rows: {len(data_rows)}")
        # Show first 15 lines
        for ml in md_lines[:15]:
            print(f"      {ml[:120]}")
        if len(md_lines) > 15:
            print(f"      ... ({len(md_lines)-15} more lines)")

doc.close()

# == PHASE 2: Detailed pymupdf table extraction on TABLE pages ==
print(f"\n{'=' * 80}")
print("PHASE 2: pymupdf find_tables() with strategy='text' on table pages")
print("=" * 80)

doc = pymupdf.open(PDF_PATH)

# Table 1 is on pages 15-16, Table 2 on 18-20, Table 3 on 30-31, Appendix tables on 54
table_pages = [14, 15, 17, 18, 19, 29, 30, 53]  # 0-indexed

for page_num in table_pages:
    if page_num >= doc.page_count:
        continue
    page = doc[page_num]
    tf = page.find_tables(strategy="text")
    tables_list = tf.tables if hasattr(tf, 'tables') else list(tf)
    
    print(f"\n--- Page {page_num+1}: {len(tables_list)} tables found ---")
    for ti, tab in enumerate(tables_list):
        print(f"  Table {ti}: {tab.row_count}x{tab.col_count} bbox={tab.bbox}")
        print(f"    header.external: {tab.header.external}")
        hnames = tab.header.names
        print(f"    header.names: {hnames}")
        
        data = tab.extract()
        
        # Show all rows with content pattern
        print(f"    --- Row data ---")
        for ri, row in enumerate(data):
            content_cols = []
            for ci, cell in enumerate(row):
                if cell and cell.strip():
                    content_cols.append(ci)
            ncols = tab.col_count
            pattern = "".join("X" if ci in content_cols else "." for ci in range(ncols))
            
            # Truncated display
            display_parts = []
            for ci, cell in enumerate(row):
                val = (cell or "").strip()
                if len(val) > 40:
                    val = val[:40] + "..."
                if val:
                    display_parts.append(f"c{ci}={val!r}")
            
            print(f"    [{ri:3d}] [{pattern}] {', '.join(display_parts)}")
            
            if ri >= 30 and tab.row_count > 35:
                print(f"    ... ({tab.row_count - ri - 1} more rows)")
                # Show last 5
                for ri2 in range(max(ri+1, tab.row_count-5), tab.row_count):
                    row2 = data[ri2]
                    content_cols2 = [ci for ci, c in enumerate(row2) if c and c.strip()]
                    pattern2 = "".join("X" if ci in content_cols2 else "." for ci in range(ncols))
                    dp2 = [f"c{ci}={(c or '').strip()[:40]!r}" for ci, c in enumerate(row2) if c and c.strip()]
                    print(f"    [{ri2:3d}] [{pattern2}] {', '.join(dp2)}")
                break

# == PHASE 3: Focus on Table 1 (pages 15-16) - identify logical rows ==
print(f"\n{'=' * 80}")
print("PHASE 3: Logical row analysis of Table 1")
print("=" * 80)

# Table 1 is on pages 15 and 16 (1-indexed), so 14 and 15 (0-indexed)
# Let's get the text content and analyze the structure
for page_num in [14, 15]:
    page = doc[page_num]
    text = page.get_text("text")
    lines = [l for l in text.split("\n")]
    
    print(f"\n--- Page {page_num+1} full text lines ---")
    for i, line in enumerate(lines):
        if line.strip():
            print(f"  [{i:3d}] {line.rstrip()[:120]}")

# Now extract blocks to understand spatial layout
print(f"\n--- Page 15 text blocks (spatial) ---")
page = doc[14]
blocks = page.get_text("dict")["blocks"]
for bi, block in enumerate(blocks):
    if "lines" in block:
        for li, line in enumerate(block["lines"]):
            spans = line["spans"]
            text = "".join(s["text"] for s in spans)
            if text.strip():
                bbox = line["bbox"]
                font = spans[0]["font"] if spans else "?"
                size = spans[0]["size"] if spans else 0
                flags = spans[0]["flags"] if spans else 0
                bold = "BOLD" if (flags & 16) else ""
                italic = "ITALIC" if (flags & 2) else ""
                print(f"  b{bi:2d} l{li:2d} y={bbox[1]:6.1f} x={bbox[0]:6.1f}-{bbox[2]:6.1f} "
                      f"font={font[:20]:20s} sz={size:5.1f} {bold:4s} {italic:6s} | {text[:80]}")

doc.close()
print("\nDone.")
