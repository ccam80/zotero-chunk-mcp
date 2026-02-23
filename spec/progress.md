# Implementation Progress

Progress is recorded here by implementation agents. Each completed task appends its status below.

## Baseline (pre-plan)

- Stress test: 250/291 passed (86%), 21 MAJOR failures
- GT cell accuracy: 73.5% (pipeline), 100% (best single method)
- Best config: FAST (84.9%) > DEFAULT (75.6%)
- Root cause: consensus combination creates phantom boundaries
- Agent QA: infrastructure built, never executed

## Phase 1: Pipeline Architecture Fix

### Task 1.1.1: Add `structure_method` field to CellGrid
- **Status**: complete
- `CellGrid.structure_method` field added with default `"consensus"`
- `CellGrid.with_structure_method()` helper returns copy with field replaced
- `CellGrid.to_dict()` includes `structure_method`
- **Files modified**: `feature_extraction/models.py`
- **Tests**: 4 methods in `TestCellGridProvenance` (test_integration.py)

### Task 1.1.2: Restructure `Pipeline.extract()` to score all grids
- **Status**: complete
- `extract()` runs cell extraction per-structure-method + consensus
- `result.cell_grids` contains grids from multiple structure methods
- Composite keys `"structure:cell"` in `grid_scores`
- **Files modified**: `feature_extraction/pipeline.py`, `feature_extraction/scoring.py`
- **Tests**: 5 methods in `TestExtractAllGrids` (test_integration.py)

### Task 1.1.3: Remove `extract_with_all_boundaries()` and update stress test
- **Status**: complete
- `extract_with_all_boundaries()` deleted from `Pipeline`
- Stress test uses `pipeline.extract()` with `grid.structure_method` grouping
- **Files modified**: `feature_extraction/pipeline.py`, `tests/stress_test_real_library.py`
- **Tests**: 1 method in `TestExtractWithAllBoundariesRemoved` (test_integration.py)

### Task 1.2.1: Replace column-count grouping tolerance
- **Status**: complete (superseded by Phase 0 + Phase 2 rewrite)
- **Files modified**: `feature_extraction/combination.py`

### Task 1.2.2: Replace expansion/tolerance/acceptance thresholds
- **Status**: complete (acceptance logic superseded by Phase 2 median method count)
- `_compute_spatial_precision()` priority chain: ruled line thickness -> word gap -> word height (no multiplier constants)
- `_compute_expansion_threshold()` and `_compute_tolerance()` deleted
- `CombinationTrace` has `spatial_precision` field
- **Files modified**: `feature_extraction/combination.py`, `feature_extraction/models.py`
- **Tests**: 4 methods in `TestSpatialPrecision`, 2 methods in `TestAcceptanceThreshold` (test_combination.py)

### Task 1.3.1: Combination trace tests
- **Status**: complete
- 6 test methods in `TestCombinationTrace` (test_combination.py)
- Covers: empty input, single input, multi input, trace=True, trace=False
- **Files modified**: `tests/test_combination.py`

### Task 1.3.2: Pipeline integration tests with real PDF
- **Status**: complete
- 11 test methods across `TestCellGridProvenance`, `TestExtractAllGrids`, `TestExtractWithAllBoundariesRemoved`
- Uses `noname1.pdf` fixture
- **Files modified**: `tests/test_feature_extraction/test_integration.py`

## Phase 1 Review Fixes

- Replaced `pytest.skip` with `pytest.fail` in `_pipeline_result` fixture (V1)
- Switched fixture from `noname2.pdf` to spec-mandated `noname1.pdf` (V2)
- Changed acceptance threshold (later superseded by Phase 2 median method count) (V3)
- Added `TestSpatialPrecision` (4 tests), `TestColumnGrouping` (5 tests) (G1, G4)
- Added `test_percentile_based_acceptance`, `test_single_cluster_always_accepted` (G2, G3)
- Strengthened `test_winning_grid_has_provenance` assertion (WT2)
- Updated `progress.md` to reflect current spec tasks (G5)

