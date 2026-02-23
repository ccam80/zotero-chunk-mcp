# zotero-chunk-rag — Project Rules

## Hard Rules

### Never Optimise for "Minimal Refactoring" or "Minimal API Change"

When designing a fix, pick the approach that solves the problem best. Do not
choose a worse approach because it touches fewer files, preserves an existing
function signature, or "minimises refactoring". If the right fix requires
restructuring, restructure. Code exists to serve correctness, not to avoid diffs.

### No Hard-Coded Thresholds

Every numeric threshold in the extraction pipeline MUST be adaptive — computed
from the actual data on the current page or paper. Examples:

- Row clustering tolerance: derive from the actual line spacing on the page, not
  a fixed 5pt constant.
- Column gap detection: derive from the gap distribution of the words in the
  table, not a fixed ratio or minimum.
- Fill rate triggers: derive from the table's own statistics relative to other
  tables on the same page.
- Merge triggers (empty col0 %, sparse row %): derive from the table's structure,
  not global constants.

If you find yourself writing a literal number as a threshold (e.g., `if ratio > 2.0`,
`if fill < 0.55`, `if len(rows) < 6`), STOP. Either:

1. Compute the threshold from the data (preferred), or
2. If you genuinely cannot avoid a fixed number, **present it to the user for
   approval** with at least two alternatives and an explanation of why adaptive
   computation isn't feasible.

This applies to ALL extraction code: `pdf_processor.py`, `feature_extraction/methods/`,
`feature_extraction/postprocessors/`, `_gap_fill.py`, `section_classifier.py`, and any
new modules.

### Tables in Academic Papers Are Not "Structurally Sparse"

Almost no tables in academic papers have genuinely sparse data. When extracted
tables show low fill rates (many empty cells), the cause is almost always an
extraction error:

- **Over-detected columns**: Gap threshold too low → one real column becomes 3-4
  columns, most of which are empty.
- **Inline headers**: Sub-group headings that span the full table width (e.g.
  "Panel A: Males") appear as rows with content only in column 0.
- **Continuation rows**: Multi-line cell content split across rows, where the
  continuation row has content only in the column being continued.

Do NOT report low fill rates as "structural sparsity", "inherent to the PDF", or
"the table genuinely has many empty cells". Investigate the actual cause. If a
table has < 70% fill, something is wrong with the extraction.

### Never Dismiss Problems as "Inherent to the PDF" or "PyMuPDF Limitation"

PDFs are not deficient — if they were, human readers wouldn't use them. PyMuPDF's
high-level functions (`find_tables()`, `get_text()`) do have limitations, but PyMuPDF
also provides low-level tools (`get_text("words")`, `get_text("dict")`, `get_text("rawdict")`,
`get_image_info()`, `get_drawings()`, page geometry, font metadata) that can work
around those limitations.

When a `find_tables()` result is wrong:
- Re-extract from word positions (`page.get_text("words")`)
- Use font metadata (`get_text("dict")`) to detect headers, footnotes, captions
- Use drawing/line data (`get_drawings()`) to find actual table rules
- Use block structure to detect boundaries

The correct response to "find_tables() merges two tables" is "detect the merge and
split using word positions and caption detection", not "this is a PyMuPDF limitation".

### Test Integrity

Test conditions and assertions are NEVER modified to fit the PDF corpus, perceived
limitations of extraction methods, or to make a failing test pass. If a test fails,
the code is wrong — fix the code, not the test.

Tests assert 100% functionality or are regarded as a complete failure. There is no
"80% correct is good enough." If a table has 10 columns, the extraction must find
10 columns. If a cell contains "0.047", the extraction must return "0.047".

Tests on synthetic data (programmatically generated PDFs, mock objects) are syntax
checks only. They verify that functions accept the right arguments and return the
right types. They tell you NOTHING about whether extraction works on real papers.
The only data that matters is real-paper performance measured by the stress test.

### Extraction Time Budget

Extra extraction time is acceptable. The pipeline should try every available method
and pick the best result, not skip methods to save time. Correctness always beats
speed. If running all methods takes 30 seconds per table instead of 3 seconds, that
is fine.

### Performance Testing

**The stress test is the ground truth.** Synthetic unit tests validate individual
functions but tell you nothing about whether the pipeline actually works on real
papers.

#### How to run it

