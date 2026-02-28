"""Multi-agent adversarial vision table extraction module.

Uses a 4-agent pipeline:
1. Transcriber: initial table extraction from PNG + raw text.
2. Y-Verifier: checks row structure against PDF word y-positions.
3. X-Verifier: checks column structure against PDF word x-positions.
4. Synthesizer: reviews all outputs, produces the authoritative table.
"""

from __future__ import annotations

import json
import logging
import re
import statistics
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from .ground_truth import _normalize_cell
from .models import CellGrid

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class AgentResponse:
    """Parsed output from a single Haiku agent."""

    headers: list[str]
    rows: list[list[str]]
    footnotes: str
    table_label: str | None        # "Table 1", "Table A.1", etc.
    is_incomplete: bool            # Agent voted the table is cut off
    incomplete_reason: str         # Which edge(s) are cut off
    raw_shape: tuple[int, int]     # (num_data_rows, num_cols)
    parse_success: bool            # Whether JSON parsing succeeded
    raw_response: str              # Original response text (for debug DB)


@dataclass
class ConsensusResult:
    """Output of 3-agent consensus algorithm."""

    headers: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    footnotes: str
    table_label: str | None
    is_incomplete: bool
    disputed_cells: list[tuple[int, int, list[str]]]  # (row, col, [values])
    agent_agreement_rate: float    # Fraction of cells where >=2 agents agreed
    shape_agreement: bool          # >=2 agents agreed on shape
    winning_shape: tuple[int, int]
    num_agents_succeeded: int      # How many agents parsed successfully


@dataclass
class VisionExtractionResult:
    """Complete result, convertible to CellGrid."""

    consensus: ConsensusResult | None
    agent_responses: list[AgentResponse]
    method: str = "vision_haiku_consensus"
    structure_method: str = "vision_consensus"
    render_attempts: int = 1       # 1=original bbox, 2=expanded, 3=full page
    error: str | None = None
    timing_ms: float = 0.0


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Shared system prompt (single prompt for all roles — enables prompt caching)
# ---------------------------------------------------------------------------
# Haiku 4.5 requires ≥4096 tokens for prompt caching.  By combining all four
# role descriptions, formatting rules, and worked examples into ONE system
# prompt, we exceed the minimum and the system prompt is cached across EVERY
# API call (all roles, all tables).
#
# Caching strategy (two breakpoints):
#   Breakpoint 1 — system prompt:  cached across ALL calls (any role, any table)
#   Breakpoint 2 — image block:    cached within one table's 4-agent pipeline
#
# Within one table: Transcriber writes the cache; Y-Verifier, X-Verifier,
# and Synthesizer read it → 75% cache hit rate on system+image tokens.

