# Extraction Performance Report

**Test Date**: 2026-02-07
**Test PDFs**: 3 academic papers in `tests/fixtures/papers/`
**Verification**: Manual review of `tests/extraction_output/`

---

## noname1.pdf (single-column review paper)

| Feature | Result | Notes |
|---------|--------|-------|
| Tables | 0/1 | 13 false positives (body text parsed as tables) |
| Table captions | 0/1 | Caption found but table content is garbage |
| Figures | 4/4 found | Captions polluted with body text below |
| Figure images | 3/4 | One figure has black background instead of white |
| Section map | 0/4 | "introduction" applied to entire body (non-standard headings) |

---

## noname2.pdf (single-column benchmark paper)

| Feature | Result | Notes |
|---------|--------|-------|
| Tables | 0/5 | 5 tables missed entirely; 2 false positives (reference list) |
| Table captions | 0/5 | N/A |
| Figures | 1/5 | 4 figures missed |
| Figure captions | 1/1 | Correct for the one detected |
| Section map | 0/5 | "introduction" applied to entire body (non-standard headings) |

---

## noname3.pdf (two-column physiology paper)

| Feature | Result | Notes |
|---------|--------|-------|
| Tables | 3/3 captions | Table content extracted as garbage from body text |
| Figures | 8/10 | 2 missed from adjacent columns |
| Figure captions | 8/10 | 2 have junk from adjacent column text |
| Figure images | 10/10 | All saved correctly |
| Section map | 2/4 | Found methods, results; missed discussion, summary |

---

## Aggregate Performance

| Feature | Accuracy |
|---------|----------|
| Table detection | 0/9 tables found (17 false positives) |
| Table content extraction | 0% usable |
| Figure detection | 5/19 (26%) |
| Figure caption accuracy | 5/15 (33%) - others polluted with body text |
| Section detection | ~25% of sections identified |

---

## Root Cause Analysis

### Tables
1. **Not using pymupdf4llm/pymupdf_layout** - PyMuPDF prints "Consider using the pymupdf_layout package for a greatly improved page layout analysis" during `find_tables()`. This suggests the current approach is known to be inadequate.
2. **Text-based fallback too aggressive** - `strategy="text"` treats any text block as a potential table
3. **No validation of table structure** - Extracted "tables" are not checked for actual tabular content (headers, consistent columns, numeric data)

### Figures
1. **Not using pymupdf4llm** - Same layout analysis limitation
2. **Caption region too greedy** - Captures body text below the actual caption
3. **Multi-column layout not handled** - Adjacent column text captured as caption
4. **Image extraction misses embedded figures** - Only finds top-level image xrefs, not figures composed of multiple elements

### Section Detection
1. **Relies on standard heading names** - Papers using "Methods and Materials" instead of "Methods", or "Concluding Remarks" instead of "Conclusion" are not detected
2. **No structural analysis** - Doesn't use font size, spacing, or numbering to identify headings

### Image Rendering
1. **Alpha channel handling** - Some images rendered with black background instead of transparent/white

---

## Verification Data

Extraction output saved to `tests/extraction_output/`:
- `extraction_report.txt` - Full extraction log
- `figures/` - 15 PNG files
- `tables/` - 22 markdown files (all garbage for noname1/noname2)

---

## Remediation

See `OVERHAUL_PLAN.md` for migration to `pymupdf.layout` + `pymupdf4llm` stack.

Key improvements from new stack:
- Layout-aware extraction handles multi-column correctly
- Font-based heading detection (not keyword matching)
- Figure images extracted with markdown `![](...)` references
- OCR via Tesseract built-in
- ~82% code reduction
