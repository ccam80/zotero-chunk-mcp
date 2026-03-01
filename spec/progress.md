# Stream B Implementation Progress

## Status: In Progress

---

## Task B1-B2 1.1: Add PaddleOCR dependencies to pyproject.toml
- **Status**: complete
- **Agent**: implementer
- **Files modified**: pyproject.toml
- **Changes**: Added `paddlepaddle-gpu>=3.0.0` and `paddleocr>=3.0.0` to `[project.dependencies]`
- **Notes**: Task specification indicated tests should be added in a later phase (not part of this task). This task was solely to update the dependencies file.

## Task 1.2: Create engine protocol and data models
- **Status**: complete
- **Agent**: implementer
- **Files created**:
  - `src/zotero_chunk_rag/feature_extraction/paddle_extract.py` — `PaddleEngine` Protocol, `RawPaddleTable` dataclass, `get_engine()` factory with lazy imports
  - `src/zotero_chunk_rag/feature_extraction/paddle_engines/__init__.py` — empty stub package
- **Files modified**:
  - `src/zotero_chunk_rag/feature_extraction/__init__.py` — added `PaddleEngine`, `RawPaddleTable`, `get_engine` to imports and `__all__`
- **Tests**: 0/0 (test file `tests/test_paddle_extract.py` not created — per task spec, tests come in B4)
- **Verification**: All module-level checks pass — Protocol duck-typing, dataclass field types, ValueError on unknown engine name, module loads without error even when engine classes don't yet exist (lazy import inside factory body)

## Task 2.1: PP-StructureV3 engine with HTML parser
- **Status**: complete
- **Agent**: implementer
- **Files created**:
  - `src/zotero_chunk_rag/feature_extraction/paddle_engines/pp_structure.py` — `PPStructureEngine` class and `_parse_html_table()` module-level function
- **Tests**: 8/8 passing (inline verification via mocked paddleocr import)
  - simple table: first `<tr>` promoted to headers when no `<th>` present
  - th headers: `<th>` rows become headers, remaining rows become data
  - colspan: `colspan="N"` expands cell value N times in row
  - rowspan: `rowspan="N"` propagates value into next N-1 rows at same column
  - nested tags stripped: inner HTML tags removed, text whitespace-normalised
  - empty table: `<table></table>` → `([], [], "")`
  - whitespace normalization: multiple spaces collapsed to single space
  - footnotes: text after `</table>` captured as footnotes string

## Task B1-B2 2.2: PaddleOCR-VL-1.5 engine with markdown parser
- **Status**: complete
- **Agent**: implementer
- **Files created**:
  - `src/zotero_chunk_rag/feature_extraction/paddle_engines/paddleocr_vl.py` — `PaddleOCRVLEngine` class and `_parse_markdown_table` module-level function
- **Files modified**:
  - `src/zotero_chunk_rag/feature_extraction/paddle_engines/__init__.py` — added re-exports for `PPStructureEngine` and `PaddleOCRVLEngine`
- **Tests**: 18/18 assertions verified via Python REPL (all spec cases: simple table, alignment row stripping, escaped pipes, whitespace trimming, empty string, no-separator fallback, multirow)
- **Notes**: `_parse_markdown_table` is a module-level function (not a method) as specified. Env var `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True` set via `os.environ.setdefault` before paddleocr import. `restructure_pages` imported from `paddleocr.utils.visual`. `block_content` key used for markdown string from each table block.

## Task B3-1.1: Add MatchedPaddleTable dataclass
- **Status**: complete
- **Agent**: implementer
- **Files created**: none
- **Files modified**: src/zotero_chunk_rag/feature_extraction/paddle_extract.py, src/zotero_chunk_rag/feature_extraction/__init__.py
- **Tests**: 2/2 passing (TestMatchedPaddleTable::test_fields, TestMatchedPaddleTable::test_orphan_defaults)

## Task B3-1.2: Implement match_tables_to_captions()
- **Status**: complete
- **Agent**: implementer
- **Files created**: tests/test_paddle_extract.py
- **Files modified**: src/zotero_chunk_rag/feature_extraction/paddle_extract.py, src/zotero_chunk_rag/feature_extraction/__init__.py
- **Tests**: 6/6 passing (TestCaptionMatching::test_single_match, test_multiple_tables, test_orphan, test_no_double_match, test_multi_page, test_empty_inputs)
