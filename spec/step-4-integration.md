# Step 4: Integration

## Overview

Wire the vision extraction path (Steps 1–3) into the document extraction
pipeline. After this step, `extract_document()` produces tables via the
Anthropic Batch API when an API key is available, and returns empty tables
when it is not.

**Precondition**: Phase 0 must be complete (specifically: `feature_extraction/models.py`
and `feature_extraction/render.py` must be deleted from disk, and all pipeline
imports removed from production code). If these files still exist, Task 4.1.1
will fail because `cell_cleaning.py`'s `from ..models import CellGrid` will
succeed instead of being absent — the task assumes the import is already broken.

**Files modified**:
- `src/zotero_chunk_rag/feature_extraction/postprocessors/cell_cleaning.py`
- `src/zotero_chunk_rag/feature_extraction/debug_db.py`
- `src/zotero_chunk_rag/pdf_processor.py`
- `src/zotero_chunk_rag/models.py`
- `src/zotero_chunk_rag/indexer.py`
- `tests/test_feature_extraction/test_pp_cell_cleaning.py`
- `tests/stress_test_real_library.py`

---

## Wave 4.1: Cell cleaning refactor

Independent of Steps 1–3. Removes the `CellGrid` dependency so
`cell_cleaning.py` works as a standalone normalization library.

### Task 4.1.1: Refactor `cell_cleaning.py` to standalone functions

- **Description**: Delete the `CellCleaning` class and the `CellGrid` import.
  Add a new top-level `clean_cells()` function that applies ligature
  normalization, negative-sign reassembly, leading-zero recovery, whitespace
  normalization, and Unicode minus replacement to headers and rows.
  `_map_control_chars` stays in the module but is NOT called by `clean_cells()`
  — it is a text-layer artifact irrelevant for vision output (vision agents
  read from images, not font-encoded text).

- **Files to modify**:
  - `src/zotero_chunk_rag/feature_extraction/postprocessors/cell_cleaning.py`:
    - **Delete**: `from ..models import CellGrid` (line 11)
    - **Delete**: `CellCleaning` class entirely (lines 158–205)
    - **Add**: `clean_cells()` function (see below)

- **New function**:
  ```python
  def clean_cells(
      headers: list[str],
      rows: list[list[str]],
  ) -> tuple[list[str], list[list[str]]]:
      """Apply text normalization to table headers and rows.

      Applies (in order):
      1. Ligature normalization (ffi → ffi, etc.)
      2. Negative sign reassembly (split minus signs)
      3. Leading zero recovery (.047 → 0.047)
      4. Whitespace normalization (collapse, strip, newline → space)
      5. Unicode minus → ASCII hyphen-minus

      Does NOT apply control character mapping (_map_control_chars) —
      that function requires font metadata from the PDF text layer,
      which is unavailable for vision-extracted tables.

      Returns:
          (cleaned_headers, cleaned_rows) with same dimensions as input.
      """
  ```

- **Kept unchanged**: `_normalize_ligatures`, `_recover_leading_zeros`,
  `_reassemble_negative_signs`, `_map_control_chars`, `_looks_numeric`,
  all regex constants, `_LIGATURE_MAP`. These are standalone functions
  that other modules import directly (e.g., `pdf_processor.py` imports
  `_normalize_ligatures` at line 950).

