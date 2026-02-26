"""
Diagnostic script: render 9GKLLJH9 Table 2 PNG and dump word-level y-positions.

Renders the table region as PNG (saved to disk for inspection), then extracts
all words from the same bbox via page.get_text("words") and groups them into
y-position clusters (3pt tolerance).  Specifically flags where "Baseline" and
the first data values (β etc.) sit in y-space.

Usage:
    "./.venv/Scripts/python.exe" debug_table2_words.py
"""

import sys
import os

# Ensure the src package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from pathlib import Path
import pymupdf

from zotero_chunk_rag.feature_extraction.vision_extract import _render_table_png
from zotero_chunk_rag.feature_extraction.pipeline import FAST_CONFIG, Pipeline

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

PDF_PATH = Path(
    r"C:\Users\cca79\Zotero\storage\7XHS8Q5J"
    r"\Helm et al. - 2014 - Coregulation of respiratory sinus arrhythmia in ad.pdf"
)
ITEM_KEY = "9GKLLJH9"
PAGE_NUM_1INDEXED = 7   # page 7 (1-indexed) = page index 6 (0-indexed)
PAGE_NUM_0INDEXED = PAGE_NUM_1INDEXED - 1

# bbox from the existing extraction JSON (page 6, table_index 1)
KNOWN_BBOX = (47.999603271484375, 118.40787506103516, 288.0240173339844, 292.2356262207031)

OUTPUT_PNG = Path(__file__).parent / "debug_table2_page7.png"

CLUSTER_TOL = 3.0   # pt — words within this distance merged into one y-cluster


# ---------------------------------------------------------------------------
# Step 1: discover bbox via pipeline (may refine vs. stored value)
# ---------------------------------------------------------------------------

def discover_bbox_from_pipeline() -> tuple[float, float, float, float] | None:
    """Run FAST_CONFIG pipeline on the page and return the bbox of the table
    whose y-midpoint is closest to the known bbox midpoint."""
    print("\n=== Step 1: Pipeline bbox discovery ===")
    pipe = Pipeline(FAST_CONFIG)
    doc = pymupdf.open(str(PDF_PATH))
    try:
        page = doc[PAGE_NUM_0INDEXED]
        results = pipe.extract_page(page, pdf_path=PDF_PATH, page_num=PAGE_NUM_1INDEXED)
        print(f"  Pipeline found {len(results)} table(s) on page {PAGE_NUM_1INDEXED}")
        for i, r in enumerate(results):
            bbox = r.bbox if hasattr(r, "bbox") else None
            cap  = getattr(r, "caption", None) or getattr(r, "detected_caption", None)
            print(f"  [{i}] bbox={bbox}  caption={cap!r}")
    except Exception as exc:
        print(f"  Pipeline extraction failed: {exc}")
        results = []
    finally:
        doc.close()

    if not results:
        return None

    known_mid_y = (KNOWN_BBOX[1] + KNOWN_BBOX[3]) / 2.0
    best = min(
        results,
        key=lambda r: abs(((r.bbox[1] + r.bbox[3]) / 2.0) - known_mid_y)
        if hasattr(r, "bbox") and r.bbox else 9999,
    )
    bbox = best.bbox if hasattr(best, "bbox") else None
    print(f"  Closest to known bbox: {bbox}")
    return tuple(bbox) if bbox else None


# ---------------------------------------------------------------------------
# Step 2: render PNG
# ---------------------------------------------------------------------------

def render_png(bbox: tuple) -> None:
    print(f"\n=== Step 2: Render PNG (bbox={bbox}) ===")
    png_bytes, _ = _render_table_png(PDF_PATH, PAGE_NUM_1INDEXED, bbox, dpi=150, padding_px=10)
    OUTPUT_PNG.write_bytes(png_bytes)
    print(f"  PNG written to: {OUTPUT_PNG}  ({len(png_bytes):,} bytes)")


# ---------------------------------------------------------------------------
# Step 3: extract words and cluster by y-position
# ---------------------------------------------------------------------------

