# Review Report: Step 4 — Integration

## Summary

| Item | Count |
|------|-------|
| Tasks reviewed | 8 (4.1.1, 4.1.2, 4.2.1, 4.2.2, 4.3.1, 4.3.2, 4.3.3, 4.4.1 + 4.4.2) |
| Violations — critical | 0 |
| Violations — major | 3 |
| Violations — minor | 4 |
| Gaps | 3 |
| Weak tests | 4 |
| Legacy references | 4 |

**Verdict**: `has-violations`

---

## Violations

### V-1 (major) — Hard-coded numeric threshold in `_assign_heading_captions`

**File**: `src/zotero_chunk_rag/pdf_processor.py`, line 940
**Rule violated**: CLAUDE.md — "No Hard-Coded Thresholds"
**Evidence**:
```python
        else:
            scan_distance = 60  # fallback
```
The adaptive path computes `scan_distance = (median_spacing + median_height) * 4` from the actual page data. The fallback of `60` is a hard literal. According to the project rules any numeric threshold must be adaptive or presented to the user for approval with alternatives — neither was done. A comment labelling it `# fallback` does not satisfy the rule; it confirms the author was aware and chose to hard-code regardless.

Also, at line 937:
```python
            else:
                median_height = 12
```
`median_height = 12` is a hard-coded fallback for the inner `line_heights` case. Same rule applies.

**Severity**: major

---

### V-2 (major) — Historical-provenance comment in `_extract_figures_for_page` spec note in `pdf_processor.py`

**File**: `src/zotero_chunk_rag/pdf_processor.py`

The spec for Task 4.3.2 required that `_extract_figures_for_page` accept an `optional all_captions: list[DetectedCaption] | None = None` parameter, and states:

> "When `None`, call it internally (backward compatibility, though no caller will use this path)."

The implementation at lines 139–147 changed the signature to require `all_captions: list` (non-optional, no default `None`):
```python
def _extract_figures_for_page(
    page: "pymupdf.Page",
    page_num: int,
    page_chunk: dict,
    write_images: bool,
    images_dir: "Path | None",
    doc: "pymupdf.Document",
    all_captions: list,
) -> "list[ExtractedFigure]":
```
The parameter is mandatory. While the spec described the optional/fallback path as one that "no caller will use", the implemented signature does not match the spec's specified interface. The spec was the source of truth for what must be built.

**Severity**: major

---

### V-3 (major) — `"no_hash"` reason string contains the word `"legacy"` (historical-provenance comment in code)

**File**: `src/zotero_chunk_rag/indexer.py`, line 109
**Rule violated**: `spec/.context/rules.md` — "No historical-provenance comments."
**Evidence**:
```python
            - "no_hash": Document indexed without hash (legacy), needs reindex
```
The word `"legacy"` appears in a docstring describing a return-value reason string. Per the rules, any comment describing historical behaviour, what code replaced, or why something changed is banned. The word `"legacy"` is an explicit red flag. Note that this text is inside the docstring of `_needs_reindex()` and was not introduced by Step 4 — however it appears in the modified file `indexer.py` and was not removed during the Step 4 modification, which modified lines in this file (adding `_vision_api` init).

**Severity**: major (rule is absolute; the file was modified and the violation was present and left in place)

---

### V-4 (minor) — `"backwards compatibility"` comment in `server.py`

**File**: `src/zotero_chunk_rag/server.py`, line 483
**Rule violated**: `spec/.context/rules.md` — "No historical-provenance comments."
**Evidence**:
```python
            # Raw similarity scores (kept for backwards compatibility)
```
This file was not modified by Step 4, so this is out-of-scope for this review. Flagged here for completeness but acknowledged as pre-existing.

**Severity**: minor (out of Step 4 scope — pre-existing)

---

### V-5 (minor) — `"# Skip for now, or make configurable"` in `zotero_client.py`

**File**: `src/zotero_chunk_rag/zotero_client.py`, line 155
**Rule violated**: `spec/.context/rules.md` — "Never mark work as deferred, TODO, or 'not implemented.'" Also matches "for now" red flag.
**Evidence**:
```python
            # Skip for now, or make configurable
```
Not in Step 4 scope — pre-existing, not modified by Step 4 tasks.

**Severity**: minor (out of Step 4 scope — pre-existing)

---

### V-6 (minor) — `"previously yielded"` in `indexer.py` docstring

**File**: `src/zotero_chunk_rag/indexer.py`, line 86
**Rule violated**: `spec/.context/rules.md` — "No historical-provenance comments."
**Evidence**:
```python
    def _load_empty_docs(self) -> dict[str, str]:
        """Load {item_key: pdf_hash} for docs that previously yielded no chunks."""
```
The word "previously" describes historical behaviour of the system (what documents did in a past run). This is a provenance comment — it describes system history rather than what the code does now. The file was modified in Step 4 (adding `_vision_api` init) but this line was not cleaned up.

