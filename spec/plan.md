# Vision-First Implementation Plan

## Status: Implementation-Ready (2026-03-01)

## Summary

Replace the multi-method extraction pipeline with a caption-driven, single-agent
vision pipeline. The transcriber alone outperforms the 4-agent pipeline (transcriber
→ Y-verifier → X-verifier → synthesizer) — every later stage makes things worse,
confirmed across multiple runs.

**Approach**: Destructive. Delete the pipeline first (Phase 0), then build vision-first.
Old code misleads agents executing rewrites.

---

## Architecture

```
Caption Detection (text layer, free)
  → Simple Crop (caption top → next caption or page bottom, full width)
  → PNG Rendering (adaptive DPI, multi-strip for tall crops)
  → Vision Transcriber (single Haiku 4.5 agent, batch API only)
  → Conditional Re-crop (model-requested, max 1 retry)
```

### No pipeline fallback

The multi-method pipeline is deleted entirely. No fallback, no offline mode.
Users without an API key get no table extraction. PaddleOCR (Stream B) is
evaluated as a potential free alternative in a parallel stream.

### Module responsibilities

| Module | Responsibility |
|--------|---------------|
| `feature_extraction/captions.py` | Caption detection (primary table/figure finding) |
| `feature_extraction/vision_extract.py` | All PDF-extraction-specific logic: crop computation, PNG rendering (`render_table_region`), system prompt, result parsing |
| `feature_extraction/vision_api.py` | Vision API access layer: sync batch submission, cost logging, API interaction |
| `feature_extraction/debug_db.py` | Debug database for stress test: GT diffs, vision agent results |
| `feature_extraction/ground_truth.py` | GT comparison framework |
| `pdf_processor.py` | Document extraction orchestrator: sections, captions→vision, figures, markdown, completeness |
| `indexer.py` | Indexing pipeline: calls `extract_document()`, stores chunks/tables/figures |

### Deleted modules (Phase 0)

| Module | Reason |
|--------|--------|
| `feature_extraction/models.py` | Only contained `CellGrid` — no longer used |
| `feature_extraction/protocols.py` | Pipeline protocols (`StructureMethod`, `CellExtractionMethod`, `PostProcessor`) — all implementations deleted |
| `feature_extraction/table_features.py` | Pipeline activation predicates (`has_ruled_lines`, etc.) — references deleted `TableContext` |
| `feature_extraction/render.py` | Standalone render utilities — replaced by `render_table_region()` in `vision_extract.py` |
| `feature_extraction/pipeline.py` | Multi-method pipeline orchestrator — deleted |
| `feature_extraction/combination.py` | Boundary combination engine — deleted |
| `feature_extraction/scoring.py` | Grid selection/scoring — deleted |
| `feature_extraction/methods/*` (except `figure_detection.py`) | Structure/cell extraction methods — deleted |
| `feature_extraction/postprocessors/*` (except `cell_cleaning.py`) | Pipeline postprocessors — deleted |

---

## Agent Execution Rules (all phases)

### No API calls

Implementation agents MUST NOT make external API calls (Anthropic, Zotero,
or any network request). All code that calls external APIs must be tested
with mocks or stubs, never live services.

The only exception is Step 5 (Evaluation), which is **user-initiated only**.
The user runs the stress test manually; agents never trigger it.

### Test execution protocol

Tests are run at most TWICE per implementation session:

1. **First run**: Execute relevant tests. Record all failures.
2. **Quick fix round**: Fix only obvious mechanical issues (broken imports,
   missing symbols, trivial type errors). No restructuring.
3. **Second run**: Execute again. Record remaining failures.
4. **Report**: Surface all remaining failures to the user. Do not loop.

### No test modification to make tests pass

If a test fails, the agent reports the failure — it does not modify test
assertions. Tests may need updating for the new architecture, but that is
a user decision, not an agent decision.

---

## Phase 0: Demolition

Delete the multi-method pipeline, 4-agent vision pipeline, all related tests,
prose table extraction, gap fill, pipeline-only data models, and dead support
modules. Stub `extract_document()` to return empty tables. Delete
`enhance_tables_with_vision()` from `indexer.py` (references deleted symbols).

**Full spec**: `spec/phase-0-demolition.md`

### Additional deletions (not in original spec, identified during audit)

**Source files** (import deleted symbols, will crash):
- `feature_extraction/protocols.py` — imports `BoundaryHypothesis`, `TableContext`
- `feature_extraction/table_features.py` — imports `TableContext`
- `feature_extraction/render.py` — replaced by `render_table_region()` in Step 2
- `feature_extraction/models.py` — only contains `CellGrid`, no longer used

