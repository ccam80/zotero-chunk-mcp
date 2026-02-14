"""Focused investigation: what does our pipeline produce for each table?"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"C:\local_working_projects\zotero_citation_mcp\src")

PDF_PATH = r"C:\Users\cca79\Zotero\storage\5Y3E4PJP\Smith et al. - 2022 - A step-by-step tutorial on active inference and it.pdf"

from zotero_chunk_rag.pdf_processor import extract_document

result = extract_document(PDF_PATH)
print(f"Pipeline found {len(result.tables)} tables\n")

for i, tbl in enumerate(result.tables):
    caption = (tbl.caption or "")[:120]
    print(f"{'=' * 80}")
    print(f"TABLE {i}: {caption}")
    print(f"{'=' * 80}")
    
    # Print all attributes
    for attr in dir(tbl):
        if attr.startswith('_'):
            continue
        val = getattr(tbl, attr)
        if callable(val):
            continue
        if attr == 'markdown':
            if val:
                lines = val.split("\n")
                print(f"  {attr}: {len(lines)} lines")
                # Count actual data rows (pipes, not separator)
                data_rows = [l for l in lines if l.strip().startswith("|") and "---" not in l]
                print(f"  data rows: {len(data_rows)}")
                # Show first 20 and last 5
                for li, line in enumerate(lines[:20]):
                    print(f"    {line[:140]}")
                if len(lines) > 25:
                    print(f"    ... ({len(lines) - 25} lines omitted) ...")
                    for li in range(max(20, len(lines)-5), len(lines)):
                        print(f"    {lines[li][:140]}")
                elif len(lines) > 20:
                    for li in range(20, len(lines)):
                        print(f"    {lines[li][:140]}")
            else:
                print(f"  {attr}: None")
        elif attr == 'content':
            if val:
                print(f"  {attr}: {len(val)} chars")
                # Show first 500 chars
                print(f"    {val[:500]}")
                if len(val) > 500:
                    print(f"    ... ({len(val)-500} more chars)")
            else:
                print(f"  {attr}: None")
        else:
            print(f"  {attr}: {val}")
    print()

# Also: check the stress test grading
print(f"\n{'=' * 80}")
print("STATS")
print(f"{'=' * 80}")
if hasattr(result, 'stats'):
    for k, v in (result.stats or {}).items():
        print(f"  {k}: {v}")
print(f"\nFigures: {len(result.figures)}")
print(f"Tables: {len(result.tables)}")
print(f"Chunks: {len(result.chunks)}")

print("\nDone.")
