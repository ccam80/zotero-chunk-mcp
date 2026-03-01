# Review Report: Step 1 — Fix Caption Detection

## Summary

| Item | Value |
|------|-------|
| Tasks reviewed | 3 (Task 1.1, Task 1.2, Task 2.1) |
| Files reviewed | `src/zotero_chunk_rag/feature_extraction/captions.py`, `tests/test_feature_extraction/test_captions.py`, `tests/audit_captions.py` |
| Violations | 6 |
| Gaps | 1 |
| Weak tests | 3 |
| Legacy references | 1 |
| Verdict | **has-violations** |

---

## Violations

### V-1 — Banned word "fallback" in comment (minor)

- **File**: `src/zotero_chunk_rag/feature_extraction/captions.py`, line 295
- **Rule violated**: rules.md — "No fallbacks. No backwards compatibility shims. No safety wrappers." and "No commented-out code. No `# previously this was...` comments." The word "fallback" is explicitly enumerated as a red flag in the reviewer posture.
- **Evidence**:
  ```python
  # Line-by-line scan fallback
  if not matched:
      scanned = _scan_lines_for_caption(block, prefix_re, relaxed_re, label_only_re)
  ```
- **Severity**: minor

The comment describes the line-by-line scan as a "fallback" — a word that signals an architecturally subordinate, compensating path. The word is banned regardless of whether the underlying code is structurally sound.

---

### V-2 — Banned word "Fallback" in comment (minor)

- **File**: `src/zotero_chunk_rag/feature_extraction/captions.py`, line 348
- **Rule violated**: rules.md — same as V-1.
- **Evidence**:
  ```python
  # Fallback: no pages available, cannot determine
  return False
  ```
- **Severity**: minor

---

### V-3 — Docstring uses "falls back" and is factually wrong (major)

- **File**: `src/zotero_chunk_rag/feature_extraction/captions.py`, lines 333–334
- **Rule violated**: rules.md — banned word "fallback" / "falls back". Additionally the docstring describes behaviour that does not exist in the code.
- **Evidence** (docstring):
  ```
  If None, falls back to checking if any references section
  spans could contain this page.
  ```
- **Actual code** (lines 348–349):
  ```python
  # Fallback: no pages available, cannot determine
  return False
  ```
- **Severity**: major

The docstring claims the function "falls back to checking if any references section spans could contain this page" when `pages is None`. The code does nothing of the sort — it simply returns `False`. The docstring is both a rules violation (banned word) and factually incorrect documentation. A caller relying on the documented behaviour would be misled.

---

### V-4 — Hard-coded threshold `5` in `_scan_lines_for_caption` (major)

- **File**: `src/zotero_chunk_rag/feature_extraction/captions.py`, lines 200–203
- **Rule violated**: CLAUDE.md — "No Hard-Coded Thresholds. Every numeric threshold in the extraction pipeline MUST be adaptive — computed from the actual data on the current page or paper."
- **Evidence**:
  ```python
  # Only scan first 5 lines -- captions merged with axis labels are
  # always near block start. Body text references buried deep in a
  # paragraph (line 20+) are not captions.
  max_scan = min(5, len(lines))
  ```
- **Severity**: major

The literal `5` is a hard-coded threshold governing how many lines of a merged block are scanned. The comment attempts to justify the value ("always near block start") — but the project rules explicitly ban this. The justification comment makes the violation worse, not better, because it is proof the agent knowingly chose a fixed number. Whether the limit is reasonable on current data is irrelevant; the rule is unconditional.

---

### V-5 — Trivially-true assertions in `TestCanonicalImports::test_captions_module_exports` (minor)

- **File**: `tests/test_feature_extraction/test_captions.py`, lines 386–388
- **Rule violated**: rules.md — "Test assertions that are trivially true (e.g. `assert result is not None`, `assert isinstance(x, dict)` without checking contents)."
- **Evidence**:
  ```python
  assert _FIG_CAPTION_RE is not None
  assert _FIG_CAPTION_RE_RELAXED is not None
  assert _FIG_LABEL_ONLY_RE is not None
  ```
- **Severity**: minor

