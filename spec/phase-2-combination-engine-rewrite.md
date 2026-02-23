# Phase 2: Combination Engine Rewrite

## Overview

Replace column-count-based grouping with per-divider confidence voting. The core
change: a boundary that many methods independently find (high method agreement)
is more trustworthy than one only a single method reports. No grouping by column
count — all boundary points from all methods are pooled and voted on independently.

Confidence multipliers from `pipeline_weights.json` scale method influence. Ruled
line boundaries get unconditional acceptance (physical features, not statistical).

**Depends on**: Phase 0 (stub removed here)
**Parallel with**: Phase 1 Wave 1.1
**Must complete before**: Phase 1 Wave 1.2

**Entry state**: `combine_hypotheses()` raises `NotImplementedError` for 2+ hypotheses.
**Exit state**: Per-divider voting produces consensus boundaries. Pipeline fully functional.

---

## Wave 2.1: Core per-divider voting

### Task 2.1.1: Rewrite `combine_hypotheses()` with per-divider voting

- **Description**: Replace the `NotImplementedError` stub in the multi-hypothesis
  path of `combine_hypotheses()` with the per-divider voting algorithm.

  **Algorithm** (multi-hypothesis path):
  1. Compute spatial precision via existing `_compute_spatial_precision(ctx)`
  2. Collect ALL col boundary points and ALL row boundary points from ALL hypotheses
     (no column-count grouping)
  3. Scale each point's confidence by its method's multiplier:
     `scaled_confidence = point.confidence * multipliers.get(point.provenance, 1.0)`
     (create new BoundaryPoint with scaled confidence, preserving provenance)
  4. Pass scaled col points and row points to `_combine_axis()` (independently)
  5. Build consensus BoundaryHypothesis from accepted boundaries

  **Changes to `_combine_axis()`** — acceptance logic only:
  - After clustering (steps 1-4 unchanged): compute `distinct_methods` per cluster
    (already done via provenance)
  - Compute `median_method_count = statistics.median([cluster.distinct_methods for each cluster])`
  - Accept cluster if `distinct_methods >= median_method_count`
  - **Ruled line override**: accept cluster if ANY point in it has
    `provenance == "ruled_lines"`, regardless of method count
  - Remove the Q1-percentile confidence threshold (replaced by method count)
  - **Consensus boundary confidence**: each accepted boundary's confidence is
    the mean of its constituent points' scaled confidences (not the sum). This
    prevents methods with many boundary points from dominating through volume.

  Add helper `_scale_point(point: BoundaryPoint, multipliers: dict[str, float] | None) -> BoundaryPoint`:
  returns the point unchanged if multipliers is None or the method's multiplier is 1.0;
  otherwise returns a new BoundaryPoint with `confidence * multiplier`.

  **Signature change**: `combine_hypotheses(hypotheses, ctx, *, confidence_multipliers=None, trace=False)`.
  New `confidence_multipliers: dict[str, float] | None` parameter. When None, no
  scaling is applied (all multipliers default to 1.0).

- **Files to modify**:
  - `src/zotero_chunk_rag/feature_extraction/combination.py`:
    - Replace the `NotImplementedError` stub in the multi-hypothesis path
    - Add `confidence_multipliers` parameter to `combine_hypotheses()` signature
    - Add `_scale_point()` helper
    - In `_combine_axis()` step 5: replace Q1-confidence acceptance with
      median-method-count acceptance + ruled line override
    - Remove the docstring references to "column count agreement grouping"
    - Update module docstring to describe per-divider voting

