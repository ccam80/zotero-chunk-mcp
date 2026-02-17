# Stress Test Tables — Author Review Report

Date: 2026-02-17. Reviewer: user (manual inspection via debug viewer).

**Verdict: 1 table correct (roland t7), maybe 2 others interpretable. Table extraction is a complete failure.**

---

## Per-Paper Issues

### active-inference-tutorial

| Table | Issue | Category |
|-------|-------|----------|
| Table 2 + continuations | One column per word. Math exists but surrounded by prose so "has greeks" guard triggers. Complete failure. | Column detection failure |
| Table 0 | Article info block — artifact, should be filtered | Artifact |
| Table 1 | Caption included as header rows | Absorbed caption (T8) |
| Table 3 | Space inserted before period: "MDP.xn" → "MDP .xn" | Decimal/punctuation displacement |

### fortune-impedance

| Table | Issue | Category |
|-------|-------|----------|
| Table 0 | Author info/keywords/abstract artifact. Abstract heading lost. | Artifact |
| Table 1 | Decimal spacing broken: 9982.0 → "9982 ." | Decimal displacement (T1) |
| Table 2/3 | Captions swapped — side-by-side in 2-column layout at page top | Caption swap (2-col) |
| Table 3 (real, t2 caption) | mean(SD) values decimals removed: 12.5(19.2) → 125(192). Package-breaking. | Decimal displacement (T1) |
| Table 4 | Same mean(SD) decimal destruction | Decimal displacement (T1) |
| Table 5 | Caption absorbed as header + top two rows | Absorbed caption (T8) |
| Table 5, 6 | LaTeX math variables broken across rows: R^\'_A(kohm) → C^\' \n A(kohm) | Math/symbol corruption + row split |

### friston-life

| Table | Issue | Category |
|-------|-------|----------|
| Table 1 | Garbled. Two-row cells in single column, alternately captures italic leading words or skips. Φ→C, Ω→C in caption+content. Math equations dropped entirely. | Multi-row cell failure + Greek corruption |

### hallett-tms-primer

| Table | Issue | Category |
|-------|-------|----------|
| Table 1 | Misses header row, first data row assigned as header. ≥5Hz → R5Hz. Final row: one first-col value, cols 2-3 are 3-row continuations incorrectly broken and transposed left. | Header detection + symbol corruption + continuation failure |

### helm-coregulation

| Table | Issue | Category |
|-------|-------|----------|
| Table 1 | Very broken. Adjacent columns merged. Negative sign lost on header. 4393.8,7 → "43938 7 .". Footnote captured as rows 8-11. | Column merge + decimal displacement + footnote (T5) |
| Table 2 | All adjacent rows merged. Baseline/conversation are two headers. β→box symbol. Merged numbers decimals ruined. < → box. | Row merge + Greek corruption + decimal displacement |

### huang-emd-1998

| Table | Issue | Category |
|-------|-------|----------|
| Table 0 | Author information + TOC artifact | Artifact |
| Table 1 | Continued TOC artifact | Artifact |

### laird-fick-polyps

| Table | Issue | Category |
|-------|-------|----------|
| Table 1 | Superscript merged: Total^b → Totalb. Decimals ruined: 5828(42.0) → .5828(420) | Superscript merge + decimal displacement (T1) |
| Table 2 | Same as t1 | Superscript merge + decimal displacement (T1) |
| Tables 3, 4, 5 | All numbers ruined. Note: t4 is sparsest correct table seen at 78.6% fill. | Decimal displacement (T1) |

### reyes-lf-hrv

| Table | Issue | Category |
|-------|-------|----------|
| Table 1 | Final column decimals broken: ".906, .870" → "906 870.,." η²→h2. | Decimal displacement (T1) + Greek corruption |
| Table 2 | F(1,39)→F(139),. Same greeks and decimals errors. | Parenthesis collapse + decimal displacement |
| Tables 3/4 | Caption swap. T3 bottom-left col, T4 top-right col. | Caption swap (2-col) |
| Table 3 (actual, t4 caption) | Same as t4 actual | Decimal displacement |
| Table 4 (actual, t3 caption) | Partial decimal survival. Panel A PEP-BL: ".081,.133,-.061,-.097" → "0.081,0.133,061-.,-.097" | Inconsistent decimal displacement |
| Table 5 | Decimals transposed: 4.50 → 0.450 | Decimal displacement (T1) |

