# Review Report: Batch 1 (S1W1, S2W2.1, S4W4.1, S4W4.2)

## Summary

| Item | Value |
|------|-------|
| Tasks reviewed | 8 (1.1, 1.2, 2.1.1, 2.1.2, 2.1.3, 2.1.4, 4.1.1, 4.1.2, 4.2.1, 4.2.2) |
| Violations | 6 |
| Gaps | 9 |
| Weak tests | 5 |
| Legacy references | 1 |
| Verdict | **has-violations** |

---

## Violations

### V1 — CRITICAL: `render_table_png` call not removed from `vision_api.py`

- **File**: `src/zotero_chunk_rag/feature_extraction/vision_api.py`, line 268
- **Rule violated**: Task 2.1.4 spec: "remove `render_table_png` from the import list (line 28)"; Code Hygiene rule: "All replaced or edited code is removed entirely. Scorched earth."
- **Evidence**:
  ```python
  png_bytes, media_type = render_table_png(
      spec.pdf_path, spec.page_num, spec.bbox,
      dpi=self._dpi, padding_px=self._padding_px,
  )
  ```
- **Severity**: critical

`render_table_png` is called in `_prepare_table()` at line 268. The function was deleted from `vision_extract.py` (Task 2.1.4 did delete it from that module), but `vision_api.py` still calls it by name. The import block at lines 23–27 does not import `render_table_png` (so no import error on load), but `_prepare_table()` references the name as a bare identifier with no import, meaning any call to `_prepare_table()` will raise a `NameError`. Task 2.1.4 required removing `render_table_png` from the import in `vision_api.py`; it also silently required that any *call sites* be updated. The call at line 268 is a live bug.

---

### V2 — MAJOR: `vision_api.py` — `_prepare_table()` method left in a broken state

- **File**: `src/zotero_chunk_rag/feature_extraction/vision_api.py`, lines 264–273
- **Rule violated**: Completeness rule: "Never mark work as deferred, TODO, or 'not implemented.'" / Code hygiene: no partial stubs. Step 2 spec explicitly states: "The `_prepare_table()` method in `vision_api.py` will be rewritten in Step 3; it references the deleted function but is never called in the current stubbed state." This justification comment appears only in the spec, not in code — the agent left a broken call site without any marker but also without fixing it, relying on an unstated assumption that it "will never be called."
- **Evidence**:
  ```python
  def _prepare_table(
      self, spec: TableVisionSpec,
  ) -> tuple[str, str, tuple]:
      """Render PNG for a table spec. Returns (image_b64, media_type, bbox)."""
      png_bytes, media_type = render_table_png(
          spec.pdf_path, spec.page_num, spec.bbox,
          dpi=self._dpi, padding_px=self._padding_px,
      )
      image_b64 = base64.b64encode(png_bytes).decode("ascii")
      return image_b64, media_type, spec.bbox
  ```
  The method body references `render_table_png` which is neither imported nor defined in this module scope. Any call to this method at runtime will raise `NameError: name 'render_table_png' is not defined`.
- **Severity**: major

The spec notes this method "will be rewritten in Step 3" and is "never called in the current stubbed state." However, the implementation rules prohibit stubs with broken runtime behaviour. A `NameError` in production code is not an acceptable deferred state regardless of the stated future plan.

---

### V3 — MAJOR: Wave 2.2 tasks entirely absent — `VISION_FIRST_SYSTEM` constant not implemented

- **File**: `src/zotero_chunk_rag/feature_extraction/vision_extract.py` — entire file
- **Rule violated**: Completeness rule: "Never mark work as deferred, TODO, or 'not implemented.'"
- **Evidence**: The wave completion report states Tasks 2.2.2 and 2.2.3 were done ("Also did 2.2.2 (AgentResponse update) and 2.2.3 (parse_agent_response update)"), but Task 2.2.1 (`VISION_FIRST_SYSTEM` prompt constant) and Task 2.2.4 (update `EXTRACTION_EXAMPLES` with `caption` field) are not listed. Searching the full `vision_extract.py` file confirms neither `VISION_FIRST_SYSTEM` nor any reference to it exists in the file. The wave completion report does not mention these tasks.
- **Severity**: major

Tasks 2.2.1 and 2.2.4 are spec requirements for Wave 2.1 as reported (the orchestrator assigned them to this wave per the assignment). `VISION_FIRST_SYSTEM` is the single-agent system prompt that replaces the multi-agent `SHARED_SYSTEM`; its absence means the vision API layer has no system prompt at all for single-agent extraction.

---

