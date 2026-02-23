"""Generate table PNGs and raw text for LLM-based table transcription evaluation.

For each ground truth table in the GT database, this script:
1. Opens the source PDF, navigates to the table's page
2. Renders the table region as a cropped PNG at 200 DPI
3. Extracts the raw text from the table region via get_text()
4. Writes a manifest JSON listing all generated tables

Usage:
    python generate_prompts.py --corpus-json corpus.json
    python generate_prompts.py --from-stress-test

The --from-stress-test flag resolves PDF paths via the Zotero library
(same mechanism as stress_test_real_library.py). The --corpus-json flag
reads a JSON file mapping paper_key to PDF path.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

import pymupdf

from zotero_chunk_rag.feature_extraction.ground_truth import GROUND_TRUTH_DB_PATH


LLM_STRUCTURE_DIR = Path(__file__).resolve().parent
TABLES_DIR = LLM_STRUCTURE_DIR / "tables"
MANIFEST_PATH = LLM_STRUCTURE_DIR / "manifest.json"


def load_gt_tables(db_path: Path) -> list[dict]:
    """Load all ground truth table entries from the database."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT table_id, paper_key, page_num, caption, headers_json, "
            "rows_json, num_rows, num_cols FROM ground_truth_tables "
            "ORDER BY table_id"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def resolve_pdf_paths_from_json(corpus_json_path: Path) -> dict[str, Path]:
    """Load paper_key -> PDF path mapping from a JSON file."""
    with open(corpus_json_path) as f:
        raw = json.load(f)
    return {k: Path(v) for k, v in raw.items()}


def resolve_pdf_paths_from_zotero() -> dict[str, Path]:
    """Resolve PDF paths via the Zotero library client."""
    from zotero_chunk_rag.config import Config
    from zotero_chunk_rag.zotero_client import ZoteroClient

    config = Config.load()
    zotero = ZoteroClient(config.zotero_data_dir)
    all_items = zotero.get_all_items_with_pdfs()
    result: dict[str, Path] = {}
    for item in all_items:
        if item.pdf_path and item.pdf_path.exists():
            result[item.item_key] = item.pdf_path
    return result


def find_table_bbox(
    page: pymupdf.Page,
    gt_entry: dict,
) -> tuple[float, float, float, float] | None:
    """Find the bounding box for a GT table on its page.

    Uses pymupdf's find_tables() to locate a table whose region best matches
    the GT table's expected column count. Falls back to searching for the
    caption text position and estimating a region below it.
    """
    caption = gt_entry.get("caption") or ""
    expected_cols = gt_entry["num_cols"]
    expected_rows = gt_entry["num_rows"]

    tables = page.find_tables()
    if tables and tables.tables:
        best_table = None
        best_score = -1
        for t in tables.tables:
            col_diff = abs(t.col_count - expected_cols)
            row_diff = abs(t.row_count - expected_rows)
            score = -(col_diff * 10 + row_diff)
            if score > best_score:
                best_score = score
                best_table = t
        if best_table is not None:
            return tuple(best_table.bbox)

    if caption:
        text_instances = page.search_for(caption[:60])
        if text_instances:
            cap_rect = text_instances[0]
            x0 = max(0, page.rect.x0)
            y0 = cap_rect.y1
            x1 = page.rect.x1
            y1 = min(page.rect.y1, y0 + (page.rect.height * 0.5))
            return (x0, y0, x1, y1)

    words = page.get_text("words")
    if words:
        all_x0 = min(w[0] for w in words)
        all_y0 = min(w[1] for w in words)
        all_x1 = max(w[2] for w in words)
        all_y1 = max(w[3] for w in words)
        return (all_x0, all_y0, all_x1, all_y1)

    return None


def render_table_png(
    page: pymupdf.Page,
    bbox: tuple[float, float, float, float],
    output_path: Path,
    dpi: int = 200,
) -> None:
    """Render the table region as a cropped PNG."""
    clip = pymupdf.Rect(bbox)
    pixmap = page.get_pixmap(clip=clip, dpi=dpi)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pixmap.save(str(output_path))


