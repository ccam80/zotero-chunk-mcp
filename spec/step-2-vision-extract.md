# Step 2: Vision Extraction Module

## Overview

Build the vision-first extraction building blocks in `vision_extract.py`:
crop computation from caption positions, multi-strip PNG rendering, a
single-agent system prompt, and updated response parsing with caption
correction and re-crop fields. Also delete `render_table_png()` (replaced
by `render_table_region()`).

After this step, `vision_extract.py` provides everything Step 3 (API layer)
and Step 4 (integration) need to build and parse vision extraction requests.

**File modified**: `src/zotero_chunk_rag/feature_extraction/vision_extract.py`
**File touched** (import removal only): `src/zotero_chunk_rag/feature_extraction/vision_api.py`
**Test file created**: `tests/test_feature_extraction/test_vision_extract.py`

---

## Wave 2.1: Geometry — crop computation and rendering

### Task 2.1.1: `compute_all_crops()`

- **Description**: Given a PyMuPDF page and all detected captions on that page,
  compute crop bounding boxes for each table caption. Each crop runs from the
  caption's top edge to the next caption's top edge (any type — table or figure),
  at full page width. The last caption on the page extends to the page bottom.

- **Files to modify**:
  - `src/zotero_chunk_rag/feature_extraction/vision_extract.py` — add function

- **Function signature**:
  ```python
  def compute_all_crops(
      page: pymupdf.Page,
      captions: list[DetectedCaption],
      *,
      caption_type: str = "table",
  ) -> list[tuple[DetectedCaption, tuple[float, float, float, float]]]:
      """Compute crop bboxes for captions of the given type.

      For each caption matching caption_type, the crop region is:
      - Top: caption.bbox[1] (include caption in crop)
      - Bottom: next caption's bbox[1] (any type), or page.rect.y1
      - Left: page.rect.x0
      - Right: page.rect.x1

      Args:
          page: PyMuPDF page object.
          captions: All detected captions on this page (sorted by y_center).
          caption_type: Which caption type to compute crops for ("table" or "figure").

      Returns:
          List of (caption, crop_bbox) tuples for matching captions only.
      """
  ```

- **Logic**:
  1. Captions are already sorted by `y_center` (from `find_all_captions`).
  2. Iterate through all captions. For each caption matching `caption_type`:
     - `top = caption.bbox[1]`
     - `bottom = next_caption.bbox[1]` if there is a next caption (of any type),
       else `page.rect.y1`
     - `left = page.rect.x0`, `right = page.rect.x1`
  3. Skip any crop where `bottom <= top` (degenerate).

- **Import needed**: `from .captions import DetectedCaption`

- **Tests**:
  - `test_vision_extract.py::TestComputeAllCrops::test_single_table_caption`
    — One table caption at y=200 on an A4 page (0, 0, 595, 842). Assert:
    returns 1 result; crop bbox is `(0.0, 200.0, 595.0, 842.0)`.
  - `test_vision_extract.py::TestComputeAllCrops::test_two_table_captions`
    — Table caption A at y=200, table caption B at y=500. Assert: 2 results;
    crop A is `(0.0, 200.0, 595.0, 500.0)`, crop B is `(0.0, 500.0, 595.0, 842.0)`.
  - `test_vision_extract.py::TestComputeAllCrops::test_table_then_figure_boundary`
    — Table caption at y=200, figure caption at y=400. Assert: 1 result
    (table only); crop is `(0.0, 200.0, 595.0, 400.0)` (bounded by figure caption).
  - `test_vision_extract.py::TestComputeAllCrops::test_no_matching_captions`
    — Two figure captions, `caption_type="table"`. Assert: returns empty list.
  - `test_vision_extract.py::TestComputeAllCrops::test_full_page_width`
    — Assert crop x0 == page.rect.x0 and x1 == page.rect.x1 regardless of
    caption's own x-coordinates.

- **Acceptance criteria**:
  - Function returns crops only for the requested `caption_type`
  - Crop boundaries use the next caption of ANY type, not just the same type
  - Full page width always used (no column detection)


---

### Task 2.1.2: `render_table_region()` with multi-strip

