# Phase 3: LLM Prompt Method

## Overview

Create a prompt-based workflow for vision-model table structure detection. The user
or an agent runs cropped table PNGs through a vision model (Sonnet or Haiku) with a
structured prompt, and the results are parsed into BoundaryHypothesis objects, run
through cell extraction, scored against ground truth, and injected into the debug DB
for evaluation alongside other methods.

This is NOT an API-integrated pipeline method. It is an offline evaluation workflow
that answers the question: "Can a vision model beat the multi-method pipeline at
table structure detection?"

**Depends on**: Phase 1 (fuzzy accuracy metric) + Phase 2 (working combination engine)

**Entry state**: No LLM-based structure detection exists.
**Exit state**: Evaluation infrastructure in `tests/llm_structure/` with per-table
accuracy data for Sonnet and Haiku, comparison report against pipeline methods.

---

## Wave 3.1: Prompt generation

### Task 3.1.1: Generate table PNGs and prompts

- **Description**: Create `tests/llm_structure/generate_prompts.py`. For each GT
  table in the ground truth database:
  1. Open the PDF, navigate to the table's page
  2. Render the table region as a cropped PNG (reuse pymupdf rendering:
     `page.get_pixmap(clip=bbox, dpi=200)`)
  3. Save to `tests/llm_structure/tables/<table_id>/table.png`
  4. Generate the prompt by reading the template from
     `tests/llm_structure/prompt_template.md` and appending any table-specific
     context (bbox dimensions, page number)
  5. Save prompt to `tests/llm_structure/tables/<table_id>/prompt.md`
  6. Generate a manifest JSON at `tests/llm_structure/manifest.json` listing all
     table IDs, their PDF paths, page numbers, and bbox coordinates

  The script needs to resolve PDF paths. GT entries have `paper_key` — the stress
  test corpus maps paper_key to PDF path via the Zotero library. The script should
  accept a `--corpus-json` argument pointing to a JSON file that maps paper_key to
  PDF path, OR reuse the CORPUS list from `stress_test_real_library.py` directly.

- **Files to create**:
  - `tests/llm_structure/generate_prompts.py` — main script
  - `tests/llm_structure/__init__.py` — empty package marker

- **Tests**:
  - `tests/test_feature_extraction/test_llm_structure.py::TestPromptGeneration::test_script_importable` —
    assert `generate_prompts` module imports without error
  - `tests/test_feature_extraction/test_llm_structure.py::TestPromptGeneration::test_manifest_schema` —
    run generation on 1 table (mock or fixture), verify manifest JSON has expected
    keys: `table_id`, `pdf_path`, `page_num`, `bbox`

- **Acceptance criteria**:
  - Script generates PNG + prompt for each GT table
  - PNGs are readable images showing the table region
  - Manifest JSON is valid and lists all generated tables
  - Prompt references the correct coordinate system (fractions of bbox)

### Task 3.1.2: Prompt template

- **Description**: Write the prompt template that instructs a vision model to
  identify table structure. The prompt should:
  - Explain the coordinate system: fractions of the table bbox (0.0 = left/top
    edge, 1.0 = right/bottom edge)
  - Request ONLY internal dividers (not the outer bbox edges)
  - Request JSON output: `{"columns": [{"position": float, "confidence": "high"|"medium"|"low"}, ...], "rows": [...]}`
  - Include a worked example showing a 3-column, 4-row table's expected output
  - Note that position values should be where the divider LINE would be drawn
    (between columns/rows), not column/row centers

- **Files to create**:
  - `tests/llm_structure/prompt_template.md` — the prompt template

- **Tests**:
  - `tests/test_feature_extraction/test_llm_structure.py::TestPromptTemplate::test_template_exists` —
    assert file exists and is non-empty
  - `tests/test_feature_extraction/test_llm_structure.py::TestPromptTemplate::test_template_contains_json_example` —
    assert template contains `"columns"` and `"rows"` and `"position"`

- **Acceptance criteria**:
  - Template clearly explains the coordinate system
  - Example JSON output is valid JSON
  - Instructions are unambiguous about internal-only dividers

---

## Wave 3.2: Response parsing + injection

### Task 3.2.1: Parse LLM responses into BoundaryHypothesis objects

- **Description**: Create `tests/llm_structure/parse_responses.py`. Reads LLM
  response JSON files placed by the user at
  `tests/llm_structure/tables/<table_id>/response_sonnet.json` and/or
  `response_haiku.json`.

  For each response:
  1. Parse the JSON (handle common model quirks: markdown code fences wrapping
     JSON, extra text before/after the JSON block)
  2. Validate structure: must have `columns` and `rows` arrays, each element must
     have `position` (float) and `confidence` (string)
  3. Convert fractional positions to absolute PDF coordinates using the table's
     bbox from the manifest: `abs_pos = bbox_min + fraction * (bbox_max - bbox_min)`
  4. Map confidence labels to scores: `high=0.9`, `medium=0.6`, `low=0.3`
  5. Create a `BoundaryHypothesis` with provenance `"llm_sonnet"` or `"llm_haiku"`
  6. Report parsing errors (invalid JSON, missing fields, positions outside 0-1)
     to stderr without crashing

  Provide a function `parse_response(table_id, model_name, manifest, response_path) -> BoundaryHypothesis | None`
  for programmatic use, plus a CLI that processes all tables.

