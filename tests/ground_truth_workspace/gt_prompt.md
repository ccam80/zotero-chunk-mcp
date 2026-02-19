# Ground Truth Drafting: Agent Prompt Template

## Role

You are reading academic paper tables from rendered images to create ground truth data. Your task is to produce an exact transcription of each table's contents as they appear in the rendered PNG image. You must read from the image only, without consulting or referencing the extraction output.

## Rules for Reading Tables

1. **Read from the image only.** Do not guess, infer, or fill in values that are not visible. Do not consult extraction JSON files, the PDF text layer, or any other data source.

2. **Merged cells (column spans).** If a cell spans multiple columns, place its content in the leftmost column position and leave the spanned columns as empty strings (`""`).

3. **Merged cells (row spans).** If a cell spans multiple rows, place the content in the topmost row and leave lower rows as empty strings (`""`) in that column.

4. **Multi-line cell content.** Join multi-line content within a single cell with a single space. For example, a cell reading:
   ```
   Odds
   Ratio
   ```
   becomes `"Odds Ratio"`.

5. **Unreadable text.** If text is too small, blurry, or otherwise unreadable, transcribe what you can see and add a description in the `notes` field. For example: `"notes": "Row 5, col 3: partially illegible, transcribed as best guess"`.

6. **Sub-headers and panel labels.** Include ALL rows that appear within the table body, including sub-group headers (e.g., "Panel A: Males", "Age group 18-30"). These are data rows, not footnotes.

7. **Footnotes.** Footnote rows (e.g., "Note: ..." or "* p < 0.05" or "CI = confidence interval") should NOT be included in the `rows` array. Instead, note their presence and content in the `notes` field.

8. **Preserve exact values.** Transcribe numbers, symbols, and text exactly as they appear. Do not round, reformat, or correct perceived typos. If the image shows `0.047`, write `"0.047"`. If it shows `.047`, write `".047"`.

9. **Column headers.** The `headers` array contains the column header labels from the table. If there are multi-level headers (e.g., a spanning header "Treatment" above sub-headers "Drug A" and "Drug B"), use the lowest-level (most specific) headers in the `headers` array. Note the spanning structure in `notes`.

10. **Empty cells.** Represent genuinely empty cells as `""`. Cells containing only a dash or similar placeholder (e.g., "-", "--", "---") should be transcribed as they appear (e.g., `"-"`).

## Procedure

### Step 1: Create the Workspace

Run the workspace creation script to generate table images and template files:

```bash
"./.venv/Scripts/python.exe" tests/create_ground_truth.py
```

This creates `tests/ground_truth_workspace/` with one subdirectory per corpus paper. Each paper directory contains:
- `table_<idx>.png` -- rendered image of each table region
- `table_<idx>_extraction.json` -- current pipeline extraction (for later comparison, NOT for drafting)
- `table_<idx>_gt.json` -- empty ground truth template (your output target)
- `manifest.json` -- listing of all tables with metadata

### Step 2: Spawn Drafting Agents

For each paper directory (10 total), spawn a Claude Code Task agent (sonnet model) with the following prompt. Replace `<PAPER_DIR>` with the paper's subdirectory name:

```
Read the file tests/ground_truth_workspace/gt_prompt.md for your instructions.

Your assignment: draft ground truth for all tables in the paper directory
tests/ground_truth_workspace/<PAPER_DIR>/

For each table:
1. Read the manifest.json to get the list of tables and their metadata.
2. Read each table_<idx>.png image using the Read tool.
3. Transcribe the table contents following the rules in gt_prompt.md.
4. Write the completed ground truth to the corresponding table_<idx>_gt.json file.

Do NOT read or reference the table_<idx>_extraction.json files. Work from images only.
```

### Step 3: Verify Coverage

After all agents complete, check that every `table_<idx>_gt.json` has been populated (non-empty `headers` or `rows`). Any tables that the agent could not read (e.g., the image shows a figure mislabeled as a table) should have a note explaining why.

## Output Format

For each table, overwrite the `table_<idx>_gt.json` template with the completed ground truth. The JSON schema is:

```json
{
  "table_id": "<from manifest.json>",
  "paper": "<short_name from manifest>",
  "item_key": "<item_key from manifest>",
  "page_num": 4,
  "table_index": 0,
  "caption": "Table 1. Patient Demographics",
  "headers": ["Variable", "Group A (n=50)", "Group B (n=48)", "p-value"],
  "rows": [
    ["Age, mean (SD)", "62.3 (11.2)", "64.1 (10.8)", "0.42"],
    ["Male, n (%)", "28 (56)", "30 (62.5)", "0.53"]
  ],
  "notes": "",
  "verified": false
}
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `table_id` | string | Copied from `manifest.json` -- do not generate |
| `paper` | string | Paper short name from manifest |
| `item_key` | string | Zotero item key from manifest |
| `page_num` | integer | 1-indexed page number from manifest |
| `table_index` | integer | Table index within the paper from manifest |
| `caption` | string | Table caption as it appears in the image (or from manifest if not visible in crop) |
| `headers` | array of strings | Column header labels, left to right |
| `rows` | array of arrays | Data rows, each an array of cell strings, left to right |
| `notes` | string | Footnote content, readability issues, spanning header structure, or other observations |
| `verified` | boolean | Always `false` during drafting -- set to `true` only during human review |

## Complete Example

Given a table image showing:

```
Table 3. Baseline Characteristics by Treatment Group

