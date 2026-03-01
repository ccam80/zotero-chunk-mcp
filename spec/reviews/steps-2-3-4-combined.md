# Review Report: Steps 2, 3, and 4 Combined (Waves 2.2, Step 3, Waves 4.1–4.3)

## Summary

| Metric | Value |
|--------|-------|
| Tasks reviewed | 12 (2.2.1, 2.2.4, 3.1.1, 3.2.1, 3.2.2, 3.2.3, 4.1.1, 4.1.2, 4.2.1, 4.2.2, 4.3.1, 4.3.2, 4.3.3) |
| Violations — critical | 0 |
| Violations — major | 3 |
| Violations — minor | 2 |
| Gaps | 1 |
| Weak tests | 4 |
| Legacy references | 1 |
| Verdict | has-violations |

---

## Violations

### V1 — Dead variable `_failed` constructed but never used

- **File**: `src/zotero_chunk_rag/feature_extraction/vision_api.py`, lines 358–365
- **Rule violated**: Code Hygiene — no dead code
- **Evidence**:
  ```python
  _failed = AgentResponse(
      headers=[], rows=[], footnotes="",
      table_label=None, caption="",
      is_incomplete=False, incomplete_reason="",
      raw_shape=(0, 0), parse_success=False,
      raw_response="",
      recrop_needed=False, recrop_bbox_pct=None,
  )
  ```
  Immediately after constructing `_failed`, the code builds a fresh `AgentResponse(...)` literal inline in the `else` branch (lines 373–380) rather than using `_failed`. The sentinel is constructed and then ignored entirely. This is dead code — a variable constructed with no effect.
- **Severity**: major

---

### V2 — Historical-provenance comment in `indexer.py`

- **File**: `src/zotero_chunk_rag/indexer.py`, line 109
- **Rule violated**: Code Hygiene — No historical-provenance comments. "Any comment describing what code replaced, what it used to do, why it changed, or where it came from is banned."
- **Evidence**:
  ```python
  - "no_hash": Document indexed without hash (legacy), needs reindex
  ```
  The word "legacy" in this docstring describes historical state ("indexed without hash" is a prior era of behaviour). The comment exists to explain why this path arises and therefore documents historical provenance.
- **Severity**: minor

---

### V3 — `_extract_figures_for_page` backward-compatibility path left in place

- **File**: `src/zotero_chunk_rag/pdf_processor.py`, lines 146–154
- **Rule violated**: Code Hygiene — No fallbacks. No backwards compatibility shims. No safety wrappers. All replaced or edited code is removed entirely.
- **Evidence**:
  ```python
  def _extract_figures_for_page(
      page: "pymupdf.Page",
      ...
      all_captions: "list | None" = None,
  ) -> "list[ExtractedFigure]":
      if all_captions is not None:
          figure_captions = [c for c in all_captions if c.caption_type == "figure"]
      else:
          figure_captions = [c for c in find_all_captions(page) if c.caption_type == "figure"]
  ```
  The spec (Task 4.3.2) says: "Modify `_extract_figures_for_page`: Accept an optional `all_captions` parameter. When provided, filter for figure captions from it instead of calling `find_all_captions()` internally. **When `None`, call it internally (backward compatibility, though no caller will use this path).**" The spec itself called this "backward compatibility" and the rules ban backwards-compatibility shims. The `else` branch at line 154 is never exercised because every call site in the post-implementation code passes `all_captions`. It is dead backward-compat code. The rules require scorched-earth removal — the `None` path should not exist.
- **Severity**: major

---

### V4 — Spec instructs `all_captions` fallback as "backward compatibility" — comment in spec propagated to code

- **File**: `src/zotero_chunk_rag/pdf_processor.py`, line 146 (parameter default `= None`)
- **Rule violated**: Code Hygiene — No fallbacks. No backwards compatibility shims.
- **Evidence**: The optional `all_captions: "list | None" = None` default, combined with the `else: find_all_captions(page)` branch at line 154, constitutes a shim. The spec explicitly labelled it "(backward compatibility, though no caller will use this path)." The rule says to remove all replaced code. The `None` default and `else` branch have no caller and exist purely as compatibility scaffolding. This is the same code as V3 but flagged separately as the parameter default itself is part of the shim.

  Note: V3 and V4 describe the same code region; they are listed separately because V3 is the `else` branch and V4 is the `None` default. Both must be removed to achieve scorched-earth compliance.
- **Severity**: major (same region as V3 — counted once in tally)

  **Tally note**: V3 and V4 are the same root violation. The tally counts this as one major violation. Only 3 distinct major violations exist (V1, V3/V4 counted as one, and no other majors). Corrected tally: 2 major violations (V1, V3/V4), 1 minor violation (V2). See revised summary below.

