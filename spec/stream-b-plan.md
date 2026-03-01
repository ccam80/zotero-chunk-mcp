# Stream B: PaddleOCR Local Document Extraction

## Status: Specced (2026-03-02)

## Origin

Extracted from the original `spec/plan.md` (git ref `41df17b^`). Stream B was
defined as a parallel evaluation track alongside the vision-first pipeline
(Stream A). This document captures all B-related content for independent
plan-spec development.

---

## Goal

Evaluate PaddleOCR PP-StructureV3 and PaddleOCR-VL-1.5 as local, zero-API-cost
alternatives to the Haiku 4.5 vision pipeline. Both engines supported behind a
common `PaddleEngine` protocol with string-based factory selection.

---

## Architecture (decided 2026-03-02)

### Extraction strategy: PaddleOCR detects, captions validate (Option C)

PaddleOCR performs its own table detection via layout analysis. Our
`find_all_captions()` validates, filters, and enriches results with structured
caption text and table numbers for GT evaluation.

```
Stream A: Caption Detection → Crop → PNG → Vision API (Haiku 4.5) → ExtractedTable
Stream B: PaddleOCR (full PDF) → table regions → Caption Matching → ExtractedTable
```

PaddleOCR opens PDFs directly — no pre-rendering by us.

### Engine abstraction

```
feature_extraction/
  paddle_extract.py          # PaddleEngine protocol, RawPaddleTable, MatchedPaddleTable,
                              # get_engine() factory, match_tables_to_captions()
  paddle_engines/
    __init__.py              # re-exports
    pp_structure.py          # PP-StructureV3 engine (HTML parser internal)
    paddleocr_vl.py          # PaddleOCR-VL-1.5 engine (markdown parser internal)
```

- `PaddleEngine` is a `typing.Protocol` with `extract_tables(pdf_path) -> list[RawPaddleTable]`
- `get_engine("pp_structure_v3")` / `get_engine("paddleocr_vl_1.5")` — string factory
- Each engine parses its own output format internally (HTML for V3, markdown for VL)

### Hard dependencies

PaddleOCR packages are main dependencies (not optional extras). Module-level
imports throughout — no lazy loading. GPU required (including for unit tests).

```toml
# pyproject.toml [project.dependencies]
paddlepaddle-gpu>=3.0.0
paddleocr>=3.0.0
```

### Configuration

Single config field `vision_api` selects the extraction engine:

| Value | Engine | Requires |
|-------|--------|----------|
| `"anthropic"` | Haiku 4.5 via Batch API | `ANTHROPIC_API_KEY` env var |
| `"paddle_v3"` | PP-StructureV3 | GPU + PaddleOCR |
| `"paddle_vl"` | PaddleOCR-VL-1.5 | GPU + PaddleOCR |
| `"none"` | No table extraction | — |

Indexer reads `config.vision_api` and creates the appropriate engine.
`extract_document()` accepts either `vision_api` or `paddle_engine`
parameter — the Indexer decides which to pass.

### Independence constraint

Stream B's `paddle_extract.py` imports only from `captions.py` (shared),
`models.py` (shared), and `postprocessors/cell_cleaning.py` (shared). No
imports from `vision_extract.py` or `vision_api.py`. Stream A works without
PaddleOCR code changes.

### PaddleOCR MCP server

Used by agents during development and testing to explore PaddleOCR outputs.
NOT used in production code — `paddle_extract.py` imports `paddleocr` directly.

### Shared infrastructure

- `feature_extraction/captions.py` — caption detection (`find_all_captions()`)
- `feature_extraction/ground_truth.py` — GT comparison framework
- `feature_extraction/postprocessors/cell_cleaning.py` — `clean_cells()`
- `feature_extraction/debug_db.py` — debug database (extended with paddle tables)
- `tests/ground_truth.db` — 44 verified ground truth tables across 10 papers
- `models.py` — `ExtractedTable`, `DocumentExtraction` dataclasses

---

## Implementation Steps

### B1–B2: Engine Foundation (merged)

Install dependencies, create engine protocol + data models + factory, implement
both engines with their output parsers. Original B2 (HTML parser) absorbed —
parsers live inside engine files.

**Spec**: `spec/b1-b2-engine-foundation.md`

### B3: Caption Matching

`match_tables_to_captions()` in `paddle_extract.py`. Normalizes pixel-space
PaddleOCR bboxes and PDF-point caption bboxes to [0,1] range for matching.
Greedy top-to-bottom assignment, unmatched tables flagged as orphans.

**Spec**: `spec/b3-caption-matching.md`

### B4: Evaluation

Unit test suite (`tests/test_paddle_extract.py`, 30+ tests) covering parsers,
matching, factory. Stress test integration: paddle extraction runs in a
background thread during vision batch API wait time, results written to debug
DB in `paddle_results` and `paddle_gt_diffs` tables.

**Spec**: `spec/b4-evaluation.md`

### B5: Comparative Report

New "Paddle Extraction Report" section in `STRESS_TEST_REPORT.md` (not a
separate file). Per-table accuracy table, summary stats, side-by-side
comparison with vision results when both exist.

**Spec**: `spec/b5-report-integration.md`

### B6: Production Integration

`extract_document()` gets `paddle_engine` parameter. Indexer reads
`config.vision_api` (`"anthropic"` / `"paddle_v3"` / `"paddle_vl"` / `"none"`)
and creates the appropriate engine. Indexer decides mode —
`extract_document()` doesn't know about modes.

**Spec**: `spec/b6-production-integration.md`

---

## Implementation Order

```
B1–B2 (engine foundation) → B3 (caption matching) → B4 (evaluation) → B5 (report) → B6 (integration)
```

B1–B4 are strictly sequential. B5 requires B4 results; vision results needed
only for the comparison section (graceful when absent). B6 depends on all prior
phases.

---

## Dependencies on Stream A

| Stream B Step | Stream A Dependency | Hard/Soft |
|---------------|-------------------|-----------|
| B1–B2 | None | — |
| B3 | Step 1 (caption fix) | Soft — works without, undercounts |
| B4 | None (uses GT directly) | — |
| B5 | Step 5 (vision eval results) | Soft — comparison section omitted if absent |
| B6 | Steps 1–4 complete | Hard — integration requires working vision path |

---

## Success Criteria

- PaddleOCR installs and runs on Windows with GPU
- Both engines (PP-StructureV3, PaddleOCR-VL-1.5) produce valid
  `RawPaddleTable` output from real PDFs
- Unit tests pass (30+ tests, synthetic inputs)
- Stress test paddle section runs without errors on 10-paper corpus
- GT comparison covers all 44 tables
- Comparative report generated in `STRESS_TEST_REPORT.md`
- If integrated: `vision_api="paddle_v3"` or `"paddle_vl"` produces valid
  `ExtractedTable` output, selectable via `config.vision_api`

---

## Agent Execution Rules

Inherited from the main plan:

### No API calls

Implementation agents MUST NOT make external API calls (Anthropic, Zotero,
or any network request). All code that calls external APIs must be tested
with mocks or stubs, never live services.

### Test execution protocol

Tests are run at most TWICE per implementation session:

1. **First run**: Execute relevant tests. Record all failures.
2. **Quick fix round**: Fix only obvious mechanical issues (broken imports,
   missing symbols, trivial type errors). No restructuring.
3. **Second run**: Execute again. Record remaining failures.
4. **Report**: Surface all remaining failures to the user. Do not loop.

### No test modification to make tests pass

If a test fails, the agent reports the failure — it does not modify test
assertions.