- **Description**: Replace `render_table_png()` with a multi-strip-aware renderer.
  When a crop is tall (height > width) and the Anthropic API would resize it to
  below the DPI threshold, split the crop into overlapping vertical strips where
  width is the long edge, yielding ~190 DPI per strip.

- **Files to modify**:
  - `src/zotero_chunk_rag/feature_extraction/vision_extract.py` — add
    `render_table_region()` and `_split_into_strips()` helper

- **Function signatures**:
  ```python
  def render_table_region(
      page: pymupdf.Page,
      bbox: tuple[float, float, float, float],
      *,
      dpi_floor: int = 150,
      dpi_cap: int = 300,
      strip_dpi_threshold: int = 200,
  ) -> list[tuple[bytes, str]]:
      """Render a table region as one or more PNGs.

      Returns list of (png_bytes, media_type). Usually 1 image; multiple
      when crop height > width and effective DPI < strip_dpi_threshold.

      The Anthropic API resizes images so the long edge is 1568px.
      When height is the long edge, effective DPI drops. Strips fix
      this by splitting tall crops so width becomes the long edge.

      Args:
          page: PyMuPDF page object.
          bbox: (x0, y0, x1, y1) crop region in PDF points.
          dpi_floor: Minimum render DPI.
          dpi_cap: Maximum render DPI.
          strip_dpi_threshold: Multi-strip trigger. If height > width
              and effective_dpi < this value, split into strips.
              Default 200 for initial crops. Pass 250 for re-crops.
      """


  def _split_into_strips(
      bbox: tuple[float, float, float, float],
      overlap_frac: float = 0.15,
  ) -> list[tuple[float, float, float, float]]:
      """Split a tall bbox into overlapping horizontal strips.

      Each strip height equals the crop width (making it square), so
      width becomes the long edge after API resize. Adjacent strips
      overlap by overlap_frac of the strip height.

      Returns list of strip bboxes, ordered top-to-bottom.
      """
  ```

- **Multi-strip logic**:
  1. Compute `width_in = (x1 - x0) / 72`, `height_in = (y1 - y0) / 72`
  2. `long_edge_in = max(width_in, height_in)`
  3. `effective_dpi = 1568 / long_edge_in`
  4. If `height_in > width_in AND effective_dpi < strip_dpi_threshold`:
     - Call `_split_into_strips(bbox)` → list of sub-bboxes
     - Render each strip at `optimal_dpi = min(dpi_cap, int(1568 / strip_width_in))`
       clamped to `[dpi_floor, dpi_cap]`
  5. Else: render single image at `optimal_dpi = min(dpi_cap, int(1568 / long_edge_in))`
     clamped to `[dpi_floor, dpi_cap]`

- **Strip construction** (`_split_into_strips`):
  1. `strip_height_pt = (x1 - x0)` — square strips
  2. `overlap_pt = strip_height_pt * overlap_frac`
  3. `step_pt = strip_height_pt - overlap_pt`
  4. Generate strips starting from `y0`, advancing by `step_pt`, each `strip_height_pt` tall
  5. Last strip's bottom clamped to `y1`
  6. All strips use same x0, x1

- **Rendering each strip/image**:
  ```python
  clip = pymupdf.Rect(x0, y0, x1, y1)
  mat = pymupdf.Matrix(dpi / 72, dpi / 72)
  pix = page.get_pixmap(matrix=mat, clip=clip)
  return (pix.tobytes("png"), "image/png")
  ```

- **Tests**:
  - `test_vision_extract.py::TestRenderTableRegion::test_single_image_short_crop`
    — Crop 595×300pt (width > height). Assert: returns 1 image; image is valid
    PNG (starts with `b'\x89PNG'`).
  - `test_vision_extract.py::TestRenderTableRegion::test_multi_strip_tall_crop`
    — Crop 595×842pt (full A4 page, height > width, effective DPI=134 < 200).
    Assert: returns 2 images; both are valid PNGs.
  - `test_vision_extract.py::TestRenderTableRegion::test_custom_strip_threshold`
    — Crop 595×700pt with `strip_dpi_threshold=250`. Height > width,
    effective_dpi = 1568/(700/72) = 161 < 250. Assert: returns 2+ images.
    Same crop with `strip_dpi_threshold=150`: 161 > 150. Assert: returns 1 image.
  - `test_vision_extract.py::TestSplitIntoStrips::test_strip_dimensions`
    — bbox = (0, 0, 595, 842). Assert: each strip height <= 595pt (strip_height = width);
    strips cover full height; last strip bottom == 842.
  - `test_vision_extract.py::TestSplitIntoStrips::test_strip_overlap`
    — Assert: for adjacent strips, `strip[i].y1 - strip[i+1].y0 > 0`
    (overlap exists); overlap is approximately `strip_height * 0.15`.
  - `test_vision_extract.py::TestSplitIntoStrips::test_short_crop_no_split`
    — bbox = (0, 0, 595, 300). Strip height (595) > crop height (300).
    Assert: returns 1 strip equal to original bbox.