## Phase 0: Dead Code Removal

### Task 0.1.1: Remove column-count grouping and fix vacuous accuracy default
- **Status**: complete
- **Agent**: implementer
- **Files modified**: `src/zotero_chunk_rag/feature_extraction/combination.py`, `src/zotero_chunk_rag/feature_extraction/ground_truth.py`, `tests/test_combination.py`
- **Tests**: 16/24 passing (8 fail with expected NotImplementedError per spec -- restored in Phase 2)
- `_select_best_column_group()` and `_group_confidence()` deleted from combination.py
- Multi-hypothesis path in `combine_hypotheses()` raises `NotImplementedError("awaiting per-divider voting rewrite")`
- Empty-list and single-hypothesis passthrough unchanged and working
- `ground_truth.py` cell_accuracy_pct default changed from `else 100.0` to `else 0.0`
- `TestColumnGrouping` class and `_make_hyp` helper deleted from test_combination.py
- `_select_best_column_group` removed from test imports

---
## Wave 0.1 Summary
- **Status**: complete
- **Tasks completed**: 1/1
- **Rounds**: 1

## Phase 1 (new): Accuracy Metric Rewrite

### Task 1.1.1: Fuzzy cell scoring function
- **Status**: complete
- **Agent**: implementer
- **Files modified**: `src/zotero_chunk_rag/feature_extraction/ground_truth.py`, `tests/test_feature_extraction/test_ground_truth.py`
- **Tests**: 12/12 passing
- `_is_numeric_cell()` and `_fuzzy_cell_score()` added after `_normalize_cell()`
- Exact match -> 1.0, both empty -> 1.0, one empty -> 0.0, numeric mismatch -> 0.0, text -> LCS ratio

### Task 1.1.2: Compute fuzzy accuracy (precision, recall, F1)
- **Status**: complete
- **Agent**: implementer
- **Files modified**: `src/zotero_chunk_rag/feature_extraction/ground_truth.py`, `tests/test_feature_extraction/test_ground_truth.py`
- **Tests**: 7/7 passing
- `_compute_fuzzy_accuracy()` added after `_fuzzy_cell_score()`
- Bag-of-cells matching with best-first greedy assignment
- Returns (precision, recall, F1) as fractions

### Task 1.1.3: Add fuzzy fields to ComparisonResult
- **Status**: complete
- **Agent**: implementer
- **Files modified**: `src/zotero_chunk_rag/feature_extraction/ground_truth.py`, `tests/test_feature_extraction/test_ground_truth.py`
- **Tests**: 3/3 passing
- `fuzzy_accuracy_pct`, `fuzzy_precision_pct`, `fuzzy_recall_pct` fields added to ComparisonResult
- `compare_extraction()` computes and populates fuzzy fields
- Fuzzy metric produces meaningful scores even when structural alignment fails
- Also fixed 2 pre-existing test failures (test_split_row_coverage_penalty, test_artifact_table) caused by Phase 0 cell_accuracy_pct default change

---
## Wave 1.1 Summary
- **Status**: complete
- **Tasks completed**: 3/3
- **Rounds**: 1

## Phase 2: Combination Engine Rewrite

### Task 2.1.1: Rewrite combine_hypotheses() with per-divider voting
- **Status**: complete
- **Agent**: implementer
- **Files modified**: `src/zotero_chunk_rag/feature_extraction/combination.py`, `tests/test_combination.py`
- **Tests**: 37/37 passing
- `NotImplementedError` stub replaced with per-divider voting algorithm
- `_scale_point()` helper added for confidence multiplier scaling
- `confidence_multipliers` parameter added to `combine_hypotheses()` signature
- `_combine_axis()` acceptance changed from Q1-confidence to median-method-count threshold
- Ruled line override: clusters with `provenance == "ruled_lines"` always accepted
- Consensus boundary confidence is mean of constituent points (not sum)
- 8 tests broken by Phase 0 now pass; 6 new test classes added (TestMethodCountRejection, TestConfidenceMultipliers, TestRuledLineOverride, TestScalePoint)
- `test_percentile_based_acceptance` renamed to `test_equal_method_agreement_all_pass`, assertion updated to 5 boundaries