Variable          | Placebo (n=100) | Active (n=98) | p-value
------------------+-----------------+---------------+--------
Age, years        | 55.2 (12.1)     | 54.8 (11.9)   | 0.82
Female, n (%)     | 52 (52.0)       | 49 (50.0)     | 0.78
BMI, kg/m2        | 28.4 (5.2)      | 27.9 (4.8)    | 0.47
  Panel A: Comorbidities
Hypertension      | 62 (62.0)       | 58 (59.2)     | 0.69
Diabetes          | 24 (24.0)       | 22 (22.4)     | 0.80

Note: Values are mean (SD) or n (%). p-values from t-test or chi-square.
```

The ground truth JSON would be:

```json
{
  "table_id": "ABCKEY_table_3",
  "paper": "example-paper",
  "item_key": "ABCKEY",
  "page_num": 7,
  "table_index": 2,
  "caption": "Table 3. Baseline Characteristics by Treatment Group",
  "headers": ["Variable", "Placebo (n=100)", "Active (n=98)", "p-value"],
  "rows": [
    ["Age, years", "55.2 (12.1)", "54.8 (11.9)", "0.82"],
    ["Female, n (%)", "52 (52.0)", "49 (50.0)", "0.78"],
    ["BMI, kg/m2", "28.4 (5.2)", "27.9 (4.8)", "0.47"],
    ["Panel A: Comorbidities", "", "", ""],
    ["Hypertension", "62 (62.0)", "58 (59.2)", "0.69"],
    ["Diabetes", "24 (24.0)", "22 (22.4)", "0.80"]
  ],
  "notes": "Footnote present: Values are mean (SD) or n (%). p-values from t-test or chi-square.",
  "verified": false
}
```

Key points illustrated in this example:
- The sub-header row "Panel A: Comorbidities" is included as a data row with empty cells for the other columns.
- The footnote "Note: Values are mean (SD)..." is NOT a row; it is recorded in `notes`.
- All numeric values are transcribed exactly as displayed.
- `verified` remains `false` until human review.

---

# Review Phase: Human Verification Procedure

After the drafting agents have populated all `table_*_gt.json` files, the human reviewer verifies each table against the original paper. This section describes the step-by-step review workflow conducted in Claude Code.

## Setup

1. Open the paper PDF on a second monitor (or in a PDF viewer on one side of the screen).
2. Open Claude Code in your terminal.

## Review Workflow

For each paper in the workspace, follow these steps:

### Step 1: Display the Draft Ground Truth

Ask the agent to read and display each ground truth file as a markdown table:

```
Read tests/ground_truth_workspace/<PAPER_DIR>/table_<idx>_gt.json and display
the headers and rows as a markdown table. Also show the caption and any notes.
```

The agent will render the data as a readable markdown table in the terminal.

### Step 2: Compare Against the Paper

Look at the corresponding table in the paper PDF on your second monitor. Compare:
- Are all column headers correct?
- Are all data rows present?
- Are cell values exact (no transpositions, missing decimals, wrong signs)?
- Are sub-header rows included where they should be?
- Are footnotes excluded from rows and recorded in notes?

### Step 3: Provide Corrections Conversationally

If you find errors, give corrections in natural language:

```
table 3, row 2, col 4 should be "0.047" not "0.47"
```

```
table 1 is missing a row between rows 3 and 4: ["Panel B: Females", "", "", ""]
```

```
table 2, header col 3 should be "95% CI" not "95%CI"
```

The agent will edit the GT JSON file and re-display the corrected table for confirmation.

### Step 4: Confirm and Verify

When the table matches the paper exactly:

```
table 3 looks correct, mark it as verified
```

The agent sets `"verified": true` in the GT JSON file.

### Step 5: Repeat

Continue through all tables in the paper, then move to the next paper. You can batch corrections:

```
For paper laird-fick-polyps:
- table 0 is correct, verify it
- table 1, row 5 col 2: change "12.3" to "12.5"
- table 2 is correct, verify it
```

## Loading Verified Ground Truth

After reviewing all tables (or a batch), load the verified entries into the ground truth database:

```bash
"./.venv/Scripts/python.exe" tests/load_ground_truth.py
```

This scans all paper directories for `table_*_gt.json` files with `"verified": true` and inserts them into `tests/ground_truth.db`. The script is idempotent: re-running it updates existing entries without duplication.

Output shows a summary:
```
Loaded: 45
Skipped (unverified): 12
Done.
```

## Tips

- Review in batches by paper to maintain context (you have the PDF open already).
- For tables where the image crop is ambiguous, open the PDF directly and cross-reference.
- Artifact tables (figure_data_table) may not contain meaningful tabular data. If the "table" is actually figure data or a decorative element, set `"headers": []`, `"rows": []`, and add a note: `"notes": "Artifact: figure data table, not a real table"`. Still mark as verified.
- After loading, run the stress test to see ground truth comparison results in the report.