**Severity**: minor

---

### V-7 (minor) — Hard-coded `scan_distance = 60` also carries a `# fallback` comment that justifies the rule violation

**File**: `src/zotero_chunk_rag/pdf_processor.py`, line 940
**Rule violated**: `spec/.context/rules.md` — "A justification comment next to a rule violation makes it worse, not better."
**Evidence**:
```python
            scan_distance = 60  # fallback
```
The `# fallback` label is a justification comment — it signals the author knew the threshold should be adaptive and wrote a comment to explain why a hard literal was used instead. Per reviewer rules, this makes the violation worse, not mitigating.

**Severity**: minor (additional finding under V-1; reported separately as required)

---

## Gaps

### G-1 — `_extract_figures_for_page` signature does not match spec

**Spec requirement** (Task 4.3.2):
> "Modify `_extract_figures_for_page`: Accept an optional `all_captions: list[DetectedCaption] | None = None` parameter. When provided, filter for figure captions from it instead of calling `find_all_captions()` internally. When `None`, call it internally (backward compatibility, though no caller will use this path)."

**What was found**: The parameter `all_captions: list` is required (no default `= None`). There is no `None` path that calls `find_all_captions()` internally. The "optional" part of the spec was dropped.

**File**: `src/zotero_chunk_rag/pdf_processor.py`, lines 139–147

---

### G-2 — `TestPrunedSchema::test_kept_tables_exist` does not check `vision_run_details`

**Spec requirement** (Task 4.2.1, test `test_kept_tables_exist`):
> "Assert: `'ground_truth_diffs'` and `'vision_agent_results'` ARE in table names."

The spec lists exactly these two tables. The test correctly asserts both. However the spec for Task 4.2.2 requires that `vision_run_details` is also created by `create_extended_tables()`, and this IS tested separately in `TestVisionRunDetails::test_table_created`. This is not a gap — noting here for completeness. No gap found on this item.

---

### G-3 — Stress test `to_markdown()` does not include a "Vision Extraction Report" section in the main body

**Spec requirement** (Task 4.4.2):
> "Integrate into main report: Call `_build_vision_extraction_report()` in the report assembly, replacing the deleted pipeline depth report section."

**What was found**: `_build_vision_extraction_report()` is called at lines 1859–1864, but it appends to the report file after the main `report.to_markdown()` call via file append. The `StressTestReport.to_markdown()` method (lines 254–344) has no "Vision Extraction Report" section in it — the section was not integrated into the class's own `to_markdown()` method. Instead, it is appended as a separate file write after the main report. The spec says to integrate it "in the report assembly" as a section replacing the pipeline depth report. While the section does appear in the final `STRESS_TEST_REPORT.md`, the assembly location is different from what the spec specified (it is appended, not integrated into the main report builder).

**File**: `tests/stress_test_real_library.py`, lines 1831–1864

---

## Weak Tests

### WT-1 — `test_debug_db.py::TestWrite::test_write_ground_truth_diff` — `assert row is not None` is a trivially-pre-checked guard

**Test path**: `tests/test_feature_extraction/test_debug_db.py::TestWrite::test_write_ground_truth_diff`
**Problem**: Line 166 asserts `assert row is not None` before proceeding to check specific field values. While the subsequent assertions are substantive, the `is not None` assertion itself does not test behaviour — it is trivially implied by the fact that a row was just inserted by the function under test. If the insert silently failed and returned nothing, the `fetchone()` would return `None` and this assertion would fail — but the proper test is to check that the actual field values are what was written, which the following lines do. The `assert row is not None` adds nothing meaningful and is the pattern flagged as a weak assertion.

**Evidence**:
```python
        assert row is not None
        assert row[0] == "paper2_table_3"
```

---

### WT-2 — `test_debug_db.py::TestVisionRunDetails::test_write_and_read` — `assert row is not None` same pattern

**Test path**: `tests/test_feature_extraction/test_debug_db.py::TestVisionRunDetails::test_write_and_read`
**Problem**: Same pattern as WT-1. Line 243 asserts `assert row is not None` before substantive checks. The write was just done unconditionally; `is not None` tells us nothing about correct behaviour.

**Evidence**:
```python
        assert row is not None
        assert row[0] == "paper1_table_1"
```

---

### WT-3 — `test_pdf_processor.py::TestExtractDocument::test_vision_details_populated` — `assert extraction.vision_details is not None` as a standalone assertion