- **Tests**:
  - `tests/test_feature_extraction/test_pp_cell_cleaning.py::TestCleanCells::test_ligature_normalization`
    — `clean_cells(["\ufb03ciency"], [["\ufb03cient", "e\ufb00ect"]])`.
    Assert: headers `== ["efficiency"]`; row 0 `== ["fficient", "effect"]`.
  - `tests/test_feature_extraction/test_pp_cell_cleaning.py::TestCleanCells::test_leading_zero`
    — `clean_cells(["A", "B"], [[".047", ".95"]])`.
    Assert: row 0 `== ["0.047", "0.95"]`.
  - `tests/test_feature_extraction/test_pp_cell_cleaning.py::TestCleanCells::test_leading_zero_guard`
    — `clean_cells(["A"], [[".txt"]])`.
    Assert: row 0, cell 0 `== ".txt"` (not numeric, unchanged).
  - `tests/test_feature_extraction/test_pp_cell_cleaning.py::TestCleanCells::test_negative_reassembly`
    — `clean_cells(["A"], [["\u2212 0.45"]])`.
    Assert: row 0, cell 0 `== "-0.45"`.
  - `tests/test_feature_extraction/test_pp_cell_cleaning.py::TestCleanCells::test_whitespace`
    — `clean_cells(["A"], [["  hello   world  ", "a\nb"]])`.
    Assert: row 0 `== ["hello world", "a b"]`.
  - `tests/test_feature_extraction/test_pp_cell_cleaning.py::TestCleanCells::test_unicode_minus`
    — `clean_cells(["A"], [["\u2212"]])`.
    Assert: row 0, cell 0 `== "-"`.
  - `tests/test_feature_extraction/test_pp_cell_cleaning.py::TestCleanCells::test_dimensions_preserved`
    — 3 headers, 2 rows of 3 cells each. Assert: output has 3 headers,
    2 rows, each row has 3 cells.
  - `tests/test_feature_extraction/test_pp_cell_cleaning.py::TestCleanCells::test_empty_input`
    — `clean_cells([], [])`. Assert: returns `([], [])`.

- **Acceptance criteria**:
  - `from ..models import CellGrid` no longer appears in the file
  - `CellCleaning` class no longer exists
  - `clean_cells()` is importable and applies all 5 normalization steps
  - `_map_control_chars` is NOT called by `clean_cells()`
  - `_normalize_ligatures` is still independently importable (used by `pdf_processor.py`)


---

### Task 4.1.2: Rewrite `test_pp_cell_cleaning.py`

- **Description**: Remove the `CellGrid` import, `_make_grid` helper, and
  `CellCleaning` class tests. Replace with tests for `clean_cells()` (from
  Task 4.1.1) and keep standalone function tests unchanged.

- **Files to modify**:
  - `tests/test_feature_extraction/test_pp_cell_cleaning.py`:
    - **Delete**: `from zotero_chunk_rag.feature_extraction.models import CellGrid` (line 6)
    - **Delete**: `from ... import CellCleaning` (line 8)
    - **Delete**: `_make_grid()` helper (lines 16–26)
    - **Delete**: `TestCellCleaning` class entirely (lines 29–135)
    - **Add**: `from ... import clean_cells` to imports
    - **Add**: `TestCleanCells` class with tests from Task 4.1.1
    - **Keep**: Standalone function tests if any exist outside the class
      (`_normalize_ligatures`, `_recover_leading_zeros`, etc.)

- **Acceptance criteria**:
  - No `CellGrid` import in the test file
  - No `CellCleaning` import in the test file
  - `TestCleanCells` class with tests from Task 4.1.1 present

---

## Wave 4.2: Debug DB pruning

Independent of Steps 1–3. Removes pipeline-specific tables and write
functions that reference deleted extraction methods.

### Task 4.2.1: Delete pipeline tables and functions from `debug_db.py`

- **Description**: Remove the `method_results`, `pipeline_runs`, and
  `vision_consensus` tables from `EXTENDED_SCHEMA` and delete their
  corresponding write functions. Keep `ground_truth_diffs` (used by
  stress test GT comparison) and `vision_agent_results` (used for
  single-agent vision reporting).