Module-level `re.compile(...)` calls never return `None` — they either return a compiled pattern or raise at import time. These assertions are trivially true and would pass even if the regex compiled to a degenerate pattern that matched nothing. They test no behaviour.

---

### V-6 — `assert callable(...)` trivially-true assertions in `TestCanonicalImports::test_captions_module_exports` (minor)

- **File**: `tests/test_feature_extraction/test_captions.py`, lines 378–385
- **Rule violated**: rules.md — trivially-true assertions.
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
- **Severity**: minor

All named objects are module-level `def` statements. `callable()` on a Python function always returns `True`. If any of these imports failed, the `ImportError` would already prevent the test from running — the `callable()` check adds zero detection value. These are import checks dressed as assertions.

---

## Gaps

### G-1 — Comment header `# TestBackwardCompat` contradicts class name and signals legacy thinking

- **Spec requirement**: Step 1 spec establishes a clean, new caption detection path. No backwards-compatibility testing was specified — the spec covers: `test_label_only_table`, `test_label_only_figure`, `test_label_only_with_supplementary_prefix`, `test_label_only_does_not_match_body_text`, `test_label_only_line_scan`, `test_label_only_line_scan_figure`.
- **What was found**: `tests/test_feature_extraction/test_captions.py`, lines 357–362:
  ```python
  # ---------------------------------------------------------------------------
  # TestBackwardCompat
  # ---------------------------------------------------------------------------


  class TestCanonicalImports:
  ```
- **File**: `tests/test_feature_extraction/test_captions.py`, lines 357–362

The section divider comment reads `TestBackwardCompat` while the class is named `TestCanonicalImports`. This is a historical-provenance comment — it describes what the section was (or was intended to be called), not what it is. The rules ban "any comment describing what code replaced, what it used to do, why it changed, or where it came from." A comment naming a class that was renamed is exactly this pattern.

---

## Weak Tests

### W-1 — `TestCanonicalImports::test_captions_module_exports` — all assertions trivially true

- **Test path**: `tests/test_feature_extraction/test_captions.py::TestCanonicalImports::test_captions_module_exports`
- **What is wrong**: All eight `assert callable(...)` and three `assert X is not None` assertions verify properties that are structurally guaranteed by the Python import system — not by the behaviour of the imported symbols. A test that imports 11 names and asserts that functions are callable and compiled regexes are not None provides zero signal about correctness. Any import error would raise before any assertion is reached; conversely, a badly broken implementation would still pass every assertion here.
- **Quoted evidence**:
  ```python
  assert callable(_block_has_label_font_change)
  assert callable(_block_is_bold)
  assert callable(_block_label_on_own_line)
  assert callable(_font_name_is_bold)
  assert callable(is_in_references)
  assert callable(find_all_captions)
  assert callable(_scan_lines_for_caption)
  assert callable(_text_from_line_onward)
  assert _FIG_CAPTION_RE is not None
  assert _FIG_CAPTION_RE_RELAXED is not None
  assert _FIG_LABEL_ONLY_RE is not None
  ```

---

### W-2 — `TestFindAllCaptions::test_label_only_does_not_match_body_text` — assertion does not isolate label-only path

- **Test path**: `tests/test_feature_extraction/test_captions.py::TestFindAllCaptions::test_label_only_does_not_match_body_text`
- **What is wrong**: The spec requires asserting that body text "does NOT match via label-only". The test only asserts `len(captions) == 0`. This passes, but does not verify *which* path rejected the text — the same zero-result outcome would occur if the label-only branch never ran at all, or if both label-only AND relaxed branches incorrectly rejected the text. A genuinely isolated test would mock or inspect which branch was attempted, or at minimum verify via a contrasting case that the relaxed path can still accept a font-changed version of the same text while the label-only path does not.
- **Quoted evidence**:
  ```python
  captions = find_all_captions(page)
  assert len(captions) == 0
  ```

---

### W-3 — `TestFontHelpers` — no test for `_block_is_bold` or `_block_has_label_font_change` behaviour

