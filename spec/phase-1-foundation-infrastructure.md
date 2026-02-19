# Phase 1: Foundation & Infrastructure

## Overview

This phase creates the groundwork for the table extraction reengineering. It adds new infrastructure alongside the existing extraction pipeline without modifying it. After this phase completes, Phases 2 (ground truth creation), 3 (core architecture), and 4 (agent QA tooling) can all start in parallel.

Three deliverables:
1. New `table_extraction/` package skeleton with dependencies installed
2. Ground truth SQLite database with a blind, split-aware comparison API
3. Extended debug database schema with ground truth diff reporting wired into the stress test

## Wave 1.1: Project Setup

### Task 1.1.1: Install Camelot and pdfplumber dependencies

- **Description**: Add `camelot-py[base]` and `pdfplumber` as core project dependencies. Verify both import correctly and that Camelot's lattice mode works with the system Ghostscript installation.
- **Files to modify**:
  - `pyproject.toml` — add `camelot-py[base]` and `pdfplumber` to `[project.dependencies]`
- **Tests**:
  - `tests/test_table_extraction/__init__.py` — (empty, makes this a test package)
  - `tests/test_table_extraction/test_dependencies.py::TestDependencies::test_camelot_imports` — assert `import camelot` succeeds and `camelot.__version__` is a non-empty string
  - `tests/test_table_extraction/test_dependencies.py::TestDependencies::test_pdfplumber_imports` — assert `import pdfplumber` succeeds and `pdfplumber.__version__` is a non-empty string
  - `tests/test_table_extraction/test_dependencies.py::TestDependencies::test_camelot_ghostscript` — assert `camelot.read_pdf()` on a trivial single-table PDF (from fixtures) does not raise a Ghostscript-related exception
- **Acceptance criteria**:
  - `"./.venv/Scripts/python.exe" -c "import camelot; import pdfplumber"` exits 0
  - `"./.venv/Scripts/python.exe" -m pytest tests/test_table_extraction/test_dependencies.py` passes all 3 tests
  - No existing tests regress

### Task 1.1.2: Create table_extraction package skeleton

- **Description**: Create the new `table_extraction/` package with empty placeholder modules. Each module contains only a module docstring describing its future purpose. No functional code yet — this establishes the directory structure that later phases populate.
- **Files to create**:
  - `src/zotero_chunk_rag/table_extraction/__init__.py` — package init, docstring: "Table extraction pipeline — composable multi-method extraction with confidence-weighted boundary combination." Empty body.
  - `src/zotero_chunk_rag/table_extraction/models.py` — docstring: "Core data models: BoundaryPoint, BoundaryHypothesis, CellGrid, ExtractionResult." Empty body.
  - `src/zotero_chunk_rag/table_extraction/protocols.py` — docstring: "Method protocols: StructureMethod, CellExtractionMethod, PostProcessor." Empty body.
  - `src/zotero_chunk_rag/table_extraction/pipeline.py` — docstring: "Pipeline class — runs structure methods, combines boundaries, extracts cells, post-processes." Empty body.
  - `src/zotero_chunk_rag/table_extraction/scoring.py` — docstring: "Quality scoring framework for cell grids." Empty body.
  - `src/zotero_chunk_rag/table_extraction/combination.py` — docstring: "Boundary combination engine — consensus voting across structure methods." Empty body.
  - `src/zotero_chunk_rag/table_extraction/ground_truth.py` — placeholder only (populated in Task 1.2.1)
  - `src/zotero_chunk_rag/table_extraction/debug_db.py` — placeholder only (populated in Task 1.3.1)
  - `src/zotero_chunk_rag/table_extraction/render.py` — placeholder only (populated in Task 1.2.3)
  - `src/zotero_chunk_rag/table_extraction/methods/__init__.py` — package init, empty
  - `src/zotero_chunk_rag/table_extraction/postprocessors/__init__.py` — package init, empty
- **Tests**:
  - `tests/test_table_extraction/test_dependencies.py::TestPackageStructure::test_package_importable` — assert `import zotero_chunk_rag.table_extraction` succeeds
  - `tests/test_table_extraction/test_dependencies.py::TestPackageStructure::test_subpackages_importable` — assert `import zotero_chunk_rag.table_extraction.methods` and `import zotero_chunk_rag.table_extraction.postprocessors` both succeed
- **Acceptance criteria**:
  - All 11 files exist at the specified paths
  - `import zotero_chunk_rag.table_extraction` succeeds
  - No existing tests regress

## Wave 1.2: Ground Truth Infrastructure

### Task 1.2.1: Ground truth database schema and creation