### Task 2.1.2: Pass confidence multipliers from Pipeline
- **Status**: complete
- **Agent**: implementer
- **Files modified**: `src/zotero_chunk_rag/feature_extraction/pipeline.py`
- **Tests**: 26/26 integration tests passing
- `Pipeline.extract()` now passes `self._config.confidence_multipliers` to `combine_hypotheses()`

---
## Wave 2.1 Summary
- **Status**: complete
- **Tasks completed**: 2/2
- **Rounds**: 1

### Task 2.2.1: Update trace models for per-divider voting
- **Status**: complete
- **Agent**: implementer
- **Files modified**: `src/zotero_chunk_rag/feature_extraction/models.py`, `src/zotero_chunk_rag/feature_extraction/combination.py`, `tests/test_combination.py`
- **Tests**: 37/37 passing
- `ClusterRecord`: added `method_names: list[str]` and `acceptance_reason: str` fields
- `AxisTrace`: added `median_method_count: float` field
- `_combine_axis()` populates new fields when `collect_trace=True`
- `_make_passthrough_trace()` sets appropriate values for new fields
- 3 new trace tests: `test_trace_cluster_has_method_names`, `test_trace_has_median_method_count`, `test_acceptance_reason_values`

---
## Wave 2.2 Summary
- **Status**: complete
- **Tasks completed**: 1/1
- **Rounds**: 1

### Task 1.2.1: Update stress test to use fuzzy metrics
- **Status**: complete
- **Agent**: implementer
- **Files modified**: `src/zotero_chunk_rag/feature_extraction/debug_db.py`, `tests/stress_test_real_library.py`, `tests/test_feature_extraction/test_debug_db.py`
- **Tests**: 6/6 passing
- Added `fuzzy_accuracy_pct`, `fuzzy_precision_pct`, `fuzzy_recall_pct` columns to `ground_truth_diffs` schema
- Updated `write_ground_truth_diff()` to write fuzzy fields from ComparisonResult
- Changed `quality_score` in `method_results` to use `cmp.fuzzy_accuracy_pct` instead of `cmp.cell_accuracy_pct`
- Changed `final_score` lookup in `pipeline_runs` to use `fuzzy_accuracy_pct` from `ground_truth_diffs`
- Updated GT comparison report section to show fuzzy accuracy, precision, and recall
- Updated pipeline depth report combination-value analysis to use `fuzzy_accuracy_pct`
- Updated variant comparison to use `cmp.fuzzy_accuracy_pct`
- Added `TestExtendedSchema::test_ground_truth_diffs_has_fuzzy_columns` test

---
## Wave 1.2 Summary
- **Status**: complete
- **Tasks completed**: 1/1
- **Rounds**: 1

## Phase 3: LLM Prompt Method

### Task 3.1.1: Generate table PNGs and prompts
- **Status**: complete
- **Agent**: implementer
- **Files created**: `tests/llm_structure/__init__.py`, `tests/llm_structure/generate_prompts.py`
- **Tests**: 2/2 passing (test_script_importable, test_manifest_schema)
- Script generates cropped PNG + prompt for each GT table
- Resolves PDF paths via --corpus-json or --from-stress-test (Zotero library)
- find_table_bbox uses find_tables(), caption search, and word-bbox fallback
- Manifest JSON lists all generated tables with table_id, pdf_path, page_num, bbox

### Task 3.1.2: Prompt template
- **Status**: complete
- **Agent**: implementer
- **Files created**: `tests/llm_structure/prompt_template.md`
- **Tests**: 2/2 passing (test_template_exists, test_template_contains_json_example)
- Coordinate system: fractions of table bbox (0.0-1.0)
- Requests internal dividers only (not outer edges)
- JSON output format with position + confidence fields
- Includes worked 3-column, 4-row example

