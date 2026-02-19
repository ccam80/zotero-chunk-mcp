# Table Extraction — Fix Plan

## Current State

0 MAJOR, 15 MINOR failures (6 abstract, 5 section, 3 table-content-quality, 1 chunk-count).
9 tables with fill < 70%. Root cause: single global gap threshold cannot
represent tables with heterogeneous row structures.

## Previously Implemented Fixes — Status

| Fix | Status | Action |
|-----|--------|--------|
| 1. Headers from rawdict | Working, low impact | Keep |
| 2. Control char stripping | **Actively harmful** — strips β from helm T2 | Rework (Fix 3 below) |
| 3. Caption swap (Euclidean) | Working for fortune pg5 | Keep |
| 4. Absorbed caption substring | Not working (2 bugs) | Rework (Fix 4 below) |
| 5. Merged-word headers | Working, clear value | Keep |
| 6. Column detection comparison | Wrong approach, regression | **Removed** |
| 7. Artifact real-caption guard | Working correctly | Keep |

---

## Fix 1: Remove `_word_based_column_detection` — DONE

Deleted the function and its call site. It duplicated `_repair_low_fill_table`,
never fired for its intended target, and caused the helm regression.

---

## Fix 2: Hotspot column detection + continuation merge

Replaces `_find_column_gap_threshold`, `_repair_low_fill_table`, and
`_merge_over_divided_rows`. Applied to ALL tables as the primary extraction
path. Multi-strategy extraction (rawdict/midpoint/words) is also replaced —
hotspot builds its own grid from word positions, so decimal displacement
doesn't exist (whole words assigned to columns, not characters to cells).

`find_tables()` is retained only for **bbox detection**.

### The problem

`_find_column_gap_threshold` pools ALL word gaps from ALL rows into one
distribution and looks for a single separating threshold. This fails when:

1. **Math micro-gaps** (active-inference Table 2): 0.0005pt gaps from math
   fragments poison the ratio break → threshold 0.016pt → 24 columns.
2. **Single-word cells** (helm Table 2, reyes Table 5): All gaps are
   inter-column. No bimodal distribution exists to separate.
3. **Prose cells** (active-inference Table 2): Intra-cell word spacing
   (2.8pt) matches body text. Global threshold either over-splits or
   under-splits.

These are the SAME problem: a single global threshold cannot represent a
table where different rows have different gap structures.

### Per-table findings

#### active-inference Table 2 (p18-19) — 24c/42% → should be 4c

- Header row has 4 clear columns at x=[107.5, 223.9, 378.3].
- Most rows are continuations with text in 1-2 columns.
- Old global threshold at 378.3 over-splits — prose cells in single
  columns get divided. With gap-interval detection, these prose cells
  produce no gap at that x-position, so the spurious boundary won't form.

#### helm Table 2 (p6) — 6c/39% → should be 6c

- Header: 6 words, ALL gaps are inter-column (17-32pt). No word-level gaps.
- Inline header rows ("Baseline", "Conversation") at x≈48, coefficient
  labels (β₀ₘ, β₁f) at x≈121-133. These are exclusive-or with data columns.
- β encoded as `\x06` in `Universal-GreekwithMathP` — deleted by Fix 2.

#### roland Table 2 (p10) — 10c/50% → should be 7c

- R0-R2: equations captured in table bbox (not table data).
- R3: absorbed caption.
- R4: header, R5-R22: data (7 cols, extremely consistent).
- R23+: figure data captured below table.

#### active-inference Table 3 continued (p31) — 4c/53% → should be 4c

- Column count correct but fill low from continuation rows.

#### reyes Table 5 (p7) — 2c/55% → should be 9c

- Every row: 9 single-word cells. All gaps 10-27pt. No intra-word gaps.
- Hotspot consensus: 9 cols, 100% agreement.

#### reyes Table 2 (p4) — 6c/56% → should be 6c

- Full data rows: 6 cols. Partial data rows: 3 cols (cols 0-2 only).
- Inline headers ("IBI", "SPD", "VLF", "LF HF") as single-word rows.

#### yang Table 2 (p5) — 13c → should be 15c

- Year→Vt gap is 6.13pt, recurs at x≈205 across all data rows.
- Continuation rows: R7 ("blood flow Doppler"), R12 ("colleagues [31]").

#### yang Table 3 (p6) — 11c → correct at 11c

- Working. 100% consensus.

#### roland Table 3 (p16) — 9c/60% → should be 5c

- All rows: 5 cols, 100% consensus. Working.

### Core idea

Column boundaries are **x-positions where gaps consistently appear across
rows**. The unit of detection is the gap x-position, not a gap size threshold.

### Algorithm

**Step 1: Extract words and cluster into rows**

1. Get words from bbox via `page.get_text("words", clip=bbox)`.
2. Cluster into rows using existing `_adaptive_row_tolerance()`.
3. Sort words within each row by x-position.

**Step 2: Collect gap-hotspot candidates**

For each row:
1. Compute gaps between adjacent words: `word[i+1].x0 - word[i].x1`.
2. Filter out micro-gaps: gaps must be ≥ median_word_height × 0.25 (~2pt).
   This kills math micro-gaps (0.0005pt) without touching real column
   gaps (smallest in corpus: 6pt).
3. Record the x0 of the word AFTER each surviving gap as a hotspot candidate.

