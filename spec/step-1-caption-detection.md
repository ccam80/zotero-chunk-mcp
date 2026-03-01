# Step 1: Fix Caption Detection

## Overview

Fix `find_all_captions()` to detect label-only captions ("Table 1", "Figure 3")
that currently fall through all match paths. In the vision-first architecture,
`find_all_captions()` is the sole mechanism for discovering tables — a missed
caption means a missed table.

**No caption merging.** When a label-only caption is detected, the vision agent
enriches the caption text at extraction time (it sees the full crop including
surrounding text). This step only fixes detection, not text enrichment.

**Scope**: Both table and figure label-only captions. The code is generic
(loops over both types), so the fix applies symmetrically.

---

## Wave 1: Label-only primary match

### Task 1.1: Add label-only match in `find_all_captions()`

- **Description**: Insert `label_only_re` as a primary match path between
  the strict (`prefix_re`) and relaxed (`relaxed_re`) branches in
  `find_all_captions()`. No structural confirmation (bold, font-change)
  required — the `\s*$` end anchor is sufficient (the entire block text
  must be just the label).

- **Files to modify**:
  - `src/zotero_chunk_rag/feature_extraction/captions.py` — In
    `find_all_captions()` (line ~281), add an `elif` branch between the
    `prefix_re.match(check_text)` check and the `relaxed_re.match(check_text)`
    check:
    ```python
    if prefix_re.match(check_text):
        matched = True
    elif label_only_re and label_only_re.match(check_text):
        matched = True
    elif relaxed_re and relaxed_re.match(check_text):
        # ... existing font-change confirmation logic (unchanged) ...
    ```

