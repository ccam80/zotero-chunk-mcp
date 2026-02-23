# Phase 0: Dead Code Removal

## Overview

Remove the column-count-based grouping code from `combination.py`, fix the vacuous
accuracy default in `ground_truth.py`, and stub `combine_hypotheses()` with
`NotImplementedError` until Phase 2 provides the per-divider voting replacement.

**Entry state**: Pipeline functional with column-count grouping.
**Exit state**: Pipeline broken for multi-hypothesis combination (single-hypothesis
passthrough and empty-list handling still work). 8 tests that require multi-hypothesis
combination will fail with `NotImplementedError` (expected — restored in Phase 2).

---

## Wave 0.1: Remove obsolete combination and metric code

### Task 0.1.1: Remove column-count grouping and fix vacuous accuracy default

- **Description**: Remove `_select_best_column_group()` and `_group_confidence()`
  from `combination.py`. Stub the multi-hypothesis path in `combine_hypotheses()`
  with `NotImplementedError`. Change the vacuous `else 100.0` default in
  `ground_truth.py` to `else 0.0`. Delete `TestColumnGrouping` tests. 8 tests
  that call `combine_hypotheses()` with 2+ hypotheses will fail with
  `NotImplementedError` until Phase 2 restores them.

- **Files to modify**:
  - `src/zotero_chunk_rag/feature_extraction/combination.py`:
    - Delete `_select_best_column_group()` (lines 157-213)
    - Delete `_group_confidence()` (lines 216-222)
    - In `combine_hypotheses()`: replace the multi-hypothesis body (everything
      after the single-hypothesis passthrough, starting at line 97) with
      `raise NotImplementedError("awaiting per-divider voting rewrite")`
    - Keep empty-list handling (lines 53-75) and single-hypothesis passthrough
      (lines 77-95) unchanged
    - Keep all remaining functions unchanged: `_make_passthrough_trace()`,
      `_compute_spatial_precision()`, `_expand_point_estimate()`,
      `_merge_overlapping()`, `_combine_axis()`
  - `src/zotero_chunk_rag/feature_extraction/ground_truth.py`:
    - Line 686: change `else 100.0` to `else 0.0` in the `cell_accuracy_pct`
      computation
  - `tests/test_combination.py`:
    - Delete `TestColumnGrouping` class entirely
    - Delete `_make_hyp()` helper function (only used by `TestColumnGrouping`)
    - Remove `_select_best_column_group` from the import block
    - The following 8 tests will fail with `NotImplementedError` after this
      change (expected — Phase 2 restores them):
      - `TestCombineHypotheses::test_two_methods_agree`
      - `TestCombineHypotheses::test_three_methods_one_disagrees`
      - `TestCombineHypotheses::test_row_and_col_independent`
      - `TestAcceptanceThreshold::test_low_confidence_rejected`
      - `TestAcceptanceThreshold::test_percentile_based_acceptance`
      - `TestAcceptanceThreshold::test_single_cluster_always_accepted`
      - `TestCombinationTrace::test_multi_hypothesis_trace_structure`
      - `TestCombinationTrace::test_axis_trace_input_points_match`

- **Tests** (all should pass after changes):
  - `tests/test_combination.py::TestCombineHypotheses::test_empty_hypotheses_list` — assert returns empty consensus
  - `tests/test_combination.py::TestCombineHypotheses::test_single_hypothesis_passthrough` — assert returns passthrough
  - `tests/test_combination.py::TestAcceptanceThreshold::test_single_high_confidence_accepted` — single hypothesis, still works
  - `tests/test_combination.py::TestCombinationTrace::test_trace_false_returns_hypothesis_only` — single hypothesis
  - `tests/test_combination.py::TestCombinationTrace::test_trace_true_returns_tuple` — single hypothesis
  - `tests/test_combination.py::TestCombinationTrace::test_empty_hypotheses_trace` — empty input
  - `tests/test_combination.py::TestCombinationTrace::test_single_hypothesis_passthrough_trace` — single hypothesis
  - `tests/test_combination.py::TestExpandPointEstimates::*` — all unchanged
  - `tests/test_combination.py::TestOverlapMerge::*` — all unchanged
  - `tests/test_combination.py::TestSpatialPrecision::*` — all unchanged
  - 8 tests listed above fail with `NotImplementedError` (expected — restored in Phase 2)

- **Acceptance criteria**:
  - `_select_best_column_group` and `_group_confidence` no longer exist in `combination.py`
  - `grep -r "_select_best_column_group\|_group_confidence" src/` returns nothing
  - `combine_hypotheses([h1, h2], ctx)` raises `NotImplementedError`
  - `combine_hypotheses([], ctx)` and `combine_hypotheses([h1], ctx)` still work correctly
  - `ground_truth.py` cell_accuracy_pct default is `else 0.0`
  - `TestColumnGrouping` class no longer exists
  - All other tests pass; 8 tests listed above fail with `NotImplementedError` (restored in Phase 2)