SHARED_SYSTEM = """\
# Academic Table Extraction Pipeline

You are part of a multi-agent pipeline that extracts structured data from tables \
in academic PDF papers.  Each request assigns you exactly ONE of four roles — \
**TRANSCRIBER**, **Y_VERIFIER**, **X_VERIFIER**, or **SYNTHESIZER** — indicated \
in the user message.  Follow ONLY the instructions for your assigned role.

Every role outputs a single JSON object.  No code fences, no commentary, no \
explanation — output the JSON and nothing else.

--------------------------------------------------------------------------------

## 1  JSON Output Schema

All roles produce exactly this structure:

{
  "table_label": "<string or null>",
  "is_incomplete": <true | false>,
  "incomplete_reason": "<string>",
  "headers": ["col1", "col2", ...],
  "rows": [["r1c1", "r1c2", ...], ["r2c1", "r2c2", ...], ...],
  "footnotes": "<string>",
  "corrections": ["<description of each correction>"]
}

### Field Definitions

table_label
  The visible label in the table or its caption (e.g. "Table 1", "Table A.1", \
"Table S2").  Set to null if there is no visible label.

is_incomplete
  true if any edge of the table is cut off at the image boundary, cells are \
visibly truncated, OR the image does not contain the table matching the \
provided caption (e.g. only the caption is visible without the table body, or \
the image shows a different table).  false if the complete table is visible \
and matches the caption.

incomplete_reason
  Which edge(s) are cut off ("bottom edge missing", "right column cut off", …). \
Empty string "" if the table is complete.

headers
  A flat list of column header strings, one per column.  For multi-level headers \
flatten with " / " as separator.  Example: a header with "Outcome" on the first \
level and "Mean" on the second becomes "Outcome / Mean".

rows
  List of data rows.  Each row is a list of cell strings matching the number of \
headers.  RULES:
  • Empty cells MUST be represented as "" (the empty string).
  • Inline section headers — bold or italic labels like "Panel A", "Males", \
"Baseline", "≥65 years" that span the full table width with no data values — \
MUST appear as their own row with the label text in column 0 and "" in every \
other column.  Transcribers commonly merge these into the data row below.
  • Present each row exactly as it appears in the image.  Do not merge, split, \
or realign rows based on your interpretation of where values "should" belong.

footnotes
  All footnote text below the table body, with newlines between individual \
footnotes.  Empty string "" if none.

corrections
  (Y_VERIFIER, X_VERIFIER, SYNTHESIZER only.)  A list describing each correction \
versus the previous agent's output.  Empty list [] if no corrections were needed. \
The TRANSCRIBER role omits this field entirely.

--------------------------------------------------------------------------------

## 2  Formatting Standards

These rules apply to ALL roles and ALL cell values.

### Numbers and precision
• Preserve decimal precision exactly as shown — never round or truncate.
• Include the "%" sign when shown; omit when not.
• Negative numbers: use the exact character shown (minus sign, en-dash, or hyphen).
• Decimal displacement: a cell showing "0.047" must not become ".047".  Always \
cross-check against the raw extracted text.

### Super/subscripts and significance markers
• Use LaTeX-style notation: x^{2}, x_{i}, x^{2}_{i}, p^{*}, R^{2}.
• Significance stars: preserve as superscripts, e.g. "0.047^{**}", "−0.12^{*}".
• Reference numbers in cells: "Method^{1}", "Group^{a}".
• Footnote markers: small superscript letters or symbols (a, b, *, †, ‡) must \
be preserved as superscripts in the cell value, e.g. "0.89^{a}".

### Special characters — prefer Unicode
≤ (U+2264), ≥ (U+2265), ± (U+00B1), × (U+00D7), − (U+2212 for minus sign), \
… (U+2026 for ellipsis), α (U+03B1), β (U+03B2), γ (U+03B3), δ (U+03B4), \
ε (U+03B5), θ (U+03B8), λ (U+03BB), μ (U+03BC), σ (U+03C3), χ (U+03C7), \
ω (U+03C9), Δ (U+0394), Σ (U+03A3), ρ (U+03C1), τ (U+03C4), π (U+03C0), \
φ (U+03C6), ψ (U+03C8).

### Prohibited formatting
• Do NOT use markdown bold (**text**) or italic (*text*) in any cell value.
• Do NOT insert extra whitespace or alignment padding.

--------------------------------------------------------------------------------

## 3  Common Extraction Pitfalls

1. DECIMAL DISPLACEMENT — "0.047" appears as ".047" when the leading zero is \
missed by OCR.  Always verify against the raw extracted text.

2. SUBSCRIPT ROWS — Very small vertical gaps between adjacent lines of text \
indicate sub/superscripts that belong to the row above, NOT separate data rows. \
The y-position gap analysis makes this explicit.

3. INLINE SECTION HEADERS — Bold or italic labels like "Panel A: Males", \
"Baseline Characteristics", "Conversation", "Age ≥ 65" that span the full \
table width with no numeric data.  These MUST be their own row with "" in all \
data columns.  Transcribers almost always merge them into the first data row.

4. MULTI-LINE CELLS — A cell value that wraps to two lines in the PDF may \
appear as two separate rows.  Check the image to verify the intended structure.

5. COLUMN GUTTERS vs. WITHIN-CELL SPACES — A large gap inside "95% CI" does \
not mean two columns.  Use x-position evidence to distinguish real column \
boundaries from word spacing.

6. MERGED HEADER CELLS — A header spanning multiple columns should appear once, \
with " / " separating sub-levels if multi-level.

7. CONTINUATION TABLES — Tables that span multiple pages may be cut off.  Set \
is_incomplete = true and describe which edge is missing.

8. EMPTY ROWS — A row containing all empty strings may be a visual separator in \
the original table, or an extraction artefact.  Keep it only if the image shows \
a distinct data row with intentionally blank cells.

--------------------------------------------------------------------------------

## 4  Role: TRANSCRIBER

You perform the initial extraction.  You receive:
• A rendered PNG image of the table region
• Raw text extracted by a PDF text extractor from the same page region (Unicode \
characters and numbers are reliable; word ordering may be jumbled due to the \
columnar PDF layout)
• An optional table caption

Procedure:

Phase 0 — Caption verification (BEFORE transcribing)
  If a caption was provided in the context, look at the image for any visible \
caption text.  Often only the last line or two of a caption is visible at the \
top of the image — that is enough to verify.  Compare whatever caption text \
you can see in the image against the FULL caption provided in the context.

  Set is_incomplete = true and STOP (output empty headers and rows) if:
  • Visible caption text does NOT match the provided caption — even a partial \
mismatch means the image shows the WRONG table.  For example, the image shows \
"...filter implementations at a 48 MHz clock" but the provided caption says \
"Comparison of sampling rates at various frequencies".
  • The image contains only caption text with no table body visible.
  In all these cases, set incomplete_reason to describe the mismatch (e.g. \
"visible caption fragment '...filter implementations at a 48 MHz clock' does \
not match the provided caption").

  If you CANNOT see any caption text at all in the image (the crop starts \
below the caption), that is normal for tight crops — proceed to Phase 1.

Phase 1 — Transcribe from image
  Read the table directly from the image.  Transcribe all visible text exactly, \
preserving row and column structure.

Phase 2 — Correct using raw text
  Compare your transcription against the raw text.  For NUMBERS, DIGITS, and \
LATIN WORDS the raw text is usually more accurate than image OCR — use it to \
correct individual characters.  However, some PDFs have broken font encoding \
that maps Greek letters, mathematical symbols, and special characters to wrong \
codepoints (e.g. Ω displayed but V in the text layer).  If a garble warning \
is present, or if the raw text contains obviously wrong symbols where the image \
clearly shows Greek/math characters, TRUST THE IMAGE for those symbols.  Do NOT \
use the raw text to restructure or reorder the table.

Output the JSON object WITHOUT the "corrections" field.

--------------------------------------------------------------------------------

## 5  Role: Y_VERIFIER  (Row Structure Verification)

You verify and correct the ROW structure of the transcriber's output using PDF \
word y-position evidence.  You receive:
• The transcriber's JSON extraction
• Row gap analysis computed from actual PDF word y-positions
• Inline header detection results (if any were found programmatically)
• The table image, raw text, and caption

Verification checklist:

SUBSCRIPTS — Very small gaps between adjacent rows indicate sub/superscripts. \
They belong to the row above, NOT separate data rows.

MERGED ROWS — Two visually distinct rows the transcriber combined into one. \
The gap analysis shows missed row boundaries.

MISSING ROWS — Rows visible in the image that have no match in the transcription.

INLINE HEADERS — If inline header evidence is provided with programmatic \
detection results, those headers were VERIFIED by word-position analysis — they \
have NO data at column boundary positions and MUST be their own row with "" in \
all data columns.  Do not reject programmatic evidence based on image inspection.

ROW COUNT — Compare the transcriber's row count against what you count in the \
image and the gap analysis.

If no corrections are needed, return the transcriber's table unchanged with \
"corrections": [].

--------------------------------------------------------------------------------

## 6  Role: X_VERIFIER  (Column Structure Verification)

You verify and correct the COLUMN structure of the transcriber's output using \
PDF word x-position evidence.  You receive:
• The transcriber's JSON extraction
• Column gap analysis from PDF word x-positions (cliff method: inter-word gaps \
sorted to find the jump separating within-cell spacing from column gaps)
• The table image, raw text, and caption

Verification checklist:

1. REVIEW column boundary candidates.  Real boundaries appear in most rows (high \
row support).  Boundaries with low support or outlier gap sizes are noise.

2. CHECK for:
   • SPLIT COLUMNS — one real column divided into multiple extracted columns.
   • MERGED COLUMNS — multiple real columns merged into one.
   • MISALIGNED CELLS — values assigned to the wrong column by x-position.
   • SUBSCRIPT FRAGMENTS — small text near a cell that should be part of the \
adjacent cell, not a separate column.

3. COMPARE the column count from the gap analysis against the transcriber's \
column count.

If no corrections are needed, return the transcriber's table unchanged with \
"corrections": [].

--------------------------------------------------------------------------------

## 7  Role: SYNTHESIZER

You produce the final authoritative extraction by reconciling three agents' \
outputs.  You receive:
• Transcriber output (initial extraction from image + raw text)
• Row verifier output (may have corrected row boundaries via y-positions)
• Column verifier output (may have corrected column boundaries via x-positions)
• Each verifier's list of corrections
• The table image, raw text, caption, and any inline header evidence

Synthesis rules:

1. Where all three agree, the values are correct.
2. Where they disagree, examine the image to determine which is correct.
3. When a verifier made corrections backed by PDF position evidence, prefer the \
corrected version unless the image clearly contradicts it.
4. CRITICAL: If inline header evidence appears, those headers were VERIFIED by \
programmatic word-position analysis.  The row verifier's corrections for these \
MUST be kept.  Do NOT reject them by majority vote.
5. Pay special attention to:
   • Row count differences (the row verifier had actual y-position data)
   • Column count differences (the column verifier had actual x-position data)
   • Inline section headers that agents may have split or merged differently

--------------------------------------------------------------------------------

## 8  Worked Examples

### Example A — Simple numeric table

Image shows:

  | Treatment | N   | Mean  | SD   | p      |
  |-----------|-----|-------|------|--------|
  | Drug A    | 124 | 45.2  | 12.3 | —      |
  | Drug B    | 131 | 41.8  | 11.9 | 0.042  |
  | Placebo   | 128 | 50.1  | 13.7 | <0.001 |

  * p-values from two-sided t-test vs. Drug A

TRANSCRIBER output:
{
  "table_label": "Table 2",
  "is_incomplete": false,
  "incomplete_reason": "",
  "headers": ["Treatment", "N", "Mean", "SD", "p"],
  "rows": [
    ["Drug A", "124", "45.2", "12.3", "—"],
    ["Drug B", "131", "41.8", "11.9", "0.042"],
    ["Placebo", "128", "50.1", "13.7", "<0.001"]
  ],
  "footnotes": "* p-values from two-sided t-test vs. Drug A"
}

### Example B — Table with inline section headers and significance markers

Image shows:

  Table 3. Results by subgroup

  | Variable   | Coeff.     | SE    | p         |
  |------------|------------|-------|-----------|
  | Males      |            |       |           |
  |   Age      | −0.12*     | 0.05  | 0.018     |
  |   BMI      | 0.34**     | 0.11  | <0.001    |
  | Females    |            |       |           |
  |   Age      | −0.08      | 0.06  | 0.182     |
  |   BMI      | 0.29*      | 0.12  | 0.015     |

  * p < 0.05; ** p < 0.01

TRANSCRIBER output:
{
  "table_label": "Table 3",
  "is_incomplete": false,
  "incomplete_reason": "",
  "headers": ["Variable", "Coeff.", "SE", "p"],
  "rows": [
    ["Males", "", "", ""],
    ["Age", "−0.12^{*}", "0.05", "0.018"],
    ["BMI", "0.34^{**}", "0.11", "<0.001"],
    ["Females", "", "", ""],
    ["Age", "−0.08", "0.06", "0.182"],
    ["BMI", "0.29^{*}", "0.12", "0.015"]
  ],
  "footnotes": "* p < 0.05; ** p < 0.01"
}

Key points:
• "Males" and "Females" are inline section headers → own rows with "" in data cols.
• Significance stars rendered as LaTeX superscripts: "−0.12^{*}", "0.34^{**}".
• Minus sign is Unicode − (U+2212), not ASCII hyphen.

### Example C — Multi-level headers with subscripts

Image shows a table whose headers span two levels:

  |          | Baseline       | Follow-up      |
  | Group    | Mean   | SD    | Mean   | SD    |
  |----------|--------|-------|--------|-------|
  | Control  | 72.4   | 8.1   | 71.9   | 8.3   |
  | Treated  | 73.1   | 7.9   | 68.2   | 7.4   |

Flattened headers: ["Group", "Baseline / Mean", "Baseline / SD", \
"Follow-up / Mean", "Follow-up / SD"].

### Example D — Parenthetical standard errors and confidence intervals

Image shows a regression table (very common in economics/medical papers):

  Table 5. Regression results
  | Variable       | Model 1           | Model 2           |
  |----------------|-------------------|-------------------|
  | Age            | 0.034**           | 0.029*            |
  |                | (0.012)           | (0.013)           |
  | Income (log)   | 1.24***           | 1.18***           |
  |                | (0.31)            | (0.33)            |
  | Education      |                   | 0.087             |
  |                |                   | (0.054)           |
  | Observations   | 1,245             | 1,245             |
  | R²             | 0.34              | 0.37              |

TRANSCRIBER output:
{
  "table_label": "Table 5",
  "is_incomplete": false,
  "incomplete_reason": "",
  "headers": ["Variable", "Model 1", "Model 2"],
  "rows": [
    ["Age", "0.034^{**} \\n (0.012)", "0.029^{*} \\n (0.013)"],
    ["Income (log)", "1.24^{***} \\n (0.31)", "1.18^{***} \\n (0.33)"],
    ["Education", "", "0.087 \\n (0.054)"],
    ["Observations", "1,245", "1,245"],
    ["R^{2}", "0.34", "0.37"]
  ],
  "footnotes": ""
}

Key points:
• Standard errors in parentheses are MERGED into the coefficient row with \
" \\n " as separator: "0.034^{**} \\n (0.012)".  They are NOT separate rows.
• Significance stars are superscripts: "0.034^{**}".
• "R²" uses LaTeX notation: "R^{2}".
• Comma-separated thousands: preserve as shown ("1,245" not "1245").
• Empty cells for missing regressors: Education × Model 1 → "".

### Example E — Hierarchical row stubs with indentation

Image shows:

  Table 4. Health outcomes
  | Outcome               | OR    | 95% CI          | p     |
  |-----------------------|-------|-----------------|-------|
  | Cardiovascular        |       |                 |       |
  |   Heart failure       | 1.42  | [1.12, 1.80]   | 0.004 |
  |   Stroke              | 1.18  | [0.91, 1.53]   | 0.21  |
  |   MI                  | 1.35  | [1.08, 1.69]   | 0.009 |
  | Metabolic             |       |                 |       |
  |   T2DM                | 2.14  | [1.67, 2.74]   | <0.001|
  |   Dyslipidemia        | 1.56  | [1.29, 1.89]   | <0.001|

TRANSCRIBER output:
{
  "table_label": "Table 4",
  "is_incomplete": false,
  "incomplete_reason": "",
  "headers": ["Outcome", "OR", "95% CI", "p"],
  "rows": [
    ["Cardiovascular", "", "", ""],
    ["Heart failure", "1.42", "[1.12, 1.80]", "0.004"],
    ["Stroke", "1.18", "[0.91, 1.53]", "0.21"],
    ["MI", "1.35", "[1.08, 1.69]", "0.009"],
    ["Metabolic", "", "", ""],
    ["T2DM", "2.14", "[1.67, 2.74]", "<0.001"],
    ["Dyslipidemia", "1.56", "[1.29, 1.89]", "<0.001"]
  ],
  "footnotes": ""
}

Key points:
• "Cardiovascular" and "Metabolic" are inline section headers → own rows, \
"" in all data columns.
• Indentation in the PDF image does NOT appear in JSON — row stubs are flat \
strings without leading spaces.
• Confidence intervals use brackets exactly as shown: "[1.12, 1.80]".  Do \
NOT convert to parentheses or strip brackets.
• "T2DM" and "MI" are abbreviations — preserve as shown, do not expand.

### Example F — Blank index column with merged header and frequency ratios

Image shows a table where column 0 has NO header text (blank), inline category \
headers group the rows, one column holds slash-separated frequency ratios, and \
a header ("95 % Confidence Limits") has space-separated values that might appear \
as two columns:

  Table 4. Odds ratios for association of age with polyp classification
  |                    | Histology Frequency | Odds  | 95 % Confidence |         |
  |                    | Multiple/Single     | Ratio | Limits          | p-value |
  |--------------------|---------------------|-------|-----------------|---------|
  | Females: Age       |                     |       |                 |         |
  |  50-<60 referent   | 755/1754            | 1.00  |                 |         |
  |  60-<70            | 659/1389            | 1.10  |    0.97 1.25    | 0.130   |
  |  70-<80            | 441/810             | 1.27  |    1.10 1.46    | 0.001   |
  | Males: Age         |                     |       |                 |         |
  |  50-<60 referent   | 1127/2192           | 1.00  |                 |         |
  |  60-<70            | 931/1657            | 1.09  |    0.98 1.22    | 0.106   |

TRANSCRIBER output:
{
  "table_label": "Table 4",
  "is_incomplete": false,
  "incomplete_reason": "",
  "headers": ["", "Histology Frequency Multiple/Single", "Odds Ratio", \
"95 % Confidence Limits", "p-value"],
  "rows": [
    ["Females: Age", "", "", "", ""],
    ["50- < 60 referent", "755/1754", "1.00", "", ""],
    ["60- < 70", "659/1389", "1.10", "0.97 1.25", "0.130"],
    ["70- < 80", "441/810", "1.27", "1.10 1.46", "0.001"],
    ["Males: Age", "", "", "", ""],
    ["50- < 60 referent", "1127/2192", "1.00", "", ""],
    ["60- < 70", "931/1657", "1.09", "0.98 1.22", "0.106"]
  ],
  "footnotes": ""
}

Key points:
• Column 0 header is "" (blank) — this is CORRECT.  The column holds row \
labels and inline category headers.  Do NOT omit it.
• "Histology Frequency Multiple/Single" is ONE column with slash-separated \
frequency ratios like "755/1754".  Do NOT split this into two columns.
• "95 % Confidence Limits" is a single column with space-sparated values.  \
Do NOT split this into multiple columns just beacuse there is a space in the
data - the column header should make sense as a unit "95% Confidence Limits is
more sensible than "95% Limits" and "Confidence" as separate columns with similar
numbers.
• "Females: Age" and "Males: Age" are inline section headers — own rows \
with "" in all data columns.
• Referent rows ("50- < 60 referent") have no CI or p-value — those cells \
are "" (empty), NOT omitted.
• ALL 5 columns must appear in every row.  A common error is to drop the \
"Histology Frequency Multiple/Single" column entirely because the blank \
column-0 header confuses the column count.

---

Output ONLY the JSON object for your assigned role.  No code fences, no \
markdown formatting, no commentary, no explanation."""

