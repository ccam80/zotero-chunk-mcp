# Phase 0: Demolition

## Prior Partial Execution — READ THIS FIRST

A previous implementation session completed ~85% of this spec but missed 6
file deletions and reported completion incorrectly. The codebase is in a
partially-demolished state. Here is what this means for each wave:

| Wave | Prior state | What to do |
|------|-------------|------------|
| **1 (delete files)** | 42 of 48 files already deleted | Delete the 6 remaining files (listed below). Already-deleted files will simply not be found — skip them. |
| **2 (delete types from models.py)** | Pipeline types already removed; only `CellGrid` remains | Delete `models.py` entirely (Wave 1.7 covers this). |
| **3 (gut vision modules)** | Already stripped — `SHARED_SYSTEM`, consensus, multi-agent code deleted | Verify the kept symbols exist and the deleted symbols are gone. No modifications needed if prior work holds. |
| **4 (modify pdf_processor.py)** | Already done — pipeline imports removed, prose functions deleted, `extract_document()` stubbed, figure extraction refactored | Verify current state matches spec. No modifications needed if prior work holds. |
| **5 (modify indexer.py)** | Already done — `enhance_tables_with_vision()` deleted | Verify. No modifications needed. |
| **6 (clean up imports)** | Mostly done — `__init__` files cleaned, most test files deleted | Delete 4 remaining test files (listed below). Run grep verification. |

**Files still needing deletion** (the 6 that were missed):

| File | Wave |
|------|------|
| `src/zotero_chunk_rag/feature_extraction/render.py` | 1.7 |
| `src/zotero_chunk_rag/feature_extraction/models.py` | 1.7 |
| `tests/test_feature_extraction/test_render.py` | 1.8 |
| `tests/test_feature_extraction/test_llm_structure.py` | 1.8 |
| `tests/test_feature_extraction/test_agent_qa.py` | 1.8 |
| `tests/test_feature_extraction/test_cell_methods.py` | 1.8 |

**Recommended approach**: Delete the 6 files, then run the Wave 6 grep
verification (acceptance criterion 1) to confirm no remaining references
to deleted symbols. If it passes, the phase is complete. Only dig into
individual waves if the verification fails.

---

## Goal

Delete the multi-method extraction pipeline, the 4-agent vision pipeline,
all prose table extraction, gap fill recovery, pipeline-only data models,
and all tests for deleted code. Stub `extract_document()` so it still
returns valid `DocumentExtraction` objects (with empty tables) while the
vision-first path is built in subsequent steps.

After this phase, the codebase is in a degraded-but-runnable state: sections,
figures, markdown, and completeness all work. Table extraction returns nothing
until Steps 1–4 restore it via vision.

---

## Wave 1: Delete files

### 1.1 Delete spec

| File | Reason |
|------|--------|
| `spec/vision_first.md` | Superseded by `spec/vision_first_plan.md` |

### 1.2 Delete pipeline methods and infrastructure

| File | Reason |
|------|--------|
| `src/zotero_chunk_rag/feature_extraction/methods/pymupdf_tables.py` | Structure detection (PyMuPDFLines, PyMuPDFLinesStrict) |
| `src/zotero_chunk_rag/feature_extraction/methods/cell_rawdict.py` | Cell extraction (RawdictExtraction) |
| `src/zotero_chunk_rag/feature_extraction/methods/cell_words.py` | Cell extraction (WordAssignment) |
| `src/zotero_chunk_rag/feature_extraction/methods/ruled_lines.py` | Ruled-line detection |
| `src/zotero_chunk_rag/feature_extraction/methods/_row_clustering.py` | Row clustering (used by prose tables and pipeline) |
| `src/zotero_chunk_rag/feature_extraction/combination.py` | Boundary combination engine |
| `src/zotero_chunk_rag/feature_extraction/scoring.py` | Grid selection/scoring framework |
| `src/zotero_chunk_rag/feature_extraction/pipeline.py` | Multi-method pipeline orchestrator (Pipeline class, extract_page, all named configs) |

