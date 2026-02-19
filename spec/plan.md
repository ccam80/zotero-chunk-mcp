# Table Extraction Reengineering — Implementation Plan

## Goals

- **Composable pipeline architecture**: Structure detection, cell extraction, and post-processing are separate concerns with named methods. Building a pipeline is constructing a list that reads like a narrative.
- **Confidence-weighted boundary combination**: Multiple structure methods propose column/row boundaries as `BoundaryHypothesis` objects with confidence scores. These combine via AND (consensus voting) and OR (best-score selection) operators.
- **Every method explored**: Word gap hotspot, cliff detection, ruled lines, pymupdf `find_tables()`, Camelot (lattice + hybrid), pdfplumber, and vision-model slot — all implemented as interchangeable pipeline steps.
- **Blind ground truth evaluation**: Human-verified ground truth for every corpus table, stored in a SQLite DB accessible only through a comparison API. Agents submit extractions and get diffs back — never see the answer.
- **Extended debug database**: Input PDFs, intermediate outputs (per-method boundary hypotheses, per-method cell extractions, scores), and ground truth diffs stored for offline analysis without re-running extraction.
- **Agent-led vision QA**: A repeatable agent-driven quality assurance loop where a haiku agent renders table images, visually reads them, and compares against automated extraction to flag discrepancies.
- **Zero MAJOR failures**: Stress test remains the acceptance criterion. All 10 papers grade A. Every table cell matches ground truth.

## Non-Goals

- **Speed optimization**: We explicitly accept extra extraction time. Try everything, pick the best.
- **Backward-compatible API**: The internal pipeline API will change completely. The external `extract_document()` signature stays the same but internals are rewritten.
- **Rewriting non-table code**: Caption detection, figure extraction, section classification, reference matching, gap-fill — these work well and stay as-is. Shared utilities (caption regex, font detection) may be refactored into common modules.
- **Supporting scanned/OCR PDFs**: All corpus papers are text-based PDFs. OCR support is out of scope.
- **tabula-py integration**: Excluded due to Java dependency. pymupdf + pdfplumber + Camelot cover the same ground.

## Verification

- **Phase 1 complete**: Ground truth DB exists with comparison API. `compare_table(extraction, table_id)` returns structured diff. Debug DB schema extended. Camelot + pdfplumber importable.
- **Phase 2 complete**: Human-reviewed ground truth for all ~44 corpus tables. Each ground truth entry has headers, rows, and metadata.
- **Phase 3 complete**: `BoundaryHypothesis` model exists. Method protocol defined. `Pipeline` class accepts a list of methods and runs them. Unit tests pass on synthetic data (syntax-check level only).
- **Phase 4 complete**: Agent QA tooling built and tested on 3-4 representative tables. Prompt template validated. Design doc for production QA pathway written.
- **Phase 5 complete**: Each method (word gap, ruled lines, pymupdf, Camelot, pdfplumber, cliff) runs independently on any corpus table and returns a `BoundaryHypothesis` or cell grid. Per-method results stored in debug DB.
- **Phase 6 complete**: Default pipeline runs all methods, combines boundaries, extracts cells, post-processes. Results for every corpus table stored in debug DB with ground truth diffs. Evaluation report identifies per-method win rates.
- **Phase 7 complete**: `extract_document()` uses new pipeline. Old table extraction code removed. Stress test: 0 MAJOR, all papers grade A. Agent-led QA confirms no regressions.

## Dependency Graph

```
Phase 1 (Foundation)
├──→ Phase 2 (Ground Truth)      ─── parallel after 1 ──────┐
├──→ Phase 3 (Architecture)      ─── parallel after 1        │
├──→ Phase 4 (QA Tooling)        ─── parallel after 1        │
│                                                             │
│    Phase 5 (Methods)           ─── sequential after 3       │
│                                                             │
│    Phase 6 (Assembly)          ─── sequential after 5 + 2 ──┘
│
└──→ Phase 7 (Integration)      ─── sequential after 6
```