```bash
"./.venv/Scripts/python.exe" tests/stress_test_real_library.py
```

This takes ~2-5 minutes. It:
1. Loads 10 specific papers from the user's live Zotero library (corpus defined
   in `CORPUS` at top of file)
2. Extracts each through the full pipeline (text, tables, figures, sections)
3. Indexes into a temp ChromaDB with local embeddings
4. Runs ~290 assertions across extraction quality, search accuracy, table/figure
   search, metadata filtering, and context expansion
5. Produces `STRESS_TEST_REPORT.md` and `_stress_test_debug.db`

#### The debug database

`_stress_test_debug.db` is a SQLite database containing every extracted artifact
from the stress test run.

**Core tables** (written by the main extraction pipeline):

| Table | Contents |
|-------|----------|
| `papers` | Per-paper: pages, chunks, grade, completeness fields, full markdown |
| `extracted_tables` | Every table: caption, headers_json, rows_json, fill_rate, bbox, artifact_type, rendered markdown |
| `extracted_figures` | Every figure: caption, bbox, image_path, reference_context |
| `sections` | Every section span: label, heading, char offsets, confidence |
| `chunks` | Every text chunk: section, page, text, char offsets |
| `pages` | Per-page markdown |
| `test_results` | Every assertion: test_name, paper, passed, detail, severity |
| `run_metadata` | Timestamps, counts, timings |

**Extended tables** (written by `_test_pipeline_methods()` for per-method analysis):

| Table | Contents |
|-------|----------|
| `method_results` | Per-table per-method: `table_id`, `method_name` (format: `structure+cell`), `boundary_hypotheses_json`, `cell_grid_json`, `quality_score` (GT accuracy or fill rate), `execution_time_ms` |
| `pipeline_runs` | Per-table pipeline outcome: `table_id`, `pipeline_config_json`, `winning_method` (format: `structure:cell`), `final_score` (GT accuracy) |
| `ground_truth_diffs` | Per-table GT comparison: `table_id`, `run_id`, `diff_json` (full `ComparisonResult`), `cell_accuracy_pct`, `num_splits`, `num_merges`, `num_cell_diffs`, `gt_shape`, `ext_shape` |

**Use this database to audit extraction quality.** Example queries:

```sql
-- Tables with low fill rates (likely broken extraction)
SELECT short_name, caption, fill_rate, num_rows, num_cols
FROM extracted_tables JOIN papers USING(item_key)
WHERE fill_rate < 0.5 AND artifact_type IS NULL;

-- Find decimal displacement (T1) — cells starting with "."
SELECT short_name, caption, rows_json
FROM extracted_tables JOIN papers USING(item_key)
WHERE rows_json LIKE '%".%' AND artifact_type IS NULL;

-- Papers with unmatched table captions (extraction missed a table)
SELECT short_name, unmatched_table_captions
FROM papers WHERE unmatched_table_captions != '[]';

-- All MAJOR failures
SELECT test_name, paper, detail FROM test_results
WHERE passed = 0 AND severity = 'MAJOR';
```

**Per-method analysis queries** (require extended tables):

```sql
-- Which structure method wins most often (highest GT accuracy)?
SELECT
  SUBSTR(method_name, 1, INSTR(method_name, '+') - 1) AS structure,
  COUNT(*) AS wins
FROM method_results mr
WHERE quality_score = (
  SELECT MAX(quality_score) FROM method_results
  WHERE table_id = mr.table_id AND quality_score IS NOT NULL
)
GROUP BY structure ORDER BY wins DESC;

-- Per-table: best single method vs pipeline consensus accuracy
SELECT
  mr.table_id,
  MAX(mr.quality_score) AS best_single,
  gtd.cell_accuracy_pct AS pipeline_acc,
  gtd.cell_accuracy_pct - MAX(mr.quality_score) AS delta
FROM method_results mr
LEFT JOIN ground_truth_diffs gtd ON mr.table_id = gtd.table_id
WHERE mr.quality_score IS NOT NULL
GROUP BY mr.table_id
ORDER BY delta;

-- Tables where combination HURTS (best method > pipeline)
SELECT mr.table_id, MAX(mr.quality_score) AS best, gtd.cell_accuracy_pct AS pipeline
FROM method_results mr
JOIN ground_truth_diffs gtd ON mr.table_id = gtd.table_id
WHERE mr.quality_score IS NOT NULL
GROUP BY mr.table_id
HAVING MAX(mr.quality_score) > gtd.cell_accuracy_pct;

-- All methods tried for a specific table, ranked by quality
SELECT method_name, quality_score
FROM method_results
WHERE table_id = '<TABLE_ID>' AND quality_score IS NOT NULL
ORDER BY quality_score DESC;

-- Pipeline winning method distribution
SELECT winning_method, COUNT(*) AS tables, AVG(final_score) AS avg_accuracy
FROM pipeline_runs GROUP BY winning_method ORDER BY tables DESC;

-- GT comparison summary: worst tables
SELECT table_id, cell_accuracy_pct, num_splits, num_merges, num_cell_diffs
FROM ground_truth_diffs ORDER BY cell_accuracy_pct ASC LIMIT 20;
```

