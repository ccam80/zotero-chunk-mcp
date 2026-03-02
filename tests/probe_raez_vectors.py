"""Probe Raez paper for vector graphics detection using PyMuPDF APIs.

Tries multiple approaches to detect figure bboxes on pages with known
missing vector figures (figures 1 and 2).
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

import pymupdf
import pymupdf4llm

PDF_PATH = r"C:\Users\cca79\Zotero\storage\3ZUJ2LH2\Raez et al. - 2006 - Techniques of EMG signal analysis detection, proc.pdf"

doc = pymupdf.open(PDF_PATH)
print(f"Pages: {len(doc)}")
print("=" * 80)

# First pass: find which pages have figure captions
for pno in range(len(doc)):
    page = doc[pno]
    text = page.get_text()
    for keyword in ["Fig. 1", "Fig. 2", "Fig. 3", "Figure 1", "Figure 2"]:
        if keyword in text:
            print(f"  p{pno+1}: contains '{keyword}'")

print("\n" + "=" * 80)

# Get pymupdf4llm chunks to check the 'graphics' and 'page_boxes' fields
chunks = pymupdf4llm.to_markdown(
    doc,
    page_chunks=True,
    write_images=False,
)

print("\n--- pymupdf4llm chunk fields per page ---")
for chunk in chunks:
    pno = chunk["metadata"]["page"] + 1  # 0-indexed in metadata
    graphics = chunk.get("graphics", [])
    page_boxes = chunk.get("page_boxes", [])
    images_field = chunk.get("images", [])
    tables_field = chunk.get("tables", [])
    print(f"  p{pno}: graphics={len(graphics)}, page_boxes={len(page_boxes)}, "
          f"images={len(images_field)}, tables={len(tables_field)}")
    if graphics:
        for i, g in enumerate(graphics):
            print(f"    graphic[{i}]: {g}")
    if page_boxes:
        for box in page_boxes:
            print(f"    box: class={box.get('class')}, bbox={box.get('bbox')}")

print("\n" + "=" * 80)

# Detailed probe on pages 1-6 (figures likely in first few pages)
for pno in range(min(8, len(doc))):
    page = doc[pno]
    print(f"\n=== Page {pno+1} ===")

    # Method 1: get_drawings() raw count and stats
    drawings = page.get_drawings()
    print(f"  get_drawings(): {len(drawings)} paths")
    if drawings:
        rects = [d["rect"] for d in drawings if d.get("rect")]
        areas = [r.get_area() for r in rects if not r.is_empty]
        if areas:
            print(f"    rect areas: min={min(areas):.1f}, max={max(areas):.1f}, "
                  f"median={sorted(areas)[len(areas)//2]:.1f}")
        # Show types of drawing items
        item_types = {}
        for d in drawings:
            for item in d.get("items", []):
                t = item[0] if item else "?"
                item_types[t] = item_types.get(t, 0) + 1
        print(f"    item types: {item_types}")

    # Method 2: cluster_drawings()
    try:
        clusters = page.cluster_drawings()
        print(f"  cluster_drawings(): {len(clusters)} clusters")
        for i, c in enumerate(clusters):
            r = pymupdf.Rect(c)
            print(f"    cluster[{i}]: {r}, area={r.get_area():.0f}, "
                  f"w={r.width:.0f}, h={r.height:.0f}")
    except Exception as e:
        print(f"  cluster_drawings() ERROR: {e}")

    # Method 2b: cluster_drawings with relaxed tolerance
    try:
        clusters_relaxed = page.cluster_drawings(x_tolerance=10, y_tolerance=10)
        if len(clusters_relaxed) != len(clusters):
            print(f"  cluster_drawings(tol=10): {len(clusters_relaxed)} clusters")
            for i, c in enumerate(clusters_relaxed):
                r = pymupdf.Rect(c)
                print(f"    cluster[{i}]: {r}, area={r.get_area():.0f}")
    except Exception as e:
        print(f"  cluster_drawings(tol=10) ERROR: {e}")

    # Method 3: get_image_info()
    images = page.get_image_info()
    print(f"  get_image_info(): {len(images)} images")
    for img in images:
        bbox = img.get("bbox")
        if bbox:
            r = pymupdf.Rect(bbox)
            print(f"    image: {r}, area={r.get_area():.0f}")

    # Method 4: get_text("dict") - check for image blocks
    td = page.get_text("dict")
    img_blocks = [b for b in td.get("blocks", []) if b.get("type") == 1]
    txt_blocks = [b for b in td.get("blocks", []) if b.get("type") == 0]
    print(f"  get_text('dict'): {len(img_blocks)} image blocks, {len(txt_blocks)} text blocks")
    for ib in img_blocks:
        r = pymupdf.Rect(ib["bbox"])
        print(f"    img_block: {r}, area={r.get_area():.0f}")

    # Method 5: page_boxes from layout engine (already in chunk)
    # (already printed above)

doc.close()