**Test path**: `tests/test_pdf_processor.py::TestExtractDocument::test_vision_details_populated`
**Problem**: Line 458 asserts `assert extraction.vision_details is not None` as the first meaningful assertion. While line 459 then checks `len(extraction.vision_details) == 1` which is substantive, the preceding `is not None` is trivially implied by the mock setup. The spec requires asserting key content of the details dict — the test only checks that 4 named keys *exist* in the dict (lines 461–464), but does not assert the *values* of those keys. The spec says to assert: `text_layer_caption`, `vision_caption`, `recropped`, `parse_success` — these are only key-existence checks, not value checks.

**Evidence**:
```python
        assert extraction.vision_details is not None
        assert len(extraction.vision_details) == 1
        detail = extraction.vision_details[0]
        assert "text_layer_caption" in detail
        assert "vision_caption" in detail
        assert "recropped" in detail
        assert "parse_success" in detail
```
The presence of keys is tested but not their values. `detail["text_layer_caption"]` should equal `"Table 1"` (the text-layer caption used). `detail["vision_caption"]` should equal `"Table 1. Full title"` (the vision response caption). `detail["parse_success"]` should be `True`. These are trivially true from the mock but the test does not assert them.

---

### WT-4 — `test_indexer_vision.py::TestIndexerInit::test_vision_api_created_with_key` — `assert indexer._vision_api is not None` only

**Test path**: `tests/test_indexer_vision.py::TestIndexerInit::test_vision_api_created_with_key`
**Problem**: The sole assertion is `assert indexer._vision_api is not None`. The spec says to assert that `VisionAPI` was constructed when the key is set — but `is not None` verifies only that the attribute is not `None`, not that it is a `VisionAPI` instance, not that it was constructed with the correct `api_key` or `cost_log_path`. The assertion would pass if `_vision_api` were set to any non-None object. The acceptance criterion ("`VisionAPI` constructed with cost log in the chroma db parent dir") is not verified.

**Evidence**:
```python
        assert indexer._vision_api is not None
```

---

## Legacy References

### LR-1 — `"(legacy)"` in `indexer.py` docstring describes historical system state

**File**: `src/zotero_chunk_rag/indexer.py`, line 109
**Quoted evidence**:
```python
            - "no_hash": Document indexed without hash (legacy), needs reindex
```
The word `"legacy"` is a historical-provenance label. The rules ban any reference to legacy, historical, or prior-state behaviour in code.

---

### LR-2 — `"previously"` in `indexer.py` docstring describes historical system state

**File**: `src/zotero_chunk_rag/indexer.py`, line 86
**Quoted evidence**:
```python
        """Load {item_key: pdf_hash} for docs that previously yielded no chunks."""
```
The word `"previously"` is an explicit historical-provenance term. The rules ban this.

---

### LR-3 — `"# fallback"` in `pdf_processor.py` describes a known rule-breaking fallback

**File**: `src/zotero_chunk_rag/pdf_processor.py`, line 940
**Quoted evidence**:
```python
            scan_distance = 60  # fallback
```
The label `"fallback"` is an explicit red-flag term from the rules list. It labels code that the author knew was a rule violation.

---

### LR-4 — `"# Heading-based caption fallback"` comment in `pdf_processor.py`

**File**: `src/zotero_chunk_rag/pdf_processor.py`, line 373
**Quoted evidence**:
```python
    # Heading-based caption fallback for orphan tables (e.g. "Abbreviations")
```
The word `"fallback"` appears in an inline comment describing a code path. By the rules' definition, this is a banned red-flag term. This describes what the code does as a fallback strategy, which a future developer could understand by reading the function name `_assign_heading_captions`. The comment is purely descriptive of historical/alternative behaviour.

Note: Lines 423 and 478 also contain `"fallback"` in comments within `pdf_processor.py` (`# heading fallback, continuation` and `# or section-header page_boxes (fallback)`). These are additional instances; the most flagrant is LR-3 above which is on a hard-coded threshold line. LR-4 covers the remaining instances collectively.

---

## Detailed Per-Task Assessment

### Task 4.1.1 (Refactor `cell_cleaning.py`)
- `from ..models import CellGrid` — ABSENT. Correct.
- `CellCleaning` class — ABSENT. Correct.
- `clean_cells()` function — PRESENT, correct signature, all 5 normalization steps applied in order.
- `_map_control_chars` not called by `clean_cells()` — CORRECT.
- `_normalize_ligatures` independently importable — CORRECT.
- **No violations specific to this task.**

