"""Tests for ground truth database schema, ID generation, insert/query, and comparison API."""
from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from zotero_chunk_rag.table_extraction.ground_truth import (
    ComparisonResult,
    _normalize_cell,
    compare_extraction,
    create_ground_truth_db,
    get_table_ids,
    insert_ground_truth,
    make_table_id,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_db(tmp_path: Path) -> Path:
    """Return a temporary database path (file does not yet exist)."""
    return tmp_path / "test_gt.db"


# ---------------------------------------------------------------------------
# TestSchema
# ---------------------------------------------------------------------------


class TestSchema:
    def test_create_db(self, tmp_db: Path) -> None:
        create_ground_truth_db(tmp_db)
        assert tmp_db.exists()
        conn = sqlite3.connect(str(tmp_db))
        try:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            assert "ground_truth_tables" in tables
            assert "ground_truth_meta" in tables
        finally:
            conn.close()

    def test_create_idempotent(self, tmp_db: Path) -> None:
        create_ground_truth_db(tmp_db)
        insert_ground_truth(
            tmp_db, "X_table_1", "X", 1, "Table 1", ["A"], [["1"]]
        )
        create_ground_truth_db(tmp_db)
        ids = get_table_ids(tmp_db)
        assert "X_table_1" in ids


# ---------------------------------------------------------------------------
# TestTableId
# ---------------------------------------------------------------------------


class TestTableId:
    def test_captioned_table(self) -> None:
        assert make_table_id("ABC", "Table 1: Results", 5, 0) == "ABC_table_1"

    def test_appendix_table(self) -> None:
        assert make_table_id("ABC", "Table A.1: Appendix data", 12, 0) == "ABC_table_A.1"

    def test_supplementary_table(self) -> None:
        assert make_table_id("ABC", "Table S2. Extra", 3, 0) == "ABC_table_S2"

    def test_orphan_table(self) -> None:
        assert make_table_id("ABC", None, 5, 0) == "ABC_orphan_p5_t0"

    def test_synthetic_caption(self) -> None:
        assert (
            make_table_id("ABC", "Uncaptioned table on page 5", 5, 0)
            == "ABC_orphan_p5_t0"
        )


# ---------------------------------------------------------------------------
# TestInsert
# ---------------------------------------------------------------------------


class TestInsert:
    def test_insert_and_retrieve(self, tmp_db: Path) -> None:
        create_ground_truth_db(tmp_db)
        headers = ["Name", "Value"]
        rows = [["alpha", "1"], ["beta", "2"]]
        insert_ground_truth(
            tmp_db, "P_table_1", "P", 3, "Table 1: Demo", headers, rows
        )
        conn = sqlite3.connect(str(tmp_db))
        try:
            row = conn.execute(
                "SELECT headers_json, rows_json FROM ground_truth_tables WHERE table_id = ?",
                ("P_table_1",),
            ).fetchone()
            assert row is not None
            assert json.loads(row[0]) == headers
            assert json.loads(row[1]) == rows
        finally:
            conn.close()

    def test_insert_replaces(self, tmp_db: Path) -> None:
        create_ground_truth_db(tmp_db)
        insert_ground_truth(
            tmp_db, "P_table_1", "P", 3, "Table 1", ["A"], [["old"]]
        )
        insert_ground_truth(
            tmp_db, "P_table_1", "P", 3, "Table 1", ["B"], [["new"]]
        )
        conn = sqlite3.connect(str(tmp_db))
        try:
            row = conn.execute(
                "SELECT headers_json, rows_json FROM ground_truth_tables WHERE table_id = ?",
                ("P_table_1",),
            ).fetchone()
            assert json.loads(row[0]) == ["B"]
            assert json.loads(row[1]) == [["new"]]
        finally:
            conn.close()

    def test_get_table_ids_filtered(self, tmp_db: Path) -> None:
        create_ground_truth_db(tmp_db)
        insert_ground_truth(
            tmp_db, "ABC_table_1", "ABC", 1, "Table 1", ["X"], [["1"]]
        )
        insert_ground_truth(
            tmp_db, "ABC_table_2", "ABC", 2, "Table 2", ["X"], [["2"]]
        )
        insert_ground_truth(
            tmp_db, "DEF_table_1", "DEF", 1, "Table 1", ["Y"], [["3"]]
        )
        abc_ids = get_table_ids(tmp_db, paper_key="ABC")
        assert abc_ids == ["ABC_table_1", "ABC_table_2"]
        all_ids = get_table_ids(tmp_db)
        assert len(all_ids) == 3


# ---------------------------------------------------------------------------
# TestNormalize
# ---------------------------------------------------------------------------


class TestNormalize:
    def test_whitespace(self) -> None:
        assert _normalize_cell("  hello  world  ") == "hello world"

    def test_unicode_minus(self) -> None:
        assert _normalize_cell("\u22120.5") == "-0.5"

    def test_ligatures(self) -> None:
        assert _normalize_cell("e\ufb03cient") == "efficient"


# ---------------------------------------------------------------------------
# TestCompare
# ---------------------------------------------------------------------------


class TestCompare:
    def _seed(self, db: Path, headers: list[str], rows: list[list[str]], table_id: str = "T_table_1") -> None:
        create_ground_truth_db(db)
        insert_ground_truth(db, table_id, "T", 1, "Table 1", headers, rows)

    def test_perfect_match(self, tmp_db: Path) -> None:
        headers = ["A", "B", "C"]
        rows = [["1", "2", "3"], ["4", "5", "6"]]
        self._seed(tmp_db, headers, rows)
        result = compare_extraction(tmp_db, "T_table_1", headers, rows)
        assert result.cell_accuracy_pct == 100.0
        assert result.cell_diffs == []
        assert result.extra_columns == []
        assert result.missing_columns == []
        assert result.row_splits == []
        assert result.row_merges == []

    def test_cell_mismatch(self, tmp_db: Path) -> None:
        headers = ["A", "B"]
        gt_rows = [["1", "2"], ["3", "4"]]
        ext_rows = [["1", "WRONG"], ["3", "4"]]
        self._seed(tmp_db, headers, gt_rows)
        result = compare_extraction(tmp_db, "T_table_1", headers, ext_rows)
        assert result.cell_accuracy_pct < 100.0
        assert len(result.cell_diffs) == 1
        diff = result.cell_diffs[0]
        assert diff.row == 0
        assert diff.col == 1
        assert diff.expected == "2"
        assert diff.actual == "WRONG"

    def test_extra_column(self, tmp_db: Path) -> None:
        gt_headers = ["A", "B"]
        gt_rows = [["1", "2"]]
        self._seed(tmp_db, gt_headers, gt_rows)
        ext_headers = ["A", "B", "Extra"]
        ext_rows = [["1", "2", "x"]]
        result = compare_extraction(tmp_db, "T_table_1", ext_headers, ext_rows)
        assert len(result.extra_columns) == 1
        # Accuracy denominator = total GT cells = 1 row * 2 cols = 2
        # Both GT cells match, so accuracy = 100%
        assert result.cell_accuracy_pct == 100.0

    def test_missing_column(self, tmp_db: Path) -> None:
        gt_headers = ["A", "B", "C"]
        gt_rows = [["1", "2", "3"]]
        self._seed(tmp_db, gt_headers, gt_rows)
        ext_headers = ["A", "B"]
        ext_rows = [["1", "2"]]
        result = compare_extraction(tmp_db, "T_table_1", ext_headers, ext_rows)
        assert len(result.missing_columns) == 1
        # GT has 3 cells; col C is missing so its cell counts as wrong
        assert result.cell_accuracy_pct < 100.0

    def test_row_split_detection(self, tmp_db: Path) -> None:
        gt_headers = ["A", "B", "C"]
        gt_rows = [["A", "B", "C"]]
        self._seed(tmp_db, gt_headers, gt_rows)
        ext_headers = ["A", "B", "C"]
        ext_rows = [["A", "B", ""], ["", "", "C"]]
        result = compare_extraction(tmp_db, "T_table_1", ext_headers, ext_rows)
        assert len(result.row_splits) == 1
        assert result.row_splits[0].gt_index == 0
        assert result.row_splits[0].ext_indices == [0, 1]

    def test_column_split_detection(self, tmp_db: Path) -> None:
        gt_headers = ["BMI", "Score"]
        gt_rows = [["25", "A"]]
        self._seed(tmp_db, gt_headers, gt_rows)
        ext_headers = ["BM", "I", "Score"]
        ext_rows = [["25", "", "A"]]
        result = compare_extraction(tmp_db, "T_table_1", ext_headers, ext_rows)
        assert len(result.column_splits) == 1

    def test_split_cells_count_as_wrong(self, tmp_db: Path) -> None:
        gt_headers = ["A", "B", "C"]
        gt_rows = [["x", "y", "z"]]
        self._seed(tmp_db, gt_headers, gt_rows)
        # Split row: GT row 0 -> ext rows 0,1
        ext_headers = ["A", "B", "C"]
        ext_rows = [["x", "y", ""], ["", "", "z"]]
        result = compare_extraction(tmp_db, "T_table_1", ext_headers, ext_rows)
        # All cells in the split row count as wrong -> 0% accuracy
        assert result.cell_accuracy_pct == 0.0

    def test_table_not_found(self, tmp_db: Path) -> None:
        create_ground_truth_db(tmp_db)
        with pytest.raises(KeyError, match="NONEXIST"):
            compare_extraction(tmp_db, "NONEXIST", ["A"], [["1"]])

    def test_header_alignment(self, tmp_db: Path) -> None:
        gt_headers = ["Name", "Age", "Score"]
        gt_rows = [["Alice", "30", "95"]]
        self._seed(tmp_db, gt_headers, gt_rows)
        # Extraction has columns in different order
        ext_headers = ["Score", "Name", "Age"]
        ext_rows = [["95", "Alice", "30"]]
        result = compare_extraction(tmp_db, "T_table_1", ext_headers, ext_rows)
        assert result.cell_accuracy_pct == 100.0
        assert len(result.matched_columns) == 3