- **Files to modify**:
  - `src/zotero_chunk_rag/feature_extraction/debug_db.py`:
    - **Delete from `EXTENDED_SCHEMA`**: `CREATE TABLE IF NOT EXISTS method_results (...)` block
    - **Delete from `EXTENDED_SCHEMA`**: `CREATE TABLE IF NOT EXISTS pipeline_runs (...)` block
    - **Delete from `EXTENDED_SCHEMA`**: `CREATE TABLE IF NOT EXISTS vision_consensus (...)` block
    - **Delete function**: `write_method_result()` (lines 91–108)
    - **Delete function**: `write_pipeline_run()` (lines 111–124)
    - **Delete function**: `write_vision_consensus()` (lines 208–233)
    - **Keep**: `create_extended_tables()`, `write_ground_truth_diff()`,
      `write_vision_agent_result()`

- **Tests**:
  - `tests/test_feature_extraction/test_debug_db.py::TestPrunedSchema::test_no_method_results_table`
    — Create extended tables on an in-memory DB. Assert:
    `"method_results"` is NOT in `sqlite_master` table names.
  - `tests/test_feature_extraction/test_debug_db.py::TestPrunedSchema::test_no_pipeline_runs_table`
    — Same. Assert: `"pipeline_runs"` not in table names.
  - `tests/test_feature_extraction/test_debug_db.py::TestPrunedSchema::test_no_vision_consensus_table`
    — Same. Assert: `"vision_consensus"` not in table names.
  - `tests/test_feature_extraction/test_debug_db.py::TestPrunedSchema::test_kept_tables_exist`
    — Assert: `"ground_truth_diffs"` and `"vision_agent_results"` ARE in
    table names.
  - `tests/test_feature_extraction/test_debug_db.py::TestPrunedExports::test_deleted_functions_not_importable`
    — Assert: `write_method_result`, `write_pipeline_run`, `write_vision_consensus`
    are NOT importable from `debug_db` (raise `ImportError` or `AttributeError`).

- **Acceptance criteria**:
  - `EXTENDED_SCHEMA` contains only `ground_truth_diffs` and `vision_agent_results`
  - Three write functions deleted; two kept
  - `create_extended_tables()` still works on a fresh DB


---

### Task 4.2.2: Add `vision_run_details` table to `debug_db.py`

- **Description**: Add a new table to store the full per-table vision extraction
  detail blob. This is the primary data source for the vision extraction report
  in the stress test — it stores re-crop status, caption changes, crop bboxes,
  and other per-table metadata that `vision_agent_results` does not carry.

- **Files to modify**:
  - `src/zotero_chunk_rag/feature_extraction/debug_db.py`:
    - **Add to `EXTENDED_SCHEMA`**:
      ```sql
      CREATE TABLE IF NOT EXISTS vision_run_details (
          table_id TEXT PRIMARY KEY,
          text_layer_caption TEXT,
          vision_caption TEXT,
          page_num INTEGER,
          crop_bbox_json TEXT,
          recropped BOOLEAN DEFAULT 0,
          recrop_bbox_pct_json TEXT,
          parse_success BOOLEAN,
          is_incomplete BOOLEAN,
          incomplete_reason TEXT,
          recrop_needed BOOLEAN,
          raw_response TEXT,
          headers_json TEXT,
          rows_json TEXT,
          footnotes TEXT,
          table_label TEXT
      )
      ```
    - **Add function**: `write_vision_run_detail(con, *, table_id, details_dict)`
      — takes a `vision_details` dict (the schema from Task 4.3.1) and inserts
      it into the table. Uses `INSERT OR REPLACE` for idempotency.

- **Tests**:
  - `tests/test_feature_extraction/test_debug_db.py::TestVisionRunDetails::test_table_created`
    — Create extended tables on an in-memory DB. Assert:
    `"vision_run_details"` IS in `sqlite_master` table names.
  - `tests/test_feature_extraction/test_debug_db.py::TestVisionRunDetails::test_write_and_read`
    — Write a detail dict, read it back. Assert: `recropped == True`,
    `text_layer_caption` matches, `vision_caption` matches.
  - `tests/test_feature_extraction/test_debug_db.py::TestVisionRunDetails::test_upsert`
    — Write a detail dict twice with different `recropped` values. Assert:
    second write overwrites first.

