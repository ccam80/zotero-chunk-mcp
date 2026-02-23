"""Tests for debug_db.py: extended schema creation and write helpers."""
from __future__ import annotations

import json
import sqlite3

import pytest

from zotero_chunk_rag.feature_extraction.debug_db import (
    create_extended_tables,
    write_ground_truth_diff,
    write_method_result,
    write_pipeline_run,
)
from zotero_chunk_rag.feature_extraction.ground_truth import ComparisonResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _in_memory_con() -> sqlite3.Connection:
    """Return a fresh in-memory SQLite connection."""
    return sqlite3.connect(":memory:")


# ---------------------------------------------------------------------------
# TestSchema
# ---------------------------------------------------------------------------


class TestSchema:
    def test_creates_tables(self) -> None:
        """create_extended_tables() adds all 3 new tables to an in-memory DB."""
        con = _in_memory_con()
        create_extended_tables(con)
        table_names = {
            row[0]
            for row in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "method_results" in table_names
        assert "pipeline_runs" in table_names
        assert "ground_truth_diffs" in table_names
        con.close()

    def test_idempotent(self) -> None:
        """Calling create_extended_tables() twice on the same connection raises no error."""
        con = _in_memory_con()
        create_extended_tables(con)
        create_extended_tables(con)
        table_names = {
            row[0]
            for row in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "method_results" in table_names
        assert "pipeline_runs" in table_names
        assert "ground_truth_diffs" in table_names
        con.close()


# ---------------------------------------------------------------------------
# TestWrite
# ---------------------------------------------------------------------------


class TestWrite:
    def test_write_method_result(self) -> None:
        """write_method_result() inserts a row with all fields queryable."""
        con = _in_memory_con()
        create_extended_tables(con)
        write_method_result(
            con,
            table_id="paper1_table_1",
            method_name="camelot_lattice",
            boundaries_json='{"rows": [10, 20], "cols": [5, 15]}',
            cell_grid_json='[["A", "B"], ["1", "2"]]',
            quality_score=0.92,
            execution_time_ms=135,
        )
        con.commit()

        row = con.execute(
            "SELECT table_id, method_name, boundary_hypotheses_json, cell_grid_json, "
            "quality_score, execution_time_ms FROM method_results WHERE table_id = ?",
            ("paper1_table_1",),
        ).fetchone()

        assert row is not None
        assert row[0] == "paper1_table_1"
        assert row[1] == "camelot_lattice"
        assert row[2] == '{"rows": [10, 20], "cols": [5, 15]}'
        assert row[3] == '[["A", "B"], ["1", "2"]]'
        assert row[4] == pytest.approx(0.92)
        assert row[5] == 135
        con.close()

    def test_write_ground_truth_diff(self) -> None:
        """write_ground_truth_diff() correctly serializes a ComparisonResult."""
        from zotero_chunk_rag.feature_extraction.ground_truth import (
            CellDiff,
            MergeInfo,
            SplitInfo,
        )

        result = ComparisonResult(
            table_id="paper2_table_3",
            gt_shape=(5, 3),
            ext_shape=(6, 3),
            matched_columns=[(0, 0), (1, 1), (2, 2)],
            extra_columns=[],
            missing_columns=[],
            column_splits=[],
            column_merges=[],
            matched_rows=[(0, 0), (1, 1), (2, 2), (3, 3), (4, 4)],
            extra_rows=[5],
            missing_rows=[],
            row_splits=[SplitInfo(gt_index=2, ext_indices=[2, 3])],
            row_merges=[],
            cell_diffs=[CellDiff(row=1, col=2, expected="0.47", actual="0.74")],
            cell_accuracy_pct=80.0,
            header_diffs=[],
        )

        con = _in_memory_con()
        create_extended_tables(con)
        write_ground_truth_diff(con, "paper2_table_3", "2026-01-01T00:00:00", result)
        con.commit()

        row = con.execute(
            "SELECT table_id, run_id, diff_json, cell_accuracy_pct, num_splits, "
            "num_merges, num_cell_diffs, gt_shape, ext_shape "
            "FROM ground_truth_diffs WHERE table_id = ?",
            ("paper2_table_3",),
        ).fetchone()

        assert row is not None
        assert row[0] == "paper2_table_3"
        assert row[1] == "2026-01-01T00:00:00"
        # diff_json must be valid JSON containing the table_id
        diff = json.loads(row[2])
        assert diff["table_id"] == "paper2_table_3"
        assert row[3] == pytest.approx(80.0)
        # num_splits = len(row_splits) + len(column_splits) = 1 + 0
        assert row[4] == 1
        # num_merges = len(row_merges) + len(column_merges) = 0 + 0
        assert row[5] == 0
        # num_cell_diffs = len(cell_diffs) = 1
        assert row[6] == 1
        assert json.loads(row[7]) == [5, 3]
        assert json.loads(row[8]) == [6, 3]
        con.close()

    def test_write_pipeline_run(self) -> None:
        """write_pipeline_run() inserts a row with all fields queryable."""
        con = _in_memory_con()
        create_extended_tables(con)
        config = json.dumps({"methods": ["camelot", "pdfplumber"], "strategy": "best"})
        write_pipeline_run(
            con,
            table_id="paper3_table_2",
            pipeline_config_json=config,
            winning_method="camelot_lattice",
            final_score=0.88,
        )
        con.commit()

        row = con.execute(
            "SELECT table_id, pipeline_config_json, winning_method, final_score "
            "FROM pipeline_runs WHERE table_id = ?",
            ("paper3_table_2",),
        ).fetchone()

        assert row is not None
        assert row[0] == "paper3_table_2"
        assert json.loads(row[1]) == {"methods": ["camelot", "pdfplumber"], "strategy": "best"}
        assert row[2] == "camelot_lattice"
        assert row[3] == pytest.approx(0.88)
        con.close()
