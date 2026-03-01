# Review Report: Step 3 — API Layer

## Summary

- **Tasks reviewed**: 4 (3.1.1, 3.2.1, 3.2.2, 3.2.3)
- **Files reviewed**:
  - `src/zotero_chunk_rag/feature_extraction/vision_api.py` (modified)
  - `tests/test_feature_extraction/test_vision_api.py` (created)
- **Violations**: 2 (0 critical, 1 major, 1 minor)
- **Gaps**: 1
- **Weak tests**: 1
- **Legacy references**: 0
- **Verdict**: `has-violations`

---

## Violations

### V-01 — Major

- **File**: `src/zotero_chunk_rag/feature_extraction/vision_api.py`, line 23
- **Rule violated**: CLAUDE.md — "No Hard-Coded Thresholds" / spec Task 3.2.2 acceptance criteria (`max_tokens = 4096`)
- **Quoted evidence**:
  ```python
  import pymupdf
  ```
  Inside `_prepare_table()` (line 263 in the module body, but the `import pymupdf` on line 23 is at module top-level via a `try/except` guard, AND there is a second `import pymupdf` at line 23 of `_prepare_table`):
  ```python
  def _prepare_table(self, spec: TableVisionSpec) -> list[tuple[str, str]]:
      ...
      doc = pymupdf.open(str(spec.pdf_path))
  ```
  The spec (Task 3.2.1) prescribes that `_prepare_table` contains a local `import pymupdf` inside the function body:
  ```python
  def _prepare_table(self, spec: TableVisionSpec) -> list[tuple[str, str]]:
      import pymupdf
      doc = pymupdf.open(str(spec.pdf_path))
  ```
  The actual implementation omits this local import and instead relies solely on the module-level `try/except` guard (`pymupdf = None` on import failure). The module-level guard sets `pymupdf` to `None` on ImportError, which means calling `pymupdf.open(...)` when the package is absent will raise `AttributeError: 'NoneType' object has no attribute 'open'` rather than a clear `ImportError`. The spec's local import was the prescribed mechanism.

- **Severity**: Major — the spec explicitly prescribes `import pymupdf` inside the function body; the implementation diverges, making the absence of the package produce a confusing `AttributeError` rather than the expected `ImportError`. It is a spec adherence failure.

---

### V-02 — Minor

- **File**: `src/zotero_chunk_rag/feature_extraction/vision_api.py`, line 358–365
- **Rule violated**: rules.md — "Never mark work as deferred, TODO, or not implemented" / Code Hygiene — no feature flags or sentinel patterns that silently swallow errors
- **Quoted evidence**:
  ```python
  failed = AgentResponse(
      headers=[], rows=[], footnotes="",
      table_label=None, caption="",
      is_incomplete=False, incomplete_reason="",
      raw_shape=(0, 0), parse_success=False,
      raw_response="",
      recrop_needed=False, recrop_bbox_pct=None,
  )
  ```
  The `failed` sentinel is defined once and then shared across ALL missing results in the loop:
  ```python
  for spec in specs:
      raw_text = results.get(f"{spec.table_id}__transcriber")
      if raw_text is not None:
          responses.append(parse_agent_response(raw_text, "transcriber"))
      else:
          responses.append(failed)
  ```
  Every missing result appends the exact same `AgentResponse` object (not a copy). If any downstream consumer mutates the returned object, all failed entries in the list will be corrupted simultaneously. The spec prescribes the sentinel fields but does not prescribe a shared-object pattern. This is a correctness risk.

- **Severity**: Minor — the spec does not explicitly prohibit this pattern, but it is a latent mutation bug introduced by the implementation that is not present in the spec's pseudocode.

---

## Gaps

### G-01

- **Spec requirement**: Task 3.1.1, Acceptance Criteria — "`VisionAPI.__init__` accepts only `api_key`, `model`, `cost_log_path`, `cache`". The spec also states Task 3.1.1 Tests must include `test_init_no_dpi_param` checking that `dpi=300` raises `TypeError`, but makes no mention of a corresponding test for `padding_px`. However, the spec's init parameter list explicitly removes `padding_px` alongside `dpi` and `concurrency`. The task description (line "Remove `dpi` and `padding_px` parameters") mandates that `padding_px` is also removed.
- **What was actually found**: The test suite has `test_init_no_concurrency_param` and `test_init_no_dpi_param`, but there is no `test_init_no_padding_px_param` test. The spec's task 3.1.1 test list does not enumerate a `padding_px` test either, so this is not a missing-test gap per the spec. However, the implementation `__init__` signature correctly omits `padding_px`. Gap is therefore limited to test coverage only (no spec-mandated test for `padding_px`), which is a minor coverage gap, not a spec non-compliance.

  Re-evaluating: the spec's enumerated test list (lines 64–76) does NOT include a `test_init_no_padding_px_param` test. The implementation correctly removes `padding_px` from `__init__`. There is no spec gap here.

  Corrected finding: **Gap G-01 is closed.** The spec does not require a `padding_px` test, and the implementation correctly omits the parameter. Removing this entry.

