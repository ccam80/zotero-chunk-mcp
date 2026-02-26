"""Debug database interface for recording and inspecting table extraction results."""
from __future__ import annotations

import dataclasses
import json
import sqlite3

from zotero_chunk_rag.feature_extraction.ground_truth import ComparisonResult


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
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    table_id            TEXT NOT NULL,
    run_id              TEXT NOT NULL,
    diff_json           TEXT NOT NULL,
    cell_accuracy_pct   REAL,
    num_splits          INTEGER,
    num_merges          INTEGER,
    num_cell_diffs      INTEGER,
    gt_shape            TEXT,
    ext_shape           TEXT,
    fuzzy_accuracy_pct  REAL,
    fuzzy_precision_pct REAL,
    fuzzy_recall_pct    REAL
);

CREATE TABLE IF NOT EXISTS vision_agent_results (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    table_id          TEXT NOT NULL,
    agent_idx         INTEGER NOT NULL,
    model             TEXT NOT NULL,
    raw_response      TEXT,
    headers_json      TEXT,
    rows_json         TEXT,
    table_label       TEXT,
    is_incomplete     INTEGER,
    incomplete_reason TEXT,
    parse_success     INTEGER,
    execution_time_ms INTEGER
);

CREATE TABLE IF NOT EXISTS vision_consensus (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    table_id                TEXT NOT NULL,
    shape_agreement         INTEGER,
    winning_shape           TEXT,
    agent_agreement_rate    REAL,
    num_disputed_cells      INTEGER,
    disputed_cells_json     TEXT,
    consensus_label         TEXT,
    consensus_footnotes     TEXT,
    render_attempts         INTEGER,
    fallback_to_traditional INTEGER,
    caption_swap            TEXT
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
        "num_merges, num_cell_diffs, gt_shape, ext_shape, "
        "fuzzy_accuracy_pct, fuzzy_precision_pct, fuzzy_recall_pct) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
            comparison_result.fuzzy_accuracy_pct,
            comparison_result.fuzzy_precision_pct,
            comparison_result.fuzzy_recall_pct,
        ),
    )


def write_vision_agent_result(
    con: sqlite3.Connection,
    table_id: str,
    agent_idx: int,
    model: str,
    raw_response: str | None,
    headers_json: str | None,
    rows_json: str | None,
    table_label: str | None,
    is_incomplete: bool,
    incomplete_reason: str,
    parse_success: bool,
    execution_time_ms: int | None,
) -> None:
    """Insert a single vision agent result row."""
    con.execute(
        "INSERT INTO vision_agent_results "
        "(table_id, agent_idx, model, raw_response, headers_json, rows_json, "
        "table_label, is_incomplete, incomplete_reason, parse_success, execution_time_ms) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (table_id, agent_idx, model, raw_response, headers_json, rows_json,
         table_label, int(is_incomplete), incomplete_reason, int(parse_success),
         execution_time_ms),
    )


def write_vision_consensus(
    con: sqlite3.Connection,
    table_id: str,
    shape_agreement: bool,
    winning_shape: str,
    agent_agreement_rate: float,
    num_disputed_cells: int,
    disputed_cells_json: str | None,
    consensus_label: str | None,
    consensus_footnotes: str | None,
    render_attempts: int,
    fallback_to_traditional: bool,
    caption_swap: str | None = None,
) -> None:
    """Insert a single vision consensus result row."""
    con.execute(
        "INSERT INTO vision_consensus "
        "(table_id, shape_agreement, winning_shape, agent_agreement_rate, "
        "num_disputed_cells, disputed_cells_json, consensus_label, "
        "consensus_footnotes, render_attempts, fallback_to_traditional, caption_swap) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (table_id, int(shape_agreement), winning_shape, agent_agreement_rate,
         num_disputed_cells, disputed_cells_json, consensus_label,
         consensus_footnotes, render_attempts, int(fallback_to_traditional),
         caption_swap),
    )