- **Tests** (update existing + add new):
  - The 8 tests broken by Phase 0's `NotImplementedError` stub should now
    pass again with the new per-divider voting implementation.
  - Update `tests/test_combination.py::TestCombineHypotheses::test_two_methods_agree` —
    2 hypotheses with overlapping boundaries at ~145. Both merge into 1 cluster
    with method_count=2, median=2, accepted. Assert 1 col boundary. **Unchanged assertion.**
  - Update `tests/test_combination.py::TestCombineHypotheses::test_three_methods_one_disagrees` —
    3 hypotheses: 2 at ~145, 1 at ~200. Clusters: ~145 (method_count=2), ~200
    (method_count=1). Median=1.5. Only count>=2 passes. Assert 1 col boundary.
    **Unchanged assertion.**
  - Update `tests/test_combination.py::TestCombineHypotheses::test_row_and_col_independent` —
    2 hypotheses with different col/row positions. Each position has method_count=1,
    median=1, all pass. Assert 2 col + 2 row boundaries. **Unchanged assertion.**
  - Update `tests/test_combination.py::TestAcceptanceThreshold::test_low_confidence_rejected` —
    Under new algorithm: cluster at ~145 has method_count=3, cluster at ~500 has
    method_count=1. Median=2. Count 1 < 2, rejected. Assert 1 col boundary.
    **Unchanged assertion.**
  - **CHANGE** `tests/test_combination.py::TestAcceptanceThreshold::test_percentile_based_acceptance` —
    Under old algorithm, weakest-confidence cluster was rejected (4 boundaries).
    Under new algorithm, ALL 5 clusters have method_count=2 (both methods contribute
    to each), median=2, all pass. **Update assertion to `len(result.col_boundaries) == 5`**.
    Rename test to `test_equal_method_agreement_all_pass`.
  - Update `tests/test_combination.py::TestAcceptanceThreshold::test_single_cluster_always_accepted` —
    2 hypotheses merge into 1 cluster, method_count=2, median=2, accepted.
    **Unchanged assertion.**
  - Update `tests/test_combination.py::TestCombinationTrace::test_multi_hypothesis_trace_structure` —
    Check that `ClusterRecord` now has `method_names` and `acceptance_reason` fields.
    Assert `cluster.method_names` is a non-empty list.
    Assert `cluster.acceptance_reason` is one of `"above_threshold"`, `"ruled_line_override"`, `"rejected"`.
  - Update `tests/test_combination.py::TestCombinationTrace::test_axis_trace_input_points_match` —
    All hypotheses' points are now in the pool (no column-count filtering). Assert
    input_provenances contains all methods. **Unchanged assertion** (both methods
    were in the winning group before too).
  - **NEW** `tests/test_combination.py::TestMethodCountRejection::test_lone_divider_rejected` —
    3 methods: m1 and m2 agree on divider at ~150, m1 and m3 agree on divider at ~300,
    m2 alone adds divider at ~500. Clusters: ~150 (count=2), ~300 (count=2), ~500
    (count=1). Median=2. Assert ~500 rejected, 2 boundaries accepted.
  - **NEW** `tests/test_combination.py::TestMethodCountRejection::test_single_method_all_pass` —
    1 method with 3 col boundaries. Passthrough (single hypothesis), all accepted.
  - **NEW** `tests/test_combination.py::TestConfidenceMultipliers::test_multipliers_scale_confidence` —
    2 hypotheses at same position. Method "m1" has multiplier 2.0, "m2" has 0.5.
    After combination, the consensus boundary's confidence is the mean of scaled
    confidences: (0.9\*2.0 + 0.9\*0.5) / 2 = 1.125. Assert `result.col_boundaries[0].confidence == pytest.approx(1.125)`.
  - **NEW** `tests/test_combination.py::TestConfidenceMultipliers::test_no_multipliers_default` —
    Call without `confidence_multipliers` parameter. Behavior unchanged from unscaled.
  - **NEW** `tests/test_combination.py::TestRuledLineOverride::test_ruled_line_always_accepted` —
    3 methods: 2 agree at ~150 (method_count=2), 1 ruled_lines point at ~300
    (method_count=1). Median=1.5. Without override, ~300 rejected. With override,
    ~300 accepted because it has ruled_lines provenance. Assert 2 boundaries.
  - **NEW** `tests/test_combination.py::TestRuledLineOverride::test_non_ruled_line_still_rejected` —
    Same setup but the lone point at ~300 has provenance "hotspot" instead of
    "ruled_lines". Assert 1 boundary (only ~150 accepted).