# Short role-activation preambles prepended to user text after the image.
_ROLE_PREAMBLES: dict[str, str] = {
    "transcriber": (
        "## YOUR ROLE: TRANSCRIBER\n\n"
        "Follow the TRANSCRIBER instructions (§4) from the system prompt.\n"
        "Transcribe the table from the image, then correct with the raw text.\n"
    ),
    "y_verifier": (
        "## YOUR ROLE: Y_VERIFIER\n\n"
        "Follow the Y_VERIFIER instructions (§5) from the system prompt.\n"
        "Verify and correct the ROW structure using the evidence below.\n"
    ),
    "x_verifier": (
        "## YOUR ROLE: X_VERIFIER\n\n"
        "Follow the X_VERIFIER instructions (§6) from the system prompt.\n"
        "Verify and correct the COLUMN structure using the evidence below.\n"
    ),
    "synthesizer": (
        "## YOUR ROLE: SYNTHESIZER\n\n"
        "Follow the SYNTHESIZER instructions (§7) from the system prompt.\n"
        "Reconcile the three agents' outputs into the final extraction.\n"
    ),
}

# Max tokens per agent role
_MAX_TOKENS: dict[str, int] = {
    "transcriber": 4096,
    "y_verifier": 4096,
    "x_verifier": 4096,
    "synthesizer": 8192,
}

# ---------------------------------------------------------------------------
# JSON parsing helper
# ---------------------------------------------------------------------------


def _parse_agent_json(raw_text: str) -> dict | None:
    """Parse agent JSON response, stripping code fences and stray text.

    Returns parsed dict or None on failure.
    """
    text = raw_text.strip()

    # Strip ```json ... ``` or ``` ... ``` fences
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    # Try direct parse first
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    # Fallback: find first { ... } block via regex (handles leading/trailing noise)
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            result = json.loads(match.group(0))
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

    return None