Phases 2, 3, and 4 can all start in parallel once Phase 1 completes.

---

## Phase 1: Foundation & Infrastructure

**Depends on**: (none)

### Wave 1.1: Project setup and rules

| Task | Description | Complexity | Key Files |
|------|-------------|------------|-----------|
| 1.1.1 | Update CLAUDE.md with new rules: test integrity (never modify tests to fit corpus), 100% assertion standard, synthetic tests are syntax-checks only, extraction time budget (try everything). Add table extraction architecture section documenting the new module structure. | S | `CLAUDE.md` |
| 1.1.2 | Install Camelot (`camelot-py[base]`) and pdfplumber as project dependencies. Verify imports work. Verify Ghostscript is installed and Camelot lattice mode functions. Add to pyproject.toml. | S | `pyproject.toml` |
| 1.1.3 | Create `src/zotero_chunk_rag/table_extraction/` package with `__init__.py`. This is the new home for all table extraction code. Create empty placeholder modules: `models.py`, `protocols.py`, `pipeline.py`, `scoring.py`, `combination.py`. Create `methods/` and `postprocessors/` sub-packages with `__init__.py`. | S | `src/zotero_chunk_rag/table_extraction/` |

### Wave 1.2: Ground truth infrastructure

| Task | Description | Complexity | Key Files |
|------|-------------|------------|-----------|
| 1.2.1 | Design and create ground truth SQLite database schema. Tables: `ground_truth_tables` (table_id, paper_key, page_num, caption, headers_json, rows_json, num_rows, num_cols, notes), `ground_truth_meta` (created_by, verified_by, timestamp). Write creation script. | M | `src/zotero_chunk_rag/table_extraction/ground_truth.py` |
| 1.2.2 | Build blind comparison API: `compare_extraction(headers, rows, table_id) -> ComparisonResult`. Returns structured diff: missing_cells, extra_cells, wrong_values (with expected vs actual), extra_columns, missing_columns, row_count_diff, col_count_diff, cell_accuracy_pct. API never exposes raw ground truth — only diffs. | M | `src/zotero_chunk_rag/table_extraction/ground_truth.py` |
| 1.2.3 | Build table image renderer: given a PDF path + page + bbox, render the region as a PNG at 200 DPI with 20px padding. Save to a specified directory. This is used for agent-led ground truth creation and QA. | S | `src/zotero_chunk_rag/table_extraction/render.py` |

### Wave 1.3: Debug database extension

| Task | Description | Complexity | Key Files |
|------|-------------|------------|-----------|
| 1.3.1 | Extend `_stress_test_debug.db` schema: add tables for `method_results` (table_id, method_name, boundary_hypotheses_json, cell_grid_json, quality_score, execution_time_ms), `pipeline_runs` (table_id, pipeline_config_json, winning_method, final_score), `ground_truth_diffs` (table_id, run_id, diff_json, cell_accuracy_pct). Update stress test to write to new tables. | M | `tests/stress_test_real_library.py`, schema in `src/zotero_chunk_rag/table_extraction/debug_db.py` |

---

## Phase 2: Ground Truth Creation

**Depends on**: Phase 1 (Wave 1.2)
**Parallel with**: Phases 3, 4

### Wave 2.1: Agent-created draft ground truth

| Task | Description | Complexity | Key Files |
|------|-------------|------------|-----------|
| 2.1.1 | Run the current stress test to populate the debug DB. Use the table image renderer (1.2.3) to render every non-artifact table in the corpus as a PNG. Create a ground truth workspace directory with one subdirectory per paper. Each subdirectory contains: table images, current extraction output (headers + rows as JSON), and a `review.md` template for human notes. | M | `tests/create_ground_truth.py`, workspace in `tests/ground_truth_workspace/` |
| 2.1.2 | Agent (haiku) visually inspects each table image via Read tool. For each table: reads the image, produces ground truth as `{"headers": [...], "rows": [[...]]}` JSON. Writes output alongside the image. Uses the current extraction as a starting point but overrides wherever the image disagrees. | L | Agent task — produces `tests/ground_truth_workspace/<paper>/table_N_gt.json` |
| 2.1.3 | Build a ground truth review tool: for each table, renders the image, shows current extraction vs agent-created ground truth side-by-side as markdown. User approves, corrects, or rejects each entry. Approved entries are written to the ground truth DB. | M | `tests/review_ground_truth.py` |

