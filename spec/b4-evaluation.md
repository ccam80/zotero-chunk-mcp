# Phase B4: Evaluation

## Overview

Create the unit test suite for all paddle extraction components (parsers,
matching, factory) and integrate PaddleOCR extraction into the stress test
alongside vision results. Paddle extraction runs concurrently with the
vision batch API poll to avoid adding wall-clock time.

---

## Wave 1: Unit Test Suite

### Task 1.1: Create tests/test_paddle_extract.py

- **Description**: Consolidate all unit tests defined in B1–B3 specs into a
  single test file. Parser and matching tests use synthetic inputs, but
  PaddleOCR must be installed and GPU available (module-level imports in
  engine files, factory tests load real models).
- **Files to create**:
  - `tests/test_paddle_extract.py` — test classes:
    - `TestImports` (3 tests from B1 Task 1.1)
    - `TestRawPaddleTable` (1 test from B1 Task 1.2)
    - `TestEngineFactory` (3 tests from B1 Task 1.2)
    - `TestHTMLParser` (8 tests from B1 Task 2.1)
    - `TestMarkdownParser` (7 tests from B1 Task 2.2)
    - `TestMatchedPaddleTable` (2 tests from B3 Task 1.1)
    - `TestCaptionMatching` (6 tests from B3 Task 1.2)
- **Tests**: All tests enumerated in B1–B3 specs (30 total)
- **Acceptance criteria**:
  - `"./.venv/Scripts/python.exe" -m pytest tests/test_paddle_extract.py -v`
    runs all 30 tests
  - PaddleOCR installed and GPU available (import and factory tests load
    real engines — module-level imports mean PaddleOCR must be present)
  - HTML parser tests use raw HTML strings as input (but PaddleOCR must
    be importable since parsers live inside engine files)
  - Markdown parser tests use raw markdown strings (same caveat)
  - Caption matching tests use synthetic `RawPaddleTable` and
    `DetectedCaption` instances with known coordinates
  - Engine factory tests verify dispatch and protocol conformance —
    `get_engine()` returns real engine instances with loaded models
  - Zero external API calls or network requests

---

## Wave 2: Debug Database Extensions

### Task 2.1: Add paddle tables to debug_db.py

- **Description**: Add database tables and write functions for storing
  PaddleOCR extraction results and GT comparison diffs in the stress test
  debug database.
- **Files to modify**:
  - `src/zotero_chunk_rag/feature_extraction/debug_db.py` — add:
    - `paddle_results` table schema:
      - `table_id TEXT` (from `make_table_id()`)
      - `page_num INTEGER`
      - `engine_name TEXT`
      - `caption TEXT`
      - `is_orphan INTEGER` (0/1)
      - `headers_json TEXT`
      - `rows_json TEXT`
      - `bbox TEXT` (JSON of pixel bbox)
      - `page_size TEXT` (JSON of pixel page dimensions)
      - `raw_output TEXT`
      - `item_key TEXT` (paper identifier)
    - `paddle_gt_diffs` table schema:
      - `table_id TEXT`
      - `engine_name TEXT`
      - `cell_accuracy_pct REAL`
      - `fuzzy_accuracy_pct REAL`
      - `num_splits INTEGER`
      - `num_merges INTEGER`
      - `num_cell_diffs INTEGER`
      - `gt_shape TEXT`
      - `ext_shape TEXT`
      - `diff_json TEXT` (full serialized `ComparisonResult`)
    - `write_paddle_result(db_path, result_dict)` function
    - `write_paddle_gt_diff(db_path, diff_dict)` function
    - Table creation added to existing `create_tables()` or equivalent
      initialization function
- **Tests**:
  - `tests/test_paddle_extract.py::TestDebugDB::test_write_paddle_result` —
    write a result dict to temp DB, read back, assert all fields match
  - `tests/test_paddle_extract.py::TestDebugDB::test_write_paddle_gt_diff` —
    write a diff dict to temp DB, read back, assert accuracy and counts match
- **Acceptance criteria**:
  - Both tables created alongside existing debug DB tables
  - Write functions handle all fields without errors
  - Existing debug DB tables and functions unchanged

---

## Wave 3: Stress Test Integration

### Task 3.1: Add paddle extraction to stress test flow

- **Description**: Add PaddleOCR extraction to the stress test. Runs during
  the vision batch API wait time using `threading.Thread`. Processes the
  same 10-paper corpus, matches tables to captions, compares against GT,
  and writes results to the debug DB.
- **Files to modify**:
  - `tests/stress_test_real_library.py`:
    - Add imports: `get_engine`, `match_tables_to_captions`,
      `MatchedPaddleTable` from `feature_extraction.paddle_extract`;
      `write_paddle_result`, `write_paddle_gt_diff` from
      `feature_extraction.debug_db`; `threading`
    - Add `_extract_with_paddle(corpus, engine_name="pp_structure_v3")`:
      1. Initialize engine via `get_engine(engine_name)`
      2. For each paper in corpus:
         a. Open PDF with PyMuPDF
         b. Run `find_all_captions()` per page → build `captions_by_page`
         c. Collect `page_rects` from `page.rect`
         d. Run `engine.extract_tables(pdf_path)`
         e. Run `match_tables_to_captions(raw_tables, captions_by_page,
            page_rects)`
      3. Return `dict[str, list[MatchedPaddleTable]]` keyed by item_key
    - Restructure extraction phases:
      1. Phase 1: `extract_document()` for all papers (unchanged)
      2. Phase 2a: Start `_extract_with_paddle()` in
         `threading.Thread(target=..., args=...)` → `paddle_thread`
      3. Phase 2b: `resolve_pending_vision()` (blocking, main thread)
      4. Phase 2c: `paddle_thread.join()` — collect paddle results
      5. Phase 3: Index vision results (unchanged)
      6. Phase 4: Run paddle GT comparisons and DB writes
    - Add `_test_paddle_extraction(paddle_results, db_path)`:
      - For each matched table with a caption number:
        generate `table_id` via `make_table_id()`
      - Run `compare_extraction(GROUND_TRUTH_DB_PATH, table_id, headers,
        rows)` for each table that has a GT entry (first param is a `Path`,
        not a connection)
      - Write results to `paddle_results` and `paddle_gt_diffs` DB tables
      - Record assertions in `test_results` table
    - Paddle-specific assertions:
      - **MAJOR**: Each GT table has a corresponding paddle extraction
        (no GT table left unmatched)
      - **MAJOR**: Each matched GT table has `cell_accuracy_pct > 0`
        (extraction produced non-empty content)
      - **MINOR**: Per-table cell accuracy recorded (tracked, no threshold)
      - **MINOR**: Orphan count per paper recorded
- **Tests**: Assertions run as part of the stress test (not pytest)
- **Acceptance criteria**:
  - Paddle extraction runs in a background thread during vision batch poll
  - Same 10-paper corpus, same GT tables, same `compare_extraction()` call
  - Results written to `paddle_results` and `paddle_gt_diffs` DB tables
  - Paddle assertions added to `test_results` table with appropriate severity
  - Stress test completes without errors; paddle thread exceptions surface
    clearly (not silently swallowed)
  - If vision API is unavailable (no API key), paddle extraction still runs
    (thread starts immediately, no vision phase to wait on)