#### When to run it

Run the stress test after any change to the extraction pipeline. A change that
passes unit tests but regresses the stress test is a bad change. The stress test
verdict (MAJOR failures = unreliable, minor = rough edges, all pass = reliable)
is the acceptance criterion.

#### Severity rules

- **MAJOR**: Orphan tables/figures (extraction missed something the paper contains),
  search failures (researcher can't find what's in the paper), data corruption
  (table values wrong enough to mislead).
- **MINOR**: Section detection misses, abstract detection misses, chunk count
  deviations. Annoying but won't cause a researcher to reach wrong conclusions.

## Architecture Notes

### Key files

| File | Role |
|------|------|
| `src/zotero_chunk_rag/pdf_processor.py` | Document extraction entry point, prose tables, cross-page coordination, stats/completeness |
| `src/zotero_chunk_rag/feature_extraction/pipeline.py` | Pipeline orchestrator: page-level detection, per-table multi-method extraction, scoring/selection |
| `src/zotero_chunk_rag/feature_extraction/methods/` | Structure detection methods (pymupdf, ruled lines, camelot, pdfplumber, hotspot, cliff, header anchor) and cell extraction methods (rawdict, words, pdfminer) |
| `src/zotero_chunk_rag/feature_extraction/postprocessors/` | Post-processors (caption strip, header detection, continuation merge, inline headers, footnotes, cell cleaning) |
| `src/zotero_chunk_rag/feature_extraction/models.py` | Pipeline data models (BoundaryHypothesis, CellGrid, ExtractionResult, TableContext, PipelineConfig) |
| `src/zotero_chunk_rag/feature_extraction/scoring.py` | Quality scoring framework for grid selection |
| `src/zotero_chunk_rag/feature_extraction/combination.py` | Boundary combination engine |
| `src/zotero_chunk_rag/feature_extraction/captions.py` | Unified caption detection (table + figure) |
| `src/zotero_chunk_rag/_gap_fill.py` | Post-extraction recovery pass for orphan captions |
| `src/zotero_chunk_rag/section_classifier.py` | Section heading classification |
| `src/zotero_chunk_rag/models.py` | Dataclasses: ExtractedTable, ExtractedFigure, SectionSpan, etc. |
| `src/zotero_chunk_rag/_reference_matcher.py` | Maps figures/tables to body-text chunks that cite them |
| `tests/stress_test_real_library.py` | 10-paper stress test (run directly, not via pytest) |
| `tests/tune_weights.py` | Data-driven weight tuning from stress test results |
| `tests/pipeline_weights.json` | Confidence multipliers for pipeline methods |
| `spec/pipeline_operators_guide.md` | Operator's guide: debug DB, comparison, scoring, weight tuning, diagnostic workflows, SQL cookbook |

### Architecture overview

The extraction pipeline uses a multi-method approach:

1. **Page-level detection** (`Pipeline.extract_page()`): finds table bboxes via
   `find_tables()` (3 strategies with dedup), detects figures via unified captions,
   matches captions to tables, classifies figure-data-table overlaps.

2. **Per-table extraction** (`Pipeline.extract()`): runs multiple structure detection
   methods in parallel (pymupdf, ruled lines, camelot, pdfplumber, hotspot, cliff,
   header anchor), combines boundary hypotheses, extracts cell text via multiple
   methods (rawdict, word assignment, pdfminer), scores/selects best grid, applies
   post-processors in canonical order.