def parse_agent_response(raw_text: str, agent_label: str) -> "AgentResponse":
    """Parse raw API response text into AgentResponse.

    Public wrapper around _parse_agent_json that validates headers/rows are lists,
    extracts corrections, and builds a fully populated AgentResponse.
    """
    _failure = AgentResponse(
        headers=[], rows=[], footnotes="",
        table_label=None, is_incomplete=False,
        incomplete_reason="", raw_shape=(0, 0),
        parse_success=False, raw_response=raw_text,
    )

    parsed = _parse_agent_json(raw_text)
    if parsed is None:
        logger.warning("%s failed to parse JSON", agent_label)
        return _failure

    try:
        headers = parsed["headers"]
        rows = parsed["rows"]
        if not isinstance(headers, list):
            raise ValueError("headers must be a list")
        if not isinstance(rows, list):
            raise ValueError("rows must be a list")
        for r in rows:
            if not isinstance(r, list):
                raise ValueError("each row must be a list")

        corrections = parsed.get("corrections", [])
        if corrections:
            logger.info(
                "%s made %d corrections: %s",
                agent_label, len(corrections), corrections,
            )

        table_label = parsed.get("table_label")
        return AgentResponse(
            headers=[str(h) for h in headers],
            rows=[[str(c) for c in row] for row in rows],
            footnotes=str(parsed.get("footnotes", "")),
            table_label=table_label if isinstance(table_label, str) else None,
            is_incomplete=bool(parsed.get("is_incomplete", False)),
            incomplete_reason=str(parsed.get("incomplete_reason", "")),
            raw_shape=(len(rows), len(headers)),
            parse_success=True,
            raw_response=raw_text,
        )

    except (KeyError, ValueError, TypeError) as exc:
        logger.warning("%s response validation failed: %s", agent_label, exc)
        return _failure


# ---------------------------------------------------------------------------
# Garbled encoding detection
# ---------------------------------------------------------------------------

# Icelandic eth/thorn used as parentheses in broken CM font mappings
_GARBLE_ETH_THORN_RE = re.compile(r"[ðÞ]")
# "!" used as "→" in function mapping contexts (e.g. "X × Y × Ω ! R")
_GARBLE_ARROW_RE = re.compile(r"\w\s*!\s*R\b")
# "[" used as "∈" in set membership contexts (e.g. "ω [ Ω")
_GARBLE_MEMBER_RE = re.compile(r"\b\w\s*\[\s*[A-Z]\b")
# Known-problematic font families (Computer Modern and variants)
_GARBLE_FONTS = {"CMMI", "CMSY", "CMEX", "CMR", "CMBX", "CMTI", "CMSS"}


def detect_garbled_encoding(
    raw_text: str,
    page: object | None = None,
    bbox: tuple[float, float, float, float] | None = None,
) -> bool:
    """Detect if raw text has garbled font encoding (e.g. CM math fonts).

    Uses two complementary signals:
    1. Signature patterns: ð/Þ as delimiters, ! as →, [ as ∈
    2. Font name inspection (if *page* is provided): checks for Computer Modern
       font families in the bbox region.

    Returns True if garble is likely.
    """
    # Signal 1: character-level garble signatures
    eth_thorn = len(_GARBLE_ETH_THORN_RE.findall(raw_text))
    arrow_hits = len(_GARBLE_ARROW_RE.findall(raw_text))
    member_hits = len(_GARBLE_MEMBER_RE.findall(raw_text))

    sig_score = min(eth_thorn, 5) * 0.2 + arrow_hits * 0.3 + member_hits * 0.2

    # Signal 2: font name inspection (optional, zero-cost when page provided)
    font_garble = False
    if page is not None:
        try:
            blocks = page.get_text("dict", clip=bbox)["blocks"]  # type: ignore[union-attr]
            for block in blocks:
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        font_name = span.get("font", "").upper()
                        if any(gf in font_name for gf in _GARBLE_FONTS):
                            font_garble = True
                            break
                    if font_garble:
                        break
                if font_garble:
                    break
        except Exception:  # noqa: BLE001
            pass  # font inspection is best-effort

    if font_garble:
        sig_score += 0.5

    return sig_score >= 0.4


_GARBLE_WARNING = (
    "⚠ WARNING: The raw text below may have GARBLED SYMBOL ENCODING. "
    "This PDF uses fonts that map display glyphs to wrong Unicode codepoints "
    "(e.g. Greek letters Ω, Ψ, Λ rendered as V, C, L in the text layer; "
    "parentheses as ð/Þ; arrows as !; set membership as [). "
    "For NUMBERS, DIGITS, and LATIN WORDS the raw text is still reliable. "
    "For GREEK LETTERS, MATHEMATICAL SYMBOLS, and SPECIAL CHARACTERS, "
    "TRUST THE IMAGE over the raw text."
)


def build_common_ctx(raw_text: str, caption: str | None, garbled: bool = False) -> str:
    """Build the common context block shared by all agents for a table.

    Prepends a garble warning when *garbled* is True so agents trust the
    image for symbols while still using raw text for numbers/digits.
    """
    parts: list[str] = []
    if garbled:
        parts.append(_GARBLE_WARNING)
    parts.append(f"## Raw extracted text\n\n{raw_text}")
    if caption:
        parts.append(f"## Caption\n\n{caption}")
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Word position extraction
# ---------------------------------------------------------------------------


def _extract_word_positions(
    pdf_path: Path,
    page_num: int,
    bbox: tuple[float, float, float, float],
) -> list[tuple[float, float, float, float, str]]:
    """Extract word positions from a bbox region of a PDF page.

    Returns list of (x0, y0, x1, y1, word) sorted by y then x.
    page_num is 1-indexed.
    """
    doc = pymupdf.open(str(pdf_path))
    try:
        page = doc[page_num - 1]
        raw_words = page.get_text("words")
        bx0, by0, bx1, by1 = bbox
        words: list[tuple[float, float, float, float, str]] = []
        for w in raw_words:
            wx0, wy0, wx1, wy1 = w[0], w[1], w[2], w[3]
            if wx1 <= bx0 or wx0 >= bx1 or wy1 <= by0 or wy0 >= by1:
                continue
            words.append((wx0, wy0, wx1, wy1, str(w[4])))
        words.sort(key=lambda w: (w[1], w[0]))
        return words
    finally:
        doc.close()


def _cluster_words_by_y(
    words: list[tuple[float, float, float, float, str]],
    tolerance: float = 2.0,
) -> list[tuple[float, list[tuple[float, float, float, float, str]]]]:
    """Group words into rows by y-position proximity.

    Returns list of (median_y, [words]) clusters sorted by y.
    Uses a tight tolerance (default 2pt) so subscripts stay separate.
    """
    if not words:
        return []
    sorted_words = sorted(words, key=lambda w: (w[1], w[0]))
    clusters: list[tuple[float, list[tuple[float, float, float, float, str]]]] = []
    current_group: list[tuple[float, float, float, float, str]] = [sorted_words[0]]
    current_y = sorted_words[0][1]

    for w in sorted_words[1:]:
        if abs(w[1] - current_y) <= tolerance:
            current_group.append(w)
        else:
            med_y = statistics.median([x[1] for x in current_group])
            clusters.append((med_y, sorted(current_group, key=lambda x: x[0])))
            current_group = [w]
            current_y = w[1]

    med_y = statistics.median([x[1] for x in current_group])
    clusters.append((med_y, sorted(current_group, key=lambda x: x[0])))
    return clusters


def _find_cliff_in_gaps(sorted_gaps: list[float]) -> tuple[int, float] | None:
    """Find the largest ratio jump between consecutive sorted gap values.

    Returns ``(cliff_index, ratio)`` where ``sorted_gaps[cliff_index]`` is
    the last value below the cliff.  Returns ``None`` if fewer than 2 gaps.
    """
    if len(sorted_gaps) < 2:
        return None
    best_idx, best_ratio = 0, 0.0
    for i in range(len(sorted_gaps) - 1):
        if sorted_gaps[i] > 0:
            ratio = sorted_gaps[i + 1] / sorted_gaps[i]
            if ratio > best_ratio:
                best_ratio = ratio
                best_idx = i
    return (best_idx, best_ratio)