### 1.3 Delete postprocessors (all except cell_cleaning)

| File | Reason |
|------|--------|
| `src/zotero_chunk_rag/feature_extraction/postprocessors/absorbed_caption.py` | Pipeline postprocessor |
| `src/zotero_chunk_rag/feature_extraction/postprocessors/header_detection.py` | Pipeline postprocessor |
| `src/zotero_chunk_rag/feature_extraction/postprocessors/header_data_split.py` | Pipeline postprocessor |
| `src/zotero_chunk_rag/feature_extraction/postprocessors/continuation_merge.py` | Pipeline postprocessor |
| `src/zotero_chunk_rag/feature_extraction/postprocessors/inline_headers.py` | Pipeline postprocessor |
| `src/zotero_chunk_rag/feature_extraction/postprocessors/footnote_strip.py` | Pipeline postprocessor |

**Kept**: `postprocessors/cell_cleaning.py` (whitespace normalization, used by vision path)

### 1.4 Delete gap fill

| File | Reason |
|------|--------|
| `src/zotero_chunk_rag/_gap_fill.py` | Orphan caption recovery — replaced by caption-first design |

### 1.5 Delete pipeline weights and tuning

| File | Reason |
|------|--------|
| `tests/pipeline_weights.json` | Confidence multipliers for deleted methods |
| `tests/tune_weights.py` | Weight tuning script for deleted pipeline |

### 1.6 Delete tests for deleted code (top-level)

| File | Reason |
|------|--------|
| `tests/test_pipeline.py` | Tests Pipeline class, combine_hypotheses, BoundaryHypothesis, PipelineConfig |
| `tests/test_table_extraction_protocols.py` | Tests StructureMethod, CellExtractionMethod, PostProcessor protocols |
| `tests/test_gap_fill.py` | Tests _gap_fill module |
| `tests/test_column_detection_isolated.py` | Tests adaptive_row_tolerance and column detection methods |
| `tests/test_header_anchored_detection.py` | Tests header-anchored detection method |
| `tests/test_vision_batch_integration.py` | Tests 4-agent batch vision pipeline |
| `tests/test_vision_indexer_integration.py` | Tests 4-agent async vision pipeline |
| `tests/test_vision_stage_eval.py` | Tests 4-agent stage-by-stage evaluation |
| `tests/test_table_extraction_models.py` | Tests deleted model types (BoundaryPoint, BoundaryHypothesis, CellGrid, etc.) |

### 1.7 Delete dead support modules

| File | Reason |
|------|--------|
| `src/zotero_chunk_rag/feature_extraction/protocols.py` | Pipeline protocols — imports deleted `BoundaryHypothesis`, `TableContext` |
| `src/zotero_chunk_rag/feature_extraction/table_features.py` | Pipeline activation predicates — imports deleted `TableContext` |
| `src/zotero_chunk_rag/feature_extraction/render.py` | Standalone render utilities — replaced by `render_table_region()` in Step 2 |
| `src/zotero_chunk_rag/feature_extraction/models.py` | Only contains `CellGrid` — no longer used in vision-first architecture |

### 1.8 Delete tests for deleted code (test_feature_extraction/)

