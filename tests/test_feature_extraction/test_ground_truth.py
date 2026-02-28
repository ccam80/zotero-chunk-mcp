"""Tests for ground truth database schema, ID generation, insert/query, and comparison API."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from zotero_chunk_rag.feature_extraction.ground_truth import (
    ComparisonResult,
    _compute_fuzzy_accuracy,
    _fuzzy_cell_score,
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

    def test_footnotes_column_exists(self, tmp_db: Path) -> None:
        create_ground_truth_db(tmp_db)
        conn = sqlite3.connect(str(tmp_db))
        try:
            cols = {
                row[1]
                for row in conn.execute("PRAGMA table_info(ground_truth_tables)").fetchall()
            }
            assert "footnotes" in cols
        finally:
            conn.close()

    def test_migrate_adds_footnotes_column(self, tmp_db: Path) -> None:
        """Databases without a footnotes column get it added by create_ground_truth_db."""
        conn = sqlite3.connect(str(tmp_db))
        try:
            conn.executescript("""\
CREATE TABLE IF NOT EXISTS ground_truth_tables (
    table_id    TEXT PRIMARY KEY,
    paper_key   TEXT NOT NULL,
    page_num    INTEGER NOT NULL,
    caption     TEXT,
    headers_json TEXT NOT NULL,
    rows_json   TEXT NOT NULL,
    num_rows    INTEGER NOT NULL,
    num_cols    INTEGER NOT NULL,
    notes       TEXT DEFAULT '',
    created_at  TEXT NOT NULL,
    verified_by TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS ground_truth_meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
""")
            conn.commit()
        finally:
            conn.close()

        create_ground_truth_db(tmp_db)
        conn = sqlite3.connect(str(tmp_db))
        try:
            cols = {
                row[1]
                for row in conn.execute("PRAGMA table_info(ground_truth_tables)").fetchall()
            }
            assert "footnotes" in cols
        finally:
            conn.close()


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

    def test_roman_numeral(self) -> None:
        assert make_table_id("X", "Table IV: Results", 1, 0) == "X_table_IV"

    def test_bold_prefix(self) -> None:
        assert make_table_id("X", "**Table 1**: Foo", 1, 0) == "X_table_1"

    def test_continuation_appends_page(self) -> None:
        assert make_table_id("X", "Table 1 (continued).", 16, 0) == "X_table_1_p16"

    def test_continuation_cont_dot(self) -> None:
        assert make_table_id("X", "Table 2 (cont.)", 5, 0) == "X_table_2_p5"

    def test_non_continuation_no_page(self) -> None:
        assert make_table_id("X", "Table 1 Model variables.", 15, 0) == "X_table_1"


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

    def test_insert_with_footnotes(self, tmp_db: Path) -> None:
        create_ground_truth_db(tmp_db)
        insert_ground_truth(
            tmp_db, "P_table_2", "P", 4, "Table 2: Notes",
            ["X"], [["1"]],
            notes="Reviewer: two-level header",
            footnotes="Note. X = cross-reference.",
        )
        conn = sqlite3.connect(str(tmp_db))
        try:
            row = conn.execute(
                "SELECT notes, footnotes FROM ground_truth_tables WHERE table_id = ?",
                ("P_table_2",),
            ).fetchone()
            assert row is not None
            assert row[0] == "Reviewer: two-level header"
            assert row[1] == "Note. X = cross-reference."
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

    def test_get_table_ids_empty(self, tmp_db: Path) -> None:
        create_ground_truth_db(tmp_db)
        assert get_table_ids(tmp_db) == []


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

    def test_empty_string(self) -> None:
        assert _normalize_cell("") == ""

    def test_en_dash(self) -> None:
        assert _normalize_cell("50\u201360") == "50-60"

    def test_em_dash(self) -> None:
        assert _normalize_cell("a\u2014b") == "a-b"


# ---------------------------------------------------------------------------
# TestCompare
# ---------------------------------------------------------------------------


class TestCompare:
    def _seed(
        self, db: Path, headers: list[str], rows: list[list[str]],
        table_id: str = "T_table_1", footnotes: str = "",
    ) -> None:
        create_ground_truth_db(db)
        insert_ground_truth(
            db, table_id, "T", 1, "Table 1", headers, rows,
            footnotes=footnotes,
        )

    def test_perfect_match(self, tmp_db: Path) -> None:
        headers = ["A", "B", "C"]
        rows = [["1", "2", "3"], ["4", "5", "6"]]
        self._seed(tmp_db, headers, rows)
        result = compare_extraction(tmp_db, "T_table_1", headers, rows)
        assert result.cell_accuracy_pct == 100.0
        assert result.structural_coverage_pct == 100.0
        assert result.cell_diffs == []
        assert result.extra_columns == []
        assert result.missing_columns == []
        assert result.row_splits == []
        assert result.row_merges == []
        assert result.gt_is_artifact is False

    def test_cell_mismatch(self, tmp_db: Path) -> None:
        headers = ["A", "B"]
        gt_rows = [["1", "2"], ["3", "4"]]
        ext_rows = [["1", "WRONG"], ["3", "4"]]
        self._seed(tmp_db, headers, gt_rows)
        result = compare_extraction(tmp_db, "T_table_1", headers, ext_rows)
        # 2 headers correct + 3 of 4 data cells correct = 5/6
        assert result.cell_accuracy_pct == pytest.approx(83.3, abs=0.1)
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
        assert result.cell_accuracy_pct == 100.0

    def test_missing_column(self, tmp_db: Path) -> None:
        gt_headers = ["A", "B", "C"]
        gt_rows = [["1", "2", "3"]]
        self._seed(tmp_db, gt_headers, gt_rows)
        ext_headers = ["A", "B"]
        ext_rows = [["1", "2"]]
        result = compare_extraction(tmp_db, "T_table_1", ext_headers, ext_rows)
        assert result.missing_columns == [2]
        # 2 of 2 comparable cells correct, but coverage < 100%
        assert result.cell_accuracy_pct == 100.0
        assert result.structural_coverage_pct < 100.0

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

    def test_split_row_coverage_penalty(self, tmp_db: Path) -> None:
        """A split row reduces coverage, not accuracy of comparable cells."""
        gt_headers = ["A", "B", "C"]
        gt_rows = [["x", "y", "z"]]
        self._seed(tmp_db, gt_headers, gt_rows)
        ext_headers = ["A", "B", "C"]
        ext_rows = [["x", "y", ""], ["", "", "z"]]
        result = compare_extraction(tmp_db, "T_table_1", ext_headers, ext_rows)
        # 3 header cells comparable (all match), 0 data rows comparable
        assert result.comparable_cells == 3
        assert result.structural_coverage_pct == 50.0  # 3 of 6 total GT cells
        assert result.cell_accuracy_pct == 100.0  # all 3 comparable (header) cells match

    def test_table_not_found(self, tmp_db: Path) -> None:
        create_ground_truth_db(tmp_db)
        with pytest.raises(KeyError, match="NONEXIST"):
            compare_extraction(tmp_db, "NONEXIST", ["A"], [["1"]])

    def test_header_alignment(self, tmp_db: Path) -> None:
        gt_headers = ["Name", "Age", "Score"]
        gt_rows = [["Alice", "30", "95"]]
        self._seed(tmp_db, gt_headers, gt_rows)
        ext_headers = ["Score", "Name", "Age"]
        ext_rows = [["95", "Alice", "30"]]
        result = compare_extraction(tmp_db, "T_table_1", ext_headers, ext_rows)
        assert result.cell_accuracy_pct == 100.0
        assert len(result.matched_columns) == 3

    # --- New: Row merge ---
    def test_row_merge_detection(self, tmp_db: Path) -> None:
        """Two GT rows merged into one extraction row."""
        gt_headers = ["A", "B"]
        gt_rows = [["x", "1"], ["y", "2"]]
        self._seed(tmp_db, gt_headers, gt_rows)
        ext_headers = ["A", "B"]
        ext_rows = [["x y", "1 2"]]
        result = compare_extraction(tmp_db, "T_table_1", ext_headers, ext_rows)
        assert len(result.row_merges) == 1
        assert result.row_merges[0].gt_indices == [0, 1]
        assert result.row_merges[0].ext_index == 0

    # --- New: Column merge ---
    def test_column_merge_detection(self, tmp_db: Path) -> None:
        """Two adjacent GT columns merged into one extraction column."""
        gt_headers = ["First", "Name"]
        gt_rows = [["A", "B"]]
        self._seed(tmp_db, gt_headers, gt_rows)
        ext_headers = ["FirstName"]
        ext_rows = [["AB"]]
        result = compare_extraction(tmp_db, "T_table_1", ext_headers, ext_rows)
        assert len(result.column_merges) == 1
        assert result.column_merges[0].gt_indices == [0, 1]
        assert result.column_merges[0].ext_index == 0

    def test_column_merge_requires_adjacency(self, tmp_db: Path) -> None:
        """Non-adjacent GT columns must NOT be detected as merged."""
        gt_headers = ["A", "X", "B"]
        gt_rows = [["1", "2", "3"]]
        self._seed(tmp_db, gt_headers, gt_rows)
        # "AB" concatenation of non-adjacent cols 0+2 should NOT match
        ext_headers = ["AB", "X"]
        ext_rows = [["13", "2"]]
        result = compare_extraction(tmp_db, "T_table_1", ext_headers, ext_rows)
        assert len(result.column_merges) == 0

    # --- New: Extra rows ---
    def test_extra_rows(self, tmp_db: Path) -> None:
        gt_headers = ["A", "B"]
        gt_rows = [["1", "2"]]
        self._seed(tmp_db, gt_headers, gt_rows)
        ext_headers = ["A", "B"]
        ext_rows = [["1", "2"], ["extra", "row"]]
        result = compare_extraction(tmp_db, "T_table_1", ext_headers, ext_rows)
        assert len(result.extra_rows) == 1
        assert result.cell_accuracy_pct == 100.0

    # --- New: Missing rows ---
    def test_missing_rows(self, tmp_db: Path) -> None:
        gt_headers = ["A", "B"]
        gt_rows = [["1", "2"], ["3", "4"]]
        self._seed(tmp_db, gt_headers, gt_rows)
        ext_headers = ["A", "B"]
        ext_rows = [["1", "2"]]
        result = compare_extraction(tmp_db, "T_table_1", ext_headers, ext_rows)
        assert len(result.missing_rows) == 1
        assert result.structural_coverage_pct < 100.0

    # --- New: Header diffs (fuzzy LCS match) ---
    def test_header_diff_lcs_match(self, tmp_db: Path) -> None:
        """Headers matching via LCS (>= 80%) should be paired but diffs reported."""
        gt_headers = ["Total Score"]
        gt_rows = [["95"]]
        self._seed(tmp_db, gt_headers, gt_rows)
        ext_headers = ["Total Scor"]  # 10/11 = 0.91 LCS
        ext_rows = [["95"]]
        result = compare_extraction(tmp_db, "T_table_1", ext_headers, ext_rows)
        assert len(result.matched_columns) == 1
        assert len(result.header_diffs) == 1
        assert result.header_diffs[0].expected == "Total Score"
        assert result.header_diffs[0].actual == "Total Scor"

    # --- New: Artifact table ---
    def test_artifact_table(self, tmp_db: Path) -> None:
        """GT with empty headers and rows is detected as artifact."""
        self._seed(tmp_db, [], [])
        result = compare_extraction(tmp_db, "T_table_1", ["X"], [["data"]])
        assert result.gt_is_artifact is True
        assert result.cell_accuracy_pct == 0.0

    # --- New: Footnote comparison ---
    def test_footnote_match(self, tmp_db: Path) -> None:
        self._seed(tmp_db, ["A"], [["1"]], footnotes="Note. X = cross-reference.")
        result = compare_extraction(
            tmp_db, "T_table_1", ["A"], [["1"]],
            footnotes="Note. X = cross-reference.",
        )
        assert result.footnote_match is True
        assert result.gt_footnotes == "Note. X = cross-reference."

    def test_footnote_mismatch(self, tmp_db: Path) -> None:
        self._seed(tmp_db, ["A"], [["1"]], footnotes="Note. X = cross-reference.")
        result = compare_extraction(
            tmp_db, "T_table_1", ["A"], [["1"]],
            footnotes="wrong",
        )
        assert result.footnote_match is False

    def test_footnote_none_when_gt_empty(self, tmp_db: Path) -> None:
        self._seed(tmp_db, ["A"], [["1"]], footnotes="")
        result = compare_extraction(
            tmp_db, "T_table_1", ["A"], [["1"]],
            footnotes="anything",
        )
        assert result.footnote_match is None

    # --- New: Row skip-ahead (C2) ---
    def test_skip_spurious_ext_row(self, tmp_db: Path) -> None:
        """A spurious extraction row should be skipped, not cascade misalignment."""
        gt_headers = ["A", "B"]
        gt_rows = [["1", "2"], ["3", "4"], ["5", "6"]]
        self._seed(tmp_db, gt_headers, gt_rows)
        ext_headers = ["A", "B"]
        # Spurious "footnote" row inserted between row 0 and row 1
        ext_rows = [["1", "2"], ["Note.", ""], ["3", "4"], ["5", "6"]]
        result = compare_extraction(tmp_db, "T_table_1", ext_headers, ext_rows)
        assert len(result.extra_rows) == 1
        assert result.cell_accuracy_pct == 100.0

    def test_skip_missing_gt_row(self, tmp_db: Path) -> None:
        """When extraction skips a GT row, subsequent rows should still align."""
        gt_headers = ["A", "B"]
        gt_rows = [["1", "2"], ["3", "4"], ["5", "6"]]
        self._seed(tmp_db, gt_headers, gt_rows)
        ext_headers = ["A", "B"]
        # Row 1 ("3","4") missing from extraction
        ext_rows = [["1", "2"], ["5", "6"]]
        result = compare_extraction(tmp_db, "T_table_1", ext_headers, ext_rows)
        assert len(result.missing_rows) == 1
        # The 2 matched rows should be correct
        assert result.cell_accuracy_pct == 100.0

    # --- New: Coverage metrics ---
    def test_coverage_with_split(self, tmp_db: Path) -> None:
        """Split row reduces coverage but not accuracy of remaining cells."""
        gt_headers = ["A", "B"]
        gt_rows = [["1", "2"], ["3", "4"]]
        self._seed(tmp_db, gt_headers, gt_rows)
        ext_headers = ["A", "B"]
        # Row 0 split, row 1 matches
        ext_rows = [["1", ""], ["", "2"], ["3", "4"]]
        result = compare_extraction(tmp_db, "T_table_1", ext_headers, ext_rows)
        assert result.total_gt_cells == 6  # 2 headers + 4 data
        assert result.comparable_cells == 4  # 2 headers + row 1 (2 data cells)
        assert result.cell_accuracy_pct == 100.0  # all 4 comparable cells match
        assert result.structural_coverage_pct == pytest.approx(66.7, abs=0.1)

    # --- Positional fallback ---
    def test_positional_fallback_header_mismatch(self, tmp_db: Path) -> None:
        """When headers differ textually but shapes match, positional fallback
        aligns columns so data cells are compared.  Header mismatches count
        against accuracy proportionally (2 wrong out of 10), not catastrophically."""
        gt_headers = ["", "(µs)"]
        gt_rows = [["Butterworth", "-1.8278"],
                    ["Chebyshev", "-1.5432"],
                    ["Bessel", "-2.1001"],
                    ["Elliptic", "-0.9876"]]
        self._seed(tmp_db, gt_headers, gt_rows)
        ext_headers = ["Filter", "Runtime (µs)"]
        ext_rows = [["Butterworth", "-1.8278"],
                     ["Chebyshev", "-1.5432"],
                     ["Bessel", "-2.1001"],
                     ["Elliptic", "-0.9876"]]
        result = compare_extraction(tmp_db, "T_table_1", ext_headers, ext_rows)
        # Both cols matched by position; 2 header mismatches, 8 data matches
        assert len(result.matched_columns) == 2
        assert len(result.header_diffs) == 2
        assert len(result.cell_diffs) == 0  # all data cells match
        assert result.cell_accuracy_pct == 80.0  # 8/10
        assert result.structural_coverage_pct == 100.0

    # --- New: Empty header positional matching ---
    def test_multiple_empty_headers(self, tmp_db: Path) -> None:
        """Multiple empty-string headers should match positionally."""
        gt_headers = ["", "A", ""]
        gt_rows = [["x", "1", "y"]]
        self._seed(tmp_db, gt_headers, gt_rows)
        ext_headers = ["", "A", ""]
        ext_rows = [["x", "1", "y"]]
        result = compare_extraction(tmp_db, "T_table_1", ext_headers, ext_rows)
        assert len(result.matched_columns) == 3
        assert result.cell_accuracy_pct == 100.0


# ---------------------------------------------------------------------------
# TestFuzzyCellScore
# ---------------------------------------------------------------------------


class TestFuzzyCellScore:
    def test_exact_match(self) -> None:
        assert _fuzzy_cell_score("hello", "hello") == 1.0

    def test_both_empty(self) -> None:
        assert _fuzzy_cell_score("", "") == 1.0

    def test_nonempty_vs_empty(self) -> None:
        assert _fuzzy_cell_score("hello", "") == 0.0

    def test_empty_vs_nonempty(self) -> None:
        assert _fuzzy_cell_score("", "hello") == 0.0

    def test_numeric_exact_match(self) -> None:
        assert _fuzzy_cell_score("0.047", "0.047") == 1.0

    def test_numeric_mismatch(self) -> None:
        assert _fuzzy_cell_score("0.047", "0.47") == 0.0

    def test_decimal_displacement(self) -> None:
        assert _fuzzy_cell_score("0.047", ".047") == 0.0

    def test_numeric_vs_text_mismatch(self) -> None:
        assert _fuzzy_cell_score("0.047", "foo") == 0.0

    def test_text_partial_match(self) -> None:
        score = _fuzzy_cell_score("efficiency", "effciency")
        assert 0.0 < score < 1.0

    def test_text_completely_different(self) -> None:
        assert _fuzzy_cell_score("abc", "xyz") == 0.0

    def test_percentage_numeric(self) -> None:
        assert _fuzzy_cell_score("45.2%", "45.3%") == 0.0

    def test_ligature_normalization(self) -> None:
        assert _fuzzy_cell_score("e\ufb03ciency", "efficiency") == 1.0


# ---------------------------------------------------------------------------
# TestFuzzyAccuracy
# ---------------------------------------------------------------------------


class TestFuzzyAccuracy:
    def test_identical_tables(self) -> None:
        headers = ["A", "B"]
        rows = [["1", "2"], ["3", "4"]]
        p, r, f1 = _compute_fuzzy_accuracy(headers, rows, headers, rows)
        assert p == 1.0
        assert r == 1.0
        assert f1 == 1.0

    def test_both_empty(self) -> None:
        p, r, f1 = _compute_fuzzy_accuracy([], [], [], [])
        assert p == 1.0
        assert r == 1.0
        assert f1 == 1.0

    def test_completely_different(self) -> None:
        p, r, f1 = _compute_fuzzy_accuracy([], [["a", "b"]], [], [["x", "y"]])
        assert p == 0.0
        assert r == 0.0
        assert f1 == 0.0

    def test_extra_ext_cells(self) -> None:
        gt_headers = ["H1", "H2"]
        gt_rows = [["a", "b"]]
        ext_headers = ["H1", "H2"]
        ext_rows = [["a", "b"], ["extra1", "extra2"]]
        p, r, f1 = _compute_fuzzy_accuracy(gt_headers, gt_rows, ext_headers, ext_rows)
        assert r == 1.0
        assert p < 1.0

    def test_missing_cells(self) -> None:
        gt_headers = ["H1", "H2"]
        gt_rows = [["a", "b"], ["c", "d"]]
        ext_headers = ["H1", "H2"]
        ext_rows = [["a", "b"]]
        p, r, f1 = _compute_fuzzy_accuracy(gt_headers, gt_rows, ext_headers, ext_rows)
        assert p == 1.0
        assert r < 1.0

    def test_headers_included(self) -> None:
        gt_headers = ["Col A"]
        gt_rows = [["wrong"]]
        ext_headers = ["Col A"]
        ext_rows = [["other"]]
        p_with, r_with, f1_with = _compute_fuzzy_accuracy(
            gt_headers, gt_rows, ext_headers, ext_rows
        )
        p_no, r_no, f1_no = _compute_fuzzy_accuracy(
            [], gt_rows, [], ext_rows
        )
        # With headers, the matching "Col A" cell adds to the score; without it,
        # only the mismatched data cells remain, producing a strictly lower F1.
        assert f1_with > f1_no

    def test_numeric_mismatch_tanks_score(self) -> None:
        gt_headers: list[str] = []
        gt_rows = [["0.047", "text"]]
        ext_headers: list[str] = []
        ext_rows = [["0.47", "text"]]
        p, r, f1 = _compute_fuzzy_accuracy(gt_headers, gt_rows, ext_headers, ext_rows)
        assert p == 0.5
        assert r == 0.5


# ---------------------------------------------------------------------------
# TestComparisonFuzzyFields
# ---------------------------------------------------------------------------


class TestComparisonFuzzyFields:
    def _seed(
        self, db: Path, headers: list[str], rows: list[list[str]],
        table_id: str = "T_table_1", footnotes: str = "",
    ) -> None:
        create_ground_truth_db(db)
        insert_ground_truth(
            db, table_id, "T", 1, "Table 1", headers, rows,
            footnotes=footnotes,
        )

    def test_fields_exist(self) -> None:
        r = ComparisonResult(
            table_id="x",
            gt_shape=(0, 0),
            ext_shape=(0, 0),
            matched_columns=[],
            extra_columns=[],
            missing_columns=[],
            column_splits=[],
            column_merges=[],
            matched_rows=[],
            extra_rows=[],
            missing_rows=[],
            row_splits=[],
            row_merges=[],
            cell_diffs=[],
            cell_accuracy_pct=0.0,
            header_diffs=[],
        )
        assert hasattr(r, "fuzzy_accuracy_pct")
        assert hasattr(r, "fuzzy_precision_pct")
        assert hasattr(r, "fuzzy_recall_pct")

    def test_compare_extraction_populates_fuzzy(self, tmp_db: Path) -> None:
        headers = ["A", "B"]
        rows = [["1", "2"], ["3", "4"]]
        self._seed(tmp_db, headers, rows)
        result = compare_extraction(tmp_db, "T_table_1", headers, rows)
        assert result.fuzzy_accuracy_pct == 100.0
        assert result.fuzzy_precision_pct == 100.0
        assert result.fuzzy_recall_pct == 100.0

    def test_fuzzy_not_vacuous_when_structural_fails(self, tmp_db: Path) -> None:
        gt_headers = ["Alpha", "Beta"]
        gt_rows = [["val1", "val2"]]
        self._seed(tmp_db, gt_headers, gt_rows)
        ext_headers = ["Gamma", "Delta"]
        ext_rows = [["val1", "val2"]]
        result = compare_extraction(tmp_db, "T_table_1", ext_headers, ext_rows)
        # Positional fallback matches col 0↔0, col 1↔1.
        # 2 header mismatches + 2 data matches = 2/4 = 50%.
        assert result.cell_accuracy_pct == 50.0
        # Fuzzy accuracy is alignment-free and unchanged.
        # 4 GT cells, 4 ext cells. val1 and val2 match exactly (1.0 each).
        # Delta/Beta share LCS "ta" (2/5=0.4), Gamma/Alpha share LCS "a" (1/5=0.2).
        # Precision = recall = (1.0+1.0+0.4+0.2)/4 = 0.65, F1 = 65%.
        assert result.fuzzy_accuracy_pct == 65.0
