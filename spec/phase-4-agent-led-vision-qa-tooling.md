# Phase 4: Agent-Led Vision QA Tooling

## Overview

This phase builds a repeatable quality assurance loop where a haiku agent visually inspects extracted tables (rendered as PNGs at 300 DPI) and compares them against the automated extraction output. The agent produces cell-level diff JSON — any difference between visual reading and extraction is an error, with no severity classification.

Three deliverables:
1. A preparation script that reads the debug DB, renders table images, writes extraction JSONs, and produces a manifest
2. A prompt template and run script for spawning haiku agents via Claude Code's Task tool, one table per agent call, with results aggregated into both JSON and Markdown reports
3. A design document scoping the production pathway for automatic QA on newly-indexed papers

**Dependencies**: Phase 1 (complete). Uses `render_table_image()` from `table_extraction.render` and table data from `_stress_test_debug.db`.

## Wave 4.1: QA Infrastructure

### Task 4.1.1: QA workspace preparation script

- **Description**: Build a script that reads `_stress_test_debug.db`, renders every non-artifact table as a 300 DPI PNG via Phase 1's `render_table_image()`, writes each table's extraction data as JSON, and produces a manifest mapping every table to its image and extraction files. The workspace lives at `tests/agent_qa/workspace/` (gitignored). Requires the stress test to have been run first (debug DB must exist).

  The script resolves PDF paths the same way `tests/create_ground_truth.py` does — via Zotero client lookup or the CORPUS definition in `stress_test_real_library.py`.

- **Files to create**:
  - `tests/agent_qa/__init__.py` — empty package init
  - `tests/agent_qa/prepare_qa.py` — standalone script (not pytest-collected). Contains:
    - `prepare_qa_workspace(debug_db_path: Path, output_dir: Path) -> Path` — main function. Returns path to the generated manifest. Steps:
      1. Opens `debug_db_path`, queries all rows from `extracted_tables` joined with `papers` (to get `short_name`)
      2. Filters to non-artifact tables (`artifact_type IS NULL`)
      3. Groups tables by paper
      4. For each paper, resolves the PDF path (import Zotero client or CORPUS lookup)
      5. For each table: calls `render_table_image(pdf_path, page_num, bbox, output_path, dpi=300)` from `table_extraction.render` to produce `{output_dir}/{short_name}/table_{idx}.png`
      6. For each table: writes `{output_dir}/{short_name}/table_{idx}_extraction.json` containing:
         ```json
         {
           "table_id": "<from make_table_id()>",
           "paper": "<short_name>",
           "item_key": "<zotero_key>",
           "page_num": 4,
           "table_index": 0,
           "caption": "Table 1. Results",
           "headers": ["Col1", "Col2"],
           "rows": [["val1", "val2"]],
           "num_rows": 1,
           "num_cols": 2,
           "fill_rate": 1.0,
           "bbox": [72.0, 200.0, 540.0, 400.0]
         }
         ```
      7. Writes `{output_dir}/manifest.json` — a flat array of all table entries:
         ```json
         [
           {
             "table_id": "SCPXVBLY_table_1",
             "paper": "active-inference-tutorial",
             "item_key": "SCPXVBLY",
             "page_num": 4,
             "table_index": 0,
             "caption": "Table 1. Results",
             "image_path": "active-inference-tutorial/table_0.png",
             "extraction_path": "active-inference-tutorial/table_0_extraction.json",
             "num_rows": 8,
             "num_cols": 5
           }
         ]
         ```
         Paths in the manifest are relative to `output_dir`.
    - `if __name__ == "__main__"` block that calls `prepare_qa_workspace()` with default paths (`_stress_test_debug.db`, `tests/agent_qa/workspace/`)

- **Files to modify**:
  - `.gitignore` — add `tests/agent_qa/workspace/` if not already ignored

- **Tests**:
  - `tests/test_table_extraction/test_agent_qa.py::TestPrepareQA::test_creates_paper_directories` — create a mock debug DB with 2 papers (1 table each, with mock PDF paths), mock `render_table_image` to write a dummy PNG, run `prepare_qa_workspace()`, assert both paper directories exist under workspace
  - `tests/test_table_extraction/test_agent_qa.py::TestPrepareQA::test_renders_images` — assert PNG files exist at expected paths and are valid (check `\x89PNG` header)
  - `tests/test_table_extraction/test_agent_qa.py::TestPrepareQA::test_writes_extraction_json` — assert extraction JSON files exist and contain required fields: `table_id`, `headers`, `rows`, `page_num`, `bbox`, `fill_rate`
  - `tests/test_table_extraction/test_agent_qa.py::TestPrepareQA::test_writes_manifest` — assert `manifest.json` exists, is valid JSON, contains entries for all tables with `table_id`, `image_path`, `extraction_path` fields
  - `tests/test_table_extraction/test_agent_qa.py::TestPrepareQA::test_skips_artifacts` — mock DB has one artifact table (`artifact_type='figure_data_table'`), assert it does NOT appear in the manifest or workspace
  - `tests/test_table_extraction/test_agent_qa.py::TestPrepareQA::test_requires_debug_db` — calling with a nonexistent debug DB path raises `FileNotFoundError`