- **Acceptance criteria**:
  - `vision_run_details` table created by `create_extended_tables()`
  - `write_vision_run_detail()` is importable and writes correctly


---

## Wave 4.3: Core integration

Depends on Steps 1–3 (caption detection, vision extraction module, API layer)
and Wave 4.1 (cell cleaning refactor).

### Task 4.3.1: Add `vision_details` field to `DocumentExtraction`

- **Description**: Add an optional field to carry per-table vision extraction
  details through to callers (stress test, debug tooling). Uses plain dicts
  to avoid importing `AgentResponse` into the models module.

- **Files to modify**:
  - `src/zotero_chunk_rag/models.py` — add field to `DocumentExtraction`:
    ```python
    @dataclass
    class DocumentExtraction:
        pages: list[PageExtraction]
        full_markdown: str
        sections: list[SectionSpan]
        tables: list[ExtractedTable]
        figures: list[ExtractedFigure]
        stats: dict
        quality_grade: str
        completeness: ExtractionCompleteness | None = None
        vision_details: list[dict] | None = None
    ```

- **Vision detail dict schema** (populated by `extract_document()`, consumed
  by the stress test and written to the `vision_run_details` debug DB table):
  ```python
  {
      "text_layer_caption": str,   # DetectedCaption.text (original)
      "vision_caption": str,       # AgentResponse.caption (enriched)
      "page_num": int,
      "crop_bbox": list[float],    # [x0, y0, x1, y1]
      "recropped": bool,
      "recrop_bbox_pct": list[float] | None,  # [x0, y0, x1, y1] 0-100 pct
      "parse_success": bool,
      "is_incomplete": bool,
      "incomplete_reason": str,
      "recrop_needed": bool,
      "raw_response": str,
      "headers": list[str],
      "rows": list[list[str]],
      "footnotes": str,
      "table_label": str | None,
  }
  ```

- **Tests**:
  - `tests/test_models.py::TestDocumentExtraction::test_vision_details_default_none`
    — Construct a `DocumentExtraction` without `vision_details`. Assert:
    `extraction.vision_details is None`.
  - `tests/test_models.py::TestDocumentExtraction::test_vision_details_accepts_list`
    — Construct with `vision_details=[{"text_layer_caption": "Table 1", ...}]`.
    Assert: `len(extraction.vision_details) == 1`.

- **Acceptance criteria**:
  - `DocumentExtraction` has `vision_details` field defaulting to `None`
  - Existing code that constructs `DocumentExtraction` without the field
    continues to work (default None)


---

### Task 4.3.2: Rewire `extract_document()` for vision extraction

- **Description**: Replace the `tables: list[ExtractedTable] = []` stub with
  a full vision extraction path: find captions per page, compute crops, build
  `TableVisionSpec` objects, batch-extract via `VisionAPI`, handle re-crops
  (max 1 retry per table), convert `AgentResponse` to `ExtractedTable` with
  cell cleaning, and populate `vision_details` for debug.

  When `vision_api is None`, tables remain `[]` (same as current stub).

  Caption handling: the vision agent's `caption` field (read from the image)
  is used for `ExtractedTable.caption`. If the vision caption is empty,
  fall back to the text-layer caption from `DetectedCaption.text`.