---
## Wave 3.1 Summary
- **Status**: complete
- **Tasks completed**: 2/2
- **Rounds**: 1

### Task 3.2.1: Parse LLM responses into BoundaryHypothesis objects
- **Status**: complete
- **Agent**: implementer
- **Files created**: `tests/llm_structure/parse_responses.py`
- **Tests**: 4/4 passing (test_valid_json_parsed, test_markdown_fenced_json, test_invalid_json_returns_none, test_confidence_mapping)
- Handles markdown code fences, extra text around JSON
- Validates structure: columns/rows arrays with position and confidence
- Converts fractional positions to absolute PDF coordinates
- Maps confidence labels: high=0.9, medium=0.6, low=0.3
- Invalid input returns None with error message

### Task 3.2.2: Inject LLM boundaries and evaluate against GT
- **Status**: complete
- **Agent**: implementer
- **Files created**: `tests/llm_structure/inject_and_evaluate.py`
- **Tests**: 1/1 passing (test_script_importable)
- Runs all 3 cell extraction methods (rawdict, word_assignment, pdfminer) against LLM boundaries
- Computes fuzzy_accuracy_pct via compare_extraction()
- Writes method_results rows to debug DB (llm_sonnet+rawdict, etc.)
- Prints summary table with per-table per-method accuracy

---
## Wave 3.2 Summary
- **Status**: complete
- **Tasks completed**: 2/2
- **Rounds**: 1

### Task 3.3.1: Comparison report generator
- **Status**: complete
- **Agent**: implementer
- **Files created**: `tests/llm_structure/compare_models.py`
- **Tests**: 1/1 passing (test_script_importable)
- Reads method_results from debug DB for LLM and pipeline entries
- Generates comparison_report.md with: per-table accuracy, LLM wins/losses, win rates, summary statistics
- Compares Sonnet, Haiku, pipeline best, and consensus accuracy

---
## Wave 3.3 Summary
- **Status**: complete
- **Tasks completed**: 1/1
- **Rounds**: 1

## Phase 4: Validation

### Task 4.1.1: Run stress test and verify targets
- **Status**: complete (targets NOT met)
- **Agent**: orchestrator (execution task)
- **Files modified**: None
- **Tests**: Stress test ran successfully (272 tests, 247 passed, 25 failed)
- **Acceptance criteria results**:
  1. **0 MAJOR failures**: FAILED -- 4 MAJOR failures
     - missing-figures (active-inference-tutorial): 1 figure caption with no extracted image
     - unmatched-captions (active-inference-tutorial): appendix captions A.1 (fig), A.1/A.2/A.3 (tables) unmatched
     - table-dimensions-sanity (roland-emg-filter): 1 degenerate 1x1 table
     - table-dimensions-sanity (fortune-impedance): 1 degenerate 1x1 table
  2. **Overall fuzzy GT accuracy >= 95%**: FAILED -- 8.4% (39 tables compared)
  3. **Consensus delta >= -5%**: FAILED -- avg delta is -53.6% (best single method 62.0% vs consensus 8.4%)
     - 37 of 39 tables show consensus worse than best single method
     - Worst deltas: -97.6% (DPYRZTFI_table_1), -93.5% (VP3NJ74M_table_4), -91.2% (Z9X4JVZ5_table_1)
  4. **DEFAULT config >= FAST and MINIMAL**: FAILED
     - DEFAULT: 7.2%, FAST: 7.7%, RULED: 7.2%, MINIMAL: 55.7%
     - MINIMAL (PyMuPDFLines only + rawdict) dramatically outperforms all multi-method configs
- **Root cause diagnosis**: The consensus combination engine is creating phantom boundaries that destroy table structure. When multiple methods contribute boundary hypotheses, the voting/merging produces boundaries that don't correspond to actual table dividers. MINIMAL config avoids this entirely by using only PyMuPDFLines boundaries without combination, achieving 55.7% accuracy. The per-divider voting rewrite (Phase 2) has not fixed the fundamental combination problem -- it may have made it worse by changing acceptance thresholds. The scoring/selection system in Pipeline.extract() is also selecting consensus grids over per-method grids that have higher accuracy.

