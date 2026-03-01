"""Tests for debug_db.py: extended schema creation and write helpers."""
from __future__ import annotations

import json
import sqlite3

import pytest

from zotero_chunk_rag.feature_extraction.debug_db import (
    create_extended_tables,
    write_ground_truth_diff,
    write_vision_agent_result,
    write_vision_run_detail,
)
from zotero_chunk_rag.feature_extraction.ground_truth import ComparisonResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _in_memory_con() -> sqlite3.Connection:
    """Return a fresh in-memory SQLite connection."""
    return sqlite3.connect(":memory:")


def _table_names(con: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }


# ---------------------------------------------------------------------------
# TestSchema — existing tables still work
# ---------------------------------------------------------------------------


class TestSchema:
    def test_creates_tables(self) -> None:
        """create_extended_tables() adds the kept tables to an in-memory DB."""
        con = _in_memory_con()
        create_extended_tables(con)
        names = _table_names(con)
        assert "ground_truth_diffs" in names
        assert "vision_agent_results" in names
        con.close()

    def test_idempotent(self) -> None:
        """Calling create_extended_tables() twice on the same connection raises no error."""
        con = _in_memory_con()
        create_extended_tables(con)
        create_extended_tables(con)
        names = _table_names(con)
        assert "ground_truth_diffs" in names
        assert "vision_agent_results" in names
        con.close()


# ---------------------------------------------------------------------------
# TestPrunedSchema — deleted tables must not exist
# ---------------------------------------------------------------------------


class TestPrunedSchema:
    def test_no_method_results_table(self) -> None:
        """method_results table must not be created by create_extended_tables()."""
        con = _in_memory_con()
        create_extended_tables(con)
        assert "method_results" not in _table_names(con)
        con.close()

    def test_no_pipeline_runs_table(self) -> None:
        """pipeline_runs table must not be created by create_extended_tables()."""
        con = _in_memory_con()
        create_extended_tables(con)
        assert "pipeline_runs" not in _table_names(con)
        con.close()

    def test_no_vision_consensus_table(self) -> None:
        """vision_consensus table must not be created by create_extended_tables()."""
        con = _in_memory_con()
        create_extended_tables(con)
        assert "vision_consensus" not in _table_names(con)
        con.close()

    def test_kept_tables_exist(self) -> None:
        """ground_truth_diffs and vision_agent_results must still be created."""
        con = _in_memory_con()
        create_extended_tables(con)
        names = _table_names(con)
        assert "ground_truth_diffs" in names
        assert "vision_agent_results" in names
        con.close()


# ---------------------------------------------------------------------------
# TestPrunedExports — deleted functions must not be importable
# ---------------------------------------------------------------------------


class TestPrunedExports:
    def test_deleted_functions_not_importable(self) -> None:
        """write_method_result, write_pipeline_run, write_vision_consensus must not exist."""
        import zotero_chunk_rag.feature_extraction.debug_db as debug_db

        assert not hasattr(debug_db, "write_method_result"), (
            "write_method_result should have been deleted"
        )
        assert not hasattr(debug_db, "write_pipeline_run"), (
            "write_pipeline_run should have been deleted"
        )
        assert not hasattr(debug_db, "write_vision_consensus"), (
            "write_vision_consensus should have been deleted"
        )


# ---------------------------------------------------------------------------
# TestWrite — retained write functions still work
# ---------------------------------------------------------------------------


class TestWrite:
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

        assert row[0] == "paper2_table_3"
        assert row[1] == "2026-01-01T00:00:00"
        diff = json.loads(row[2])
        assert diff["table_id"] == "paper2_table_3"
        assert row[3] == 80.0
        assert row[4] == 1
        assert row[5] == 0
        assert row[6] == 1
        assert json.loads(row[7]) == [5, 3]
        assert json.loads(row[8]) == [6, 3]
        con.close()


# ---------------------------------------------------------------------------
# TestExtendedSchema — column-level checks on kept tables
# ---------------------------------------------------------------------------


class TestExtendedSchema:
    def test_ground_truth_diffs_has_fuzzy_columns(self) -> None:
        """ground_truth_diffs table has fuzzy_accuracy_pct, fuzzy_precision_pct, fuzzy_recall_pct columns."""
        con = _in_memory_con()
        create_extended_tables(con)
        column_info = con.execute("PRAGMA table_info(ground_truth_diffs)").fetchall()
        column_names = {row[1] for row in column_info}
        assert "fuzzy_accuracy_pct" in column_names
        assert "fuzzy_precision_pct" in column_names
        assert "fuzzy_recall_pct" in column_names
        con.close()


# ---------------------------------------------------------------------------
# TestVisionRunDetails — new table from Task 4.2.2
# ---------------------------------------------------------------------------


class TestVisionRunDetails:
    def test_table_created(self) -> None:
        """vision_run_details table must be created by create_extended_tables()."""
        con = _in_memory_con()
        create_extended_tables(con)
        assert "vision_run_details" in _table_names(con)
        con.close()

    def test_write_and_read(self) -> None:
        """write_vision_run_detail() inserts a row that can be read back correctly."""
        con = _in_memory_con()
        create_extended_tables(con)

        details = {
            "text_layer_caption": "Table 1",
            "vision_caption": "Table 1. Demographics by group",
            "page_num": 3,
            "crop_bbox": [50.0, 100.0, 400.0, 300.0],
            "recropped": True,
            "recrop_bbox_pct": [10.0, 5.0, 90.0, 95.0],
            "parse_success": True,
            "is_incomplete": False,
            "incomplete_reason": "",
            "recrop_needed": False,
            "raw_response": "raw text here",
            "headers": ["A", "B", "C"],
            "rows": [["1", "2", "3"]],
            "footnotes": "Note: p < 0.05",
            "table_label": "Table 1",
        }

        write_vision_run_detail(con, table_id="paper1_table_1", details_dict=details)
        con.commit()

        row = con.execute(
            "SELECT table_id, text_layer_caption, vision_caption, recropped "
            "FROM vision_run_details WHERE table_id = ?",
            ("paper1_table_1",),
        ).fetchone()

        assert row[0] == "paper1_table_1"
        assert row[1] == "Table 1"
        assert row[2] == "Table 1. Demographics by group"
        assert bool(row[3]) is True
        con.close()

    def test_upsert(self) -> None:
        """Writing the same table_id twice overwrites the first entry (INSERT OR REPLACE)."""
        con = _in_memory_con()
        create_extended_tables(con)

        base = {
            "text_layer_caption": "Table 2",
            "vision_caption": "Table 2. Outcomes",
            "page_num": 5,
            "crop_bbox": [0.0, 0.0, 200.0, 150.0],
            "recropped": False,
            "recrop_bbox_pct": None,
            "parse_success": True,
            "is_incomplete": False,
            "incomplete_reason": "",
            "recrop_needed": False,
            "raw_response": "first",
            "headers": ["X"],
            "rows": [["1"]],
            "footnotes": "",
            "table_label": None,
        }

        write_vision_run_detail(con, table_id="paper1_table_2", details_dict=base)
        con.commit()

        updated = dict(base)
        updated["recropped"] = True
        updated["raw_response"] = "second"

        write_vision_run_detail(con, table_id="paper1_table_2", details_dict=updated)
        con.commit()

        rows = con.execute(
            "SELECT recropped, raw_response FROM vision_run_details WHERE table_id = ?",
            ("paper1_table_2",),
        ).fetchall()

        assert len(rows) == 1, "INSERT OR REPLACE must leave exactly one row"
        assert bool(rows[0][0]) is True
        assert rows[0][1] == "second"
        con.close()
