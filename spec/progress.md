# Implementation Progress

## Phase 0: Demolition
**Status**: not_started

### Previous attempt (2026-03-01) — INCOMPLETE

A prior execution session completed most waves but missed 6 file deletions
and reported completion incorrectly. The entire phase must be re-executed
from scratch. Deletions are idempotent — already-deleted files will simply
not be found.

**Files missed in prior attempt**:

| File | Wave | Status |
|------|------|--------|
| `src/zotero_chunk_rag/feature_extraction/render.py` | 1.7 | NOT DELETED |
| `src/zotero_chunk_rag/feature_extraction/models.py` | 1.7 | NOT DELETED |
| `tests/test_feature_extraction/test_render.py` | 1.8 | NOT DELETED |
| `tests/test_feature_extraction/test_llm_structure.py` | 1.8 | NOT DELETED |
| `tests/test_feature_extraction/test_agent_qa.py` | 1.8 | NOT DELETED |
| `tests/test_feature_extraction/test_cell_methods.py` | 1.8 | NOT DELETED |

**What was completed** (will be no-ops on re-execution):
- Wave 1: 42 of 48 file deletions
- Wave 2: Pipeline types removed from models.py (BoundaryPoint, etc.)
- Wave 3.1: vision_extract.py stripped (SHARED_SYSTEM, consensus, multi-agent)
- Wave 3.2: vision_api.py stripped (4-agent orchestration, async entry points)
- Wave 4: pdf_processor.py gutted (pipeline integration, prose tables, regex consolidation, figure extraction refactored)
- Wave 5: indexer.py cleaned (enhance_tables_with_vision deleted)
- Wave 6: __init__ files cleaned, stress test imports fixed (partial — 20 test files deleted, but missed 4 above)

---

## Step 1: Fix Caption Detection
**Status**: not_started

## Step 2: Vision Extraction Module
**Status**: not_started

## Step 3: API Layer
**Status**: not_started

## Step 4: Integration
**Status**: not_started

## Step 5: Evaluation
**Status**: not_started (user-initiated, no formal spec)
