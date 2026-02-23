"""Score LLM markdown table responses against ground truth.

For each response_<model>.md file in the tables directories, this module:
1. Parses the markdown via parse_markdown.load_response()
2. Calls compare_extraction() from feature_extraction/ground_truth.py
3. Collects fuzzy_accuracy_pct, cell_accuracy_pct, shape, diffs
4. Optionally writes results into _stress_test_debug.db method_results table

CLI: python -m tests.llm_structure.evaluate
"""
from __future__ import annotations

import json
import sqlite3
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from zotero_chunk_rag.feature_extraction.ground_truth import (
    GROUND_TRUTH_DB_PATH,
    ComparisonResult,
    compare_extraction,
)

from . import parse_markdown

LLM_STRUCTURE_DIR = Path(__file__).resolve().parent
TABLES_DIR = LLM_STRUCTURE_DIR / "tables"
MANIFEST_PATH = LLM_STRUCTURE_DIR / "manifest.json"


@dataclass
class EvaluationResult:
    """Result of evaluating one LLM response against ground truth."""
    table_id: str
    model: str
    fuzzy_accuracy_pct: float
    fuzzy_precision_pct: float
    fuzzy_recall_pct: float
    cell_accuracy_pct: float
    structural_coverage_pct: float
    gt_shape: tuple[int, int]
    ext_shape: tuple[int, int]
    num_cell_diffs: int
    num_header_diffs: int
    num_extra_cols: int
    num_missing_cols: int
    num_extra_rows: int
    num_missing_rows: int
    footnote_match: bool | None


def evaluate_response(
    table_id: str,
    model: str,
    response_path: Path,
    db_path: Path = GROUND_TRUTH_DB_PATH,
) -> EvaluationResult | None:
    """Evaluate a single LLM response against ground truth.

    Returns None if the response cannot be parsed or has no table content.
    """
    try:
        headers, rows, footnotes = parse_markdown.load_response(response_path)
    except Exception as e:
        print(f"  [ERROR] {table_id}/{model}: parse failed: {e}", file=sys.stderr)
        return None

    if not headers:
        print(f"  [SKIP] {table_id}/{model}: no headers parsed", file=sys.stderr)
        return None

    try:
        cr = compare_extraction(
            db_path=db_path,
            table_id=table_id,
            headers=headers,
            rows=rows,
            footnotes=footnotes,
        )
    except KeyError as e:
        print(f"  [ERROR] {table_id}/{model}: {e}", file=sys.stderr)
        return None

    return EvaluationResult(
        table_id=table_id,
        model=model,
        fuzzy_accuracy_pct=cr.fuzzy_accuracy_pct,
        fuzzy_precision_pct=cr.fuzzy_precision_pct,
        fuzzy_recall_pct=cr.fuzzy_recall_pct,
        cell_accuracy_pct=cr.cell_accuracy_pct,
        structural_coverage_pct=cr.structural_coverage_pct,
        gt_shape=cr.gt_shape,
        ext_shape=cr.ext_shape,
        num_cell_diffs=len(cr.cell_diffs),
        num_header_diffs=len(cr.header_diffs),
        num_extra_cols=len(cr.extra_columns),
        num_missing_cols=len(cr.missing_columns),
        num_extra_rows=len(cr.extra_rows),
        num_missing_rows=len(cr.missing_rows),
        footnote_match=cr.footnote_match,
    )


def find_responses(tables_dir: Path = TABLES_DIR) -> list[tuple[str, str, Path]]:
    """Find all response_<model>.md files.

    Returns list of (table_id, model, response_path).
    """
    results: list[tuple[str, str, Path]] = []
    if not tables_dir.exists():
        return results

    for table_dir in sorted(tables_dir.iterdir()):
        if not table_dir.is_dir():
            continue
        table_id = table_dir.name
        for response_file in sorted(table_dir.glob("response_*.md")):
            # Extract model name from response_<model>.md
            stem = response_file.stem  # response_<model>
            model = stem.replace("response_", "", 1)
            results.append((table_id, model, response_file))

    return results


def evaluate_all(
    tables_dir: Path = TABLES_DIR,
    db_path: Path = GROUND_TRUTH_DB_PATH,
) -> list[EvaluationResult]:
    """Evaluate all response files against ground truth.

    Returns list of EvaluationResult for successful evaluations.
    """
    responses = find_responses(tables_dir)
    if not responses:
        print("No response files found.", file=sys.stderr)
        return []

    results: list[EvaluationResult] = []
    for table_id, model, response_path in responses:
        result = evaluate_response(table_id, model, response_path, db_path=db_path)
        if result is not None:
            results.append(result)

    return results