- **Description**: Design and implement the ground truth SQLite database. The database stores human-verified "correct answers" for every table in the 10-paper corpus. Each table is identified by a caption-based ID scheme:
  - Captioned tables: `{paper_key}_table_{N}` where N is the parsed caption number (e.g., `SCPXVBLY_table_1`, `SCPXVBLY_table_A1`)
  - Orphan tables (no caption): `{paper_key}_orphan_p{page}_t{index}` (e.g., `SCPXVBLY_orphan_p5_0`)

  The database file lives at `tests/ground_truth.db`.

- **Files to create**:
  - `src/zotero_chunk_rag/table_extraction/ground_truth.py` — replaces placeholder. Contains:
    - `GROUND_TRUTH_DB_PATH` constant pointing to `tests/ground_truth.db`
    - `create_ground_truth_db(db_path: Path) -> None` — creates the database with the schema below if it doesn't exist
    - `make_table_id(paper_key: str, caption: str | None, page_num: int, table_index: int) -> str` — generates a table ID from caption text (parses the caption number) or falls back to orphan format
    - `insert_ground_truth(db_path: Path, table_id: str, paper_key: str, page_num: int, caption: str, headers: list[str], rows: list[list[str]], notes: str = "") -> None` — inserts or replaces a ground truth entry
    - `get_table_ids(db_path: Path, paper_key: str | None = None) -> list[str]` — list all table IDs, optionally filtered by paper

  **Schema:**
  ```sql
  CREATE TABLE ground_truth_tables (
      table_id    TEXT PRIMARY KEY,
      paper_key   TEXT NOT NULL,
      page_num    INTEGER NOT NULL,
      caption     TEXT,
      headers_json TEXT NOT NULL,   -- JSON array of header strings
      rows_json   TEXT NOT NULL,    -- JSON array of arrays of cell strings
      num_rows    INTEGER NOT NULL,
      num_cols    INTEGER NOT NULL,
      notes       TEXT DEFAULT '',
      created_at  TEXT NOT NULL,    -- ISO 8601 timestamp
      verified_by TEXT DEFAULT ''   -- 'human' | 'agent' | ''
  );

  CREATE TABLE ground_truth_meta (
      key   TEXT PRIMARY KEY,
      value TEXT
  );
  ```

- **Tests**:
  - `tests/test_table_extraction/test_ground_truth.py::TestSchema::test_create_db` — call `create_ground_truth_db()` on a temp path, assert the file exists and both tables are present (query `sqlite_master`)
  - `tests/test_table_extraction/test_ground_truth.py::TestSchema::test_create_idempotent` — call `create_ground_truth_db()` twice on the same path, assert no error and data is preserved
  - `tests/test_table_extraction/test_ground_truth.py::TestTableId::test_captioned_table` — `make_table_id("ABC", "Table 1: Results", 5, 0)` returns `"ABC_table_1"`
  - `tests/test_table_extraction/test_ground_truth.py::TestTableId::test_appendix_table` — `make_table_id("ABC", "Table A.1: Appendix data", 12, 0)` returns `"ABC_table_A.1"`
  - `tests/test_table_extraction/test_ground_truth.py::TestTableId::test_supplementary_table` — `make_table_id("ABC", "Table S2. Extra", 3, 0)` returns `"ABC_table_S2"`
  - `tests/test_table_extraction/test_ground_truth.py::TestTableId::test_orphan_table` — `make_table_id("ABC", None, 5, 0)` returns `"ABC_orphan_p5_t0"`
  - `tests/test_table_extraction/test_ground_truth.py::TestTableId::test_synthetic_caption` — `make_table_id("ABC", "Uncaptioned table on page 5", 5, 0)` returns `"ABC_orphan_p5_t0"` (synthetic captions treated as orphans)
  - `tests/test_table_extraction/test_ground_truth.py::TestInsert::test_insert_and_retrieve` — insert a ground truth entry, query it back, assert headers and rows match
  - `tests/test_table_extraction/test_ground_truth.py::TestInsert::test_insert_replaces` — insert twice with same table_id but different data, assert the latest data is stored
  - `tests/test_table_extraction/test_ground_truth.py::TestInsert::test_get_table_ids_filtered` — insert entries for two papers, call `get_table_ids(paper_key="ABC")`, assert only ABC's entries returned
- **Acceptance criteria**:
  - `create_ground_truth_db()` creates a valid SQLite database with the specified schema
  - `make_table_id()` correctly parses caption numbers for standard (`Table 1`), appendix (`Table A.1`), supplementary (`Table S2`), Roman numeral (`Table IV`), and orphan cases
  - `insert_ground_truth()` stores and retrieves data with exact fidelity (JSON round-trip preserves all cell values)
  - All 10 tests pass