- **Files to modify**:
  - `src/zotero_chunk_rag/pdf_processor.py`:
    - **Add imports** (at top or inline):
      ```python
      from .feature_extraction.vision_extract import (
          compute_all_crops,
          compute_recrop_bbox,
      )
      from .feature_extraction.postprocessors.cell_cleaning import clean_cells
      ```
      `VisionAPI` and `TableVisionSpec` imported via TYPE_CHECKING or inline
      (to avoid hard dependency on `anthropic` package).

    - **Change signature** of `extract_document()`:
      ```python
      def extract_document(
          pdf_path: Path | str,
          *,
          write_images: bool = False,
          images_dir: Path | str | None = None,
          ocr_language: str = "eng",
          vision_api: "VisionAPI | None" = None,
      ) -> DocumentExtraction:
      ```

    - **Refactor page loop**: Call `find_all_captions(page)` once per page
      (currently called inside `_extract_figures_for_page`). Pass figure
      captions to figure extraction; collect table captions and crops for
      batch vision extraction.

    - **Modify `_extract_figures_for_page`**: Accept an optional
      `all_captions: list[DetectedCaption] | None = None` parameter. When
      provided, filter for figure captions from it instead of calling
      `find_all_captions()` internally. When `None`, call it internally
      (backward compatibility, though no caller will use this path).

    - **Vision extraction block** (after page loop, before post-processing):
      1. If `vision_api is None` or no table crops collected: skip (tables = []).
      2. Build `TableVisionSpec` per crop:
         - `table_id`: `f"p{page_num}_t{sequential_index}"` (unique per batch)
         - `pdf_path`: the input `pdf_path`
         - `page_num`: from the page loop
         - `bbox`: from `compute_all_crops()`
         - `raw_text`: `page.get_text("text", clip=pymupdf.Rect(crop_bbox))`
         - `caption`: `detected_caption.text` (text-layer, for context)
         - `garbled`: `False` (vision reads from images; garble detection
           is a text-layer concern and not implemented in vision-first)
      3. Call `vision_api.extract_tables_batch(specs)` → responses.
      4. **Re-crop pass**: For each response where `recrop_needed` is True
         and `recrop_bbox_pct` is not None:
         - Compute new bbox via `compute_recrop_bbox(original_bbox, bbox_pct)`
         - Extract new `raw_text` for the tighter region
         - Build a new `TableVisionSpec` with the tighter bbox
         - Collect all re-crop specs, submit as a second batch
         - Replace original responses with re-crop responses, UNLESS the
           re-crop response has `is_incomplete=True` (keep original if
           re-crop made things worse)
         - Max 1 re-crop pass (no recursive re-cropping)
      5. **Convert** each successful `AgentResponse` to `ExtractedTable`:
         - `headers`, `rows` ← `clean_cells(resp.headers, resp.rows)`
         - `caption` ← `resp.caption if resp.caption else detected_caption.text`
         - `caption_position` ← `"above"`
         - `footnotes` ← `resp.footnotes`
         - `bbox` ← crop bbox
         - `page_num` ← from spec
         - `table_index` ← sequential per page (0-based)
         - `extraction_strategy` ← `"vision"`
         - Skip responses where `parse_success is False`
      6. **Populate `vision_details`**: Build a list of dicts (one per table
         crop, including failed parses) with the schema from Task 4.3.1.

    - **Post-processing** (lines 253+): The existing post-processing
      (`_assign_heading_captions`, `_assign_continuation_captions`, ligature
      normalization, artifact classification, figure-table overlap, etc.)
      runs unchanged on the vision-produced tables.

    - **Return**: Pass `vision_details=vision_details_list` to the
      `DocumentExtraction` constructor (only when `vision_api` was provided).

