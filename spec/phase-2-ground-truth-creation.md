# Phase 2: Ground Truth Creation

## Overview

This phase creates a human-verified "answer key" for every table in the 10-paper corpus. The ground truth is used in Phase 6 (pipeline evaluation — compare extraction accuracy against ground truth) and Phase 7 (permanent regression tests). The blind comparison API from Phase 1 (Task 1.2.2) consumes this ground truth to evaluate extraction methods without exposing the answers.

The workflow is:
1. A Python script creates a workspace with rendered table images and current extraction output from the debug DB
2. Sonnet agents in Claude Code visually read each table image (blind — no extraction hint) and produce draft ground truth JSON
3. The user reviews each draft against the paper, corrects errors conversationally in Claude Code, and marks tables as verified
4. A batch load script writes all verified ground truth into the SQLite database

All tables are included, including those tagged as artifacts — this validates that artifact detection is working correctly.

## Wave 2.1: Ground Truth Workspace and Agent Drafting

### Task 2.1.1: Create ground truth workspace from debug DB

- **Description**: Build a script that reads the existing `_stress_test_debug.db` and creates a workspace directory with one subdirectory per paper. For each table (including artifacts), the script renders the table region as a PNG image and writes the current extraction output as JSON. The script requires a pre-existing debug DB from a recent stress test run.

  The workspace uses a flat per-paper structure. Table files are named by table index (matching the debug DB's `table_index`). Each paper directory also gets a `manifest.json` listing all tables for that paper with their metadata.

- **Files to create**:
  - `tests/create_ground_truth.py` — standalone script (not pytest-collected). Contains:
    - `create_workspace(debug_db_path: Path, output_dir: Path) -> None` — main function. For each paper in the debug DB:
      1. Creates `output_dir/<short_name>/`
      2. Queries all `extracted_tables` rows for the paper (no artifact filter)
      3. Resolves the PDF path for each paper from the CORPUS definition in `stress_test_real_library.py` (import the `CORPUS` list or replicate the Zotero lookup)
      4. For each table: calls `render_table_image()` from `table_extraction.render` to produce `table_<idx>.png`
      5. For each table: writes `table_<idx>_extraction.json` with all available fields
      6. For each table: writes an empty `table_<idx>_gt.json` template with the correct schema and `"verified": false`
      7. Writes `manifest.json` listing all tables with metadata
    - `if __name__ == "__main__"` block that runs `create_workspace()` with default paths

  **Extraction JSON schema** (`table_<idx>_extraction.json`):
  ```json
  {
    "paper": "<short_name>",
    "item_key": "<zotero_key>",
    "page_num": 4,
    "table_index": 0,
    "caption": "Table 1. Patient Demographics",
    "caption_position": "above",
    "headers": ["Variable", "Group A", "Group B", "p-value"],
    "rows": [["Age", "62.3", "64.1", "0.42"]],
    "num_rows": 1,
    "num_cols": 4,
    "fill_rate": 1.0,
    "bbox": [72.0, 200.0, 540.0, 400.0],
    "artifact_type": null,
    "extraction_strategy": "rawdict",
    "footnotes": "",
    "reference_context": "",
    "markdown": "| Variable | Group A | ... |"
  }
  ```

  **Ground truth template** (`table_<idx>_gt.json`):
  ```json
  {
    "table_id": "<generated via make_table_id()>",
    "paper": "<short_name>",
    "item_key": "<zotero_key>",
    "page_num": 4,
    "table_index": 0,
    "caption": "Table 1. Patient Demographics",
    "headers": [],
    "rows": [],
    "notes": "",
    "verified": false
  }
  ```

  **Manifest schema** (`manifest.json`):
  ```json
  {
    "paper": "<short_name>",
    "item_key": "<zotero_key>",
    "num_tables": 5,
    "tables": [
      {
        "table_index": 0,
        "table_id": "<from make_table_id()>",
        "page_num": 4,
        "caption": "Table 1. Patient Demographics",
        "artifact_type": null,
        "image_path": "table_0.png",
        "extraction_path": "table_0_extraction.json",
        "gt_path": "table_0_gt.json"
      }
    ]
  }
  ```

- **Files to modify**: (none)
- **Tests**:
  - `tests/test_table_extraction/test_ground_truth_workspace.py::TestWorkspace::test_creates_paper_directories` — run `create_workspace()` with a mock debug DB containing 2 papers with 1 table each, assert both paper directories are created
  - `tests/test_table_extraction/test_ground_truth_workspace.py::TestWorkspace::test_renders_table_images` — assert PNG files exist for each table and are valid PNGs (check `\x89PNG` header bytes)
  - `tests/test_table_extraction/test_ground_truth_workspace.py::TestWorkspace::test_writes_extraction_json` — assert extraction JSON files exist and contain all required fields (`headers`, `rows`, `bbox`, `fill_rate`, `artifact_type`, `markdown`)
  - `tests/test_table_extraction/test_ground_truth_workspace.py::TestWorkspace::test_writes_gt_template` — assert GT template files exist with `"verified": false`, empty `headers` and `rows`, and a valid `table_id` from `make_table_id()`
  - `tests/test_table_extraction/test_ground_truth_workspace.py::TestWorkspace::test_writes_manifest` — assert manifest.json exists, contains correct `num_tables`, and each entry has all required fields
  - `tests/test_table_extraction/test_ground_truth_workspace.py::TestWorkspace::test_includes_artifact_tables` — mock DB has one artifact table (`artifact_type="figure_data_table"`), assert it appears in the workspace and manifest
  - `tests/test_table_extraction/test_ground_truth_workspace.py::TestWorkspace::test_requires_debug_db` — calling with a nonexistent debug DB path raises `FileNotFoundError`
- **Acceptance criteria**:
  - Running `"./.venv/Scripts/python.exe" tests/create_ground_truth.py` creates `tests/ground_truth_workspace/` with one subdirectory per corpus paper
  - Each paper directory contains PNG images, extraction JSONs, GT templates, and a manifest
  - All tables are included (no artifact filtering)
  - GT templates have valid `table_id` values from `make_table_id()`
  - All 7 tests pass

### Task 2.1.2: Agent-led blind ground truth drafting

- **Description**: A documented procedure for using Claude Code to produce draft ground truth for every table in the corpus. This is not a Python script — it is a prompt template and step-by-step instructions for spawning sonnet agents in Claude Code.

  **Procedure**:
  1. Run `"./.venv/Scripts/python.exe" tests/create_ground_truth.py` to create the workspace (Task 2.1.1)
  2. For each paper (10 total), spawn a Claude Code Task agent (sonnet) with the prompt template below
  3. Each agent reads all table images for its paper via the Read tool (which renders images visually)
  4. For each table image, the agent produces ground truth JSON: headers and rows as it reads them from the image
  5. The agent writes the completed `table_<idx>_gt.json` files to the workspace

  **Batching**: One agent per paper (10 agents). Can be parallelized.

  **Agent input**: The agent receives:
  - The paper's `manifest.json` (to know which tables to process and where the images are)
  - The paper's short name and page count (context)
  - NO extraction data — blind read only

  **Agent output**: For each table, the agent overwrites the GT template with populated `headers` and `rows` from its visual reading of the image. If the agent cannot confidently read part of a table, it populates what it can and describes the uncertainty in the `notes` field. The `verified` field stays `false` (human verification happens in Task 2.1.3).

- **Files to create**:
  - `tests/ground_truth_workspace/gt_prompt.md` — the prompt template for agents. Contains:
    - Role description: "You are reading academic paper tables from rendered images to create ground truth data."
    - Instructions: Read each table image via the Read tool. For each table, produce exact cell contents as they appear in the image. Headers are the column headers. Rows are the data rows. Preserve exact numeric values, special characters, and formatting.
    - Rules:
      - Read from the image only — do not guess or infer values
      - If a cell spans multiple columns, place its content in the leftmost column and leave spanned columns empty
      - If a cell spans multiple rows, place content in the topmost row
      - Multi-line cell content: join with a single space
      - If text is too small or blurry to read confidently, write what you can see and add a note
      - Include ALL rows, including sub-headers (e.g., "Panel A: Males") as rows in the data
      - Footnote rows (e.g., "Note: ..." or "* p < 0.05") should NOT be included in the rows — note their presence in the `notes` field
    - Output format: overwrite each `table_<idx>_gt.json` with the populated schema
    - Example of a completed GT JSON
- **Tests**: (none — this is a procedure, not code)
- **Acceptance criteria**:
  - `gt_prompt.md` exists with clear, unambiguous instructions
  - After running the procedure, every `table_<idx>_gt.json` in the workspace has non-empty `headers` and/or `rows` (or a `notes` field explaining why the table couldn't be read)
  - No GT file references the extraction JSON — all content comes from visual image reading

### Task 2.1.3: Ground truth review procedure and batch loader

- **Description**: Two deliverables:

  1. **Review procedure** (documented in `gt_prompt.md` as a "Review Phase" section): Step-by-step instructions for the human review workflow in Claude Code:
     - Open the paper PDF on a second monitor
     - In Claude Code, ask the agent to read and display each `table_<idx>_gt.json` as a markdown table
     - Compare the rendered markdown table against the paper
     - Give corrections conversationally: "table 3, row 2, col 4 should be 0.047 not 0.47"
     - Agent edits the GT JSON and re-displays for confirmation
     - When satisfied, agent sets `"verified": true` in the GT JSON
     - Repeat for all tables in all papers

  2. **Batch load script**: A Python script that scans the workspace for verified GT files and inserts them into the ground truth database (`tests/ground_truth.db`) via the Phase 1 API.

- **Files to create**:
  - `tests/load_ground_truth.py` — standalone script. Contains:
    - `load_verified_ground_truth(workspace_dir: Path, db_path: Path) -> dict` — scans all paper subdirectories for `table_*_gt.json` files where `"verified": true`. For each: calls `insert_ground_truth()` from `table_extraction.ground_truth`. Returns summary: `{"loaded": N, "skipped_unverified": M, "errors": [...]}`
    - `if __name__ == "__main__"` block with default paths (`tests/ground_truth_workspace/`, `tests/ground_truth.db`)
- **Files to modify**:
  - `tests/ground_truth_workspace/gt_prompt.md` — append "Review Phase" section with the review procedure
- **Tests**:
  - `tests/test_table_extraction/test_ground_truth_workspace.py::TestLoader::test_loads_verified` — create a temp workspace with 2 GT files (one verified, one not), run `load_verified_ground_truth()`, assert only the verified entry is in the DB
  - `tests/test_table_extraction/test_ground_truth_workspace.py::TestLoader::test_skips_unverified` — GT file with `"verified": false` is not loaded, returned in `skipped_unverified` count
  - `tests/test_table_extraction/test_ground_truth_workspace.py::TestLoader::test_data_fidelity` — load a verified GT with known headers/rows, query the DB, assert exact match on all cell values (JSON round-trip preserves data)
  - `tests/test_table_extraction/test_ground_truth_workspace.py::TestLoader::test_creates_db_if_missing` — run loader when `ground_truth.db` doesn't exist, assert it creates the DB and loads the entry
  - `tests/test_table_extraction/test_ground_truth_workspace.py::TestLoader::test_idempotent_reload` — load the same verified GT twice, assert no error and data is current (upsert behavior via `insert_ground_truth` which replaces)
- **Acceptance criteria**:
  - `load_verified_ground_truth()` loads only verified GT entries into the database
  - Data fidelity: headers and rows survive the JSON → DB → JSON round-trip exactly
  - Creates the ground truth DB if it doesn't exist (via `create_ground_truth_db()`)
  - Idempotent: re-running the loader updates existing entries without duplication
  - All 5 tests pass
  - `gt_prompt.md` contains both the agent drafting instructions and the human review procedure

## Wave 2.2: Human Review

### Task 2.2.1: User reviews all ground truth (human task)

- **Description**: The user works through all tables in the corpus using the review procedure from Task 2.1.3. For each table:
  1. View the GT as a markdown table in Claude Code
  2. Compare against the paper PDF on a second monitor
  3. Correct any errors conversationally
  4. Mark as verified

  After all tables are reviewed, run the batch loader (`tests/load_ground_truth.py`) to populate `tests/ground_truth.db`.

- **Files to modify**: (none — human task)
- **Tests**: (none — human task)
- **Acceptance criteria**:
  - Every `table_*_gt.json` in the workspace has `"verified": true`
  - `tests/ground_truth.db` exists and contains entries for all corpus tables
  - `get_table_ids(db_path)` returns IDs for all papers in the corpus
  - Spot-check: at least 3 tables from different papers have cell-accurate ground truth when visually compared to the PDF