| File | Reason |
|------|--------|
| `tests/test_feature_extraction/test_pp_footnote_strip.py` | Tests deleted `FootnoteStrip` postprocessor |
| `tests/test_feature_extraction/test_pp_inline_headers.py` | Tests deleted `InlineHeaderFill` postprocessor |
| `tests/test_feature_extraction/test_pp_continuation_merge.py` | Tests deleted `ContinuationMerge` postprocessor |
| `tests/test_feature_extraction/test_pp_header_data_split.py` | Tests deleted `HeaderDataSplit` postprocessor |
| `tests/test_feature_extraction/test_pp_header_detection.py` | Tests deleted `HeaderDetection` postprocessor |
| `tests/test_feature_extraction/test_pp_absorbed_caption.py` | Tests deleted `AbsorbedCaptionStrip` postprocessor |
| `tests/test_feature_extraction/test_cell_rawdict.py` | Tests deleted `RawdictExtraction` |
| `tests/test_feature_extraction/test_cell_words.py` | Tests deleted `WordAssignment` |
| `tests/test_feature_extraction/test_cell_methods.py` | Tests deleted cell extraction methods |
| `tests/test_feature_extraction/test_ruled_lines.py` | Tests deleted `ruled_lines` module |
| `tests/test_feature_extraction/test_pymupdf_tables.py` | Tests deleted `PyMuPDFLines`/`PyMuPDFLinesStrict` |
| `tests/test_feature_extraction/test_row_clustering.py` | Tests deleted `_row_clustering` module |
| `tests/test_feature_extraction/test_pipeline_extract_page.py` | Tests deleted `Pipeline.extract_page()` |
| `tests/test_feature_extraction/test_pipeline_configs.py` | Tests deleted pipeline named configs |
| `tests/test_feature_extraction/test_table_features.py` | Tests deleted `table_features.py` |
| `tests/test_feature_extraction/test_vision_consensus.py` | Tests deleted consensus logic (`ConsensusResult`, `vision_result_to_cell_grid`) |
| `tests/test_feature_extraction/test_vision_integration.py` | Tests deleted 4-agent vision integration |
| `tests/test_feature_extraction/test_llm_structure.py` | Tests deleted LLM structure code |
| `tests/test_feature_extraction/test_agent_qa.py` | Tests deleted agent QA pipeline |
| `tests/test_feature_extraction/test_render.py` | Tests deleted `render.py` |

**Keep** from `tests/test_feature_extraction/`: `test_pp_cell_cleaning.py`,
`test_captions.py`, `test_figure_detection.py`, `test_ground_truth.py`,
`test_ground_truth_workspace.py`, `test_debug_db.py`, `test_integration.py`,
`__init__.py`

**Total files deleted: 48** (24 original + 4 dead modules + 20 test files)

---

## Wave 2: Delete pipeline-only types from models

**File**: `src/zotero_chunk_rag/feature_extraction/models.py`

**Status**: DONE (pipeline types deleted). `models.py` now contains only `CellGrid`.

`CellGrid` is also deleted (Wave 1.7) — `models.py` is fully removed.

---

## Wave 3: Gut vision modules

### 3.1 Strip `vision_extract.py`

**File**: `src/zotero_chunk_rag/feature_extraction/vision_extract.py`

**Delete**:
- `SHARED_SYSTEM` prompt (entire multi-agent system prompt, ~4900 tokens)
- `_ROLE_PREAMBLES` dict
- `ConsensusResult` dataclass
- `VisionExtractionResult` dataclass
- All consensus/voting functions: `compute_agreement_rate`, `_cell_vote`,
  `_shape_vote`, any majority-vote logic
- `build_verifier_inputs()`, `build_synthesizer_user_text()`
- `build_transcriber_cache_block()` (rebuilding for single-agent in Step 2)
- `detect_garbled_encoding()` — if only used by multi-agent prompt construction
- `_MAX_TOKENS` — if only referenced by deleted code

**Keep**:
- `AgentResponse` dataclass (single-agent still produces this shape)
- `parse_agent_response()` (JSON parsing logic — reusable)
- `build_common_ctx()` (builds raw_text + caption context — reusable)
- `render_table_png()` (PNG rendering — will be replaced in Step 2 but
  needed as a reference during the build phase)
- Worked examples text (Examples A–F) — extract into a constant for reuse

**Result**: `vision_extract.py` becomes a shell with `AgentResponse`,
`parse_agent_response`, `build_common_ctx`, `render_table_png`, and examples.
New vision-first logic gets built here in Step 2.

### 3.2 Strip `vision_api.py`

**File**: `src/zotero_chunk_rag/feature_extraction/vision_api.py`

**Delete**:
- Async path: `_async_extract()`, warm-up logic, `asyncio.gather` with semaphore
- 4-agent orchestration: `_submit_batch_stage()`, `_submit_verifier_batch()`,
  `_submit_synthesizer_batch()`