- **Tests** (in `tests/test_pdf_processor.py`):
  - `TestExtractDocument::test_vision_api_none_returns_empty_tables`
    — Call `extract_document(some_pdf, vision_api=None)`. Assert:
    `extraction.tables == []`; `extraction.vision_details is None`.
  - `TestExtractDocument::test_vision_api_populates_tables`
    — Mock `VisionAPI.extract_tables_batch` to return 2 `AgentResponse`
    objects with known headers/rows. Mock `find_all_captions` to return
    2 table captions. Call `extract_document(pdf, vision_api=mock_api)`.
    Assert: `len(extraction.tables) == 2`; headers/rows match (after
    cleaning); `extraction_strategy == "vision"` on both tables.
  - `TestExtractDocument::test_vision_caption_used`
    — Mock response with `caption="Table 1. Full demographics"`.
    Text-layer caption is `"Table 1"`. Assert:
    `extraction.tables[0].caption == "Table 1. Full demographics"`.
  - `TestExtractDocument::test_vision_caption_fallback_to_text_layer`
    — Mock response with `caption=""` (empty). Text-layer caption is
    `"Table 1"`. Assert: `extraction.tables[0].caption == "Table 1"`.
  - `TestExtractDocument::test_recrop_replaces_response`
    — Mock first batch: 1 response with `recrop_needed=True`,
    `recrop_bbox_pct=[10, 10, 90, 90]`. Mock second batch (re-crop):
    1 response with `is_incomplete=False`, better data. Assert: table
    uses re-crop response data.
  - `TestExtractDocument::test_recrop_keeps_original_when_incomplete`
    — Same setup but re-crop response has `is_incomplete=True`. Assert:
    table uses original response data.
  - `TestExtractDocument::test_failed_parse_skipped`
    — Mock response with `parse_success=False`. Assert:
    `len(extraction.tables) == 0` (failed response not converted).
  - `TestExtractDocument::test_vision_details_populated`
    — Mock 1 table response. Assert: `extraction.vision_details` is a
    list with 1 entry; entry has `text_layer_caption`, `vision_caption`,
    `recropped`, `parse_success` keys.
  - `TestExtractDocument::test_cell_cleaning_applied`
    — Mock response with `headers=["\ufb03ciency"]`, `rows=[[".047"]]`.
    Assert: table headers `== ["efficiency"]`; row 0, cell 0 `== "0.047"`.

- **Acceptance criteria**:
  - `extract_document()` accepts `vision_api` parameter
  - When `vision_api is None`: tables `== []`, `vision_details is None`
  - When `vision_api` provided: tables populated from vision responses
  - Vision caption used for `ExtractedTable.caption` with text-layer fallback
  - Re-crop: max 1 retry, keeps original if re-crop worsens (is_incomplete)
  - Cell cleaning applied to all vision output
  - `vision_details` populated with per-table debug info
  - `find_all_captions` called once per page (not duplicated)
  - Existing post-processing runs on vision tables


---

### Task 4.3.3: Update `indexer.py` to construct and pass `VisionAPI`

- **Description**: Construct a `VisionAPI` in `Indexer.__init__()` when the
  `ANTHROPIC_API_KEY` environment variable is set. Pass it to every
  `extract_document()` call. When the env var is not set, `_vision_api`
  is `None` and tables are not extracted.

- **Files to modify**:
  - `src/zotero_chunk_rag/indexer.py`:
    - **In `__init__()`** (after existing init, before end of method):
      ```python
      import os
      api_key = os.environ.get("ANTHROPIC_API_KEY")
      if api_key:
          from .feature_extraction.vision_api import VisionAPI
          cost_log_path = config.chroma_db_path.parent / "vision_costs.json"
          self._vision_api = VisionAPI(
              api_key=api_key,
              cost_log_path=cost_log_path,
          )
      else:
          self._vision_api = None
      ```
    - **In `_index_document_detailed()`** (line 292): pass `vision_api`:
      ```python
      extraction = extract_document(
          item.pdf_path,
          write_images=True,
          images_dir=figures_dir,
          ocr_language=self.config.ocr_language,
          vision_api=self._vision_api,
      )
      ```

- **Tests** (in `tests/test_indexer.py` or inline):
  - `TestIndexerInit::test_vision_api_created_with_key`
    — Set `ANTHROPIC_API_KEY` in `os.environ`. Construct `Indexer(config)`.
    Assert: `indexer._vision_api is not None`.
  - `TestIndexerInit::test_vision_api_none_without_key`
    — Ensure `ANTHROPIC_API_KEY` is NOT in `os.environ`. Construct `Indexer`.
    Assert: `indexer._vision_api is None`.

- **Acceptance criteria**:
  - `Indexer` reads `ANTHROPIC_API_KEY` from environment
  - When set: `VisionAPI` constructed with cost log in the chroma db parent dir
  - When unset: `_vision_api is None`, tables not extracted (graceful degradation)
  - `extract_document()` receives `vision_api` in all call sites


