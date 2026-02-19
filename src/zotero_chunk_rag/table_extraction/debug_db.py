"""Debug database interface for recording and inspecting table extraction results."""
from __future__ import annotations

import dataclasses
import json
import sqlite3

from zotero_chunk_rag.table_extraction.ground_truth import ComparisonResult


EXTENDED_SCHEMA = """\
CREATE TABLE IF NOT EXISTS method_results (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    table_id                TEXT NOT NULL,
    method_name             TEXT NOT NULL,
    boundary_hypotheses_json TEXT,
    cell_grid_json          TEXT,
    quality_score           REAL,
    execution_time_ms       INTEGER
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    table_id            TEXT NOT NULL,
    pipeline_config_json TEXT,
    winning_method      TEXT,
    final_score         REAL
);

CREATE TABLE IF NOT EXISTS ground_truth_diffs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    table_id          TEXT NOT NULL,
    run_id            TEXT NOT NULL,
    diff_json         TEXT NOT NULL,
    cell_accuracy_pct REAL,
    num_splits        INTEGER,
    num_merges        INTEGER,
    num_cell_diffs    INTEGER,
    gt_shape          TEXT,
    ext_shape         TEXT
);
"""


def create_extended_tables(con: sqlite3.Connection) -> None:
    """Execute the extended schema on an existing connection.

    Safe to call multiple times — all statements use CREATE TABLE IF NOT EXISTS.
    """
    con.executescript(EXTENDED_SCHEMA)


def write_method_result(
    con: sqlite3.Connection,
    table_id: str,
    method_name: str,
    boundaries_json: str | None,
    cell_grid_json: str | None,
    quality_score: float | None,
    execution_time_ms: int | None,
) -> None:
    """Insert a single method extraction result row."""
    con.execute(
        "INSERT INTO method_results "
        "(table_id, method_name, boundary_hypotheses_json, cell_grid_json, "
        "quality_score, execution_time_ms) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (table_id, method_name, boundaries_json, cell_grid_json,
         quality_score, execution_time_ms),
    )


def write_pipeline_run(
    con: sqlite3.Connection,
    table_id: str,
    pipeline_config_json: str | None,
    winning_method: str | None,
    final_score: float | None,
) -> None:
    """Insert a single pipeline run row."""
    con.execute(
        "INSERT INTO pipeline_runs "
        "(table_id, pipeline_config_json, winning_method, final_score) "
        "VALUES (?, ?, ?, ?)",
        (table_id, pipeline_config_json, winning_method, final_score),
    )


def write_ground_truth_diff(
    con: sqlite3.Connection,
    table_id: str,
    run_id: str,
    comparison_result: ComparisonResult,
) -> None:
    """Serialize a ComparisonResult and insert a ground truth diff row.

    ``diff_json`` contains the full ComparisonResult serialized via
    ``dataclasses.asdict()`` + ``json.dumps()``.  Summary fields are extracted
    directly from the ComparisonResult for easy querying without JSON parsing.
    """
    diff_dict = dataclasses.asdict(comparison_result)
    diff_json = json.dumps(diff_dict, ensure_ascii=False)

    num_splits = (
        len(comparison_result.row_splits) + len(comparison_result.column_splits)
    )
    num_merges = (
        len(comparison_result.row_merges) + len(comparison_result.column_merges)
    )
    num_cell_diffs = len(comparison_result.cell_diffs)
    gt_shape = json.dumps(list(comparison_result.gt_shape))
    ext_shape = json.dumps(list(comparison_result.ext_shape))

    con.execute(
        "INSERT INTO ground_truth_diffs "
        "(table_id, run_id, diff_json, cell_accuracy_pct, num_splits, "
        "num_merges, num_cell_diffs, gt_shape, ext_shape) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            table_id,
            run_id,
            diff_json,
            comparison_result.cell_accuracy_pct,
            num_splits,
            num_merges,
            num_cell_diffs,
            gt_shape,
            ext_shape,
        ),
    )