- **Acceptance criteria**:
  - Running `"./.venv/Scripts/python.exe" tests/agent_qa/prepare_qa.py` creates `tests/agent_qa/workspace/` with rendered PNGs and extraction JSONs for all non-artifact corpus tables
  - Manifest contains entries for every non-artifact table with correct relative paths
  - All images render at 300 DPI via `render_table_image()`
  - Extraction JSONs contain `table_id` generated via `make_table_id()` from `table_extraction.ground_truth`
  - All 6 tests pass

### Task 4.1.2: Agent QA prompt template and run script

- **Description**: Design the haiku agent prompt template and build a run script that orchestrates QA across all tables. The run script is designed to be called FROM a Claude Code session — it reads the manifest and spawns one haiku Task agent per table. Each agent receives the table image (via Read tool) and extraction JSON, visually reads the image, compares against the extraction, and returns a cell-level diff JSON. Any difference is an error — no severity classification.

  The run script aggregates all per-table results into two output files:
  - `tests/agent_qa/workspace/qa_results.json` — machine-readable, all diffs
  - `tests/agent_qa/workspace/qa_report.md` — human-readable summary + per-table detail

  **Prompt validation**: The prompt template is tested on 3-4 representative tables from the corpus during development, selected to cover: (a) a clean simple table that should match, (b) a dense numeric table, (c) a table with known extraction issues, (d) a multi-row-header or footnoted table.

- **Files to create**:
  - `tests/agent_qa/qa_prompt.md` — the prompt template. Contains:
    - Role: "You are a quality assurance agent for academic table extraction. Your job is to visually read a table image and compare it cell-by-cell against an automated extraction."
    - Instructions:
      1. Read the table image using the Read tool (it will be rendered visually)
      2. Read the extraction JSON
      3. Compare every cell: first check that the row count and column count match, then compare each cell value
      4. Any difference — missing value, wrong number, extra whitespace, different formatting — is an error
      5. Do NOT guess or infer what the extraction "should" have produced. Read the image literally.
      6. Ignore footnote rows (text below the table grid like "Note:" or "* p < 0.05"). Only compare the tabular grid itself: headers + data rows.
      7. If the image is too blurry or small to read a cell confidently, report it as `"visual": "UNREADABLE"` for that cell
    - Output format (strict JSON):
      ```json
      {
        "table_id": "<from extraction JSON>",
        "matches": false,
        "visual_rows": 8,
        "visual_cols": 5,
        "extraction_rows": 8,
        "extraction_cols": 5,
        "structural_errors": [
          "Extraction has 4 columns, image shows 5"
        ],
        "errors": [
          {"row": 2, "col": 3, "visual": "0.047", "extracted": ".047"},
          {"row": 5, "col": 1, "visual": "Treatment B", "extracted": ""}
        ]
      }
      ```
    - Rules for row/col numbering: 0-indexed, headers are row -1 (report header errors with `"row": -1`)
    - Template variables: `{IMAGE_PATH}`, `{EXTRACTION_JSON_PATH}`, `{TABLE_ID}`

  - `tests/agent_qa/run_qa.py` — orchestration script. Contains:
    - `build_agent_prompt(image_path: str, extraction_json_path: str, table_id: str) -> str` — reads `qa_prompt.md` template, substitutes variables, returns the full prompt string
    - `parse_agent_response(response_text: str) -> dict` — extracts the JSON object from the agent's response text (handles markdown code fences, preamble text). Returns the parsed dict. Raises `ValueError` if no valid JSON found.
    - `aggregate_results(results: list[dict]) -> tuple[dict, str]` — takes list of per-table result dicts, produces:
      - `qa_results` dict: `{"run_timestamp": "...", "total_tables": N, "tables_matching": M, "tables_with_errors": K, "total_errors": E, "results": [...]}`
      - `qa_report` markdown string: summary table (paper | table | pass/fail | error count), then per-table sections listing each error
    - `write_outputs(qa_results: dict, qa_report: str, output_dir: Path) -> tuple[Path, Path]` — writes `qa_results.json` and `qa_report.md` to output_dir, returns their paths
    - The script is NOT directly executable (`if __name__` block prints usage instructions directing the user to invoke from Claude Code). The actual agent spawning happens when a Claude Code agent reads `manifest.json` and uses the Task tool with haiku model for each table.

- **Files to modify**: (none)

