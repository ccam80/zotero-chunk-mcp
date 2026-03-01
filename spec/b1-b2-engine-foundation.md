# Phase B1–B2: Engine Foundation

## Overview

Install PaddleOCR as a hard dependency, create the engine abstraction protocol,
implement PP-StructureV3 and PaddleOCR-VL-1.5 engines with their respective
output parsers (HTML and markdown), and provide a string-based factory function.

B2 (HTML-to-structured-data converter) from the original plan is absorbed into
this phase — parsers live inside their respective engine files.

---

## Wave 1: Dependencies & Core Abstractions

### Task 1.1: Add PaddleOCR dependencies to pyproject.toml

- **Description**: Add PaddleOCR packages as hard (non-optional) dependencies.
  GPU-only — no CPU variant.
- **Files to modify**:
  - `pyproject.toml` — Add to `[project.dependencies]`:
    - `paddlepaddle-gpu>=3.0.0`
    - `paddleocr>=3.0.0`
- **Tests**:
  - `tests/test_paddle_extract.py::TestImports::test_paddleocr_importable` —
    assert `import paddleocr` succeeds without error
  - `tests/test_paddle_extract.py::TestImports::test_ppstructurev3_importable` —
    assert `from paddleocr import PPStructureV3` succeeds
  - `tests/test_paddle_extract.py::TestImports::test_paddleocrvl_importable` —
    assert `from paddleocr import PaddleOCRVL` succeeds
- **Acceptance criteria**:
  - `"./.venv/Scripts/python.exe" -m uv pip install -e .` installs PaddleOCR
    and PaddlePaddle GPU packages without errors
  - All three imports succeed in the test environment

### Task 1.2: Create engine protocol and data models

- **Description**: Define the `PaddleEngine` protocol that all engines must
  conform to, the `RawPaddleTable` intermediate dataclass, and the
  `get_engine()` factory function. PaddleOCR opens PDFs directly — no
  pre-rendering.
- **Files to create**:
  - `src/zotero_chunk_rag/feature_extraction/paddle_extract.py`:
    - `PaddleEngine(Protocol)` with method
      `extract_tables(self, pdf_path: Path) -> list[RawPaddleTable]`
    - `RawPaddleTable` dataclass with fields:
      - `page_num: int` (1-indexed)
      - `bbox: tuple[float, float, float, float]` (x0, y0, x1, y1 in pixels)
      - `page_size: tuple[int, int]` (width, height in pixels)
      - `headers: list[str]`
      - `rows: list[list[str]]`
      - `footnotes: str`
      - `engine_name: str`
      - `raw_output: str` (original HTML/markdown for debugging)
    - `get_engine(name: str) -> PaddleEngine` factory — dispatches
      `"pp_structure_v3"` → `PPStructureEngine`,
      `"paddleocr_vl_1.5"` → `PaddleOCRVLEngine`.
      Raises `ValueError` for unknown names.
  - `src/zotero_chunk_rag/feature_extraction/paddle_engines/__init__.py` —
    empty stub initially (re-exports added in Task 2.2 after engine classes
    exist)
- **Files to modify**:
  - `src/zotero_chunk_rag/feature_extraction/__init__.py` — add exports for
    `PaddleEngine`, `RawPaddleTable`, `get_engine`
- **Tests**:
  - `tests/test_paddle_extract.py::TestRawPaddleTable::test_fields_present` —
    construct a `RawPaddleTable` with all fields, assert each is accessible
    and correctly typed
  - `tests/test_paddle_extract.py::TestEngineFactory::test_pp_structure_v3` —
    assert `get_engine("pp_structure_v3")` returns instance satisfying
    `PaddleEngine` protocol (has `extract_tables` method)
  - `tests/test_paddle_extract.py::TestEngineFactory::test_paddleocr_vl` —
    assert `get_engine("paddleocr_vl_1.5")` returns instance satisfying
    `PaddleEngine` protocol
  - `tests/test_paddle_extract.py::TestEngineFactory::test_unknown_raises` —
    assert `get_engine("nonexistent")` raises `ValueError` with message
    containing the invalid name