def _format_y_evidence(
    words: list[tuple[float, float, float, float, str]],
    headers: list[str] | None = None,
) -> str:
    """Row gap analysis using cliff detection for the Y-verifier.

    Clusters words by y-position, computes gaps between consecutive rows,
    finds the cliff (largest ratio jump) separating regular row spacing
    from section boundaries or inline headers.

    The *headers* parameter is accepted for API compatibility but the
    y-evidence is computed from all words — x-range filtering would
    exclude the Variable column where inline headers appear.
    """
    if not words:
        return "No words found in table region."

    clusters = _cluster_words_by_y(words)
    if len(clusters) < 2:
        return f"Only {len(clusters)} y-position cluster(s) found."

    # Gaps between consecutive y-clusters
    row_gaps: list[tuple[float, int]] = []  # (gap_size, index_of_row_below)
    for i in range(len(clusters) - 1):
        gap = clusters[i + 1][0] - clusters[i][0]
        row_gaps.append((gap, i))

    sorted_gap_sizes = sorted(g[0] for g in row_gaps)
    cliff = _find_cliff_in_gaps(sorted_gap_sizes)

    lines: list[str] = []
    lines.append(f"Y-position clusters: {len(clusters)}")
    lines.append(f"Row-to-row gaps: {len(row_gaps)}\n")

    if cliff is not None:
        cliff_idx, cliff_ratio = cliff
        threshold = sorted_gap_sizes[cliff_idx]
        below = sorted_gap_sizes[:cliff_idx + 1]
        above = sorted_gap_sizes[cliff_idx + 1:]

        median_spacing = statistics.median(below) if below else 0
        lines.append(
            f"Regular row spacing: {len(below)} gaps, "
            f"{below[0]:.1f}\u2013{below[-1]:.1f}pt "
            f"(median {median_spacing:.1f}pt)"
        )
        lines.append(
            f"\u2500\u2500 CLIFF ({cliff_ratio:.1f}\u00d7 at "
            f"{threshold:.1f}pt \u2192 {above[0]:.1f}pt) \u2500\u2500"
        )
        lines.append(
            f"Large gaps: {len(above)}, "
            f"{', '.join(f'{g:.1f}pt' for g in above)}"
        )

        # Show rows preceded by above-cliff gaps
        large_gap_rows = [
            (gap_size, ci) for gap_size, ci in row_gaps if gap_size > threshold
        ]
        if large_gap_rows:
            lines.append("\nRows preceded by above-cliff gaps:")
            for gap_size, ci in large_gap_rows:
                _y, row_words = clusters[ci + 1]
                word_texts = [w[4] for w in row_words]
                x_min = min(w[0] for w in row_words)
                x_max = max(w[2] for w in row_words)
                snippet = " ".join(word_texts[:8])
                if len(word_texts) > 8:
                    snippet += " ..."
                lines.append(
                    f"  y\u2248{_y:.1f} (+{gap_size:.1f}pt gap): "
                    f"{len(word_texts)} word(s), "
                    f"x: {x_min:.0f}\u2013{x_max:.0f}"
                    f' \u2192 "{snippet}"'
                )
    else:
        lines.append("Only 1 gap \u2014 cannot determine cliff.")

    # Sparse-cluster detection: cliff analysis on per-cluster word counts.
    # Inline section headers (e.g. "Baseline", "Panel A") have very few
    # words compared to data rows.
    word_counts = sorted(len(rw) for _y, rw in clusters)
    wc_cliff = _find_cliff_in_gaps([float(c) for c in word_counts])
    if wc_cliff is not None and wc_cliff[1] >= 1.5:
        wc_threshold = word_counts[wc_cliff[0]]
        sparse = [
            (y, rw) for y, rw in clusters if len(rw) <= wc_threshold
        ]
        if sparse:
            lines.append(
                f"\nSparse rows ({len(sparse)} clusters with "
                f"\u2264{wc_threshold} words, cliff ratio "
                f"{wc_cliff[1]:.1f}\u00d7):"
            )
            for y, rw in sparse[:25]:
                texts = [w[4] for w in rw]
                x_min = min(w[0] for w in rw)
                x_max = max(w[2] for w in rw)
                snippet = " ".join(texts[:6])
                lines.append(
                    f"  y\u2248{y:.1f}: {len(rw)} word(s), "
                    f"x: {x_min:.0f}\u2013{x_max:.0f}"
                    f' \u2192 "{snippet}"'
                )

    return "\n".join(lines)


def _format_x_evidence(
    words: list[tuple[float, float, float, float, str]],
) -> str:
    """Column gap analysis using cliff detection for the X-verifier.

    Collects all inter-word gaps across rows (same approach as the cliff
    structure method), sorts by size, finds the cliff separating intra-cell
    word spacing from column-boundary gaps, and presents clustered boundary
    candidates with row support counts.
    """
    if not words:
        return "No words found in table region."

    y_clusters = _cluster_words_by_y(words)
    if not y_clusters:
        return "No word rows found."

    num_rows = len(y_clusters)

    # Adaptive min_gap from median word height (same as cliff method)
    word_heights = [w[3] - w[1] for w in words if (w[3] - w[1]) > 0]
    median_height = statistics.median(word_heights) if word_heights else 8.0
    min_gap = median_height * 0.25

    # Collect inter-word gaps: (gap_size, x_midpoint, row_idx)
    gap_data: list[tuple[float, float, int]] = []
    for row_idx, (_y, row_words) in enumerate(y_clusters):
        if len(row_words) < 2:
            continue
        for i in range(len(row_words) - 1):
            gap = row_words[i + 1][0] - row_words[i][2]
            if gap >= min_gap:
                midpoint = (row_words[i][2] + row_words[i + 1][0]) / 2
                gap_data.append((gap, midpoint, row_idx))

    if not gap_data:
        return "No significant inter-word gaps found."

    sorted_sizes = sorted(g[0] for g in gap_data)
    cliff = _find_cliff_in_gaps(sorted_sizes)

    lines: list[str] = []
    lines.append(f"Inter-word gaps: {len(gap_data)} (across {num_rows} rows)\n")

    if cliff is None:
        lines.append(
            f"Gap range: {sorted_sizes[0]:.1f}\u2013{sorted_sizes[-1]:.1f}pt"
        )
        lines.append("Cannot determine cliff (< 2 distinct gap sizes).")
        return "\n".join(lines)

    cliff_idx, cliff_ratio = cliff
    threshold = sorted_sizes[cliff_idx]
    below = sorted_sizes[:cliff_idx + 1]
    above = sorted_sizes[cliff_idx + 1:]

    lines.append(
        f"Word spacing (below cliff): {len(below)} gaps, "
        f"{below[0]:.1f}\u2013{below[-1]:.1f}pt"
    )
    lines.append(
        f"\u2500\u2500 CLIFF ({cliff_ratio:.1f}\u00d7 at "
        f"{threshold:.1f}pt \u2192 {above[0]:.1f}pt) \u2500\u2500"
    )
    lines.append(
        f"Structural gaps (above cliff): {len(above)}, "
        f"{above[0]:.1f}\u2013{above[-1]:.1f}pt"
    )

    # Cluster all above-cliff gap positions by x-coordinate
    boundary_items = [
        (mid, gap, ri)
        for gap, mid, ri in gap_data
        if gap > threshold
    ]

    if not boundary_items:
        return "\n".join(lines)

    # Tolerance = median word width (same as cliff method)
    word_widths = [w[2] - w[0] for w in words if (w[2] - w[0]) > 0]
    tol = statistics.median(word_widths) if word_widths else 10.0

    sorted_by_x = sorted(boundary_items, key=lambda g: g[0])
    x_groups: list[tuple[list[float], list[float], set[int]]] = []
    cur_xs: list[float] = [sorted_by_x[0][0]]
    cur_gaps: list[float] = [sorted_by_x[0][1]]
    cur_rows: set[int] = {sorted_by_x[0][2]}

    for mid, gap, ri in sorted_by_x[1:]:
        if mid - statistics.median(cur_xs) <= tol:
            cur_xs.append(mid)
            cur_gaps.append(gap)
            cur_rows.add(ri)
        else:
            x_groups.append((cur_xs, cur_gaps, cur_rows))
            cur_xs = [mid]
            cur_gaps = [gap]
            cur_rows = {ri}
    x_groups.append((cur_xs, cur_gaps, cur_rows))

    lines.append(f"\nColumn boundary candidates ({len(x_groups)} positions):")
    for xs, gaps, rows in x_groups:
        pos = statistics.median(xs)
        med_gap = statistics.median(gaps)
        lines.append(
            f"  x\u2248{pos:.0f} "
            f"(gap {med_gap:.0f}pt, in {len(rows)}/{num_rows} rows)"
        )

    lines.append(f"\nSuggested columns: {len(x_groups) + 1}")

    return "\n".join(lines)