- **Tests**:
  - `tests/test_table_extraction/test_agent_qa.py::TestPromptBuilder::test_substitutes_variables` — call `build_agent_prompt("path/to/img.png", "path/to/ext.json", "ABC_table_1")`, assert result contains all three concrete values and no unsubstituted `{` template markers
  - `tests/test_table_extraction/test_agent_qa.py::TestPromptBuilder::test_reads_template` — assert `build_agent_prompt()` reads from `qa_prompt.md` and the result contains key instruction phrases ("visually read", "cell-by-cell")
  - `tests/test_table_extraction/test_agent_qa.py::TestResponseParser::test_parses_clean_json` — pass a clean JSON string matching the output schema, assert `parse_agent_response()` returns a dict with `matches`, `errors`, `table_id` keys
  - `tests/test_table_extraction/test_agent_qa.py::TestResponseParser::test_parses_fenced_json` — pass JSON wrapped in ````json\n...\n``` `` markers, assert it parses correctly
  - `tests/test_table_extraction/test_agent_qa.py::TestResponseParser::test_parses_json_with_preamble` — pass "Here are the results:\n{...json...}", assert it extracts the JSON
  - `tests/test_table_extraction/test_agent_qa.py::TestResponseParser::test_rejects_no_json` — pass "I couldn't read the image", assert `ValueError` is raised
  - `tests/test_table_extraction/test_agent_qa.py::TestAggregation::test_all_matching` — pass 3 results all with `matches: true`, assert `tables_with_errors == 0`, `total_errors == 0`, report contains "3/3 tables match"
  - `tests/test_table_extraction/test_agent_qa.py::TestAggregation::test_with_errors` — pass 2 results (1 matching, 1 with 3 errors), assert `tables_with_errors == 1`, `total_errors == 3`, report lists each error
  - `tests/test_table_extraction/test_agent_qa.py::TestAggregation::test_structural_errors_counted` — pass a result with 2 structural errors and 1 cell error, assert `total_errors == 3` (structural + cell)
  - `tests/test_table_extraction/test_agent_qa.py::TestOutputWriter::test_writes_json_and_markdown` — call `write_outputs()` with mock data, assert both files exist, JSON is valid, markdown contains summary table

- **Acceptance criteria**:
  - `qa_prompt.md` provides clear, unambiguous instructions for a haiku agent to visually compare a table image against extraction data
  - `build_agent_prompt()` produces a complete prompt string with all variables substituted
  - `parse_agent_response()` handles clean JSON, fenced JSON, and JSON with preamble text; rejects responses with no JSON
  - `aggregate_results()` correctly counts matching vs error tables and total error count (structural + cell errors combined)
  - `write_outputs()` produces valid `qa_results.json` and readable `qa_report.md`
  - All 10 tests pass

### Task 4.1.3: Production QA pathway design document

- **Description**: Scope what a production-mode agent QA pipeline would look like — where every newly-indexed PDF gets an automatic haiku agent QA pass on its extracted tables. This is a design document, not code.

  The document covers:
  1. **Cost analysis**: tokens per table image at 300 DPI (~1600 input tokens for a typical table image), haiku pricing per table, estimated cost per paper (assuming average N tables per paper from corpus statistics)
  2. **Latency analysis**: time per agent call, total time per paper, comparison with current extraction time
  3. **Async vs sync recommendation**: whether QA should block indexing or run as a background pass
  4. **Trigger policy**: when to run QA — every indexing? only new papers? manual? on pipeline changes only?
  5. **Failure modes**: what happens when the agent disagrees with a correct extraction? False positive handling strategy. What happens when the agent can't read an image (blurry, too small, complex layout)?
  6. **Confidence calibration**: how much to trust agent readings vs automated extraction. When should a human review agent-flagged discrepancies vs auto-accepting the agent's reading?
  7. **Integration with ground truth**: relationship between agent QA diffs and ground truth comparison diffs. Can agent QA supplement or replace ground truth for new papers?
  8. **Decision framework**: when to use agent QA vs statistical checks (fill rate, garbled detection) vs ground truth comparison. Which is appropriate at which stage of the pipeline lifecycle.

- **Files to create**:
  - `spec/agent_qa_design.md` — the design document, 2-4 pages

- **Tests**:
  - `tests/test_table_extraction/test_agent_qa.py::TestDesignDoc::test_design_doc_exists` — assert `spec/agent_qa_design.md` exists and has >500 characters of content
  - `tests/test_table_extraction/test_agent_qa.py::TestDesignDoc::test_design_doc_sections` — assert the document contains section headers for at least: "Cost", "Latency", "Failure", "Confidence" (case-insensitive grep for these keywords)

- **Acceptance criteria**:
  - `spec/agent_qa_design.md` exists and covers all 8 topics listed above
  - Cost estimates use current Anthropic haiku pricing (looked up at implementation time)
  - Latency estimates are grounded in measured per-table extraction times from the stress test
  - The document provides a concrete recommendation for async vs sync and trigger policy
  - Both tests pass