3. **Cross-page coordination** (in `pdf_processor.py`): gap fill for orphan captions,
   heading/continuation caption assignment, artifact tagging, completeness grading.

4. **Named configs**: `DEFAULT_CONFIG` (all methods), `FAST_CONFIG` (subset),
   `RULED_CONFIG` (boosted ruled-line weight), `MINIMAL_CONFIG` (baseline).

### Ground truth comparison framework

`feature_extraction/ground_truth.py` provides `compare_extraction()` — the core
comparison function that diffs an extraction attempt against verified ground truth.

**Table IDs**: Generated by `make_table_id(paper_key, caption, page_num, index)`:
- Captioned: `{paper_key}_table_{N}` (e.g., `5SIZVS65_table_1`)
- Continuation: `{paper_key}_table_{N}_p{page}` (e.g., `SCPXVBLY_table_1_p16`)
- Orphan: `{paper_key}_orphan_p{page}_t{index}`

**ComparisonResult fields**:

| Field | Meaning |
|-------|---------|
| `gt_shape`, `ext_shape` | (rows, cols) of ground truth vs extraction |
| `matched_columns` | List of (gt_col, ext_col) index pairs aligned by header text |
| `extra_columns` | Extraction columns with no GT match (over-detection) |
| `missing_columns` | GT columns not found in extraction (under-detection) |
| `column_splits` | One GT column split into multiple extraction columns |
| `column_merges` | Multiple GT columns merged into one extraction column |
| `matched_rows`, `extra_rows`, `missing_rows` | Same as columns but for rows |
| `row_splits`, `row_merges` | Row-level structural mismatches |
| `cell_diffs` | Individual cell mismatches (row, col, expected, actual) |
| `cell_accuracy_pct` | Percentage of comparable cells that match (0--100) |
| `structural_coverage_pct` | Fraction of GT cells that were comparable |
| `header_diffs` | Header-level cell mismatches |
| `footnote_match` | Whether extracted footnotes match GT footnotes |

**Column alignment algorithm** (3-pass):
1. Exact match on normalized header text
2. LCS (longest common substring) fallback for ≥80% similarity
3. Split/merge detection: concatenation of adjacent headers
4. Positional matching for empty-string headers

**Row alignment**: Sequential walk with split/merge detection (up to 3-row spans)
and skip-ahead for spurious extra rows.

**Cell normalization**: Whitespace collapse, dash/hyphen unification
(unicode minus, en-dash, em-dash → ASCII hyphen), ligature expansion (ff, fi, fl, ffi, ffl).

### Scoring and grid selection

`feature_extraction/scoring.py` uses **rank-based selection**: each grid is ranked
across multiple quality metrics, ranks are summed, and the lowest total rank wins.
No absolute weights to calibrate.

**Metrics** (4 built-in, optional GT accuracy):

| Metric | Direction | Meaning |
|--------|-----------|---------|
| `fill_rate` | Higher = better | Fraction of non-empty cells |
| `decimal_displacement_count` | Lower = better | Cells matching `^\.\d+` (leading dot without zero) |
| `garbled_text_score` | Lower = better | Fraction of cells with avg word length > 25 |
| `numeric_coherence` | Higher = better | Fraction of numeric columns that are all-numeric or all-text |
| GT accuracy (optional) | Higher = better | Cell accuracy vs ground truth when `ground_truth_fn` is provided |

**Grid identification**: Each grid has a composite key `structure_method:cell_method`
(e.g., `single_point_hotspot:rawdict`, `consensus:word_assignment`).

### Pipeline configurations

**Named configs** (defined in `pipeline.py`):

| Config | Structure Methods | Cell Methods | Post-Processors | Notes |
|--------|------------------|-------------|-----------------|-------|
| `DEFAULT_CONFIG` | All 13 | All 3 | All 7 | Full pipeline, activation rules for camelot/cliff |
| `FAST_CONFIG` | PyMuPDFLines, GapSpanHotspot | Rawdict, WordAssignment | All 7 | Speed-focused |
| `RULED_CONFIG` | All 13 | All 3 | All 7 | Boosted `ruled_lines` multiplier (3.0×) |
| `MINIMAL_CONFIG` | PyMuPDFLines only | Rawdict only | AbsorbedCaption + CellCleaning | Baseline |

