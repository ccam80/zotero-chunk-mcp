"""Extract raw text from PDF table regions for ground truth reconciliation.

For each table in the ground truth workspace, this script:
1. Reads the bbox from the extraction JSON
2. Opens the PDF via ZoteroClient
3. Extracts text via page.get_text("text", clip=bbox)
4. Also extracts words via page.get_text("words", clip=bbox) for word-level analysis
5. Writes raw text to table_N_rawtext.txt alongside the GT files

Usage::

    "./.venv/Scripts/python.exe" tests/extract_table_text.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

import pymupdf

from zotero_chunk_rag.config import Config
from zotero_chunk_rag.zotero_client import ZoteroClient


def _resolve_pdf_paths() -> dict[str, Path]:
    config = Config.load()
    zotero = ZoteroClient(config.zotero_data_dir)
    items = zotero.get_all_items_with_pdfs()
    return {
        item.item_key: item.pdf_path
        for item in items
        if item.pdf_path and item.pdf_path.exists()
    }


def extract_all(workspace_dir: Path) -> None:
    pdf_paths = _resolve_pdf_paths()

    paper_dirs = sorted(
        p for p in workspace_dir.iterdir()
        if p.is_dir() and (p / "manifest.json").exists()
    )

    total = 0
    skipped = 0

    for paper_dir in paper_dirs:
        manifest = json.loads((paper_dir / "manifest.json").read_text(encoding="utf-8"))
        item_key = manifest["item_key"]
        short_name = manifest["paper"]

        pdf_path = pdf_paths.get(item_key)
        if not pdf_path:
            print(f"  [{short_name}] SKIP — no PDF found for {item_key}")
            skipped += manifest["num_tables"]
            continue

        doc = pymupdf.open(str(pdf_path))

        for table_info in manifest["tables"]:
            idx = table_info["table_index"]
            page_num = table_info["page_num"]

            # Read bbox from extraction JSON
            ext_path = paper_dir / table_info["extraction_path"]
            if not ext_path.exists():
                print(f"  [{short_name}] table_{idx} SKIP — no extraction JSON")
                skipped += 1
                continue

            ext_data = json.loads(ext_path.read_text(encoding="utf-8"))
            bbox = ext_data.get("bbox")
            if not bbox or bbox == [0, 0, 0, 0]:
                print(f"  [{short_name}] table_{idx} SKIP — no bbox")
                skipped += 1
                continue

            # Extract text from PDF
            page = doc[page_num - 1]  # 0-indexed
            clip = pymupdf.Rect(bbox)

            # Raw text extraction
            raw_text = page.get_text("text", clip=clip)

            # Word-level extraction (for detailed analysis)
            words = page.get_text("words", clip=clip)
            # words is list of (x0, y0, x1, y1, text, block_no, line_no, word_no)

            # Write output
            output = []
            output.append(f"Paper: {short_name}")
            output.append(f"Table index: {idx}")
            output.append(f"Page: {page_num}")
            output.append(f"Caption: {table_info['caption']}")
            output.append(f"Artifact: {table_info.get('artifact_type', 'none')}")
            output.append(f"Bbox: {bbox}")
            output.append(f"Word count: {len(words)}")
            output.append("")
            output.append("=" * 60)
            output.append("RAW TEXT (get_text('text', clip=bbox))")
            output.append("=" * 60)
            output.append(raw_text)
            output.append("")
            output.append("=" * 60)
            output.append("WORDS (get_text('words', clip=bbox))")
            output.append("=" * 60)
            for w in words:
                x0, y0, x1, y1 = w[0], w[1], w[2], w[3]
                text = w[4]
                block_no, line_no, word_no = w[5], w[6], w[7]
                output.append(f"  [{block_no}:{line_no}:{word_no}] ({x0:.1f},{y0:.1f})–({x1:.1f},{y1:.1f}) '{text}'")

            rawtext_path = paper_dir / f"table_{idx}_rawtext.txt"
            rawtext_path.write_text("\n".join(output), encoding="utf-8")
            total += 1

        doc.close()
        print(f"  [{short_name}] {len(manifest['tables'])} tables extracted")

    print(f"\nDone. {total} tables extracted, {skipped} skipped.")


if __name__ == "__main__":
    workspace = _PROJECT_ROOT / "tests" / "ground_truth_workspace"
    print(f"Extracting text from table regions...")
    print(f"Workspace: {workspace}")
    extract_all(workspace)
