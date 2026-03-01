# Implementation Progress

## Phase 0: Demolition
**Status**: in_progress
**Started**: 2026-03-01

## Task P0-W1: Delete files (Wave 1)
- **Status**: complete
- **Agent**: implementer

### Wave 1: Delete files
- **Status**: complete
- **Files deleted**: 24
- **Files not found**: none

### Wave 2: Delete pipeline-only types from models.py
- **Status**: complete
- **Types deleted**: BoundaryPoint, BoundaryHypothesis, TableContext, ExtractionResult, PipelineConfig, PageFeatures, FeatureType, DetectedFeature (FeatureType/DetectedFeature deleted as they exist solely to support PageFeatures)
- **Types kept**: CellGrid

### Wave 3.2: Strip vision_api.py
- **Status**: complete
- **Deleted**: `extract_tables()`, `extract_tables_sync()`, `_async_extract()`, `_run_pipeline()`, `_call_agent()`, `_batch_extract()`, `_submit_batch_stage()`, `_submit_verifier_batch()`, `_submit_synthesizer_batch()`, `_build_batch_request()`, `_retry_incomplete_transcriptions()`, `_needs_retry()`; imports of `SHARED_SYSTEM`, `_ROLE_PREAMBLES`, `ConsensusResult`, `VisionExtractionResult`, `_MAX_TOKENS`, `build_verifier_inputs`, `build_synthesizer_user_text`, `compute_agreement_rate`, `detect_garbled_encoding`, `build_transcriber_cache_block`
- **Kept**: `TableVisionSpec`, `CostEntry`, `_PRICING`, `_compute_cost()`, `_LOG_LOCK`, `_append_cost_entry()`, `VisionAPI.__init__()`, `session_cost`, `_create_batch()`, `_poll_batch()`, `_submit_and_poll()`, `_prepare_table()`; imports of `AgentResponse`, `parse_agent_response`, `build_common_ctx`, `render_table_png`

## Task P0-W3-T1: Strip vision_extract.py
- **Status**: complete
- **Agent**: implementer
- **Files modified**: src/zotero_chunk_rag/feature_extraction/vision_extract.py

### Wave 3.1: Strip vision_extract.py
- **Status**: complete
- **Deleted**: SHARED_SYSTEM, _ROLE_PREAMBLES, _MAX_TOKENS, ConsensusResult, VisionExtractionResult, build_transcriber_cache_block, build_verifier_inputs, build_synthesizer_user_text, compute_agreement_rate, build_consensus, vision_result_to_cell_grid, _structural_consensus, _align_agent_to_shape, _cell_level_vote, _merge_footnotes, _vote_table_label, _vote_incomplete, _extract_word_positions, _cluster_words_by_y, _find_cliff_in_gaps, _format_y_evidence, _format_x_evidence, _compute_x_boundaries, _detect_inline_headers
- **Kept**: AgentResponse, parse_agent_response, build_common_ctx, render_table_png, detect_garbled_encoding, EXTRACTION_EXAMPLES (worked examples A-F extracted from SHARED_SYSTEM into standalone constant)
- **Tests**: verification import check passes ("OK")

## Task P0-W4: Modify pdf_processor.py
- **Status**: complete
- **Agent**: implementer
- **Files modified**: src/zotero_chunk_rag/pdf_processor.py, src/zotero_chunk_rag/feature_extraction/postprocessors/cell_cleaning.py, tests/test_content_quality.py

### Wave 4: Modify pdf_processor.py
- **Status**: complete
- **Changes**:
  - 4.1: Replaced module-level regex definitions (_TABLE_CAPTION_RE, _TABLE_CAPTION_RE_RELAXED, _TABLE_LABEL_ONLY_RE, _FIG_CAPTION_RE_COMP) with imports from feature_extraction/captions.py. _CAPTION_NUM_RE and _NUM_GROUP deleted entirely (only used by deleted prose functions).
  - 4.2: Deleted pipeline integration imports (Pipeline, DEFAULT_CONFIG, run_recovery, adaptive_row_tolerance, CellGrid, TableContext, AbsorbedCaptionStrip).
  - 4.3: Deleted pipeline-dependent functions: _result_to_extracted_table, _adaptive_row_tolerance, _parse_prose_rows, _extract_table_from_words, _apply_prose_postprocessors, _extract_prose_tables, _collect_prose_table_content, _find_column_gap_threshold (only called by _extract_table_from_words). Also removed unused `import math`.
  - 4.4: Replaced pipeline extraction block in extract_document() with stubbed tables=[] and new _extract_figures_for_page() helper. Figure extraction now calls detect_figures/render_figure from figure_detection module directly.
  - Also fixed cell_cleaning.py: removed TableContext import (deleted in Wave 2) and updated CellCleaning.process() signature to accept dict_blocks directly instead of TableContext.
  - Also fixed test_content_quality.py: removed imports and test classes for deleted functions (_parse_prose_rows, _find_column_gap_threshold, _adaptive_row_tolerance).
- **Tests**: 300/316 passing. 16 failures are all EXPECTED: tables=[] stub causes test_table_quality, test_extraction_completeness, test_pdf_processor, test_extraction_integration to fail (all assert table counts > 0 or quality_grade == "A"). Spec explicitly notes these as expected failures.
- **Pre-existing test failures (not from Wave 4)**: 19 test files in tests/test_feature_extraction/ and test_table_extraction_models.py reference deleted modules (Pipeline, BoundaryHypothesis, etc.) — these are Wave 1 leftovers that were never deleted.

