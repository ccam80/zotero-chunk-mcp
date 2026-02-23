# Pipeline Operator's Guide

Reference guide for exploring, debugging, and optimizing the multi-method
table extraction pipeline. Covers the debug database, ground truth comparison
framework, scoring system, weight tuning, and common diagnostic workflows.

## Table of Contents

- [Quick Start](#quick-start)
- [Debug Database Reference](#debug-database-reference)
- [Structure Methods](#structure-methods)
- [Cell Extraction Methods](#cell-extraction-methods)
- [Post-Processors](#post-processors)
- [Scoring Framework](#scoring-framework)
- [Ground Truth Comparison](#ground-truth-comparison)
- [Pipeline Configurations](#pipeline-configurations)
- [Weight Tuning](#weight-tuning)
- [Combination Engine](#combination-engine)
- [Diagnostic Workflows](#diagnostic-workflows)
- [SQL Query Cookbook](#sql-query-cookbook)

---

## Quick Start

### Run the stress test

```bash
"./.venv/Scripts/python.exe" tests/stress_test_real_library.py
```

Produces:
- `STRESS_TEST_REPORT.md` — human-readable summary
- `_stress_test_debug.db` — SQLite database with all per-method data

### Query the debug DB

```bash
"./.venv/Scripts/python.exe" -c "
import sqlite3
con = sqlite3.connect('_stress_test_debug.db')
for row in con.execute('SELECT table_id, cell_accuracy_pct FROM ground_truth_diffs ORDER BY cell_accuracy_pct'):
    print(f'{row[0]:40s} {row[1]:6.1f}%')
con.close()
"
```

### Tune pipeline weights

```bash
"./.venv/Scripts/python.exe" tests/tune_weights.py
```

Reads `_stress_test_debug.db` → writes `tests/pipeline_weights.json`.

---

## Debug Database Reference

The stress test creates `_stress_test_debug.db` with two layers of tables.

### Core tables (extraction artifacts)

| Table | Key Columns | Written By |
|-------|-------------|-----------|
| `papers` | `item_key`, `short_name`, `pages`, `chunks_count`, `grade`, `completeness_*`, `markdown` | Main extraction loop |
| `extracted_tables` | `item_key`, `caption`, `headers_json`, `rows_json`, `fill_rate`, `num_rows`, `num_cols`, `bbox`, `artifact_type`, `markdown` | Main extraction loop |
| `extracted_figures` | `item_key`, `caption`, `bbox`, `image_path`, `reference_context` | Main extraction loop |
| `sections` | `item_key`, `label`, `heading`, `start_char`, `end_char`, `confidence` | Main extraction loop |
| `chunks` | `item_key`, `section`, `page_num`, `text`, `start_char`, `end_char` | Main extraction loop |
| `pages` | `item_key`, `page_num`, `markdown` | Main extraction loop |
| `test_results` | `test_name`, `paper`, `passed`, `detail`, `severity` | Assertion framework |
| `run_metadata` | `key`, `value` (timestamps, counts, timings) | Test harness |

### Extended tables (per-method analysis)

Written by `_test_pipeline_methods()` and the GT comparison pass.

#### `method_results`

One row per (table, structure_method, cell_method) combination.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment |
| `table_id` | TEXT | Stable ID from `make_table_id()` |
| `method_name` | TEXT | Format: `structure_name+cell_name` (e.g., `single_point_hotspot+rawdict`) |
| `boundary_hypotheses_json` | TEXT | JSON with structure_method, cell_method, col_boundaries, row_boundaries |
| `cell_grid_json` | TEXT | Full `CellGrid.to_dict()` — headers, rows, boundaries, methods |
| `quality_score` | REAL | GT cell accuracy (%) if GT exists, otherwise fill_rate × 100 |
| `execution_time_ms` | INTEGER | NULL (timing tracked separately in ExtractionResult) |

**Note**: `method_name` uses `+` as separator, while `pipeline_runs.winning_method`
uses `:` as separator. This is an inconsistency in the current code.

#### `pipeline_runs`

One row per table: the pipeline's final selection.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment |
| `table_id` | TEXT | Stable table ID |
| `pipeline_config_json` | TEXT | Full config serialized via `PipelineConfig.to_dict()` |
| `winning_method` | TEXT | Format: `structure_name:cell_name` (e.g., `consensus:rawdict`) |
| `final_score` | REAL | GT cell accuracy from `ground_truth_diffs` (or NULL) |

#### `ground_truth_diffs`

One row per table: structured diff between extraction and ground truth.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment |
| `table_id` | TEXT | Stable table ID |
| `run_id` | TEXT | Identifies the stress test run |
| `diff_json` | TEXT | Full `ComparisonResult` serialized via `dataclasses.asdict()` |
| `cell_accuracy_pct` | REAL | Percentage of comparable cells matching GT (0–100) |
| `num_splits` | INTEGER | Row splits + column splits |
| `num_merges` | INTEGER | Row merges + column merges |
| `num_cell_diffs` | INTEGER | Count of individual cell mismatches |
| `gt_shape` | TEXT | JSON array `[rows, cols]` of ground truth |
| `ext_shape` | TEXT | JSON array `[rows, cols]` of extraction |

---

## Structure Methods

Structure methods detect column and row boundaries for a table region.
Each returns a `BoundaryHypothesis` with `col_boundaries` and `row_boundaries`
(tuples of `BoundaryPoint`).

### Method inventory

| Method | Class | Source File | Approach |
|--------|-------|------------|----------|
| `single_point_hotspot` | `SinglePointHotspot` | `methods/hotspot.py` | Word gap analysis: finds column gaps from word x-positions |
| `gap_span_hotspot` | `GapSpanHotspot` | `methods/hotspot.py` | Extended gap analysis with span-based gap detection |
| `global_cliff` | `GlobalCliff` | `methods/cliff.py` | Global gap distribution cliff detection across all words |
| `per_row_cliff` | `PerRowCliff` | `methods/cliff.py` | Per-row cliff detection for inconsistent column layouts |
| `header_anchor` | `HeaderAnchor` | `methods/header_anchor.py` | Uses header row word positions to anchor column boundaries |
| `ruled_lines` | `RuledLineDetection` | `methods/ruled_lines.py` | Detects actual drawn lines (rules) from `page.get_drawings()` |
| `pymupdf_lines` | `PyMuPDFLines` | `methods/pymupdf_tables.py` | Wraps `page.find_tables(strategy="lines")` |
| `pymupdf_lines_strict` | `PyMuPDFLinesStrict` | `methods/pymupdf_tables.py` | Wraps `page.find_tables(strategy="lines_strict")` |
| `pymupdf_text` | `PyMuPDFText` | `methods/pymupdf_tables.py` | Wraps `page.find_tables(strategy="text")` |
| `camelot_lattice` | `CamelotLattice` | `methods/camelot_extraction.py` | Camelot lattice mode (requires ruled lines) |
| `camelot_hybrid` | `CamelotHybrid` | `methods/camelot_extraction.py` | Camelot with hybrid lattice+stream detection |
| `pdfplumber_lines` | `PdfplumberLines` | `methods/pdfplumber_structure.py` | pdfplumber line-based table detection |
| `pdfplumber_text` | `PdfplumberText` | `methods/pdfplumber_structure.py` | pdfplumber text-based table detection |

### Activation rules (DEFAULT_CONFIG)

- `camelot_lattice`, `camelot_hybrid`: Only activated when `has_ruled_lines(ctx)` is True
- `global_cliff`, `per_row_cliff`: Only activated when `has_ruled_lines(ctx)` is False
- All other methods: Always activated

### What a BoundaryHypothesis contains

```python
BoundaryHypothesis(
    col_boundaries=(BoundaryPoint(min_pos=72.0, max_pos=72.0, confidence=0.9, provenance="ruled_lines"), ...),
    row_boundaries=(BoundaryPoint(min_pos=150.0, max_pos=152.0, confidence=0.7, provenance="single_point_hotspot"), ...),
    method="single_point_hotspot",
    metadata={"num_word_rows": 15, "gap_threshold": 8.2},
)
```

- **Exact boundaries** (ruled lines): `min_pos == max_pos`, high confidence
- **Gap-based boundaries** (hotspot, cliff): `min_pos` = left edge of gap,
  `max_pos` = right edge; confidence proportional to gap size / consistency

---

## Cell Extraction Methods

Cell methods take boundary positions and extract text content into a `CellGrid`.
Each method runs against every `BoundaryHypothesis` (including consensus),
producing multiple grids that compete in scoring.

| Method | Class | Source File | Approach |
|--------|-------|------------|----------|
| `rawdict` | `RawdictExtraction` | `methods/cell_rawdict.py` | Uses `page.get_text("rawdict")` character-level data, assigns chars to cells by bbox intersection |
| `word_assignment` | `WordAssignment` | `methods/cell_words.py` | Uses `page.get_text("words")`, assigns whole words to cells by midpoint |
| `pdfminer` | `PdfMinerExtraction` | `methods/cell_pdfminer.py` | Uses pdfminer.six for independent text extraction, assigns to cells |

### CellGrid structure

```python
CellGrid(
    headers=("Study", "N", "Mean", "SD"),
    rows=(("Smith 2020", "150", "3.2", "0.8"), ("Jones 2021", "200", "4.1", "1.1")),
    col_boundaries=(72.0, 150.0, 220.0, 300.0, 380.0),
    row_boundaries=(100.0, 120.0, 140.0),
    method="rawdict",
    structure_method="single_point_hotspot",
)
```

The composite key `structure_method:method` identifies which pipeline path
produced this grid (e.g., `single_point_hotspot:rawdict`).

---

## Post-Processors

Post-processors transform the winning `CellGrid` in a fixed canonical order.
Each returns a new `CellGrid` (immutable). Snapshots are saved in
`ExtractionResult.snapshots` for debugging.

| Order | Post-Processor | Class | Purpose |
|-------|---------------|-------|---------|
| 1 | `absorbed_caption` | `AbsorbedCaptionStrip` | Remove caption text accidentally absorbed into first row |
| 2 | `header_detection` | `HeaderDetection` | Detect header row(s) by font weight, case, content patterns |
| 3 | `header_data_split` | `HeaderDataSplit` | Split headers from data rows if detection finds header boundary |
| 4 | `continuation_merge` | `ContinuationMerge` | Merge continuation rows (multi-line cell content split across rows) |
| 5 | `inline_header_fill` | `InlineHeaderFill` | Fill inline sub-group headers (rows with content only in col 0) |
| 6 | `footnote_strip` | `FootnoteStrip` | Remove footnote rows from the bottom of the grid |
| 7 | `cell_cleaning` | `CellCleaning` | Whitespace normalization, dash unification, ligature expansion |

### Debugging post-processors

Post-processor snapshots in `ExtractionResult.snapshots` are `(name, CellGrid)` tuples.
To see what each post-processor changed:

```python
result = pipeline.extract(ctx)
for name, grid in result.snapshots:
    print(f"After {name}: {len(grid.headers)} cols, {len(grid.rows)} rows")
```

Footnote extraction is derived by diffing pre- and post-`FootnoteStrip` grids.

---

## Scoring Framework

`scoring.py` uses **rank-based selection** — no absolute weights to calibrate.

### How it works

1. Compute 4 metrics for each candidate grid
2. Rank grids per metric (ties get averaged rank)
3. Sum ranks across all metrics
4. Lowest rank sum wins

### Metrics

| Metric | Function | Higher/Lower | Measures |
|--------|----------|-------------|---------|
| Fill rate | `fill_rate(grid)` | Higher = better | Fraction of non-empty cells (0.0–1.0) |
| Decimal displacement | `decimal_displacement_count(grid)` | Lower = better | Count of cells matching `^\.\d+` |
| Garbled text | `garbled_text_score(grid)` | Lower = better | Fraction of cells with avg word length > 25 |
| Numeric coherence | `numeric_coherence(grid)` | Higher = better | Fraction of numeric columns that are consistently typed |
| GT accuracy (optional) | `ground_truth_fn(headers, rows)` | Higher = better | Cell accuracy vs ground truth |

### Grid identification in scores dict

`ExtractionResult.grid_scores` maps `"structure_method:cell_method"` → rank sum.

Example:
```python
{
    "single_point_hotspot:rawdict": 4.0,
    "single_point_hotspot:word_assignment": 8.0,
    "consensus:rawdict": 6.0,
    "consensus:word_assignment": 10.0,
    "pymupdf_lines:rawdict": 12.0,
}
```

Lower = better. The winning grid is `single_point_hotspot:rawdict` (rank sum 4.0).

---

## Ground Truth Comparison

### Overview

44 ground truth tables across 10 papers, stored in `tests/ground_truth.db`.
Verified through human review in `tests/ground_truth_workspace/`.

### ComparisonResult interpretation

**Perfect extraction**: `cell_accuracy_pct == 100.0`, no splits/merges/diffs.

**Structural problems** (column/row level):
- `extra_columns > 0`: Extraction detected too many columns (over-segmentation)
- `missing_columns > 0`: Extraction missed columns (under-segmentation)
- `column_splits`: One GT column became multiple extraction columns
- `column_merges`: Multiple GT columns became one extraction column
- Same patterns for rows

**Content problems** (cell level):
- `cell_diffs`: Individual cells where extraction differs from GT
- `cell_accuracy_pct < 100`: Percentage of comparable cells matching

**Coverage**:
- `structural_coverage_pct`: How much of the GT table was actually comparable.
  Low coverage means structural issues (splits/merges/missing) prevented comparison
  of many cells.
- `comparable_cells / total_gt_cells`: Raw ratio

### Interpreting diff_json

The `diff_json` column in `ground_truth_diffs` contains the full serialized
`ComparisonResult`. Parse it to get detailed cell-level diffs:

```python
import json, sqlite3
con = sqlite3.connect("_stress_test_debug.db")
row = con.execute(
    "SELECT diff_json FROM ground_truth_diffs WHERE table_id = ?",
    ("5SIZVS65_table_1",)
).fetchone()
diff = json.loads(row[0])
for cd in diff["cell_diffs"]:
    print(f"  Row {cd['row']}, Col {cd['col']}: expected={cd['expected']!r}, got={cd['actual']!r}")
```

### Ground truth workspace

`tests/ground_truth_workspace/<paper_slug>/` contains per-paper directories with:
- `table_N_gt.json`: Verified ground truth (headers + rows)
- `table_N_rawtext.txt`: Raw text extracted from the table region
- `REVIEW.md`: Human review notes

---

## Pipeline Configurations

### Named configs

| Config | Use Case | Structure Methods | Cell Methods |
|--------|----------|------------------|-------------|
| `DEFAULT_CONFIG` | Production extraction | All 13 (with activation rules) | All 3 |
| `FAST_CONFIG` | Quick extraction | PyMuPDFLines, GapSpanHotspot | Rawdict, WordAssignment |
| `RULED_CONFIG` | Tables with visible rules/lines | All 13 | All 3 (ruled_lines × 3.0) |
| `MINIMAL_CONFIG` | Baseline / debugging | PyMuPDFLines only | Rawdict only |

### Creating a custom config

```python
from zotero_chunk_rag.feature_extraction.pipeline import Pipeline, DEFAULT_CONFIG
from zotero_chunk_rag.feature_extraction.methods.hotspot import SinglePointHotspot

custom = DEFAULT_CONFIG.with_overrides(
    structure_methods=(SinglePointHotspot(),),
    confidence_multipliers={"single_point_hotspot": 1.0},
)
pipeline = Pipeline(custom)
result = pipeline.extract(ctx)
```

### Running variant comparison

The stress test automatically runs all 4 named configs on the first 3 tables per
paper and produces the "Variant Comparison" section in the report. This shows
per-table accuracy and timing across configs.

---

## Weight Tuning

### Workflow

```
Stress test → _stress_test_debug.db → tune_weights.py → pipeline_weights.json → Pipeline
```

### Step by step

1. **Run stress test**: Populates `method_results` with per-method GT accuracy
2. **Run tuner**:
   ```bash
   "./.venv/Scripts/python.exe" tests/tune_weights.py
   ```
3. **Tuner logic**:
   - For each table: find the `structure+cell` combo with highest `quality_score`
   - The structure method gets a "win"
   - Win rate = wins / tables where method participated
   - Best method → multiplier 1.0; others proportional; zero-wins → floor 0.1
4. **Output**: `tests/pipeline_weights.json`
5. **Pipeline reads at init**: `Pipeline.__init__()` merges file multipliers into config

### Custom tuning

```bash
# Use a different debug DB
"./.venv/Scripts/python.exe" tests/tune_weights.py path/to/debug.db

# Write to custom location
"./.venv/Scripts/python.exe" tests/tune_weights.py _stress_test_debug.db custom_weights.json
```

### Interpreting the output

```
Win rates:
  single_point_hotspot: 1.000
  gap_span_hotspot: 0.000
  pymupdf_lines: 0.000
  ...

Confidence multipliers:
  single_point_hotspot: 1.000
  gap_span_hotspot: 0.100
  pymupdf_lines: 0.100
```

A method with win rate 0.000 means its boundaries never produced the best cell
accuracy for any table. It still participates in combination (floor multiplier
0.1) but has minimal influence.

---

## Combination Engine

### How boundary combination works

`combine_hypotheses()` in `combination.py` merges all `BoundaryHypothesis` objects
into a single consensus hypothesis.

**Per-axis algorithm**:
1. **Confidence scaling**: Each boundary point's confidence is multiplied by its
   method's multiplier (from `pipeline_weights.json`).
2. **Point expansion**: Narrow boundary ranges (span < spatial precision) are
   expanded symmetrically around their midpoint to spatial precision width.
3. **Overlap merge**: Expanded points sorted by position; overlapping ranges
   merged into clusters.
4. **Acceptance**: Each cluster's distinct method count is computed. The acceptance
   threshold is the **median of all clusters' distinct method counts**. Clusters
   meeting or exceeding this threshold are accepted. Clusters containing a
   `provenance == "ruled_lines"` boundary are unconditionally accepted.
5. **Consensus confidence**: Each accepted boundary's confidence is the **mean**
   of its constituent points' scaled confidences.

### Spatial precision

Adaptive tolerance for point expansion and merge distance. Derived from a unified
priority chain (not per-axis):
1. Ruled line thickness (if ruled lines detected)
2. Median word gap (fallback)
3. Median word height (final fallback)

Higher precision = tighter clusters = more boundaries preserved.

### Enabling trace mode

```python
from zotero_chunk_rag.feature_extraction.combination import combine_hypotheses

consensus, trace = combine_hypotheses(hypotheses, ctx, trace=True)

# Inspect column clusters
for c in trace.col_trace.clusters:
    print(f"Cluster at {c.weighted_position:.1f}: "
          f"confidence={c.total_confidence:.2f}, "
          f"methods={c.distinct_methods}, "
          f"accepted={c.accepted}")
```

### Common combination issues

| Symptom | Likely Cause |
|---------|-------------|
| Too many columns | Spatial precision too wide; unrelated gaps from different methods cluster together |
| Missing columns | Acceptance threshold too high; good boundaries from one method diluted by silence from others |
| Columns shifted | Weighted average pulled by inaccurate method boundaries |
| Consensus worse than single method | Multiple poor methods outvote the single accurate one |

---

## Diagnostic Workflows

### "Why does this table have low fill rate?"

1. Query the extracted table:
   ```sql
   SELECT caption, fill_rate, num_rows, num_cols, rows_json
   FROM extracted_tables WHERE item_key = '<KEY>' AND fill_rate < 0.5;
   ```

2. Check if it's an over-segmentation issue (too many columns):
   ```sql
   SELECT table_id, ext_shape, gt_shape, num_cell_diffs, cell_accuracy_pct
   FROM ground_truth_diffs WHERE table_id LIKE '<PAPER>%';
   ```

3. If `ext_shape` has more columns than `gt_shape`, the boundary detection
   over-segmented. Check which method's boundaries won:
   ```sql
   SELECT winning_method, final_score
   FROM pipeline_runs WHERE table_id = '<TABLE_ID>';
   ```

4. Check all methods' accuracy for this table:
   ```sql
   SELECT method_name, quality_score
   FROM method_results WHERE table_id = '<TABLE_ID>'
   ORDER BY quality_score DESC;
   ```

### "Which method should be winning?"

Query per-method accuracy for all tables to find the overall best:

```sql
SELECT
  SUBSTR(method_name, 1, INSTR(method_name, '+') - 1) AS structure,
  SUBSTR(method_name, INSTR(method_name, '+') + 1) AS cell,
  COUNT(*) AS tables,
  AVG(quality_score) AS avg_accuracy,
  SUM(CASE WHEN quality_score = 100.0 THEN 1 ELSE 0 END) AS perfect
FROM method_results
WHERE quality_score IS NOT NULL
GROUP BY structure, cell
ORDER BY avg_accuracy DESC;
```

### "Is consensus helping or hurting?"

```sql
-- Average delta between best-single-method and pipeline consensus
SELECT
  AVG(best_single) AS avg_best,
  AVG(pipeline_acc) AS avg_pipeline,
  AVG(pipeline_acc - best_single) AS avg_delta
FROM (
  SELECT
    mr.table_id,
    MAX(mr.quality_score) AS best_single,
    gtd.cell_accuracy_pct AS pipeline_acc
  FROM method_results mr
  JOIN ground_truth_diffs gtd ON mr.table_id = gtd.table_id
  WHERE mr.quality_score IS NOT NULL
  GROUP BY mr.table_id
);
```

Negative `avg_delta` = combination is hurting. Positive = helping.

### "What changed between two stress test runs?"

The debug DB is overwritten each run. To compare, save copies:

```bash
cp _stress_test_debug.db _debug_before.db
# ... make code changes ...
"./.venv/Scripts/python.exe" tests/stress_test_real_library.py
cp _stress_test_debug.db _debug_after.db
```

Then compare:

```sql
-- Attach both databases
ATTACH '_debug_before.db' AS before;
ATTACH '_debug_after.db' AS after;

-- Tables that improved
SELECT b.table_id, b.cell_accuracy_pct AS before, a.cell_accuracy_pct AS after
FROM before.ground_truth_diffs b
JOIN after.ground_truth_diffs a ON b.table_id = a.table_id
WHERE a.cell_accuracy_pct > b.cell_accuracy_pct;

-- Tables that regressed
SELECT b.table_id, b.cell_accuracy_pct AS before, a.cell_accuracy_pct AS after
FROM before.ground_truth_diffs b
JOIN after.ground_truth_diffs a ON b.table_id = a.table_id
WHERE a.cell_accuracy_pct < b.cell_accuracy_pct;
```

---

## SQL Query Cookbook

### Basic queries

```sql
-- All MAJOR test failures
SELECT test_name, paper, detail FROM test_results
WHERE passed = 0 AND severity = 'MAJOR';

-- Per-paper extraction grades
SELECT short_name, grade, pages, chunks_count FROM papers;

-- Tables with low fill (extraction problems)
SELECT short_name, caption, fill_rate, num_rows, num_cols
FROM extracted_tables JOIN papers USING(item_key)
WHERE fill_rate < 0.5 AND artifact_type IS NULL;
```

### Per-method analysis

```sql
-- Structure method win rates (which method produces best accuracy most often)
WITH best_per_table AS (
  SELECT table_id,
    SUBSTR(method_name, 1, INSTR(method_name, '+') - 1) AS winner
  FROM method_results mr
  WHERE quality_score = (
    SELECT MAX(quality_score) FROM method_results
    WHERE table_id = mr.table_id AND quality_score IS NOT NULL
  )
),
participation AS (
  SELECT DISTINCT table_id,
    SUBSTR(method_name, 1, INSTR(method_name, '+') - 1) AS structure
  FROM method_results
)
SELECT p.structure,
  COUNT(DISTINCT p.table_id) AS participated,
  COUNT(DISTINCT b.table_id) AS wins,
  ROUND(COUNT(DISTINCT b.table_id) * 100.0 / COUNT(DISTINCT p.table_id), 1) AS win_pct
FROM participation p
LEFT JOIN best_per_table b ON p.structure = b.winner AND p.table_id = b.table_id
GROUP BY p.structure
ORDER BY win_pct DESC;

-- Cell method comparison across all tables
SELECT
  SUBSTR(method_name, INSTR(method_name, '+') + 1) AS cell_method,
  COUNT(*) AS grids,
  ROUND(AVG(quality_score), 1) AS avg_acc,
  SUM(CASE WHEN quality_score = 100 THEN 1 ELSE 0 END) AS perfect
FROM method_results WHERE quality_score IS NOT NULL
GROUP BY cell_method;

-- Per-table accuracy breakdown: all methods for one table
SELECT method_name, quality_score
FROM method_results WHERE table_id = '<TABLE_ID>'
ORDER BY quality_score DESC;
```

### Ground truth analysis

```sql
-- Worst tables by accuracy
SELECT table_id, cell_accuracy_pct, num_splits, num_merges, num_cell_diffs
FROM ground_truth_diffs ORDER BY cell_accuracy_pct ASC;

-- Tables with structural issues (splits or merges)
SELECT table_id, gt_shape, ext_shape, num_splits, num_merges
FROM ground_truth_diffs WHERE num_splits > 0 OR num_merges > 0;

-- Overall corpus accuracy
SELECT ROUND(AVG(cell_accuracy_pct), 1) AS avg_accuracy,
  COUNT(*) AS tables,
  SUM(CASE WHEN cell_accuracy_pct = 100 THEN 1 ELSE 0 END) AS perfect
FROM ground_truth_diffs;
```

### Pipeline selection analysis

```sql
-- Which methods does the pipeline select?
SELECT winning_method, COUNT(*) AS times, ROUND(AVG(final_score), 1) AS avg_acc
FROM pipeline_runs GROUP BY winning_method ORDER BY times DESC;

-- Tables where pipeline chose sub-optimally
SELECT pr.table_id, pr.winning_method, pr.final_score,
  (SELECT MAX(quality_score) FROM method_results WHERE table_id = pr.table_id) AS best_available
FROM pipeline_runs pr
WHERE pr.final_score < (SELECT MAX(quality_score) FROM method_results WHERE table_id = pr.table_id);
```

### Variant comparison

```sql
-- Compare extraction shapes across GT
SELECT
  table_id,
  gt_shape,
  ext_shape,
  CASE WHEN gt_shape = ext_shape THEN 'match' ELSE 'MISMATCH' END AS shape_status
FROM ground_truth_diffs;
```
