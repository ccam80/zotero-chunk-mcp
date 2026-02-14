"""Run actual extraction on Hallett TMS Primer and investigate missing figs."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, "src")

from zotero_chunk_rag.pdf_processor import extract_document
import dataclasses

PDF_PATH = r"C:\Users\cca79\Zotero\storage\4X5IWKMD\Hallett - 2007 - Transcranial Magnetic Stimulation A Primer.pdf"

result = extract_document(PDF_PATH)

print(f"Extracted {len(result.figures)} figures:")
for fig in result.figures:
    d = dataclasses.asdict(fig)
    cap = (d.get('caption') or 'NONE')[:120]
    label = d.get('label', d.get('figure_index', '?'))
    page = d.get('page', d.get('page_num', '?'))
    print(f"  label={label}, page={page}, bbox={d.get('bbox', '?')}")
    print(f"    caption: '{cap}'")

print(f"\nExtracted {len(result.tables)} tables:")
for tab in result.tables:
    d = dataclasses.asdict(tab)
    cap = (d.get('caption') or 'NONE')[:120]
    label = d.get('label', d.get('table_index', '?'))
    page = d.get('page', d.get('page_num', '?'))
    print(f"  label={label}, page={page}, bbox={d.get('bbox', '?')}")
    print(f"    caption: '{cap}'")

print(f"\nGrade: {result.grade}")
if hasattr(result, 'stats') and result.stats:
    for k, v in result.stats.items():
        print(f"  {k}: {v}")

# Also check what fields exist
print(f"\nFigure fields: {[f.name for f in dataclasses.fields(result.figures[0])]}" if result.figures else "No figures")
print(f"Table fields: {[f.name for f in dataclasses.fields(result.tables[0])]}" if result.tables else "No tables")
print(f"Result fields: {[f.name for f in dataclasses.fields(result)]}")