- **Acceptance criteria**:
  - `combine_hypotheses()` no longer raises `NotImplementedError`
  - No column-count grouping in the code
  - All boundary points from all hypotheses are pooled (no filtering by group)
  - Acceptance based on median method_count, not Q1 confidence percentile
  - Ruled line override works: `provenance == "ruled_lines"` always accepted
  - Confidence multipliers scale point confidences before combination
  - All existing tests pass (with updated assertions where noted)
  - All new tests pass
  - All 8 tests broken by Phase 0 now pass

### Task 2.1.2: Pass confidence multipliers from Pipeline

- **Description**: Update `Pipeline.extract()` to pass
  `self._config.confidence_multipliers` to `combine_hypotheses()` at the call site.

- **Files to modify**:
  - `src/zotero_chunk_rag/feature_extraction/pipeline.py`:
    - In `Pipeline.extract()`, line ~270 where `combine_hypotheses()` is called:
      change from `combine_hypotheses(result.boundary_hypotheses, ctx)` to
      `combine_hypotheses(result.boundary_hypotheses, ctx, confidence_multipliers=self._config.confidence_multipliers)`

- **Tests**:
  - `tests/test_feature_extraction/test_integration.py::TestExtractAllGrids::*` —
    all existing integration tests should still pass (Pipeline now passes multipliers,
    but behavior is compatible)

- **Acceptance criteria**:
  - `Pipeline.extract()` passes `confidence_multipliers` to `combine_hypotheses()`
  - Existing integration tests pass
  - `pipeline_weights.json` multipliers are actually used during combination

---

## Wave 2.2: Trace infrastructure updates

### Task 2.2.1: Update trace models for per-divider voting

- **Description**: Update `ClusterRecord` and `AxisTrace` in `models.py` to
  reflect the new algorithm's diagnostic data.

- **Files to modify**:
  - `src/zotero_chunk_rag/feature_extraction/models.py`:
    - `ClusterRecord`: add `method_names: list[str]` (names of distinct methods
      in this cluster) and `acceptance_reason: str` (one of `"above_threshold"`,
      `"ruled_line_override"`, `"rejected"`)
    - `AxisTrace`: add `median_method_count: float` (the median used as threshold)
  - `src/zotero_chunk_rag/feature_extraction/combination.py`:
    - In `_combine_axis()`: populate `method_names` and `acceptance_reason` on
      each `ClusterRecord` when `collect_trace=True`
    - Populate `median_method_count` on `AxisTrace`
    - In `_make_passthrough_trace()`: set `method_names` and `acceptance_reason`
      appropriately for passthrough clusters

- **Tests**:
  - `tests/test_combination.py::TestCombinationTrace::test_multi_hypothesis_trace_structure` —
    already updated in Task 2.1.1 to check new fields
  - `tests/test_combination.py::TestCombinationTrace::test_trace_cluster_has_method_names` —
    (new) Pass 2 hypotheses with trace=True. Assert each ClusterRecord in
    `trace.col_trace.clusters` has a non-empty `method_names` list.
  - `tests/test_combination.py::TestCombinationTrace::test_trace_has_median_method_count` —
    (new) Pass 2 hypotheses with trace=True. Assert `trace.col_trace.median_method_count > 0`.
  - `tests/test_combination.py::TestCombinationTrace::test_acceptance_reason_values` —
    (new) Pass 3 hypotheses where one cluster is rejected. Assert at least one cluster
    has `acceptance_reason == "rejected"` and at least one has `acceptance_reason == "above_threshold"`.

- **Acceptance criteria**:
  - `ClusterRecord` has `method_names` and `acceptance_reason` fields
  - `AxisTrace` has `median_method_count` field
  - Passthrough traces have appropriate values for new fields
  - All trace tests pass
