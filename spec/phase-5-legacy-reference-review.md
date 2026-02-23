# Phase 5: Legacy Reference Review

## Overview

Audit the entire repository for any remaining references to removed code, old
algorithm descriptions, or stale documentation. No legacy references are
acceptable in any form.

**Depends on**: Phase 4

**Entry state**: Pipeline passes all targets. Code is correct but may have stale references.
**Exit state**: Clean repository with no references to removed functions, old algorithms,
or superseded spec files.

---

## Wave 5.1: Full legacy audit

### Task 5.1.1: Search and remove all stale references

- **Description**: Search the entire repository for references to removed or
  changed code. Fix or remove every match.

  **Search targets** (grep repo-wide for each):
  - `_select_best_column_group` — removed function
  - `_group_confidence` — removed function
  - `"else 100.0"` — old vacuous default (now `else 0.0`)
  - `"column count grouping"` or `"column-count grouping"` — old algorithm description
  - `"column-count-based"` — old algorithm description
  - `"Q1 percentile"` or `"25th percentile"` in combination context — old acceptance logic
  - `normalize_method_confidence` — removed toggle (never implemented)
  - `reevaluate_accuracy` — removed script (never created)
  - `extract_with_all_boundaries` — removed method (already checked, but verify)

  **Files to check specifically**:
  - `CLAUDE.md` — update architecture notes if they reference old combination algorithm
  - `MEMORY.md` — update if references old algorithm
  - `spec/plan.md` — update dependency graph to reflect actual execution order
  - `spec/pipeline_operators_guide.md` — update if references old combination logic
  - All files in `src/zotero_chunk_rag/feature_extraction/` — check docstrings, comments
  - All files in `tests/` — check test comments, docstrings

  Also verify:
  - No dead imports in `combination.py` (all imports are used)
  - No dead imports in `ground_truth.py`
  - No references to `table_extraction` package (old name, already checked by
    existing test but verify no new references crept in)

- **Files to modify**: Any file containing stale references (determined by search)

- **Tests**:
  - `tests/test_feature_extraction/test_integration.py::TestDocs::test_claude_md_no_table_extraction_refs` —
    existing test, should still pass
  - `tests/test_feature_extraction/test_integration.py::TestDocs::test_claude_md_no_figure_extraction_ref` —
    existing test, should still pass
  - Manual verification: `grep -r "_select_best_column_group\|_group_confidence" src/ tests/` returns 0 matches
  - Manual verification: `grep -r "else 100.0" src/zotero_chunk_rag/feature_extraction/ground_truth.py` returns 0 matches

- **Acceptance criteria**:
  - `grep -r "_select_best_column_group" .` returns 0 matches repo-wide
  - `grep -r "_group_confidence" .` returns 0 matches repo-wide
  - `grep -r "column.count.group" src/ tests/` returns 0 matches (case-insensitive)
  - `grep -r "normalize_method_confidence" .` returns 0 matches repo-wide
  - `CLAUDE.md` accurately describes the current combination algorithm (per-divider voting)
  - `MEMORY.md` accurately describes the current architecture
  - No dead imports in any modified source file
  - All existing tests pass