### Task 4.1.2 (Rewrite `test_pp_cell_cleaning.py`)
- `CellGrid` import — ABSENT. Correct.
- `CellCleaning` import — ABSENT. Correct.
- `_make_grid` helper — ABSENT. Correct.
- `TestCellCleaning` class — ABSENT. Correct.
- `TestCleanCells` class — PRESENT with all 8 required tests, all matching spec assertions exactly.
- Standalone function tests (`TestNormalizeLigatures`, `TestRecoverLeadingZeros`, `TestReassembleNegativeSigns`, `TestMapControlChars`) — PRESENT and retained.
- **No violations specific to this task.**

### Task 4.2.1 (Delete pipeline tables/functions from `debug_db.py`)
- `method_results`, `pipeline_runs`, `vision_consensus` tables — ABSENT from `EXTENDED_SCHEMA`. Correct.
- `write_method_result`, `write_pipeline_run`, `write_vision_consensus` functions — ABSENT. Correct.
- `create_extended_tables`, `write_ground_truth_diff`, `write_vision_agent_result` — PRESENT. Correct.
- All 5 required tests present with correct assertions.
- **No violations specific to this task.**

### Task 4.2.2 (Add `vision_run_details` table)
- `vision_run_details` table in `EXTENDED_SCHEMA` — PRESENT with all specified columns. Correct.
- `write_vision_run_detail()` function — PRESENT, uses `INSERT OR REPLACE`, correct parameter handling.
- All 3 required tests present. Tests `test_write_and_read` and `test_upsert` are substantive and test actual values.
- Weak `assert row is not None` guards noted in WT-1 and WT-2.
- **No task-specific spec violations.**

### Task 4.3.1 (Add `vision_details` field to `DocumentExtraction`)
- `vision_details: list[dict] | None = None` field — PRESENT on `DocumentExtraction`. Correct.
- Both required tests present in `tests/test_models.py`.
- `test_vision_details_accepts_list` checks `len == 1` AND the dict content (`extraction.vision_details[0]["text_layer_caption"] == "Table 1"`). This is adequately substantive.
- **No violations specific to this task.**

### Task 4.3.2 (Rewire `extract_document()`)
- Imports: `compute_all_crops`, `compute_recrop_bbox`, `clean_cells` — PRESENT at top level.
- `VisionAPI`, `TableVisionSpec` under `TYPE_CHECKING` — CORRECT.
- Signature: `vision_api: "VisionAPI | None" = None` — PRESENT. Correct.
- `find_all_captions` called once per page — CONFIRMED (line 256, single call per page).
- Vision extraction block: `TableVisionSpec` construction, batch call, re-crop pass — ALL PRESENT and correct.
- Re-crop: max 1 pass, keeps original if `is_incomplete` — CONFIRMED.
- `clean_cells` applied — CONFIRMED (line 355).
- Caption fallback logic — CONFIRMED (line 356).
- `vision_details` populated — CONFIRMED.
- `_extract_figures_for_page` signature gap — see G-1 and V-2.
- All 9 required tests present with correct assertions for the main behaviours.
- Weak test WT-3 noted.

### Task 4.3.3 (Update `indexer.py`)
- `os.environ.get("ANTHROPIC_API_KEY")` — PRESENT in `__init__()`.
- `VisionAPI` constructed when key set — CONFIRMED.
- `cost_log_path = config.chroma_db_path.parent / "vision_costs.json"` — CONFIRMED.
- `_vision_api = None` when unset — CONFIRMED.
- `vision_api=self._vision_api` passed to `extract_document()` — CONFIRMED (line 308).
- Both required tests present.
- Weak test WT-4 noted.
- Legacy references LR-1, LR-2 in this file noted.

### Task 4.4.1 (Fix imports and delete dead code in stress test)
- `write_method_result`, `write_pipeline_run`, `write_vision_consensus` — ABSENT from imports. Correct.
- `write_vision_run_detail` — PRESENT in imports. Correct.
- `_EVAL_STAGE_PAIRS`, `_eval_cell_diff`, multi-agent code — not found in file. Correct.
- `_build_pipeline_depth_report` — not found in file. Correct.
- `vision_result_to_cell_grid`, `Pipeline`, `DEFAULT_CONFIG` — not found in file. Correct.
- GT comparison section — PRESENT and unchanged. Correct.
- **No violations specific to this task.**

### Task 4.4.2 (Add single-agent vision extraction report)
- `write_vision_agent_result()` called per vision detail entry — CONFIRMED (lines 1582–1597).
- `write_vision_run_detail()` called per vision detail entry — CONFIRMED (line 1598).
- `_build_vision_extraction_report()` — PRESENT (lines 1710–1809).
- Report contains: total tables, parse success rate, re-crop rate, incomplete count, per-paper breakdown, caption changes — ALL PRESENT.
- GT table IDs use text-layer caption — CONFIRMED (line 1578).
- Gap G-3: vision report appended to file rather than integrated into `to_markdown()` body — noted.
