"""Agent QA orchestration script.

This module provides the tools to orchestrate QA across all tables in the
QA workspace. It is designed to be called FROM a Claude Code session — it
reads the manifest and the calling agent spawns one haiku Task agent per
table.

Each agent receives the table image (via Read tool) and extraction JSON,
visually reads the image, compares against the extraction, and returns a
cell-level diff JSON.

The run script aggregates all per-table results into two output files:
  - ``tests/agent_qa/workspace/qa_results.json`` — machine-readable, all diffs
  - ``tests/agent_qa/workspace/qa_report.md`` — human-readable summary

Usage::

    This script is NOT directly executable. Invoke from a Claude Code session:
    1. Run prepare_qa.py to create the workspace
    2. Read manifest.json
    3. For each table entry, use the Task tool (haiku model) with build_agent_prompt()
    4. Parse each response with parse_agent_response()
    5. Aggregate with aggregate_results() and write with write_outputs()
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

_PROMPT_TEMPLATE_PATH = Path(__file__).resolve().parent / "qa_prompt.md"


def build_agent_prompt(
    image_path: str,
    extraction_json_path: str,
    table_id: str,
) -> str:
    """Build a complete QA prompt for a single table.

    Reads the ``qa_prompt.md`` template and substitutes the three variables.

    Parameters
    ----------
    image_path:
        Absolute or relative path to the table PNG image.
    extraction_json_path:
        Absolute or relative path to the extraction JSON file.
    table_id:
        The table's unique identifier.

    Returns
    -------
    str
        The fully substituted prompt string.
    """
    template = _PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")
    result = template.replace("{IMAGE_PATH}", image_path)
    result = result.replace("{EXTRACTION_JSON_PATH}", extraction_json_path)
    result = result.replace("{TABLE_ID}", table_id)
    return result


def parse_agent_response(response_text: str) -> dict:
    """Extract and parse the JSON object from an agent's response.

    Handles three formats:
    1. Clean JSON (the entire response is valid JSON)
    2. Fenced JSON (wrapped in ```json ... ``` markers)
    3. JSON with preamble text (e.g. "Here are the results:\\n{...}")

    Parameters
    ----------
    response_text:
        The raw text returned by the agent.

    Returns
    -------
    dict
        The parsed JSON result.

    Raises
    ------
    ValueError
        If no valid JSON object can be found in the response.
    """
    text = response_text.strip()

    # Strategy 1: Clean JSON
    if text.startswith("{"):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

    # Strategy 2: Fenced JSON (```json ... ``` or ``` ... ```)
    fence_match = re.search(r"```(?:json)?\s*\n(\{.*?\})\s*\n```", text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    # Strategy 3: Find the first { ... } block in the text
    brace_match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    # Strategy 4: More aggressive — find outermost braces
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace >= 0 and last_brace > first_brace:
        candidate = text[first_brace:last_brace + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    raise ValueError(
        f"No valid JSON object found in agent response. "
        f"Response starts with: {text[:200]!r}"
    )


def aggregate_results(results: list[dict]) -> tuple[dict, str]:
    """Aggregate per-table QA results into summary and report.

    Parameters
    ----------
    results:
        List of per-table result dicts (as returned by ``parse_agent_response``).

    Returns
    -------
    tuple[dict, str]
        A tuple of (qa_results dict, qa_report markdown string).
    """
    total_tables = len(results)
    tables_matching = sum(1 for r in results if r.get("matches", False))
    tables_with_errors = total_tables - tables_matching

    total_errors = 0
    for r in results:
        total_errors += len(r.get("errors", []))
        total_errors += len(r.get("structural_errors", []))

    qa_results = {
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "total_tables": total_tables,
        "tables_matching": tables_matching,
        "tables_with_errors": tables_with_errors,
        "total_errors": total_errors,
        "results": results,
    }

    # Build markdown report
    lines: list[str] = []
    lines.append("# Agent QA Report")
    lines.append("")
    lines.append(f"**Run timestamp**: {qa_results['run_timestamp']}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Total tables**: {total_tables}")
    lines.append(f"- **{tables_matching}/{total_tables} tables match**")
    lines.append(f"- **Tables with errors**: {tables_with_errors}")
    lines.append(f"- **Total errors**: {total_errors}")
    lines.append("")

    # Summary table
    lines.append("| Paper | Table ID | Status | Errors |")
    lines.append("|-------|----------|--------|--------|")
    for r in results:
        table_id = r.get("table_id", "unknown")
        status = "PASS" if r.get("matches", False) else "FAIL"
        error_count = len(r.get("errors", [])) + len(r.get("structural_errors", []))
        lines.append(f"| {table_id.split('_')[0] if '_' in table_id else '?'} | {table_id} | {status} | {error_count} |")
    lines.append("")

    # Per-table detail sections for tables with errors
    error_tables = [r for r in results if not r.get("matches", False)]
    if error_tables:
        lines.append("## Error Details")
        lines.append("")
        for r in error_tables:
            table_id = r.get("table_id", "unknown")
            lines.append(f"### {table_id}")
            lines.append("")
            lines.append(f"- Visual: {r.get('visual_rows', '?')} rows x {r.get('visual_cols', '?')} cols")
            lines.append(f"- Extraction: {r.get('extraction_rows', '?')} rows x {r.get('extraction_cols', '?')} cols")
            lines.append("")

            structural = r.get("structural_errors", [])
            if structural:
                lines.append("**Structural errors:**")
                for se in structural:
                    lines.append(f"- {se}")
                lines.append("")

            errors = r.get("errors", [])
            if errors:
                lines.append("**Cell errors:**")
                lines.append("")
                lines.append("| Row | Col | Visual | Extracted |")
                lines.append("|-----|-----|--------|-----------|")
                for e in errors:
                    lines.append(f"| {e.get('row', '?')} | {e.get('col', '?')} | {e.get('visual', '')} | {e.get('extracted', '')} |")
                lines.append("")

    qa_report = "\n".join(lines)
    return qa_results, qa_report


def write_outputs(
    qa_results: dict,
    qa_report: str,
    output_dir: Path,
) -> tuple[Path, Path]:
    """Write QA results and report to the output directory.

    Parameters
    ----------
    qa_results:
        The aggregated QA results dict.
    qa_report:
        The markdown report string.
    output_dir:
        Directory to write output files into.

    Returns
    -------
    tuple[Path, Path]
        Paths to (qa_results.json, qa_report.md).
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results_path = output_dir / "qa_results.json"
    results_path.write_text(
        json.dumps(qa_results, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    report_path = output_dir / "qa_report.md"
    report_path.write_text(qa_report, encoding="utf-8")

    return results_path, report_path


if __name__ == "__main__":
    print("This script is not directly executable.")
    print()
    print("Usage from a Claude Code session:")
    print("  1. Run prepare_qa.py to create the workspace")
    print("  2. Read manifest.json from tests/agent_qa/workspace/")
    print("  3. For each table, spawn a haiku Task agent with build_agent_prompt()")
    print("  4. Parse each response with parse_agent_response()")
    print("  5. Call aggregate_results() and write_outputs()")
