# Review Report: Phase 0 Waves 2–4

## Summary

| Item | Count |
|------|-------|
| Tasks reviewed | 4 (Wave 2, Wave 3.1, Wave 3.2, Wave 4) |
| Violations — critical | 3 |
| Violations — major | 4 |
| Violations — minor | 1 |
| Gaps | 1 |
| Weak tests | 4 |
| Legacy references | 4 |

**Verdict: has-violations**

---

## Violations

### V-1 — CRITICAL: `protocols.py` imports deleted types `BoundaryHypothesis` and `TableContext`

- **File**: `src/zotero_chunk_rag/feature_extraction/protocols.py`, line 12
- **Rule violated**: "No deleted files imported" (spec acceptance criterion 7); "No dead references" (spec acceptance criterion 6)
- **Evidence**:
  ```python
  from .models import BoundaryHypothesis, CellGrid, TableContext
  ```
  Both `BoundaryHypothesis` and `TableContext` were deleted from `models.py` in Wave 2. The import will raise `ImportError` at module load time. `protocols.py` is not listed in `spec/progress.md` as a file modified in any Wave 2–4 task, meaning this broken import was left untouched.
- **Severity**: critical — causes `ImportError` when any code imports from `feature_extraction.protocols`.

---

### V-2 — CRITICAL: `table_features.py` imports deleted type `TableContext`

- **File**: `src/zotero_chunk_rag/feature_extraction/table_features.py`, line 17
- **Rule violated**: "No deleted files imported" (spec acceptance criterion 7); "No dead references" (spec acceptance criterion 6)
- **Evidence**:
  ```python
  from .models import TableContext
  ```
  `TableContext` was deleted in Wave 2. `table_features.py` is not listed in `spec/progress.md` as modified in any wave. All five functions in this file (`has_ruled_lines`, `is_dense_numeric`, `has_sparse_content`, `is_wide_table`, `has_complex_headers`) accept `ctx: TableContext` parameters. This import raises `ImportError` at module load time.
- **Severity**: critical — causes `ImportError` when any code imports from `feature_extraction.table_features`.

---

### V-3 — CRITICAL: `protocols.py` `PostProcessor.process()` signature references deleted `TableContext`

- **File**: `src/zotero_chunk_rag/feature_extraction/protocols.py`, line 100
- **Rule violated**: "No dead references" (spec acceptance criterion 6)
- **Evidence**:
  ```python
  def process(self, grid: CellGrid, ctx: TableContext) -> CellGrid:
  ```
  This protocol signature declares `ctx: TableContext` as the second argument. `TableContext` was deleted in Wave 2. Meanwhile, `cell_cleaning.py` was correctly updated (Wave 4) to accept `dict_blocks: list[dict]` instead. The protocol and the implementation now have incompatible signatures, and the protocol still references a deleted type. Any runtime `isinstance` check against `PostProcessor` will fail on import due to V-1.
- **Severity**: critical — the protocol is permanently broken relative to the changed implementation.

---

### V-4 — MAJOR: `figure_detection.py` module docstring contains historical-provenance reference to deleted `Pipeline`

- **File**: `src/zotero_chunk_rag/feature_extraction/methods/figure_detection.py`, line 4
- **Rule violated**: "No historical-provenance comments. Any comment describing what code replaced, what it used to do, why it changed, or where it came from is banned." (`spec/.context/rules.md`, Code Hygiene)
- **Evidence**:
  ```python
  """Figure detection — detecting and rendering figures on PDF pages.

  Consumes DetectedCaption objects from captions.py. NOT a StructureMethod
  (figures have no grid structure); called by Pipeline.extract_page().
  """
  ```
  `Pipeline.extract_page()` was deleted. The docstring describes the module's former role within the deleted pipeline. This is a stale historical-provenance reference that was not cleaned up in Wave 4 when the pipeline was removed.
- **Severity**: major

---

### V-5 — MAJOR: `pdf_processor.py` line 261 contains historical-provenance reference to deleted pipeline

