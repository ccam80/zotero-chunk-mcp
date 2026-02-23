# Phase 1: Accuracy Metric Rewrite

## Overview

Add an alignment-free symmetric fuzzy accuracy metric to `ground_truth.py` that
produces meaningful scores regardless of structural alignment success. The metric
uses bag-of-cells matching with best-first greedy assignment, computing precision,
recall, and F1. Numeric cells are scored strictly (exact match or zero), while text
cells get partial credit via longest common substring ratio.

**Depends on**: Phase 0 (dead code removal)
**Wave 1.1**: Can run in parallel with Phase 2
**Wave 1.2**: Must wait for Phase 2 (needs working `combine_hypotheses()` for stress test)

**Entry state**: `cell_accuracy_pct` returns vacuous 100% on 31/41 tables (0 comparable cells).
**Exit state**: `fuzzy_accuracy_pct` returns meaningful accuracy on every GT table.

---

## Wave 1.1: Symmetric fuzzy cell accuracy

### Task 1.1.1: Fuzzy cell scoring function

- **Description**: Implement `_fuzzy_cell_score(a: str, b: str) -> float` in
  `ground_truth.py`. After normalizing both cells via `_normalize_cell()`:
  exact match -> 1.0; both empty -> 1.0; one empty/one not -> 0.0; if either
  cell is numeric and they don't match -> 0.0 (numeric mismatch is complete
  failure); otherwise text -> `_longest_common_substring_len(a, b) / max(len(a), len(b))`.

  Also implement `_is_numeric_cell(text: str) -> bool` helper: strip whitespace,
  strip trailing `%`, try `float()`. If it parses, the cell is numeric. Reuses the
  same logic pattern as `scoring.py::_is_numeric()` but lives in `ground_truth.py`
  to avoid cross-module dependency.

- **Files to modify**:
  - `src/zotero_chunk_rag/feature_extraction/ground_truth.py`:
    - Add `_is_numeric_cell(text: str) -> bool` function
    - Add `_fuzzy_cell_score(a: str, b: str) -> float` function
    - Both placed in a new section after `_normalize_cell()` (before column alignment)

- **Tests**:
  - `tests/test_feature_extraction/test_ground_truth.py::TestFuzzyCellScore::test_exact_match` —
    assert `_fuzzy_cell_score("hello", "hello") == 1.0`
  - `tests/test_feature_extraction/test_ground_truth.py::TestFuzzyCellScore::test_both_empty` —
    assert `_fuzzy_cell_score("", "") == 1.0`
  - `tests/test_feature_extraction/test_ground_truth.py::TestFuzzyCellScore::test_nonempty_vs_empty` —
    assert `_fuzzy_cell_score("hello", "") == 0.0`
  - `tests/test_feature_extraction/test_ground_truth.py::TestFuzzyCellScore::test_empty_vs_nonempty` —
    assert `_fuzzy_cell_score("", "hello") == 0.0`
  - `tests/test_feature_extraction/test_ground_truth.py::TestFuzzyCellScore::test_numeric_exact_match` —
    assert `_fuzzy_cell_score("0.047", "0.047") == 1.0`
  - `tests/test_feature_extraction/test_ground_truth.py::TestFuzzyCellScore::test_numeric_mismatch` —
    assert `_fuzzy_cell_score("0.047", "0.47") == 0.0`
  - `tests/test_feature_extraction/test_ground_truth.py::TestFuzzyCellScore::test_decimal_displacement` —
    assert `_fuzzy_cell_score("0.047", ".047") == 0.0` (different strings, both numeric)
  - `tests/test_feature_extraction/test_ground_truth.py::TestFuzzyCellScore::test_numeric_vs_text_mismatch` —
    assert `_fuzzy_cell_score("0.047", "foo") == 0.0` (GT is numeric, mismatch is fatal)
  - `tests/test_feature_extraction/test_ground_truth.py::TestFuzzyCellScore::test_text_partial_match` —
    assert `0.0 < _fuzzy_cell_score("efficiency", "effciency") < 1.0`
  - `tests/test_feature_extraction/test_ground_truth.py::TestFuzzyCellScore::test_text_completely_different` —
    `_fuzzy_cell_score("abc", "xyz")` — LCS is 0, returns 0.0
  - `tests/test_feature_extraction/test_ground_truth.py::TestFuzzyCellScore::test_percentage_numeric` —
    assert `_fuzzy_cell_score("45.2%", "45.3%") == 0.0` (both numeric after strip %)
  - `tests/test_feature_extraction/test_ground_truth.py::TestFuzzyCellScore::test_ligature_normalization` —
    assert `_fuzzy_cell_score("e\ufb03ciency", "efficiency") == 1.0` (normalization handles ligatures)