### Wave 2.2: User review (human task)

| Task | Description | Complexity | Key Files |
|------|-------------|------------|-----------|
| 2.2.1 | User reviews all agent-created ground truth using the review tool (2.1.3). Corrects any errors. Approves final entries into the ground truth DB. Target: 100% of corpus tables have verified ground truth. | — (human) | `tests/ground_truth.db` |

---

## Phase 3: Core Architecture

**Depends on**: Phase 1 (Wave 1.1, 1.3)
**Parallel with**: Phases 2, 4

### Wave 3.1: Data models

| Task | Description | Complexity | Key Files |
|------|-------------|------------|-----------|
| 3.1.1 | Define core data models: `BoundaryPoint(position, confidence, support, provenance)`, `BoundaryHypothesis(col_boundaries, row_boundaries, method, metadata)`, `CellGrid(headers, rows, method, quality_score)`, `ExtractionResult(table_id, boundary_hypotheses, cell_grids, winning_grid, post_processed)`. All are dataclasses with JSON serialization. | M | `src/zotero_chunk_rag/table_extraction/models.py` |

### Wave 3.2: Method protocols and pipeline framework

| Task | Description | Complexity | Key Files |
|------|-------------|------------|-----------|
| 3.2.1 | Define method protocols (Python `Protocol` classes): `StructureMethod.detect(page, bbox, words) -> BoundaryHypothesis`, `CellExtractionMethod.extract(page, bbox, row_bounds, col_bounds) -> CellGrid`, `PostProcessor.process(headers, rows, page, bbox) -> tuple[headers, rows]`. Each protocol has a `name` property and optional `activate(table_features) -> bool` for per-table method selection. | M | `src/zotero_chunk_rag/table_extraction/protocols.py` |
| 3.2.2 | Build `Pipeline` class. Constructor takes lists of structure methods, cell extraction methods, and post-processors. `Pipeline.extract(page, bbox) -> ExtractionResult` runs: (1) all structure methods → collect hypotheses, (2) combine boundaries, (3) all cell extraction methods on consensus grid → collect grids, (4) score and select best grid, (5) run post-processors sequentially. Pipeline is configurable per-table: `Pipeline.extract(page, bbox, method_overrides=...)`. | L | `src/zotero_chunk_rag/table_extraction/pipeline.py` |

### Wave 3.3: Combination and scoring

| Task | Description | Complexity | Key Files |
|------|-------------|------------|-----------|
| 3.3.1 | Build boundary combination engine: `combine_hypotheses(hypotheses: list[BoundaryHypothesis]) -> BoundaryHypothesis`. Algorithm: (1) pool all boundary points, (2) cluster nearby points (tolerance = adaptive from word dimensions), (3) for each cluster: combined confidence = weighted sum (weight per method configurable), support = distinct methods contributing, (4) filter by minimum support threshold (adaptive: fraction of methods that ran), (5) return consensus boundaries sorted by position. | L | `src/zotero_chunk_rag/table_extraction/combination.py` |
| 3.3.2 | Build quality scoring framework: `score_cell_grid(grid: CellGrid, page, bbox) -> float`. Metrics: fill rate, decimal integrity, garbled text detection, numeric coherence (columns should be consistently numeric or text), header-data type consistency. All metric weights derived from the grid's own statistics — no fixed scoring weights. If ground truth is available, also compute cell accuracy. | M | `src/zotero_chunk_rag/table_extraction/scoring.py` |

---

