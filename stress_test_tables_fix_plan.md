# Table Extraction Pipeline — Post-Implementation Audit & Revised Plan

## Summary

7 fixes were implemented. Investigation on real papers reveals:

| Fix | Status | Effect on real papers |
|-----|--------|---------------------|
| 1. Headers from rawdict | Implemented, minimal impact | Only 1 table (laird-fick T3) has different output. Keep but low value. |
| 2. Control char stripping | **Working** | Strips chars from 24 cells in helm-coregulation. |
| 3. Caption swap (Euclidean) | Implemented, narrow scope | Triggers only for fortune pg5 (T2/T3). Reyes tables are NOT side-by-side. |
| 4. Absorbed caption substring | **Not working** | Misses active-inference T4 (caption split across cells) and roland T2 (caption in row 2). |
| 5. Merged-word headers | **Working** | Fixes 8+ headers across yang T0/T1, laird-fick T4. |
| 6. Column detection | **Wrong approach, causes regression** | Never fires for target (active-inference T2). Causes helm regression (7->6 cols, 58%->41% fill). |
| 7. Artifact real-caption guard | **Working** | All expected artifacts classified correctly. |

Baseline was 15 MINOR. Current is 16 MINOR (+1 helm-coregulation table-1 regression from Fix 6).

---

## Fix 1: Headers from rawdict

### What it does
Uses `cleaned_rows[0]` (from multi-strategy winner, usually rawdict) for internal headers instead of `tab.header.names` (midpoint path). For external headers, re-extracts via `_table_mod.extract_cells`.

### Investigation findings
- Across all 10 papers, only **1 table** (laird-fick T3) has `tab.header.names` differ from `tab.extract()[0]`. In that case `header.names` picked up a stray word "patients" that `extract()[0]` missed.
- The real header improvements (e.g. fortune T1 decimal displacement `9982\n.` -> `998.2`) come from multi-strategy extraction scoring, not from Fix 1 itself.
- Fix 1's contribution is that `cleaned_rows[0]` uses the winning strategy's output. Without Fix 1, headers always go through midpoint even when rawdict won for the body.

### Verdict
**Keep as-is.** Low independent impact but architecturally correct -- headers should come from the same extraction strategy as the body. No regressions.

---

## Fix 2: Control character stripping

### What it does
Strips `\x00-\x08`, `\x0b-\x0c`, `\x0e-\x1f` from cell text at the start of `_clean_cell_text()`.

### Investigation findings
- **helm-coregulation**: 24 raw cells on page 5 contain `\x08` (backspace), `\x03` (ETX), `\x02` (STX). All stripped successfully -- zero control chars in extracted output.
- **friston-life**: No control characters in raw source. Fix 2 is a no-op here.
- No regressions. Preserves `\t`, `\n`, `\r` which are used as signals downstream.

### Verdict
**Keep as-is.** Working correctly, clean implementation, zero risk.

---

## Fix 3: Caption swap in 2-column papers

### What it does
Detects side-by-side objects (y-overlap > 30% of shorter height), switches from ordinal y-sort matching to Euclidean distance matching.

### Investigation findings
- **fortune-impedance pg5**: T2 (x=42-284) and T3 (x=311-553) are fully side-by-side (y-overlap ratio 1.00). Fix 3 triggers. Captions correctly assigned (Table 2 -> left, Table 3 -> right).
- **fortune-impedance pg6**: T5 and T6 share identical bboxes (116-480, 507-657). Fix 3 triggers but this looks like a duplicate/merged extraction issue, not a side-by-side layout.
- **reyes-lf-hrv**: No side-by-side tables at all. pg6 has T2 (y=136-276) and T3 (y=554-693) -- vertically stacked, not side-by-side. Fix 3 **never fires** for this paper.
- **roland-emg-filter**: Despite being 2-column IEEE, all tables span full width. No side-by-side tables.

### Verdict
**Keep as-is.** Correctly handles the fortune pg5 case. Reyes tables were incorrectly identified as a target in the original plan -- they're vertically stacked.

---

## Fix 4: Absorbed caption via substring match

### What it does
When a caption IS matched externally, `_strip_known_caption_from_table()` checks if the caption text also leaked into the headers or first 3 rows of the table grid, and removes it.

### Investigation findings -- NOT WORKING for 2 targets:

