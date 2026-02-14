# Missed Cases from Stress Test + Matching Audit

Every known table/figure extraction failure with root cause and fix status.
Updated: 2026-02-11

---

## Architectural Flaws — Status

| # | Flaw | Status | Impact |
|---|------|--------|--------|
| A1 | Positional-index caption matching | **FIXED** — Number-ordered matching with y-fallback | fortune, roland, yang |
| A2 | `^`-anchored regex misses mid-block captions | **FIXED** — Line-by-line scan of first 5 lines | huang (4 figs) |
| A3 | No appendix/supplementary numbering | **FIXED** — Extended to `[A-Z].\d+`, `S\d+` | active-inference |
| A4 | Phantom tables pass filters | **FIXED** — Multi-signal: 1-row, page-1, back-matter, >50 row | 5 papers |
| A5 | Lineless definition-list tables | **FIXED** — Prose table extraction from caption + text blocks | friston |
| A6 | Multi-figure pages with single box | **PARTIALLY FIXED** — Phase 1 split with x-overlap guard, Phase 2 height guard | roland, yang |

---

## Remaining Issues

### Huang EMD (D grade) — XIAINRVS

- **1 table, 0 captions**: `find_tables()` detects a structure on an early page
  but no "Table N" caption exists near it. Huang has no real data tables —
  only embedded tabular content in figures.
- **84 figures detected**: Many are legitimate (96-page paper with dense figures).
  The D grade comes entirely from `table_captions_found=0, tables_found=1`.

### Abstract detection misses (6/10 papers)

active-inference-tutorial, huang, hallett, helm, friston, fortune.
The 3-tier detector (keyword → TOC → font-based) misses these because:
- No "Abstract" heading in the text
- Font-based detection requires exactly 1 candidate block

### Introduction section detection gaps (4/10 papers)

hallett, laird, helm, reyes. These papers don't use a standard
"Introduction" heading or it's not in the TOC.

---

## Fixes Implemented (commit reference)

1. **A1**: `_match_by_proximity()` in `_figure_extraction.py` — number-ordered
   matching replaces positional index. Falls back to y-order when no numbers.
2. **A2**: `_scan_lines_for_caption()` — scans first 5 lines of multi-line blocks
   for caption patterns (catches axis-label-merged captions).
3. **A3**: `_NUM_GROUP` constant in both `_figure_extraction.py` and
   `pdf_processor.py` — 9 regex patterns extended.
4. **A4**: Multi-signal phantom filter in `_extract_tables_native()` — rejects
   1-row headerless, page-1 uncaptioned, final-2-page uncaptioned, >50 row.
5. **A5**: `_extract_prose_tables()` + `_collect_prose_table_content()` in
   `pdf_processor.py` — finds orphan "Table N" captions, collects text blocks
   below as table content.
6. **A6**: Phase 1 split with x-overlap check (prevents 2-column false splits),
   Phase 2 synthetic rects with height guard (250pt per expected figure).
7. **Gap-fill**: String-based caption number keys (handles appendix "A.1" etc.).