## Phase 4: Agent-Led Vision QA Tooling

**Depends on**: Phase 1 (Wave 1.2)
**Parallel with**: Phases 2, 3

### Wave 4.1: QA infrastructure

| Task | Description | Complexity | Key Files |
|------|-------------|------------|-----------|
| 4.1.1 | Build agent QA orchestration script: (1) renders all non-artifact tables as images, (2) writes current extraction as JSON alongside each image, (3) produces a manifest file listing all table_id → image_path → extraction_path mappings. | M | `tests/agent_qa/prepare_qa.py` |
| 4.1.2 | Design the agent QA prompt template: given an image path and extraction JSON, the agent (haiku) reads the image, reads the extraction, and returns a structured comparison: `{matches: bool, discrepancies: [{cell: [row,col], expected: str, actual: str, severity: "MAJOR"|"MINOR"}]}`. Test the prompt on 3-4 representative tables. | M | `tests/agent_qa/qa_prompt.md`, `tests/agent_qa/run_qa.py` |
| 4.1.3 | Scope the full agent-led indexing pathway: document what would be required for a production mode where every newly-indexed PDF gets an automatic haiku agent QA pass. Estimate: tokens per table image (~1600), cost per paper (10 tables × haiku pricing), latency, and whether this should be async/background. Write up as a design doc. | S | `spec/agent_qa_design.md` |

---

## Phase 5: Method Implementation

**Depends on**: Phase 3

### Wave 5.1: Structure methods — word-position based

| Task | Description | Complexity | Key Files |
|------|-------------|------------|-----------|
| 5.1.1 | **Word gap hotspot method**: Implement the hotspot algorithm from `stress_test_tables_fix_plan.md`. For each row, record x-positions where word gaps occur (filter micro-gaps via adaptive word-height threshold). Cluster x-positions across rows. Column boundaries = clusters with sufficient row support. Confidence = support fraction. Header row weighting (first multi-gap row gets extra votes). Returns `BoundaryHypothesis`. | L | `src/zotero_chunk_rag/table_extraction/methods/word_gap_hotspot.py` |
| 5.1.2 | **Cliff detection method**: Sort all inter-word gaps within the table. Find the largest relative jump (cliff) in the sorted gap sequence. Gaps above the cliff are column gaps; below are intra-word/intra-cell gaps. Convert to x-position boundaries. Confidence derived from cliff magnitude. Known weakness: sensitive to math kerning artifacts — detect and exclude spans from math/symbol fonts. Returns `BoundaryHypothesis`. | M | `src/zotero_chunk_rag/table_extraction/methods/cliff_detection.py` |
| 5.1.3 | **Row clustering utility**: Extract `_adaptive_row_tolerance()` and row clustering from current pdf_processor.py into a shared utility. All structure methods use this for consistent row detection. Tolerance = median word height × adaptive multiplier from gap distribution. | M | `src/zotero_chunk_rag/table_extraction/methods/_row_clustering.py` |

### Wave 5.2: Structure methods — library-based

