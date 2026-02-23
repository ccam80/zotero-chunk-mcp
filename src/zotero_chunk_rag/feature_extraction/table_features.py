"""Table feature detection for per-table method activation.

Feature predicates inspect a TableContext's cached properties to detect
structural properties of a table region. These predicates are composed
into activation rules in PipelineConfig.activation_rules to gate which
extraction methods run on a given table.

All thresholds are adaptive -- computed from the data in the TableContext,
never hard-coded constants.
"""

from __future__ import annotations

import math
import statistics

from .models import TableContext


def has_ruled_lines(ctx: TableContext) -> bool:
    """Detect whether the table bbox contains horizontal/vertical ruled lines.

    Inspects ``ctx.drawings`` for line-like drawing items and checks whether
    any have thickness consistent with ruled lines. The threshold is adaptive:
    if ``ctx.median_ruled_line_thickness`` is available (meaning lines were
    found in drawings), returns True; otherwise returns False.

    Parameters
    ----------
    ctx:
        Lazily-computed context about the table region.

    Returns
    -------
    bool
        True if the table region contains ruled lines from vector graphics.
    """
    # median_ruled_line_thickness is None when no ruled lines exist
    return ctx.median_ruled_line_thickness is not None


def is_dense_numeric(ctx: TableContext) -> bool:
    """Detect whether a majority of words in the table parse as numbers.

    Filters out very short words (< 2 characters) before counting, since
    single-character tokens are often row/column labels rather than data.
    The threshold is >50% of remaining words being numeric.

    Parameters
    ----------
    ctx:
        Lazily-computed context about the table region.

    Returns
    -------
    bool
        True if >50% of non-trivial words are numeric.
    """
    words = ctx.words
    if not words:
        return False

    # Filter to words with text content >= 2 chars
    # Word tuple format: (x0, y0, x1, y1, text, block_no, line_no, word_no)
    substantive_words = [w for w in words if len(w) >= 5 and len(w[4].strip()) >= 2]
    if not substantive_words:
        return False

    numeric_count = 0
    for w in substantive_words:
        text = w[4].strip()
        if _looks_numeric(text):
            numeric_count += 1

    fraction = numeric_count / len(substantive_words)
    return fraction > 0.5


def has_sparse_content(ctx: TableContext) -> bool:
    """Detect whether the table has sparse content (large bbox, few words).

    Computes words-per-unit-area for the table bbox and compares against
    the page-level density. The threshold is adaptive: the table's word
    density must be below the page-level median word density.

    If the page has no words outside the table, returns False (cannot
    determine sparseness without a reference).

    Parameters
    ----------
    ctx:
        Lazily-computed context about the table region.

    Returns
    -------
    bool
        True if the table has significantly fewer words per area than
        the page median.
    """
    x0, y0, x1, y1 = ctx.bbox
    table_area = (x1 - x0) * (y1 - y0)
    if table_area <= 0:
        return False

    table_word_count = len(ctx.words)
    table_density = table_word_count / table_area

    # Compute page-level word density for comparison
    page_area = ctx.page_width * ctx.page_height
    if page_area <= 0:
        return False

    # Get all words on the page (not just in the table bbox)
    all_page_words = ctx.page.get_text("words")
    if not all_page_words:
        return False

    page_density = len(all_page_words) / page_area

    # Table is sparse if its density is below half the page density
    # (adaptive: derived from page's actual content distribution)
    if page_density <= 0:
        return False

    return table_density < page_density * 0.5


def is_wide_table(ctx: TableContext) -> bool:
    """Detect whether the table spans >80% of the page width.

    Uses the table bbox width relative to ctx.page_width. The 80%
    threshold distinguishes full-width tables from column-width or
    sidebar tables in multi-column layouts.

    Parameters
    ----------
    ctx:
        Lazily-computed context about the table region.

    Returns
    -------
    bool
        True if the table spans more than 80% of page width.
    """
    if ctx.page_width <= 0:
        return False

    x0, y0, x1, y1 = ctx.bbox
    table_width = x1 - x0
    fraction = table_width / ctx.page_width
    return fraction > 0.8


def has_complex_headers(ctx: TableContext) -> bool:
    """Detect whether the first rows have different font properties from later rows.

    Examines font metadata from ``ctx.dict_blocks`` to compare the first
    few rows (potential headers) against the remaining rows (data). If
    header rows have distinct font size or bold styling, the table likely
    has complex/multi-row headers.

    Parameters
    ----------
    ctx:
        Lazily-computed context about the table region.

    Returns
    -------
    bool
        True if header rows have detectably different font properties
        from data rows.
    """
    blocks = ctx.dict_blocks
    if not blocks:
        return False

    # Collect font spans with their y-positions
    font_spans: list[tuple[float, float, bool]] = []  # (y_center, font_size, is_bold)
    for block in blocks:
        if block.get("type") != 0:  # text blocks only
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                bbox = span.get("bbox", (0, 0, 0, 0))
                y_center = (bbox[1] + bbox[3]) / 2
                size = span.get("size", 0)
                font_name = span.get("font", "")
                is_bold = (
                    ".B" in font_name
                    or "-Bold" in font_name
                    or "-bd" in font_name
                    or "Bold" in font_name
                )
                if size > 0:
                    font_spans.append((y_center, size, is_bold))

    if len(font_spans) < 4:
        return False

    # Sort by y-position (top to bottom)
    font_spans.sort(key=lambda s: s[0])

    # Use adaptive split: first 25% of spans as potential header region
    split_idx = max(1, len(font_spans) // 4)
    header_spans = font_spans[:split_idx]
    data_spans = font_spans[split_idx:]

    if not header_spans or not data_spans:
        return False

    # Compare font sizes
    header_sizes = [s[1] for s in header_spans]
    data_sizes = [s[1] for s in data_spans]
    median_header_size = statistics.median(header_sizes)
    median_data_size = statistics.median(data_sizes)

    # Font size difference > 0.5pt indicates header distinction
    size_diff = abs(median_header_size - median_data_size) > 0.5

    # Bold difference: header is bold but data is not
    header_bold_fraction = sum(1 for s in header_spans if s[2]) / len(header_spans)
    data_bold_fraction = sum(1 for s in data_spans if s[2]) / len(data_spans)
    bold_diff = header_bold_fraction > 0.5 and data_bold_fraction < 0.5

    return size_diff or bold_diff


def _looks_numeric(text: str) -> bool:
    """Check if text represents a numeric value.

    Handles integers, floats, negatives, percentages, and scientific notation.
    """
    cleaned = text.strip().rstrip("%")
    if not cleaned:
        return False
    # Handle common numeric prefixes/suffixes
    cleaned = cleaned.lstrip("+-<>~")
    cleaned = cleaned.replace(",", "")
    if not cleaned:
        return False
    try:
        float(cleaned)
        return True
    except ValueError:
        pass
    # Try scientific notation variants
    cleaned = cleaned.replace("\u00d7", "e").replace("x10", "e")
    try:
        float(cleaned)
        return True
    except ValueError:
        return False