- **Acceptance criteria**:
  - Single image returned when width >= height or effective DPI >= threshold
  - Multiple strips returned when height > width and effective DPI < threshold
  - Each strip has width as the long edge (square or wider)
  - Strips overlap by ~15% of strip height
  - All returned items are valid PNG bytes with media_type "image/png"


---

### Task 2.1.3: `compute_recrop_bbox()`

- **Description**: Convert re-crop percentage coordinates (0–100, relative to the
  full original crop region) to absolute PDF points.

- **Files to modify**:
  - `src/zotero_chunk_rag/feature_extraction/vision_extract.py` — add function

- **Function signature**:
  ```python
  def compute_recrop_bbox(
      original_bbox: tuple[float, float, float, float],
      bbox_pct: list[float],
  ) -> tuple[float, float, float, float]:
      """Convert re-crop percentages to absolute PDF coordinates.

      Args:
          original_bbox: The original crop region (x0, y0, x1, y1) in PDF points.
          bbox_pct: [x0_pct, y0_pct, x1_pct, y1_pct] where each value is 0-100,
              relative to the original crop dimensions.

      Returns:
          Absolute (x0, y0, x1, y1) in PDF points, clamped to original bbox.
      """
  ```

- **Logic**:
  ```python
  ox0, oy0, ox1, oy1 = original_bbox
  w, h = ox1 - ox0, oy1 - oy0
  x0 = ox0 + clamp(bbox_pct[0], 0, 100) / 100 * w
  y0 = oy0 + clamp(bbox_pct[1], 0, 100) / 100 * h
  x1 = ox0 + clamp(bbox_pct[2], 0, 100) / 100 * w
  y1 = oy0 + clamp(bbox_pct[3], 0, 100) / 100 * h
  ```

- **Tests**:
  - `test_vision_extract.py::TestComputeRecropBbox::test_full_region`
    — `bbox_pct = [0, 0, 100, 100]`, original = (100, 200, 700, 1000).
    Assert: result == (100.0, 200.0, 700.0, 1000.0).
  - `test_vision_extract.py::TestComputeRecropBbox::test_center_quarter`
    — `bbox_pct = [25, 25, 75, 75]`, original = (0, 0, 600, 800).
    Assert: result == (150.0, 200.0, 450.0, 600.0).
  - `test_vision_extract.py::TestComputeRecropBbox::test_clamped`
    — `bbox_pct = [-10, 0, 110, 100]`. Assert: x0 clamped to original x0,
    x1 clamped to original x1.

- **Acceptance criteria**:
  - Percentages correctly converted to absolute coordinates within original bbox
  - Out-of-range percentages clamped to [0, 100]


---

### Task 2.1.4: Delete `render_table_png()` and fix imports

- **Description**: Delete the old single-image renderer. Remove its import from
  `vision_api.py`. The `_prepare_table()` method in `vision_api.py` will be
  rewritten in Step 3; it references the deleted function but is never called
  in the current stubbed state.

- **Files to modify**:
  - `src/zotero_chunk_rag/feature_extraction/vision_extract.py` — delete
    `render_table_png()` function (lines 386–418)
  - `src/zotero_chunk_rag/feature_extraction/vision_api.py` — remove
    `render_table_png` from the import list (line 28)

- **Tests**:
  - `test_vision_extract.py::TestDeletedRenderTablePng::test_not_importable`
    — Assert: `from zotero_chunk_rag.feature_extraction.vision_extract import render_table_png`
    raises `ImportError`.