def _compute_x_boundaries(
    words: list[tuple[float, float, float, float, str]],
) -> list[tuple[float, int]]:
    """Compute column boundary x-positions via cliff analysis on inter-word gaps.

    Same algorithm as ``_format_x_evidence`` but returns structured data:
    list of ``(median_x_position, num_supporting_rows)`` sorted by x,
    or an empty list when no cliff can be determined.
    """
    if not words:
        return []

    y_clusters = _cluster_words_by_y(words)
    if not y_clusters:
        return []

    # Adaptive min_gap from median word height
    word_heights = [w[3] - w[1] for w in words if (w[3] - w[1]) > 0]
    median_height = statistics.median(word_heights) if word_heights else 8.0
    min_gap = median_height * 0.25

    # Collect inter-word gaps: (gap_size, x_midpoint, row_idx)
    gap_data: list[tuple[float, float, int]] = []
    for row_idx, (_y, row_words) in enumerate(y_clusters):
        if len(row_words) < 2:
            continue
        for i in range(len(row_words) - 1):
            gap = row_words[i + 1][0] - row_words[i][2]
            if gap >= min_gap:
                midpoint = (row_words[i][2] + row_words[i + 1][0]) / 2
                gap_data.append((gap, midpoint, row_idx))

    if not gap_data:
        return []

    sorted_sizes = sorted(g[0] for g in gap_data)
    cliff = _find_cliff_in_gaps(sorted_sizes)
    if cliff is None:
        return []

    threshold = sorted_sizes[cliff[0]]

    boundary_items = [
        (mid, gap, ri) for gap, mid, ri in gap_data if gap > threshold
    ]
    if not boundary_items:
        return []

    # Cluster by x using median word width as tolerance
    word_widths = [w[2] - w[0] for w in words if (w[2] - w[0]) > 0]
    tol = statistics.median(word_widths) if word_widths else 10.0

    sorted_by_x = sorted(boundary_items, key=lambda g: g[0])
    groups: list[tuple[list[float], set[int]]] = []
    cur_xs: list[float] = [sorted_by_x[0][0]]
    cur_rows: set[int] = {sorted_by_x[0][2]}

    for mid, _gap, ri in sorted_by_x[1:]:
        if mid - statistics.median(cur_xs) <= tol:
            cur_xs.append(mid)
            cur_rows.add(ri)
        else:
            groups.append((cur_xs, cur_rows))
            cur_xs = [mid]
            cur_rows = {ri}
    groups.append((cur_xs, cur_rows))

    return sorted(
        [(statistics.median(xs), len(rows)) for xs, rows in groups],
        key=lambda b: b[0],
    )