| Task | Description | Complexity | Key Files |
|------|-------------|------------|-----------|
| 5.2.1 | **PyMuPDF find_tables wrapper**: Wrap `page.find_tables(clip=bbox, strategy=...)` as a `StructureMethod`. Try all three strategies (`lines`, `lines_strict`, `text`). Convert detected cell bboxes to row/column boundaries. Confidence based on strategy (lines > lines_strict > text) and table regularity (consistent column count across rows). Return best hypothesis. | M | `src/zotero_chunk_rag/table_extraction/methods/pymupdf_tables.py` |
| 5.2.2 | **Ruled line detection**: Use `page.get_drawings()` to find horizontal and vertical lines within the table bbox. Filter to lines that span a significant fraction of the table width/height. Horizontal lines → row boundaries (high confidence). Vertical lines → column boundaries (high confidence). This is a strong signal when present — ruled tables are common in journals. | M | `src/zotero_chunk_rag/table_extraction/methods/ruled_lines.py` |
| 5.2.3 | **Camelot lattice + hybrid**: Wrap Camelot's `read_pdf()` with `flavor="lattice"` and `flavor="hybrid"` as `StructureMethod` implementations. Convert Camelot's coordinate system (PDF bottom-left origin) to pymupdf's (top-left origin). Pass `table_areas` derived from our known bbox. Convert Camelot's cell structure to `BoundaryHypothesis`. Handle Ghostscript dependency gracefully. | M | `src/zotero_chunk_rag/table_extraction/methods/camelot_extraction.py` |
| 5.2.4 | **pdfplumber structure detection**: Wrap pdfplumber's `page.crop(bbox).find_tables()` as a `StructureMethod`. Try both `vertical_strategy="lines"` and `vertical_strategy="text"`. Convert cell bboxes to boundaries. pdfplumber uses the same coordinate system as pymupdf (top-left origin) but different page model — handle conversion. | M | `src/zotero_chunk_rag/table_extraction/methods/pdfplumber_extraction.py` |

### Wave 5.3: Cell extraction methods

| Task | Description | Complexity | Key Files |
|------|-------------|------------|-----------|
| 5.3.1 | **rawdict 50% overlap method**: Extract existing `_extract_via_rawdict()` logic as a `CellExtractionMethod`. Given row/column boundaries, construct cell bboxes. Use `pymupdf.table.extract_cells()` with 50% overlap to assign characters to cells. Include font-aware control character handling (Fix 3 from the fix plan): detect control chars, check font name for Greek/Math/Symbol, attempt Unicode mapping. | M | `src/zotero_chunk_rag/table_extraction/methods/cell_rawdict.py` |
| 5.3.2 | **Word assignment method**: Given row/column boundaries, get words via `page.get_text("words", clip=bbox)`. Assign each word to the cell whose column boundaries contain the word's x-center. Concatenate words per cell with spaces. This is the simplest method but robust against character-level extraction artifacts. | S | `src/zotero_chunk_rag/table_extraction/methods/cell_words.py` |
| 5.3.3 | **pdfplumber cell extraction**: Use pdfplumber's `crop(cell_bbox).extract_text()` for each cell. Compare against pdfplumber's full-table `extract_table()` if cell-level results differ. pdfplumber uses a different text grouping algorithm that may handle some edge cases better. | M | `src/zotero_chunk_rag/table_extraction/methods/cell_pdfplumber.py` |
| 5.3.4 | **Camelot cell extraction**: When Camelot successfully detects a table, its `.data` provides pre-extracted cell text. Wrap as a `CellExtractionMethod`. Camelot's text extraction uses PDFMiner internally — different algorithm from pymupdf. | S | `src/zotero_chunk_rag/table_extraction/methods/cell_camelot.py` |

### Wave 5.4: Post-processors