- `extract_tables()` (the current multi-agent entry point)
- `extract_tables_sync()` (sync wrapper for async)
- All imports from `vision_extract.py` that reference deleted symbols
  (`SHARED_SYSTEM`, `_ROLE_PREAMBLES`, `ConsensusResult`,
  `VisionExtractionResult`, `build_verifier_inputs`,
  `build_synthesizer_user_text`, `compute_agreement_rate`,
  `detect_garbled_encoding`, `build_transcriber_cache_block`)

**Keep**:
- `TableVisionSpec` dataclass
- `CostEntry` dataclass
- Cost logging: `_append_cost_entry()`, `_LOG_LOCK`, `_cost_log_path`
- Batch API infrastructure: batch submission, polling, result retrieval
  (the generic batch mechanics, not the 4-agent-specific orchestration)
- Model configuration, API client setup
- Any imports from `vision_extract.py` for kept symbols
  (`AgentResponse`, `parse_agent_response`, `build_common_ctx`,
  `render_table_png`)

**Result**: `vision_api.py` becomes the API access layer shell with
`TableVisionSpec`, cost logging, and generic batch infrastructure.
New single-agent batch logic gets built here in Step 3.

---

## Wave 4: Modify `pdf_processor.py`

**File**: `src/zotero_chunk_rag/pdf_processor.py`

### 4.1 Consolidate caption regexes

**Delete** these module-level definitions (lines 33–61):
- `_TABLE_CAPTION_RE`
- `_TABLE_CAPTION_RE_RELAXED`
- `_TABLE_LABEL_ONLY_RE`
- `_FIG_CAPTION_RE_COMP`
- `_CAPTION_NUM_RE`
- `_CAP_PATTERNS`
- `_NUM_GROUP`

**Replace** with imports from `feature_extraction/captions.py`:
```python
from .feature_extraction.captions import (
    _TABLE_CAPTION_RE,
    _TABLE_CAPTION_RE_RELAXED,
    _TABLE_LABEL_ONLY_RE,
    _FIG_CAPTION_RE as _FIG_CAPTION_RE_COMP,
    _CAPTION_NUM_PARSE_RE as _CAPTION_NUM_RE,
)
_CAP_PATTERNS = (_TABLE_CAPTION_RE, _TABLE_CAPTION_RE_RELAXED, _TABLE_LABEL_ONLY_RE)
```

Note: verify patterns are identical before replacing. The `_NUM_GROUP`
constant is defined identically in both files. `_CAPTION_NUM_RE` in
pdf_processor.py uses `r"(\d+)"` while `_CAPTION_NUM_PARSE_RE` in
captions.py uses the full `(?:Figure|Fig\.?|Table|Tab\.?)\s+{_NUM_GROUP}`
pattern — these are NOT identical. The `_CAPTION_NUM_RE` in pdf_processor.py
is simpler (just extracts digits). Keep the local `_CAPTION_NUM_RE` definition
if it differs; consolidate only the truly identical patterns.

### 4.2 Delete pipeline integration

**Delete** these import lines:
- `from .feature_extraction.pipeline import Pipeline, DEFAULT_CONFIG` (line 260)
- `from ._gap_fill import run_recovery` (line 313)
- `from .feature_extraction.methods._row_clustering import adaptive_row_tolerance` (line 1032)
- `from .feature_extraction.models import CellGrid, TableContext` (line 1207)
- `from .feature_extraction.postprocessors.absorbed_caption import AbsorbedCaptionStrip` (line 1208)

### 4.3 Delete pipeline-dependent functions

| Function | Lines | Reason |
|----------|-------|--------|
| `_result_to_extracted_table()` | 160–194 | Converts pipeline `ExtractionResult` → `ExtractedTable` |
| `_extract_footnotes_from_snapshots()` | 508–536 | Uses pipeline snapshot mechanism |
| `_adaptive_row_tolerance()` | 1027–1033 | Delegates to deleted `_row_clustering` |
| `_parse_prose_rows()` | 1036–1056 | Prose table parsing |
| `_extract_table_from_words()` | 1059–~1190 | Word-position table building |
| `_apply_prose_postprocessors()` | 1193–1251 | Uses CellGrid, TableContext, AbsorbedCaptionStrip |
| `_extract_prose_tables()` | 1254–~1380 | Main prose table extraction |
| `_collect_prose_table_content()` | 1381–~1465 | Prose content collection |