**active-inference T4** -- Caption `Table 2 (continued).` absorbed into headers as `['Table', '2', '(continued).', '']`. The function's substring logic SHOULD match (`"table 2"` prefix is in joined header text), and the per-cell guard SHOULD pass. But this table comes from `_split_at_internal_captions()`. The absorbed caption is in a data row of the PRE-SPLIT table. `_strip_known_caption_from_table` runs BEFORE `_split_at_internal_captions`, so it operates on the wrong grid.

**roland T2** -- Caption `"Table 2. Floating-point highpass filter coefficients."` appears in row 2. Rows 0-1 contain equation text (`"GHP[z] = ..."`, `"HPin[z] ..."`). The function's `else: break` early-exit stops scanning at row 0 (non-matching) and never reaches row 2.

### Bugs

1. **Early-exit logic** (`else: break`) stops scanning at the first non-matching row. Absorbed captions can appear after equation/header rows. Fix: scan all rows in range, don't stop at first non-match.

2. **Ordering problem** -- `_strip_known_caption_from_table` runs before `_split_at_internal_captions`. For continuation tables created by the split, the absorbed caption is in a data row of the pre-split table. Fix: also run caption stripping on each segment AFTER splitting.

### Reproposal

```python
# Bug A fix: remove early-exit, scan all rows in range 0..min(4, len)
for ri, row in enumerate(cleaned_rows):
    if ri > 3:
        break
    if _row_matches_caption(row):
        remove_indices.add(ri)
    elif row and _cell_contains_caption(row[0]):
        # clear just the first cell if other cells have data
        ...

# Bug B fix: after _split_at_internal_captions, strip each segment's caption
for seg in segments:
    if seg["caption"]:
        seg["headers"], seg["rows"] = _strip_known_caption_from_table(
            seg["caption"], seg["headers"], seg["rows"]
        )
```

---

## Fix 5: Merged-word headers

### What it does
After header extraction, cross-checks rawdict headers against words-strategy row 0. When rawdict has no space but words does, uses the words version.

### Investigation findings
Actively producing correct different output:

| Paper | Table | Rawdict header | After Fix 5 |
|-------|-------|---------------|-------------|
| yang T0 | Table 1 | `Samplesize` | `Sample size` |
| yang T1 | Table 2 | `Bodyweight` | `Body weight` |
| yang T1 | Table 2 | `Respiratoryrate` | `Respiratory rate` |
| yang T1 | Table 2 | `Infusiontime` | `Infusion time` |
| yang T1 | Table 2 | `Methodfor` | `Method for` |
| yang T1 | Table 2 | `Vt(ml/kg)` | `Vt (ml/kg)` |
| laird-fick T4 | Table 5 | `Distancefromrectum` | `Distance from rectum` |

No false positives.

### Verdict
**Keep as-is.** Clear value, working correctly, no regressions.

---

## Fix 6: Column detection -- run both, pick fewer columns

### What it does
Runs `_word_based_column_detection()` on every table's bbox, then replaces the native grid when word-based has fewer columns (and, after the latest edit, better fill rate).

### Investigation findings -- WRONG APPROACH

**Target: active-inference T2 (pages 18-19, "24 cols, 42% fill" in baseline)**

Actual pipeline trace for page 18:

| Stage | Cols | Rows | Fill | What happened |
|-------|------|------|------|---------------|
| Multi-strategy (rawdict wins) | 15 | 59 | 12% | Raw extraction |
| Fix 6: word-based | 24 | 83 | 42% | 24 > 15 cols -> Fix 6 **does nothing** |
| `_repair_low_fill_table` | 24 | 82 | 42% | 42% > 12% -> repair replaces |

Fix 6 **never fires** for its intended target because word-based produces MORE columns (24) than native (15). The 24-col/42% result in the DB comes from `_repair_low_fill_table`, not Fix 6.

**Root cause of the 24-column problem**: `_find_column_gap_threshold` Tier 1 (ratio break) fires on the wrong discontinuity.

Actual gap distribution for this table (751 positive gaps):

```
     0-0.5pt:    5    ← math expression fragments: "(" touching "ln", "(B†", etc
     0.5-1pt:    0
       1-2pt:   29
       2-3pt:  629    ← normal intra-word spacing (bulk of gaps)
       3-5pt:   19
      5-10pt:   11    ← transition zone
     10-20pt:    8    ← actual column gaps start here
     20-50pt:   25    ← inter-column gaps
       50+pt:   25    ← large column gaps
```