- **Tests**:
  - `tests/test_feature_extraction/test_captions.py::TestFindAllCaptions::test_label_only_table`
    — A mock page with a single block containing only "Table 1" (no trailing
    text). Assert `find_all_captions()` returns exactly 1 caption with
    `caption_type="table"`, `number="1"`, `text="Table 1"`.
  - `tests/test_feature_extraction/test_captions.py::TestFindAllCaptions::test_label_only_figure`
    — A mock page with a single block containing only "Figure 3". Assert
    1 caption with `caption_type="figure"`, `number="3"`.
  - `tests/test_feature_extraction/test_captions.py::TestFindAllCaptions::test_label_only_with_supplementary_prefix`
    — A mock page with "Supplementary Table S2". Assert 1 caption with
    `number="S2"`.
  - `tests/test_feature_extraction/test_captions.py::TestFindAllCaptions::test_label_only_does_not_match_body_text`
    — A mock page with a block containing "Table 1 shows the results of
    our analysis". Assert this matches via relaxed (with font-change) or
    not at all — NOT via label-only (because text after the number means
    `\s*$` won't anchor).

- **Acceptance criteria**:
  - A standalone "Table 1" block is detected as a table caption
  - A standalone "Figure 3" block is detected as a figure caption
  - "Table 1 shows the results" (body text) does NOT match via label-only
  - All existing `test_captions.py` tests still pass (no regressions)

---

### Task 1.2: Add label-only match in `_scan_lines_for_caption()`

- **Description**: Add `label_only_re` matching in `_scan_lines_for_caption()`
  (line ~213) between the `prefix_re` and `relaxed_re` checks. This handles
  cases where PyMuPDF merges preceding text (axis labels, etc.) into the
  same block as a caption, so the block-level match fails but a line-level
  scan finds it. No structural confirmation required.

- **Files to modify**:
  - `src/zotero_chunk_rag/feature_extraction/captions.py` — In
    `_scan_lines_for_caption()` (line ~214), after the `prefix_re.match(check_line)`
    check, add:
    ```python
    if prefix_re.match(check_line):
        return _text_from_line_onward(block, line_idx)
    if label_only_re and label_only_re.match(check_line):
        return _text_from_line_onward(block, line_idx)
    if relaxed_re and relaxed_re.match(check_line):
        # ... existing font-change confirmation (unchanged) ...
    ```
    Note: `_text_from_line_onward(block, line_idx)` returns text from the
    matching line *onward*, so if the block has "axis labels / Table 1 /
    Summary of demographics...", the returned caption text will be
    "Table 1 Summary of demographics..." — naturally capturing any
    description from subsequent lines in the same block.

- **Tests**:
  - `tests/test_feature_extraction/test_captions.py::TestFindAllCaptions::test_label_only_line_scan`
    — A mock page with a 3-line block: line 0 = "Y-axis label", line 1 =
    "Table 2", line 2 = "Patient demographics by age group". Assert
    `find_all_captions()` returns 1 caption with `caption_type="table"`,
    `number="2"`, and text containing both "Table 2" and "Patient demographics".
  - `tests/test_feature_extraction/test_captions.py::TestFindAllCaptions::test_label_only_line_scan_figure`
    — Same structure but with "Figure 5" on line 1. Assert 1 figure caption
    with `number="5"`.

- **Acceptance criteria**:
  - A "Table N" line buried inside a multi-line block is detected
  - The returned caption text includes text from subsequent lines in the
    same block (via `_text_from_line_onward`)
  - All existing tests still pass

---

## Wave 2: Caption audit script

### Task 2.1: Standalone caption audit on 20-paper corpus

- **Description**: Create a standalone script that opens 20 papers from the
  user's Zotero library, runs `find_all_captions()` on every page, and
  reports per-paper caption counts. This validates the label-only fix
  against real PDFs without calling any external API (Zotero's SQLite
  database and local PDF storage only).

- **Files to create**:
  - `tests/audit_captions.py` — Standalone script (run directly, not via
    pytest). Key components:

    **Corpus**: The 20 item keys from the vision integration test:
    ```python
    CORPUS_KEYS = [
        "SCPXVBLY",  # active-inference-tutorial
        "XIAINRVS",  # huang-emd-1998
        "C626CYVT",  # hallett-tms-primer
        "5SIZVS65",  # laird-fick-polyps
        "9GKLLJH9",  # helm-coregulation
        "Z9X4JVZ5",  # roland-emg-filter
        "YMWV46JA",  # friston-life
        "DPYRZTFI",  # yang-ppv-meta
        "VP3NJ74M",  # fortune-impedance
        "AQ3D94VC",  # reyes-lf-hrv
        "UHSPFNS3",  # vagal tone preterm
        "5LY5DK3R",  # PPG variability
        "E2PC978X",  # improved HRV method
        "8QZ8IQFC",  # surgeon stress HRV
        "GMVKXTRD",  # peak detection HRV
        "HGHR7F4P",  # premature beats fractal
        "JL2AFCL6",  # cardiac regulation
        "QRN8G52V",  # subjective stress cortisol
        "XHS29V4K",  # infant emotion regulation
        "EGXBPFLE",  # editing R-R intervals
    ]
    ```

    **Flow**:
    1. Instantiate `ZoteroClient` from `Config`
    2. For each item key: `get_item(key)` → open PDF with `pymupdf.open()`
    3. For each page: `find_all_captions(page)` → collect results
    4. Track per-paper: table caption count, figure caption count,
       label-only caption count (captions where text matches
       `_TABLE_LABEL_ONLY_RE` or `_FIG_LABEL_ONLY_RE`)
    5. Print summary table to stdout:
       ```
       Paper                     Tables  Figures  Label-Only  Pages
       active-inference-tutorial       3        5           0     24
       huang-emd-1998                  0        9           0     39
       ...
       TOTAL                          45       62           3    312
       ```
    6. Print per-caption detail for any label-only captions found
       (paper, page, text, bbox)
    7. Exit with code 0

    **No assertions** — this is an audit/report tool, not a test.
    The user inspects the output to verify caption counts are correct.

    **Imports**: `ZoteroClient`, `Config` from `zotero_chunk_rag`;
    `find_all_captions`, `_TABLE_LABEL_ONLY_RE` from
    `feature_extraction.captions`; `pymupdf`. No external API calls.

    **Note**: If a `_FIG_LABEL_ONLY_RE` constant exists in `captions.py`,
    import and use it for figure label-only detection. If it does not
    exist (the caption code uses a generic loop with per-type regex
    variables), detect label-only figures by checking if the caption
    text matches `_TABLE_LABEL_ONLY_RE`'s figure counterpart pattern
    (`r"^(?:Figure|Fig\.?)\s+..."`) or by inspecting
    `DetectedCaption.text` length heuristically. The audit script
    should report label-only counts for both types regardless.

- **Tests**: None (the audit script IS the verification tool).

- **Acceptance criteria**:
  - Script runs without errors: `.venv/Scripts/python.exe tests/audit_captions.py`
  - Prints a per-paper summary table with caption counts
  - Reports any label-only captions found (validating the fix works on real PDFs)
  - Does not call any external API (Zotero SQLite + local PDFs only)

---

## Agent Execution Rules

### No API calls

Implementation agents MUST NOT make external API calls (Anthropic, Zotero
network API, or any network request). `ZoteroClient` reads from local SQLite
— this is permitted. `pymupdf.open()` reads local PDFs — this is permitted.

### Test execution protocol

Tests are run at most TWICE per implementation session:

1. **First run**: Execute `pytest tests/test_feature_extraction/test_captions.py -v`.
   Record all failures.
2. **Quick fix round**: Fix only obvious mechanical issues (broken imports,
   missing mock helpers). No restructuring.
3. **Second run**: Execute again. Record remaining failures.
4. **Report**: Surface all remaining failures to the user. Do not loop.

### No test modification to make tests pass

If an existing test fails after the change, the agent reports it — it does
not modify existing test assertions.

---

## Acceptance Criteria (Step-level)

1. `find_all_captions()` detects standalone "Table N" and "Figure N" blocks
2. `_scan_lines_for_caption()` detects "Table N" and "Figure N" lines within
   multi-line blocks
3. All existing `test_captions.py` tests pass (no regressions)
4. All new tests pass
5. Caption audit script runs successfully on the 20-paper corpus and prints
   per-paper caption counts
6. No code changes outside `captions.py` and test files
