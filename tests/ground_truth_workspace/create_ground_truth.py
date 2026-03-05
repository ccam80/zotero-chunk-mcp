"""Create a ground truth workspace from the stress test debug database.

This standalone script reads ``_stress_test_debug.db`` and creates a workspace
directory with one subdirectory per paper.  For each table (including artifacts),
the script renders the table region as a PNG image and writes the current
extraction output as JSON alongside an empty ground truth template.

Usage::

    "./.venv/Scripts/python.exe" tests/create_ground_truth.py

Requires a recent ``_stress_test_debug.db`` in the project root (produced by
running ``tests/stress_test_real_library.py``).
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

# Ensure the project source is importable when run as a script.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from zotero_chunk_rag.config import Config
from zotero_chunk_rag.feature_extraction.ground_truth import make_table_id
from zotero_chunk_rag.feature_extraction.render import render_table_image
from zotero_chunk_rag.zotero_client import ZoteroClient


def _resolve_pdf_paths() -> dict[str, Path]:
    """Return a mapping of ``item_key -> pdf_path`` for all Zotero items."""
    config = Config.load()
    zotero = ZoteroClient(config.zotero_data_dir)
    items = zotero.get_all_items_with_pdfs()
    return {
        item.item_key: item.pdf_path
        for item in items
        if item.pdf_path and item.pdf_path.exists()
    }


def create_workspace(
    debug_db_path: Path,
    output_dir: Path,
    *,
    pdf_paths: dict[str, Path] | None = None,
) -> None:
    """Build a ground truth workspace from a stress test debug database.

    Parameters
    ----------
    debug_db_path:
        Path to ``_stress_test_debug.db``.
    output_dir:
        Root directory for the workspace (one subdirectory per paper).
    pdf_paths:
        Optional pre-resolved mapping of ``item_key -> pdf_path``.
        When *None*, the function resolves paths via the Zotero client.
    """
    debug_db_path = Path(debug_db_path)
    output_dir = Path(output_dir)

    if not debug_db_path.exists():
        raise FileNotFoundError(f"Debug database not found: {debug_db_path}")

    if pdf_paths is None:
        pdf_paths = _resolve_pdf_paths()

    conn = sqlite3.connect(str(debug_db_path))
    conn.row_factory = sqlite3.Row
    try:
        papers = conn.execute(
            "SELECT item_key, short_name FROM papers ORDER BY short_name"
        ).fetchall()

        for paper in papers:
            item_key = paper["item_key"]
            short_name = paper["short_name"]
            paper_dir = output_dir / short_name
            paper_dir.mkdir(parents=True, exist_ok=True)

            tables = conn.execute(
                "SELECT * FROM extracted_tables WHERE item_key = ? ORDER BY table_index",
                (item_key,),
            ).fetchall()

            manifest_tables: list[dict] = []

            for table_row in tables:
                idx = table_row["table_index"]
                page_num = table_row["page_num"]
                caption = table_row["caption"]
                artifact_type = table_row["artifact_type"]

                # Parse bbox from JSON text
                bbox_raw = table_row["bbox"]
                bbox_list = json.loads(bbox_raw) if bbox_raw else [0, 0, 0, 0]
                bbox_tuple = tuple(float(v) for v in bbox_list)

                # Generate table ID
                table_id = make_table_id(item_key, caption, page_num, idx)

                # Parse headers and rows from JSON
                headers = json.loads(table_row["headers_json"]) if table_row["headers_json"] else []
                rows = json.loads(table_row["rows_json"]) if table_row["rows_json"] else []

                # --- Render table image ---
                image_path = paper_dir / f"table_{idx}.png"
                pdf_path = pdf_paths.get(item_key)
                if pdf_path and pdf_path.exists():
                    render_table_image(
                        pdf_path,
                        page_num,
                        bbox_tuple,
                        image_path,
                    )

                # --- Write extraction JSON ---
                extraction_data = {
                    "paper": short_name,
                    "item_key": item_key,
                    "page_num": page_num,
                    "table_index": idx,
                    "caption": caption,
                    "caption_position": table_row["caption_position"],
                    "headers": headers,
                    "rows": rows,
                    "num_rows": table_row["num_rows"],
                    "num_cols": table_row["num_cols"],
                    "fill_rate": table_row["fill_rate"],
                    "bbox": bbox_list,
                    "artifact_type": artifact_type,
                    "extraction_strategy": table_row["extraction_strategy"],
                    "footnotes": "",
                    "reference_context": table_row["reference_context"] or "",
                    "markdown": table_row["markdown"] or "",
                }
                extraction_path = paper_dir / f"table_{idx}_extraction.json"
                extraction_path.write_text(
                    json.dumps(extraction_data, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )

                # --- Write GT template ---
                gt_data = {
                    "table_id": table_id,
                    "paper": short_name,
                    "item_key": item_key,
                    "page_num": page_num,
                    "table_index": idx,
                    "caption": caption,
                    "headers": [],
                    "rows": [],
                    "notes": "",
                    "verified": False,
                }
                gt_path = paper_dir / f"table_{idx}_gt.json"
                gt_path.write_text(
                    json.dumps(gt_data, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )

                # --- Collect manifest entry ---
                manifest_tables.append({
                    "table_index": idx,
                    "table_id": table_id,
                    "page_num": page_num,
                    "caption": caption,
                    "artifact_type": artifact_type,
                    "image_path": f"table_{idx}.png",
                    "extraction_path": f"table_{idx}_extraction.json",
                    "gt_path": f"table_{idx}_gt.json",
                })

            # --- Write manifest ---
            manifest = {
                "paper": short_name,
                "item_key": item_key,
                "num_tables": len(manifest_tables),
                "tables": manifest_tables,
            }
            manifest_path = paper_dir / "manifest.json"
            manifest_path.write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            print(f"  [{short_name}] {len(manifest_tables)} tables")

    finally:
        conn.close()


if __name__ == "__main__":
    db_path = _PROJECT_ROOT / "_stress_test_debug.db"
    workspace_dir = _PROJECT_ROOT / "tests" / "ground_truth_workspace"
    print(f"Creating ground truth workspace from {db_path}")
    print(f"Output directory: {workspace_dir}")
    create_workspace(db_path, workspace_dir)
    print("Done.")