### V4 — MAJOR: `EXTRACTION_EXAMPLES` lacks `caption` field in all six examples

- **File**: `src/zotero_chunk_rag/feature_extraction/vision_extract.py`, lines 44–261
- **Rule violated**: Task 2.2.4 spec: "Add the `caption` field to each worked example's output JSON."
- **Evidence**: Examining `EXTRACTION_EXAMPLES` in full: Example A output JSON contains `"table_label"`, `"is_incomplete"`, `"incomplete_reason"`, `"headers"`, `"rows"`, `"footnotes"` — no `"caption"` key. Same for Examples B, C, D, E, F. Zero examples contain a `"caption"` field.

  Example A as present in the file:
  ```json
  {
    "table_label": "Table 2",
    "is_incomplete": false,
    "incomplete_reason": "",
    "headers": ["Treatment", "N", "Mean", "SD", "p"],
    ...
    "footnotes": "* p-values from two-sided t-test vs. Drug A"
  }
  ```
  The `"caption"` key is absent in all six examples.
- **Severity**: major

---

### V5 — MINOR: Historical-provenance comment in `cell_cleaning.py` docstring

- **File**: `src/zotero_chunk_rag/feature_extraction/postprocessors/cell_cleaning.py`, lines 165–171
- **Rule violated**: Code Hygiene: "No historical-provenance comments. Any comment describing what code replaced, what it used to do, why it changed, or where it came from is banned."
- **Evidence**:
  ```python
  Does NOT apply control character mapping (_map_control_chars) —
  that function requires font metadata from the PDF text layer,
  which is unavailable for vision-extracted tables.
  ```
  The phrase "that function requires font metadata from the PDF text layer, which is unavailable for vision-extracted tables" is a historical-provenance explanation describing *why* a design decision was made in relation to what the previous architecture required. It describes the architectural context that led to the current design, which is exactly what the ban covers. The legitimate content ("Does NOT apply control character mapping") is sufficient; the clause explaining why ("that function requires… unavailable for vision-extracted tables") is the violation.
- **Severity**: minor

---

### V6 — MINOR: `_scan_lines_for_caption` comment uses "fallback" language

- **File**: `src/zotero_chunk_rag/feature_extraction/captions.py`, line 295
- **Rule violated**: Code Hygiene: "No historical-provenance comments" / red-flag word "fallback"
- **Evidence**:
  ```python
  # Line-by-line scan fallback
  if not matched:
      scanned = _scan_lines_for_caption(block, prefix_re, relaxed_re, label_only_re)
  ```
  The comment names the code a "fallback" — a banned term per the reviewer posture. The comment describes the scan as a secondary/backup mechanism, which is a structural description of the old/new behaviour relationship.
- **Severity**: minor

---

## Gaps

### G1 — Task 2.2.1 `VISION_FIRST_SYSTEM` constant entirely absent

- **Spec requirement**: Task 2.2.1: Add `VISION_FIRST_SYSTEM` constant to `vision_extract.py`. Must be a static string of at least 8,000 characters containing all 7 sections and worked examples with no multi-agent references.
- **What was found**: No `VISION_FIRST_SYSTEM` symbol exists anywhere in `vision_extract.py`. Grep confirms zero occurrences.
- **File**: `src/zotero_chunk_rag/feature_extraction/vision_extract.py`

---

### G2 — Task 2.2.4 `caption` field missing from all six `EXTRACTION_EXAMPLES` examples

- **Spec requirement**: Task 2.2.4: Insert `"caption"` after `"table_label"` in each of the six example JSON blocks in `EXTRACTION_EXAMPLES`.
- **What was found**: All six examples (A through F) in `EXTRACTION_EXAMPLES` lack the `"caption"` key entirely.
- **File**: `src/zotero_chunk_rag/feature_extraction/vision_extract.py`, lines 44–261

---

### G3 — Tests for Task 2.2.1 (`TestVisionFirstSystem`) entirely absent

- **Spec requirement**: `test_vision_extract.py` must contain `TestVisionFirstSystem` with four methods: `test_prompt_is_string`, `test_contains_key_sections`, `test_no_multi_agent_references`, `test_minimum_length`.
- **What was found**: None of these test classes or methods exist in `test_vision_extract.py`. The file contains only `TestComputeAllCrops`, `TestRenderTableRegion`, `TestSplitIntoStrips`, `TestComputeRecropBbox`, and `TestDeletedRenderTablePng`.
- **File**: `tests/test_feature_extraction/test_vision_extract.py`

---

### G4 — Tests for Task 2.2.2 (`TestAgentResponse::test_new_fields_exist`) entirely absent