def extract_rawtext(
    page: pymupdf.Page,
    bbox: tuple[float, float, float, float],
) -> str:
    """Extract raw text from the table region via get_text()."""
    clip = pymupdf.Rect(bbox)
    return page.get_text("text", clip=clip)


def generate_for_table(
    gt_entry: dict,
    pdf_path: Path,
) -> dict | None:
    """Generate PNG and raw text for a single GT table.

    Returns a manifest entry dict, or None if the table bbox could not be found.
    """
    table_id = gt_entry["table_id"]
    page_num = gt_entry["page_num"]

    doc = pymupdf.open(str(pdf_path))
    try:
        page_index = page_num - 1
        if page_index < 0 or page_index >= len(doc):
            print(f"  [SKIP] {table_id}: page {page_num} out of range", file=sys.stderr)
            return None

        page = doc[page_index]
        bbox = find_table_bbox(page, gt_entry)
        if bbox is None:
            print(f"  [SKIP] {table_id}: could not find table bbox", file=sys.stderr)
            return None

        table_dir = TABLES_DIR / table_id
        table_dir.mkdir(parents=True, exist_ok=True)

        # Render PNG
        png_path = table_dir / "table.png"
        render_table_png(page, bbox, png_path)

        # Extract and save raw text
        rawtext = extract_rawtext(page, bbox)
        rawtext_path = table_dir / "rawtext.txt"
        rawtext_path.write_text(rawtext, encoding="utf-8")

        # Relative path for manifest
        rawtext_rel = str(rawtext_path.relative_to(LLM_STRUCTURE_DIR)).replace("\\", "/")

        return {
            "table_id": table_id,
            "pdf_path": str(pdf_path),
            "page_num": page_num,
            "bbox": list(bbox),
            "rawtext_path": rawtext_rel,
        }
    finally:
        doc.close()


def generate_all(
    pdf_paths: dict[str, Path],
    db_path: Path = GROUND_TRUTH_DB_PATH,
) -> list[dict]:
    """Generate PNGs and raw text for all GT tables.

    Returns the manifest entries list.
    """
    gt_tables = load_gt_tables(db_path)
    manifest_entries: list[dict] = []

    paper_keys_needed = {t["paper_key"] for t in gt_tables}
    missing_keys = paper_keys_needed - set(pdf_paths.keys())
    if missing_keys:
        print(
            f"  [WARN] Missing PDF paths for paper keys: {sorted(missing_keys)}",
            file=sys.stderr,
        )

    for gt_entry in gt_tables:
        paper_key = gt_entry["paper_key"]
        pdf_path = pdf_paths.get(paper_key)
        if pdf_path is None:
            print(
                f"  [SKIP] {gt_entry['table_id']}: no PDF path for {paper_key}",
                file=sys.stderr,
            )
            continue

        entry = generate_for_table(gt_entry, pdf_path)
        if entry is not None:
            manifest_entries.append(entry)
            print(f"  [OK] {entry['table_id']}")

    MANIFEST_PATH.write_text(
        json.dumps(manifest_entries, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nManifest written: {MANIFEST_PATH} ({len(manifest_entries)} tables)")
    return manifest_entries


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate table PNGs and raw text for LLM table transcription."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--corpus-json",
        type=Path,
        help="JSON file mapping paper_key to PDF file path.",
    )
    group.add_argument(
        "--from-stress-test",
        action="store_true",
        help="Resolve PDF paths via the Zotero library (like the stress test).",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=GROUND_TRUTH_DB_PATH,
        help="Path to the ground truth database.",
    )
    args = parser.parse_args()

    if args.corpus_json:
        pdf_paths = resolve_pdf_paths_from_json(args.corpus_json)
    else:
        pdf_paths = resolve_pdf_paths_from_zotero()

    generate_all(pdf_paths, db_path=args.db_path)


if __name__ == "__main__":
    main()
