# zotero-chunk-rag — Project Rules

## Hard Rules

### Never Optimise for "Minimal Refactoring" or "Minimal API Change"

When designing a fix, pick the approach that solves the problem best. Do not
choose a worse approach because it touches fewer files, preserves an existing
function signature, or "minimises refactoring". If the right fix requires
restructuring, restructure. Code exists to serve correctness, not to avoid diffs.

### No Hard-Coded Thresholds

Every numeric threshold in the extraction pipeline MUST be adaptive — computed
from the actual data on the current page or paper. Examples:

- Row clustering tolerance: derive from the actual line spacing on the page, not
  a fixed 5pt constant.
- Column gap detection: derive from the gap distribution of the words in the
  table, not a fixed ratio or minimum.
- Fill rate triggers: derive from the table's own statistics relative to other
  tables on the same page.
- Merge triggers (empty col0 %, sparse row %): derive from the table's structure,
  not global constants.

If you find yourself writing a literal number as a threshold (e.g., `if ratio > 2.0`,
`if fill < 0.55`, `if len(rows) < 6`), STOP. Either:

1. Compute the threshold from the data (preferred), or
2. If you genuinely cannot avoid a fixed number, **present it to the user for
   approval** with at least two alternatives and an explanation of why adaptive
   computation isn't feasible.

This applies to ALL extraction code: `pdf_processor.py`, `_figure_extraction.py`,
`_gap_fill.py`, `section_classifier.py`, and any new modules.

### Tables in Academic Papers Are Not "Structurally Sparse"

Almost no tables in academic papers have genuinely sparse data. When extracted
tables show low fill rates (many empty cells), the cause is almost always an
extraction error:

- **Over-detected columns**: Gap threshold too low → one real column becomes 3-4
  columns, most of which are empty.
- **Inline headers**: Sub-group headings that span the full table width (e.g.
  "Panel A: Males") appear as rows with content only in column 0.
- **Continuation rows**: Multi-line cell content split across rows, where the
  continuation row has content only in the column being continued.

Do NOT report low fill rates as "structural sparsity", "inherent to the PDF", or
"the table genuinely has many empty cells". Investigate the actual cause. If a
table has < 70% fill, something is wrong with the extraction.

### Never Dismiss Problems as "Inherent to the PDF" or "PyMuPDF Limitation"

PDFs are not deficient — if they were, human readers wouldn't use them. PyMuPDF's
high-level functions (`find_tables()`, `get_text()`) do have limitations, but PyMuPDF
also provides low-level tools (`get_text("words")`, `get_text("dict")`, `get_text("rawdict")`,
`get_image_info()`, `get_drawings()`, page geometry, font metadata) that can work
around those limitations.

When a `find_tables()` result is wrong:
- Re-extract from word positions (`page.get_text("words")`)
- Use font metadata (`get_text("dict")`) to detect headers, footnotes, captions
- Use drawing/line data (`get_drawings()`) to find actual table rules
- Use block structure to detect boundaries

The correct response to "find_tables() merges two tables" is "detect the merge and
split using word positions and caption detection", not "this is a PyMuPDF limitation".

### Performance Testing

**The stress test is the ground truth.** Synthetic unit tests validate individual
functions but tell you nothing about whether the pipeline actually works on real
papers.

#### How to run it

```bash
"./.venv/Scripts/python.exe" tests/stress_test_real_library.py
```

This takes ~2-5 minutes. It:
1. Loads 10 specific papers from the user's live Zotero library (corpus defined
   in `CORPUS` at top of file)
2. Extracts each through the full pipeline (text, tables, figures, sections)
3. Indexes into a temp ChromaDB with local embeddings
4. Runs ~290 assertions across extraction quality, search accuracy, table/figure
   search, metadata filtering, and context expansion
5. Produces `STRESS_TEST_REPORT.md` and `_stress_test_debug.db`

#### The debug database

`_stress_test_debug.db` is a SQLite database containing every extracted artifact
from the stress test run. Tables:

| Table | Contents |
|-------|----------|
| `papers` | Per-paper: pages, chunks, grade, completeness fields, full markdown |
| `extracted_tables` | Every table: caption, headers_json, rows_json, fill_rate, bbox, artifact_type, rendered markdown |
| `extracted_figures` | Every figure: caption, bbox, image_path, reference_context |
| `sections` | Every section span: label, heading, char offsets, confidence |
| `chunks` | Every text chunk: section, page, text, char offsets |
| `pages` | Per-page markdown |
| `test_results` | Every assertion: test_name, paper, passed, detail, severity |
| `run_metadata` | Timestamps, counts, timings |

**Use this database to audit extraction quality.** Example queries:

```sql
-- Tables with low fill rates (likely broken extraction)
SELECT short_name, caption, fill_rate, num_rows, num_cols
FROM extracted_tables JOIN papers USING(item_key)
WHERE fill_rate < 0.5 AND artifact_type IS NULL;

-- Find decimal displacement (T1) — cells starting with "."
SELECT short_name, caption, rows_json
FROM extracted_tables JOIN papers USING(item_key)
WHERE rows_json LIKE '%".%' AND artifact_type IS NULL;

-- Papers with unmatched table captions (extraction missed a table)
SELECT short_name, unmatched_table_captions
FROM papers WHERE unmatched_table_captions != '[]';

-- All MAJOR failures
SELECT test_name, paper, detail FROM test_results
WHERE passed = 0 AND severity = 'MAJOR';
```

#### When to run it

Run the stress test after any change to the extraction pipeline. A change that
passes unit tests but regresses the stress test is a bad change. The stress test
verdict (MAJOR failures = unreliable, minor = rough edges, all pass = reliable)
is the acceptance criterion.

#### Severity rules

- **MAJOR**: Orphan tables/figures (extraction missed something the paper contains),
  search failures (researcher can't find what's in the paper), data corruption
  (table values wrong enough to mislead).
- **MINOR**: Section detection misses, abstract detection misses, chunk count
  deviations. Annoying but won't cause a researcher to reach wrong conclusions.

## Architecture Notes

### Key files

| File | Role |
|------|------|
| `src/zotero_chunk_rag/pdf_processor.py` | Main extraction pipeline, table extraction, cell cleaning, quality grading |
| `src/zotero_chunk_rag/_figure_extraction.py` | Figure extraction, caption detection, caption-to-object matching |
| `src/zotero_chunk_rag/_gap_fill.py` | Post-extraction recovery pass for orphan captions |
| `src/zotero_chunk_rag/section_classifier.py` | Section heading classification |
| `src/zotero_chunk_rag/models.py` | Dataclasses: ExtractedTable, ExtractedFigure, SectionSpan, etc. |
| `src/zotero_chunk_rag/_reference_matcher.py` | Maps figures/tables to body-text chunks that cite them |
| `tests/stress_test_real_library.py` | 10-paper stress test (run directly, not via pytest) |
| `table_shortcomings.md` | Current audit of table extraction problems and threshold inventory |

### Known shortcomings

See `table_shortcomings.md` for the full inventory of:
- T1-T8: Specific output quality bugs
- D1-D7: Hard-coded threshold groups that need to be made adaptive