### roland-emg-filter

| Table | Issue | Category |
|-------|-------|----------|
| Table 0 | Block diagram captured as table | Artifact |
| Table 1 | Decimals broken: −1.8278,0.8501 → "18278-.,0.08501". Negative signs detached. | Decimal displacement (T1) + negative sign (T6) |
| Table 2 | Decimals good, but from row 23 reads Figure 8 as table — check overlap. | Figure/table overlap |
| Figure 5 | Contains all of table 2 + equation above it. | Figure/table overlap |
| Table 3 | Numbers cooked: 0.914±0.119i → "0.914,0.119i" then ±symbols on next row in wrong cols | Complex number corruption + symbol row split |
| Table 4 | Decimals mangled: 0.992±0.013i → "0992±0013i . ." | Decimal displacement |
| Table 5 | Close to good — μs column header over col 1, should be col 2 | Header misalignment |
| Table 6 | Same as t5. Decimals: 1.28 → 0.128 | Header misalignment + decimal displacement |
| Table 7 | **CORRECT** — first correct table in dataset | ✅ |
| Table 8 | Abbreviations (acceptable) | Minor |

### yang-ppv-meta

| Table | Issue | Category |
|-------|-------|----------|
| Table 1 | Superscripts flattened: 20^a → 20a. Words merged: "Vascular surgery, trauma, septic shock" → "Vascularsurgery trauma septicshock , ," | Superscript merge + word merge + punctuation displacement |
| Table 2 | Continuation rows unmerged: row 6/7 and 11/12 | Row continuation failure |
| Table 3 | Most continuations missed | Row continuation failure |
| Table 3 (internal, uncaptioned p7) | Figure interpreted as text | Misclassification |

---

## Issue Categories (by frequency)

| Category | Count | Papers Affected | Mechanism Exists? |
|----------|-------|-----------------|-------------------|
| **Decimal displacement (T1)** | ~25+ instances | 8/10 papers | Yes — `_clean_cell_text` leading zero + reassembly. **NOT WORKING** for most cases. |
| **Greek/math symbol corruption** | ~10 instances | 5 papers | No mechanism. PyMuPDF text extraction returns wrong chars. |
| **Artifacts (author info, TOC, diagrams)** | 5 tables | 3 papers | Phantom filter was REMOVED (net-negative). No current filter. |
| **Caption swap (2-column papers)** | 2 pairs (4 tables) | 2 papers | No mechanism. Caption matching is y-sorted; fails for side-by-side. |
| **Absorbed caption as header (T8)** | 3 tables | 2 papers | Yes — `_strip_absorbed_caption`. **NOT WORKING** for these cases. |
| **Footnote as data rows (T5)** | 1+ tables | 1 paper | Yes — `_strip_footnote_rows`. **NOT WORKING** for helm t1. |
| **Row continuation failure** | 4+ tables | 3 papers | Yes — `_merge_over_divided_rows`. **NOT WORKING** for these cases. |
| **Column detection failure** | 2+ tables | 2 papers | Yes — `_find_column_gap_threshold`. **CATASTROPHICALLY WRONG** for active-inference t2. |
| **Superscript merge** | 3+ tables | 2 papers | No mechanism. PyMuPDF extracts superscript inline. |
| **Figure/table bbox overlap** | 2 tables | 1 paper | Yes — `figure_data_table` artifact tag. **NOT WORKING** for roland. |
| **Negative sign detachment (T6)** | 2+ tables | 2 papers | Yes — `_CELL_NEG_DOT_RE`. **NOT WORKING** for these patterns. |
| **Header misdetection** | 2+ tables | 2 papers | Partial — `_separate_header_data`. Not covering these cases. |
| **Word/punctuation merge/split** | 3+ tables | 2 papers | No mechanism. |
| **Parenthesis collapse** | 1+ tables | 1 paper | No mechanism. |
| **Complex number ± split** | 2 tables | 1 paper | No mechanism. |

---

## Critical Finding: Decimal Displacement Root Cause

**Confirmed**: PDF values are correct. `get_text("dict")` and `get_text("words")` both return
proper decimals (e.g. `"998.2"`, `"5828 (42.0)"`). The corruption is caused by `pymupdf.layout`.