### Task 1.2.2: Blind comparison API with split-aware alignment

- **Description**: Build the comparison API that takes an extraction attempt and a ground truth table ID, and returns a structured diff. The API never exposes raw ground truth data — only diffs.

  **Cell normalization** (applied to both GT and extraction before comparison):
  1. Strip leading/trailing whitespace
  2. Collapse internal whitespace to single space
  3. Unicode minus (−) → ASCII hyphen (-)
  4. Ligature normalization (ff → ff, fi → fi, fl → fl, ffi → ffi, ffl → ffl)

  **Column alignment**: Match extraction columns to GT columns by normalized header text. Use exact normalized match first, then longest-common-substring fallback for partial matches. Unmatched columns reported as extra (extraction) or missing (GT).

  **Row alignment**: Top-to-bottom sequential alignment with split/merge detection:
  - **Split detection**: When an extraction row partially matches a GT row, check if the next extraction row(s) contain the remaining content. If concatenating adjacent extraction rows matches the GT row, report as a row split.
  - **Merge detection**: When an extraction row contains content from two GT rows, report as a row merge.
  - Aligned rows contribute to cell accuracy. Split and merged rows/columns are diagnosed for debugging but their cells count as **0% accurate** (failures).

  **Accuracy**: `cell_accuracy_pct = correct_cells / total_gt_cells × 100`. Cells in split/merged rows and columns count as incorrect (0%). Only cells on successfully 1:1 aligned rows and columns can be correct.

- **Files to modify**:
  - `src/zotero_chunk_rag/table_extraction/ground_truth.py` — add:
    - `@dataclass CellDiff(row: int, col: int, expected: str, actual: str)` — a single cell mismatch
    - `@dataclass SplitInfo(gt_index: int, ext_indices: list[int])` — one GT row/col split into multiple extraction rows/cols
    - `@dataclass MergeInfo(gt_indices: list[int], ext_index: int)` — multiple GT rows/cols merged into one extraction row/col
    - `@dataclass ComparisonResult` with fields:
      - `table_id: str`
      - `gt_shape: tuple[int, int]` — (rows, cols) of ground truth
      - `ext_shape: tuple[int, int]` — (rows, cols) of extraction
      - `matched_columns: list[tuple[int, int]]` — (gt_col_idx, ext_col_idx) pairs
      - `extra_columns: list[int]` — extraction column indices with no GT match
      - `missing_columns: list[int]` — GT column indices with no extraction match
      - `column_splits: list[SplitInfo]` — GT columns that were split in extraction
      - `column_merges: list[MergeInfo]` — GT columns that were merged in extraction
      - `matched_rows: list[tuple[int, int]]` — (gt_row_idx, ext_row_idx) pairs
      - `extra_rows: list[int]` — extraction row indices with no GT match
      - `missing_rows: list[int]` — GT row indices with no extraction match
      - `row_splits: list[SplitInfo]` — GT rows split into multiple extraction rows
      - `row_merges: list[MergeInfo]` — GT rows merged into single extraction row
      - `cell_diffs: list[CellDiff]` — individual cell mismatches on aligned cells
      - `cell_accuracy_pct: float` — correct cells / total GT cells × 100
      - `header_diffs: list[CellDiff]` — header-level mismatches
    - `_normalize_cell(text: str) -> str` — applies the 4-step normalization
    - `compare_extraction(db_path: Path, table_id: str, headers: list[str], rows: list[list[str]]) -> ComparisonResult` — the main comparison function. Loads GT from DB, aligns, diffs, returns result. Raises `KeyError` if `table_id` not found in DB.