- **Acceptance criteria**:
  - `PaddleEngine` is a `typing.Protocol` (not ABC) — duck typing, no
    inheritance required
  - `RawPaddleTable` stores pixel-space bounding boxes (engine-native coords)
  - Factory returns fully initialized engine instances (model loading happens
    in `__init__`)
  - Module-level imports — `paddleocr` imported at top of engine files, not
    lazily

---

## Wave 2: Engine Implementations

### Task 2.1: PP-StructureV3 engine with HTML parser

- **Description**: Implement PP-StructureV3 engine. Initializes
  `PPStructureV3(device="gpu", lang="en")`, processes full PDFs, extracts
  table regions from results, parses HTML table output into headers/rows.
- **Files to create**:
  - `src/zotero_chunk_rag/feature_extraction/paddle_engines/pp_structure.py`:
    - `PPStructureEngine` class:
      - `__init__(self)` — creates `PPStructureV3(device="gpu", lang="en")`
      - `extract_tables(self, pdf_path: Path) -> list[RawPaddleTable]` —
        calls `self._pipeline.predict(str(pdf_path))`, iterates per-page
        results, identifies table regions from layout detection, extracts
        HTML from table recognition, parses each via `_parse_html_table()`,
        constructs `RawPaddleTable` per table
    - `_parse_html_table(html: str) -> tuple[list[str], list[list[str]], str]`:
      - Returns `(headers, rows, footnotes)`
      - Header detection: if any `<th>` tags exist, those rows are headers;
        otherwise first `<tr>` row becomes headers
      - `colspan="N"` → cell value repeated N times in that row
      - `rowspan="N"` → cell value copied into the next N-1 rows at that
        column position
      - Text content stripped of HTML tags and whitespace-normalized
      - Footnotes: any text content after the closing `</table>` tag within
        the table region's raw output
- **Tests**:
  - `tests/test_paddle_extract.py::TestHTMLParser::test_simple_table` —
    `<table><tr><td>Name</td><td>Age</td></tr><tr><td>Alice</td><td>30</td></tr></table>`
    → headers=`["Name", "Age"]`, rows=`[["Alice", "30"]]`
  - `tests/test_paddle_extract.py::TestHTMLParser::test_th_headers` —
    `<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>`
    → headers=`["A", "B"]`, rows=`[["1", "2"]]`
  - `tests/test_paddle_extract.py::TestHTMLParser::test_no_th_first_row_fallback` —
    all `<td>` → first row promoted to headers
  - `tests/test_paddle_extract.py::TestHTMLParser::test_colspan` —
    `<td colspan="3">Merged</td>` in a 3-col table → `["Merged", "Merged", "Merged"]`
  - `tests/test_paddle_extract.py::TestHTMLParser::test_rowspan` —
    `<td rowspan="2">Span</td>` → value `"Span"` appears in current row and
    next row at same column index
  - `tests/test_paddle_extract.py::TestHTMLParser::test_nested_tags_stripped` —
    `<td><b>Bold</b> text</td>` → `"Bold text"`
  - `tests/test_paddle_extract.py::TestHTMLParser::test_empty_table` —
    `<table></table>` → headers=`[]`, rows=`[]`, footnotes=`""`
  - `tests/test_paddle_extract.py::TestHTMLParser::test_whitespace_normalization` —
    `<td>  multiple   spaces  </td>` → `"multiple spaces"`
- **Acceptance criteria**:
  - Engine initializes `PPStructureV3` at module load time (hard dependency)
  - Full PDF path passed to PaddleOCR — no pre-rendering
  - Per-page results iterated; each table region produces one `RawPaddleTable`
  - `bbox` and `page_size` sourced from PaddleOCR's layout detection output
  - `engine_name` is always `"pp_structure_v3"`
  - `raw_output` stores the original HTML string before parsing