def write_to_debug_db(
    debug_db_path: Path,
    tables_dir: Path = TABLES_DIR,
    gt_db_path: Path = GROUND_TRUTH_DB_PATH,
) -> int:
    """Parse LLM responses, evaluate against GT, and write into the debug DB.

    Inserts one ``method_results`` row per (table_id, model) combination,
    using method_name format ``llm_{model}+llm`` to match the pipeline's
    ``structure+cell`` convention.

    Returns the number of rows written.
    """
    from zotero_chunk_rag.feature_extraction.debug_db import (
        create_extended_tables,
        write_method_result,
    )

    if not debug_db_path.exists():
        print(f"Debug DB not found: {debug_db_path}", file=sys.stderr)
        return 0

    responses = find_responses(tables_dir)
    if not responses:
        print("No LLM response files found.", file=sys.stderr)
        return 0

    conn = sqlite3.connect(str(debug_db_path))
    conn.row_factory = sqlite3.Row
    try:
        create_extended_tables(conn)

        # Remove previous LLM rows to avoid duplicates on re-run
        conn.execute("DELETE FROM method_results WHERE method_name LIKE 'llm_%+llm'")

        written = 0
        for table_id, model, response_path in responses:
            try:
                headers, rows, footnotes = parse_markdown.load_response(response_path)
            except Exception:
                continue
            if not headers:
                continue

            # Compute quality score via GT comparison
            quality_score: float | None = None
            try:
                cr = compare_extraction(
                    db_path=gt_db_path,
                    table_id=table_id,
                    headers=headers,
                    rows=rows,
                    footnotes=footnotes,
                )
                quality_score = cr.fuzzy_accuracy_pct
            except KeyError:
                pass

            # Build cell_grid_json in the same format as pipeline methods
            cell_grid = {
                "headers": headers,
                "rows": rows,
                "col_boundaries": [],
                "row_boundaries": [],
                "method": "llm",
                "structure_method": f"llm_{model}",
            }

            method_name = f"llm_{model}+llm"
            write_method_result(
                conn,
                table_id=table_id,
                method_name=method_name,
                boundaries_json=json.dumps({
                    "structure_method": f"llm_{model}",
                    "cell_method": "llm",
                    "col_boundaries": [],
                    "row_boundaries": [],
                }),
                cell_grid_json=json.dumps(cell_grid, ensure_ascii=False),
                quality_score=quality_score,
                execution_time_ms=None,
            )
            written += 1

        conn.commit()
        print(f"Wrote {written} LLM method_results rows to {debug_db_path.name}")
        return written
    finally:
        conn.close()


def format_results_table(results: list[EvaluationResult]) -> str:
    """Format evaluation results as a markdown table."""
    if not results:
        return "No results to display."

    lines: list[str] = []
    lines.append(
        "| Table ID | Model | Fuzzy Acc% | Cell Acc% | Coverage% | "
        "GT Shape | Ext Shape | Cell Diffs | Hdr Diffs |"
    )
    lines.append(
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"
    )

    for r in sorted(results, key=lambda x: (x.table_id, x.model)):
        lines.append(
            f"| {r.table_id} | {r.model} | {r.fuzzy_accuracy_pct:.1f} | "
            f"{r.cell_accuracy_pct:.1f} | {r.structural_coverage_pct:.1f} | "
            f"{r.gt_shape[0]}x{r.gt_shape[1]} | {r.ext_shape[0]}x{r.ext_shape[1]} | "
            f"{r.num_cell_diffs} | {r.num_header_diffs} |"
        )

    return "\n".join(lines)


def format_summary(results: list[EvaluationResult]) -> str:
    """Format aggregate summary statistics."""
    if not results:
        return "No results."

    models = sorted(set(r.model for r in results))
    lines: list[str] = []
    lines.append("## Summary\n")

    for model in models:
        model_results = [r for r in results if r.model == model]
        n = len(model_results)
        avg_fuzzy = sum(r.fuzzy_accuracy_pct for r in model_results) / n
        avg_cell = sum(r.cell_accuracy_pct for r in model_results) / n
        avg_coverage = sum(r.structural_coverage_pct for r in model_results) / n
        median_fuzzy = sorted(r.fuzzy_accuracy_pct for r in model_results)[n // 2]

        lines.append(f"### {model} (n={n})")
        lines.append(f"- Mean fuzzy accuracy: {avg_fuzzy:.1f}%")
        lines.append(f"- Median fuzzy accuracy: {median_fuzzy:.1f}%")
        lines.append(f"- Mean cell accuracy: {avg_cell:.1f}%")
        lines.append(f"- Mean structural coverage: {avg_coverage:.1f}%")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    """CLI entry point."""
    results = evaluate_all()
    if not results:
        print("No evaluation results.")
        return

    print(format_results_table(results))
    print()
    print(format_summary(results))


if __name__ == "__main__":
    main()