- **Tests**:
  - `tests/test_table_extraction/test_ground_truth.py::TestNormalize::test_whitespace` — `_normalize_cell("  hello  world  ")` returns `"hello world"`
  - `tests/test_table_extraction/test_ground_truth.py::TestNormalize::test_unicode_minus` — `_normalize_cell("−0.5")` returns `"-0.5"`
  - `tests/test_table_extraction/test_ground_truth.py::TestNormalize::test_ligatures` — `_normalize_cell("effi\ucient")` normalizes the ffi ligature
  - `tests/test_table_extraction/test_ground_truth.py::TestCompare::test_perfect_match` — extraction exactly matches GT → `cell_accuracy_pct == 100.0`, empty diffs lists
  - `tests/test_table_extraction/test_ground_truth.py::TestCompare::test_cell_mismatch` — one cell differs → `cell_accuracy_pct < 100.0`, `cell_diffs` has one entry with correct row/col/expected/actual
  - `tests/test_table_extraction/test_ground_truth.py::TestCompare::test_extra_column` — extraction has 1 extra column → `extra_columns` has 1 entry, accuracy denominator is total GT cells
  - `tests/test_table_extraction/test_ground_truth.py::TestCompare::test_missing_column` — extraction missing 1 column → `missing_columns` has 1 entry, all cells in that GT column count as incorrect
  - `tests/test_table_extraction/test_ground_truth.py::TestCompare::test_row_split_detection` — GT row "A B C" appears in extraction as two rows "A B" + "C" → `row_splits` has 1 entry, those cells count as 0% accurate
  - `tests/test_table_extraction/test_ground_truth.py::TestCompare::test_column_split_detection` — GT has header "BMI" but extraction has "BM" + "I" → `column_splits` has 1 entry
  - `tests/test_table_extraction/test_ground_truth.py::TestCompare::test_split_cells_count_as_wrong` — any split/merged dimension → cells in those dimensions are excluded from correct count, accuracy reflects this
  - `tests/test_table_extraction/test_ground_truth.py::TestCompare::test_table_not_found` — `compare_extraction()` with unknown table_id raises `KeyError`
  - `tests/test_table_extraction/test_ground_truth.py::TestCompare::test_header_alignment` — columns matched by normalized header text, not position. Extraction columns in different order still match correctly.
- **Acceptance criteria**:
  - `compare_extraction()` returns a `ComparisonResult` that correctly reports cell-level accuracy
  - Split and merged rows/columns are detected and reported, with their cells counting as 0% accurate
  - Column alignment is by header text similarity, not position
  - The API never returns raw ground truth cell values — only the comparison diff (CellDiff contains expected vs actual, but only for cells that were compared)
  - All 12 tests pass

### Task 1.2.3: Table image renderer

- **Description**: Render a specific table region from a PDF page as a PNG image at 300 DPI. Used by the ground truth creation workflow (Phase 2) and agent QA (Phase 4). Renders the bbox area with padding to include surrounding context (captions above/below).
- **Files to modify**:
  - `src/zotero_chunk_rag/table_extraction/render.py` — replaces placeholder. Contains:
    - `render_table_image(pdf_path: Path | str, page_num: int, bbox: tuple[float, float, float, float], output_path: Path, *, dpi: int = 300, padding: int = 20) -> Path` — renders the specified region as PNG. `page_num` is 1-indexed (consistent with the rest of the codebase). `padding` is in PDF points added around the bbox before rendering. Clips to page bounds. Returns the output path.
    - `render_all_tables(pdf_path: Path | str, tables: list[ExtractedTable], output_dir: Path, *, dpi: int = 300) -> dict[str, Path]` — renders all non-artifact tables from an extraction result. Returns `{table_caption_or_id: output_path}` mapping.
- **Tests**:
  - `tests/test_table_extraction/test_render.py::TestRender::test_renders_png` — render a table from `tests/fixtures/papers/noname1.pdf` page 7 (which has Table 1), assert output file exists and is a valid PNG (check file header bytes `\x89PNG`)
  - `tests/test_table_extraction/test_render.py::TestRender::test_output_dimensions` — rendered image width and height are > 0 (use PIL/pymupdf to read dimensions)
  - `tests/test_table_extraction/test_render.py::TestRender::test_padding_expands_region` — render with padding=0 and padding=40, assert the padded image has larger dimensions
  - `tests/test_table_extraction/test_render.py::TestRender::test_clips_to_page` — render with a bbox that extends beyond page bounds (e.g., negative x0), assert no error and image has valid dimensions
  - `tests/test_table_extraction/test_render.py::TestRender::test_page_num_one_indexed` — render page_num=1 of a known PDF, assert it renders the first page (not the second)
- **Acceptance criteria**:
  - `render_table_image()` produces a valid PNG file at the specified path
  - Image is rendered at 300 DPI by default, producing files in the ~500KB range for typical academic tables
  - Padding clips to page bounds (no crash on edge tables)
  - `page_num` is 1-indexed, consistent with the rest of the codebase
  - All 5 tests pass

## Wave 1.3: Debug Database Extension

### Task 1.3.1: Extend debug database schema and wire ground truth diffs