- **Files to create**:
  - `tests/llm_structure/parse_responses.py`

- **Tests**:
  - `tests/test_feature_extraction/test_llm_structure.py::TestResponseParsing::test_valid_json_parsed` —
    create a synthetic response JSON with known positions. Assert returned
    BoundaryHypothesis has correct col/row boundary count and positions within
    tolerance of expected absolute coordinates.
  - `tests/test_feature_extraction/test_llm_structure.py::TestResponseParsing::test_markdown_fenced_json` —
    response wrapped in ```json ... ```. Assert still parsed correctly.
  - `tests/test_feature_extraction/test_llm_structure.py::TestResponseParsing::test_invalid_json_returns_none` —
    malformed JSON returns None without crashing.
  - `tests/test_feature_extraction/test_llm_structure.py::TestResponseParsing::test_confidence_mapping` —
    "high" -> 0.9, "medium" -> 0.6, "low" -> 0.3 on the resulting BoundaryPoints.

- **Acceptance criteria**:
  - Valid response JSON produces a correct BoundaryHypothesis
  - Markdown-fenced JSON is handled
  - Invalid input returns None with error message (no crash)
  - Confidence labels correctly mapped to scores
  - Positions correctly converted from fractions to absolute PDF coordinates

### Task 3.2.2: Inject LLM boundaries and evaluate against GT

- **Description**: Create `tests/llm_structure/inject_and_evaluate.py`. For each
  parsed BoundaryHypothesis from LLM responses:
  1. Open the PDF, build a `TableContext` for the table region
  2. Resolve col/row boundary midpoints from the BoundaryHypothesis
  3. Run each cell extraction method (rawdict, words, pdfminer) against the
     LLM boundaries — call each method's `extract(ctx, col_positions, row_positions)`
     directly
  4. For each resulting CellGrid, compute `fuzzy_accuracy_pct` against ground truth
     via `compare_extraction()`
  5. Write `method_results` rows to the debug DB with method_name
     `"llm_sonnet+rawdict"`, `"llm_sonnet+word_assignment"`, etc.
  6. Print a summary table: table_id, model, cell_method, fuzzy_accuracy

  The script reads the manifest and response files, opens the debug DB
  (`_stress_test_debug.db`), and appends rows. It should be safe to run
  multiple times (uses INSERT, not REPLACE — accumulates results).

- **Files to create**:
  - `tests/llm_structure/inject_and_evaluate.py`

- **Tests**:
  - `tests/test_feature_extraction/test_llm_structure.py::TestInjection::test_script_importable` —
    assert module imports without error
  - Full integration is tested by actually running the script after obtaining model
    responses — acceptance verified via the debug DB contents.

- **Acceptance criteria**:
  - Cell extraction runs successfully against LLM boundaries
  - `method_results` rows written with correct method names (`llm_<model>+<cell_method>`)
  - Fuzzy accuracy scores computed and stored
  - Script handles missing response files gracefully (skips, doesn't crash)

---

## Wave 3.3: Model comparison

### Task 3.3.1: Comparison report generator

- **Description**: Create `tests/llm_structure/compare_models.py`. Reads
  `method_results` from the debug DB for all `llm_sonnet` and `llm_haiku` entries.
  Produces a comparison report:

  1. **Per-table accuracy**: table_id, Sonnet best accuracy, Haiku best accuracy,
     best non-LLM method accuracy, pipeline consensus accuracy
  2. **Tables where LLM wins**: tables where LLM accuracy > best non-LLM method
  3. **Tables where LLM loses**: tables where LLM accuracy < best non-LLM method
  4. **Overall win rates**: Sonnet wins, Haiku wins, pipeline wins
  5. **Summary statistics**: mean/median accuracy per approach

  Output: `tests/llm_structure/comparison_report.md`

- **Files to create**:
  - `tests/llm_structure/compare_models.py`

- **Tests**:
  - `tests/test_feature_extraction/test_llm_structure.py::TestComparison::test_script_importable` —
    assert module imports without error
  - Full integration tested by running after injection.

- **Acceptance criteria**:
  - Report generated as markdown at the expected path
  - Report shows per-table comparison with all approaches
  - Win rates computed correctly
  - Report is readable and actionable (shows where LLM method adds value)