def extract_and_cluster_words(bbox: tuple) -> None:
    print(f"\n=== Step 3: Word-level y-position analysis (bbox={bbox}) ===")

    x0, y0, x1, y1 = bbox
    doc = pymupdf.open(str(PDF_PATH))
    try:
        page = doc[PAGE_NUM_0INDEXED]

        # get_text("words") returns tuples:
        #   (x0, y0, x1, y1, "word", block_no, line_no, word_no)
        all_words = page.get_text("words")
    finally:
        doc.close()

    # Filter to words inside (or overlapping) our bbox with a small margin
    margin = 2.0
    in_bbox = [
        w for w in all_words
        if w[0] < x1 + margin and w[2] > x0 - margin
        and w[1] < y1 + margin and w[3] > y0 - margin
    ]

    print(f"  Total words on page: {len(all_words)}")
    print(f"  Words inside bbox:   {len(in_bbox)}")

    if not in_bbox:
        print("  ERROR: no words found in bbox — check page/bbox values")
        return

    # Cluster by y_top (word[1]) within CLUSTER_TOL
    in_bbox_sorted = sorted(in_bbox, key=lambda w: (w[1], w[0]))  # sort by y, then x

    clusters: list[list] = []
    current_cluster: list = []
    cluster_y_top: float = -9999.0

    for w in in_bbox_sorted:
        word_y = w[1]
        if not current_cluster or abs(word_y - cluster_y_top) <= CLUSTER_TOL:
            current_cluster.append(w)
            # keep cluster_y_top as the first word's y in the cluster
            if len(current_cluster) == 1:
                cluster_y_top = word_y
        else:
            clusters.append(current_cluster)
            current_cluster = [w]
            cluster_y_top = word_y

    if current_cluster:
        clusters.append(current_cluster)

    print(f"\n  Found {len(clusters)} y-clusters (tol={CLUSTER_TOL}pt):\n")
    print(f"  {'Cluster':>3}  {'y_top':>7}  {'y_bot':>7}  {'Words'}")
    print(f"  {'-'*3}  {'-'*7}  {'-'*7}  {'-'*50}")

    # Track which clusters contain "Baseline" or look like data rows
    baseline_clusters: list[int] = []
    data_clusters: list[int] = []

    for ci, cluster in enumerate(clusters):
        words_text = [w[4] for w in cluster]
        y_tops = [w[1] for w in cluster]
        y_bots = [w[3] for w in cluster]
        y_top_mean = sum(y_tops) / len(y_tops)
        y_bot_mean = sum(y_bots) / len(y_bots)

        # Flag interesting rows
        joined = " ".join(words_text).lower()
        is_baseline = "baseline" in joined or "baselin" in joined
        # data rows: contain digits or Greek letters (β, α etc.)
        has_data = any(
            any(c.isdigit() or c in "βαγδεζηθλμνξπρστυφχψω.−−" for c in w)
            for w in words_text
        )

        tag = ""
        if is_baseline:
            baseline_clusters.append(ci)
            tag = "  <<< BASELINE"
        elif has_data:
            data_clusters.append(ci)
            tag = "  [data]"

        words_display = " | ".join(words_text)
        if len(words_display) > 80:
            words_display = words_display[:77] + "..."
        print(f"  {ci:>3}  {y_top_mean:>7.2f}  {y_bot_mean:>7.2f}  {words_display}{tag}")

    # ---------------------------------------------------------------------------
    # Summary: spacing between adjacent clusters
    # ---------------------------------------------------------------------------
    print(f"\n  === Cluster spacing (gap between consecutive cluster tops) ===")
    cluster_tops = []
    for cluster in clusters:
        y_tops = [w[1] for w in cluster]
        cluster_tops.append(sum(y_tops) / len(y_tops))

    for i in range(1, len(cluster_tops)):
        gap = cluster_tops[i] - cluster_tops[i - 1]
        print(f"  cluster {i-1:>2} -> {i:>2}  gap={gap:>6.2f}pt")

    # ---------------------------------------------------------------------------
    # Zoom in: Baseline and surrounding rows
    # ---------------------------------------------------------------------------
    if baseline_clusters:
        print(f"\n  === Baseline cluster(s) and ±3 neighbors ===")
        for ci in baseline_clusters:
            lo = max(0, ci - 3)
            hi = min(len(clusters) - 1, ci + 5)
            for idx in range(lo, hi + 1):
                cluster = clusters[idx]
                words_text = [w[4] for w in cluster]
                y_tops = [w[1] for w in cluster]
                y_mean = sum(y_tops) / len(y_tops)
                marker = " <<< BASELINE" if idx == ci else ""
                print(f"    [{idx:>2}] y={y_mean:>7.2f}  {' | '.join(words_text)}{marker}")
    else:
        print("\n  WARNING: 'Baseline' not found in any cluster in this bbox")
        print("  Showing first 10 clusters for sanity check:")
        for ci, cluster in enumerate(clusters[:10]):
            words_text = [w[4] for w in cluster]
            y_tops = [w[1] for w in cluster]
            y_mean = sum(y_tops) / len(y_tops)
            print(f"    [{ci:>2}] y={y_mean:>7.2f}  {' | '.join(words_text)}")

    # ---------------------------------------------------------------------------
    # Raw word dump for inspection
    # ---------------------------------------------------------------------------
    print(f"\n  === Raw word dump (sorted by y, x) ===")
    print(f"  {'#':>4}  {'x0':>7} {'y0':>7} {'x1':>7} {'y1':>7}  word")
    for i, w in enumerate(in_bbox_sorted):
        print(f"  {i:>4}  {w[0]:>7.2f} {w[1]:>7.2f} {w[2]:>7.2f} {w[3]:>7.2f}  {w[4]!r}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"PDF: {PDF_PATH}")
    print(f"Page: {PAGE_NUM_1INDEXED} (1-indexed), bbox (known): {KNOWN_BBOX}")

    if not PDF_PATH.exists():
        print(f"\nERROR: PDF not found at {PDF_PATH}")
        sys.exit(1)

    # Try pipeline discovery first; fall back to known bbox
    pipeline_bbox = discover_bbox_from_pipeline()
    bbox = pipeline_bbox if pipeline_bbox else KNOWN_BBOX

    render_png(bbox)
    extract_and_cluster_words(bbox)