| Task | Description | Complexity | Key Files |
|------|-------------|------------|-----------|
| 5.4.1 | **Continuation row merger**: Extract and improve `_merge_over_divided_rows()` as a `PostProcessor`. Detect continuation rows (subset of previous row's populated columns, adjacent). Merge text. Adaptive thresholds from the table's own row structure. | M | `src/zotero_chunk_rag/table_extraction/postprocessors/continuation_merge.py` |
| 5.4.2 | **Header detection**: Detect header rows using font metadata (`page.get_text("dict")`). Headers have different font size, weight, or style from data rows. Also detect multi-row headers (common in academic tables). Output: which rows are headers, which are data. | M | `src/zotero_chunk_rag/table_extraction/postprocessors/header_detection.py` |
| 5.4.3 | **Footnote stripping**: Extract and improve `_strip_footnote_rows()`. Detect footnote rows at bottom of table using font size change, "Note"/"Source" patterns, spanning cells. Adaptive outlier detection. Store stripped footnotes in `ExtractedTable.footnotes`. | S | `src/zotero_chunk_rag/table_extraction/postprocessors/footnote_strip.py` |
| 5.4.4 | **Inline header fill**: Detect inline sub-headers ("Baseline", "Panel A: Males") that span the full table width. Forward-fill these values into the sub-header column below. Delete the pure-header rows. Produces a flat table with an extra categorical column. | M | `src/zotero_chunk_rag/table_extraction/postprocessors/inline_headers.py` |
| 5.4.5 | **Absorbed caption stripping**: Detect and remove table/figure captions that leaked into the first row(s) of the table grid. Scan rows for caption regex patterns. Do not stop at first non-match (captions can appear after equation rows). Run after internal caption splitting. | S | `src/zotero_chunk_rag/table_extraction/postprocessors/absorbed_caption.py` |
| 5.4.6 | **Header/data separation**: Detect header cells with fused header+data text (e.g., "ZTA R1 9982" where "ZTA R1" is the header and "9982" is data). Split numeric suffixes into a new first data row. Adaptive trigger from header cell content. | S | `src/zotero_chunk_rag/table_extraction/postprocessors/header_data_split.py` |
| 5.4.7 | **Cell text cleaning**: Extract `_clean_cell_text()` and ligature normalization as a post-processor. Decimal recovery, negative sign reassembly, leading zero recovery, whitespace normalization. Applied to all cells uniformly. | S | `src/zotero_chunk_rag/table_extraction/postprocessors/cell_cleaning.py` |

---

## Phase 6: Pipeline Assembly & Evaluation

**Depends on**: Phase 5, Phase 2

### Wave 6.1: Default pipeline and corpus run

| Task | Description | Complexity | Key Files |
|------|-------------|------------|-----------|
| 6.1.1 | Construct the default pipeline configuration: all structure methods AND-combined, all cell methods OR-selected, all post-processors in order (absorbed caption → header detection → header/data split → continuation merge → inline headers → footnote strip → cell cleaning). Write as a named constant `DEFAULT_PIPELINE`. | M | `src/zotero_chunk_rag/table_extraction/pipeline.py` |
| 6.1.2 | Build a corpus evaluation harness: for each table in the corpus, run the pipeline, compare against ground truth, store all intermediate results in the debug DB. Produce a summary report: per-table cell accuracy, per-method win rates (which method's boundaries/cells were selected), overall accuracy. | L | `tests/evaluate_pipeline.py` |
| 6.1.3 | Run evaluation on full corpus. Identify: (a) tables where all methods fail — these need new approaches, (b) tables where only one method succeeds — these validate that method's unique value, (c) tables where combination beats any individual method — these validate the AND architecture. | M | Analysis task — results in `spec/evaluation_report.md` |

### Wave 6.2: Optimization

| Task | Description | Complexity | Key Files |
|------|-------------|------------|-----------|
| 6.2.1 | Implement per-table method activation: analyze table features (has ruled lines? single-column text blocks? dense numeric grid? 2-column layout?) and activate/deactivate methods accordingly. Feature detection runs before the pipeline. Method activation criteria stored as pipeline configuration, not hard-coded. | M | `src/zotero_chunk_rag/table_extraction/pipeline.py`, `src/zotero_chunk_rag/table_extraction/table_features.py` |
| 6.2.2 | Tune boundary combination weights based on corpus evaluation: methods that consistently produce correct boundaries get higher confidence multipliers. This is a data-driven calibration, not manual tuning — the evaluation report from 6.1.3 drives it. | M | `src/zotero_chunk_rag/table_extraction/combination.py` |
| 6.2.3 | Implement pipeline variant testing: define 3-4 pipeline variants (e.g., "all methods", "fast: pymupdf + hotspot only", "ruled: emphasize line detection"). Evaluate each on the full corpus. Produce a comparison showing accuracy vs. speed tradeoffs. | M | `tests/evaluate_pipeline.py` |

---

## Phase 7: Integration & Migration

**Depends on**: Phase 6

### Wave 7.1: Wire into main pipeline

| Task | Description | Complexity | Key Files |
|------|-------------|------------|-----------|
| 7.1.1 | Replace `_extract_tables_native()` in pdf_processor.py with a call to the new pipeline. The new pipeline receives page + bbox (from `find_tables()` or caption detection) and returns `ExtractedTable` objects. Caption matching, artifact classification, and figure-data-table tagging remain in pdf_processor.py. The new pipeline handles everything from boundary detection through post-processing. | L | `src/zotero_chunk_rag/pdf_processor.py`, `src/zotero_chunk_rag/table_extraction/pipeline.py` |
| 7.1.2 | Update `_extract_prose_tables()` to use new pipeline methods for word-based extraction. Prose tables (definition lists, key-value pairs) use the same post-processors but may skip structure detection (they don't have a grid). | M | `src/zotero_chunk_rag/pdf_processor.py` |
| 7.1.3 | Run the full stress test. Target: 0 MAJOR failures, equal or fewer MINOR failures than current baseline (15). All papers grade A. If any regression, investigate and fix before proceeding. | M | `tests/stress_test_real_library.py` |

### Wave 7.2: Cleanup and QA

| Task | Description | Complexity | Key Files |
|------|-------------|------------|-----------|
| 7.2.1 | Remove old table extraction code from pdf_processor.py: `_find_column_gap_threshold()`, `_word_based_column_detection()`, `_extract_cell_text_multi_strategy()`, `_extract_via_rawdict()`, `_extract_via_words()`, `_repair_low_fill_table()`, `_merge_over_divided_rows()`, `_repair_garbled_cells()`, `_score_extraction()`, `_count_decimal_displacement()`, `_count_numeric_integrity()`, and related helpers. Keep only the integration shim that calls the new pipeline. | M | `src/zotero_chunk_rag/pdf_processor.py` |
| 7.2.2 | Run agent-led vision QA: agent renders each corpus table as an image, visually reads it, compares against the pipeline's extraction, flags any discrepancies. Produces a QA report with severity per discrepancy. Any MAJOR discrepancy triggers a fix cycle. | L | Agent task — produces `spec/qa_report.md` |
| 7.2.3 | Update stress test assertions to use ground truth comparisons where applicable. Add new assertions for cell-level accuracy (compare pipeline output against ground truth DB). These become the permanent regression tests for table extraction. | M | `tests/stress_test_real_library.py` |
| 7.2.4 | Update CLAUDE.md architecture section with new module structure, key files, and pipeline documentation. Update MEMORY.md with final design decisions. | S | `CLAUDE.md`, memory files |

---

## Architecture Summary

### Module structure

```
src/zotero_chunk_rag/
├── table_extraction/
│   ├── __init__.py              # Public API: extract_tables(page, bboxes)
│   ├── models.py                # BoundaryHypothesis, BoundaryPoint, CellGrid, etc.
│   ├── protocols.py             # StructureMethod, CellExtractionMethod, PostProcessor
│   ├── pipeline.py              # Pipeline class, DEFAULT_PIPELINE config
│   ├── combination.py           # combine_hypotheses(), consensus voting
│   ├── scoring.py               # score_cell_grid(), quality metrics
│   ├── table_features.py        # Feature detection for method activation
│   ├── ground_truth.py          # Ground truth DB + blind comparison API
│   ├── debug_db.py              # Debug DB extension for intermediate outputs
│   ├── render.py                # Table image renderer for QA
│   ├── methods/
│   │   ├── __init__.py
│   │   ├── _row_clustering.py   # Shared row clustering utility
│   │   ├── word_gap_hotspot.py  # Hotspot consensus column detection
│   │   ├── cliff_detection.py   # Gap cliff / natural break detection
│   │   ├── ruled_lines.py       # pymupdf get_drawings() line detection
│   │   ├── pymupdf_tables.py    # find_tables() wrapper (structure only)
│   │   ├── camelot_extraction.py # Camelot lattice + hybrid
│   │   ├── pdfplumber_extraction.py # pdfplumber structure
│   │   ├── cell_rawdict.py      # rawdict 50% overlap cell extraction
│   │   ├── cell_words.py        # Word assignment cell extraction
│   │   ├── cell_pdfplumber.py   # pdfplumber cell extraction
│   │   ├── cell_camelot.py      # Camelot cell extraction
│   │   └── vision_slot.py       # Placeholder for future vision-model method
│   └── postprocessors/
│       ├── __init__.py
│       ├── continuation_merge.py
│       ├── header_detection.py
│       ├── footnote_strip.py
│       ├── inline_headers.py
│       ├── absorbed_caption.py
│       ├── header_data_split.py
│       └── cell_cleaning.py
├── pdf_processor.py             # Calls table_extraction.pipeline (integration shim)
├── _figure_extraction.py        # Unchanged
├── _gap_fill.py                 # Unchanged
├── _reference_matcher.py        # Unchanged
├── section_classifier.py        # Unchanged
└── models.py                    # ExtractedTable, ExtractedFigure (unchanged interface)
```

### Pipeline composition example

```python
# The default pipeline reads like a narrative:
DEFAULT_PIPELINE = Pipeline(
    structure_methods=[
        WordGapHotspot(),        # Word-position consensus boundaries
        RuledLineDetection(),    # Strong signal from vector graphics
        PyMuPDFTableFinder(),    # Library heuristic boundaries
        CamelotLattice(),        # Raster-based lattice detection
        PdfPlumberStructure(),   # Alternative text-based detection
        CliffDetection(),        # Gap distribution natural breaks
    ],
    cell_methods=[
        RawDictOverlap(),        # Character-level 50% overlap assignment
        WordAssignment(),        # Whole-word column assignment
        PdfPlumberCells(),       # pdfplumber text extraction
        CamelotCells(),          # Camelot/PDFMiner text extraction
    ],
    postprocessors=[
        AbsorbedCaptionStrip(),  # Remove leaked captions
        HeaderDetection(),       # Font-based header identification
        HeaderDataSplit(),       # Separate fused header+data cells
        ContinuationMerge(),     # Merge wrapped multi-line rows
        InlineHeaderFill(),      # Forward-fill sub-group headers
        FootnoteStrip(),         # Remove footnote rows
        CellCleaning(),          # Decimal recovery, ligatures, whitespace
    ],
    combination_strategy="consensus_voting",  # AND for structure
    selection_strategy="best_score",           # OR for cells
)
```

### Boundary AND/OR semantics

**AND (structure methods)**: All methods run. Their `BoundaryHypothesis` objects are combined via `combine_hypotheses()`: cluster nearby boundary points across methods, weight by method confidence, require minimum support threshold (adaptive: fraction of methods that proposed a boundary at that position). Output: consensus `BoundaryHypothesis`.

**OR (cell extraction)**: All cell methods run on the consensus grid. Each produces a `CellGrid` with quality score. Best score wins. If ground truth is available (testing mode), cell accuracy against ground truth is the tiebreaker.

### Vision method slot

The `VisionMethod` implements both `StructureMethod` and `CellExtractionMethod` — it returns complete structure and content from a single vision-model call. When API access is available:
1. Render table bbox as PNG
2. Send to Claude/GPT-4 with structured output schema
3. Parse response into `BoundaryHypothesis` + `CellGrid`
4. Both participate in AND/OR combination with rule-based methods

Until API access is available, `vision_slot.py` is a no-op that returns empty results.

### Agent-led QA loop

Repeatable process for quality assurance:
1. Extract all tables with the automated pipeline
2. Render each table bbox as PNG at 200 DPI
3. Spawn haiku agent per table (or batch)
4. Agent reads image via Read tool → produces expected content
5. Compare agent's reading against pipeline output
6. Flag discrepancies with severity
7. Aggregate into QA report for human review

This runs after any significant pipeline change and when new papers are added to the corpus.
