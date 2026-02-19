# Implementation Progress

Progress is recorded here by implementation agents. Each completed task appends its status below.

## Task 1.1.1: Install Camelot and pdfplumber dependencies
- **Status**: complete
- **Agent**: implementer
- **Files created**: tests/test_table_extraction/__init__.py, tests/test_table_extraction/test_dependencies.py (TestDependencies class)
- **Files modified**: pyproject.toml (added camelot-py>=0.11.0 and pdfplumber>=0.11.0 to dependencies)
- **Tests**: 3/3 passing (test_camelot_imports, test_pdfplumber_imports, test_camelot_ghostscript)
- **Note**: camelot-py 1.0.9 no longer has a [base] extra; dependency recorded without extra.

## Task 1.1.2: Create table_extraction package skeleton
- **Status**: complete
- **Agent**: implementer
- **Files created**:
  - src/zotero_chunk_rag/table_extraction/__init__.py
  - src/zotero_chunk_rag/table_extraction/models.py
  - src/zotero_chunk_rag/table_extraction/protocols.py
  - src/zotero_chunk_rag/table_extraction/pipeline.py
  - src/zotero_chunk_rag/table_extraction/scoring.py
  - src/zotero_chunk_rag/table_extraction/combination.py
  - src/zotero_chunk_rag/table_extraction/ground_truth.py
  - src/zotero_chunk_rag/table_extraction/debug_db.py
  - src/zotero_chunk_rag/table_extraction/render.py
  - src/zotero_chunk_rag/table_extraction/methods/__init__.py
  - src/zotero_chunk_rag/table_extraction/postprocessors/__init__.py
  - tests/test_table_extraction/test_dependencies.py (TestPackageStructure class added)
- **Files modified**: (none beyond task 1.1.1)
- **Tests**: 2/2 passing (test_package_importable, test_subpackages_importable)
- **Total suite**: 429 tests passing, 0 regressions

## Task 1.2.1: Ground truth database schema and creation
- **Status**: complete
- **Agent**: implementer
- **Files created**: tests/test_table_extraction/test_ground_truth.py (TestSchema, TestTableId, TestInsert classes)
- **Files modified**: src/zotero_chunk_rag/table_extraction/ground_truth.py (replaced placeholder with full implementation)
- **Tests**: 10/10 passing
- **Details**: Implemented `GROUND_TRUTH_DB_PATH`, `create_ground_truth_db()`, `make_table_id()`, `insert_ground_truth()`, `get_table_ids()`. Caption number parsing handles standard, appendix (A.1), supplementary (S2), Roman numeral (IV), and orphan/synthetic caption cases.

## Task 1.2.2: Blind comparison API with split-aware alignment
- **Status**: complete
- **Agent**: implementer
- **Files created**: (tests added to existing test_ground_truth.py: TestNormalize, TestCompare classes)
- **Files modified**: src/zotero_chunk_rag/table_extraction/ground_truth.py (added dataclasses, normalization, column/row alignment, compare_extraction)
- **Tests**: 12/12 passing
- **Details**: Implemented `CellDiff`, `SplitInfo`, `MergeInfo`, `ComparisonResult` dataclasses. `_normalize_cell()` applies 4-step normalization (strip, collapse whitespace, unicode minus, ligatures). Column alignment by exact header match then LCS fallback (0.8 threshold). Row alignment is sequential with split/merge detection. Split/merged cells count as 0% accurate. Column alignment is by header text, not position.

## Task 1.2.3: Table image renderer
- **Status**: complete
- **Agent**: implementer
- **Files created**: tests/test_table_extraction/test_render.py (TestRender class)
- **Files modified**: src/zotero_chunk_rag/table_extraction/render.py (replaced placeholder with full implementation)
- **Tests**: 5/5 passing
- **Details**: Implemented `render_table_image()` (renders bbox region as PNG via pymupdf pixmap) and `render_all_tables()` (renders all non-artifact tables). 1-indexed page_num, 300 DPI default, padding clips to page bounds.
- **Total suite**: 456 tests passing, 0 regressions

## Task 1.3.1: Extend debug database schema and wire ground truth diffs
- **Status**: complete
- **Agent**: sonnet-implementer
- **Files created**: tests/test_table_extraction/test_debug_db.py (TestSchema, TestWrite classes — 5 tests)
- **Files modified**:
  - src/zotero_chunk_rag/table_extraction/debug_db.py (replaced placeholder with full implementation)
  - tests/stress_test_real_library.py (added imports, create_extended_tables() call, GT diff writing loop, GT summary helper and report append)