### Task 4.1.2: Generate tuned weights and verify
- **Status**: complete (no regression from tuned weights, but targets still not met)
- **Agent**: orchestrator (execution task)
- **Files modified**: `tests/pipeline_weights.json` (generated by tune_weights.py)
- **Weight tuning results**:
  - pymupdf_lines: 1.000 (dominant winner, 16% win rate)
  - pymupdf_text: 0.526 (9% win rate)
  - ruled_lines: 0.283 (5% win rate)
  - single_point_hotspot: 0.162 (3% win rate)
  - camelot_hybrid: 0.158 (3% win rate)
  - global_cliff: 0.147 (2% win rate)
  - header_anchor: 0.055 (1% win rate)
  - All others (pdfplumber_text, pymupdf_lines_strict, camelot_lattice, consensus, per_row_cliff, gap_span_hotspot): 0.100 (floor, 0% win rate)
- **Re-run stress test results**: Identical to pre-tuning (8.4% accuracy, 4 MAJOR failures, same variant comparison). Tuned weights did not regress but also did not improve -- the problem is structural (combination engine), not weight-related.
- **Key finding**: The consensus method itself has 0% win rate -- it never produces the best result for any table. Yet Pipeline.extract() appears to be selecting consensus-derived grids over superior per-method grids. This is the core bug.

---
## Wave 4.1 Summary
- **Status**: complete (targets NOT met -- requires iteration on combination engine)
- **Tasks completed**: 2/2
- **Rounds**: 1
- **Critical findings**:
  - Consensus combination destroys accuracy (8.4% vs 62.0% best single method)
  - MINIMAL config (no combination) achieves 55.7% -- 7.7x better than DEFAULT
  - The scoring system is selecting consensus grids over better per-method grids
  - Weight tuning has no effect because the problem is structural, not weight-related
  - To meet targets, Pipeline.extract() must prefer per-method grids when they score better than consensus

## Phase 5: Legacy Reference Review

### Task 5.1.1: Search and remove all stale references
- **Status**: complete
- **Agent**: implementer
- **Files modified**:
  - `src/zotero_chunk_rag/feature_extraction/ground_truth.py` -- removed dead `field` import, replaced historical-provenance comment
  - `tests/test_feature_extraction/test_ground_truth.py` -- replaced historical-provenance docstring, tightened 3 weak assertions (test_headers_included, test_compare_extraction_populates_fuzzy, test_fuzzy_not_vacuous_when_structural_fails)
  - `tests/test_combination.py` -- tightened 3 weak assertions (test_multi_hypothesis_trace_structure, test_trace_cluster_has_method_names, test_trace_has_median_method_count)
  - `tests/diagnose_combination.py` -- renamed "Column count grouping" label to "Methods by column count"
  - `CLAUDE.md` -- added combination algorithm section, updated combination tracing to describe median method count acceptance and ClusterRecord fields
  - `MEMORY.md` -- added combination algorithm design decisions, updated current state
  - `spec/progress.md` -- updated Phase 1 entries that referenced superseded algorithms
- **Tests**: 397/397 passing
- **Verification**:
  - `_select_best_column_group`: 0 matches in src/ and tests/
  - `_group_confidence`: 0 matches in src/ and tests/
  - `column.count.group` (case-insensitive): 0 matches in src/ and tests/
  - `normalize_method_confidence`: 0 matches in src/ and tests/
  - `else 100.0` in ground_truth.py: only in `structural_coverage_pct` (correct default)
  - No dead imports in combination.py or ground_truth.py
  - CLAUDE.md accurately describes per-divider voting with median method count acceptance
  - All existing doc tests (test_claude_md_no_table_extraction_refs, test_claude_md_no_figure_extraction_ref) pass

---
## Wave 5.1 Summary
- **Status**: complete
- **Tasks completed**: 1/1
- **Rounds**: 1