- **Acceptance criteria**:
  - `_fuzzy_cell_score` returns 1.0 for exact matches (after normalization)
  - `_fuzzy_cell_score` returns 0.0 for any mismatch where either cell is numeric
  - `_fuzzy_cell_score` returns LCS ratio (0.0-1.0) for text mismatches
  - All 12 test cases pass

### Task 1.1.2: Compute fuzzy accuracy (precision, recall, F1)

- **Description**: Implement `_compute_fuzzy_accuracy(gt_headers, gt_rows, ext_headers, ext_rows) -> tuple[float, float, float]` in `ground_truth.py`.

  Algorithm:
  1. Collect all non-empty cells from GT (headers + rows) into `gt_cells: list[str]`
  2. Collect all non-empty cells from extraction (headers + rows) into `ext_cells: list[str]`
  3. If both empty: return `(1.0, 1.0, 1.0)`
  4. If one empty and other not: return `(0.0, 0.0, 0.0)`
  5. **Precision (ext -> GT)**: Build all `(ext_idx, gt_idx, score)` triples via
     `_fuzzy_cell_score`. Sort descending by score. Greedily assign: for each triple
     in order, if neither ext_idx nor gt_idx is already assigned, assign them.
     Precision = sum(assigned scores) / len(ext_cells).
  6. **Recall (GT -> ext)**: Same algorithm in reverse direction — build
     `(gt_idx, ext_idx, score)` triples, greedy assign, recall = sum / len(gt_cells).
  7. **F1**: Harmonic mean of precision and recall. If both are 0.0, F1 = 0.0.
  8. Return `(precision, recall, f1)` as fractions (0.0-1.0).

- **Files to modify**:
  - `src/zotero_chunk_rag/feature_extraction/ground_truth.py`:
    - Add `_compute_fuzzy_accuracy()` function after `_fuzzy_cell_score()`

- **Tests**:
  - `tests/test_feature_extraction/test_ground_truth.py::TestFuzzyAccuracy::test_identical_tables` —
    same headers and rows -> `(1.0, 1.0, 1.0)`
  - `tests/test_feature_extraction/test_ground_truth.py::TestFuzzyAccuracy::test_both_empty` —
    no headers, no rows on either side -> `(1.0, 1.0, 1.0)`
  - `tests/test_feature_extraction/test_ground_truth.py::TestFuzzyAccuracy::test_completely_different` —
    GT has `["a", "b"]`, ext has `["x", "y"]`, no common substrings -> all 0.0
  - `tests/test_feature_extraction/test_ground_truth.py::TestFuzzyAccuracy::test_extra_ext_cells` —
    GT has 4 cells, ext has 6 cells (4 matching + 2 extra). Recall = 1.0 (all GT found),
    precision < 1.0 (extra ext cells unmatched).
  - `tests/test_feature_extraction/test_ground_truth.py::TestFuzzyAccuracy::test_missing_cells` —
    GT has 6 cells, ext has 4 (all matching GT subset). Precision = 1.0 (all ext correct),
    recall < 1.0 (missing GT cells).
  - `tests/test_feature_extraction/test_ground_truth.py::TestFuzzyAccuracy::test_headers_included` —
    Header cells contribute to the comparison. GT headers `["Col A"]` with matching ext
    headers -> higher score than if headers were excluded.
  - `tests/test_feature_extraction/test_ground_truth.py::TestFuzzyAccuracy::test_numeric_mismatch_tanks_score` —
    GT row `["0.047", "text"]`, ext row `["0.47", "text"]`. The numeric mismatch scores 0.0;
    "text" matches 1.0. Precision and recall both 0.5.

- **Acceptance criteria**:
  - Returns `(1.0, 1.0, 1.0)` for identical tables and for both-empty tables
  - Returns `(0.0, 0.0, 0.0)` when tables share no common cells
  - Precision and recall correctly reflect extra/missing cells
  - Headers are included in the cell bags
  - Best-first greedy assignment: highest-scoring pairs assigned first
  - All 7 test cases pass

### Task 1.1.3: Add fuzzy fields to ComparisonResult

- **Description**: Add `fuzzy_accuracy_pct`, `fuzzy_precision_pct`,
  `fuzzy_recall_pct` fields to the `ComparisonResult` dataclass. Compute them
  in `compare_extraction()` by calling `_compute_fuzzy_accuracy()` with the
  GT and extraction headers + rows. Keep existing structural analysis unchanged.

