"""Vision table extraction utilities: response parsing, rendering, and context building."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import pymupdf

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


# ---------------------------------------------------------------------------
# Worked examples (shared across all prompt templates)
# ---------------------------------------------------------------------------

EXTRACTION_EXAMPLES = """\
## Worked Examples

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
• "95 % Confidence Limits" is a single column with space-separated values.  \
Do NOT split this into multiple columns just because there is a space in the
data - the column header should make sense as a unit "95% Confidence Limits is
more sensible than "95% Limits" and "Confidence" as separate columns with similar
numbers.
• "Females: Age" and "Males: Age" are inline section headers — own rows \
with "" in all data columns.
• Referent rows ("50- < 60 referent") have no CI or p-value — those cells \
are "" (empty), NOT omitted.
• ALL 5 columns must appear in every row.  A common error is to drop the \
"Histology Frequency Multiple/Single" column entirely because the blank \
column-0 header confuses the column count."""


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