- **Acceptance criteria**:
  - `render_table_png` no longer exists in `vision_extract.py`
  - `render_table_png` removed from `vision_api.py` import list

---

## Wave 2.2: Prompt and response parsing

### Task 2.2.1: `VISION_FIRST_SYSTEM` prompt constant

- **Description**: Static single-agent system prompt for table transcription.
  Includes all instructions regardless of whether the table uses multi-strip
  (inert instructions when single image — maximizes cache hit rate since all
  tables in a batch share the same system prompt).

- **Files to modify**:
  - `src/zotero_chunk_rag/feature_extraction/vision_extract.py` — add
    `VISION_FIRST_SYSTEM` constant

- **Structure**: Build by concatenation: `VISION_FIRST_SYSTEM = _PROMPT_BODY + "\n\n" + EXTRACTION_EXAMPLES`

  `_PROMPT_BODY` sections (in order):

  | # | Section | Content summary |
  |---|---------|----------------|
  | 1 | Role | "You are a table transcription agent. Given PNG image(s) of a table region from an academic paper, plus raw text extracted from the PDF text layer, extract the table into structured JSON." |
  | 2 | Input format | You receive: 1+ PNG images (may be overlapping vertical strips of the same table, ordered top-to-bottom, with ~15% overlap — deduplicate rows near strip boundaries); raw text from PDF text layer (use to verify numbers/text, but trust image for structure, layout, special characters); caption text that triggered this crop. |
  | 3 | Caption verification | Read the actual caption from the image. The provided caption was extracted from the PDF text layer and may be garbled or incomplete. Return the full corrected caption in `caption`. Return just the label portion (e.g. "Table 1") in `table_label`. If no caption is visible in the image, return `table_label: null` and `caption: ""`. |
  | 4 | Formatting standards | (Adapted from old SHARED_SYSTEM Section 2) Significance markers as LaTeX superscripts `^{*}`, `^{**}`, `^{***}`; Unicode minus U+2212 for negative numbers; multi-level headers flattened with " / "; inline section headers get own row with "" in data columns; standard errors in parentheses merged into coefficient row with `" \n "`; confidence intervals preserved with brackets; comma-separated thousands preserved; empty cells as ""; R², β etc. as LaTeX `R^{2}`, `\beta`. |
  | 5 | Pitfall warnings | (Adapted from old Section 3) Do NOT split columns on spaces in data; do NOT split slash-separated ratios; do NOT drop columns with blank headers; do NOT expand abbreviations; row count == data rows (exclude header); every row must have exactly N cells where N == len(headers). |
  | 6 | Re-crop | If the table extends beyond the crop or the crop includes too much non-table content, set `recrop.needed = true` and provide `recrop.bbox_pct` as `[x0_pct, y0_pct, x1_pct, y1_pct]` (0–100) relative to the full visible region (all strips combined). If crop is adequate, set `recrop.needed = false` and omit `bbox_pct`. |
  | 7 | Output schema | Exact JSON schema (see below) |

  **Output schema (in the prompt)**:
  ```json
  {
    "table_label": "<'Table N' or null if no label visible>",
    "caption": "<full caption text as read from image, or empty string>",
    "is_incomplete": false,
    "incomplete_reason": "",
    "headers": ["col1", "col2", "..."],
    "rows": [["r1c1", "r1c2", "..."], ["..."]],
    "footnotes": "<footnote text below the table, or empty string>",
    "recrop": {
      "needed": false,
      "bbox_pct": [0, 0, 100, 100]
    }
  }
  ```

- **Minimum token target**: The system prompt must be at least 2,048 tokens
  (Haiku 4.5 cache minimum). With examples A–F included, the total should
  be ~4,000–5,000 tokens. No artificial padding needed.

