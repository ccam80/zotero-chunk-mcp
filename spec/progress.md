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

## Task b4-1.1: Create/consolidate tests/test_paddle_extract.py
- **Status**: partial
- **Agent**: implementer
- **Files created**: none (file already existed; fully rewritten)
- **Files modified**: `tests/test_paddle_extract.py`
- **Tests**: 28/30 passing

### What was done
Consolidated all B1–B3 unit tests into `tests/test_paddle_extract.py` with 30 tests across 7 classes:
- `TestImports` (3): all pass — `import paddleocr`, `PPStructureV3`, `PaddleOCRVL` all importable
- `TestRawPaddleTable` (1): passes
- `TestEngineFactory` (3): 1 pass (`test_unknown_raises`), 2 fail (see below)
- `TestHTMLParser` (8): all pass
- `TestMarkdownParser` (7): all pass
- `TestMatchedPaddleTable` (2): all pass
- `TestCaptionMatching` (6): all pass

Also installed `paddlex[ocr]==3.4.2` (was missing, needed by `PaddleOCRVLEngine.__init__`).

### Remaining failures (2/30) — environment issue, not code issue
`TestEngineFactory::test_pp_structure_v3` and `TestEngineFactory::test_paddleocr_vl` both fail with:
```
OSError: [WinError 127] The specified procedure could not be found.
Error loading "paddle\libs\phi.dll" or one of its dependencies.
```
This is `paddlepaddle-gpu`'s native C++ inference library failing to load. Root cause: CUDA/GPU drivers or Visual C++ redistributables required by PaddlePaddle-GPU are not properly installed on this Windows machine. The test assertions are correct (they call `get_engine()` which calls `PPStructureV3(device="gpu")` and `PaddleOCRVL(pipeline_version="v1.5", device="gpu:0")` — both trigger `paddle.__init__` which loads `phi.dll`). The tests cannot pass until the CUDA environment is functional. No code changes needed.

## Task b4-3.1: Add paddle extraction to stress test flow
- **Status**: complete
- **Agent**: implementer
- **Files created**: none
- **Files modified**: tests/stress_test_real_library.py
- **Tests**: stress test assertions (not pytest; not run — requires live Zotero library)
- **Changes**:
  - Added imports: `threading`, `find_all_captions`, `write_paddle_result`, `write_paddle_gt_diff`, `MatchedPaddleTable`, `get_engine`, `match_tables_to_captions`
  - Added `_extract_with_paddle(corpus_items, engine_name)` function before `run_stress_test()`
  - Added `_test_paddle_extraction(paddle_results, db_path, engine_name)` function before `write_debug_database()`
  - Restructured extraction phases in `run_stress_test()`:
    - Phase 2b: start `_paddle_worker` in `threading.Thread`
    - Phase 2c: `resolve_pending_vision()` (main thread, blocking)
    - Phase 2d: `paddle_thread.join()` with exception surfacing
    - Phase 2e: index documents (unchanged)
  - `run_stress_test()` now returns `(report, extractions, paddle_results)`
  - `__main__` block unpacks all three; calls `_test_paddle_extraction` after `write_debug_database` when paddle results are available
  - Paddle assertions added: `paddle-orphan-count` (MINOR), `paddle-gt-cell-accuracy` (MAJOR), `paddle-gt-accuracy-recorded` (MINOR), `paddle-gt-coverage` (MAJOR)
  - Results written to `paddle_results` and `paddle_gt_diffs` DB tables via `write_paddle_result`/`write_paddle_gt_diff`