### Task 2.2: PaddleOCR-VL-1.5 engine with markdown parser

- **Description**: Implement PaddleOCR-VL-1.5 engine. Initializes
  `PaddleOCRVL(pipeline_version="v1.5", device="gpu:0")`, processes full
  PDFs with cross-page table merging, extracts table blocks from
  `parsing_res_list`, parses markdown table output into headers/rows.
- **Files to create**:
  - `src/zotero_chunk_rag/feature_extraction/paddle_engines/paddleocr_vl.py`:
    - `PaddleOCRVLEngine` class:
      - `__init__(self)` — creates
        `PaddleOCRVL(pipeline_version="v1.5", device="gpu:0")`
      - `extract_tables(self, pdf_path: Path) -> list[RawPaddleTable]` —
        calls `self._pipeline.predict(str(pdf_path))`, uses
        `restructure_pages(pages_res, merge_tables=True)`, iterates
        `parsing_res_list` blocks, filters for table blocks
        (`block_label` indicates table), parses markdown via
        `_parse_markdown_table()`, constructs `RawPaddleTable` per block
    - `_parse_markdown_table(md: str) -> tuple[list[str], list[list[str]], str]`:
      - Returns `(headers, rows, footnotes)`
      - First row (before separator `|---|`) is headers
      - Alignment separator row (`|:---|`, `|:---:|`, `|---:|`) stripped
      - Escaped pipes (`\|`) inside cells handled correctly
      - Leading/trailing pipes and whitespace stripped per cell
      - Empty markdown → `([], [], "")`
- **Tests**:
  - `tests/test_paddle_extract.py::TestMarkdownParser::test_simple_table` —
    `"| A | B |\n|---|---|\n| 1 | 2 |"` → headers=`["A", "B"]`,
    rows=`[["1", "2"]]`
  - `tests/test_paddle_extract.py::TestMarkdownParser::test_alignment_stripped` —
    `"| A | B |\n|:---|---:|\n| 1 | 2 |"` → same result, alignment row
    not treated as data
  - `tests/test_paddle_extract.py::TestMarkdownParser::test_escaped_pipes` —
    `"| A |\n|---|\n| val\\|ue |"` → rows=`[["val|ue"]]`
  - `tests/test_paddle_extract.py::TestMarkdownParser::test_whitespace_trimmed` —
    `"|  A  |  B  |\n|---|---|\n|  1  |  2  |"` → `["A", "B"]`, `[["1", "2"]]`
  - `tests/test_paddle_extract.py::TestMarkdownParser::test_empty_string` —
    `""` → headers=`[]`, rows=`[]`, footnotes=`""`
  - `tests/test_paddle_extract.py::TestMarkdownParser::test_no_separator_row` —
    markdown table without `|---|` separator → first row still treated as
    headers (fallback)
  - `tests/test_paddle_extract.py::TestMarkdownParser::test_multirow` —
    3 data rows → `rows` has length 3, each row has correct cell count
- **Files to modify**:
  - `src/zotero_chunk_rag/feature_extraction/paddle_engines/__init__.py` —
    add re-exports: `PPStructureEngine` from `.pp_structure`,
    `PaddleOCRVLEngine` from `.paddleocr_vl`
- **Acceptance criteria**:
  - Engine initializes `PaddleOCRVL` at module load time (hard dependency)
  - Cross-page table merging enabled via `restructure_pages(merge_tables=True)`
  - Table blocks identified by `block_label` from `parsing_res_list`
  - `bbox` sourced from `block_bbox`; `page_size` from page result metadata
  - `engine_name` is always `"paddleocr_vl_1.5"`
  - `raw_output` stores the original markdown string before parsing
  - `paddle_engines/__init__.py` re-exports both engine classes after this
    task completes