- **Tests**:
  - `test_vision_extract.py::TestVisionFirstSystem::test_prompt_is_string`
    — Assert: `VISION_FIRST_SYSTEM` is a non-empty string.
  - `test_vision_extract.py::TestVisionFirstSystem::test_contains_key_sections`
    — Assert: prompt contains "table transcription", "Raw extracted text" or
    "raw text", "re-crop" or "recrop", "bbox_pct", "table_label", "caption",
    "footnotes", "Worked Examples", "Example A".
  - `test_vision_extract.py::TestVisionFirstSystem::test_no_multi_agent_references`
    — Assert: prompt does NOT contain "VERIFIER", "SYNTHESIZER", "corrections",
    "Y_VERIFIER", "X_VERIFIER" (no leftovers from deleted 4-agent prompt).
  - `test_vision_extract.py::TestVisionFirstSystem::test_minimum_length`
    — Assert: `len(VISION_FIRST_SYSTEM) > 8000` (rough char proxy for >2048 tokens).

- **Acceptance criteria**:
  - Static string constant (not dynamically built per-table)
  - Includes all 7 sections + worked examples
  - Contains caption correction instructions
  - Contains re-crop instructions
  - Contains multi-strip deduplication instructions
  - No references to the deleted multi-agent pipeline


---

### Task 2.2.2: Update `AgentResponse` dataclass

- **Description**: Add `caption`, `recrop_needed`, and `recrop_bbox_pct` fields
  to `AgentResponse`.

- **Files to modify**:
  - `src/zotero_chunk_rag/feature_extraction/vision_extract.py` — modify
    `AgentResponse` dataclass

- **Updated dataclass**:
  ```python
  @dataclass
  class AgentResponse:
      """Parsed output from a vision transcription agent."""

      headers: list[str]
      rows: list[list[str]]
      footnotes: str
      table_label: str | None        # "Table 1", "Table A.1", etc.
      caption: str                   # Full caption text from image
      is_incomplete: bool            # Table extends beyond crop
      incomplete_reason: str         # Which edge(s) are cut off
      raw_shape: tuple[int, int]     # (num_data_rows, num_cols)
      parse_success: bool            # Whether JSON parsing succeeded
      raw_response: str              # Original response text (for debug DB)
      recrop_needed: bool            # Model requests a tighter crop
      recrop_bbox_pct: list[float] | None  # [x0, y0, x1, y1] 0-100 pct
  ```

- **Tests**:
  - `test_vision_extract.py::TestAgentResponse::test_new_fields_exist`
    — Construct an `AgentResponse` with all fields including new ones.
    Assert: `response.caption == "Table 1. Demographics"`,
    `response.recrop_needed == True`,
    `response.recrop_bbox_pct == [10, 5, 90, 95]`.

- **Acceptance criteria**:
  - Three new fields added: `caption`, `recrop_needed`, `recrop_bbox_pct`
  - Existing fields unchanged (no renames, no type changes)


---

### Task 2.2.3: Update `parse_agent_response()`

- **Description**: Update the parser to extract `caption`, `recrop` from the
  JSON response. Maintain backward compatibility with old-format responses
  (missing fields get safe defaults).

- **Files to modify**:
  - `src/zotero_chunk_rag/feature_extraction/vision_extract.py` — modify
    `parse_agent_response()` function

- **Changes**:
  1. Parse `caption` from `parsed.get("caption", "")` → `str`
  2. Parse `recrop` dict from `parsed.get("recrop", {})`:
     - `recrop_needed = bool(recrop_dict.get("needed", False))`
     - `recrop_bbox_pct = recrop_dict.get("bbox_pct")` (list or None)
     - Validate `recrop_bbox_pct` is a list of 4 numbers if present
  3. Update the failure sentinel to include new fields with safe defaults:
     `caption=""`, `recrop_needed=False`, `recrop_bbox_pct=None`
  4. Remove parsing of `corrections` field (deleted multi-agent artifact):
     delete the `corrections = parsed.get("corrections", [])` block

