# Review Report: Phase 0 — Demolition

## Summary

| Item | Count |
|------|-------|
| Tasks reviewed | 6 waves (Wave 1–6) |
| Violations — critical | 0 |
| Violations — major | 2 |
| Violations — minor | 4 |
| Gaps | 2 |
| Weak tests | 0 |
| Legacy references | 3 |

**Verdict**: has-violations

---

## Violations

### V-1 — Major: Historical-provenance comment references deleted module (`_gap_fill`)

**File**: `src/zotero_chunk_rag/pdf_processor.py`, line 422

**Rule**: Rules.md — "No historical-provenance comments. Any comment describing what code replaced, what it used to do, why it changed, or where it came from is banned."

**Evidence**:
```python
    # Remove false-positive figures: after all recovery passes (gap-fill,
    # heading fallback, continuation), figures still without captions are
    # layout engine misclassifications (logos, decorative elements, headers).
```

The comment text `(gap-fill, heading fallback, continuation)` names the `_gap_fill` recovery pass which was deleted in Wave 4 of this very demolition phase. The comment describes historical behaviour (three formerly-present recovery passes) as context for the current filter. The deleted `_gap_fill` module is gone; the comment tells a reader about a pass that no longer exists, which is precisely the historical-provenance pattern the rule bans.

**Severity**: Major

---

### V-2 — Major: Hardcoded numeric threshold `60` used as fallback for `scan_distance`

**File**: `src/zotero_chunk_rag/pdf_processor.py`, line 940

**Rule**: CLAUDE.md — "No Hard-Coded Thresholds. Every numeric threshold in the extraction pipeline MUST be adaptive — computed from the actual data on the current page or paper."

**Evidence**:
```python
            scan_distance = 60  # fallback
```

This is a hard-coded 60pt distance used when no line-height data is available to derive a scan distance adaptively. The comment explicitly labels it `# fallback`, which is itself a red-flag keyword under the rules. The CLAUDE.md rule requires adaptive computation or explicit user approval of any fixed number. No approval is documented here. The scan_distance computation two lines above (line 938) is correctly data-derived; the fallback branch violates the rule.

**Severity**: Major

---

### V-3 — Minor: Hardcoded threshold `0.5` for figure-table overlap ratio

**File**: `src/zotero_chunk_rag/pdf_processor.py`, line 414

**Rule**: CLAUDE.md — "No Hard-Coded Thresholds."

**Evidence**:
```python
                if overlap_ratio > 0.5:
```

The 0.5 overlap threshold for tagging a table as a `figure_data_table` artifact is a fixed constant with no derivation from page or table geometry. No user approval is documented.

**Severity**: Minor

---

### V-4 — Minor: Hardcoded threshold `0.4` in `_is_interleaved_columns`

**File**: `src/zotero_chunk_rag/pdf_processor.py`, line 1093

**Rule**: CLAUDE.md — "No Hard-Coded Thresholds."

**Evidence**:
```python
    if ratio > 0.4:
        return True, f"{ratio:.0%} of tokens are single alpha chars (likely interleaved columns)"
```

The 0.4 ratio for detecting interleaved columns is a fixed constant, not derived from the data or document structure. No user approval is documented.

**Severity**: Minor

---

### V-5 — Minor: Historical-provenance comment in `server.py` references backwards compatibility

**File**: `src/zotero_chunk_rag/server.py`, line 483

**Rule**: Rules.md — "No historical-provenance comments." and "No backwards compatibility shims."

**Evidence**:
```python
            # Raw similarity scores (kept for backwards compatibility)
```

The comment explicitly states the field is kept for "backwards compatibility" — this is a banned phrase that describes a historical relationship to a prior API shape. Phase 0 is not the origin of this comment, but it was not cleaned up during the demolition pass which touched `indexer.py` and `pdf_processor.py`. The Scorched Earth rule ("All replaced or edited code is removed entirely") and the historical-provenance comment ban apply to the entire codebase, not only to directly modified files. Note: this file is outside the formal Phase 0 modification scope, so this is flagged as minor rather than major.

