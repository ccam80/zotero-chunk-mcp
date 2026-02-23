# Pipeline Accuracy & Combination Fix — Implementation Plan

## Context

Deep exploration of the debug database and source code revealed three critical issues
with the extraction pipeline:

1. **Vacuous accuracy metric**: `compare_extraction()` reports 100% on 31/41 tables
   by comparing 0 cells. When column alignment fails (headers don't match),
   `comparable_cells = 0` and accuracy defaults to `100.0`. The metric is useless
   for grid selection or evaluation.

2. **Destructive consensus combination**: The boundary combination engine groups
   methods by column count, then merges all boundary points in the winning group.
   When methods in the same group disagree on exact positions, this creates phantom
   columns — producing 3-8x the correct column count. 10 tables drop from 100% to
   0% accuracy because of consensus. The pipeline architecture already scores
   per-method grids alongside consensus (Tasks 1.1.1-1.1.2 from the previous plan
   are complete), but the scoring can't distinguish grids effectively because the
   accuracy metric is vacuous.

3. **No LLM structure method**: Phase 4 of the original plan built a Haiku vision
   QA layer (verification), but no LLM-based method was ever implemented as a
   competing structure detection approach. Vision models excel at table structure
   recognition — this capability is missing from the pipeline.

### Current state

| Metric | Value |
|--------|-------|
| Pipeline GT accuracy (vacuous metric) | 76.2% |
| Best single-method GT accuracy (vacuous metric) | 100.0% |
| Tables degraded by consensus | 10 (8 at 0%, 2 at 8-17%) |
| MAJOR stress test failures | 18 |
| Tables with vacuous 100% (0 comparable cells) | 31/41 |

The pipeline already scores per-method grids alongside consensus grids (`Pipeline.extract()`
runs cell extraction for each structure method individually, then also for consensus).
The problem is that: (a) the accuracy metric can't distinguish real quality, so scoring
falls back to heuristics like fill_rate which don't always pick the right grid; and
(b) consensus boundaries are destructive even when they're just one candidate among many.

### Completed infrastructure

From the previous implementation pass:

- `CellGrid.structure_method` field with provenance tracking (complete)
- `Pipeline.extract()` scores all grids: per-method + consensus (complete)
- `combine_hypotheses()` trace mode with `CombinationTrace` (complete)
- `tests/diagnose_combination.py` + `_combination_diagnosis.md` (diagnostic analysis)
- Agent QA workspace with 42 table PNGs, extraction JSONs, manifest
- `tune_weights.py` infrastructure (data-driven weight computation, never run)
- `confidence_multipliers` in PipelineConfig (loaded from JSON, but combination.py
  never reads them — dead infrastructure)

## Goals

- **Honest accuracy metric**: no vacuous 100% scores; all GT comparisons produce
  meaningful accuracy reflecting actual cell-level correctness
- **Pipeline GT accuracy >= 95%** (from 76.2% on the vacuous metric)
- **Consensus never degrades**: pipeline accuracy >= best single-method accuracy
  on every GT table (delta >= -5%)
- **DEFAULT config matches or beats FAST and MINIMAL**
- **LLM vision boundaries**: prompt-based structure detection using Sonnet and Haiku,
  evaluated against other methods — if LLM beats the pipeline, it replaces it
- **Data-driven confidence multipliers** generated from stress test results and
  actually used by the combination engine

## Non-Goals

- API-integrated LLM method (no runtime calls from the pipeline; prompt-based only)
- Figure-data-table overlap detection fix
- Adding new non-LLM structure or cell extraction methods
- Changing the post-processor chain
- Production deployment of agent QA

## Verification

- **Phase 0**: `combination.py` no longer contains `_select_best_column_group` or
  `_group_confidence`; ground_truth.py no longer contains `else 100.0` default;
  `combine_hypotheses()` raises `NotImplementedError` for multi-hypothesis case
- **Phase 1**: All GT tables have meaningful `fuzzy_accuracy_pct`; both precision
  and recall reported; no vacuous 100% scores
- **Phase 2**: `combine_hypotheses()` works with per-divider voting; combination
  delta >= -5% on all tables; confidence multipliers actually used
- **Phase 3**: LLM boundaries stored in debug DB; Sonnet vs Haiku comparison report
  generated with per-table fuzzy accuracy
- **Phase 4**: 0 MAJOR stress test failures; overall fuzzy accuracy meets target;
  `pipeline_weights.json` generated from data
- **Phase 5**: grep for removed function names returns 0 matches repo-wide

## Dependency Graph

```
Phase 0 (Dead Code Removal)         ─── runs first, alone
│
├──→ Phase 1 Wave 1.1 (Fuzzy Metric code)   ─── parallel after 0
├──→ Phase 2 (Combination Rewrite)           ─── parallel after 0
│                                                         │
└──→ Phase 1 Wave 1.2 (Stress Test Integration)  ─── after Phase 2
│
├──→ Phase 3 (LLM Prompt Method)             ─── after 1 + 2 (independent of 4)
├──→ Phase 4 (Validation)                    ─── after 1 + 2
│
Phase 5 (Legacy Reference Review)            ─── after 4
```

Phase 0 stubs `combine_hypotheses()` for multi-hypothesis case, breaking the pipeline.
Phase 1 Wave 1.1 (fuzzy metric functions) can run in parallel with Phase 2 since it's
pure computation in `ground_truth.py`. Phase 1 Wave 1.2 (stress test integration) needs
a working pipeline, so it waits for Phase 2 to restore `combine_hypotheses()`. Phase 3
needs both the fuzzy metric (Phase 1) and working combination (Phase 2) to evaluate LLM
boundaries meaningfully, but is independent of Phase 4. Phase 4 (validation) runs the
stress test gate after Phases 1+2; it does not need Phase 3's LLM results. Phase 5 is
the final audit.

## Spec-Level Design Decisions

Decisions made during spec authoring that override or refine the original plan:

- **Numeric cell scoring**: `_fuzzy_cell_score()` returns 0.0 for ANY mismatch where
  either cell is numeric. No partial credit for numeric errors. Text mismatches get
  LCS partial credit. Rationale: "0.047" vs ".047" is extraction failure, not a
  minor variation.
- **Best-first greedy assignment**: The fuzzy accuracy matching sorts all
  `(ext_idx, gt_idx, score)` triples by score descending before greedy assignment.
  This approximates optimal matching without Hungarian algorithm complexity.
- **No reevaluate_accuracy.py script**: Removed Task 1.2.2. The stress test itself
  computes the new metrics directly. Avoids unnecessary tooling.
- **No normalize_method_confidence toggle**: Removed Task 2.2.2. Normalization adds
  complexity without demonstrated need. If chatty-method domination becomes a
  problem, it can be added later.
- **Confidence multipliers via parameter**: `combine_hypotheses()` gets a new
  `confidence_multipliers: dict[str, float] | None = None` parameter. Pipeline
  passes `self._config.confidence_multipliers` at the call site. Clean separation
  of concerns — combination doesn't know about PipelineConfig.
- **Ruled line override**: `provenance == "ruled_lines"` only. No other methods
  qualify for unconditional acceptance.
- **Consensus boundary confidence = mean**: Each accepted consensus boundary's
  confidence is the mean (not sum) of its constituent points' scaled confidences.
  Prevents methods with many boundary points from dominating through volume.

---

## Phase 0: Dead Code Removal
**Depends on**: (none — runs first)

Remove code that will be replaced by this plan. This breaks the pipeline
(combination.py raises NotImplementedError for multi-hypothesis case) — Phase 2
builds the replacement. Tests that call combine_hypotheses() with 2+ hypotheses
will fail with NotImplementedError until Phase 2 restores them.

### Wave 0.1: Remove obsolete combination and metric code

| Task | Description | Complexity | Key Files |
|------|-------------|------------|-----------|
| 0.1.1 | Remove `_select_best_column_group()` and `_group_confidence()` from `combination.py`. Stub the multi-hypothesis path in `combine_hypotheses()` with `NotImplementedError("awaiting per-divider voting rewrite")`. Change the vacuous `else 100.0` default in `ground_truth.py` to `else 0.0`. Delete `TestColumnGrouping` tests from `test_combination.py`. 8 tests that call combine_hypotheses() with 2+ hypotheses will fail with NotImplementedError (expected — Phase 2 restores them). | M | `combination.py`, `ground_truth.py`, `tests/test_combination.py` |

---

## Phase 1: Accuracy Metric Rewrite
**Depends on**: Phase 0
**Wave 1.1 parallel with**: Phase 2
**Wave 1.2 depends on**: Phase 2

The fix adds an alignment-free symmetric fuzzy accuracy metric using bag-of-cells
matching with best-first greedy assignment. Numeric cells are scored strictly
(exact match or 0.0). Text cells get LCS partial credit.

### Wave 1.1: Symmetric fuzzy cell accuracy

| Task | Description | Complexity | Key Files |
|------|-------------|------------|-----------|
| 1.1.1 | Implement `_fuzzy_cell_score(a, b) -> float` in `ground_truth.py`. After normalization: exact match -> 1.0; both empty -> 1.0; one empty/one not -> 0.0; either cell numeric and not matching -> 0.0; text -> LCS ratio. Also add `_is_numeric_cell()` helper. | M | `ground_truth.py` |
| 1.1.2 | Implement `_compute_fuzzy_accuracy(gt_headers, gt_rows, ext_headers, ext_rows) -> (precision, recall, f1)`. Headers included in cell bags. Best-first greedy assignment (sort all score triples descending, assign greedily). | L | `ground_truth.py` |
| 1.1.3 | Add `fuzzy_accuracy_pct`, `fuzzy_precision_pct`, `fuzzy_recall_pct` to `ComparisonResult`. Compute in `compare_extraction()`. Keep existing structural analysis unchanged. | M | `ground_truth.py` |

### Wave 1.2: Stress test integration

| Task | Description | Complexity | Key Files |
|------|-------------|------------|-----------|
| 1.2.1 | Update stress test to use `fuzzy_accuracy_pct` as primary `quality_score`. Add fuzzy columns to `ground_truth_diffs` schema. Update GT comparison report and pipeline depth report. | M | `tests/stress_test_real_library.py`, `debug_db.py` |

---

## Phase 2: Combination Engine Rewrite
**Depends on**: Phase 0
**Parallel with**: Phase 1 Wave 1.1
**Must complete before**: Phase 1 Wave 1.2

Replace column-count-based grouping with per-divider confidence voting. All boundary
points from all methods are pooled and voted on independently. Acceptance based on
median method_count. Ruled line override for physical boundaries.

### Design

**Per-divider voting algorithm:**

1. **Collect** all boundary points from all methods (no grouping by column count).
2. **Scale** each point's confidence by its method's multiplier from the
   `confidence_multipliers` parameter (passed by Pipeline from PipelineConfig).
3. **Cluster by position**: expand narrow ranges, merge overlapping (existing logic).
4. **Score each cluster**: count distinct methods (method_count), mean weighted confidence.
5. **Accept/reject**: accept if `method_count >= median(all method_counts)`.
   Ruled line override: accept if any point has `provenance == "ruled_lines"`.

### Wave 2.1: Core per-divider voting

| Task | Description | Complexity | Key Files |
|------|-------------|------------|-----------|
| 2.1.1 | Rewrite `combine_hypotheses()` with per-divider voting. Add `confidence_multipliers: dict[str, float] | None = None` parameter. Replace NotImplementedError stub. New acceptance: median method_count threshold + ruled line override. Add `_scale_point()` helper. | L | `combination.py` |
| 2.1.2 | Pass `self._config.confidence_multipliers` from `Pipeline.extract()` to `combine_hypotheses()`. | S | `pipeline.py` |

### Wave 2.2: Trace infrastructure

| Task | Description | Complexity | Key Files |
|------|-------------|------------|-----------|
| 2.2.1 | Add `method_names: list[str]` and `acceptance_reason: str` to `ClusterRecord`. Add `median_method_count: float` to `AxisTrace`. Update combination trace output. | M | `models.py`, `combination.py` |

---

## Phase 3: LLM Prompt Method
**Depends on**: Phase 1 + Phase 2

Offline evaluation workflow: generate prompts, user runs through vision models,
parse responses, inject into debug DB, compare against pipeline methods.

### Wave 3.1: Prompt generation

| Task | Description | Complexity | Key Files |
|------|-------------|------------|-----------|
| 3.1.1 | Create `tests/llm_structure/generate_prompts.py`: render GT table PNGs, generate prompts, write manifest. | M | `tests/llm_structure/generate_prompts.py` |
| 3.1.2 | Write prompt template requesting JSON with fractional divider positions and confidence labels. | S | `tests/llm_structure/prompt_template.md` |

### Wave 3.2: Response parsing + injection

| Task | Description | Complexity | Key Files |
|------|-------------|------------|-----------|
| 3.2.1 | Create `tests/llm_structure/parse_responses.py`: parse LLM JSON -> BoundaryHypothesis. Handle markdown fences, validate structure. | M | `tests/llm_structure/parse_responses.py` |
| 3.2.2 | Create `tests/llm_structure/inject_and_evaluate.py`: run cell extraction against LLM boundaries, compute fuzzy accuracy, write to debug DB. | M | `tests/llm_structure/inject_and_evaluate.py` |

### Wave 3.3: Model comparison

| Task | Description | Complexity | Key Files |
|------|-------------|------------|-----------|
| 3.3.1 | Create `tests/llm_structure/compare_models.py`: per-table Sonnet vs Haiku vs pipeline accuracy report. | M | `tests/llm_structure/compare_models.py` |

---

## Phase 4: Validation
**Depends on**: Phase 1 + Phase 2 + Phase 3

### Wave 4.1: Full stress test

| Task | Description | Complexity | Key Files |
|------|-------------|------------|-----------|
| 4.1.1 | Run stress test. Verify: 0 MAJOR failures, fuzzy GT accuracy >= 95%, consensus delta >= -5%, DEFAULT >= FAST/MINIMAL. | M | `stress_test_real_library.py` |
| 4.1.2 | Run `tune_weights.py` to generate `pipeline_weights.json` from fuzzy win rates. Re-run stress test to verify no regression. | S | `tune_weights.py`, `pipeline_weights.json` |

---

## Phase 5: Legacy Reference Review
**Depends on**: Phase 4

### Wave 5.1: Full legacy audit

| Task | Description | Complexity | Key Files |
|------|-------------|------------|-----------|
| 5.1.1 | Search and remove all stale references: `_select_best_column_group`, `_group_confidence`, `else 100.0`, column count grouping descriptions, `normalize_method_confidence`, old spec files. Update CLAUDE.md and MEMORY.md. | M | (repo-wide) |