---

## Wave 4.4: Stress test

Depends on Waves 4.2 (debug_db pruned + `vision_run_details` table added)
and 4.3 (extract_document rewired).

### Task 4.4.1: Fix imports and delete dead code in stress test

- **Description**: Remove imports of deleted debug_db functions, delete the
  4-agent vision evaluation code and the pipeline depth report builder.
  The GT comparison section (lines ~1546–1561) is kept as-is — it works
  with vision-produced tables identically.

- **Files to modify**:
  - `tests/stress_test_real_library.py`:
    - **Fix imports** (lines 35–42): Remove `write_method_result`,
      `write_pipeline_run`, `write_vision_consensus` from the debug_db
      import. Keep `create_extended_tables`, `write_ground_truth_diff`,
      `write_vision_agent_result`. Add `write_vision_run_detail`.
    - **Delete**: 4-agent vision eval code — the `_EVAL_STAGE_PAIRS`
      constant, the `_eval_cell_diff()` helper, the vision eval function
      that writes to `_vision_stage_eval.db` (or equivalent), and any
      references to it in the main test flow. This is the code that
      tracks per-agent corrections, stage-to-stage diffs, and multi-agent
      consensus results.
    - **Delete**: `_build_pipeline_depth_report()` function and any call
      to it in the report builder. This queries `method_results` and
      `pipeline_runs` tables which no longer exist.
    - **Delete**: Any remaining references to `vision_result_to_cell_grid`,
      `Pipeline`, `DEFAULT_CONFIG`, or other deleted symbols.

- **Tests**: None (the stress test IS the test — it must run without import
  errors).

- **Acceptance criteria**:
  - `stress_test_real_library.py` imports without error:
    `.venv/Scripts/python.exe -c "import tests.stress_test_real_library"`
  - No references to `write_method_result`, `write_pipeline_run`,
    `write_vision_consensus`, `_build_pipeline_depth_report`,
    `vision_result_to_cell_grid`, `Pipeline`, `DEFAULT_CONFIG`
  - GT comparison section unchanged and functional

---

### Task 4.4.2: Add single-agent vision extraction report to stress test

- **Description**: After extraction, write per-table vision details to the
  debug database via both `write_vision_agent_result()` (agent-level data)
  and `write_vision_run_detail()` (full run details including re-crop status)
  and build a "Vision Extraction Report" section in `STRESS_TEST_REPORT.md`.

  The data source is `extraction.vision_details` (populated by
  `extract_document()` when `vision_api` is provided). Each entry
  contains the `AgentResponse` fields needed for `write_vision_agent_result()`
  and the full detail dict for `write_vision_run_detail()`.

