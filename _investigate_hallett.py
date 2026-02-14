"""Investigate why figures 2 and 4 are missing from Hallett TMS Primer."""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import fitz  # pymupdf
import re

PDF_PATH = r"C:\Users\cca79\Zotero\storage\4X5IWKMD\Hallett - 2007 - Transcranial Magnetic Stimulation A Primer.pdf"

doc = fitz.open(PDF_PATH)
print(f"PDF: {PDF_PATH}")
print(f"Pages: {doc.page_count}")
print("=" * 80)

CAPTION_RE = re.compile(
    r"(?:^|\n)\s*(?:Fig(?:ure|\.)?|Table)\s*\.?\s*(\d+|[IVXLCDM]+|[A-Z]\.\d+|S\d+)",
    re.IGNORECASE,
)

# Focus on pages 1 and 2 (PDF pages 2 and 3) where figs 1-4 live
for page_idx in range(min(doc.page_count, 8)):
    page = doc[page_idx]
    print(f"\n{'='*80}")
    print(f"PAGE {page_idx} (PDF page {page_idx + 1})")
    print(f"{'='*80}")
    
    images = page.get_images(full=True)
    print(f"\n  IMAGES: {len(images)}")
    
    img_info = page.get_image_info(xrefs=True)
    if img_info:
        print(f"  IMAGE POSITIONS ({len(img_info)} entries):")
        for ii in img_info:
            w = ii['bbox'][2] - ii['bbox'][0]
            h = ii['bbox'][3] - ii['bbox'][1]
            print(f"    xref={ii.get('xref', '?')}, bbox=({ii['bbox'][0]:.1f}, {ii['bbox'][1]:.1f}, {ii['bbox'][2]:.1f}, {ii['bbox'][3]:.1f}), "
                  f"render_size={w:.0f}x{h:.0f}, native={ii.get('width', '?')}x{ii.get('height', '?')}")
    
    drawings = page.get_drawings()
    print(f"\n  DRAWINGS: {len(drawings)}")
    
    # Text: show caption matches
    text_content = page.get_text("text")
    caption_matches = list(CAPTION_RE.finditer(text_content))
    if caption_matches:
        print(f"\n  CAPTION MATCHES:")
        for m in caption_matches:
            start = max(0, m.start() - 10)
            end = min(len(text_content), m.end() + 80)
            context = text_content[start:end].replace("\n", "\n")
            print(f"    pos={m.start()}: '{context}'")

doc.close()

# Now run the actual extraction
print("\n\n" + "=" * 80)
print("RUNNING ACTUAL EXTRACTION")
print("=" * 80)

sys.path.insert(0, "src")
from zotero_chunk_rag.pdf_processor import PDFProcessor

proc = PDFProcessor()
result = proc.extract(PDF_PATH)

print(f"\nExtracted {len(result.figures)} figures:")
for fig in result.figures:
    cap = fig.caption[:100] if fig.caption else 'NONE'
    has_img = bool(fig.image_base64)
    print(f"  {fig.label}: page={fig.page}, has_image={has_img}, caption='{cap}'")

print(f"\nExtracted {len(result.tables)} tables:")
for tab in result.tables:
    cap = tab.caption[:100] if tab.caption else 'NONE'
    print(f"  {tab.label}: page={tab.page}, caption='{cap}'")

print(f"\nGrade: {result.grade}")
if hasattr(result, 'stats') and result.stats:
    print(f"Stats: {result.stats}")
