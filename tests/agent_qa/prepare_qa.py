"""Prepare a QA workspace from the stress test debug database.

This standalone script reads ``_stress_test_debug.db``, renders every non-artifact
table as a 300 DPI PNG via ``render_table_image()``, writes each table's
extraction data as JSON, and produces a manifest mapping every table to its
image and extraction files.

The workspace lives at ``tests/agent_qa/workspace/`` (gitignored).

Usage::

    "./.venv/Scripts/python.exe" tests/agent_qa/prepare_qa.py

Requires a recent ``_stress_test_debug.db`` in the project root (produced by
running ``tests/stress_test_real_library.py``).
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from zotero_chunk_rag.feature_extraction.ground_truth import make_table_id
from zotero_chunk_rag.feature_extraction.render import render_table_image

# Re-use PDF path resolution from the ground truth workspace script.
from tests.create_ground_truth import _resolve_pdf_paths


def prepare_qa_workspace(
    debug_db_path: Path,
    output_dir: Path,
    *,
    pdf_paths: dict[str, Path] | None = None,
) -> Path:
    """Build a QA workspace from a stress test debug database.

    Parameters
    ----------
    debug_db_path:
        Path to ``_stress_test_debug.db``.
    output_dir:
        Root directory for the workspace (one subdirectory per paper).
    pdf_paths:
        Optional pre-resolved mapping of ``item_key -> pdf_path``.
        When *None*, the function resolves paths via the Zotero client.

    Returns
    -------
    Path
        Path to the generated ``manifest.json``.
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
        rows = conn.execute(
            """
            SELECT
                et.id,
                et.item_key,
                et.table_index,
                et.page_num,
                et.caption,
                et.num_rows,
                et.num_cols,
                et.fill_rate,
                et.headers_json,
                et.rows_json,
                et.bbox,
                et.artifact_type,
                et.extraction_strategy,
                p.short_name
            FROM extracted_tables et
            JOIN papers p ON et.item_key = p.item_key
            WHERE et.artifact_type IS NULL
            ORDER BY p.short_name, et.table_index
            """
        ).fetchall()

        manifest_entries: list[dict] = []

        for table_row in rows:
            item_key = table_row["item_key"]
            short_name = table_row["short_name"]
            idx = table_row["table_index"]
            page_num = table_row["page_num"]
            caption = table_row["caption"]

            bbox_raw = table_row["bbox"]
            bbox_list = json.loads(bbox_raw) if bbox_raw else [0, 0, 0, 0]
            bbox_tuple = tuple(float(v) for v in bbox_list)

            headers = json.loads(table_row["headers_json"]) if table_row["headers_json"] else []
            rows_data = json.loads(table_row["rows_json"]) if table_row["rows_json"] else []

            table_id = make_table_id(item_key, caption, page_num, idx)

            paper_dir = output_dir / short_name
            paper_dir.mkdir(parents=True, exist_ok=True)

            # Render table image
            image_path = paper_dir / f"table_{idx}.png"
            pdf_path = pdf_paths.get(item_key)
            if pdf_path and pdf_path.exists():
                render_table_image(
                    pdf_path,
                    page_num,
                    bbox_tuple,
                    image_path,
                    dpi=300,
                )

            # Write extraction JSON
            extraction_data = {
                "table_id": table_id,
                "paper": short_name,
                "item_key": item_key,
                "page_num": page_num,
                "table_index": idx,
                "caption": caption,
                "headers": headers,
                "rows": rows_data,
                "num_rows": table_row["num_rows"],
                "num_cols": table_row["num_cols"],
                "fill_rate": table_row["fill_rate"],
                "bbox": bbox_list,
                "extraction_strategy": table_row["extraction_strategy"],
            }
            extraction_path = paper_dir / f"table_{idx}_extraction.json"
            extraction_path.write_text(
                json.dumps(extraction_data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            # Collect manifest entry
            manifest_entries.append({
                "table_id": table_id,
                "paper": short_name,
                "item_key": item_key,
                "page_num": page_num,
                "table_index": idx,
                "caption": caption,
                "image_path": f"{short_name}/table_{idx}.png",
                "extraction_path": f"{short_name}/table_{idx}_extraction.json",
                "num_rows": table_row["num_rows"],
                "num_cols": table_row["num_cols"],
            })

        # Write manifest
        manifest_path = output_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest_entries, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        print(f"QA workspace: {len(manifest_entries)} non-artifact tables across {len(set(e['paper'] for e in manifest_entries))} papers")

    finally:
        conn.close()

    return manifest_path


if __name__ == "__main__":
    db_path = _PROJECT_ROOT / "_stress_test_debug.db"
    workspace_dir = _PROJECT_ROOT / "tests" / "agent_qa" / "workspace"
    print(f"Creating QA workspace from {db_path}")
    print(f"Output directory: {workspace_dir}")
    prepare_qa_workspace(db_path, workspace_dir)
    print("Done.")
