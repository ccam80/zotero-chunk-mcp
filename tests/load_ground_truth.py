"""Load verified ground truth files from the workspace into the ground truth database.

This standalone script scans ``tests/ground_truth_workspace/`` for verified
``table_*_gt.json`` files and inserts them into ``tests/ground_truth.db`` via
the Phase 1 API.

Usage::

    "./.venv/Scripts/python.exe" tests/load_ground_truth.py

Only files with ``"verified": true`` are loaded.  Unverified files are skipped.
Re-running the script is safe (idempotent) -- existing entries are updated via
``INSERT OR REPLACE``.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from zotero_chunk_rag.feature_extraction.ground_truth import (
    create_ground_truth_db,
    insert_ground_truth,
)


def load_verified_ground_truth(
    workspace_dir: Path,
    db_path: Path,
) -> dict:
    """Scan the workspace for verified GT files and load them into the database.

    Parameters
    ----------
    workspace_dir:
        Root of the ground truth workspace (contains one subdirectory per paper).
    db_path:
        Path to the ground truth database.  Created if it does not exist.

    Returns
    -------
    dict
        Summary with keys ``"loaded"`` (int), ``"skipped_unverified"`` (int),
        and ``"errors"`` (list of str).
    """
    workspace_dir = Path(workspace_dir)
    db_path = Path(db_path)

    create_ground_truth_db(db_path)

    loaded = 0
    skipped_unverified = 0
    errors: list[str] = []

    for paper_dir in sorted(workspace_dir.iterdir()):
        if not paper_dir.is_dir():
            continue

        for gt_file in sorted(paper_dir.glob("table_*_gt.json")):
            try:
                data = json.loads(gt_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                errors.append(f"{gt_file}: {exc}")
                continue

            if not data.get("verified", False):
                skipped_unverified += 1
                continue

            try:
                insert_ground_truth(
                    db_path=db_path,
                    table_id=data["table_id"],
                    paper_key=data["item_key"],
                    page_num=data["page_num"],
                    caption=data.get("caption", ""),
                    headers=data.get("headers", []),
                    rows=data.get("rows", []),
                    notes=data.get("notes", ""),
                    footnotes=data.get("footnotes", ""),
                )
                loaded += 1
            except Exception as exc:
                errors.append(f"{gt_file}: insert failed: {exc}")

    return {
        "loaded": loaded,
        "skipped_unverified": skipped_unverified,
        "errors": errors,
    }


if __name__ == "__main__":
    workspace = _PROJECT_ROOT / "tests" / "ground_truth_workspace"
    db = _PROJECT_ROOT / "tests" / "ground_truth.db"
    print(f"Loading verified ground truth from {workspace}")
    print(f"Database: {db}")
    result = load_verified_ground_truth(workspace, db)
    print(f"Loaded: {result['loaded']}")
    print(f"Skipped (unverified): {result['skipped_unverified']}")
    if result["errors"]:
        print(f"Errors ({len(result['errors'])}):")
        for err in result["errors"]:
            print(f"  {err}")
    if result["errors"]:
        sys.exit(1)
    print("Done.")
