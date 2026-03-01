# Review Report: Step 2 — Vision Extraction Module

## Summary

| Item | Count |
|------|-------|
| Tasks reviewed | 8 (2.1.1, 2.1.2, 2.1.3, 2.1.4, 2.2.1, 2.2.2, 2.2.3, 2.2.4) |
| Violations — critical | 1 |
| Violations — major | 1 |
| Violations — minor | 1 |
| Gaps | 1 |
| Weak tests | 3 |
| Legacy references | 0 |

**Verdict**: has-violations

---

## Violations

### Violation 1 — Critical

**File**: `src/zotero_chunk_rag/feature_extraction/vision_extract.py`, line 498

**Rule violated**: `rules.md` — "No fallbacks. No backwards compatibility shims. No safety wrappers."

**Evidence**:
```python
    # Fallback: find first { ... } block via regex (handles leading/trailing noise)
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            result = json.loads(match.group(0))
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass
```

The `_parse_agent_json` function has two code paths: a direct `json.loads` attempt (lines 491–496) and then a second regex-based extraction path explicitly named "Fallback" in the comment. This is a safety wrapper around parse failures — exactly what the rules forbid. The comment does not merely explain complicated code; it announces that a fallback code path exists, which is a banned construct. The rules require no fallbacks, no safety wrappers. If `json.loads` fails, the function should return `None`. The fallback block at lines 498–507 must be deleted.

**Severity**: critical

---

### Violation 2 — Major

**File**: `tests/test_feature_extraction/test_vision_extract.py`, line 407

**Rule violated**: `spec/step-2-vision-extract.md` Task 2.2.4 acceptance criteria — "All 6 examples include the `caption` field" and the test spec: "Parse each JSON block in `EXTRACTION_EXAMPLES`. Assert: every example output contains a `"caption"` key."

**Evidence**:
```python
        assert len(parsed_blocks) >= 5, (
            f"Expected at least 5 parseable example JSON blocks, got {len(parsed_blocks)}"
        )
        for obj in parsed_blocks:
            assert "caption" in obj, f"Example JSON missing 'caption' field: {obj}"
```

The spec explicitly states there are 6 worked examples (A through F) and the acceptance criterion is that **all 6** include the `caption` field. The test asserts `>= 5`, which passes if only 5 of the 6 examples are parseable with a `caption` key. This weakens the assertion to allow one example to be silently missing the field. The test must assert `== 6`.

**Severity**: major

---

### Violation 3 — Minor

**File**: `src/zotero_chunk_rag/feature_extraction/vision_extract.py`, line 498 (comment)

**Rule violated**: `rules.md` — "No historical-provenance comments. Any comment describing what code replaced, what it used to do, why it changed, or where it came from is banned." / "Comments exist ONLY to explain complicated code to future developers."

**Evidence**:
```python
    # Fallback: find first { ... } block via regex (handles leading/trailing noise)
```

This comment names the pattern as "Fallback" — a label that describes the role of the code in a two-path strategy, not just the mechanics of the regex. It exists to justify a defensive code path. This is a separate, discrete violation from Violation 1 (which addresses the fallback code itself). The comment is prohibited regardless of whether the fallback code is retained or removed.

**Severity**: minor

---

## Gaps

### Gap 1

**Spec requirement**: Task 2.2.4 — `tests/test_vision_extract.py::TestExtractionExamples::test_all_examples_have_caption` — "Parse each JSON block in `EXTRACTION_EXAMPLES`. Assert: every example output contains a `"caption"` key."

**What was found**: The test at line 407 asserts `len(parsed_blocks) >= 5` rather than `== 6`. The spec states there are 6 examples (A–F). The test does not enforce that all 6 are present and all 6 contain `caption`.

**File**: `tests/test_feature_extraction/test_vision_extract.py`, line 407

---

## Weak Tests

### Weak Test 1

**Test path**: `tests/test_feature_extraction/test_vision_extract.py::TestVisionFirstSystem::test_prompt_is_string`

**What is wrong**: The assertion `assert len(VISION_FIRST_SYSTEM) > 0` is trivially true for any non-empty string. The same test also contains `assert isinstance(VISION_FIRST_SYSTEM, str)`. While `test_minimum_length` provides the meaningful length check (`> 8000`), the `> 0` assertion in `test_prompt_is_string` adds no information — a 1-character string would pass. Bare `isinstance` + `len > 0` together constitute a weak test body for the spec's intended "verify it is a non-empty string" intent, which is rendered meaningless by the `test_minimum_length` test existing separately. The `test_prompt_is_string` method's `len > 0` assertion is trivially satisfied.

**Evidence**:
```python
    def test_prompt_is_string(self):
        assert isinstance(VISION_FIRST_SYSTEM, str)
        assert len(VISION_FIRST_SYSTEM) > 0
```

