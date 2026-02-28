# Vision-First Table Extraction Architecture

## Status: Proposal (2026-03-01)

## Problem

The current pipeline uses 13 structure detection methods, 3 cell extraction
methods, a combination engine, and a scoring framework to extract tables from
PDFs. This machinery:

- Completely fails on text-formatted tables (no ruled lines, no borders)
- Produces inconsistent quality (some tables 100%, others catastrophic)
- Is unnecessary when vision extraction works — vision transcriber alone
  achieves 89.3% mean accuracy across 67 tables spanning 1973–2023
- Later pipeline stages (Y-verifier, X-verifier, Synthesizer) actively hurt
  accuracy (confirmed across 20 papers, 67 tables)

Caption detection is reliable: 100% of data tables in 20 papers across 50 years
have captions. Detection found 7/8 in the problem paper (1 fixable bug).

## Proposed Architecture

### Overview

Replace the multi-method extraction pipeline with:

```
Caption Detection (text layer, free)
  → Region Estimation (text layer, free)
  → PNG Rendering
  → Vision Transcriber (single agent, Haiku 4.5)
  → Conditional Re-crop (self-requested by model)
```

### Phase 1: Caption Detection

Use existing `find_all_captions()` — already reliable.

**Fix needed**: standalone label-only blocks (e.g., "TABLE V" as its own block
with title on a separate block) are not detected. The `_TABLE_LABEL_ONLY_RE`
regex matches but is never used as a primary detection path. Fix: add
`label_only_re.match(check_text)` as a primary match alongside strict/relaxed.

After fix, caption detection should find effectively all captioned tables.

### Phase 2: Region Estimation

For each detected caption, estimate the table region from text-layer data:

```python
def estimate_table_region(page, caption_bbox, next_caption_bbox=None):
    """Estimate table bbox from caption position and page structure.

    - Top: caption top (include caption in the image — model needs it for context)
    - Bottom: next_caption_top - margin, or page bottom, or next section heading
    - Left/Right: initially full page width

    For two-column detection:
    - Use word x-positions to detect column layout
    - If caption sits within one column, crop to that column's x-range
    - If table appears to span both columns (words span full width below
      caption), use full page width
    """
```

Column detection heuristic (from word positions):
1. Get all words on the page via `page.get_text("words")`
2. Build histogram of word x-center positions
3. If bimodal distribution with gap in the middle → two-column layout
4. Check which column the caption falls in
5. Check if content below caption stays in that column or spans full width

This doesn't need to be perfect — it's a first estimate. The re-crop mechanism
handles cases where it's wrong.

### Phase 3: Vision Transcription (Single Agent)

Send cropped region + raw_text to the transcriber (Haiku 4.5). Single agent
only — the 4-stage pipeline (transcriber → Y/X verifiers → synthesizer) was
proven harmful across 20 papers.

**System prompt**: Adapted from the current SHARED_SYSTEM but simplified:
- Remove verifier/synthesizer role preambles
- Keep worked examples (A–F)
- Add re-crop request instructions

**Input**:
- PNG of estimated table region
- `raw_text`: `page.get_text("text", clip=estimated_bbox)`
- Caption text (so model knows which table to extract if multiple visible)

**Output schema**:
```json
{
  "headers": ["col1", "col2", ...],
  "rows": [["cell", "cell", ...], ...],
  "footnotes": "footnote text",
  "recrop": {
    "needed": false
  }
}
```

### Phase 4: Self-Requested Re-crop

The transcriber already uses `raw_text` to correct its visual transcription.
During this correction process, it compares what it visually reads against the
text-layer content. The **re-crop trigger** is:

> A high rate of mismatched characters between the model's visual transcription
> and the corresponding raw_text elements.

This is NOT about raw_text containing extra text (that's expected with broad
crops). It's about the model's extracted cell content not matching the text-layer
content for those same cells. Causes:

1. **Column bleed**: model reads text from adjacent column because the crop
   includes it, and the visual column boundary is ambiguous
2. **Wrong table**: crop includes multiple tables, model extracts the wrong one
3. **Truncated table**: table extends beyond crop boundary
4. **Caption/table separation**: caption is in a different column or page region
   than the table body

**Re-crop request schema**:
```json
{
  "headers": [...],
  "rows": [...],
  "footnotes": "...",
  "recrop": {
    "needed": true,
    "reason": "High character mismatch rate — visual read of column 3 values
               does not correspond to any raw_text elements",
    "bbox_pct": {
      "top": 5,
      "bottom": 70,
      "left": 0,
      "right": 48
    }
  }
}
```

`bbox_pct` values are percentages of the original crop image dimensions.

**Re-crop flow**:
1. Convert `bbox_pct` to absolute PDF coordinates using the original crop bbox
2. Re-render the tighter region as PNG
3. Re-extract `raw_text` for the tighter region
4. Re-send to transcriber (same model, same system prompt)
5. Accept result (no further re-crops — max 1 retry)