**Severity**: Minor

---

### V-6 — Minor: "Legacy" terminology in `indexer.py` docstring

**File**: `src/zotero_chunk_rag/indexer.py`, line 109

**Rule**: Rules.md — "No historical-provenance comments."

**Evidence**:
```python
            - "no_hash": Document indexed without hash (legacy), needs reindex
```

The word `legacy` inside a docstring describes a historical state ("documents indexed without hash under a previous implementation"). This is a historical-provenance description, which the rules ban even in docstrings. `indexer.py` is a file explicitly modified in Wave 5 of this phase, making this a compliance failure in directly touched code.

**Severity**: Minor

---

## Gaps

### G-1: `_CAPTION_NUM_RE` not imported from `captions.py` as specified

**Spec requirement** (Wave 4.1): Replace the local `_CAPTION_NUM_RE` definition with an import from `feature_extraction/captions.py`. The spec notes that if the patterns differ, the local definition may be kept, but explicitly requires verifying before deciding.

**What was found**: `pdf_processor.py` imports `_TABLE_CAPTION_RE`, `_TABLE_CAPTION_RE_RELAXED`, `_TABLE_LABEL_ONLY_RE`, and `_FIG_CAPTION_RE` from `captions.py` (lines 39–44), but `_CAPTION_NUM_RE` is neither imported nor present anywhere in the current `pdf_processor.py`. The progress note says "Verification: Grep verification across `src/` for all deleted symbols: CLEAN" but does not document whether the `_CAPTION_NUM_RE` consolidation decision was explicitly made and recorded. The symbol is simply absent from the file with no explanation.

**File**: `src/zotero_chunk_rag/pdf_processor.py`

---

### G-2: `_NUM_GROUP` constant not consolidated or explicitly retained

**Spec requirement** (Wave 4.1): The spec notes that `_NUM_GROUP` is "defined identically in both files" and should be consolidated, or the local copy kept if it differs. The spec does not permit silent removal without resolution.

**What was found**: `_NUM_GROUP` does not appear anywhere in `pdf_processor.py`. It exists only in `captions.py` (line 17). There is no import of `_NUM_GROUP` from `captions.py` into `pdf_processor.py`, and there is no documented decision about whether the local definition was identical. The progress note does not mention this symbol at all. Whether the removal is intentional (because `_NUM_GROUP` was no longer needed after pattern consolidation) or accidental is not recorded.

**File**: `src/zotero_chunk_rag/pdf_processor.py`

---

## Weak Tests

None found. Phase 0 is a demolition phase — no new tests were written as part of this phase. The files kept from `test_feature_extraction/` (`test_pp_cell_cleaning.py`, `test_captions.py`, `test_debug_db.py`, etc.) were not reviewed here as they are outside the Phase 0 modification scope.

---

## Legacy References

### L-1: `gap-fill` named in comment referencing deleted module

**File**: `src/zotero_chunk_rag/pdf_processor.py`, line 422

**Evidence**:
```
    # Remove false-positive figures: after all recovery passes (gap-fill,
```

`gap-fill` is a reference to `_gap_fill.py`, which was deleted in Wave 4 of this phase. This is both a legacy reference and a historical-provenance comment violation (also reported as V-1 above).

---

### L-2: `backwards compatibility` phrase in `server.py`

**File**: `src/zotero_chunk_rag/server.py`, line 483

**Evidence**:
```
            # Raw similarity scores (kept for backwards compatibility)
```

The phrase "backwards compatibility" explicitly describes a field being preserved for historical API consumers. This is a legacy reference pattern banned by the rules (also reported as V-5 above).

---

### L-3: `legacy` label in `indexer.py` docstring

