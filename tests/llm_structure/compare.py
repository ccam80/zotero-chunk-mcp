"""Compare LLM markdown table accuracy against pipeline extraction accuracy.

Loads LLM results from evaluate module + pipeline results from
_stress_test_debug.db. Produces comparison_report.md.

CLI: python -m tests.llm_structure.compare
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

from .evaluate import (
    TABLES_DIR,
    EvaluationResult,
    evaluate_all,
    write_to_debug_db,
)

LLM_STRUCTURE_DIR = Path(__file__).resolve().parent
DEFAULT_DEBUG_DB = Path(__file__).resolve().parents[2] / "_stress_test_debug.db"
DEFAULT_OUTPUT = LLM_STRUCTURE_DIR / "comparison_report.md"


def _load_pipeline_accuracies(db_path: Path) -> dict[str, float]:
    """Load pipeline fuzzy accuracy per table from the stress test debug DB.

    Uses ground_truth_diffs table. Returns {table_id: cell_accuracy_pct}.
    """
    if not db_path.exists():
        return {}

    conn = sqlite3.connect(str(db_path))
    try:
        # Check if ground_truth_diffs table exists
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if "ground_truth_diffs" not in tables:
            return {}

        rows = conn.execute(
            "SELECT table_id, cell_accuracy_pct FROM ground_truth_diffs"
        ).fetchall()
        return {row[0]: row[1] for row in rows if row[1] is not None}
    finally:
        conn.close()


def _load_pipeline_fuzzy_accuracies(db_path: Path) -> dict[str, float]:
    """Load pipeline fuzzy accuracy from method_results or ground_truth_diffs.

    Falls back to cell_accuracy_pct if fuzzy not available.
    """
    if not db_path.exists():
        return {}

    conn = sqlite3.connect(str(db_path))
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }

        # Try ground_truth_diffs first (has cell_accuracy_pct)
        if "ground_truth_diffs" in tables:
            rows = conn.execute(
                "SELECT table_id, cell_accuracy_pct FROM ground_truth_diffs"
            ).fetchall()
            return {row[0]: row[1] for row in rows if row[1] is not None}

        return {}
    finally:
        conn.close()


def generate_report(
    llm_results: list[EvaluationResult],
    pipeline_accs: dict[str, float],
    output_path: Path = DEFAULT_OUTPUT,
) -> str:
    """Generate a comparison report and write it to output_path.

    Returns the report text.
    """
    lines: list[str] = []
    lines.append("# LLM vs Pipeline Table Extraction Comparison\n")

    # --- Per-table accuracy ---
    lines.append("## Per-Table Accuracy\n")
    lines.append(
        "| Table ID | LLM Model | LLM Fuzzy% | LLM Cell% | Pipeline Cell% | Winner |"
    )
    lines.append("| --- | --- | --- | --- | --- | --- |")

    # Group LLM results by table, pick best model per table
    best_llm_by_table: dict[str, EvaluationResult] = {}
    for r in llm_results:
        existing = best_llm_by_table.get(r.table_id)
        if existing is None or r.fuzzy_accuracy_pct > existing.fuzzy_accuracy_pct:
            best_llm_by_table[r.table_id] = r

    all_table_ids = sorted(
        set(best_llm_by_table.keys()) | set(pipeline_accs.keys())
    )

    llm_wins = 0
    pipeline_wins = 0
    ties = 0
    llm_scores: list[float] = []
    pipeline_scores: list[float] = []

    for tid in all_table_ids:
        llm_r = best_llm_by_table.get(tid)
        pipe_acc = pipeline_accs.get(tid)

        llm_model = llm_r.model if llm_r else "-"
        llm_fuzzy = f"{llm_r.fuzzy_accuracy_pct:.1f}" if llm_r else "-"
        llm_cell = f"{llm_r.cell_accuracy_pct:.1f}" if llm_r else "-"
        pipe_str = f"{pipe_acc:.1f}" if pipe_acc is not None else "-"

        # Determine winner
        if llm_r and pipe_acc is not None:
            llm_val = llm_r.fuzzy_accuracy_pct
            pipe_val = pipe_acc
            llm_scores.append(llm_val)
            pipeline_scores.append(pipe_val)
            if abs(llm_val - pipe_val) < 1.0:
                winner = "Tie"
                ties += 1
            elif llm_val > pipe_val:
                winner = "LLM"
                llm_wins += 1
            else:
                winner = "Pipeline"
                pipeline_wins += 1
        elif llm_r:
            winner = "LLM only"
            llm_scores.append(llm_r.fuzzy_accuracy_pct)
        elif pipe_acc is not None:
            winner = "Pipeline only"
            pipeline_scores.append(pipe_acc)
        else:
            winner = "-"

        lines.append(
            f"| {tid} | {llm_model} | {llm_fuzzy} | {llm_cell} | {pipe_str} | {winner} |"
        )

    # --- Win/Loss Summary ---
    lines.append("\n## Win/Loss Summary\n")
    total = llm_wins + pipeline_wins + ties
    lines.append(f"- LLM wins: {llm_wins}" + (f" ({llm_wins/total*100:.0f}%)" if total else ""))
    lines.append(f"- Pipeline wins: {pipeline_wins}" + (f" ({pipeline_wins/total*100:.0f}%)" if total else ""))
    lines.append(f"- Ties (<1% difference): {ties}" + (f" ({ties/total*100:.0f}%)" if total else ""))
    lines.append(f"- Total compared: {total}")

    # --- Aggregate Statistics ---
    lines.append("\n## Aggregate Statistics\n")
    if llm_scores:
        mean_llm = sum(llm_scores) / len(llm_scores)
        median_llm = sorted(llm_scores)[len(llm_scores) // 2]
        lines.append(f"- LLM mean fuzzy accuracy: {mean_llm:.1f}% (n={len(llm_scores)})")
        lines.append(f"- LLM median fuzzy accuracy: {median_llm:.1f}%")
    if pipeline_scores:
        mean_pipe = sum(pipeline_scores) / len(pipeline_scores)
        median_pipe = sorted(pipeline_scores)[len(pipeline_scores) // 2]
        lines.append(f"- Pipeline mean cell accuracy: {mean_pipe:.1f}% (n={len(pipeline_scores)})")
        lines.append(f"- Pipeline median cell accuracy: {median_pipe:.1f}%")

    # --- Per-model breakdown ---
    models = sorted(set(r.model for r in llm_results))
    if len(models) > 1:
        lines.append("\n## Per-Model Breakdown\n")
        for model in models:
            model_results = [r for r in llm_results if r.model == model]
            n = len(model_results)
            avg_fuzzy = sum(r.fuzzy_accuracy_pct for r in model_results) / n
            avg_cell = sum(r.cell_accuracy_pct for r in model_results) / n
            lines.append(f"### {model} (n={n})")
            lines.append(f"- Mean fuzzy accuracy: {avg_fuzzy:.1f}%")
            lines.append(f"- Mean cell accuracy: {avg_cell:.1f}%")
            lines.append("")

    report = "\n".join(lines)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    print(f"Report written: {output_path}")
    return report


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Compare LLM table transcription vs pipeline extraction."
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DEBUG_DB,
        help="Path to _stress_test_debug.db.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output report path.",
    )
    args = parser.parse_args()

    llm_results = evaluate_all()
    pipeline_accs = _load_pipeline_accuracies(args.db)
    generate_report(llm_results, pipeline_accs, output_path=args.output)

    # Write LLM results into the debug DB so the viewer can display them
    if args.db.exists():
        write_to_debug_db(args.db)


if __name__ == "__main__":
    main()