- **Tests**:
  - `test_vision_extract.py::TestParseAgentResponse::test_full_new_schema`
    — JSON with all fields including `caption` and `recrop`. Assert: all
    fields correctly parsed; `response.caption == "Table 3. Results by sex"`;
    `response.recrop_needed == False`.
  - `test_vision_extract.py::TestParseAgentResponse::test_recrop_needed`
    — JSON with `"recrop": {"needed": true, "bbox_pct": [10, 5, 95, 90]}`.
    Assert: `response.recrop_needed == True`;
    `response.recrop_bbox_pct == [10, 5, 95, 90]`.
  - `test_vision_extract.py::TestParseAgentResponse::test_missing_new_fields`
    — JSON with only `headers`, `rows`, `table_label` (old format, no
    `caption` or `recrop`). Assert: `response.caption == ""`;
    `response.recrop_needed == False`; `response.recrop_bbox_pct is None`;
    `response.parse_success == True`.
  - `test_vision_extract.py::TestParseAgentResponse::test_parse_failure`
    — Malformed input (not valid JSON). Assert: `response.parse_success == False`;
    `response.caption == ""`; `response.recrop_needed == False`.
  - `test_vision_extract.py::TestParseAgentResponse::test_corrections_field_ignored`
    — JSON with a `"corrections"` field. Assert: no error raised; field is
    silently ignored (not stored in AgentResponse).
  - `test_vision_extract.py::TestParseAgentResponse::test_invalid_recrop_bbox`
    — JSON with `"recrop": {"needed": true, "bbox_pct": "bad"}`. Assert:
    `response.recrop_needed == True`; `response.recrop_bbox_pct is None`
    (invalid bbox_pct treated as absent).

- **Acceptance criteria**:
  - New fields parsed correctly from well-formed JSON
  - Missing fields default safely (caption="", recrop_needed=False, recrop_bbox_pct=None)
  - Invalid recrop bbox_pct does not crash — treated as None
  - Old `corrections` parsing removed


---

### Task 2.2.4: Update `EXTRACTION_EXAMPLES` with `caption` field

- **Description**: Add the `caption` field to each worked example's output JSON.
  The field contains the full caption text visible in the example's image
  description.

- **Files to modify**:
  - `src/zotero_chunk_rag/feature_extraction/vision_extract.py` — modify
    `EXTRACTION_EXAMPLES` constant

- **Changes per example**:

  | Example | `caption` value |
  |---------|----------------|
  | A | `"caption": ""` (no caption shown in example) |
  | B | `"caption": "Table 3. Results by subgroup"` |
  | C | `"caption": ""` (no caption shown) |
  | D | `"caption": "Table 5. Regression results"` |
  | E | `"caption": "Table 4. Health outcomes"` |
  | F | `"caption": "Table 4. Odds ratios for association of age with polyp classification"` |

  Insert `"caption"` after `"table_label"` in each example JSON.

- **Tests**:
  - `test_vision_extract.py::TestExtractionExamples::test_all_examples_have_caption`
    — Parse each JSON block in `EXTRACTION_EXAMPLES`. Assert: every example
    output contains a `"caption"` key.

- **Acceptance criteria**:
  - All 6 examples include the `caption` field
  - Caption values match the visible caption text in each example's image description
  - JSON in examples is valid (parseable)


---

## Agent Execution Rules

### No API calls

Implementation agents MUST NOT make external API calls (Anthropic, Zotero,
or any network request). All code is testable with synthetic data and mock
PyMuPDF page objects.

### Test execution protocol

Tests are run at most TWICE per implementation session:

1. **First run**: Execute `tests/test_feature_extraction/test_vision_extract.py`.
   Record all failures.
2. **Quick fix round**: Fix only mechanical issues (broken imports, missing
   symbols, trivial type errors). No restructuring.
3. **Second run**: Execute again. Record remaining failures.
4. **Report**: Surface all remaining failures to the user. Do not loop.

### No test modification to make tests pass

If a test fails, the agent reports the failure — it does not modify test
assertions.

---

## Acceptance Criteria

1. **Deleted**: `render_table_png` no longer exists in `vision_extract.py`
2. **Prompt**: `VISION_FIRST_SYSTEM` is a static string containing all 7 sections + worked examples, with no multi-agent references
3. **AgentResponse**: has `caption: str`, `recrop_needed: bool`, `recrop_bbox_pct: list[float] | None` fields
4. **parse_agent_response**: handles new fields with safe defaults for missing/invalid values
5. **Rendering**: `render_table_region` returns 1 image for short crops, 2+ overlapping strips for tall crops
6. **Crops**: `compute_all_crops` returns full-width crops bounded by next caption of any type
7. **Recrop**: `compute_recrop_bbox` correctly converts 0–100 percentages to absolute PDF coordinates
8. **Examples**: all 6 worked examples include `caption` field