Also delete `_find_column_gap_threshold()` (line 831) **if** it is only
called by the prose table / word-extraction functions above. Verify by
grepping for its callers before deleting.

### 4.4 Stub `extract_document()` table extraction

In `extract_document()` (line 197), replace the pipeline extraction block
(lines 260–317) with:

```python
    # --- TABLE EXTRACTION (stubbed — vision-first path built in Steps 1-4) ---
    tables: list[ExtractedTable] = []
    table_idx = 0

    # --- FIGURE EXTRACTION (unchanged) ---
    from .feature_extraction.pipeline_support import extract_figures_from_pages
    # ... (figure detection loop stays as-is, lines 299-307) ...
```

Specifically, **remove**:
- `from .feature_extraction.pipeline import Pipeline, DEFAULT_CONFIG`
- `pipeline = Pipeline(DEFAULT_CONFIG)`
- The `for chunk in page_chunks:` loop that calls `pipeline.extract_page()` (lines 269–307)
- The `_extract_prose_tables()` call (line 310)
- The `from ._gap_fill import run_recovery` and `run_recovery()` call (lines 313–317)

**Keep** the figure extraction from the page loop. The figure detection
currently lives inside `pipeline.extract_page()` — it needs to be extracted
into a standalone call. Create a minimal helper:

```python
def _extract_figures_for_page(
    page, page_num, page_chunk, write_images, images_dir, doc,
) -> list[ExtractedFigure]:
    """Detect and optionally render figures on a page."""
    from .feature_extraction.captions import find_all_captions
    from .feature_extraction.methods.figure_detection import detect_figures, render_figure

    figure_captions = [c for c in find_all_captions(page) if c.caption_type == "figure"]
    figure_results = detect_figures(page, page_chunk, figure_captions) if page_chunk else []

    figures = []
    for fi, (fbbox, fcaption) in enumerate(figure_results):
        image_path = None
        if write_images and doc is not None and images_dir is not None:
            img = render_figure(doc, page_num, fbbox, Path(images_dir), fi)
            image_path = str(img) if img else None
        figures.append(ExtractedFigure(
            page_num=page_num,
            figure_index=fi,
            bbox=tuple(fbbox),
            caption=fcaption,
            image_path=Path(image_path) if image_path else None,
        ))
    return figures
```

Then the `extract_document()` page loop becomes:

```python
    tables: list[ExtractedTable] = []
    figures: list[ExtractedFigure] = []
    fig_idx = 0

    for chunk in page_chunks:
        pnum = chunk.get("metadata", {}).get("page_number", 1)
        page = doc[pnum - 1]

        # Skip references/appendix
        page_label = None
        if sections and pages:
            from .section_classifier import assign_section
            for p in pages:
                if p.page_num == pnum:
                    page_label = assign_section(p.char_start, sections)
                    break
            if page_label in ("references", "appendix"):
                continue

        # Figures (unchanged)
        page_figs = _extract_figures_for_page(
            page, pnum, chunk, write_images, images_dir, doc,
        )
        for f in page_figs:
            f.figure_index = fig_idx
            figures.append(f)
            fig_idx += 1

    # Tables: empty until vision-first path is built (Steps 1-4)
```

**Keep** everything after the page loop:
- `_assign_heading_captions()` call (line 320) — still useful for figures
- `_assign_continuation_captions()` call (line 324) — needed for cross-page tables
- Ligature normalization (lines 326–332)
- Artifact classification (lines 334–367)
- Figure-table overlap detection (lines 343–367) — harmless with empty tables
- False-positive figure removal (line 372)
- Artifact table removal (line 376)
- Stats and completeness (lines 378–401)
- Synthetic caption assignment (lines 383–390)

