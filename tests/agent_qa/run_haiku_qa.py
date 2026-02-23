"""Orchestrate haiku vision QA across all tables in the workspace."""
from __future__ import annotations

import asyncio
import base64
import json
import sys
import traceback
from pathlib import Path

import anthropic

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tests" / "agent_qa"))

from run_qa import aggregate_results, parse_agent_response, write_outputs

WORKSPACE = PROJECT_ROOT / "tests" / "agent_qa" / "workspace"
MANIFEST_PATH = WORKSPACE / "manifest.json"
MODEL = "claude-haiku-4-20250414"
BATCH_SIZE = 5


def _build_vision_messages(image_path, extraction_path, table_id):
    image_data = image_path.read_bytes()
    image_b64 = base64.standard_b64encode(image_data).decode("ascii")
    suffix = image_path.suffix.lower()
    media_type = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }.get(suffix, "image/png")
    extraction_json = extraction_path.read_text(encoding="utf-8")

    prompt_text = (
        "You are a quality assurance agent for academic table extraction. "
        "Your job is to visually read the table image below and compare it "
        "cell-by-cell against the automated extraction JSON provided.\n\n"
        "## Instructions\n\n"
        "1. Look at the table image carefully.\n"
        "2. Read the extraction JSON below.\n"
        "3. Compare every cell: first check that the row count and column "
        "count match, then compare each cell value.\n"
        "4. Any difference - missing value, wrong number, extra whitespace, "
        "different formatting - is an error.\n"
        "5. Do NOT guess or infer what the extraction should have produced. "
        "Read the image literally.\n"
        "6. Ignore footnote rows (text below the table grid like Note: or "
        "* p < 0.05). Only compare the tabular grid itself: headers + data rows.\n"
        "7. If the image is too blurry or small to read a cell confidently, "
        'report it as "visual": "UNREADABLE" for that cell.\n\n'
        "## Extraction JSON\n\n"
        "```json\n" + extraction_json + "\n```\n\n"
        "## Output Format\n\n"
        "You MUST output a single JSON object. Do not include any text "
        "before or after it.\n\n"
        "The JSON object must have these fields:\n"
        '- table_id: "' + table_id + '"\n'
        "- matches: true or false\n"
        "- visual_rows: number of data rows you see in the image "
        "(excluding headers)\n"
        "- visual_cols: number of columns you see in the image\n"
        "- extraction_rows: from the extraction JSON\n"
        "- extraction_cols: from the extraction JSON\n"
        "- structural_errors: list of strings describing row/column "
        "count mismatches\n"
        "- errors: list of objects with row, col, visual, extracted fields\n\n"
        "## Row and Column Numbering\n\n"
        "- Rows and columns are 0-indexed.\n"
        "- Headers are row -1. Report header errors with row: -1.\n"
        "- Data rows start at row 0.\n\n"
        "## Rules\n\n"
        "- If the table matches perfectly, set matches: true, "
        "structural_errors: [], errors: [].\n"
        "- Every cell difference is an error. There is no severity.\n"
        "- Do not skip any cells. Compare every single one.\n"
        "- If a header cell differs, report it with row: -1 and the "
        "column index.\n"
    )

    return [{
        "role": "user",
        "content": [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": image_b64,
                },
            },
            {"type": "text", "text": prompt_text},
        ],
    }]


def _failure_result(table_id, reason):
    return {
        "table_id": table_id,
        "matches": False,
        "errors": [],
        "structural_errors": [f"Agent failed: {reason}"],
        "visual_rows": 0,
        "visual_cols": 0,
        "extraction_rows": 0,
        "extraction_cols": 0,
    }


async def _process_one_table(client, entry, semaphore):
    table_id = entry["table_id"]
    image_path = WORKSPACE / entry["image_path"]
    extraction_path = WORKSPACE / entry["extraction_path"]

    if not image_path.exists():
        print(f"  SKIP {table_id}: image not found")
        return _failure_result(table_id, "Image not found")
    if not extraction_path.exists():
        print(f"  SKIP {table_id}: extraction JSON not found")
        return _failure_result(table_id, "Extraction JSON not found")

    async with semaphore:
        print(f"  Processing {table_id}...", flush=True)
        try:
            messages = _build_vision_messages(
                image_path, extraction_path, table_id
            )
            response = await client.messages.create(
                model=MODEL, max_tokens=4096, messages=messages,
            )
            response_text = response.content[0].text
            result = parse_agent_response(response_text)
            result["table_id"] = table_id
            status = "PASS" if result.get("matches", False) else "FAIL"
            n_err = len(result.get("errors", [])) + len(
                result.get("structural_errors", [])
            )
            print(f"  Done {table_id}: {status} ({n_err} errors)", flush=True)
            return result
        except Exception as e:
            print(f"  ERROR {table_id}: {e}")
            traceback.print_exc()
            return _failure_result(table_id, str(e))


async def main():
    print("=" * 60)
    print("Agent QA: Haiku Vision QA for Table Extraction")
    print("=" * 60)

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    print(f"\nLoaded manifest with {len(manifest)} tables")

    client = anthropic.AsyncAnthropic()
    semaphore = asyncio.Semaphore(BATCH_SIZE)
    tasks = [
        _process_one_table(client, entry, semaphore) for entry in manifest
    ]

    print(f"\nProcessing {len(tasks)} tables (batch size {BATCH_SIZE})...\n")
    results = await asyncio.gather(*tasks)

    print("\nAggregating results...")
    qa_results, qa_report = aggregate_results(results)

    print("Writing outputs...")
    results_path, report_path = write_outputs(qa_results, qa_report, WORKSPACE)

    print(f"\nResults written to:")
    print(f"  {results_path}")
    print(f"  {report_path}")

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total tables: {qa_results['total_tables']}")
    print(f"Tables matching: {qa_results['tables_matching']}")
    print(f"Tables with errors: {qa_results['tables_with_errors']}")
    print(f"Total errors: {qa_results['total_errors']}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