**Test files** (entire `tests/test_feature_extraction/` directory missed):
- `test_pp_footnote_strip.py`, `test_pp_inline_headers.py`, `test_pp_continuation_merge.py`
- `test_pp_header_data_split.py`, `test_pp_header_detection.py`, `test_pp_absorbed_caption.py`
- `test_cell_rawdict.py`, `test_cell_words.py`, `test_cell_methods.py`
- `test_ruled_lines.py`, `test_pymupdf_tables.py`, `test_row_clustering.py`
- `test_pipeline_extract_page.py`, `test_pipeline_configs.py`, `test_table_features.py`
- `test_vision_consensus.py`, `test_vision_integration.py`
- `test_llm_structure.py`, `test_agent_qa.py`
- `test_render.py`

**Keep** from that directory: `test_pp_cell_cleaning.py`, `test_captions.py`,
`test_figure_detection.py`, `test_ground_truth.py`, `test_ground_truth_workspace.py`,
`test_debug_db.py`, `test_integration.py`, `__init__.py`

**indexer.py**: Delete `enhance_tables_with_vision()` (line 433–end of method).
References `vision_result_to_cell_grid` and `extract_tables_sync`, both deleted
in Wave 3. This is demolition, not Step 4 — it's broken now.

**stress_test_real_library.py**: Remove import of `vision_result_to_cell_grid`
(line 2105) and the `_test_pipeline_methods()` function that uses it. The stress
test needs updating in Step 5 anyway, but the import crash should be fixed in
Phase 0 so the file at least loads.

---

## Step 1: Fix caption detection

**File**: `feature_extraction/captions.py`

### Label-only bug

`_TABLE_LABEL_ONLY_RE` exists but is never tried as a primary match. Add it
as a primary match path between strict and relaxed:

```python
if prefix_re.match(check_text):
    matched = True
elif label_only_re and label_only_re.match(check_text):
    matched = True
elif relaxed_re and relaxed_re.match(check_text):
    # ... existing font-change confirmation logic ...
```

Also add label-only matching to `_scan_lines_for_caption()`.

### Multi-block caption merging — NOT IMPLEMENTED

~~When a label-only caption is detected, merge with the next text block.~~

**Decision**: No merge in `captions.py`. The vision agent enriches caption
text at extraction time — it sees the full crop (caption top → next caption
or page bottom) and can read the descriptive text directly. This avoids
fragile heuristics about block proximity and block-order reliability in
2-column layouts.

### Regex consolidation (done in Phase 0)

`pdf_processor.py`'s duplicate caption regexes are already consolidated
to import from `captions.py` during Phase 0 demolition.

### Verification

Standalone caption audit script (`tests/audit_captions.py`) runs
`find_all_captions()` on the 20-paper vision test corpus (10 stress test +
10 extra). Reports per-paper table/figure/label-only caption counts. No
external API calls (Zotero SQLite + local PDFs only). Target: 100% of known
data tables detected.

**Full spec**: `spec/step-1-caption-detection.md`

---

## Step 2: Vision extraction module

**File**: `feature_extraction/vision_extract.py`
**Full spec**: `spec/step-2-vision-extract.md`

### Rendering transition

Delete `render_table_png()` in this step (not deferred to Step 3). Replace
with `render_table_region()` (multi-strip aware). Also remove the
`render_table_png` import from `vision_api.py` (the `_prepare_table` method
that references it is rewritten in Step 3 and is never called in the
stubbed state).

### Simple crop

`compute_all_crops(page, captions, caption_type="table")` returns crop
bboxes for each table caption:
- **Top**: `caption.bbox[1]` (include caption — model needs it for context)
- **Bottom**: Next caption's `bbox[1]` on the same page (any type), or page bottom
- **Left/Right**: Full page width (page.rect.x0, page.rect.x1)

No column detection. No region estimation. Full width always.

### PNG rendering with multi-strip

The Anthropic API resizes images with long edge > 1568px. For full-width
crops, effective DPI depends on which dimension is the long edge:

| Crop | Long edge | Effective DPI |
|------|-----------|--------------|
| Full-width × short table (< 8.27") | Width | **190** |
| Full-width × full page (11.7") | Height | **134** |

At 134 DPI, 8pt font is ~15px — marginal for structural reading. Strips
fix this by splitting tall crops so width becomes the long edge (~190 DPI).

**Trigger**: `height > width AND effective_dpi < strip_dpi_threshold`

```python
def render_table_region(
    page: pymupdf.Page,
    bbox: tuple[float, float, float, float],
    *,
    dpi_floor: int = 150,
    dpi_cap: int = 300,
    strip_dpi_threshold: int = 200,
) -> list[tuple[bytes, str]]:
```

`strip_dpi_threshold` is parameterizable: default 200 for initial crops,
pass 250 for re-crops (higher quality on tighter regions).

**Strip construction**: Each strip is at most `width` tall (square), so
width becomes the long edge. 15% overlap between strips prevents row loss
at boundaries. Typical full-page table: 2 strips at ~190 DPI.

**Multi-image API call**: Multiple images in one message, ordered
top-to-bottom. System prompt instructs the model to deduplicate rows
in the overlap zone.

### System prompt (VISION_FIRST_SYSTEM)

Static single-agent prompt (same for all tables in a batch, maximizes
cache hit rate). Adapted from SHARED_SYSTEM:
- Remove all multi-agent role preambles (Y_VERIFIER, X_VERIFIER, SYNTHESIZER)
- Remove "corrections" field from output schema
- Keep formatting standards (Section 2), pitfall warnings (Section 3)
- Keep worked examples (A–F) — valuable for single-agent
- Add re-crop request instructions
- Add caption correction: agent reads actual caption from image and returns
  corrected full caption in `caption` field (separate from `table_label`)
- Add strip-aware instructions (always present, inert for single-image tables)

### Output schema

```json
{
  "table_label": "<string or null>",
  "caption": "<full caption text from image>",
  "is_incomplete": false,
  "incomplete_reason": "",
  "headers": ["col1", "col2", ...],
  "rows": [["r1c1", "r1c2", ...], ...],
  "footnotes": "<string>",
  "recrop": {
    "needed": false,
    "bbox_pct": [0, 0, 100, 100]
  }
}
```

### AgentResponse updates

`AgentResponse` dataclass gets three new fields:
- `caption: str` — full caption text as read from image
- `recrop_needed: bool` — model requests a tighter crop
- `recrop_bbox_pct: list[float] | None` — [x0, y0, x1, y1] as 0–100 pct
  relative to the full original crop region

### Re-crop mechanism

The transcriber compares its visual read against raw_text. High character
mismatch rate → requests re-crop with `bbox_pct` (percentages relative to
the full original crop region, not individual strips).

`compute_recrop_bbox(original_bbox, bbox_pct)` converts percentages to
absolute PDF coordinates with clamping.

**Re-crop flow**:
1. Parse `recrop` from `AgentResponse`
2. Convert `bbox_pct` to absolute PDF coordinates via `compute_recrop_bbox()`
3. Re-render tighter region as PNG (with `strip_dpi_threshold=250`)
4. Re-extract raw_text for new region
5. Re-send to transcriber (same prompt)
6. Max 1 retry. Always keep the re-cropped result unless it has `is_incomplete`.

---

## Step 3: API layer

**File**: `feature_extraction/vision_api.py`

### Batch-only, fully synchronous

No async path. All extraction uses the Anthropic Batch API. The entire
module converts from async to sync.

### Component audit

**Reuse as-is** (no changes needed):
- `TableVisionSpec` — input spec dataclass. Works for single agent.
- `CostEntry` — cost record dataclass. `agent_role` = `"transcriber"`.
- `_PRICING` — pricing dict.
- `_compute_cost()` — cost computation from usage object.
- `_create_batch()` — generic `list[dict]` → batch ID. No agent-specific logic.
- `session_cost` property.

**Rewrite async → sync**:
- `_poll_batch()` → sync: replace `async def` + `asyncio.sleep` with
  `def` + `time.sleep`. Cost logging and result parsing logic reusable.
- `_submit_and_poll()` → sync: thin wrapper, mirrors `_poll_batch` change.
- `_append_cost_entry()` → sync: replace `asyncio.Lock` with
  `threading.Lock`. Same JSON read-append-write logic.
- `_LOG_LOCK` → `threading.Lock()` instead of `asyncio.Lock()`.
- Replace `import asyncio` with `import threading`, `import time`.

**Rewrite for single-agent + multi-strip**:
- `_prepare_table()` → call `render_table_region()` instead of
  `render_table_png()`. Return `list[tuple[str, str]]` (multiple
  base64 images for multi-strip tables) instead of single image.
- `VisionAPI.__init__()` → drop `AsyncAnthropic` client, drop
  `concurrency` param. Keep `_sync_client`, model, cost paths.

**New**:
- `extract_tables_batch(specs: list[TableVisionSpec]) -> list[AgentResponse]`
  — main entry point. Builds batch requests with VISION_FIRST_SYSTEM prompt
  + image(s) + raw_text per table, submits batch, polls, parses responses.

### Cache strategy

- BP1 = system prompt (cached across all tables in batch)
- BP2 = image (per-table, within-table cache for re-crops)

---

## Step 4: Integration

**Files**: `pdf_processor.py`, `indexer.py`, `feature_extraction/postprocessors/cell_cleaning.py`,
`feature_extraction/debug_db.py`

### Rewire `extract_document()`

The pipeline extraction loop is already stubbed (Phase 0). Replace the
`tables: list[ExtractedTable] = []` stub with:
1. For each page: `find_all_captions()` → collect table captions
2. For each table caption: compute crop, build `TableVisionSpec`
3. Send all specs to vision API (batch) via `vision_api.py`
4. Parse results → `ExtractedTable` objects
5. Apply cell cleaning (standalone normalization functions)
6. Figure detection (unchanged — already wired)
7. Continuation caption detection (cross-page tables)
8. Artifact classification, completeness, stats (unchanged)

### Refactor `cell_cleaning.py`

`cell_cleaning.py` imports `CellGrid` from deleted `models.py`. Refactor to:
- Extract normalization functions (ligatures, leading-zero recovery,
  negative-sign reassembly, control-char mapping) as standalone functions
  that operate on `list[str]` (headers) and `list[list[str]]` (rows).
- Delete the `CellCleaning` class and its `process(grid: CellGrid)` method.
- `pdf_processor.py` already imports only `_normalize_ligatures` from this
  module (line 951) — that path continues to work.

### Prune `debug_db.py`

Remove pipeline-specific tables and functions:
- Delete: `write_method_result` / `method_results` table
- Delete: `write_pipeline_run` / `pipeline_runs` table
- Delete: `write_vision_consensus` / `vision_consensus` table
- Keep: `write_ground_truth_diff` / `ground_truth_diffs` table
- Keep: `write_vision_agent_result` / `vision_agent_results` table
- Update: `EXTENDED_SCHEMA` and `create_extended_tables` to match

### Update stress test

`stress_test_real_library.py` needs updating for vision-first:
- Remove `_test_pipeline_methods()` and its `vision_result_to_cell_grid` import
- Update GT comparison to use `AgentResponse` output directly
- Pipeline depth report section → vision extraction report

### Known limitation: uncaptioned continuation tables

Tables that continue on the next page WITHOUT a "Table N (continued)"
caption won't be found (no caption = no vision extraction). This is
accepted as a minor regression — most journals require continuation captions.

---

## Step 5: Evaluation

### Stress test

The stress test calls `extract_document()` → auto-uses new vision path.
Run the existing `tests/stress_test_real_library.py` after integration.

### Success criteria

- Caption detection: 100% of known data tables found
- Mean cell accuracy ≥ 85% (on 44 GT tables)
- Re-crop rate: < 20%
- Cost: < $0.01 per table (batch+cache)
- Zero MAJOR stress test failures

---

## Implementation Order

```
Phase 0: Demolition
  ↓
Step 1 (caption fix) ──┐
Step 2 (vision extract) ├── Step 4 (integration) ── Step 5 (evaluation)
Step 3 (API layer) ─────┘

Stream B: [B1 install] ── [B2 HTML parser] ── [B3 caption match] ── [B4 eval] ── [B5 report] ── [B6 conditional integration]
```

Steps 1–3 can run in parallel after Phase 0.
Step 4 depends on all of Steps 1–3.
Step 5 validates the complete system.
Stream B is mostly independent — B3 (caption matching) uses `find_all_captions()`
from `captions.py`, which Step 1 fixes (label-only bug, multi-block merging).
If B3 runs before Step 1, it will miss some captions. This is acceptable for
evaluation purposes (it just means B4 results undercount PaddleOCR's potential).
For final B6 integration, Step 1 must be complete.

---

## Stream B: PaddleOCR Local Extraction (Parallel Evaluation)

### Goal

Evaluate PaddleOCR PP-StructureV3 as a free, local, zero-API-cost
alternative. Must be independently viewable in vision_viewer without
completing any Stream A steps (and vice versa).

### Steps

1. **B1**: Install `paddlepaddle`, `paddleocr`. New file: `feature_extraction/paddle_extract.py`
2. **B2**: HTML-to-structured-data converter (`parse_paddle_html()`)
3. **B3**: Caption matching (uses `find_all_captions()` from `captions.py`)
4. **B4**: Evaluation harness (`tests/test_paddle_eval.py`) — compare against 44 GT tables
5. **B5**: Comparative report (`_paddle_vs_vision_comparison.md`)
6. **B6**: Integration (conditional) — `ExtractionMode.VISION` / `ExtractionMode.LOCAL`

### Independence constraint

Stream B's extractor must produce output viewable in vision_viewer without
any Stream A code. Stream A must work without PaddleOCR installed.