**Activation rules** gate method execution:
- `camelot_lattice`, `camelot_hybrid`: Only run when `has_ruled_lines(ctx)` is True
- `global_cliff`, `per_row_cliff`: Only run when `has_ruled_lines(ctx)` is False

**Confidence multipliers** (`PipelineConfig.confidence_multipliers`): Scale boundary
confidence during combination. Higher multiplier → more influence on consensus.
Loaded from `tests/pipeline_weights.json` at `Pipeline.__init__()`.

### Weight tuning workflow

1. **Run the stress test** to generate `_stress_test_debug.db`
2. **Run weight tuning** to compute win rates and generate multipliers:

```bash
"./.venv/Scripts/python.exe" tests/tune_weights.py
```

3. **Output**: `tests/pipeline_weights.json` containing:
```json
{
  "confidence_multipliers": {
    "single_point_hotspot": 1.0,
    "gap_span_hotspot": 0.5,
    ...
  }
}
```

**How it works**: For each table in `method_results`, the structure method whose
boundaries produced the highest GT accuracy gets a "win". Win rate = wins /
participation count. The best method gets multiplier 1.0; others are proportional.
Zero-win methods get a floor of 0.1.

**Pipeline reads this at init**: `Pipeline.__init__()` checks for the weights
file and merges its multipliers with the config's defaults (file values override).

### Combination algorithm

`combine_hypotheses()` uses per-divider voting with median method count acceptance:

1. **Confidence scaling**: Each boundary point's confidence is multiplied by
   its method's multiplier (from `pipeline_weights.json`).
2. **Point expansion**: Narrow boundary ranges (span < `spatial_precision`) are
   expanded symmetrically around their midpoint. `spatial_precision` is derived
   adaptively: ruled line thickness > median word gap > median word height.
3. **Overlap merge**: Expanded points are sorted by position and merged into
   clusters where ranges overlap.
4. **Acceptance**: Compute each cluster's distinct method count. The acceptance
   threshold is the median of all clusters' method counts. Clusters meeting or
   exceeding this threshold are accepted. Ruled line boundaries (`provenance ==
   "ruled_lines"`) are unconditionally accepted regardless of method count.
5. **Consensus confidence**: Each accepted boundary's confidence is the mean of
   its constituent points' scaled confidences.

Single-hypothesis input is passed through unchanged. Empty input returns empty boundaries.

### Combination tracing

`combine_hypotheses(hypotheses, ctx, trace=True)` returns a
`(BoundaryHypothesis, CombinationTrace)` tuple for diagnostics.

**CombinationTrace** contains:
- `col_trace` / `row_trace` (`AxisTrace`): Per-axis combination details
- `spatial_precision`: Adaptive merge tolerance (derived from ruled line thickness,
  median word gap, or median word height)
- `source_methods`: List of structure methods that contributed hypotheses

**AxisTrace** contains:
- `input_points`: All `BoundaryPoint`s from all methods
- `expansions`: How each point was expanded (narrow → widened, wide → unchanged)
- `clusters`: `ClusterRecord` objects with `method_names`, `acceptance_reason`
  (`"above_threshold"`, `"ruled_line_override"`, `"rejected"`), and `distinct_methods`
- `acceptance_threshold`: Median method count used as the acceptance cutoff
- `median_method_count`: The computed median of distinct method counts across clusters
- `accepted_positions`: Final boundary positions

### Stress test report sections

The stress test produces `STRESS_TEST_REPORT.md` with these sections:

1. **Executive Summary**: Total tests, pass rate, verdict
2. **Performance**: Indexing time
3. **Extraction Quality per Paper**: Pages, sections, tables, figures, grade, issues
4. **Failures (Detailed)**: Per-failure explanation with severity
5. **Passes**: Full assertion pass list
6. **Ground Truth Comparison**: Per-table cell accuracy, splits, merges, cell diffs
7. **Pipeline Depth Report**: Per-method win rates, combination value (best-single
   vs consensus), per-table accuracy chain
8. **Variant Comparison**: All 4 named configs compared on accuracy and speed

### Known shortcomings

The pipeline addresses most historical extraction issues (T1-T8, D1-D7 from the
original `table_shortcomings.md`) through adaptive thresholds and multi-method
consensus. Remaining edge cases are tracked via the stress test and ground truth
database (44 tables across 10 papers).