- **Spec requirement**: `test_vision_extract.py::TestAgentResponse::test_new_fields_exist` — construct an `AgentResponse` with all fields including new ones; assert `caption`, `recrop_needed`, `recrop_bbox_pct` values.
- **What was found**: No `TestAgentResponse` class exists in `test_vision_extract.py`.
- **File**: `tests/test_feature_extraction/test_vision_extract.py`

---

### G5 — Tests for Task 2.2.3 (`TestParseAgentResponse`) entirely absent

- **Spec requirement**: `test_vision_extract.py` must contain `TestParseAgentResponse` with six methods: `test_full_new_schema`, `test_recrop_needed`, `test_missing_new_fields`, `test_parse_failure`, `test_corrections_field_ignored`, `test_invalid_recrop_bbox`.
- **What was found**: No `TestParseAgentResponse` class exists in `test_vision_extract.py`.
- **File**: `tests/test_feature_extraction/test_vision_extract.py`

---

### G6 — Tests for Task 2.2.4 (`TestExtractionExamples::test_all_examples_have_caption`) absent

- **Spec requirement**: `test_vision_extract.py::TestExtractionExamples::test_all_examples_have_caption` — parse each JSON block in `EXTRACTION_EXAMPLES`; assert every example output contains a `"caption"` key.
- **What was found**: No `TestExtractionExamples` class exists in `test_vision_extract.py`.
- **File**: `tests/test_feature_extraction/test_vision_extract.py`

---

### G7 — `vision_api.py` import of `render_table_png` not removed (Task 2.1.4 incomplete)

- **Spec requirement**: Task 2.1.4: "remove `render_table_png` from the import list (line 28)" in `vision_api.py`.
- **What was found**: The import block at lines 23–27 does NOT import `render_table_png` by name (which may be why no `ImportError` occurs on module load), but the *call site* at line 268 (`render_table_png(...)`) still references the deleted symbol as a bare name. Task 2.1.4 was interpreted as only removing the import name, not removing the call. The function call was left in place with no import, creating a dormant `NameError`. The spec's intent ("fix imports") extends to removing the dead call site.
- **File**: `src/zotero_chunk_rag/feature_extraction/vision_api.py`, line 268

---

### G8 — `test_captions.py::TestBackwardCompat` class renamed to `TestCanonicalImports` — scope creep

- **Spec requirement**: No spec requirement to add a `TestCanonicalImports` class testing module exports. This class is not mentioned in any task specification.
- **What was found**: A class `TestCanonicalImports` (lines 362–388) was added to `test_captions.py`. It tests that internal symbols (`_scan_lines_for_caption`, `_text_from_line_onward`, `_FIG_CAPTION_RE`, etc.) are importable. While not harmful, it is out-of-spec addition that was not requested. It also includes three trivially-true assertions (see Weak Tests W3, W4, W5).
- **File**: `tests/test_feature_extraction/test_captions.py`, lines 362–388

---

### G9 — `vision_extract.py` missing `VISION_FIRST_SYSTEM` also means the system prompt cannot be cached (Haiku 4.5 requires 2,048 token minimum)

- **Spec requirement**: Task 2.2.1 acceptance criterion: "Static string constant (not dynamically built per-table)" and "Minimum token target: at least 2,048 tokens".
- **What was found**: Not implemented at all. No caching is possible without the prompt constant. The entire cache architecture described in the spec (dual-breakpoint caching, BP1 = system prompt) is non-functional.
- **File**: `src/zotero_chunk_rag/feature_extraction/vision_extract.py`

---

## Weak Tests

### W1 — `test_vision_extract.py::TestSplitIntoStrips::test_strip_overlap` — loose tolerance

- **Test path**: `tests/test_feature_extraction/test_vision_extract.py::TestSplitIntoStrips::test_strip_overlap`
- **Problem**: The assertion `assert abs(overlap - expected_overlap) < 1.0` uses a tolerance of 1.0 PDF point, which is ~1/72 inch. For a strip height of 595pt and overlap_frac of 0.15, the expected overlap is 89.25pt. Allowing ±1.0pt tolerance (a 1.1% relative error) is loose, but not egregiously so. However, the rules state "exact values" — the overlap should be deterministic given fixed inputs: `strip_height_pt * 0.15 = 595 * 0.15 = 89.25`. The assertion should use `== 89.25` or a float tolerance of `< 1e-6`, not `< 1.0`.
- **Evidence**:
  ```python
  assert abs(overlap - expected_overlap) < 1.0
  ```

---

### W2 — `test_debug_db.py::TestWrite::test_write_ground_truth_diff` — `assert row is not None` before accessing row content