- **Files to modify**:
  - `src/zotero_chunk_rag/feature_extraction/ground_truth.py`:
    - Add 3 float fields to `ComparisonResult` (defaults 0.0):
      - `fuzzy_accuracy_pct: float = 0.0`
      - `fuzzy_precision_pct: float = 0.0`
      - `fuzzy_recall_pct: float = 0.0`
    - In `compare_extraction()`, after structural analysis, call
      `_compute_fuzzy_accuracy(gt_headers, gt_rows, headers, rows)` and
      multiply each component by 100.0 to get percentage values. Assign
      to the result.

- **Tests**:
  - `tests/test_feature_extraction/test_ground_truth.py::TestComparisonFuzzyFields::test_fields_exist` —
    `ComparisonResult` has `fuzzy_accuracy_pct`, `fuzzy_precision_pct`, `fuzzy_recall_pct`
  - `tests/test_feature_extraction/test_ground_truth.py::TestComparisonFuzzyFields::test_compare_extraction_populates_fuzzy` —
    Call `compare_extraction()` with a known GT table. Assert fuzzy fields are > 0.0
    (not default).
  - `tests/test_feature_extraction/test_ground_truth.py::TestComparisonFuzzyFields::test_fuzzy_not_vacuous_when_structural_fails` —
    Call `compare_extraction()` with headers that don't align (0 comparable cells).
    Assert `cell_accuracy_pct == 0.0` (the new default) but `fuzzy_accuracy_pct > 0.0`
    (fuzzy metric still produces a meaningful score from the cell bags).

- **Acceptance criteria**:
  - `ComparisonResult` has all 3 new fuzzy fields
  - `compare_extraction()` populates them with non-default values
  - When structural alignment fails, fuzzy accuracy is still meaningful
  - Existing structural fields (`cell_accuracy_pct`, `matched_columns`, etc.) unchanged
  - All 3 test cases pass

---

## Wave 1.2: Stress test integration

**Depends on**: Phase 2 complete (needs working `combine_hypotheses()`)

### Task 1.2.1: Update stress test to use fuzzy metrics

- **Description**: Update the stress test to use `fuzzy_accuracy_pct` as the
  primary quality metric throughout. Add fuzzy columns to the `ground_truth_diffs`
  table schema. Update the GT comparison report section.

- **Files to modify**:
  - `src/zotero_chunk_rag/feature_extraction/debug_db.py`:
    - Add `fuzzy_accuracy_pct REAL`, `fuzzy_precision_pct REAL`,
      `fuzzy_recall_pct REAL` columns to the `ground_truth_diffs` table in
      `EXTENDED_SCHEMA`
    - Update `write_ground_truth_diff()` to accept and write the fuzzy fields
  - `tests/stress_test_real_library.py`:
    - In `_test_pipeline_methods()`: change `quality_score` written to
      `method_results` from `cmp.cell_accuracy_pct` to `cmp.fuzzy_accuracy_pct`
    - In `_write_ground_truth_diffs()` (or wherever GT diffs are written): pass
      the 3 fuzzy fields from `ComparisonResult` to `write_ground_truth_diff()`
    - In the GT comparison report section: show `fuzzy_accuracy_pct` as the
      primary accuracy, show precision and recall alongside
    - In the pipeline depth report: use `fuzzy_accuracy_pct` for win rate
      computation and combination-value analysis

- **Tests**:
  - `tests/test_feature_extraction/test_debug_db.py::TestExtendedSchema::test_ground_truth_diffs_has_fuzzy_columns` —
    Create a temp DB, write the extended schema, assert `ground_truth_diffs` table
    has columns `fuzzy_accuracy_pct`, `fuzzy_precision_pct`, `fuzzy_recall_pct`
    (query `PRAGMA table_info(ground_truth_diffs)`).
  - The stress test itself is the integration test. Acceptance verified by running
    it and inspecting the output.

- **Acceptance criteria**:
  - `ground_truth_diffs` table has `fuzzy_accuracy_pct`, `fuzzy_precision_pct`,
    `fuzzy_recall_pct` columns
  - `method_results.quality_score` contains fuzzy accuracy values (no vacuous 100%)
  - Stress test report shows fuzzy accuracy per table
  - `tune_weights.py` win rate computation uses the fuzzy-based `quality_score`
  - No vacuous 100% scores in the report (every GT table has a meaningful metric)
