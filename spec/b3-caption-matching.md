# Phase B3: Caption Matching

## Overview

Match PaddleOCR-detected table regions to caption detections from
`find_all_captions()`. PaddleOCR detects tables independently via its own
layout analysis; captions validate, filter, and enrich the results with
structured caption text and table numbers for GT evaluation.

Coordinate systems differ: PaddleOCR returns pixel-space bboxes, captions
use PDF-point bboxes. Both are normalized to [0,1] fractions of page
dimensions for matching.

### Known limitation: above-only matching

The matching algorithm assigns captions that appear **above** the table's top
edge. Some papers place captions below tables — those tables will be orphaned.
This is acceptable for v1; below-table matching can be added later if orphan
rates are high.

---

## Wave 1: Data Model & Matching Function

### Task 1.1: Add MatchedPaddleTable dataclass

- **Description**: Create a result dataclass that extends `RawPaddleTable`
  fields with caption information and orphan status.
- **Files to modify**:
  - `src/zotero_chunk_rag/feature_extraction/paddle_extract.py` — add:
    - `MatchedPaddleTable` dataclass with fields:
      - All `RawPaddleTable` fields (composed, not inherited)
      - `caption: str | None` — full caption text from `DetectedCaption.text`
      - `caption_number: str | None` — table number from
        `DetectedCaption.number` (e.g., `"1"`, `"A.1"`)
      - `is_orphan: bool` — `True` when no caption matched
- **Tests**:
  - `tests/test_paddle_extract.py::TestMatchedPaddleTable::test_fields` —
    construct with all fields, assert caption and is_orphan accessible
  - `tests/test_paddle_extract.py::TestMatchedPaddleTable::test_orphan_defaults` —
    orphan table has `caption=None`, `caption_number=None`, `is_orphan=True`
- **Acceptance criteria**:
  - `MatchedPaddleTable` is a standalone dataclass (not subclass of
    `RawPaddleTable`) containing all fields needed for downstream conversion
    to `ExtractedTable`

### Task 1.2: Implement match_tables_to_captions()

- **Description**: Match PaddleOCR-detected table regions to captions by
  normalized vertical proximity. For each page, normalize both coordinate
  systems to [0,1] range, then assign each table to the closest caption
  above it. Greedy assignment prevents double-matching.
- **Files to modify**:
  - `src/zotero_chunk_rag/feature_extraction/paddle_extract.py` — add:
    - `match_tables_to_captions(raw_tables, captions_by_page, page_rects)`
      - Parameters:
        - `raw_tables: list[RawPaddleTable]`
        - `captions_by_page: dict[int, list[DetectedCaption]]` — from
          `find_all_captions()`, keyed by 1-indexed page number
        - `page_rects: dict[int, tuple[float, float, float, float]]` —
          PDF page rect per page (from `page.rect`), keyed by 1-indexed
          page number
      - Returns: `list[MatchedPaddleTable]`
      - Algorithm:
        1. Group `raw_tables` by `page_num`
        2. For each page, normalize table bboxes:
           `y_norm = y_px / page_size[1]` (pixel height)
        3. Normalize caption bboxes:
           `y_norm = (y_pt - page_rect[1]) / (page_rect[3] - page_rect[1])`
        4. For each table (sorted top-to-bottom by normalized y0):
           find the caption whose normalized `y_center` is closest to and
           above the table's normalized top edge (`y0_norm`)
        5. Matched caption removed from candidate pool (greedy, no
           double-matching)
        6. Unmatched tables → `is_orphan=True`
- **Tests**:
  - `tests/test_paddle_extract.py::TestCaptionMatching::test_single_match` —
    one table at pixel y=400 on 1000px page, one caption at PDF y=28.8 on
    72pt page → both normalize to ~0.4, matched
  - `tests/test_paddle_extract.py::TestCaptionMatching::test_multiple_tables` —
    3 tables at pixel y=200, 500, 800 on 1000px page; 3 captions at
    proportional PDF positions → correct 1:1 assignment, each table gets
    nearest-above caption
  - `tests/test_paddle_extract.py::TestCaptionMatching::test_orphan` —
    table at pixel y=100 with no caption above it (caption is below at
    y=900) → `is_orphan=True`
  - `tests/test_paddle_extract.py::TestCaptionMatching::test_no_double_match` —
    2 tables close together, 1 caption → first table gets caption, second
    is orphan
  - `tests/test_paddle_extract.py::TestCaptionMatching::test_multi_page` —
    tables on pages 1 and 3, captions on pages 1 and 3 → matching is
    per-page, no cross-page matching
  - `tests/test_paddle_extract.py::TestCaptionMatching::test_empty_inputs` —
    empty `raw_tables` → empty result; tables with no captions on their
    page → all orphans
- **Acceptance criteria**:
  - Matching uses normalized [0,1] y-coordinates throughout
  - Greedy top-to-bottom assignment: closest caption above table's top edge
  - Each caption matched to at most one table
  - Tables on pages with no captions are all orphans
  - Function is pure (no side effects, no PaddleOCR calls)
  - Callers must convert PyMuPDF `page.rect` (a `Rect` object) to
    `tuple[float, float, float, float]` before passing as `page_rects`
- **Files to modify** (additional):
  - `src/zotero_chunk_rag/feature_extraction/__init__.py` — add exports:
    `MatchedPaddleTable`, `match_tables_to_captions`