- **Files to modify**:
  - `tests/stress_test_real_library.py`:
    - **In the per-paper extraction loop** (after writing tables/figures
      to the debug DB): if `extraction.vision_details` is not None, iterate
      the list and call `write_vision_agent_result()` for each entry:
      ```python
      if extraction.vision_details:
          for vi, vd in enumerate(extraction.vision_details):
              table_id = make_table_id(
                  item_key,
                  vd["text_layer_caption"],
                  vd["page_num"],
                  vi,
              )
              write_vision_agent_result(
                  con,
                  table_id=table_id,
                  agent_idx=0,
                  model="claude-haiku-4-5-20251001",
                  raw_response=vd["raw_response"],
                  headers_json=json.dumps(vd["headers"]),
                  rows_json=json.dumps(vd["rows"]),
                  table_label=vd["table_label"],
                  is_incomplete=vd["is_incomplete"],
                  incomplete_reason=vd["incomplete_reason"],
                  parse_success=vd["parse_success"],
                  execution_time_ms=None,
                  agent_role="transcriber",
                  footnotes=vd["footnotes"],
              )
              write_vision_run_detail(con, table_id=table_id, details_dict=vd)
      ```

      Note: `make_table_id()` is called with the **text_layer_caption**
      (not the vision caption) to maintain stable GT table IDs for
      debugging. The vision caption is stored in the `ExtractedTable` and
      in `vision_details["vision_caption"]` for auditing.

    - **Add report builder function**: `_build_vision_extraction_report(db_path)`
      that queries the debug DB and produces a markdown section:

      ```
      ## Vision Extraction Report

      | Metric | Value |
      |--------|-------|
      | Tables attempted | 44 |
      | Parse success | 42 (95.5%) |
      | Re-crops performed | 5 (11.4%) |
      | Incomplete tables | 2 (4.5%) |

      ### Per-paper breakdown

      | Paper | Tables | Parsed | Re-cropped | Incomplete |
      |-------|--------|--------|------------|------------|
      | laird-fick-polyps | 6 | 6 | 1 | 0 |
      | ... | ... | ... | ... | ... |

      ### Caption changes (text-layer → vision)

      | Table ID | Text Layer | Vision |
      |----------|-----------|--------|
      | 5SIZVS65_table_1 | Table 1 | Table 1. Demographics by... |
      | ... | ... | ... |
      ```

      Data sources:
      - `vision_run_details` table: `recropped`, `recrop_bbox_pct_json`,
        `text_layer_caption`, `vision_caption`, `parse_success`,
        `is_incomplete` — primary source for the report
      - `vision_agent_results` table: `parse_success`, `is_incomplete`,
        `table_label` — agent-level data for GT comparison
      - `extracted_tables` table: join on `table_id` for paper info

    - **Integrate into main report**: Call `_build_vision_extraction_report()`
      in the report assembly, replacing the deleted pipeline depth report
      section.

- **Tests**: None (verified by running the stress test).

- **Acceptance criteria**:
  - `write_vision_agent_result()` and `write_vision_run_detail()` called
    for every table crop (including failed parses)
  - `STRESS_TEST_REPORT.md` contains a "Vision Extraction Report" section
  - Report shows: total tables, parse success rate, re-crop rate,
    incomplete count, per-paper breakdown, caption changes
  - Re-crop rate is computed from `vision_run_details.recropped` column
  - Caption changes are computed by comparing `text_layer_caption` vs
    `vision_caption` in `vision_run_details`
  - GT table IDs use text-layer caption (stable matching)

---

## Agent Execution Rules

### No API calls

Implementation agents MUST NOT make external API calls (Anthropic, Zotero,
or any network request). All `VisionAPI` usage in tests must be mocked.
`pymupdf.open()` on local test PDFs is permitted.

The only exception is Step 5 (Evaluation), which is user-initiated.

### Test execution protocol

Tests are run at most TWICE per implementation session:

1. **First run**: Execute relevant tests. Record all failures.
2. **Quick fix round**: Fix only obvious mechanical issues (broken imports,
   missing symbols, trivial type errors). No restructuring.
3. **Second run**: Execute again. Record remaining failures.
4. **Report**: Surface all remaining failures to the user. Do not loop.

### No test modification to make tests pass

If a test fails, the agent reports the failure — it does not modify test
assertions.

---

## Acceptance Criteria (Step-level)

1. **Vision path**: `extract_document(pdf, vision_api=mock)` returns tables with headers, rows, and `extraction_strategy="vision"`
2. **No vision**: `extract_document(pdf, vision_api=None)` returns `tables=[]`
3. **Caption**: Vision caption used for `ExtractedTable.caption`, text-layer caption as fallback
4. **Re-crop**: Max 1 retry; original kept if re-crop has `is_incomplete=True`
5. **Cell cleaning**: Ligatures, leading zeros, negative signs normalized in vision output
6. **Debug DB**: `ground_truth_diffs`, `vision_agent_results`, and `vision_run_details` tables present
7. **Indexer**: Creates `VisionAPI` from `ANTHROPIC_API_KEY` env var; passes to `extract_document()`
8. **Stress test**: No references to deleted functions; vision report section present