The 5 tiny gaps (0.0005pt) come from math expressions where pymupdf splits `(ln` into `(` and `ln` as separate words with nearly zero space. The ratio-break finds the first jump > 2x: 0.0005 -> 0.499 (ratio 960), setting threshold at `sqrt(0.0005 * 0.499) = 0.016pt`. This means EVERY word boundary (2-3pt) becomes a column separator.

The algorithm's intent is to find the break between intra-word gaps and inter-column gaps (~2-3pt vs ~10+pt). But it fires on a much earlier discontinuity (math fragments vs normal text) that has nothing to do with column structure.

**Regression: helm-coregulation table-1**

- Native: 7 cols, 12 rows, 58% fill (correct)
- Word-based: 6 cols, 32 rows, 41% fill (wrong -- splits rows, worse fill)
- The original unconditional "fewer columns wins" code picked words (6 < 7), causing the regression.
- The revised code (fewer cols AND better fill) should block this (41% < 58%), but the stress test was run with the old code.

### Verdict: REMOVE entirely

1. **Redundant**: `_repair_low_fill_table` already handles the same case with the same algorithm.
2. **Wrong target**: Word-based produces MORE columns for active-inference T2, so Fix 6 can never help.
3. **Root cause is in `_find_column_gap_threshold`**: The ratio-break fires on math-expression micro-gaps (5 occurrences) before reaching the real intra-word vs inter-column break. Fixing this would help both `_repair_low_fill_table` and any future column detection.

---

## Fix 7: Artifact tables -- real caption guard

### What it does
In `_classify_artifact()`, replaces `if not table.caption:` with `if not has_real_caption:` where `has_real_caption` checks if the caption matches "Table N" patterns.

### Investigation findings
Working correctly. Current artifact classifications:

| Paper | Table | Artifact type | Caption |
|-------|-------|--------------|---------|
| active-inference T0 | article_info_box | Author affiliation text |
| fortune T0 | article_info_box | Department/university text |
| huang T0 | table_of_contents | "Received" date line |
| roland T0 | diagram_as_table | Uncaptioned (circuit diagram) |
| yang T3 | figure_data_table | Uncaptioned (figure data) |

No false positives. No tables with spurious (non-"Table N") captions escaping detection.

### Verdict
**Keep as-is.** Working correctly, no regressions.

---

## Action Plan

### Keep as-is (no changes needed)
- Fix 1 -- Headers from rawdict
- Fix 2 -- Control character stripping
- Fix 3 -- Caption swap Euclidean matching
- Fix 5 -- Merged-word headers
- Fix 7 -- Artifact real-caption guard

### Rework
- **Fix 4** -- Absorbed caption substring match:
  - Bug A: Remove `else: break` early-exit. Scan rows 0..min(3, len) without stopping at first non-match.
  - Bug B: Also run `_strip_known_caption_from_table` on each segment AFTER `_split_at_internal_captions`.

### Remove
- **Fix 6** -- Column detection comparison. Remove `_word_based_column_detection` call site and the helper function.

### New fix needed (replacing Fix 6's intent)
- **`_find_column_gap_threshold` math-fragment gap filtering**: The ratio-break algorithm fires on 5 tiny gaps (0.0005pt) from math expression fragments like `(` touching `ln`. The bulk of gaps are at 2-3pt (intra-word) with real column gaps at 10+pt. The ratio break should skip the first discontinuity and find the second one (2-3pt vs 10+pt).

  Options:
  1. **Skip the first ratio break if the gap is far below the median**: if `unique[i] < median_gap * 0.1`, skip this break and continue looking. This would skip the 0.0005→0.499 break (0.0005 < 0.277) and find the real break between ~5pt and ~10pt.
  2. **Filter gaps below a minimum before ratio analysis**: Remove gaps < 0.1pt (a hard floor, which violates CLAUDE.md's no-hard-coded-thresholds rule) or gaps below `median_gap * some_fraction`.
  3. **Use the second or third ratio break instead of the first**: Scan all ratio breaks and pick the one closest to the median gap.

  Option 1 is simplest and data-derived (uses the gap distribution's own median). Would fix active-inference T2 in `_repair_low_fill_table` without needing a separate Fix 6 at all.
