# Phase B6: Production Integration

## Overview

Wire PaddleOCR extraction into the production pipeline as an alternative to
vision API extraction. The Indexer reads configuration to select the
extraction mode and passes the appropriate engine to `extract_document()`.

---

## Wave 1: Extract Document Integration

### Task 1.1: Add paddle_engine parameter to extract_document()

- **Description**: Add a `paddle_engine` parameter to `extract_document()`.
  When provided (and `vision_api` is `None`), use PaddleOCR for table
  extraction. The paddle path is synchronous — no pending/resolve flow
  needed since inference is local.
- **Files to modify**:
  - `src/zotero_chunk_rag/pdf_processor.py`:
    - Add parameter `paddle_engine: "PaddleEngine | None" = None`
    - When `paddle_engine is not None` and `vision_api is None`:
      1. Call `paddle_engine.extract_tables(pdf_path)` → `list[RawPaddleTable]`
      2. Build `captions_by_page` from already-detected captions (the
         `find_all_captions()` call already runs per page in the existing
         extraction loop)
      3. Build `page_rects` from PyMuPDF `page.rect` per page
      4. Call `match_tables_to_captions(raw_tables, captions_by_page,
         page_rects)` → `list[MatchedPaddleTable]`
      5. Convert each `MatchedPaddleTable` → `ExtractedTable`:
         - `page_num` from matched table
         - `table_index` from enumeration within page
         - `bbox` converted from pixel to PDF points using
           `page_rect` and `page_size`:
           `x_pt = x_px * (page_width_pt / page_width_px)`
         - `headers`, `rows` passed through `clean_cells()`
         - `caption` from `MatchedPaddleTable.caption`
         - `footnotes` from `MatchedPaddleTable.footnotes`
         - `extraction_strategy` = `MatchedPaddleTable.engine_name`
         - `caption_position` = `"above"` (paddle matching uses above-only
           strategy)
         - `artifact_type` = `None` (all paddle tables treated as real data)
      6. Populate `DocumentExtraction.tables` directly
      7. No `pending_vision` set (synchronous path)
    - When `vision_api is not None`: existing behavior (unchanged)
    - When both `None`: `tables = []` (existing fallback)
    - When both provided: `vision_api` takes precedence (paddle ignored)
- **Tests**:
  - `tests/test_paddle_extract.py::TestExtractDocumentPaddle::test_paddle_produces_tables` —
    mock `PaddleEngine.extract_tables()` to return 2 `RawPaddleTable`s,
    mock `find_all_captions()` to return matching captions; call
    `extract_document(pdf_path, paddle_engine=mock_engine)`; assert
    result has 2 `ExtractedTable`s with correct headers and rows
  - `tests/test_paddle_extract.py::TestExtractDocumentPaddle::test_clean_cells_applied` —
    mock engine returns rows with ligatures (`"ﬁ"`) and extra whitespace;
    assert `ExtractedTable.rows` have cleaned values (`"fi"`, normalized
    spaces)
  - `tests/test_paddle_extract.py::TestExtractDocumentPaddle::test_bbox_conversion` —
    mock engine returns pixel bbox `(100, 200, 500, 800)` on `(1000, 1400)`
    page; page rect is `(0, 0, 595, 842)`; assert `ExtractedTable.bbox`
    is approximately `(59.5, 120.3, 297.5, 481.1)` (within tolerance)
  - `tests/test_paddle_extract.py::TestExtractDocumentPaddle::test_no_engines_no_tables` —
    `extract_document(path)` with neither engine → `tables == []`
  - `tests/test_paddle_extract.py::TestExtractDocumentPaddle::test_vision_takes_precedence` —
    both `vision_api` and `paddle_engine` provided → `pending_vision`
    set (vision path), paddle not called
- **Acceptance criteria**:
  - `extract_document(pdf_path, paddle_engine=engine)` returns
    `DocumentExtraction` with populated `tables`
  - `clean_cells()` applied to all PaddleOCR output
  - Bounding boxes correctly converted from pixel space to PDF points
  - Caption text from matching populates `ExtractedTable.caption`
  - Orphan tables have `ExtractedTable.caption = None`
  - `extraction_strategy` set to engine name for each table
  - Existing vision path completely unchanged

