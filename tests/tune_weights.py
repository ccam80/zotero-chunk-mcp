"""Data-driven weight tuning for pipeline confidence multipliers.

Reads per-method results from the debug DB, computes per-method win rates
(how often each structure method's boundaries produce the best cell accuracy),
and outputs a JSON config file with confidence multipliers proportional to
win rates. The pipeline reads this config at startup to weight boundary
combination.

Usage:
    "./.venv/Scripts/python.exe" tests/tune_weights.py [debug_db_path] [output_path]

Defaults:
    debug_db_path: _stress_test_debug.db (project root)
    output_path:   tests/pipeline_weights.json
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path


def compute_win_rates(debug_db_path: Path) -> dict[str, float]:
    """Compute per-structure-method win rates from the debug DB.

    For each table_id in the method_results table, finds the method
    combination (structure+cell) with the highest quality_score.
    The structure method part of that winning combination gets a win.

    Win rate = wins / total tables where the method participated.

    Parameters
    ----------
    debug_db_path:
        Path to the stress test debug SQLite database.

    Returns
    -------
    dict[str, float]
        Maps structure method name to its win rate (0.0--1.0).
    """
    con = sqlite3.connect(str(debug_db_path))
    try:
        # Get all distinct table IDs
        table_ids = [
            r[0] for r in con.execute(
                "SELECT DISTINCT table_id FROM method_results"
            ).fetchall()
        ]

        structure_wins: dict[str, int] = {}
        structure_participation: dict[str, int] = {}

        for tid in table_ids:
            # Find the best method (highest quality_score) for this table
            best_row = con.execute(
                "SELECT method_name, quality_score FROM method_results "
                "WHERE table_id = ? AND quality_score IS NOT NULL "
                "ORDER BY quality_score DESC LIMIT 1",
                (tid,),
            ).fetchone()

            # Count participation for all methods on this table
            all_methods = con.execute(
                "SELECT DISTINCT method_name FROM method_results WHERE table_id = ?",
                (tid,),
            ).fetchall()

            for (method_name,) in all_methods:
                parts = method_name.split("+", 1)
                if len(parts) == 2:
                    struct_name = parts[0]
                    structure_participation[struct_name] = (
                        structure_participation.get(struct_name, 0) + 1
                    )

            if best_row:
                parts = best_row[0].split("+", 1)
                if len(parts) == 2:
                    struct_name = parts[0]
                    structure_wins[struct_name] = (
                        structure_wins.get(struct_name, 0) + 1
                    )

        # Compute win rates
        win_rates: dict[str, float] = {}
        all_methods = set(structure_wins.keys()) | set(structure_participation.keys())
        for method in all_methods:
            wins = structure_wins.get(method, 0)
            participated = structure_participation.get(method, 0)
            if participated > 0:
                win_rates[method] = wins / participated
            else:
                win_rates[method] = 0.0

        return win_rates
    finally:
        con.close()


def compute_multipliers(win_rates: dict[str, float]) -> dict[str, float]:
    """Convert win rates to confidence multipliers.

    Normalizes so the best method gets multiplier 1.0, others are
    proportional to their win rate relative to the best. Methods
    with zero wins get a floor of 0.1 (so they still contribute
    to boundary combination, just weakly).

    Parameters
    ----------
    win_rates:
        Maps method name to win rate (0.0--1.0).

    Returns
    -------
    dict[str, float]
        Maps method name to confidence multiplier.
    """
    if not win_rates:
        return {}

    max_rate = max(win_rates.values())
    if max_rate <= 0:
        # All methods have zero wins; give everyone the floor
        return {name: 0.1 for name in win_rates}

    multipliers: dict[str, float] = {}
    for name, rate in win_rates.items():
        if rate <= 0:
            multipliers[name] = 0.1
        else:
            multipliers[name] = rate / max_rate

    return multipliers


def write_config(multipliers: dict[str, float], output_path: Path) -> None:
    """Write confidence multipliers as a JSON config file.

    The JSON structure is:
    {
        "confidence_multipliers": { "method_name": float, ... }
    }

    Parameters
    ----------
    multipliers:
        Maps method name to confidence multiplier.
    output_path:
        Where to write the JSON file.
    """
    config = {"confidence_multipliers": multipliers}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    # Default paths
    project_root = Path(__file__).parent.parent
    debug_db_path = project_root / "_stress_test_debug.db"
    output_path = project_root / "tests" / "pipeline_weights.json"

    # Override from command-line args
    if len(sys.argv) >= 2:
        debug_db_path = Path(sys.argv[1])
    if len(sys.argv) >= 3:
        output_path = Path(sys.argv[2])

    if not debug_db_path.exists():
        print(f"Debug DB not found: {debug_db_path}")
        print("Run the stress test first to generate the debug database.")
        sys.exit(1)

    print(f"Reading method results from: {debug_db_path}")
    win_rates = compute_win_rates(debug_db_path)

    if not win_rates:
        print("No method results found in the database.")
        print("Run the stress test first to populate method_results.")
        sys.exit(1)

    print("\nWin rates:")
    for name, rate in sorted(win_rates.items(), key=lambda x: x[1], reverse=True):
        print(f"  {name}: {rate:.3f}")

    multipliers = compute_multipliers(win_rates)

    print("\nConfidence multipliers:")
    for name, mult in sorted(multipliers.items(), key=lambda x: x[1], reverse=True):
        print(f"  {name}: {mult:.3f}")

    write_config(multipliers, output_path)
    print(f"\nConfig written to: {output_path}")