---

### Weak Test 2

**Test path**: `tests/test_feature_extraction/test_vision_extract.py::TestVisionFirstSystem::test_contains_key_sections`

**What is wrong**: The assertion for "raw text" presence uses a redundant disjunction:
```python
        assert any(phrase in prompt for phrase in ["Raw extracted text", "raw text", "Raw extracted text"])
```
The list contains `"Raw extracted text"` twice (index 0 and index 2). This is not a correctness bug but indicates copy-paste inattention that weakens readability of the test contract. Additionally, the word `"corrections"` is checked in `test_no_multi_agent_references` with `assert "corrections" not in prompt`, but the prompt body section "Caption Verification" contains the word "corrections" as part of "caption correction instructions" is referenced in the spec — however inspecting the actual `_PROMPT_BODY` text reveals the word "corrections" is not present, so this passes legitimately. The duplicate entry in the `any()` list remains a weak test defect.

**Evidence**:
```python
        assert any(phrase in prompt for phrase in ["Raw extracted text", "raw text", "Raw extracted text"])
```

---

### Weak Test 3

**Test path**: `tests/test_feature_extraction/test_vision_extract.py::TestExtractionExamples::test_all_examples_have_caption`

**What is wrong**: `assert len(parsed_blocks) >= 5` — as documented in Gap 1, this allows one of the 6 specified examples to be absent without test failure. This is a weak assertion that does not enforce the spec. It should be `assert len(parsed_blocks) == 6`.

**Evidence**:
```python
        assert len(parsed_blocks) >= 5, (
            f"Expected at least 5 parseable example JSON blocks, got {len(parsed_blocks)}"
        )
```

---

## Legacy References

None found.

---

## Additional Notes

### Spec Adherence: All Tasks — Clean (except where noted)

The following tasks are fully implemented and conform to their spec:

- **Task 2.1.1** (`compute_all_crops`): Function signature matches spec exactly. Logic correctly iterates all captions, uses `caption.bbox[1]` for top, next caption's `bbox[1]` for bottom (any type), full page width, degenerate-crop skip. All 5 specified tests are present and test correct behaviour.

- **Task 2.1.2** (`render_table_region`, `_split_into_strips`): Signatures match spec. Multi-strip logic correctly checks `height_in > width_in AND effective_dpi < strip_dpi_threshold`. Strip construction uses `strip_height_pt = crop_width` (square strips), overlap is `strip_height_pt * overlap_frac`, step advances by `step_pt = strip_height_pt - overlap_pt`. Short-crop guard (`crop_height <= strip_height_pt`) returns unchanged bbox. All 6 specified tests are present and test correct behaviour.

- **Task 2.1.3** (`compute_recrop_bbox`): Signature and logic match spec. Clamping uses local `clamp()` helper. All 3 specified tests are present and verify exact coordinate values.

- **Task 2.1.4** (delete `render_table_png`): `render_table_png` is not present in `vision_extract.py`. The import in `vision_api.py` line 27–33 imports `render_table_region` (not `render_table_png`) — deletion confirmed. Test `TestDeletedRenderTablePng::test_not_importable` is present.

- **Task 2.2.1** (`VISION_FIRST_SYSTEM`): All 7 sections present. Built as `_PROMPT_BODY + "\n\n" + EXTRACTION_EXAMPLES`. No multi-agent references. Character length is well above 8000.

- **Task 2.2.2** (`AgentResponse`): All three new fields (`caption: str`, `recrop_needed: bool`, `recrop_bbox_pct: list[float] | None`) present. Existing fields unchanged.

- **Task 2.2.3** (`parse_agent_response`): `caption` parsed from `parsed.get("caption", "")`. `recrop` dict parsed with `needed` and `bbox_pct` with 4-element numeric list validation. Failure sentinel includes all new fields with safe defaults. `corrections` field not read anywhere in the function. All 6 specified tests are present.

- **Task 2.2.4** (`EXTRACTION_EXAMPLES` caption field): All 6 examples contain the `"caption"` key in their JSON blocks. Values match the spec table. However the test asserts `>= 5` rather than `== 6` (Gap 1 / Violation 2).

### Scope Creep

None found. No functionality was added beyond what the spec requires.

### Hard-Coded Thresholds Assessment

The spec explicitly specifies the DPI values used in `render_table_region`: `dpi_floor=150`, `dpi_cap=300`, `strip_dpi_threshold=200`. These are function-signature **parameters with defaults**, not bare if-condition thresholds — callers can override them. The Anthropic API resize constant `1568` is a documented API property, not an arbitrary threshold. The `overlap_frac=0.15` in `_split_into_strips` is a parameter default. None of these constitute a CLAUDE.md "no hard-coded thresholds" violation in the extraction pipeline sense (these are rendering parameters, not extraction analysis thresholds). No violation raised.
