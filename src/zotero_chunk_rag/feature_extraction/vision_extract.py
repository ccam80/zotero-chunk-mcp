"""Multi-agent adversarial vision table extraction module.

Uses a 4-agent pipeline:
1. Transcriber: initial table extraction from PNG + raw text.
2. Y-Verifier: checks row structure against PDF word y-positions.
3. X-Verifier: checks column structure against PDF word x-positions.
4. Synthesizer: reviews all outputs, produces the authoritative table.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
import statistics
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

try:
    import anthropic
except ImportError:
    anthropic = None  # type: ignore[assignment]

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

VISION_PROMPT_TEMPLATE = """\
You are a precise table transcription agent. Your task is to extract the exact \
contents of the table visible in the image and output a single JSON object.

The JSON object must have exactly these fields:
{{
  "table_label": "<string or null>",
  "is_incomplete": <true|false>,
  "incomplete_reason": "<string>",
  "headers": ["<col1>", "<col2>", ...],
  "rows": [["<r1c1>", "<r1c2>", ...], ["<r2c1>", ...], ...],
  "footnotes": "<string>"
}}

Field definitions:
- table_label: The label you see in the table (e.g. "Table 1", "Table A.1", \
"Table S2"). Set to null if there is no visible label.
- is_incomplete: Set to true if you cannot see all four edges of the table, or \
if cells are visibly cut off at the image boundary. Set to false if you can see \
the complete table.
- incomplete_reason: If is_incomplete is true, describe which edge(s) are cut off \
(e.g. "bottom edge missing", "right column cut off"). Empty string if complete.
- headers: A flat list of column header strings, one per column. If there are \
multi-level headers, flatten them using " / " as separator.
- rows: A list of rows. Each row is a list of cell strings, one per column. \
Empty cells must be represented as "". A table may contain an inline header \
or a data value in a row by itself with no other data in that row. Present \
the table exactly as it appears — do not merge or realign rows based on your \
interpretation of which row a value should belong to.
- footnotes: All footnote text below the table body, as a single string with \
newlines separating individual footnotes. Empty string if none.

Formatting rules:
- Use LaTeX-style notation for super/subscripts: x^{{2}}, x_{{i}}, x^{{2}}_{{i}}.
- Do NOT use markdown bold (**text**) or italic (*text*) in any cell.
- Prefer Unicode characters where available (e.g. ≤, ≥, ±, ×, α, β).
- Preserve decimal precision exactly as shown. Do not round or truncate.
- Represent genuinely empty cells as "".

Phase 1 — Transcribe from image:
Read the table directly from the image. Transcribe all visible text exactly, \
preserving the row and column structure.

Phase 2 — Correct using raw text:
The following raw text was extracted by a PDF text extractor from the same region. \
The Unicode characters and numbers are more reliable than the image rendering, but \
word ordering may be jumbled due to the columnar PDF layout. Use it to correct \
individual characters, digits, and special symbols — do not use it to restructure \
the table.

Raw extracted text:
{raw_text}

{caption_section}\
Output ONLY the JSON object. No code fences, no commentary, no explanation."""

CAPTION_SECTION_TEMPLATE = """\
The extraction system detected this caption for the table:
"{caption}"
If the table label you see differs from this caption's number, report the label \
you actually see — do not match it to this caption.

"""

Y_VERIFIER_PROMPT_TEMPLATE = """\
You are a row-structure verification agent. A transcription agent produced an \
initial table extraction from the image below. Your job is to verify and correct \
the ROW structure using actual word y-positions extracted from the PDF.

## Transcriber's extraction

{transcriber_json}

## Row gap analysis

{y_evidence}

{inline_header_section}

## Verification checklist

{inline_header_instruction}

Additional checks:
1. COMPARE the transcriber's row count ({transcriber_rows} data rows + 1 header \
row = {transcriber_total} total rows) against what you see in the image.
2. SUBSCRIPTS: Very small gaps between adjacent rows indicate sub/superscripts — \
these belong to the row above, NOT separate rows.
3. MERGED ROWS: Two visually distinct rows the transcriber combined into one.
4. MISSING ROWS: Rows visible in the image with no match in the transcription.

## Raw extracted text

{raw_text}

{caption_section}\
## Output