**File**: `src/zotero_chunk_rag/indexer.py`, line 109

**Evidence**:
```
            - "no_hash": Document indexed without hash (legacy), needs reindex
```

The word `legacy` inside a docstring describes a prior implementation state. This is a legacy reference (also reported as V-6 above).

---

## Observations (Non-Violation)

The following items were investigated and found **not** to be violations:

- **`extract_tables_batch` in `pdf_processor.py` and `vision_api.py`**: This is the new single-agent batch entry point, distinct from the deleted `extract_tables` and `extract_tables_sync` functions. Not a legacy reference.
- **`fallback` keyword in `captions.py` lines 295, 348**: Used in inline code comments describing algorithm fallback logic (e.g., "Line-by-line scan fallback"), not historical-provenance descriptions.
- **`CONFIDENCE_FALLBACK` constant in `models.py` line 15**: A semantic name for a data value; not a comment describing historical behaviour.
- **`pass` in `vector_store.py` line 71 and `server.py` line 31**: Both occur inside `except` blocks as intentional exception swallowing, which is standard Python. Not production-code stubs.
- **`scan_distance` adaptive derivation (lines 930–938)**: The primary path correctly derives `scan_distance` from `median_spacing` and `median_height`. Only the fallback branch (V-2) is a violation.
- **`overlap_ratio > 0.85` for section heading weight (line 533)**: This is a classification weight threshold in `_sections_from_toc`, not an extraction threshold for table/figure detection. CLAUDE.md's "No Hard-Coded Thresholds" rule applies to the extraction pipeline. Classified as outside scope, but noted.
- **`abs(block_font[1] - body_font_size) > 0.3` (line 822)**: Font size difference threshold in abstract detection. Same scope consideration as above — abstract detection is not extraction pipeline code per the CLAUDE.md examples. Noted but not flagged.
- **All 48 Wave 1 file deletions**: Confirmed. All files from Waves 1.1–1.8 are absent. Spot-checked 39 of 48; git status and file existence checks confirm the deletions.
- **Wave 3 deletions (vision modules stripped)**: Confirmed. `SHARED_SYSTEM`, `_ROLE_PREAMBLES`, `ConsensusResult`, `VisionExtractionResult`, `vision_result_to_cell_grid`, and all multi-agent orchestration functions are gone from `vision_extract.py` and `vision_api.py`. Kept symbols (`AgentResponse`, `parse_agent_response`, `build_common_ctx`, `EXTRACTION_EXAMPLES`, `TableVisionSpec`, `CostEntry`, batch infrastructure) are present.
- **Wave 5 (`indexer.py`)**: `enhance_tables_with_vision` is deleted. No references to deleted symbols found.
- **Wave 6 (`__init__` files)**: `feature_extraction/methods/__init__.py` and `feature_extraction/postprocessors/__init__.py` are empty (1 line). `feature_extraction/__init__.py` exports only `DetectedCaption` and `find_all_captions`. No deleted symbols re-exported.
- **Wave 6 grep verification**: Grep across `src/` for all deleted symbols listed in the spec returns zero matches (excluding the `extract_tables_batch` new method and the `scan_distance = 60` hardcoded threshold).
- **Stress test import crash (Wave 5.1)**: No references to `vision_result_to_cell_grid` or `_test_pipeline_methods` found in `stress_test_real_library.py`. Import crash is resolved.
- **`cell_cleaning.py` CellGrid move**: `CellGrid` does not appear anywhere in `src/`. The progress note says it was "moved locally" to `cell_cleaning.py`, but inspection of the file shows it was removed entirely (not relocated). This is correct behaviour — `CellGrid` is no longer needed in the vision-first architecture.
- **`_CAPTION_NUM_RE` absence from `pdf_processor.py`**: Investigated as Gap G-1. The symbol was not consolidated from `captions.py` and is not locally defined. Whether it is genuinely no longer needed or was accidentally dropped is unclear.