## Task P0-W5: Modify indexer.py
- **Status**: complete
- **Agent**: implementer
- **Files modified**: src/zotero_chunk_rag/indexer.py
- **Files created**: none
- **Tests**: import smoke test passing (from zotero_chunk_rag.indexer import Indexer; print('OK'))
- **Deleted**: enhance_tables_with_vision() method and supporting code (lines 429-595 of original); removed `import os` and `ExtractedTable` import which were only used by the deleted method; updated module docstring to remove two-phase extraction description
- **Kept**: index_all(), _index_document_detailed(), index_document(), reindex_document(), get_stats(), get_library_diagnostics(), _load_empty_docs(), _save_empty_docs(), _pdf_hash(), _needs_reindex(), _config_hash(), IndexResult dataclass, all figure storage, reference matching, stats

## Task P0-W6: Clean up __init__ files and remaining imports
- **Status**: complete
- **Agent**: implementer
- **Files modified**:
  - `src/zotero_chunk_rag/feature_extraction/__init__.py` — updated module docstring (removed stale "pipeline/combination" reference)
  - `src/zotero_chunk_rag/feature_extraction/methods/figure_detection.py` — fixed docstring (removed "called by Pipeline.extract_page()")
  - `tests/test_feature_extraction/test_pp_cell_cleaning.py` — removed TableContext/PostProcessor imports (deleted symbols), updated _make_ctx() helper to pass dict_blocks directly, updated all pp.process() calls to match new CellCleaning.process(grid, dict_blocks) signature
  - `tests/stress_test_real_library.py` — removed top-level imports of Pipeline/DEFAULT_CONFIG/FAST_CONFIG/RULED_CONFIG/MINIMAL_CONFIG/_compute_fill_rate; deleted _test_pipeline_methods() function (~350 lines) and its call block; deleted _build_variant_comparison() function (~157 lines) and its call block
- **Files deleted**:
  - `src/zotero_chunk_rag/feature_extraction/protocols.py` — entire file (StructureMethod/CellExtractionMethod/PostProcessor protocols, all pipeline-only)
  - `src/zotero_chunk_rag/feature_extraction/table_features.py` — entire file (TableContext-dependent feature predicates, all pipeline-only)
  - `tests/diag_pipeline_methods.py` — diagnostic script importing deleted Pipeline/TableContext
  - `tests/test_table_extraction_models.py` — all tests for BoundaryPoint/BoundaryHypothesis/ExtractionResult/PipelineConfig/TableContext (deleted types)
  - `tests/test_feature_extraction/test_cell_rawdict.py` — imports deleted cell_rawdict module
  - `tests/test_feature_extraction/test_cell_words.py` — imports deleted cell_words module
  - `tests/test_feature_extraction/test_integration.py` — imports ExtractionResult/TableContext
  - `tests/test_feature_extraction/test_pipeline_configs.py` — imports Pipeline/DEFAULT_CONFIG
  - `tests/test_feature_extraction/test_pipeline_extract_page.py` — imports Pipeline/PageFeatures
  - `tests/test_feature_extraction/test_pp_absorbed_caption.py` — imports deleted absorbed_caption
  - `tests/test_feature_extraction/test_pp_continuation_merge.py` — imports deleted continuation_merge
  - `tests/test_feature_extraction/test_pp_footnote_strip.py` — imports deleted footnote_strip
  - `tests/test_feature_extraction/test_pp_header_data_split.py` — imports deleted header_data_split
  - `tests/test_feature_extraction/test_pp_header_detection.py` — imports deleted header_detection
  - `tests/test_feature_extraction/test_pp_inline_headers.py` — imports deleted inline_headers
  - `tests/test_feature_extraction/test_pymupdf_tables.py` — imports deleted pymupdf_tables
  - `tests/test_feature_extraction/test_row_clustering.py` — imports deleted _row_clustering
  - `tests/test_feature_extraction/test_ruled_lines.py` — imports deleted ruled_lines
  - `tests/test_feature_extraction/test_table_features.py` — imports BoundaryHypothesis/BoundaryPoint
  - `tests/test_feature_extraction/test_vision_consensus.py` — tests deleted 4-agent consensus
  - `tests/test_feature_extraction/test_vision_integration.py` — tests deleted 4-agent vision pipeline
- **Dead references found and fixed**: 0 remaining in src/; 0 remaining in tests/ (all cleaned)
- **Import smoke test**: pass — "All imports clean"
- **Tests**: 160/163 passing in tests/test_feature_extraction/. 3 pre-existing failures in test_ground_truth.py (TestCompare::test_extra_column, test_extra_rows, test_skip_spurious_ext_row) — these assert cell_accuracy_pct==100.0 for extra-column/row cases but the implementation returns fuzzy_precision_pct; test_ground_truth.py was not modified in this session (confirmed via git diff).

### Wave 6: Clean up __init__ files and remaining imports
- **Status**: complete
- **__init__ files cleaned**: feature_extraction/__init__.py (docstring only — no dead imports were present)
- **Test files cleaned/deleted**: 20 deleted, 1 modified (test_pp_cell_cleaning.py)
- **Dead references found and fixed**: 0 remaining after cleanup
- **Import smoke test**: pass