Output a single JSON object with the corrected table:
{{
  "table_label": "<string or null>",
  "is_incomplete": <true|false>,
  "incomplete_reason": "<string>",
  "headers": ["<col1>", "<col2>", ...],
  "rows": [["<r1c1>", "<r1c2>", ...], ...],
  "footnotes": "<string>",
  "corrections": ["<description of each row-structure correction>"]
}}

Formatting: use LaTeX-style x^{{2}}, x_{{i}} for sub/superscripts. \
Prefer Unicode (≤, ≥, ±, α, β). Preserve decimal precision exactly. \
Empty cells = "".

If no row corrections are needed, return the transcriber's table unchanged with \
"corrections": [].

Output ONLY the JSON object. No code fences, no commentary."""

X_VERIFIER_PROMPT_TEMPLATE = """\
You are a column-structure verification agent. A transcription agent produced an \
initial table extraction from the image below. Your job is to verify and correct \
the COLUMN structure using actual word x-positions extracted from the PDF.

## Transcriber's extraction

{transcriber_json}

## Column gap analysis (cliff method)

Inter-word gaps from all rows are pooled and sorted. The "cliff" is the largest \
ratio jump, separating small within-cell word spacing from larger column-boundary \
gaps. Each boundary candidate shows the median gap size and how many rows support \
it. If a boundary has a dramatically larger gap than the others (e.g. 200pt vs \
20pt) and low row support, it is a page layout gutter, not a table column.

{x_evidence}

## Verification checklist

1. REVIEW the column boundary candidates. Each real column boundary should appear \
in most rows (high row support). Boundaries with low support or outlier gap sizes \
are likely noise or page layout gutters.
2. COMPARE the suggested column count against the transcriber ({transcriber_cols} \
columns).
3. CHECK for these specific errors:
   - SPLIT COLUMNS: One real column the transcriber divided into multiple. The \
cliff analysis will show boundary candidates close together.
   - MERGED COLUMNS: Multiple real columns the transcriber merged into one. The \
cliff analysis will show boundary candidates the transcriber missed.
   - MISALIGNED CELLS: Values assigned to the wrong column based on x-position.
   - SUBSCRIPT FRAGMENTS: Small text near a cell (like subscript indices) that \
should be part of the adjacent cell content, not a separate column.

## Raw extracted text

{raw_text}

{caption_section}\
## Output

Output a single JSON object with the corrected table:
{{
  "table_label": "<string or null>",
  "is_incomplete": <true|false>,
  "incomplete_reason": "<string>",
  "headers": ["<col1>", "<col2>", ...],
  "rows": [["<r1c1>", "<r1c2>", ...], ...],
  "footnotes": "<string>",
  "corrections": ["<description of each column-structure correction>"]
}}

Formatting: use LaTeX-style x^{{2}}, x_{{i}} for sub/superscripts. \
Prefer Unicode (≤, ≥, ±, α, β). Preserve decimal precision exactly. \
Empty cells = "".

If no column corrections are needed, return the transcriber's table unchanged \
with "corrections": [].

Output ONLY the JSON object. No code fences, no commentary."""

SYNTHESIZER_PROMPT_TEMPLATE = """\
You are a synthesis agent producing the final authoritative table extraction. \
Three agents have analyzed the same table from the image below:

1. A **transcriber** produced the initial extraction from the image.
2. A **row verifier** checked word y-positions and may have corrected row boundaries.
3. A **column verifier** checked word x-positions and may have corrected column boundaries.

## Transcriber output ({transcriber_shape})

{transcriber_json}

## Row verifier output ({y_verifier_shape})

{y_verifier_json}

Row corrections: {y_corrections}

## Column verifier output ({x_verifier_shape})

{x_verifier_json}

Column corrections: {x_corrections}

## Raw extracted text

{raw_text}

{caption_section}\
{inline_header_evidence}

## Your task

1. Compare the three outputs. Where they agree, the values are likely correct.
2. Where they disagree, examine the image to determine which is correct.
3. When a verifier made corrections backed by PDF position evidence, prefer the \
corrected version unless the image clearly contradicts it.
4. CRITICAL: If "Inline header detection" evidence appears above, those headers \
were VERIFIED by programmatic word-position analysis — they have NO data at column \
positions. The row verifier's corrections for these MUST be kept. Do NOT reject \
them based on majority voting with agents that lacked this evidence.
5. Pay special attention to:
   - Row count differences (the row verifier had actual y-position data)
   - Column count differences (the column verifier had actual x-position data)
   - Inline section headers that may have been merged or split differently