- **Test path**: `tests/test_feature_extraction/test_captions.py::TestFontHelpers`
- **What is wrong**: The spec for Tasks 1.1 and 1.2 involves the relaxed path's structural confirmation signals (`_block_has_label_font_change`, `_block_is_bold`, `_block_label_on_own_line`). The `TestFontHelpers` class tests only `_font_name_is_bold` (a simple string check). No dedicated unit tests exist for `_block_is_bold` or `_block_has_label_font_change` with constructed block dicts, so those code paths are only exercised indirectly through `test_relaxed_with_font_change`. This is not a hard rule violation (the spec did not explicitly require unit tests for these helpers) but the coverage gap is worth flagging.
- **Quoted evidence** (the class contains only two test methods, both for `_font_name_is_bold`):
  ```python
  class TestFontHelpers:
      def test_bold_detection(self) -> None:
          assert _font_name_is_bold("TimesNewRoman.B")
          ...
      def test_non_bold(self) -> None:
          assert not _font_name_is_bold("TimesNewRoman")
          ...
  ```

---

## Legacy References

### L-1 — `# TestBackwardCompat` comment in test file

- **File**: `tests/test_feature_extraction/test_captions.py`, line 358
- **Quoted evidence**:
  ```python
  # ---------------------------------------------------------------------------
  # TestBackwardCompat
  # ---------------------------------------------------------------------------
  ```

This comment names a class that does not exist in the file. The existing class is `TestCanonicalImports`. The stale comment is either a copy-paste relic from a prior naming of this section or a renamed class whose comment was not updated. Either way it is a historical-provenance reference — it describes what a code element was called, not what it is — and is banned by rules.md.

---

## Spec Adherence Check

### Task 1.1 — Add label-only match in `find_all_captions()`

| Requirement | Status |
|-------------|--------|
| `elif label_only_re and label_only_re.match(check_text): matched = True` inserted between prefix_re and relaxed_re branches | PASS — lines 285–286 |
| No structural confirmation required for label-only | PASS |
| `test_label_only_table` exists and asserts `caption_type="table"`, `number="1"`, `text="Table 1"` | PASS |
| `test_label_only_figure` exists and asserts `caption_type="figure"`, `number="3"` | PASS |
| `test_label_only_with_supplementary_prefix` exists and asserts `number="S2"` | PASS |
| `test_label_only_does_not_match_body_text` exists | PASS (with weakness noted in W-2) |

### Task 1.2 — Add label-only match in `_scan_lines_for_caption()`

| Requirement | Status |
|-------------|--------|
| `if label_only_re and label_only_re.match(check_line): return _text_from_line_onward(...)` inserted between prefix_re and relaxed_re checks | PASS — lines 216–217 |
| `test_label_only_line_scan` exists and asserts `caption_type="table"`, `number="2"`, text contains both "Table 2" and "Patient demographics" | PASS |
| `test_label_only_line_scan_figure` exists and asserts `caption_type="figure"`, `number="5"`, text contains "Figure 5" | PASS |

### Task 2.1 — Caption audit script

| Requirement | Status |
|-------------|--------|
| `tests/audit_captions.py` created | PASS |
| 20 CORPUS_KEYS match spec exactly | PASS |
| Instantiates `ZoteroClient` from `Config` | PASS |
| Uses `get_item(key)` → `pymupdf.open()` | PASS |
| Calls `find_all_captions(page)` per page | PASS |
| Tracks table count, figure count, label-only count | PASS |
| Tracks label-only using `_TABLE_LABEL_ONLY_RE` and `_FIG_LABEL_ONLY_RE` | PASS |
| Prints summary table | PASS |
| Prints per-caption detail for label-only captions | PASS |
| Exits with code 0 | PASS (`sys.exit(0)`) |
| No external API calls | PASS |
| No pytest assertions | PASS |

### Step-level acceptance criteria

| Criterion | Status |
|-----------|--------|
| `find_all_captions()` detects standalone "Table N" and "Figure N" blocks | PASS |
| `_scan_lines_for_caption()` detects "Table N"/"Figure N" lines within multi-line blocks | PASS |
| Caption audit script created at `tests/audit_captions.py` | PASS |
| No code changes outside `captions.py` and test files | PASS |