---

## Wave 2: Config & Indexer Routing

### Task 2.1: Add `vision_api` config field and route in Indexer

- **Description**: Add a single `vision_api` field to `Config` that selects
  the extraction engine. The Indexer reads `config.vision_api` to create the
  appropriate engine. Supported values: `"anthropic"`, `"paddle_v3"`,
  `"paddle_vl"`, `"none"`. This replaces the current hard-coded
  `ANTHROPIC_API_KEY` check in `Indexer.__init__()`.
- **Files to modify**:
  - `src/zotero_chunk_rag/config.py`:
    - Add field `vision_api: str` (default `"anthropic"` for backward
      compatibility)
    - Add to `_DEFAULTS` dict and JSON parsing logic so it reads from
      config files
  - `src/zotero_chunk_rag/indexer.py`:
    - Replace `ANTHROPIC_API_KEY`-based engine creation in `__init__()`:
      - `config.vision_api == "anthropic"`: create `VisionAPI` from
        `ANTHROPIC_API_KEY` env var (existing behavior); if key missing,
        log warning and set `self._vision_api = None`
      - `config.vision_api == "paddle_v3"`: import `get_engine` from
        `feature_extraction.paddle_extract`, create
        `self._paddle_engine = get_engine("pp_structure_v3")`, set
        `self._vision_api = None`
      - `config.vision_api == "paddle_vl"`: same pattern, call
        `get_engine("paddleocr_vl_1.5")`
      - `config.vision_api == "none"`: both engines `None` (text-only
        extraction)
      - Any other value: raise `ValueError`
    - In `index_all()`:
      - When paddle mode: pass `paddle_engine=self._paddle_engine` to
        each `extract_document()` call; skip `resolve_pending_vision()`
        entirely
      - When vision mode: existing flow unchanged
    - In `_index_document_detailed()`: same routing logic — pass
      `paddle_engine=self._paddle_engine` to `extract_document()`, skip
      `resolve_pending_vision()` when in paddle mode
  - `config.example.json` — add `"vision_api": "anthropic"`
- **Tests**:
  - `tests/test_paddle_extract.py::TestIndexerPaddle::test_paddle_v3_creates_engine` —
    mock `get_engine`, create Indexer with config where
    `vision_api="paddle_v3"`, assert `get_engine` called with
    `"pp_structure_v3"`
  - `tests/test_paddle_extract.py::TestIndexerPaddle::test_paddle_vl_creates_engine` —
    mock `get_engine`, create Indexer with config where
    `vision_api="paddle_vl"`, assert `get_engine` called with
    `"paddleocr_vl_1.5"`
  - `tests/test_paddle_extract.py::TestIndexerPaddle::test_anthropic_mode_unchanged` —
    config with `vision_api="anthropic"` and `ANTHROPIC_API_KEY` set →
    `self._vision_api` is `VisionAPI` instance, `self._paddle_engine` is
    `None`
  - `tests/test_paddle_extract.py::TestIndexerPaddle::test_none_mode` —
    config with `vision_api="none"` → both engines `None`
  - `tests/test_paddle_extract.py::TestIndexerPaddle::test_invalid_mode_raises` —
    config with `vision_api="invalid"` raises `ValueError` with message
    containing `"invalid"`
  - `tests/test_paddle_extract.py::TestIndexerPaddle::test_paddle_skips_vision_resolve` —
    mock extraction flow, assert `resolve_pending_vision` never called
    when `vision_api="paddle_v3"`
- **Acceptance criteria**:
  - `vision_api="paddle_v3"` → PP-StructureV3 extraction, no API key needed
  - `vision_api="paddle_vl"` → PaddleOCR-VL-1.5 extraction, no API key
    needed
  - `vision_api="anthropic"` → existing VisionAPI path (fully backward
    compatible)
  - `vision_api="none"` → no table extraction at all
  - Invalid value raises `ValueError` with clear message
  - `resolve_pending_vision()` skipped entirely in paddle modes
  - Both `index_all()` and `_index_document_detailed()` route correctly
  - `Config` reads `vision_api` from JSON config files with default
    `"anthropic"`