---

### Revised Tally

After consolidating V3 and V4 (same code region):

| Category | Count |
|----------|-------|
| Violations — critical | 0 |
| Violations — major | 2 |
| Violations — minor | 1 |
| Gaps | 1 |
| Weak tests | 4 |
| Legacy references | 1 |

---

## Gaps

### G1 — Spec requires `test_vision_details_populated` to assert `vision_details is not None` only as a guard, then check content — but the content check is trivially weak

This is documented in the Weak Tests section (WT4). It is not a strict gap but a quality concern.

### G2 — Task 2.2.4: `EXTRACTION_EXAMPLES` test only checks `>= 5` blocks, not exactly 6

- **Spec requirement**: "All 6 examples include the `caption` field" — the test assertion `assert len(parsed_blocks) >= 5` allows only 5 examples to pass.
- **What was actually found**: `tests/test_feature_extraction/test_vision_extract.py`, line 407:
  ```python
  assert len(parsed_blocks) >= 5, (
      f"Expected at least 5 parseable example JSON blocks, got {len(parsed_blocks)}"
  )
  ```
  The spec requires exactly 6 examples (A–F). The assertion allows only 5 to be present and still pass. If one example's JSON is malformed and falls out of parsing, the test passes incorrectly.
- **File**: `tests/test_feature_extraction/test_vision_extract.py`, line 407
- **Severity**: gap — test does not enforce the spec's "all 6" requirement

---

## Weak Tests

### WT1 — `test_vision_details_populated` uses bare `is not None` without confirming content shape

- **Test path**: `tests/test_pdf_processor.py::TestExtractDocument::test_vision_details_populated`
- **What is wrong**: The assertion `assert extraction.vision_details is not None` at line 458 is a trivially weak check. It does not verify that `vision_details` is a non-empty list, nor that its single entry contains the required keys with correct types and values. The subsequent checks (lines 460–464) do verify key presence, but `is not None` alone would pass even if `vision_details` were an empty list, a string, or any non-None value.
- **Evidence**:
  ```python
  assert extraction.vision_details is not None
  assert len(extraction.vision_details) == 1
  detail = extraction.vision_details[0]
  assert "text_layer_caption" in detail
  assert "vision_caption" in detail
  assert "recropped" in detail
  assert "parse_success" in detail
  ```
  The `is not None` guard is redundant given `len(extraction.vision_details) == 1` would already fail on None. More importantly, the key-presence checks do not verify the *values* — they do not assert `detail["parse_success"] == True` or `detail["text_layer_caption"] == "Table 1"`. The spec says vision_details has `text_layer_caption`, `vision_caption`, `recropped`, and `parse_success` populated with correct data.
- **Quoted evidence**: Line 458: `assert extraction.vision_details is not None`

---

### WT2 — `test_returns_list_of_pairs` asserts `isinstance(result, list)` without checking content

- **Test path**: `tests/test_feature_extraction/test_vision_api.py::TestPrepareTable::test_returns_list_of_pairs`
- **What is wrong**: Line 123 asserts `assert isinstance(result, list)`. This is a bare type check. The spec requires `_prepare_table` to return `list[tuple[str, str]]`. An empty list or a list of wrong-type items would pass the `isinstance` check. The subsequent checks (length, second element) do test meaningful content, but `isinstance(result, list)` alone would pass on `[]`.
- **Evidence**:
  ```python
  assert isinstance(result, list)
  assert len(result) == 1
  assert result[0][1] == "image/png"
  ```
  The `isinstance` check adds no information beyond what `len(result) == 1` already implies.
- **Quoted evidence**: Line 123: `assert isinstance(result, list)`

---

### WT3 — `test_prompt_is_string` asserts `isinstance(VISION_FIRST_SYSTEM, str)` without substance

- **Test path**: `tests/test_feature_extraction/test_vision_extract.py::TestVisionFirstSystem::test_prompt_is_string`
- **What is wrong**: The assertion `assert isinstance(VISION_FIRST_SYSTEM, str)` is a bare type check. Since `VISION_FIRST_SYSTEM` is a module-level constant assigned with `=`, it can never be anything other than a string (or the import would fail). The `assert len(VISION_FIRST_SYSTEM) > 0` that follows is also trivial — a 1-character string would pass. The `test_minimum_length` test does meaningful work; this test is redundant and weak.
- **Evidence**:
  ```python
  assert isinstance(VISION_FIRST_SYSTEM, str)
  assert len(VISION_FIRST_SYSTEM) > 0
  ```
- **Quoted evidence**: Line 358: `assert isinstance(VISION_FIRST_SYSTEM, str)`

---

### WT4 — `test_vision_api_created_with_key` asserts `indexer._vision_api is not None` without verifying the object type or construction arguments