## Output

Output a single JSON object with the final table:
{{
  "table_label": "<string or null>",
  "is_incomplete": <true|false>,
  "incomplete_reason": "<string>",
  "headers": ["<col1>", "<col2>", ...],
  "rows": [["<r1c1>", "<r1c2>", ...], ...],
  "footnotes": "<string>",
  "corrections": ["<description of each correction vs the transcriber>"]
}}

Formatting rules:
- Use LaTeX-style notation for super/subscripts: x^{{2}}, x_{{i}}.
- Prefer Unicode characters (≤, ≥, ±, ×, α, β).
- Preserve decimal precision exactly as shown.
- Represent genuinely empty cells as "".

Output ONLY the JSON object. No code fences, no commentary."""

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
# Agent calling (async)
# ---------------------------------------------------------------------------


async def _call_single_agent(
    client: anthropic.AsyncAnthropic,
    image_b64: str,
    media_type: str,
    raw_text: str,
    caption: str | None,
    model: str,
    agent_id: int,
) -> AgentResponse:
    """Call a single Haiku agent and parse its response."""
    caption_section = ""
    if caption:
        caption_section = CAPTION_SECTION_TEMPLATE.format(caption=caption)

    prompt = VISION_PROMPT_TEMPLATE.format(
        raw_text=raw_text,
        caption_section=caption_section,
    )

    _failure = AgentResponse(
        headers=[],
        rows=[],
        footnotes="",
        table_label=None,
        is_incomplete=False,
        incomplete_reason="",
        raw_shape=(0, 0),
        parse_success=False,
        raw_response="",
    )

    try:
        response = await client.messages.create(
            model=model,
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt,
                        },
                    ],
                }
            ],
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Agent %d API error: %s", agent_id, exc)
        _failure.raw_response = str(exc)
        return _failure

    raw_response = ""
    for block in response.content:
        if hasattr(block, "text"):
            raw_response += block.text

    parsed = _parse_agent_json(raw_response)
    if parsed is None:
        logger.warning("Agent %d failed to parse JSON from response", agent_id)
        _failure.raw_response = raw_response
        return _failure

    # Validate required fields
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

        table_label = parsed.get("table_label")
        is_incomplete = bool(parsed.get("is_incomplete", False))
        incomplete_reason = str(parsed.get("incomplete_reason", ""))
        footnotes = str(parsed.get("footnotes", ""))

        num_cols = len(headers)
        num_rows = len(rows)

        return AgentResponse(
            headers=[str(h) for h in headers],
            rows=[[str(c) for c in row] for row in rows],
            footnotes=footnotes,
            table_label=table_label if isinstance(table_label, str) else None,
            is_incomplete=is_incomplete,
            incomplete_reason=incomplete_reason,
            raw_shape=(num_rows, num_cols),
            parse_success=True,
            raw_response=raw_response,
        )

    except (KeyError, ValueError, TypeError) as exc:
        logger.warning("Agent %d response validation failed: %s", agent_id, exc)
        _failure.raw_response = raw_response
        return _failure


async def _call_agent_with_prompt(
    client: "anthropic.AsyncAnthropic",
    image_b64: str,
    media_type: str,
    prompt: str,
    model: str,
    agent_label: str,
    max_tokens: int = 4096,
) -> AgentResponse:
    """Generic agent caller: sends image + prompt, parses AgentResponse."""
    _failure = AgentResponse(
        headers=[], rows=[], footnotes="",
        table_label=None, is_incomplete=False,
        incomplete_reason="", raw_shape=(0, 0),
        parse_success=False, raw_response="",
    )

    try:
        response = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_b64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }],
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("%s API error: %s", agent_label, exc)
        _failure.raw_response = str(exc)
        return _failure

    raw_response = ""
    for block in response.content:
        if hasattr(block, "text"):
            raw_response += block.text

    parsed = _parse_agent_json(raw_response)
    if parsed is None:
        logger.warning("%s failed to parse JSON", agent_label)
        _failure.raw_response = raw_response
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
            raw_response=raw_response,
        )

    except (KeyError, ValueError, TypeError) as exc:
        logger.warning("%s response validation failed: %s", agent_label, exc)
        _failure.raw_response = raw_response
        return _failure


# ---------------------------------------------------------------------------
# PNG rendering
# ---------------------------------------------------------------------------


def _render_table_png(
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


def _compute_agreement_rate(
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
# Main entry point (async)
# ---------------------------------------------------------------------------


async def extract_table_vision(
    pdf_path: Path,
    page_num: int,
    bbox: tuple[float, float, float, float],
    raw_text: str,
    caption: str | None = None,
    *,
    client: anthropic.AsyncAnthropic | None = None,
    model: str = "claude-haiku-4-5-20251001",
    num_agents: int = 3,
    dpi: int = 300,
    padding_px: int = 20,
    verify: bool = True,
) -> VisionExtractionResult:
    """Extract a table using the adversarial 4-agent pipeline.

    Pipeline (when verify=True):
    1. Transcriber: initial extraction from PNG + raw text.
    2. Y-Verifier + X-Verifier (parallel): structural verification using
       actual PDF word positions as evidence.
    3. Synthesizer: reviews all outputs, produces authoritative table.

    When verify=False, runs only the transcriber (single-agent mode).
    num_agents is accepted for backward compatibility but ignored.
    """
    t0 = time.monotonic()

    if client is None:
        return VisionExtractionResult(
            consensus=None,
            agent_responses=[],
            error="No Anthropic client",
            timing_ms=0.0,
        )

    # --- Render PNG ---
    render_attempts = 1
    current_bbox = bbox
    try:
        png_bytes, media_type = _render_table_png(
            pdf_path, page_num, current_bbox, dpi=dpi, padding_px=padding_px,
        )
    except Exception as exc:  # noqa: BLE001
        return VisionExtractionResult(
            consensus=None, agent_responses=[],
            error=f"Render failed: {exc}",
            timing_ms=(time.monotonic() - t0) * 1000.0,
        )
    image_b64 = base64.b64encode(png_bytes).decode("ascii")

    # --- Phase 1: Transcriber ---
    logger.info("Phase 1: Transcriber")
    transcriber = await _call_single_agent(
        client=client, image_b64=image_b64, media_type=media_type,
        raw_text=raw_text, caption=caption, model=model, agent_id=0,
    )

    if not transcriber.parse_success:
        elapsed = (time.monotonic() - t0) * 1000.0
        return VisionExtractionResult(
            consensus=None, agent_responses=[transcriber],
            render_attempts=1, error="Transcriber failed to parse",
            timing_ms=elapsed,
        )

    # Handle incomplete or empty: retry with full page render
    _needs_retry = (
        transcriber.is_incomplete
        or (not transcriber.headers and not transcriber.rows)
    )
    if _needs_retry:
        try:
            doc = pymupdf.open(str(pdf_path))
            page_rect = doc[page_num - 1].rect
            page_w, page_h = page_rect.width, page_rect.height
            doc.close()
        except Exception:  # noqa: BLE001
            page_w = page_h = 0.0

        if page_w > 0:
            full = (0.0, 0.0, page_w, page_h)
            try:
                png2, mt2 = _render_table_png(
                    pdf_path, page_num, full, dpi=dpi, padding_px=padding_px,
                )
                b64_2 = base64.b64encode(png2).decode("ascii")
                t2 = await _call_single_agent(
                    client, b64_2, mt2, raw_text, caption, model, 0,
                )
                if t2.parse_success:
                    transcriber, image_b64, media_type = t2, b64_2, mt2
                    current_bbox, render_attempts = full, 2
            except Exception:  # noqa: BLE001
                pass

    # --- Single-agent mode (verify=False) ---
    if not verify:
        consensus = ConsensusResult(
            headers=tuple(transcriber.headers),
            rows=tuple(tuple(r) for r in transcriber.rows),
            footnotes=transcriber.footnotes,
            table_label=transcriber.table_label,
            is_incomplete=transcriber.is_incomplete,
            disputed_cells=[],
            agent_agreement_rate=1.0,
            shape_agreement=True,
            winning_shape=transcriber.raw_shape,
            num_agents_succeeded=1,
        )
        elapsed = (time.monotonic() - t0) * 1000.0
        return VisionExtractionResult(
            consensus=consensus, agent_responses=[transcriber],
            render_attempts=render_attempts, timing_ms=elapsed,
        )

    # --- Extract word positions for verifiers ---
    word_positions = _extract_word_positions(pdf_path, page_num, current_bbox)
    y_evidence = _format_y_evidence(word_positions, headers=transcriber.headers)
    x_evidence = _format_x_evidence(word_positions)

    # --- Detect inline headers programmatically ---
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

    caption_section = (
        CAPTION_SECTION_TEMPLATE.format(caption=caption) if caption else ""
    )

    # --- Phase 2: Y-Verifier + X-Verifier in parallel ---
    logger.info("Phase 2: Y-Verifier + X-Verifier (parallel)")

    y_prompt = Y_VERIFIER_PROMPT_TEMPLATE.format(
        transcriber_json=transcriber_json,
        y_evidence=y_evidence,
        inline_header_section=inline_header_section,
        inline_header_instruction=inline_header_instruction,
        transcriber_rows=transcriber.raw_shape[0],
        transcriber_total=transcriber.raw_shape[0] + 1,
        raw_text=raw_text,
        caption_section=caption_section,
    )

    x_prompt = X_VERIFIER_PROMPT_TEMPLATE.format(
        transcriber_json=transcriber_json,
        x_evidence=x_evidence,
        transcriber_cols=transcriber.raw_shape[1],
        raw_text=raw_text,
        caption_section=caption_section,
    )

    y_verifier, x_verifier = await asyncio.gather(
        _call_agent_with_prompt(
            client, image_b64, media_type, y_prompt, model, "Y-Verifier",
        ),
        _call_agent_with_prompt(
            client, image_b64, media_type, x_prompt, model, "X-Verifier",
        ),
    )

    # --- Phase 3: Synthesizer ---
    logger.info("Phase 3: Synthesizer")

    def _agent_json(resp: AgentResponse) -> str:
        if not resp.parse_success:
            return "(agent failed to produce valid output)"
        return json.dumps(
            {"table_label": resp.table_label, "headers": resp.headers,
             "rows": resp.rows, "footnotes": resp.footnotes},
            indent=2, ensure_ascii=False,
        )

    def _agent_corrections(resp: AgentResponse) -> str:
        if not resp.parse_success:
            return "N/A (agent failed)"
        parsed = _parse_agent_json(resp.raw_response)
        if parsed and parsed.get("corrections"):
            return json.dumps(parsed["corrections"], ensure_ascii=False)
        return "None"

    def _shape_str(resp: AgentResponse) -> str:
        if not resp.parse_success:
            return "failed"
        return f"{resp.raw_shape[0]} rows x {resp.raw_shape[1]} cols"

    synth_prompt = SYNTHESIZER_PROMPT_TEMPLATE.format(
        transcriber_json=transcriber_json,
        transcriber_shape=_shape_str(transcriber),
        y_verifier_json=_agent_json(y_verifier),
        y_verifier_shape=_shape_str(y_verifier),
        y_corrections=_agent_corrections(y_verifier),
        x_verifier_json=_agent_json(x_verifier),
        x_verifier_shape=_shape_str(x_verifier),
        x_corrections=_agent_corrections(x_verifier),
        inline_header_evidence=inline_header_section,
        raw_text=raw_text,
        caption_section=caption_section,
    )

    synthesizer = await _call_agent_with_prompt(
        client, image_b64, media_type, synth_prompt, model,
        "Synthesizer", max_tokens=8192,
    )

    # --- Build result ---
    all_responses = [transcriber, y_verifier, x_verifier, synthesizer]

    # Synthesizer is authoritative; fall back to transcriber if it failed
    authority = synthesizer if synthesizer.parse_success else transcriber

    agreement_rate = _compute_agreement_rate(authority, all_responses)
    successful = [r for r in all_responses if r.parse_success]
    shape_agreeing = sum(
        1 for r in successful if r.raw_shape == authority.raw_shape
    )

    consensus = ConsensusResult(
        headers=tuple(authority.headers),
        rows=tuple(tuple(r) for r in authority.rows),
        footnotes=authority.footnotes,
        table_label=authority.table_label,
        is_incomplete=authority.is_incomplete,
        disputed_cells=[],
        agent_agreement_rate=agreement_rate,
        shape_agreement=shape_agreeing >= 2,
        winning_shape=authority.raw_shape,
        num_agents_succeeded=len(successful),
    )

    elapsed_ms = (time.monotonic() - t0) * 1000.0
    logger.info(
        "Adversarial pipeline complete: shape=%s, agreement=%.0f%%, "
        "T=%s Y=%s X=%s S=%s, %.0fms",
        authority.raw_shape, agreement_rate * 100,
        "ok" if transcriber.parse_success else "FAIL",
        "ok" if y_verifier.parse_success else "FAIL",
        "ok" if x_verifier.parse_success else "FAIL",
        "ok" if synthesizer.parse_success else "FAIL",
        elapsed_ms,
    )

    return VisionExtractionResult(
        consensus=consensus,
        agent_responses=all_responses,
        render_attempts=render_attempts,
        timing_ms=elapsed_ms,
    )


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


# ---------------------------------------------------------------------------
# Caption verification
# ---------------------------------------------------------------------------

_CAPTION_NUM_RE = re.compile(
    r"(\d+|[IVXLCDM]+|[A-Z]\.\d+|S\d+)", re.IGNORECASE
)


def verify_and_swap_captions(
    tables: list,  # list of ExtractedTable from models.py
    vision_labels: dict[int, str | None],  # table_index -> agent-reported label
    all_captions: dict[int, list],  # page_num -> list of DetectedCaption
) -> list[tuple[int, int, str]]:  # list of (from_idx, to_idx, reason) swaps
    """Verify vision-reported table labels against pipeline-assigned captions.

    For each table where the vision agent reported a label that differs from the
    pipeline-assigned caption number, attempt to:
      a) Find another table whose caption matches the agent-reported number and swap.
      b) If not found, search all_captions for a floating caption and assign it.

    Returns list of (from_idx, to_idx, reason) tuples for logging.
    """
    swaps: list[tuple[int, int, str]] = []

    def _extract_num(text: str | None) -> str | None:
        if not text:
            return None
        m = _CAPTION_NUM_RE.search(text)
        return m.group(1).upper() if m else None

    # Build index: caption_number -> table index
    caption_num_to_idx: dict[str, int] = {}
    for idx, table in enumerate(tables):
        cap = getattr(table, "caption", None)
        num = _extract_num(cap)
        if num:
            caption_num_to_idx[num] = idx

    for idx, vision_label in vision_labels.items():
        if vision_label is None:
            continue

        vision_num = _extract_num(vision_label)
        if vision_num is None:
            continue

        if idx >= len(tables):
            continue

        pipeline_caption = getattr(tables[idx], "caption", None)
        pipeline_num = _extract_num(pipeline_caption)

        if pipeline_num == vision_num:
            continue  # Already correct

        # Try to find another table with the agent's number
        other_idx = caption_num_to_idx.get(vision_num)
        if other_idx is not None and other_idx != idx:
            swaps.append((idx, other_idx, f"vision label {vision_label} matched table {other_idx}"))
            logger.info(
                "Caption swap: table[%d] <-> table[%d] (vision reported '%s')",
                idx,
                other_idx,
                vision_label,
            )
            continue

        # Search floating captions on all pages
        found_caption = None
        for page_captions in all_captions.values():
            for det_caption in page_captions:
                cap_text = getattr(det_caption, "text", "") or ""
                cap_num = _extract_num(cap_text)
                if cap_num == vision_num:
                    found_caption = cap_text
                    break
            if found_caption:
                break

        if found_caption and idx < len(tables):
            old_caption = getattr(tables[idx], "caption", None)
            try:
                # ExtractedTable may be frozen; attempt attribute assignment
                object.__setattr__(tables[idx], "caption", found_caption)
            except (TypeError, AttributeError):
                pass
            logger.info(
                "Caption reassigned: table[%d] caption '%s' -> '%s' (vision reported '%s')",
                idx,
                old_caption,
                found_caption,
                vision_label,
            )

    return swaps