- **File**: `src/zotero_chunk_rag/pdf_processor.py`, line 261
- **Rule violated**: "No historical-provenance comments." (`spec/.context/rules.md`, Code Hygiene)
- **Evidence**:
  ```python
  # Cell text is already cleaned by the pipeline's CellCleaning post-processor.
  # Only captions need ligature normalization here.
  ```
  The pipeline was deleted in Wave 4. The comment `"already cleaned by the pipeline's CellCleaning post-processor"` describes a relationship to deleted code. With `tables=[]` (stub), no cell text is cleaned at all. The comment is factually false and historically describes the previous architecture.
- **Severity**: major

---

### V-6 — MAJOR: `feature_extraction/__init__.py` module docstring references deleted pipeline

- **File**: `src/zotero_chunk_rag/feature_extraction/__init__.py`, line 1
- **Rule violated**: "No historical-provenance comments." (`spec/.context/rules.md`, Code Hygiene)
- **Evidence**:
  ```python
  """Table extraction pipeline — composable multi-method extraction with confidence-weighted boundary combination."""
  ```
  The "composable multi-method extraction with confidence-weighted boundary combination" pipeline was deleted entirely in Wave 1. The module docstring was not updated in any of Waves 2–4. The description is a historical account of code that no longer exists.
- **Severity**: major

---

### V-7 — MAJOR: `table_features.py` module docstring references deleted `PipelineConfig` and `TableContext`

- **File**: `src/zotero_chunk_rag/feature_extraction/table_features.py`, lines 3–9
- **Rule violated**: "No historical-provenance comments." (`spec/.context/rules.md`, Code Hygiene); "No dead references" (spec acceptance criterion 6)
- **Evidence**:
  ```python
  """Table feature detection for per-table method activation.

  Feature predicates inspect a TableContext's cached properties to detect
  structural properties of a table region. These predicates are composed
  into activation rules in PipelineConfig.activation_rules to gate which
  extraction methods run on a given table.
  ```
  Both `TableContext` and `PipelineConfig` were deleted. The docstring describes the module's role in the deleted pipeline architecture. String references to deleted symbols `PipelineConfig` and `TableContext` appear in comments/docstrings in violation of acceptance criterion 6 ("No dead references: `grep -r` for all deleted symbols across `src/` returns zero matches (excluding comments)" — but the spec's exclusion of comments does not excuse historical-provenance violations under the rules.md ban).
- **Severity**: major

---

### V-8 — MINOR: `detect_garbled_encoding` retained despite spec calling for deletion if only used by multi-agent prompt construction

- **File**: `src/zotero_chunk_rag/feature_extraction/vision_extract.py`, lines 365–408
- **Rule violated**: Spec Wave 3.1 — "Delete: `detect_garbled_encoding()` — if only used by multi-agent prompt construction"
- **Evidence**:
  Grep of the entire `src/` directory shows `detect_garbled_encoding` appears only in `vision_extract.py` (definition at line 365). No callers exist anywhere in `src/`. The spec required the function to be deleted if it was only used by multi-agent prompt construction. It has no callers. It was retained without justification.

  Progress.md states: "Kept: ... `detect_garbled_encoding`" — but does not verify it has callers outside deleted code.
- **Severity**: minor — dead code; does not cause failures but violates the completeness rule ("All replaced or edited code is removed entirely. Scorched earth.")

---

## Gaps

### G-1: `protocols.py` and `table_features.py` not cleaned up after Wave 2 deleted their core types

- **Spec requirement**: Wave 2 task — "Delete these types (no remaining importers after Wave 1)" — the spec assumes no remaining importers exist. Acceptance criterion 6: "No dead references: `grep -r` for all deleted symbols across `src/` returns zero matches (excluding comments)." Acceptance criterion 7: "No deleted files imported."
- **What was found**: `protocols.py` (line 12) imports `BoundaryHypothesis` and `TableContext`. `table_features.py` (line 17) imports `TableContext`. Neither file appears in `spec/progress.md` as modified in any of Waves 2–4. The progress note for Wave 2 states "Import verified" — but the verification was insufficient, as these two files retain live imports of the deleted types.
- **File**: `src/zotero_chunk_rag/feature_extraction/protocols.py` line 12; `src/zotero_chunk_rag/feature_extraction/table_features.py` line 17

---

## Weak Tests

### WT-1: `tests/test_content_quality.py::TestClassifyArtifact::test_elsevier_article_info_box` — redundant `is not None` assertion before specific assertion

