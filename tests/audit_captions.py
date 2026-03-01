"""Standalone caption audit script — run directly, NOT via pytest.

Reads 20 papers from the local Zotero library (SQLite + local PDFs), runs
find_all_captions() on every page, and reports per-paper caption counts.
Validates label-only caption detection against real PDFs without external API calls.

Usage:
    .venv/Scripts/python.exe tests/audit_captions.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pymupdf

# Ensure the src directory is on the path when running directly
_repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(_repo_root / "src"))

from zotero_chunk_rag.config import Config
from zotero_chunk_rag.zotero_client import ZoteroClient
from zotero_chunk_rag.feature_extraction.captions import (
    find_all_captions,
    _FIG_LABEL_ONLY_RE,
    _TABLE_LABEL_ONLY_RE,
)

CORPUS_KEYS = [
    "SCPXVBLY",  # active-inference-tutorial
    "XIAINRVS",  # huang-emd-1998
    "C626CYVT",  # hallett-tms-primer
    "5SIZVS65",  # laird-fick-polyps
    "9GKLLJH9",  # helm-coregulation
    "Z9X4JVZ5",  # roland-emg-filter
    "YMWV46JA",  # friston-life
    "DPYRZTFI",  # yang-ppv-meta
    "VP3NJ74M",  # fortune-impedance
    "AQ3D94VC",  # reyes-lf-hrv
    "UHSPFNS3",  # vagal tone preterm
    "5LY5DK3R",  # PPG variability
    "E2PC978X",  # improved HRV method
    "8QZ8IQFC",  # surgeon stress HRV
    "GMVKXTRD",  # peak detection HRV
    "HGHR7F4P",  # premature beats fractal
    "JL2AFCL6",  # cardiac regulation
    "QRN8G52V",  # subjective stress cortisol
    "XHS29V4K",  # infant emotion regulation
    "EGXBPFLE",  # editing R-R intervals
]


def _is_label_only(caption_text: str) -> bool:
    """Return True if the caption text matches a label-only pattern."""
    text = caption_text.strip()
    if _TABLE_LABEL_ONLY_RE.match(text):
        return True
    if _FIG_LABEL_ONLY_RE.match(text):
        return True
    return False


def main() -> None:
    config = Config.load()
    zotero = ZoteroClient(config.zotero_data_dir)

    # Per-paper results: (key, short_name, tables, figures, label_only, pages, label_only_details)
    results = []
    all_label_only_details = []

    total_tables = 0
    total_figures = 0
    total_label_only = 0
    total_pages = 0

    for key in CORPUS_KEYS:
        item = zotero.get_item(key)
        if item is None:
            print(f"WARNING: Item {key} not found in Zotero library", file=sys.stderr)
            results.append((key, key, 0, 0, 0, 0, []))
            continue

        pdf_path = item.pdf_path
        if pdf_path is None or not Path(pdf_path).exists():
            print(f"WARNING: PDF not found for {key}", file=sys.stderr)
            results.append((key, key, 0, 0, 0, 0, []))
            continue

        short_name = item.title[:30] if item.title else key

        paper_tables = 0
        paper_figures = 0
        paper_label_only = 0
        paper_pages = 0
        paper_label_only_details = []

        doc = pymupdf.open(str(pdf_path))
        try:
            paper_pages = doc.page_count
            for page_num in range(doc.page_count):
                page = doc[page_num]
                captions = find_all_captions(page)
                for cap in captions:
                    if cap.caption_type == "table":
                        paper_tables += 1
                    elif cap.caption_type == "figure":
                        paper_figures += 1

                    if _is_label_only(cap.text):
                        paper_label_only += 1
                        paper_label_only_details.append({
                            "key": key,
                            "short_name": short_name,
                            "page": page_num + 1,
                            "caption_type": cap.caption_type,
                            "text": cap.text,
                            "bbox": cap.bbox,
                        })
        finally:
            doc.close()

        total_tables += paper_tables
        total_figures += paper_figures
        total_label_only += paper_label_only
        total_pages += paper_pages
        all_label_only_details.extend(paper_label_only_details)

        results.append((key, short_name, paper_tables, paper_figures, paper_label_only, paper_pages, paper_label_only_details))

    # Print summary table
    col_name = 30
    col_tables = 7
    col_figures = 8
    col_label = 11
    col_pages = 6

    header = (
        f"{'Paper':<{col_name}}"
        f"{'Tables':>{col_tables}}"
        f"{'Figures':>{col_figures}}"
        f"{'Label-Only':>{col_label}}"
        f"{'Pages':>{col_pages}}"
    )
    separator = "-" * len(header)

    print()
    print(header)
    print(separator)

    for key, short_name, tables, figures, label_only, pages, _ in results:
        display = f"{short_name[:col_name - 1]}"
        print(
            f"{display:<{col_name}}"
            f"{tables:>{col_tables}}"
            f"{figures:>{col_figures}}"
            f"{label_only:>{col_label}}"
            f"{pages:>{col_pages}}"
        )

    print(separator)
    print(
        f"{'TOTAL':<{col_name}}"
        f"{total_tables:>{col_tables}}"
        f"{total_figures:>{col_figures}}"
        f"{total_label_only:>{col_label}}"
        f"{total_pages:>{col_pages}}"
    )
    print()

    # Print detail for label-only captions
    if all_label_only_details:
        print(f"Label-only captions found ({len(all_label_only_details)} total):")
        print("-" * 70)
        for detail in all_label_only_details:
            bbox_str = "({:.1f}, {:.1f}, {:.1f}, {:.1f})".format(*detail["bbox"])
            print(
                f"  [{detail['key']}] p{detail['page']} "
                f"[{detail['caption_type']}] "
                f"{detail['text']!r} "
                f"bbox={bbox_str}"
            )
        print()
    else:
        print("No label-only captions found.")
        print()

    sys.exit(0)


if __name__ == "__main__":
    main()