def _detect_inline_headers(
    words: list[tuple[float, float, float, float, str]],
    col_boundaries: list[tuple[float, int]],
    transcriber_rows: list[list[str]] | None = None,
) -> str:
    """Detect inline section headers from word positions and column boundaries.

    An inline header is a y-cluster where:
    1. Words exist only in the leftmost column (before the first real column
       boundary).
    2. No words occupy multiple data column ranges (a single body-text word
       bleeding into one range does not disqualify).
    3. The cluster has few words (\u22645), consistent with a section label.

    Uses spatial clustering of high-support boundaries to identify the real
    table column group, and anchors the table's y-range by matching
    distinctive numeric values from *transcriber_rows* against word positions.

    Returns formatted evidence for the Y-verifier prompt, or empty string.
    """
    if not col_boundaries or not words:
        return ""

    # --- Identify the real table column boundaries ---
    # Step 1: filter to high-support boundaries (>= 50% of max support)
    max_support = max(s for _, s in col_boundaries)
    high_support = sorted(
        [(pos, sup) for pos, sup in col_boundaries
         if sup >= max_support * 0.5],
        key=lambda b: b[0],
    )
    if len(high_support) < 2:
        return ""

    # Step 2: spatially cluster — real table boundaries are close together
    # while page gutters and body-text separations are outliers.
    positions = [pos for pos, _ in high_support]
    spacings = [
        positions[i + 1] - positions[i] for i in range(len(positions) - 1)
    ]
    median_spacing = statistics.median(spacings)
    max_gap = median_spacing * 2.5

    spatial_clusters: list[list[tuple[float, int]]] = [[high_support[0]]]
    for i in range(1, len(high_support)):
        if high_support[i][0] - spatial_clusters[-1][-1][0] <= max_gap:
            spatial_clusters[-1].append(high_support[i])
        else:
            spatial_clusters.append([high_support[i]])

    # Take the largest spatial cluster as the real table boundaries
    table_cluster = max(spatial_clusters, key=len)
    if len(table_cluster) < 2:
        return ""

    real_boundaries = sorted(pos for pos, _ in table_cluster)
    first_boundary = real_boundaries[0]
    last_boundary = real_boundaries[-1]

    # Table x-max: last boundary + median inter-boundary spacing
    inner_spacings = [
        real_boundaries[i + 1] - real_boundaries[i]
        for i in range(len(real_boundaries) - 1)
    ]
    margin = statistics.median(inner_spacings) if inner_spacings else 50.0
    table_x_max = last_boundary + margin

    # --- Define column ranges for occupancy checking ---
    col_ranges: list[tuple[float, float]] = []
    for i in range(len(real_boundaries)):
        left = real_boundaries[i]
        right = (
            real_boundaries[i + 1]
            if i + 1 < len(real_boundaries)
            else table_x_max
        )
        col_ranges.append((left, right))
    min_cols_for_data = max(1, len(col_ranges) // 2)

    y_clusters = _cluster_words_by_y(words)

    def _cols_occupied(cluster_words: list) -> int:
        return sum(
            1 for left, right in col_ranges
            if any(w[0] >= left and w[2] <= right for w in cluster_words)
        )

    # --- Anchor the table's y-range using transcriber data values ---
    # Match distinctive numeric values from the transcriber against word
    # positions in the table's x-range to find the actual table rows.
    anchor_values: set[str] = set()
    if transcriber_rows:
        for row in transcriber_rows:
            for cell in row[1:]:  # skip label column
                val = cell.strip()
                if val and any(c.isdigit() for c in val) and len(val) >= 3:
                    anchor_values.add(val)

    anchor_ys: list[float] = []
    for w in words:
        if first_boundary <= w[0] <= table_x_max:
            if w[4].strip() in anchor_values:
                anchor_ys.append(w[1])

    if not anchor_ys:
        # Fallback: cannot anchor the table without matched values
        return ""

    # Row spacing from anchor positions
    sorted_anchor = sorted(set(round(y, 1) for y in anchor_ys))
    if len(sorted_anchor) >= 2:
        anchor_spacings = [
            sorted_anchor[i + 1] - sorted_anchor[i]
            for i in range(len(sorted_anchor) - 1)
            if sorted_anchor[i + 1] - sorted_anchor[i] > 0.5
        ]
        row_margin = (
            statistics.median(anchor_spacings) * 3
            if anchor_spacings else 30.0
        )
    else:
        row_margin = 30.0
    table_y_min = min(anchor_ys) - row_margin
    table_y_max = max(anchor_ys) + row_margin

    # --- Check y-clusters for inline headers ---
    candidates: list[tuple[float, str, int, float, float]] = []
    for y, cluster_words in y_clusters:
        # Must be within the table's y-extent
        if y < table_y_min or y > table_y_max:
            continue

        col0_words = [w for w in cluster_words if w[2] <= first_boundary]
        if not col0_words or len(col0_words) > 5:
            continue

        # Must NOT have data in multiple column ranges
        if _cols_occupied(cluster_words) >= min_cols_for_data:
            continue

        label = " ".join(
            w[4] for w in sorted(col0_words, key=lambda w: w[0])
        )

        # Filter subscript fragments: short text containing digits
        total_chars = sum(len(w[4]) for w in col0_words)
        if total_chars <= 3 and any(c.isdigit() for c in label):
            continue

        # Inline headers are capitalized labels ("Baseline", "Panel A")
        first_word = col0_words[0][4]
        if not first_word[0].isupper():
            continue

        x_min = min(w[0] for w in col0_words)
        x_max = max(w[2] for w in col0_words)
        candidates.append((y, label, len(col0_words), x_min, x_max))

    if not candidates:
        return ""

    lines = [
        "## Inline header detection (programmatic)\n",
        f"Checked {len(y_clusters)} y-clusters against "
        f"{len(real_boundaries)} column boundaries "
        f"(first at x\u2248{first_boundary:.0f}), "
        f"table y-range {table_y_min:.0f}\u2013{table_y_max:.0f}.\n",
        "The following y-positions have words ONLY in the leftmost column "
        "with NO data in the column boundary ranges. Each is an "
        "inline section header and MUST be its own row with empty strings "
        "in all data columns:\n",
    ]
    for y, label, count, x_min, x_max in candidates:
        lines.append(
            f'  y\u2248{y:.1f}: "{label}" '
            f"({count} word(s), x: {x_min:.0f}\u2013{x_max:.0f})"
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public builder functions (used by VisionAPI)
# ---------------------------------------------------------------------------


def build_transcriber_cache_block(transcriber: "AgentResponse") -> str:
    """Build canonical transcriber output text for BP3 caching.

    This text is identical for y_verifier, x_verifier, and synthesizer,
    enabling cache reads across verifier pairs and cross-batch to synthesizer.
    """
    transcriber_json = json.dumps(
        {
            "table_label": transcriber.table_label,
            "headers": transcriber.headers,
            "rows": transcriber.rows,
            "footnotes": transcriber.footnotes,
        },
        indent=2,
        ensure_ascii=False,
    )
    return f"## Transcriber's extraction\n\n{transcriber_json}"


def build_verifier_inputs(
    pdf_path: Path,
    page_num: int,
    bbox: tuple[float, float, float, float],
    transcriber: "AgentResponse",
) -> tuple[str, str, str, str]:
    """Build Y-verifier and X-verifier role texts from PDF word positions.

    Returns (y_role_text, x_role_text, inline_header_section, inline_header_instruction).
    """
    word_positions = _extract_word_positions(pdf_path, page_num, bbox)
    y_evidence = _format_y_evidence(word_positions, headers=transcriber.headers)
    x_evidence = _format_x_evidence(word_positions)

    col_boundaries = _compute_x_boundaries(word_positions)
    inline_headers = _detect_inline_headers(
        word_positions, col_boundaries, transcriber.rows,
    )

    if inline_headers:
        inline_header_section = inline_headers
        inline_header_instruction = (
            "INLINE SECTION HEADERS: The programmatic detection above found "
            "rows that have words ONLY in the leftmost column with NO data at "
            "column boundary positions. These are VERIFIED inline headers \u2014 "
            "each MUST be split into its own row with empty strings (\"\") in "
            "all data columns. Also check the IMAGE for any additional inline "
            "headers the detection may have missed."
        )
    else:
        inline_header_section = ""
        inline_header_instruction = (
            "CRITICAL \u2014 INLINE SECTION HEADERS: Look at the table IMAGE "
            "carefully. Many tables have inline section headers \u2014 bold or "
            "italic labels like \"Baseline\", \"Conversation\", \"Panel A\", "
            "\"Males\", \"Females\" that span the full table width with NO "
            "data values. These MUST be their own row with empty strings "
            "(\"\") in all data columns. The transcriber almost always merges "
            "these into the data row below. If you see ANY such labels in the "
            "image, add them as separate rows. USE THE IMAGE for this check."
        )

    y_role_text = (
        f"## Row gap analysis\n\n{y_evidence}\n\n"
        f"{inline_header_section + chr(10) + chr(10) if inline_header_section else ''}"
        f"## Verification\n\n{inline_header_instruction}\n\n"
        f"Additional checks:\n"
        f"1. COMPARE the transcriber's row count ({transcriber.raw_shape[0]} "
        f"data rows + 1 header row = {transcriber.raw_shape[0] + 1} total rows) "
        f"against what you see in the image.\n"
        f"2. SUBSCRIPTS: Very small gaps between adjacent rows indicate "
        f"sub/superscripts \u2014 these belong to the row above, NOT separate rows.\n"
        f"3. MERGED ROWS: Two visually distinct rows the transcriber combined.\n"
        f"4. MISSING ROWS: Rows visible in the image with no match.\n"
    )

    x_role_text = (
        f"## Column gap analysis (cliff method)\n\n"
        f"Inter-word gaps from all rows are pooled and sorted. The \"cliff\" "
        f"is the largest ratio jump, separating small within-cell word spacing "
        f"from larger column-boundary gaps.\n\n{x_evidence}\n\n"
        f"## Verification\n\n"
        f"Compare the suggested column count against the transcriber "
        f"({transcriber.raw_shape[1]} columns).\n"
    )

    return y_role_text, x_role_text, inline_header_section, inline_header_instruction


def build_synthesizer_user_text(
    transcriber: "AgentResponse",
    y_verifier: "AgentResponse",
    x_verifier: "AgentResponse",
    inline_header_section: str,
) -> str:
    """Build synthesizer role text from the three agents' outputs."""

    def _agent_json(resp: "AgentResponse") -> str:
        if not resp.parse_success:
            return "(agent failed to produce valid output)"
        return json.dumps(
            {"table_label": resp.table_label, "headers": resp.headers,
             "rows": resp.rows, "footnotes": resp.footnotes},
            indent=2, ensure_ascii=False,
        )

    def _agent_corrections(resp: "AgentResponse") -> str:
        if not resp.parse_success:
            return "N/A (agent failed)"
        parsed = _parse_agent_json(resp.raw_response)
        if parsed and parsed.get("corrections"):
            return json.dumps(parsed["corrections"], ensure_ascii=False)
        return "None"

    def _shape_str(resp: "AgentResponse") -> str:
        if not resp.parse_success:
            return "failed"
        return f"{resp.raw_shape[0]} rows x {resp.raw_shape[1]} cols"

    text = (
        f"Transcriber shape: {_shape_str(transcriber)}\n\n"
        f"## Row verifier ({_shape_str(y_verifier)})\n\n{_agent_json(y_verifier)}\n\n"
        f"Row corrections: {_agent_corrections(y_verifier)}\n\n"
        f"## Column verifier ({_shape_str(x_verifier)})\n\n{_agent_json(x_verifier)}\n\n"
        f"Column corrections: {_agent_corrections(x_verifier)}\n"
    )
    if inline_header_section:
        text += f"\n{inline_header_section}\n"
    return text


# ---------------------------------------------------------------------------
# PNG rendering
# ---------------------------------------------------------------------------


def render_table_png(
    pdf_path: Path,
    page_num: int,
    bbox: tuple[float, float, float, float],
    dpi: int = 300,
    padding_px: int = 20,
) -> tuple[bytes, str]:
    """Render table region as PNG. Returns (png_bytes, media_type).

    page_num is 1-indexed.
    """
    doc = pymupdf.open(str(pdf_path))
    try:
        page = doc[page_num - 1]
        page_rect = page.rect

        # Convert padding from pixels to PDF points
        points_per_pixel = 72.0 / dpi
        pad_pts = padding_px * points_per_pixel

        x0, y0, x1, y1 = bbox
        x0 = max(page_rect.x0, x0 - pad_pts)
        y0 = max(page_rect.y0, y0 - pad_pts)
        x1 = min(page_rect.x1, x1 + pad_pts)
        y1 = min(page_rect.y1, y1 + pad_pts)

        clip = pymupdf.Rect(x0, y0, x1, y1)
        mat = pymupdf.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat, clip=clip)
        return pix.tobytes("png"), "image/png"
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Consensus algorithm helpers
# ---------------------------------------------------------------------------


def _structural_consensus(
    responses: list[AgentResponse],
) -> tuple[int, int] | None:
    """Determine winning shape from agent responses.

    Returns (num_rows, num_cols) or None if <2 agents succeeded.
    """
    successful = [r for r in responses if r.parse_success]
    if len(successful) < 2:
        return None

    shape_counts: Counter[tuple[int, int]] = Counter(r.raw_shape for r in successful)
    most_common = shape_counts.most_common(1)[0]

    if most_common[1] >= 2:
        # Majority agreement
        return most_common[0]

    # All 3 differ: pick median dimensions and closest agent
    all_rows = [r.raw_shape[0] for r in successful]
    all_cols = [r.raw_shape[1] for r in successful]
    med_rows = statistics.median(all_rows)
    med_cols = statistics.median(all_cols)

    def distance(shape: tuple[int, int]) -> float:
        return abs(shape[0] - med_rows) + abs(shape[1] - med_cols)

    return min((r.raw_shape for r in successful), key=distance)


def _align_agent_to_shape(
    response: AgentResponse,
    target_shape: tuple[int, int],
    target_headers: list[str],
) -> AgentResponse | None:
    """Align an agent response to a target shape by matching headers/rows.

    Returns adjusted AgentResponse or None if alignment fails.
    """
    if response.raw_shape == target_shape:
        return response

    target_rows, target_cols = target_shape
    current_rows, current_cols = response.raw_shape

    # Try column alignment via normalized header matching
    headers = response.headers
    rows = response.rows

    if target_headers and len(headers) != target_cols:
        norm_target = [_normalize_cell(h) for h in target_headers]
        norm_actual = [_normalize_cell(h) for h in headers]

        # Build mapping from actual index to target index
        col_map: dict[int, int] = {}
        for ai, ah in enumerate(norm_actual):
            for ti, th in enumerate(norm_target):
                if ah == th and ti not in col_map.values():
                    col_map[ai] = ti
                    break

        if len(col_map) >= max(1, target_cols // 2):
            # Reorder/pad columns
            new_headers: list[str] = [""] * target_cols
            for ai, ti in col_map.items():
                if ti < target_cols:
                    new_headers[ti] = headers[ai]

            new_rows: list[list[str]] = []
            for row in rows:
                new_row: list[str] = [""] * target_cols
                for ai, ti in col_map.items():
                    if ai < len(row) and ti < target_cols:
                        new_row[ti] = row[ai]
                new_rows.append(new_row)

            headers = new_headers
            rows = new_rows
            current_cols = target_cols

    # Try row alignment via first-column matching
    if current_rows != target_rows and rows:
        # Simple truncation/padding — only pad with empty rows
        if len(rows) > target_rows:
            rows = rows[:target_rows]
        elif len(rows) < target_rows:
            pad = [""] * (current_cols if rows else target_cols)
            rows = rows + [list(pad)] * (target_rows - len(rows))

    new_shape = (len(rows), len(headers))
    if new_shape != target_shape:
        return None

    return AgentResponse(
        headers=headers,
        rows=rows,
        footnotes=response.footnotes,
        table_label=response.table_label,
        is_incomplete=response.is_incomplete,
        incomplete_reason=response.incomplete_reason,
        raw_shape=new_shape,
        parse_success=True,
        raw_response=response.raw_response,
    )


def _cell_level_vote(
    responses: list[AgentResponse],
    target_shape: tuple[int, int],
    target_headers: list[str],
) -> tuple[list[str], list[list[str]], list[tuple[int, int, list[str]]]]:
    """Vote on each cell and header independently.

    Returns (voted_headers, voted_rows, disputed_cells).
    """
    num_rows, num_cols = target_shape
    disputed_cells: list[tuple[int, int, list[str]]] = []

    # Align all agents to target shape
    aligned: list[AgentResponse] = []
    for resp in responses:
        if not resp.parse_success:
            continue
        a = _align_agent_to_shape(resp, target_shape, target_headers)
        if a is not None:
            aligned.append(a)

    if not aligned:
        # Fallback: use first successful response
        for resp in responses:
            if resp.parse_success:
                aligned = [resp]
                break

    # Vote on headers (per-column majority)
    voted_headers: list[str] = []
    for c in range(num_cols):
        values = []
        for resp in aligned:
            if c < len(resp.headers):
                values.append(_normalize_cell(resp.headers[c]))
        if not values:
            voted_headers.append("")
            continue
        counter: Counter[str] = Counter(values)
        most_common_val, count = counter.most_common(1)[0]
        # Find original (non-normalized) version from first agent that had majority value
        original_val = most_common_val
        for resp in aligned:
            if c < len(resp.headers) and _normalize_cell(resp.headers[c]) == most_common_val:
                original_val = resp.headers[c]
                break
        voted_headers.append(original_val)

    # Vote on rows (per-cell majority)
    voted_rows: list[list[str]] = []
    for r in range(num_rows):
        voted_row: list[str] = []
        for c in range(num_cols):
            values: list[str] = []
            for resp in aligned:
                if r < len(resp.rows) and c < len(resp.rows[r]):
                    values.append(_normalize_cell(resp.rows[r][c]))

            if not values:
                voted_row.append("")
                continue

            counter = Counter(values)
            most_common_val, count = counter.most_common(1)[0]

            if count >= 2:
                # Majority: find original value
                original_val = most_common_val
                for resp in aligned:
                    if (r < len(resp.rows)
                            and c < len(resp.rows[r])
                            and _normalize_cell(resp.rows[r][c]) == most_common_val):
                        original_val = resp.rows[r][c]
                        break
                voted_row.append(original_val)
            else:
                # All disagree: flag as disputed, use first agent's value
                all_vals = [resp.rows[r][c] for resp in aligned
                            if r < len(resp.rows) and c < len(resp.rows[r])]
                disputed_cells.append((r, c, all_vals))
                voted_row.append(all_vals[0] if all_vals else "")

        voted_rows.append(voted_row)

    return voted_headers, voted_rows, disputed_cells


def _merge_footnotes(responses: list[AgentResponse]) -> str:
    """Union-merge footnotes from all agents, preserving first-appearance order."""
    seen: set[str] = set()
    merged: list[str] = []
    for resp in responses:
        if not resp.parse_success or not resp.footnotes:
            continue
        for line in resp.footnotes.splitlines():
            norm = line.strip()
            if norm and norm not in seen:
                seen.add(norm)
                merged.append(norm)
    return "\n".join(merged)


def _vote_table_label(responses: list[AgentResponse]) -> str | None:
    """Majority vote on the table label across successful agents."""
    labels: list[str] = []
    for resp in responses:
        if not resp.parse_success or not resp.table_label:
            continue
        # Normalize: strip whitespace, expand "Tab." -> "Table"
        label = resp.table_label.strip()
        label = re.sub(r"\bTab\.\s*", "Table ", label, flags=re.IGNORECASE)
        labels.append(label)

    if not labels:
        return None

    # Case-insensitive counting
    norm_to_originals: dict[str, list[str]] = {}
    for lbl in labels:
        key = lbl.lower()
        norm_to_originals.setdefault(key, []).append(lbl)

    counter: Counter[str] = Counter(lbl.lower() for lbl in labels)
    most_common_key, count = counter.most_common(1)[0]

    if count >= 2 or len(labels) == 1:
        # Return original casing from first occurrence
        return norm_to_originals[most_common_key][0]

    return None


def _vote_incomplete(responses: list[AgentResponse]) -> bool:
    """Return True if >=2 successful agents voted is_incomplete=True."""
    successful = [r for r in responses if r.parse_success]
    incomplete_count = sum(1 for r in successful if r.is_incomplete)
    return incomplete_count >= 2


# ---------------------------------------------------------------------------
# Main consensus builder
# ---------------------------------------------------------------------------


def build_consensus(responses: list[AgentResponse]) -> ConsensusResult | None:
    """Build consensus from agent responses.

    Returns None if <2 agents parsed successfully (caller should fall back).
    """
    successful = [r for r in responses if r.parse_success]
    num_succeeded = len(successful)

    if num_succeeded < 2:
        logger.warning(
            "Only %d agents succeeded; cannot build consensus", num_succeeded
        )
        return None

    winning_shape = _structural_consensus(responses)
    if winning_shape is None:
        return None

    shape_agreement = sum(
        1 for r in successful if r.raw_shape == winning_shape
    ) >= 2

    # Use headers from first agent with winning shape as reference
    reference_headers: list[str] = []
    for resp in successful:
        if resp.raw_shape == winning_shape:
            reference_headers = resp.headers
            break

    voted_headers, voted_rows, disputed_cells = _cell_level_vote(
        responses, winning_shape, reference_headers
    )

    num_rows, num_cols = winning_shape
    total_cells = num_rows * num_cols + num_cols  # data cells + header cells
    disputed_count = len(disputed_cells)
    agreement_rate = 1.0 - (disputed_count / total_cells) if total_cells > 0 else 1.0

    return ConsensusResult(
        headers=tuple(voted_headers),
        rows=tuple(tuple(row) for row in voted_rows),
        footnotes=_merge_footnotes(responses),
        table_label=_vote_table_label(responses),
        is_incomplete=_vote_incomplete(responses),
        disputed_cells=disputed_cells,
        agent_agreement_rate=agreement_rate,
        shape_agreement=shape_agreement,
        winning_shape=winning_shape,
        num_agents_succeeded=num_succeeded,
    )


# ---------------------------------------------------------------------------
# Agreement rate computation
# ---------------------------------------------------------------------------


def compute_agreement_rate(
    authority: AgentResponse,
    all_responses: list[AgentResponse],
) -> float:
    """Fraction of authority's cells confirmed by at least one other agent.

    Only compares against agents with the same shape (row/col count).
    Returns 1.0 if no other agents have matching shape (nothing to compare).
    """
    if not authority.parse_success:
        return 0.0

    same_shape = [
        r for r in all_responses
        if r is not authority and r.parse_success
        and r.raw_shape == authority.raw_shape
    ]

    if not same_shape:
        # No same-shape agents to compare — return 1.0 (authoritative)
        return 1.0

    total_cells = 0
    confirmed = 0

    # Check headers
    for c, h in enumerate(authority.headers):
        total_cells += 1
        norm_h = _normalize_cell(h)
        for r in same_shape:
            if c < len(r.headers) and _normalize_cell(r.headers[c]) == norm_h:
                confirmed += 1
                break

    # Check data cells
    for ri, row in enumerate(authority.rows):
        for ci, cell in enumerate(row):
            total_cells += 1
            norm_cell = _normalize_cell(cell)
            for r in same_shape:
                if (ri < len(r.rows) and ci < len(r.rows[ri])
                        and _normalize_cell(r.rows[ri][ci]) == norm_cell):
                    confirmed += 1
                    break

    return confirmed / total_cells if total_cells > 0 else 1.0



# ---------------------------------------------------------------------------
# CellGrid conversion
# ---------------------------------------------------------------------------


def vision_result_to_cell_grid(result: VisionExtractionResult) -> CellGrid | None:
    """Convert a VisionExtractionResult to a CellGrid, or None on failure."""
    if result.consensus is None:
        return None

    consensus = result.consensus
    return CellGrid(
        headers=consensus.headers,
        rows=consensus.rows,
        col_boundaries=(),
        row_boundaries=(),
        method="vision_consensus",
        structure_method="vision_haiku_consensus",
    )