- **Description**: Extend the `_stress_test_debug.db` schema with three new tables for storing per-method extraction results, pipeline run metadata, and ground truth comparison diffs. Wire ground truth comparisons into the existing stress test so that every run automatically compares extracted tables against ground truth (when ground truth exists) and writes the results to the debug DB and the test report.

  The method_results and pipeline_runs tables will be empty until Phase 5+ when pipeline methods are implemented. The ground_truth_diffs table is populated immediately by the stress test.

- **Files to create**:
  - `src/zotero_chunk_rag/table_extraction/debug_db.py` — replaces placeholder. Contains:
    - `EXTENDED_SCHEMA` — SQL string with CREATE TABLE statements for the three new tables (see schema below)
    - `create_extended_tables(con: sqlite3.Connection) -> None` — executes the schema on an existing connection
    - `write_method_result(con, table_id, method_name, boundaries_json, cell_grid_json, quality_score, execution_time_ms) -> None` — inserts a method result row
    - `write_pipeline_run(con, table_id, pipeline_config_json, winning_method, final_score) -> None` — inserts a pipeline run row
    - `write_ground_truth_diff(con, table_id, run_id, comparison_result: ComparisonResult) -> None` — serializes a `ComparisonResult` to JSON and inserts a ground truth diff row

  **New schema:**
  ```sql
  CREATE TABLE IF NOT EXISTS method_results (
      id                      INTEGER PRIMARY KEY AUTOINCREMENT,
      table_id                TEXT NOT NULL,
      method_name             TEXT NOT NULL,
      boundary_hypotheses_json TEXT,
      cell_grid_json          TEXT,
      quality_score           REAL,
      execution_time_ms       INTEGER
  );

  CREATE TABLE IF NOT EXISTS pipeline_runs (
      id                  INTEGER PRIMARY KEY AUTOINCREMENT,
      table_id            TEXT NOT NULL,
      pipeline_config_json TEXT,
      winning_method      TEXT,
      final_score         REAL
  );

  CREATE TABLE IF NOT EXISTS ground_truth_diffs (
      id                INTEGER PRIMARY KEY AUTOINCREMENT,
      table_id          TEXT NOT NULL,
      run_id            TEXT NOT NULL,
      diff_json         TEXT NOT NULL,
      cell_accuracy_pct REAL,
      num_splits        INTEGER,
      num_merges        INTEGER,
      num_cell_diffs    INTEGER,
      gt_shape          TEXT,
      ext_shape         TEXT
  );
  ```

- **Files to modify**:
  - `tests/stress_test_real_library.py` — modify `write_debug_database()` to:
    1. Import `create_extended_tables` from `table_extraction.debug_db` and call it after creating the existing schema
    2. Import `compare_extraction` and `make_table_id` from `table_extraction.ground_truth`
    3. After writing each paper's extracted_tables, check if `tests/ground_truth.db` exists
    4. If it exists, for each non-artifact extracted table: generate a `table_id` via `make_table_id()`, attempt `compare_extraction()`, and if the table_id exists in ground truth, write the diff to `ground_truth_diffs`
    5. Add a ground truth summary section to the report output: per-table cell accuracy percentage, number of splits/merges detected, and overall corpus accuracy
    6. Ground truth comparison results are reported as factual data in the test output (no MAJOR/MINOR severity classification)
- **Tests**:
  - `tests/test_table_extraction/test_debug_db.py::TestSchema::test_creates_tables` — call `create_extended_tables()` on an in-memory DB, assert all 3 tables exist in `sqlite_master`
  - `tests/test_table_extraction/test_debug_db.py::TestSchema::test_idempotent` — call twice, assert no error
  - `tests/test_table_extraction/test_debug_db.py::TestWrite::test_write_method_result` — insert a method result, query it back, assert all fields match
  - `tests/test_table_extraction/test_debug_db.py::TestWrite::test_write_ground_truth_diff` — create a `ComparisonResult` with known values, write it, query back, assert `cell_accuracy_pct` and `num_splits` match
  - `tests/test_table_extraction/test_debug_db.py::TestWrite::test_write_pipeline_run` — insert a pipeline run, query back, assert fields match
- **Acceptance criteria**:
  - `create_extended_tables()` adds 3 new tables to an existing SQLite connection without affecting existing tables
  - `write_ground_truth_diff()` correctly serializes a `ComparisonResult` including accuracy, split count, merge count, and full diff JSON
  - The stress test creates the extended tables and writes ground truth diffs when `tests/ground_truth.db` exists
  - The stress test report includes a ground truth comparison section showing per-table cell accuracy
  - When `tests/ground_truth.db` does not exist, the stress test runs normally without errors (graceful skip)
  - All 5 tests pass
  - Existing stress test behavior is unchanged when no ground truth DB exists