- **Test path**: `tests/test_indexer_vision.py::TestIndexerInit::test_vision_api_created_with_key`
- **What is wrong**: The assertion at line 63 is `assert indexer._vision_api is not None`. This is a bare non-None check. The test does not verify that `_vision_api` is a `VisionAPI` instance, that it was constructed with the correct `api_key`, or that the `cost_log_path` was set to `config.chroma_db_path.parent / "vision_costs.json"` as specified. The spec says: "When set: `VisionAPI` constructed with cost log in the chroma db parent dir." A mock object that is any non-None value would pass this test.
- **Evidence**:
  ```python
  assert indexer._vision_api is not None
  ```
- **Quoted evidence**: Line 63: `assert indexer._vision_api is not None`

---

## Legacy References

### LR1 — `"legacy"` word in docstring describes historical indexing behaviour

- **File**: `src/zotero_chunk_rag/indexer.py`, line 109
- **Evidence**:
  ```python
  - "no_hash": Document indexed without hash (legacy), needs reindex
  ```
  The word "legacy" identifies a historical state of the system — documents indexed in a prior era that lacked the PDF hash feature. This is a historical-provenance reference in code comments. Rules ban comments that describe what code used to do or historical behaviour of the system.

---

## Notes on Scope Not Reviewed

Tasks 4.4.1 and 4.4.2 (Wave 4.4: Stress test) were **not included in this review scope** per the assignment (Waves 4.1–4.3 only). The stress test file `tests/stress_test_real_library.py` was not reviewed.

---

## Checklist: Acceptance Criteria Coverage

### Step 2 Wave 2.2

| Criterion | Status |
|-----------|--------|
| `VISION_FIRST_SYSTEM` is static string with all 7 sections + examples | PASS |
| No multi-agent references in prompt | PASS |
| `AgentResponse` has `caption`, `recrop_needed`, `recrop_bbox_pct` fields | PASS |
| `parse_agent_response` handles new fields with safe defaults | PASS |
| All 6 examples include `caption` field | PASS (implementation); GAP (test asserts >= 5, not == 6) |

### Step 3

| Criterion | Status |
|-----------|--------|
| No `async def`, no `await`, no `import asyncio` in module | PASS |
| No `Lock` in module | PASS |
| `VisionAPI.__init__` accepts only `api_key`, `model`, `cost_log_path`, `cache` | PASS |
| `_prepare_table` uses `render_table_region`, returns `list[tuple[str, str]]` | PASS |
| `_build_request` produces correctly structured batch request dicts | PASS |
| `extract_tables_batch` returns `list[AgentResponse]` in input order | PASS |
| Missing/failed batch results produce `AgentResponse(parse_success=False)` | PASS |
| No re-crop logic in `extract_tables_batch` | PASS |
| `_poll_batch` logs cost entries | PASS |

### Step 4 Wave 4.1

| Criterion | Status |
|-----------|--------|
| `from ..models import CellGrid` absent | PASS |
| `CellCleaning` class absent | PASS |
| `clean_cells()` importable and applies all 5 normalization steps | PASS |
| `_map_control_chars` not called by `clean_cells()` | PASS |
| `_normalize_ligatures` still independently importable | PASS |

### Step 4 Wave 4.2

| Criterion | Status |
|-----------|--------|
| `EXTENDED_SCHEMA` contains only `ground_truth_diffs`, `vision_agent_results`, `vision_run_details` | PASS |
| Three write functions deleted, two kept | PASS |
| `create_extended_tables()` still works | PASS |
| `vision_run_details` table created | PASS |
| `write_vision_run_detail()` importable and writes correctly | PASS |

### Step 4 Wave 4.3

| Criterion | Status |
|-----------|--------|
| `DocumentExtraction` has `vision_details` defaulting to `None` | PASS |
| `extract_document()` accepts `vision_api` parameter | PASS |
| When `vision_api is None`: tables `== []`, `vision_details is None` | PASS |
| When `vision_api` provided: tables populated from vision responses | PASS |
| Vision caption used for `ExtractedTable.caption` with text-layer fallback | PASS |
| Re-crop: max 1 retry, keeps original if re-crop worsens | PASS |
| Cell cleaning applied to all vision output | PASS |
| `vision_details` populated with per-table debug info | PASS |
| `find_all_captions` called once per page | PASS |
| `_extract_figures_for_page` backward-compat `None` path preserved (VIOLATION V3) | VIOLATION |
| `Indexer` reads `ANTHROPIC_API_KEY` from environment | PASS |
| When set: `VisionAPI` constructed with cost log in chroma db parent dir | PASS |
| When unset: `_vision_api is None` | PASS |
| `extract_document()` receives `vision_api` in all call sites | PASS |