---

## Wave 5: Modify `indexer.py`

**File**: `src/zotero_chunk_rag/indexer.py`

**Delete**: `enhance_tables_with_vision()` method (line 433 to end of method)
and all its supporting code. This method imports `vision_result_to_cell_grid`
(deleted in Wave 3.1) and calls `extract_tables_sync` (deleted in Wave 3.2) —
it is broken now and must be removed as demolition, not deferred to Step 4.

**Keep**: Everything else — `index_all()`, `_index_document_detailed()`,
figure storage, reference matching, stats.

### 5.1 Fix `stress_test_real_library.py` import crash

Remove the import of `vision_result_to_cell_grid` (line 2105) and stub or
remove `_test_pipeline_methods()` so the file at least loads. The full stress
test update happens in Step 5, but the import crash must be fixed here.

---

## Wave 6: Clean up `__init__` files and remaining imports

### 6.1 `feature_extraction/methods/__init__.py`

Remove imports of deleted modules. Keep `figure_detection` import if present.

### 6.2 `feature_extraction/postprocessors/__init__.py`

Remove imports of deleted modules. Keep `cell_cleaning` import if present.

### 6.3 `feature_extraction/__init__.py`

Remove any re-exports of deleted symbols (Pipeline, configs, etc.).

### 6.4 Grep verification

Run `grep -r` for every deleted module name and symbol across the entire
`src/` directory. Fix any remaining references.

Specifically verify no remaining references to:
- `Pipeline`, `DEFAULT_CONFIG`, `FAST_CONFIG`, `RULED_CONFIG`, `MINIMAL_CONFIG`
- `BoundaryPoint`, `BoundaryHypothesis`, `PipelineConfig`, `ExtractionResult`, `PageFeatures`, `TableContext`
- `CellGrid` (deleted with `models.py`)
- `combination`, `scoring`, `_gap_fill`, `run_recovery`
- `AbsorbedCaptionStrip`, `HeaderDetection`, `HeaderDataSplit`,
  `ContinuationMerge`, `InlineHeaderFill`, `FootnoteStrip`
- `PyMuPDFLines`, `PyMuPDFLinesStrict`, `RawdictExtraction`, `WordAssignment`
- `_row_clustering`, `adaptive_row_tolerance`
- `extract_tables`, `extract_tables_sync`, `enhance_tables_with_vision`
- `SHARED_SYSTEM`, `_ROLE_PREAMBLES`, `ConsensusResult`, `VisionExtractionResult`
- `vision_result_to_cell_grid`
- `StructureMethod`, `CellExtractionMethod` (from deleted `protocols.py`)
- `has_ruled_lines`, `table_features` (from deleted `table_features.py`)
- `render_table_image`, `render_all_tables` (from deleted `render.py`)

---

## Agent Execution Rules

### No API calls

Implementation agents MUST NOT make any external API calls. This includes:
- Anthropic API (no vision calls, no batch submissions)
- Zotero API (no library queries)
- Any network requests

All verification is local: import checks, grep, and running existing tests
that use mocked/synthetic data.

### Test execution protocol

Tests are run at most TWICE per implementation session:

1. **First run**: Execute the relevant test suite. Record all failures.
2. **Quick fix round**: Fix only obvious, mechanical issues (broken imports,
   missing symbol renames, trivial type errors). Do NOT restructure code or
   chase cascading failures.
3. **Second run**: Execute the test suite again. Record remaining failures.
4. **Report**: Surface ALL remaining failures to the user for review.
   Do not attempt further fixes. Do not loop.

### No test modification to make tests pass

If a test fails, the agent reports the failure. The agent NEVER modifies
test assertions to make a failing test pass.

---

## Acceptance Criteria

1. **No dead references**: `grep -r` for all deleted symbols across `src/` returns zero matches (excluding comments)
2. **No deleted files imported**: No remaining `import` or `from` statement references a deleted module
3. **Git status**: Only deletions and modifications, no new files except this spec