- **Tests**: 5/5 passing
- **Total suite**: 461 tests passing, 0 regressions
- **Details**:
  - `EXTENDED_SCHEMA` defines three new tables: `method_results`, `pipeline_runs`, `ground_truth_diffs`
  - `create_extended_tables(con)` executes the schema on an existing connection (idempotent)
  - `write_method_result()` inserts a method extraction result row
  - `write_pipeline_run()` inserts a pipeline run row
  - `write_ground_truth_diff()` serializes a `ComparisonResult` via `dataclasses.asdict()` + `json.dumps()`, extracts summary fields (cell_accuracy_pct, num_splits, num_merges, num_cell_diffs, gt_shape, ext_shape)
  - Stress test now calls `create_extended_tables()` after creating the base schema
  - Stress test writes GT diffs when `tests/ground_truth.db` exists; silently skips per-table when not in GT (KeyError)
  - `_build_gt_summary_markdown()` queries the DB for GT diffs and builds a markdown table with per-table accuracy and overall corpus accuracy; appended to the report file if any diffs exist

## Task 2.1.1: Create ground truth workspace from debug DB
- **Status**: complete
- **Agent**: implementer
- **Files created**: tests/create_ground_truth.py, tests/test_table_extraction/test_ground_truth_workspace.py (TestWorkspace class)
- **Files modified**: (none)
- **Tests**: 7/7 passing (test_creates_paper_directories, test_renders_table_images, test_writes_extraction_json, test_writes_gt_template, test_writes_manifest, test_includes_artifact_tables, test_requires_debug_db)
- **Details**: Standalone script reads _stress_test_debug.db and creates workspace with per-paper directories. Each table gets: PNG render, extraction JSON, GT template (with make_table_id()), and manifest.json. All tables included (no artifact filtering). Uses render_table_image() from table_extraction.render. PDF paths resolved via ZoteroClient or optional pdf_paths parameter. Tests use mock DB with synthetic data and mock rendering.

## Task 2.1.2: Agent-led blind ground truth drafting (prompt template)
- **Status**: complete
- **Agent**: implementer
- **Files created**: tests/ground_truth_workspace/gt_prompt.md
- **Files modified**: (none)
- **Tests**: (none -- document only, no code)
- **Details**: Created prompt template for Claude Code agents to produce blind ground truth from table images. Contains: role description, 10 rules for reading tables (merged cells, multi-line content, footnotes, sub-headers, exact values), 3-step procedure (create workspace, spawn agents, verify coverage), output JSON schema with field descriptions, and a complete worked example showing sub-header rows, footnote handling, and exact transcription.

## Task 2.1.3: Ground truth review procedure and batch loader
- **Status**: complete
- **Agent**: implementer
- **Files created**: tests/load_ground_truth.py
- **Files modified**: tests/ground_truth_workspace/gt_prompt.md (appended Review Phase section), tests/test_table_extraction/test_ground_truth_workspace.py (added TestLoader class with 5 tests)
- **Tests**: 12/12 passing (7 TestWorkspace + 5 TestLoader: test_loads_verified, test_skips_unverified, test_data_fidelity, test_creates_db_if_missing, test_idempotent_reload)
- **Details**: `load_verified_ground_truth()` scans workspace for table_*_gt.json with verified=true, inserts via insert_ground_truth() (upsert). Creates DB if missing via create_ground_truth_db(). Returns summary dict with loaded/skipped_unverified/errors counts. Review Phase section in gt_prompt.md provides step-by-step human review workflow: display GT as markdown table, compare against PDF, give corrections conversationally, mark verified, then batch load.

---
## Wave 2.1 Summary
- **Status**: complete
- **Tasks completed**: 3/3
- **Rounds**: 2 (2.1.1 + 2.1.2 parallel, then 2.1.3)
- **Tests**: 12/12 passing (7 TestWorkspace + 5 TestLoader)

## Wave 2.1 Execution: Workspace Creation and Agent Drafting
- **Status**: complete
- **Workspace created**: `"./.venv/Scripts/python.exe" tests/create_ground_truth.py` ran successfully, 44 tables across 10 papers
- **Agent drafting**: 7 sonnet agents spawned (one per paper, 4 small papers batched together), all completed
- **All 44 GT JSON files populated** with agent-drafted headers and rows from blind image reading
- **Known issues for human review**:
  - friston-life table_0: Rendered PNG was too small/cropped — only captured caption and first line. Needs re-rendering with wider bbox before human review
  - reyes-lf-hrv tables 2/3: Agent flagged possible image/caption mismatch (table_2.png and table_3.png may be swapped)
  - roland-emg-filter table_2: Small image, digits may need careful verification
  - fortune-impedance table_4: Agent noted Ag/AgCl_SP and Ag_SP sections appear to have only 9 data rows (subject 10 not visible in image)
  - 5 artifact tables correctly identified as non-data: active-inference-tutorial table_0, fortune-impedance table_0, huang-emd-1998 table_0, huang-emd-1998 table_1, roland-emg-filter table_0, yang-ppv-meta table_3

## Wave 2.2: Human Review — NOT YET STARTED
- **Next step**: Human reviews each GT JSON against the paper PDF, corrects errors conversationally in Claude Code, marks each table as verified
- **After review**: Run `"./.venv/Scripts/python.exe" tests/load_ground_truth.py` to populate tests/ground_truth.db
- **Review procedure**: See tests/ground_truth_workspace/gt_prompt.md "Review Phase" section
