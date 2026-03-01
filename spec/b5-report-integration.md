# Phase B5: Report Integration

## Overview

Add a "Paddle Extraction Report" section to `STRESS_TEST_REPORT.md` that
shows per-table PaddleOCR accuracy metrics and, when vision results also
exist, a side-by-side comparison table.

---

## Wave 1: Report Generation

### Task 1.1: Add paddle report builder

- **Description**: Create a function that generates a markdown report section
  from paddle extraction results and GT diffs. When vision GT diffs also
  exist in the debug DB, produce a side-by-side comparison table showing
  both engines' accuracy per GT table.
- **Files to modify**:
  - `tests/stress_test_real_library.py` — add:
    - `_build_paddle_report(paddle_gt_diffs, vision_gt_diffs=None) -> str`:
      - **Header**: `## Paddle Extraction Report`
      - **Engine info**: engine name, total tables extracted, orphan count
      - **Per-table results table** (markdown):
        `| Table ID | Caption | Cell Accuracy | Fuzzy Accuracy | Splits | Merges | Cell Diffs |`
      - **Summary stats**: mean accuracy, median accuracy, min/max accuracy,
        tables with >90% accuracy, tables with <50% accuracy
      - **Side-by-side comparison** (only when `vision_gt_diffs` provided):
        `| Table ID | Vision Acc. | Paddle Acc. | Delta | Better Engine |`
        - Delta = paddle - vision (positive = paddle wins)
        - Better Engine = "paddle" / "vision" / "tie" (within 1%)
      - **Comparison summary**: tables where paddle wins, ties, loses;
        mean delta
      - If no paddle results: returns section with "No paddle extraction
        results available."
    - Append output of `_build_paddle_report()` to the report markdown
      string before writing `STRESS_TEST_REPORT.md`
- **Tests**:
  - `tests/test_paddle_extract.py::TestReportGeneration::test_report_format` —
    given 3 mock GT diff dicts with known accuracies, assert output
    contains `## Paddle Extraction Report`, per-table markdown table,
    summary stats with correct mean
  - `tests/test_paddle_extract.py::TestReportGeneration::test_report_comparison` —
    given paddle and vision diffs for same table IDs, assert side-by-side
    table present with correct deltas and "Better Engine" labels
  - `tests/test_paddle_extract.py::TestReportGeneration::test_report_no_results` —
    empty diffs list → output contains "No paddle extraction results
    available."
  - `tests/test_paddle_extract.py::TestReportGeneration::test_report_no_vision` —
    paddle diffs present but `vision_gt_diffs=None` → no comparison
    section, per-table results still present
- **Acceptance criteria**:
  - Report section appended to existing `STRESS_TEST_REPORT.md` after the
    GT comparison section
  - Markdown renders correctly in standard viewers (tables aligned,
    headers present)
  - Comparison section only generated when both vision and paddle GT diffs
    exist for overlapping table IDs
  - Report function is pure (reads diffs from arguments, not from DB
    directly — caller passes data)