*(No valid gaps found after re-evaluation — see note below.)*

---

## Gaps (revised)

None found. All "Files to create", "Files to modify", specified methods, and acceptance criteria are present and consistent with the spec:

- `vision_api.py` has no `asyncio` import, no `async def`, no `await`, no `_LOG_LOCK`, no `Lock`.
- `VisionAPI.__init__` accepts only `api_key`, `model`, `cost_log_path`, `cache`.
- `_poll_batch` uses `time.sleep` for polling.
- `_append_cost_entry` has no locking.
- `_prepare_table` calls `render_table_region`, returns `list[tuple[str, str]]`, uses `try/finally` to close the document.
- `_build_request` produces the correct custom_id format, system cache control, max_tokens=4096, user content ordering.
- `extract_tables_batch` returns one `AgentResponse` per input spec in input order; missing results produce `parse_success=False`; no re-crop logic present.
- `VISION_FIRST_SYSTEM`, `render_table_region`, `AgentResponse`, `build_common_ctx`, `parse_agent_response` are all imported from `vision_extract`.
- Cost logging via `_append_cost_entry` is called in `_poll_batch` for each successful result.
- Test file `tests/test_feature_extraction/test_vision_api.py` was created.
- All 13 specified tests are present. The implementation also adds two additional tests beyond the spec (`test_user_content_text_contains_raw_text`, `test_document_closed_on_render_error`) — these are scope additions, not violations (they strengthen coverage without breaking rules).

---

## Weak Tests

### WT-01

- **Test path**: `tests/test_feature_extraction/test_vision_api.py::TestPrepareTable::test_returns_list_of_pairs`
- **Problem**: `assert isinstance(result, list)` is a bare type check with no content verification of the kind the rules flag as trivially true. The assertion confirms the Python list type but does not verify that the first element of the returned tuple is a valid base64 string (that check is deferred to `test_base64_encoded`). On its own, `assert isinstance(result, list)` adds no useful signal — if `_prepare_table` returned `[(None, "image/png")]`, this assertion would still pass.
- **Quoted evidence**:
  ```python
  assert isinstance(result, list)
  assert len(result) == 1
  assert result[0][1] == "image/png"
  ```
  The `isinstance` check is the weak assertion. The `len` and element checks are substantive, but the bare `isinstance` without checking the first element's contents makes it partly trivial.

---

## Legacy References

None found.

- No `render_table_png` reference in `vision_api.py`.
- No `AsyncAnthropic` reference in `vision_api.py`.
- No `asyncio` import in `vision_api.py`.
- No `_LOG_LOCK` in `vision_api.py`.
- No `concurrency`, `dpi`, or `padding_px` parameters in `__init__`.
- No references to removed pipeline types (`BoundaryPoint`, `CellGrid`, `PipelineConfig`, etc.).
- No feature flags or environment-variable toggles.
- No historical-provenance comments in either file.

---

## Additional Observations (informational, not violations)

1. **Extra tests beyond spec**: `test_user_content_text_contains_raw_text` (not in spec test list for Task 3.2.2) and `test_document_closed_on_render_error` (not in spec test list for Task 3.2.1) are present. These increase coverage and do not violate any rule. They are noted for completeness.

2. **`inspect` import unused in test file**: Line 7 of `test_vision_api.py` imports `inspect` but it is not used anywhere in the file. This is a dead import. It does not violate a spec rule but is a code hygiene issue.

3. **Shared failed-sentinel mutation risk (V-02)**: As noted in Violations, the single `failed` AgentResponse object is appended to the list multiple times by reference. This is a latent correctness issue if callers mutate results, but since `AgentResponse` is a dataclass (likely not deeply mutable in practice), the practical risk is low.