### The layout engine decimal split

`import pymupdf.layout` changes `find_tables()` behavior. Without layout: 0 tables found.
With layout: tables found, but the layout engine splits decimal numbers into separate lines
within cells:

```
PDF actual: "998.2"     → find_tables cell: "9982\n."
PDF actual: "5828 (42.0)" → find_tables cell: "5828(420)\n."
```

### Three distinct bugs in the cleaning pipeline

| Raw cell from layout engine | `_clean_cell_text` result | Why it fails |
|---|---|---|
| `"9982\n."` | `"0.9982"` | **Works** — `_CELL_LEADING_DOT_RE` matches `\n.` |
| `"9982 ."` (after `_separate_header_data` `.split()`) | `"9982 ."` | **Bug 1**: `.split()` collapses `\n` to space. Regexes only match `\n`, not space. |
| `"5828(420)\n."` | `".5828(420)"` | **Bug 2**: Step 2 moves dot to front, but `_looks_numeric` rejects `()` so Step 2b (prepend `0`) is skipped. PDF value is `5828 (42.0%)`. |
| `"906 870\n. , ."` | `"906 870 . , ."` | **Bug 3**: Multi-value cell. `_CELL_LEADING_DOT_RE` expects single value pattern, doesn't match. |

### Bug 1 chain (dominant — affects 8/10 papers)

1. `pymupdf.layout` + `find_tables()` returns header cell `"ZTA\n𝑅1(Ω)\n9982\n."` (first data row fused into header)
2. `_separate_header_data()` calls `.split()` (splits on all whitespace including `\n`)
3. Numeric parts become `["9982", "."]`, re-joined with space: `"9982 ."`
4. `_clean_cell_text("9982 .")` — no pattern matches (all expect `\n`)
5. Data rows NOT from header split retain `\n` → correctly cleaned

**Fix**: `_separate_header_data` must join numeric suffix parts with `\n` not space, OR
`_clean_cell_text` must also handle `"digits ."` (space + trailing dot).

### Bug 2 chain (laird-fick)

1. PDF: `"5828 (42.0)"` → layout engine: `"5828(420)\n."` (space removed, decimal relocated)
2. `_CELL_LEADING_DOT_RE` matches, moves dot to front: `".5828(420)"`
3. `_looks_numeric(".5828(420)")` → False (parentheses not in allowed charset)
4. Step 2b skipped, no leading zero prepended

**Fix**: `_looks_numeric` must allow `()` in numeric cells (common for SD/CI values).
Also need to reconstruct the interior decimal in `(420)` → `(42.0)`.

### Bug 3 chain (reyes multi-value cells)

1. Multiple values in one cell: `"906 870\n. , ."`
2. No pattern handles multiple values + multiple trailing dots
3. `_CELL_MULTI_DOT_RE` exists but requires exact 2-number pattern

**Fix**: Generalize multi-value decimal reassembly to handle N values.

---

## Other Critical Findings

### Caption matching for 2-column papers is fundamentally broken

Caption-to-table matching uses y-sort only. In 2-column papers where tables sit side-by-side
(fortune Tables 2/3, reyes Tables 3/4), captions get swapped. The matching algorithm has
no x-position awareness. This is not an edge case — 2-column layouts are the dominant format
in academic papers.

### Greek/math symbol corruption has no mechanism

Φ→C, Ω→C, η²→h2, β→box, <→box, ≥→R across 5 papers. This is a font-level extraction
error where PyMuPDF maps glyphs to wrong Unicode codepoints (likely CMap issues in embedded
fonts). No current code addresses this. Needs font-aware extraction or OCR fallback for
affected cells.

### Artifact filtering needs revisiting

The phantom table filter was removed (net-negative per MEMORY.md) but artifacts remain in
output: author info blocks, TOC pages, block diagrams captured as tables across 3 papers.
These are presented to the researcher as real tables. A new artifact detection strategy is
needed.

### Automated quality checks are missing

The only way to detect these failures currently is manual author review. The pipeline needs
automated quality signals — e.g. digit-count consistency within numeric columns, decimal
presence validation, cross-checking `find_tables()` values against `get_text("words")` for
the same region.