- **Test path**: `tests/test_content_quality.py::TestClassifyArtifact::test_elsevier_article_info_box`
- **What is wrong**: The test asserts `_classify_artifact(table) is not None` on line 244 and then immediately calls `_classify_artifact(table) == "article_info_box"` on line 245. The first assertion is trivially subsumed by the second. The `is not None` check is a weak assertion pattern — it would pass even if the function returned the wrong artifact type.
- **Evidence**:
  ```python
  assert _classify_artifact(table) is not None
  assert _classify_artifact(table) == "article_info_box"
  ```

---

### WT-2: `tests/test_content_quality.py::TestClassifyArtifact::test_elsevier_uppercase_variant` — same redundant `is not None` pattern

- **Test path**: `tests/test_content_quality.py::TestClassifyArtifact::test_elsevier_uppercase_variant`
- **What is wrong**: Same pattern as WT-1. The `is not None` assertion on line 256 is trivially weaker than the equality check on line 257 that follows.
- **Evidence**:
  ```python
  assert _classify_artifact(table) is not None
  assert _classify_artifact(table) == "article_info_box"
  ```

---

### WT-3: `tests/test_content_quality.py::TestClassifyArtifact::test_table_of_contents` — redundant `is not None` assertion

- **Test path**: `tests/test_content_quality.py::TestClassifyArtifact::test_table_of_contents`
- **What is wrong**: `is not None` assertion on line 274 is redundant before the equality check on line 275.
- **Evidence**:
  ```python
  assert _classify_artifact(table) is not None
  assert _classify_artifact(table) == "table_of_contents"
  ```

---

### WT-4: `tests/test_content_quality.py::TestClassifyArtifact::test_real_data_table_not_filtered` and `test_header_with_plain_abstract_not_filtered` — duplicate `is None` assertions

- **Test path**: `tests/test_content_quality.py::TestClassifyArtifact::test_real_data_table_not_filtered`, `tests/test_content_quality.py::TestClassifyArtifact::test_header_with_plain_abstract_not_filtered`
- **What is wrong**: Both tests call `_classify_artifact(table)` twice and assert `is None` twice. The second assertion is an identical duplicate of the first — it adds no coverage and reads as a copy-paste error.
- **Evidence** (test_real_data_table_not_filtered, lines 338–339):
  ```python
  assert _classify_artifact(table) is None
  assert _classify_artifact(table) is None
  ```
  Evidence (test_header_with_plain_abstract_not_filtered, lines 383–384):
  ```python
  assert _classify_artifact(table) is None
  assert _classify_artifact(table) is None
  ```

---

## Legacy References

### LR-1: `protocols.py` line 12 — live import of deleted `BoundaryHypothesis` and `TableContext`

- **File**: `src/zotero_chunk_rag/feature_extraction/protocols.py`, line 12
- **Evidence**:
  ```python
  from .models import BoundaryHypothesis, CellGrid, TableContext
  ```
  `BoundaryHypothesis` and `TableContext` no longer exist in `models.py`. This import will fail at runtime.

---

### LR-2: `table_features.py` line 17 — live import of deleted `TableContext`

- **File**: `src/zotero_chunk_rag/feature_extraction/table_features.py`, line 17
- **Evidence**:
  ```python
  from .models import TableContext
  ```
  `TableContext` no longer exists in `models.py`. This import will fail at runtime.

---

### LR-3: `figure_detection.py` line 4 — string reference to deleted `Pipeline.extract_page()` in module docstring

- **File**: `src/zotero_chunk_rag/feature_extraction/methods/figure_detection.py`, line 4
- **Evidence**:
  ```python
  (figures have no grid structure); called by Pipeline.extract_page().
  ```
  `Pipeline` and its `extract_page()` method were deleted in Wave 1.

---

### LR-4: `pdf_processor.py` line 261 — comment references deleted pipeline's `CellCleaning` post-processor role

- **File**: `src/zotero_chunk_rag/pdf_processor.py`, line 261
- **Evidence**:
  ```python
  # Cell text is already cleaned by the pipeline's CellCleaning post-processor.
  ```
  The pipeline no longer exists. Tables are currently `[]`. The statement describes a mechanism that no longer operates.