No body-text reference needed. No "large gap" threshold. ALL non-micro gaps
produce hotspot candidates. Column boundaries emerge from x-position
consensus, not from gap size filtering.

**Step 3: Cluster candidates into column boundaries**

1. Sort all hotspot candidates by x-position.
2. Cluster within a tolerance (median word width from the table's own words).
3. Each cluster's representative x-position = median of its members.
4. Cluster support = number of DISTINCT rows contributing.
5. Minimum support threshold for initial pass: need to determine
   adaptively. Probably a fraction of total non-caption rows. Must be
   low enough to catch columns that only appear in some rows (partial
   data rows in reyes Table 2), but high enough to exclude noise from
   equation/figure artifact rows.
6. Surviving clusters = column boundaries. Count + 1 = column count.

Header row weighting: the first non-caption row with ≥ 3 gaps gets its
hotspot candidates counted with extra weight (e.g., each header hotspot =
N votes where N = ceil(total_rows × 0.3)). This ensures headers anchor
column structure even when most data rows are continuations.

**Step 4: Assign words to columns**

For each row, assign each word to a column based on its x-position relative
to the column boundary x-positions. Words before the first boundary → col 0.
Words between boundary[i] and boundary[i+1] → col i+1. Etc.

Concatenate words within each cell with spaces.

**Step 5: Detect and merge continuation rows**

A continuation row is a row where long cell text in one (or a few) columns
wraps to a new line. The continuation text stays within its column — it
never crosses column boundaries. The other columns in that row are empty.
Because the empty columns produce gaps at every boundary position, a
continuation row supports ALL column boundaries in the matrix (max row sum).

Detection: after word-to-column assignment, a row is a continuation if:
- Its populated columns are a strict subset of the previous primary row's
  populated columns, AND
- The populated columns are adjacent (no populated-empty-populated pattern
  that would indicate a misaligned data row)

Merge: append continuation row's cell text to the previous primary row's
corresponding cells.

**Step 6: Iterative refinement (add-only)**

After initial assignment, check for rows with gaps at x-positions not near
any current hotspot. If multiple non-continuation rows share a gap position
→ add as new hotspot → re-run from Step 4.

Iterations only ADD hotspots, never remove. This ensures monotone
convergence toward the correct column count (can only increase, never
decrease toward 1).

Terminate when no new hotspots are found.

**Step 7: Inline header detection (post-continuation)**

After continuation merging, detect columns with exclusive-or population
pattern: a column is an inline-header column if, whenever it is populated,
no other columns are populated in that row, and whenever other columns are
populated, it is empty.

Fix: forward-fill the inline header value into all empty positions in that
column below it until the next header row. Delete the pure-header rows.

This converts:
```
| Baseline |          |      |      |
|          | β₀ₘ      | 0.47 | 0.03 |
|          | β₁f      |-0.16 | 0.03 |
| Convers. |          |      |      |
|          | β₀ₘ      | 0.35 | 0.04 |
```
Into:
```
| Baseline | β₀ₘ      | 0.47 | 0.03 |
| Baseline | β₁f      |-0.16 | 0.03 |
| Convers. | β₀ₘ      | 0.35 | 0.04 |
```

### Pipeline change

Current:
```
find_tables() → bbox + native grid
    → multi_strategy_extract(native grid) → headers, rows
    → absorbed_caption → header_data_sep → repair → merge → remove_empty → split → footnotes
```

New:
```
find_tables() → bbox only
    → hotspot_extract(page, bbox) → headers, rows (with continuations merged)
    → absorbed_caption → header_data_sep → remove_empty → split → footnotes
```

`_repair_low_fill_table`, `_find_column_gap_threshold`, `_merge_over_divided_rows`,
and `_extract_cell_text_multi_strategy` are all removed.

---

## Fix 3: Font-aware control character stripping

### Problem

Helm Table 2: β encoded as `\x06` in font `Universal-GreekwithMathP`.
Current control-char stripping (`\x00-\x08`) deletes every β. Output
shows "0m" instead of "β₀ₘ".

### Root cause

`\x06` (ACK) is a control character in Unicode but a valid glyph in the
PDF's custom Greek font. Stripping blindly by codepoint without checking
the font.

### Fix

This now needs to work in the hotspot extraction path rather than
`_clean_cell_text()`. When assembling cell text from words, check whether
control characters come from specialized fonts (name containing "Greek",
"Math", "Symbol"). If so, attempt Unicode mapping via font metadata or
preserve as-is. Only strip control characters from standard text fonts.

Since hotspot extraction uses `page.get_text("words")` which returns plain
text without font info, we may need a rawdict pass specifically for cells
that contain control characters — detect them in the words output, then
look up the font from rawdict for just those characters.

---

## Fix 4: Absorbed caption bugs

### Problem

Two bugs in `_strip_absorbed_caption()`:

1. **Early-exit**: `else: break` stops at first non-matching row. Absorbed
   captions can appear after equation rows (roland Table 2, row 2 is an
   equation, row 3 is the absorbed caption).
2. **Ordering**: Runs before `_split_at_internal_captions`. Continuation
   table segments never get their absorbed captions stripped.

### Fix

1. Remove the `else: break` — scan all rows (or first N rows) for caption
   pattern, don't stop at first non-match.
2. Move absorbed caption stripping to run after split, so each segment
   gets its own pass.