**Cost**: the `recrop` field adds ~10 output tokens when not needed. The second
pass only fires for problem cases. Expected re-crop rate: 5–15% of tables.

### Phase 5: Figure Detection (Unchanged)

Figures use `page.get_image_info()` for bbox detection + `find_all_captions()`
for caption matching. No vision needed for figure detection — only for reading
figure-data-tables if applicable.

## What This Eliminates

The entire multi-method extraction machinery becomes unnecessary for the vision
path:

| Component | Current | Vision-first |
|-----------|---------|-------------|
| `feature_extraction/methods/` (13 structure methods) | Required | **Removed from vision path** |
| `feature_extraction/combination.py` | Required | **Removed** |
| `feature_extraction/scoring.py` | Required | **Removed** |
| `feature_extraction/pipeline.py` (orchestrator) | Required | **Simplified** — caption detection + region estimation only |
| `feature_extraction/captions.py` | Used | **Primary detection** — fix label-only bug |
| `feature_extraction/vision_api.py` | 4-agent pipeline | **Single transcriber** |
| `feature_extraction/vision_extract.py` | 4-stage adversarial | **Single-pass + conditional re-crop** |
| `feature_extraction/postprocessors/` | 7 post-processors | **Keep cell cleaning only** — model handles the rest |

## Fallback: Pipeline as Offline Mode

The existing pipeline remains available as an offline/free fallback for users
who can't or don't want to use the vision API:

```python
class ExtractionMode(Enum):
    VISION = "vision"       # Caption + vision (default when API key available)
    PIPELINE = "pipeline"   # Multi-method pipeline (offline/free)
    HYBRID = "hybrid"       # Pipeline first, vision for failures
```

## Cost Projections

| Scenario | Per table | 800 papers (~2,480 tables) |
|----------|----------|---------------------------|
| Current: 4-agent pipeline (batch+cache) | $0.016 | $39 |
| Vision-first: single transcriber (batch+cache) | ~$0.005 | ~$12 |
| Vision-first + 10% re-crop rate | ~$0.006 | ~$14 |

Single transcriber is ~3× cheaper than the 4-agent pipeline because:
- 1 API call per table instead of 4
- Same system prompt cache benefits
- Smaller output (no correction fields)

## Implementation Plan

### Step 1: Fix caption detection (label-only bug)
- Add `label_only_re.match(check_text)` as primary match path in
  `find_all_captions()`
- Merge multi-block captions (label block + title block on next line)
- Verify on the 20-paper corpus

### Step 2: Implement region estimation
- `estimate_table_region(page, caption, next_caption)` function
- Column layout detection from word x-positions
- Unit tests with known two-column and single-column papers

### Step 3: Simplify vision pipeline to single transcriber
- Strip verifier/synthesizer stages from `vision_extract.py`
- Add `recrop` field to transcriber output schema
- Update system prompt with re-crop instructions
- Update `vision_api.py` for single-agent path

### Step 4: Implement re-crop mechanism
- Parse `recrop.bbox_pct` → absolute coordinates
- Re-render + re-extract on re-crop request
- Max 1 retry per table
- Log re-crop rate and reasons for monitoring

### Step 5: Integration into indexer
- New `extract_tables_vision_first()` entry point
- Caption detection → region estimation → vision → optional re-crop
- Replace `enhance_tables_with_vision()` (current post-hoc enhancement)
- Vision becomes the primary path, not an enhancement layer

### Step 6: Evaluation
- Run on 20-paper corpus, compare against:
  - Current pipeline-only extraction
  - Current 4-agent vision pipeline
  - Ground truth (44 tables)
- Key metrics: tables found, cell accuracy, re-crop rate, cost

## Open Questions

1. **Multi-block captions**: When caption label ("TABLE V") and title
   ("Energy per Photon...") are in separate text blocks, should caption
   detection merge them? Or should region estimation start from the label
   block and let the model read the title from the image?

2. **Caption-table separation**: Some papers put the caption below the table,
   or in an adjacent column. Region estimation needs to handle both
   above-table and below-table captions. Heuristic: check if content above
   the caption looks tabular (aligned columns in word positions).

3. **Cross-page tables**: Table starts on page N, continues on page N+1.
   Current pipeline handles this via continuation caption detection. Vision
   path needs the same — detect "Table N (continued)" captions and merge
   results across pages.

4. **Very large tables**: Tables spanning most of a page produce large PNG
   images (more tokens). Is there a point where the image should be split
   into sections? Or does the model handle full-page images adequately?

5. **Pipeline fallback threshold**: In hybrid mode, what quality metric
   triggers a fallback from pipeline to vision? Fill rate < X%?
   `post_processed is None`? Character mismatch rate?