- **Test path**: `tests/test_feature_extraction/test_debug_db.py::TestWrite::test_write_ground_truth_diff`
- **Problem**: Line 166 asserts `assert row is not None`. This is a weak assertion — if the insert succeeded but `fetchone()` returned `None` (which would only happen if the insert somehow failed silently), the subsequent `row[0]` access would raise an `IndexError` anyway. The `is not None` assertion adds no useful information and is the pattern explicitly called out in the reviewer posture.
- **Evidence**:
  ```python
  assert row is not None
  assert row[0] == "paper2_table_3"
  ```

---

### W3 — `test_captions.py::TestCanonicalImports::test_captions_module_exports` — trivially-true `is not None` assertions on regex constants

- **Test path**: `tests/test_feature_extraction/test_captions.py::TestCanonicalImports::test_captions_module_exports`
- **Problem**: Lines 386–388 assert `_FIG_CAPTION_RE is not None`, `_FIG_CAPTION_RE_RELAXED is not None`, `_FIG_LABEL_ONLY_RE is not None`. These are module-level compiled `re.Pattern` objects. They can only be `None` if explicitly assigned as `None`. An `ImportError` would occur before these lines if the import failed. These assertions are trivially true and test nothing meaningful.
- **Evidence**:
  ```python
  assert _FIG_CAPTION_RE is not None
  assert _FIG_CAPTION_RE_RELAXED is not None
  assert _FIG_LABEL_ONLY_RE is not None
  ```

---

### W4 — `test_captions.py::TestCanonicalImports::test_captions_module_exports` — `assert callable(...)` on functions without testing behaviour

- **Test path**: `tests/test_feature_extraction/test_captions.py::TestCanonicalImports::test_captions_module_exports`
- **Problem**: Lines 378–385 use eight `assert callable(...)` assertions. These verify that the named symbols are callable (i.e., they are functions), but do not verify any behaviour. If a function were replaced with a broken stub that still had a `__call__` method, all eight assertions would still pass. These assertions test implementation structure, not desired behaviour.
- **Evidence**:
  ```python
  assert callable(_block_has_label_font_change)
  assert callable(_block_is_bold)
  assert callable(_block_label_on_own_line)
  assert callable(_font_name_is_bold)
  assert callable(is_in_references)
  assert callable(find_all_captions)
  assert callable(_scan_lines_for_caption)
  assert callable(_text_from_line_onward)
  ```

---

### W5 — `test_debug_db.py::TestVisionRunDetails::test_write_and_read` — `assert row is not None` before row field access

- **Test path**: `tests/test_feature_extraction/test_debug_db.py::TestVisionRunDetails::test_write_and_read`
- **Problem**: Line 243 asserts `assert row is not None`. Same pattern as W2: the subsequent `row[0]`, `row[1]`, etc. accesses would raise `TypeError` if `row` were `None`, making the `is not None` check redundant and not a meaningful assertion.
- **Evidence**:
  ```python
  assert row is not None
  assert row[0] == "paper1_table_1"
  assert row[1] == "Table 1"
  ```

---

## Legacy References

### L1 — `vision_api.py` calls deleted `render_table_png` by bare name

- **File**: `src/zotero_chunk_rag/feature_extraction/vision_api.py`, line 268
- **Evidence**:
  ```python
  png_bytes, media_type = render_table_png(
      spec.pdf_path, spec.page_num, spec.bbox,
      dpi=self._dpi, padding_px=self._padding_px,
  )
  ```
  `render_table_png` was deleted from `vision_extract.py` as part of Task 2.1.4. The call at line 268 in `vision_api.py` is a stale reference to the deleted function. It is not imported and does not exist anywhere in the codebase. This is an exact match for the legacy reference pattern: a reference to a symbol that was removed.

---

## Notes on Scope

The wave completion report for S2W2.1 states: "Also did 2.2.2 (AgentResponse update) and 2.2.3 (parse_agent_response update)." Tasks 2.2.2 and 2.2.3 were indeed implemented in `vision_extract.py` — `AgentResponse` has the three new fields (`caption`, `recrop_needed`, `recrop_bbox_pct`) and `parse_agent_response()` correctly parses them with safe defaults. These implementations are correct. However, the orchestrator reported the wave scope as including only Tasks 2.1.1–2.1.4, and the test file covers only those tasks. Tasks 2.2.2 and 2.2.3 were implemented without their corresponding tests (`TestAgentResponse::test_new_fields_exist` and `TestParseAgentResponse` with six methods). Tasks 2.2.1 and 2.2.4 were not implemented at all.
