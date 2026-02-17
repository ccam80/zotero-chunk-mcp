"""PDF extraction via pymupdf4llm with pymupdf-layout.

pymupdf-layout MUST be imported before pymupdf4llm to activate
ML-based layout detection (tables, figures, headers, footers, OCR).
"""
from __future__ import annotations

import logging
import math
import re
from pathlib import Path

import pymupdf.layout  # noqa: F401 — activates layout engine, MUST be before pymupdf4llm
import pymupdf.table as _table_mod
import pymupdf4llm
import pymupdf

assert hasattr(_table_mod, "TEXTPAGE"), "pymupdf.table API changed — missing TEXTPAGE"
assert hasattr(_table_mod, "extract_cells"), "pymupdf.table API changed — missing extract_cells"

from .models import (
    PageExtraction,
    DocumentExtraction,
    ExtractedFigure,
    ExtractedTable,
    SectionSpan,
    CONFIDENCE_SCHEME_MATCH,
    CONFIDENCE_GAP_FILL,
)
from .section_classifier import categorize_heading

logger = logging.getLogger(__name__)

# Pattern for filtering page identifiers from section-header boxes (e.g. "R1356")
_PAGE_ID_RE = re.compile(r"^R?\d+$")

_NUM_GROUP = r"(\d+|[IVXLCDM]+|[A-Z]\.\d+|S\d+)"

# Pattern for matching table captions
_TABLE_CAPTION_RE = re.compile(
    rf"^(?:\*\*)?(?:Table|Tab\.)\s+{_NUM_GROUP}\s*[.:()\u2014\u2013-]",
    re.IGNORECASE,
)

# Relaxed table caption regex — no delimiter required after the number.
# Only used when font-change detection confirms a distinct label font.
_TABLE_CAPTION_RE_RELAXED = re.compile(
    rf"^(?:\*\*)?(?:Table|Tab\.)\s+{_NUM_GROUP}\s+\S",
    re.IGNORECASE,
)

# Label-only regex — matches "Table N" on its own line (no description).
_TABLE_LABEL_ONLY_RE = re.compile(
    rf"^(?:\*\*)?(?:Table|Tab\.?)\s+{_NUM_GROUP}\s*$",
    re.IGNORECASE,
)

# Patterns for caption completeness counting
_FIG_CAPTION_RE_COMP = re.compile(
    rf"^(?:Figure|Fig\.?)\s+{_NUM_GROUP}\s*[.:()\u2014\u2013-]", re.IGNORECASE,
)
_FIG_CAPTION_RE_COMP_RELAXED = re.compile(
    rf"^(?:Figure|Fig\.?)\s+{_NUM_GROUP}\s+\S", re.IGNORECASE,
)
_TABLE_CAPTION_RE_COMP = re.compile(
    rf"^(?:\*\*)?(?:Table|Tab\.)\s+{_NUM_GROUP}\s*[.:()\u2014\u2013-]", re.IGNORECASE,
)
_TABLE_CAPTION_RE_COMP_RELAXED = re.compile(
    rf"^(?:\*\*)?(?:Table|Tab\.)\s+{_NUM_GROUP}\s+\S", re.IGNORECASE,
)
_CAPTION_NUM_RE = re.compile(r"(\d+)")

# Module-level caption patterns tuple (shared by artifact detection, native, word, and prose paths)
_CAP_PATTERNS = (_TABLE_CAPTION_RE, _TABLE_CAPTION_RE_RELAXED, _TABLE_LABEL_ONLY_RE)

# Ligature codepoints that pymupdf often fails to decompose
_LIGATURE_MAP = {
    "\ufb00": "ff",
    "\ufb01": "fi",
    "\ufb02": "fl",
    "\ufb03": "ffi",
    "\ufb04": "ffl",
}

# Prefix for synthetic captions assigned to orphan tables/figures
SYNTHETIC_CAPTION_PREFIX = "Uncaptioned "

# --- Layout-artifact table detection ---
# Spaced-out header words from Elsevier article-info boxes.
# Each word requires at least one internal whitespace gap (the spaced-letter
# formatting that Elsevier uses) so plain "article" / "abstract" in a normal
# header column does NOT match.
_ARTICLE_INFO_RE = re.compile(
    r"a\s+r\s*t\s*i\s*c\s*l\s*e|i\s+n\s*f\s*o|a\s+b\s*s\s*t\s*r\s*a\s*c\s*t",
    re.IGNORECASE,
)
# TOC-like cell: "N  Section Title  PageNum"  (e.g. "2 Review of methods 907")
_TOC_LINE_RE = re.compile(r"^\d+\s+[A-Z].*\d{2,}$")
# TOC entries packed into a single cell (after newline collapse):
# "page 1 Introduction 904 . 2 Review of methods 907 . 3 ..."
# Look for 3+ occurrences of "digit(s) Title-word ... digit(s)" separated by anything.
_TOC_PACKED_RE = re.compile(r"\d+\s+[A-Z][a-z]+.*?\d{2,}")
# Multi-column TOC row: number in col 0, title in col 1, page in col 2
_TOC_MULTICOLUMN_RE = re.compile(r"^\.?\d+\.?$")
# Figure reference inside a table cell
_FIG_REF_IN_CELL_RE = re.compile(
    r"(?:Figure|Fig\.?)\s+\d+\b.*(?:diagram|block|schematic|overview|flowchart)",
    re.IGNORECASE,
)


def _classify_artifact(table: "ExtractedTable") -> str | None:
    """Classify a table as a layout artifact or real data.

    Returns an artifact-type tag string, or None for real data tables.

    Tags:
    - ``"article_info_box"``  — Elsevier article-info / abstract header box
    - ``"table_of_contents"`` — sequential section-number + page-number rows
    - ``"diagram_as_table"``  — block diagram / figure text mis-parsed as table
    """
    header_text = " ".join(table.headers).strip()
    cell_parts = " ".join(c for row in table.rows for c in row) if table.rows else ""
    all_text = (header_text + " " + cell_parts).strip()

    # A "real" caption is one matching "Table N" patterns — spurious captions
    # (author affiliations, dates) don't protect a table from artifact detection.
    has_real_caption = bool(
        table.caption and any(p.match(table.caption) for p in _CAP_PATTERNS)
    )

    # Pattern 1: Elsevier article-info box (tables without real "Table N" captions)
    if not has_real_caption:
        if _ARTICLE_INFO_RE.search(header_text):
            return "article_info_box"

    # Pattern 2a: Table of contents — one entry per cell
    all_cells = list(table.headers) + [c for row in table.rows for c in row]
    toc_hits = sum(1 for c in all_cells if c.strip() and _TOC_LINE_RE.match(c.strip()))
    total_rows = len(table.rows) + (1 if table.headers else 0)
    if toc_hits >= 3 and toc_hits >= total_rows * 0.4:
        return "table_of_contents"

    # Pattern 2b: TOC packed into a single cell (entries joined on one line)
    if not has_real_caption:
        for c in all_cells:
            if c and len(_TOC_PACKED_RE.findall(c)) >= 3:
                return "table_of_contents"

    # Pattern 2c: Multi-column TOC (number | title | page across columns)
    if not has_real_caption and total_rows >= 2:
        mc_hits = 0
        all_rows = []
        if table.headers and len(table.headers) >= 3:
            all_rows.append(table.headers)
        all_rows.extend(table.rows)
        for row in all_rows:
            if len(row) >= 3:
                col0 = row[0].strip()
                col2 = row[-1].strip()
                if _TOC_MULTICOLUMN_RE.match(col0) and _TOC_MULTICOLUMN_RE.match(col2):
                    mc_hits += 1
        if mc_hits >= 2 and mc_hits >= total_rows * 0.4:
            return "table_of_contents"

    # Pattern 3: Block diagram / figure parsed as table — if the cell text
    # contains a figure caption ("Figure N. block diagram ..."), the table
    # is a misidentified figure regardless of fill rate.
    if not has_real_caption:
        if _FIG_REF_IN_CELL_RE.search(all_text):
            return "diagram_as_table"

    return None


# Backwards-compatible wrapper used by tests
def _is_layout_artifact(table: "ExtractedTable") -> bool:
    """Return True if a table is a layout artifact."""
    return _classify_artifact(table) is not None


# --- Table cell text cleaning regexes ---
# Control characters that pollute cell text (preserves \t 0x09, \n 0x0a, \r 0x0d)
_CONTROL_CHAR_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')

# PyMuPDF table extraction often splits decimals across lines:
#   "4198\n."  should be  ".4198"
#   "9931 1789\n. ."  should be  ".9931 .1789"
_CELL_MULTI_DOT_RE = re.compile(r"^(\d+)\s+(\d+)\n\.\s*\.\s*$")
_CELL_LEADING_DOT_RE = re.compile(r"^(\d\S*)\n\.\s*$")
_CELL_INLINE_DOT_RE = re.compile(r"(?:^|(?<=\s))(\d)\s+\.(\d)")
_CELL_WHITESPACE_RE = re.compile(r"  +")

# Statistical markers that can decorate a numeric cell (stripped for numeric check)
_STAT_MARKERS = re.compile(r"[*\u2020\u2021\u00a7\u2016]+")  # * † ‡ § ‖

# Leading-dot numeric: ".digits" possibly repeated, e.g. ".9931 .1789"
_CELL_LEADING_ZERO_RE = re.compile(r"(?:^|(?<=\s))\.(\d)")

# Negative sign reassembly patterns (must run before newline removal)
# Pattern: "18278 − ." or "18278 − .5" → "-1.8278" (digits, minus, dot)
_CELL_NEG_DOT_RE = re.compile(
    r"(\d+)\s*[\u2212\-]\s*\.\s*(\d*)",
)
# Pattern: "− 18278" or "−18278" → "-18278" (standalone minus before digits)
_CELL_NEG_DIGITS_RE = re.compile(
    r"[\u2212\-]\s*(\d[\d.]*)",
)


def _looks_numeric(text: str) -> bool:
    """Check if text is purely numeric (with statistical markers stripped).

    Strips markers like * † ‡ § and checks if the remainder is only
    digits, dots, hyphens/minus signs, and commas. No thresholds —
    pure character-class check.
    """
    stripped = _STAT_MARKERS.sub("", text).strip()
    if not stripped:
        return False
    return all(c in "0123456789.\u2212-+, " for c in stripped)


def _clean_cell_text(text: str) -> str:
    """Fix common PyMuPDF table-cell extraction artifacts.

    Repairs broken decimals (digits separated from their decimal point
    by a newline) and collapses artifact newlines/whitespace.  Must run
    AFTER ligature normalization but the decimal fixes must run BEFORE
    newline removal (they use ``\\n.`` as a signal).
    """
    if not text:
        return text
    # Step 0: Strip control characters (keeps \t \n \r used as signals)
    text = _CONTROL_CHAR_RE.sub('', text)
    # Step 1: Multi-value leading dots  "9931 1789\n. ." → ".9931 .1789"
    text = _CELL_MULTI_DOT_RE.sub(r".\1 .\2", text)
    # Step 1b: Negative decimal reassembly  "18278 − ." → "-1.8278"
    # Must run before newline removal (uses \n as signal boundary)
    m_neg_dot = _CELL_NEG_DOT_RE.match(text.strip())
    if m_neg_dot and _looks_numeric(text):
        digits = m_neg_dot.group(1)
        frac = m_neg_dot.group(2) or ""
        if frac:
            text = f"-{digits}.{frac}"
        else:
            text = f"-{digits}."
    # Step 1c: Standalone negative  "− 18278" → "-18278"
    elif text.strip().startswith(("\u2212", "-")) and _looks_numeric(text):
        m_neg = _CELL_NEG_DIGITS_RE.match(text.strip())
        if m_neg:
            text = f"-{m_neg.group(1)}"
    # Step 2: Single leading dot  "4198\n." → ".4198"
    text = _CELL_LEADING_DOT_RE.sub(r".\1", text)
    # Step 3: Inline broken decimal  "0 .14" → "0.14"
    text = _CELL_INLINE_DOT_RE.sub(r"\1.\2", text)
    # Step 2b: Leading-zero recovery  ".4198" → "0.4198", ".9931 .1789" → "0.9931 0.1789"
    if _looks_numeric(text):
        text = _CELL_LEADING_ZERO_RE.sub(r"0.\1", text)
    # Step 4: Collapse artifact newlines (AFTER decimal fix)
    text = text.replace("\n", " ")
    # Step 5: Collapse runs of whitespace
    text = _CELL_WHITESPACE_RE.sub(" ", text).strip()
    # Step 6: Normalize Unicode minus (U+2212) to ASCII hyphen-minus
    text = text.replace("\u2212", "-")
    return text


# Footnote indicator patterns (anchored to start of cell text)
_FOOTNOTE_NOTE_RE = re.compile(r"^Notes?[\s.:]", re.IGNORECASE)
_FOOTNOTE_MARKER_RE = re.compile(r"^[*\u2020\u2021\u00a7\u2016a-d]\s")


def _strip_footnote_rows(
    rows: list[list[str]],
    headers: list[str],
) -> tuple[list[list[str]], str]:
    """Strip footnote rows from the bottom of a table.

    Footnote rows are identified by a **two-signal rule** (require 2+ of):
    1. Text starts with "Note." / "Notes:" or a footnote marker (†‡§*a-d).
    2. Row has only 1 non-empty cell (spanning all columns).
    3. Cell text length is an outlier (beyond Q3 + 1.5*IQR of cell lengths).

    Returns (cleaned_rows, footnote_text). Scanning stops at the first
    non-footnote row from the bottom.
    """
    if not rows:
        return rows, ""

    ncols = max(len(r) for r in rows) if rows else 0
    if ncols == 0:
        return rows, ""

    # Compute IQR-based outlier threshold from the table's own cell lengths
    all_lengths = []
    for r in rows:
        for c in r:
            stripped = c.strip()
            if stripped:
                all_lengths.append(len(stripped))
    for h in headers:
        if h.strip():
            all_lengths.append(len(h.strip()))
    if not all_lengths:
        return rows, ""

    all_lengths.sort()
    n = len(all_lengths)
    median_len = all_lengths[n // 2]
    q1 = all_lengths[n // 4]
    q3 = all_lengths[3 * n // 4]
    iqr = q3 - q1
    # IQR outlier fence, but never less than 3× median — prevents
    # over-sensitivity when cell lengths are uniform (small IQR).
    long_cell_threshold = max(q3 + 1.5 * iqr, median_len * 3)

    # Scan from bottom
    footnote_parts: list[str] = []
    cut_idx = len(rows)

    for i in range(len(rows) - 1, -1, -1):
        row = rows[i]
        non_empty = [(j, c.strip()) for j, c in enumerate(row) if c.strip()]

        if not non_empty:
            continue  # empty row, skip

        # Build the full row text for checking
        full_text = " ".join(c for _, c in non_empty)

        # Count signals
        signals = 0

        # Signal 1: starts with footnote pattern
        first_cell_text = non_empty[0][1]
        if _FOOTNOTE_NOTE_RE.match(first_cell_text) or _FOOTNOTE_MARKER_RE.match(first_cell_text):
            signals += 1

        # Signal 2: single non-empty cell (spanning all columns)
        if len(non_empty) == 1:
            signals += 1

        # Signal 3: cell text is an outlier (beyond IQR fence)
        max_cell_len = max(len(c) for _, c in non_empty)
        if max_cell_len > long_cell_threshold:
            signals += 1

        if signals >= 2:
            footnote_parts.append(full_text)
            cut_idx = i
        else:
            break  # stop at first non-footnote row from bottom

    if cut_idx < len(rows):
        footnote_parts.reverse()  # restore top-to-bottom order
        return rows[:cut_idx], " ".join(footnote_parts)

    return rows, ""


def extract_document(
    pdf_path: Path | str,
    *,
    write_images: bool = False,
    images_dir: Path | str | None = None,
    ocr_language: str = "eng",
) -> DocumentExtraction:
    """Extract a PDF document using pymupdf4llm with layout detection."""
    pdf_path = Path(pdf_path)

    kwargs: dict = dict(
        page_chunks=True,
        write_images=False,
        header=False,
        footer=False,
        show_progress=False,
    )

    page_chunks: list[dict] = pymupdf4llm.to_markdown(str(pdf_path), **kwargs)

    # Build pages and full markdown
    pages: list[PageExtraction] = []
    md_parts: list[str] = []
    char_offset = 0

    for chunk in page_chunks:
        md = chunk.get("text", "")
        page_num = chunk.get("metadata", {}).get("page_number", 1)
        page_boxes = chunk.get("page_boxes", [])
        tables_on_page = sum(1 for b in page_boxes if b.get("class") == "table")
        images_on_page = sum(1 for b in page_boxes if b.get("class") == "picture")

        pages.append(PageExtraction(
            page_num=page_num,
            markdown=md,
            char_start=char_offset,
            tables_on_page=tables_on_page,
            images_on_page=images_on_page,
        ))
        md_parts.append(md)
        char_offset += len(md) + 1  # +1 for join newline

    full_markdown = "\n".join(md_parts)

    # --- Ligature normalization (all text) ---
    full_markdown = _normalize_ligatures(full_markdown)
    for p in pages:
        p.markdown = _normalize_ligatures(p.markdown)

    # Detect sections using toc_items or section-header page_boxes
    sections = _detect_sections(page_chunks, full_markdown, pages)

    # --- STRUCTURED EXTRACTION (use native PyMuPDF) ---
    doc = pymupdf.open(str(pdf_path))

    # --- Abstract detection ---
    # If no section is labelled "abstract", check first pages for abstract text
    has_abstract = any(s.label == "abstract" for s in sections)
    if not has_abstract and pages:
        abstract_span = _detect_abstract(pages, full_markdown, doc, sections)
        if abstract_span:
            sections = _insert_abstract(sections, abstract_span)

    tables = _extract_tables_native(doc, sections=sections, pages=pages)

    from ._figure_extraction import extract_figures
    figures = extract_figures(
        doc,
        page_chunks,
        write_images=write_images,
        images_dir=Path(images_dir) if images_dir else None,
        sections=sections,
        pages=pages,
    )

    # Recovery pass: fill orphan captions via proximity matching and gap search
    from ._gap_fill import run_recovery
    figures, tables = run_recovery(
        doc, figures, tables, page_chunks,
        sections=sections, pages=pages,
    )

    # Heading-based caption fallback for orphan tables (e.g. "Abbreviations")
    _assign_heading_captions(doc, tables)

    # Continuation table detection — orphan tables with same headers
    # as a captioned table on a nearby page get "Caption (continued)".
    _assign_continuation_captions(tables)

    # --- Normalize ligatures and clean cell text in tables/figures ---
    for t in tables:
        t.caption = _normalize_ligatures(t.caption)
        t.headers = [_clean_cell_text(_normalize_ligatures(h) or "") for h in t.headers]
        t.rows = [
            [_clean_cell_text(_normalize_ligatures(c) or "") for c in row]
            for row in t.rows
        ]
    for f in figures:
        f.caption = _normalize_ligatures(f.caption)

    # --- Tag layout artifacts (before completeness scoring) ---
    for t in tables:
        t.artifact_type = _classify_artifact(t)
        if t.artifact_type:
            logger.info(
                "Tagged table on page %d as artifact: %s",
                t.page_num, t.artifact_type,
            )

    # Tag uncaptioned tables that overlap with figures as artifacts (e.g. forest
    # plot data tables where find_tables() extracts text from within a figure).
    for t in tables:
        if t.artifact_type:
            continue
        if t.caption and not t.caption.startswith(SYNTHETIC_CAPTION_PREFIX):
            continue  # has a real caption — not a figure sub-component
        t_rect = pymupdf.Rect(t.bbox)
        t_area = t_rect.get_area()
        if t_area <= 0:
            continue
        for f in figures:
            if f.page_num != t.page_num:
                continue
            f_rect = pymupdf.Rect(f.bbox)
            overlap = t_rect & f_rect
            if not overlap.is_empty:
                overlap_ratio = overlap.get_area() / t_area
                if overlap_ratio > 0.5:
                    t.artifact_type = "figure_data_table"
                    logger.info(
                        "Tagged table on page %d as figure_data_table (%.0f%% overlap with figure)",
                        t.page_num, overlap_ratio * 100,
                    )
                    break

    # Compute extraction stats (needs open doc for OCR detection)
    stats = _compute_stats(pages, page_chunks, doc)
    completeness = _compute_completeness(doc, pages, sections, tables, figures, stats)
    doc.close()

    # Assign synthetic captions to orphan tables/figures AFTER completeness
    # (so completeness counts reflect reality, but returned data is usable)
    for t in tables:
        if not t.caption:
            t.caption = f"{SYNTHETIC_CAPTION_PREFIX}table on page {t.page_num}"
    for f in figures:
        if not f.caption:
            f.caption = f"{SYNTHETIC_CAPTION_PREFIX}figure on page {f.page_num}"

    return DocumentExtraction(
        pages=pages,
        full_markdown=full_markdown,
        sections=sections,
        tables=tables,
        figures=figures,
        stats=stats,
        quality_grade=completeness.grade,
        completeness=completeness,
    )


# ---------------------------------------------------------------------------
# Section detection
# ---------------------------------------------------------------------------

def _strip_md_formatting(text: str) -> str:
    """Strip markdown formatting characters (#, *, _, parens, leading numbers/dots)."""
    text = re.sub(r"^#+\s*", "", text)
    text = text.replace("**", "").replace("*", "").replace("_", "")
    # Remove leading section numbers like "1.", "2.1.", "3.2.1."
    text = re.sub(r"^\d+(\.\d+)*\.?\s*", "", text)
    # Remove surrounding parens and extra whitespace
    text = re.sub(r"\(\s*([a-z])\s*\)", "", text)
    return text.strip()


def _detect_sections(
    page_chunks: list[dict],
    full_markdown: str,
    pages: list[PageExtraction],
) -> list[SectionSpan]:
    """Detect sections using toc_items (preferred) or section-header page_boxes (fallback)."""
    total_len = len(full_markdown)
    if total_len == 0:
        return []

    # Strategy 1: Use toc_items if available
    toc_entries = []
    for chunk in page_chunks:
        for item in chunk.get("toc_items", []):
            toc_entries.append(item)

    if toc_entries:
        return _sections_from_toc(toc_entries, page_chunks, full_markdown, pages)

    # Strategy 2: Fall back to section-header page_boxes
    return _sections_from_header_boxes(page_chunks, full_markdown, pages)


def _sections_from_toc(
    toc_entries: list[list],
    page_chunks: list[dict],
    full_markdown: str,
    pages: list[PageExtraction],
) -> list[SectionSpan]:
    """Build sections from PDF table-of-contents entries matched to section-header boxes."""
    total_len = len(full_markdown)

    # Build page-indexed section-header box lookup
    header_boxes_by_page: dict[int, list[dict]] = {}
    for chunk in page_chunks:
        page_num = chunk.get("metadata", {}).get("page_number", 1)
        text = chunk.get("text", "")
        for box in chunk.get("page_boxes", []):
            if box.get("class") == "section-header":
                pos = box.get("pos")
                if pos and isinstance(pos, (list, tuple)) and len(pos) == 2:
                    box_text = text[pos[0]:pos[1]]
                    header_boxes_by_page.setdefault(page_num, []).append({
                        "text": box_text,
                        "pos": pos,
                        "page_num": page_num,
                    })

    # Match TOC entries to section-header boxes, get global char offsets
    # Only use level-1 and level-2 entries
    matched: list[tuple[int, int, str, str]] = []  # (global_offset, level, toc_title, heading_text)

    for entry in toc_entries:
        level, title, page = entry[0], entry[1], entry[2]
        if level > 3:
            continue
        # For level-3+, only include if the heading has a high-value keyword match
        if level == 3:
            clean = _strip_md_formatting(title)
            cat, weight = categorize_heading(clean)
            if not cat or weight < 0.85:
                continue

        toc_clean = _strip_md_formatting(title).lower().strip()
        if not toc_clean:
            continue

        # Find matching section-header box on the correct page (or adjacent pages,
        # since TOC page numbers can be off by 1 from layout engine detection)
        matched_box = None
        for search_page in [page, page + 1, page - 1]:
            boxes_on_page = header_boxes_by_page.get(search_page, [])
            for hbox in boxes_on_page:
                box_clean = _strip_md_formatting(hbox["text"]).lower().strip()
                if toc_clean in box_clean or box_clean in toc_clean:
                    matched_box = hbox
                    break
            if matched_box:
                break

        if matched_box is None:
            logger.debug("TOC entry %r (page %d) not matched to any section-header box", title, page)
            continue

        # Compute global char offset using the page the box was actually found on
        actual_page = matched_box["page_num"]
        page_obj = None
        for p in pages:
            if p.page_num == actual_page:
                page_obj = p
                break
        if page_obj is None:
            continue

        global_offset = page_obj.char_start + matched_box["pos"][0]
        matched.append((global_offset, level, title, matched_box["text"]))

    if not matched:
        return _sections_from_header_boxes(page_chunks, full_markdown, pages)

    # Sort by global offset
    matched.sort(key=lambda x: x[0])

    # Two-pass classification:
    # Pass 1: Keyword match or defer
    # Pass 2: L2+ entries inherit from keyword-matched L1 parent;
    #         everything else → unknown
    labels: list[str] = []
    confs: list[float] = []

    # Build parallel lists: classified labels and the matched entry info
    entries: list[tuple[int, int, str, str]] = matched  # (offset, level, toc_title, heading_text)

    # Pass 1: keyword classification
    for global_offset, level, toc_title, heading_text in entries:
        clean_title = _strip_md_formatting(toc_title)
        cat, weight = categorize_heading(clean_title)
        if cat:
            labels.append(cat)
            confs.append(CONFIDENCE_SCHEME_MATCH)
        else:
            labels.append("__deferred__")
            confs.append(CONFIDENCE_GAP_FILL)

    # Pass 2: L2+ entries inherit from their keyword-matched L1 parent.
    # This is structural inheritance (subsection belongs to parent), not
    # position guessing. L1 entries without keywords stay deferred → unknown.
    for i in range(len(entries)):
        if labels[i] != "__deferred__":
            continue
        if entries[i][1] >= 2:  # level 2 or deeper
            for j in range(i - 1, -1, -1):
                if entries[j][1] == 1 and labels[j] not in ("__deferred__", "unknown", "preamble"):
                    labels[i] = labels[j]
                    break

    # Remaining deferred → unknown
    for i in range(len(entries)):
        if labels[i] == "__deferred__":
            labels[i] = "unknown"

    # Build classified tuples
    classified: list[tuple[int, str, str, float]] = []
    for i in range(len(entries)):
        classified.append((entries[i][0], labels[i], entries[i][3], confs[i]))

    return _build_spans(classified, total_len)


def _sections_from_header_boxes(
    page_chunks: list[dict],
    full_markdown: str,
    pages: list[PageExtraction],
) -> list[SectionSpan]:
    """Build sections from section-header page_boxes (for PDFs without TOC)."""
    total_len = len(full_markdown)

    headers: list[tuple[int, str]] = []  # (global_offset, heading_text)

    for chunk in page_chunks:
        page_num = chunk.get("metadata", {}).get("page_number", 1)
        text = chunk.get("text", "")
        page_obj = None
        for p in pages:
            if p.page_num == page_num:
                page_obj = p
                break
        if page_obj is None:
            continue

        for box in chunk.get("page_boxes", []):
            if box.get("class") != "section-header":
                continue
            pos = box.get("pos")
            if not (pos and isinstance(pos, (list, tuple)) and len(pos) == 2):
                continue

            heading_text = text[pos[0]:pos[1]].strip()
            cleaned = _strip_md_formatting(heading_text).strip()

            # Filter page identifiers
            if _PAGE_ID_RE.match(cleaned):
                continue

            global_offset = page_obj.char_start + pos[0]
            headers.append((global_offset, heading_text))

    if not headers:
        return [SectionSpan(
            label="unknown",
            char_start=0,
            char_end=total_len,
            heading_text="",
            confidence=0.5,
        )]

    headers.sort(key=lambda x: x[0])

    # Classify
    classified: list[tuple[int, str, str, float]] = []
    for global_offset, heading_text in headers:
        clean = _strip_md_formatting(heading_text)
        cat, weight = categorize_heading(clean)
        if cat:
            classified.append((global_offset, cat, heading_text, CONFIDENCE_SCHEME_MATCH))
        else:
            classified.append((global_offset, "__deferred__", heading_text, CONFIDENCE_GAP_FILL))

    # Classify: keyword match or unknown (no TOC levels to inherit from)
    for i, (offset, label, heading_text, conf) in enumerate(classified):
        if label != "__deferred__":
            continue
        classified[i] = (offset, "unknown", heading_text, CONFIDENCE_GAP_FILL)

    return _build_spans(classified, total_len)


def _build_spans(
    classified: list[tuple[int, str, str, float]],
    total_len: int,
) -> list[SectionSpan]:
    """Build SectionSpan list from classified entries, covering the full document."""
    spans: list[SectionSpan] = []

    if classified[0][0] > 0:
        spans.append(SectionSpan(
            label="preamble",
            char_start=0,
            char_end=classified[0][0],
            heading_text="",
            confidence=CONFIDENCE_SCHEME_MATCH,
        ))

    for i, (offset, label, heading_text, conf) in enumerate(classified):
        char_end = classified[i + 1][0] if i + 1 < len(classified) else total_len
        spans.append(SectionSpan(
            label=label,
            char_start=offset,
            char_end=char_end,
            heading_text=heading_text,
            confidence=conf,
        ))

    return spans


def _detect_abstract(
    pages: list[PageExtraction],
    full_markdown: str,
    doc: pymupdf.Document,
    sections: list[SectionSpan],
) -> SectionSpan | None:
    """Detect abstract using three-tier approach.

    Tier 2: Already labelled via TOC — return None.
    Tier 1: Keyword match ('abstract') in first 3 pages.
    Tier 3: Font-based detection — differently-styled prose block.
    """
    import re

    # Tier 2: Already detected via TOC
    if any(s.label == "abstract" for s in sections):
        return None

    # Tier 1: Keyword detection in first 3 pages
    for page in pages[:3]:
        page_text = page.markdown
        lower = page_text.lower()
        match = re.search(
            r"(?:^|\n)\s*(?:#{1,3}\s*)?(?:\*\*)?abstract(?:\*\*)?\.?\s*[\n:]?",
            lower,
        )
        if match:
            abs_start = page.char_start + match.start()
            rest = page_text[match.end():]
            next_heading = re.search(r"\n\s*(?:#{1,3}\s|\*\*\d)", rest)
            if next_heading:
                abs_end = page.char_start + match.end() + next_heading.start()
            else:
                abs_end = page.char_start + len(page_text)
            return SectionSpan(
                label="abstract",
                char_start=abs_start,
                char_end=abs_end,
                heading_text="Abstract",
                confidence=CONFIDENCE_SCHEME_MATCH,
            )

    # Tier 3: Font-based detection (find differently-styled prose in first pages)
    if len(doc) < 4:
        return None

    # Compute body font from pages 3+
    font_counts: dict[tuple[str, float], int] = {}
    for page_idx in range(3, min(len(doc), 10)):
        page = doc[page_idx]
        text_dict = page.get_text("dict")
        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    font_key = (span.get("font", ""), round(span.get("size", 0), 1))
                    char_count = len(span.get("text", ""))
                    font_counts[font_key] = font_counts.get(font_key, 0) + char_count

    if not font_counts:
        return None

    body_font = max(font_counts, key=font_counts.get)
    body_font_name, body_font_size = body_font

    # Scan first 3 pages for differently-styled prose blocks
    candidates: list[tuple[int, int, str]] = []  # (char_start, char_end, text)
    for page_idx in range(min(3, len(doc))):
        page = doc[page_idx]
        page_obj = pages[page_idx] if page_idx < len(pages) else None
        if page_obj is None:
            continue

        text_dict = page.get_text("dict")
        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:
                continue

            # Get dominant font for this block
            block_font_counts: dict[tuple[str, float], int] = {}
            block_text = ""
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    font_key = (span.get("font", ""), round(span.get("size", 0), 1))
                    char_count = len(span.get("text", ""))
                    block_font_counts[font_key] = block_font_counts.get(font_key, 0) + char_count
                    block_text += span.get("text", "")
                block_text += " "
            block_text = block_text.strip()

            if not block_text or len(block_text) < 100:
                continue

            # Skip if it looks like affiliations/emails
            if re.search(r"@[\w.]+\.\w+", block_text):
                continue

            if not block_font_counts:
                continue

            block_font = max(block_font_counts, key=block_font_counts.get)
            # Different font = potential abstract
            if block_font != body_font and abs(block_font[1] - body_font_size) > 0.3:
                candidates.append((
                    page_obj.char_start,
                    page_obj.char_start + len(page_obj.markdown),
                    block_text,
                ))

    if len(candidates) == 1:
        return SectionSpan(
            label="abstract",
            char_start=candidates[0][0],
            char_end=candidates[0][1],
            heading_text="Abstract",
            confidence=CONFIDENCE_GAP_FILL,
        )

    return None


def _insert_abstract(
    sections: list[SectionSpan],
    abstract: SectionSpan,
) -> list[SectionSpan]:
    """Insert an abstract span into the sections list, adjusting boundaries."""
    result = []
    inserted = False
    for s in sections:
        if not inserted and s.char_start <= abstract.char_start < s.char_end:
            if abstract.char_start > s.char_start:
                result.append(SectionSpan(
                    label=s.label,
                    char_start=s.char_start,
                    char_end=abstract.char_start,
                    heading_text=s.heading_text,
                    confidence=s.confidence,
                ))
            abs_end = min(abstract.char_end, s.char_end)
            result.append(SectionSpan(
                label="abstract",
                char_start=abstract.char_start,
                char_end=abs_end,
                heading_text="Abstract",
                confidence=CONFIDENCE_SCHEME_MATCH,
            ))
            if abs_end < s.char_end:
                result.append(SectionSpan(
                    label=s.label,
                    char_start=abs_end,
                    char_end=s.char_end,
                    heading_text=s.heading_text,
                    confidence=s.confidence,
                ))
            inserted = True
        else:
            result.append(s)

    if not inserted:
        result.append(abstract)
        result.sort(key=lambda s: s.char_start)

    return result


# ---------------------------------------------------------------------------
# Table extraction
# ---------------------------------------------------------------------------


def _find_column_gap_threshold(all_gaps: list[float]) -> float:
    """Find the natural break between intra-word and inter-column gaps.

    Three-tier adaptive approach — no fixed floors, data decides:

    1. **Ratio-based natural break** (primary): first large jump (ratio > 2.0)
       in sorted unique gaps. Geometric mean of the gap pair at the break.
       Works well for bimodal distributions (intra-word vs inter-column).
    2. **IQR-based** (fallback): Q3 + 1.0*IQR. Adapts to actual gap
       distribution when no clear ratio break exists.
    3. **Median + 1.5*std_dev** (last resort): when data is too uniform for
       either of the above.
    """
    if not all_gaps:
        return 15.0
    positive_gaps = sorted(g for g in all_gaps if g > 0)
    if not positive_gaps:
        return 15.0

    n = len(positive_gaps)

    # Tier 1: Ratio-based natural break
    # Deduplicate: group gaps within adaptive tolerance (10% of median)
    median_gap = positive_gaps[n // 2]
    dedup_tol = max(median_gap * 0.1, 0.1)
    unique: list[float] = [positive_gaps[0]]
    for g in positive_gaps[1:]:
        if g - unique[-1] > dedup_tol:
            unique.append(g)

    for i in range(len(unique) - 1):
        if unique[i] > 0 and unique[i + 1] / unique[i] > 2.0:
            threshold = math.sqrt(unique[i] * unique[i + 1])
            return threshold

    # Tier 2: IQR-based
    q1 = positive_gaps[n // 4] if n >= 4 else positive_gaps[0]
    q3 = positive_gaps[3 * n // 4] if n >= 4 else positive_gaps[-1]
    iqr = q3 - q1

    if iqr > 0:
        threshold = q3 + iqr
        if threshold > median_gap:
            return threshold

    # Tier 3: Median + 1.5 * std_dev
    mean = sum(positive_gaps) / n
    variance = sum((g - mean) ** 2 for g in positive_gaps) / n
    std_dev = math.sqrt(variance)
    return median_gap + 1.5 * std_dev

def _merge_over_divided_rows(
    rows: list[list[str]],
    *,
    pattern_a_rate: float = 0.40,
    pattern_b_rate: float = 0.50,
    min_row_floor: int = 3,
    min_row_intercept: int = 8,
    filled_limit: int = 1,
) -> list[list[str]]:
    """Merge continuation rows produced by pymupdf's find_tables().

    pymupdf often treats each wrapped text line as a separate table row,
    producing e.g. 59 rows where ~10 logical rows exist.  Two patterns:

    Pattern A (empty-col0): rows with empty first cell exceed *pattern_a_rate*.
    Pattern B (sparse continuation): rows with <= *filled_limit* non-empty
      cells exceed *pattern_b_rate* (3+ column tables only).

    Minimum rows: ``max(min_row_floor, min_row_intercept - ncols)``.
    """
    if not rows:
        return rows

    ncols = max(len(r) for r in rows)

    min_rows = max(min_row_floor, min_row_intercept - ncols)
    if len(rows) < min_rows:
        return rows

    # Pattern A: count rows with empty first cell
    empty_col0 = sum(
        1 for r in rows
        if len(r) == 0 or not r[0].strip()
    )
    use_pattern_a = empty_col0 / len(rows) >= pattern_a_rate

    # Pattern B: count rows with few non-empty cells (only for wide tables)
    use_pattern_b = False
    if not use_pattern_a and ncols >= 3:
        sparse_rows = sum(
            1 for r in rows
            if sum(1 for c in r if c.strip()) <= filled_limit
        )
        use_pattern_b = sparse_rows / len(rows) >= pattern_b_rate

    if not use_pattern_a and not use_pattern_b:
        return rows

    merged: list[list[str]] = []
    for row in rows:
        # Pad row to ncols
        padded = list(row) + [""] * (ncols - len(row))

        is_continuation = False
        if merged:
            if use_pattern_a:
                is_continuation = not padded[0].strip()
            else:  # pattern B
                filled = sum(1 for c in padded if c.strip())
                is_continuation = filled <= filled_limit

        if is_continuation:
            # Continuation: append into previous anchor row
            anchor = merged[-1]
            for j in range(ncols):
                cell = padded[j].strip()
                if cell:
                    if anchor[j].strip():
                        anchor[j] = anchor[j].rstrip() + " " + cell
                    else:
                        anchor[j] = cell
        else:
            merged.append(padded)

    # Strip trailing all-empty rows
    while merged and all(not c.strip() for c in merged[-1]):
        merged.pop()

    return merged


def _remove_empty_columns(
    rows: list[list[str]], headers: list[str],
) -> tuple[list[list[str]], list[str]]:
    """Drop columns that are empty in every row AND have no header text."""
    if not rows:
        return rows, headers
    ncols = max((len(r) for r in rows), default=0)
    ncols = max(ncols, len(headers))
    if ncols == 0:
        return rows, headers
    keep = []
    for j in range(ncols):
        h = headers[j].strip() if j < len(headers) else ""
        if h:
            keep.append(j)
            continue
        if any(r[j].strip() for r in rows if j < len(r)):
            keep.append(j)
    if len(keep) == ncols:
        return rows, headers  # nothing to remove
    new_rows = [[r[j] if j < len(r) else "" for j in keep] for r in rows]
    new_headers = [headers[j] if j < len(headers) else "" for j in keep]
    return new_rows, new_headers


def _should_replace_with_word_api(
    cell_text: str,
    word_tokens: list[str],
    *,
    min_ratio: float = 1.5,
    min_diff: int = 2,
) -> bool:
    """Decide whether a cell should be replaced with word-API text.

    Compares the token count from ``find_tables().extract()`` against the
    tokens returned by ``page.get_text("words")``.  When the word API
    produces significantly more tokens, the extracted text likely has
    merged words (e.g. "Michardandcolleagues[23]").

    *min_ratio* and *min_diff* are noise filters — they prevent
    replacement when the difference is trivially small (one extra token
    from a hyphen split, etc.).

    Guards
    ------
    - Math/Greek cells: skipped (word API can reorder symbols).
    - Numeric cells: skipped (no prose to merge).
    - Short single-token cells (< 15 chars): skipped (too little signal).
    """
    if not cell_text or not cell_text.strip():
        return False
    if not word_tokens:
        return False
    if _MATH_GREEK_RE.search(cell_text):
        return False

    # Normalise newlines to spaces for token counting
    flat = " ".join(cell_text.split())
    if _looks_numeric(flat):
        return False

    extract_tokens = flat.split()
    n_extract = len(extract_tokens)
    n_words = len(word_tokens)

    # Short single-token cells — too little signal to judge
    if n_extract <= 1 and len(flat) < 15:
        return False

    # Only replace when the word API found MORE tokens
    if n_words <= n_extract:
        return False

    ratio = n_words / max(n_extract, 1)
    diff = n_words - n_extract

    return ratio >= min_ratio or diff >= min_diff


def _repair_garbled_cells(
    page: pymupdf.Page,
    tab,
    data: list[list[str | None]],
) -> None:
    """Re-extract garbled cells using PyMuPDF's word-level text API.

    ``find_tables().extract()`` sometimes concatenates words without
    spaces when the PDF encodes characters as individually-positioned
    glyphs.  ``page.get_text("words")`` uses a different word-boundary
    algorithm that handles this correctly.

    Uses ``_should_replace_with_word_api`` to compare token counts
    between the two extraction methods.  Math/Greek and numeric cells
    are never re-extracted because the word API can reorder symbols.

    Mutates *data* in-place.
    """
    table_rows = tab.rows
    for ri, table_row in enumerate(table_rows):
        if ri >= len(data):
            break
        for ci, cell_bbox in enumerate(table_row.cells):
            if ci >= len(data[ri]) or cell_bbox is None:
                continue
            cell_text = data[ri][ci]
            if not cell_text:
                continue
            words = page.get_text("words", clip=pymupdf.Rect(cell_bbox))
            if not words:
                continue
            word_tokens = [w[4] for w in words]
            if not _should_replace_with_word_api(cell_text, word_tokens):
                continue
            words.sort(key=lambda w: (w[1], w[0]))
            new_text = " ".join(w[4] for w in words)
            if new_text.strip():
                data[ri][ci] = new_text


# ---------------------------------------------------------------------------
# Multi-strategy cell text extraction
# ---------------------------------------------------------------------------

# Regex detecting decimal displacement: digits followed by whitespace/newline
# then an isolated period (the decimal point got separated from its digits).
_DECIMAL_DISPLACEMENT_RE = re.compile(r"\d\s+\.$|\d\n\.")

# Regex for a valid decimal number (digits.digits)
_VALID_DECIMAL_RE = re.compile(r"\d+\.\d+")


def _extract_via_rawdict(tab) -> list[list[str | None]]:
    """Strategy A: extract cell text using pymupdf.table.extract_cells.

    Uses the rawdict 50% bbox-overlap algorithm which correctly assigns
    characters to cells even when the layout engine shifts cell boundaries.
    Reuses the TEXTPAGE global set by find_tables() for zero extra cost.
    """
    textpage = _table_mod.TEXTPAGE
    if textpage is None or not tab.cells:
        return []

    result: list[list[str | None]] = []
    for row in tab.rows:
        row_data: list[str | None] = []
        for cell_bbox in row.cells:
            if cell_bbox is None:
                row_data.append(None)
            else:
                text = _table_mod.extract_cells(textpage, cell_bbox)
                row_data.append(text if text else "")
        result.append(row_data)
    return result


def _extract_via_words(page: pymupdf.Page, tab) -> list[list[str | None]]:
    """Strategy C: extract cell text using page.get_text('words').

    Collects words within the table bbox, then assigns each word to the
    cell whose bbox contains the word's center point. Words are joined
    with spaces, sorted top-to-bottom then left-to-right within each cell.
    """
    if not tab.cells:
        return []
    table_clip = pymupdf.Rect(tab.bbox)
    words = page.get_text("words", clip=table_clip)
    if not words:
        return []

    # Build cell grid: row_index → col_index → cell_bbox
    rows_meta = tab.rows
    cell_grid: list[list[tuple | None]] = []
    for row in rows_meta:
        cell_grid.append(list(row.cells))

    # For each word, find which cell it belongs to via center-point containment
    cell_words: dict[tuple[int, int], list] = {}
    for w in words:
        # w = (x0, y0, x1, y1, text, block_no, line_no, word_no)
        cx = (w[0] + w[2]) / 2
        cy = (w[1] + w[3]) / 2
        best_ri, best_ci = -1, -1
        for ri, row_cells in enumerate(cell_grid):
            for ci, cell_bbox in enumerate(row_cells):
                if cell_bbox is None:
                    continue
                if cell_bbox[0] <= cx <= cell_bbox[2] and cell_bbox[1] <= cy <= cell_bbox[3]:
                    best_ri, best_ci = ri, ci
                    break
            if best_ri >= 0:
                break
        if best_ri >= 0:
            cell_words.setdefault((best_ri, best_ci), []).append(w)

    # Build result grid
    result: list[list[str | None]] = []
    for ri, row_cells in enumerate(cell_grid):
        row_data: list[str | None] = []
        for ci, cell_bbox in enumerate(row_cells):
            if cell_bbox is None:
                row_data.append(None)
            else:
                cw = cell_words.get((ri, ci), [])
                if cw:
                    # Sort by y then x for reading order
                    cw.sort(key=lambda w: (w[1], w[0]))
                    row_data.append(" ".join(w[4] for w in cw))
                else:
                    row_data.append("")
        result.append(row_data)
    return result


def _count_decimal_displacement(data: list[list[str | None]]) -> int:
    """Count cells showing decimal displacement artifacts."""
    count = 0
    for row in data:
        for cell in row:
            if cell and _DECIMAL_DISPLACEMENT_RE.search(cell):
                count += 1
    return count


def _count_numeric_integrity(data: list[list[str | None]]) -> tuple[int, int]:
    """Count cells with valid decimals vs cells containing a period.

    Returns (valid_decimal_count, cells_with_period_count).
    """
    valid = 0
    with_period = 0
    for row in data:
        for cell in row:
            if not cell or "." not in cell:
                continue
            with_period += 1
            if _VALID_DECIMAL_RE.search(cell):
                valid += 1
    return valid, with_period


def _compute_fill_rate(data: list[list[str | None]]) -> float:
    """Fraction of non-empty, non-None cells."""
    total = 0
    non_empty = 0
    for row in data:
        for cell in row:
            total += 1
            if cell and cell.strip():
                non_empty += 1
    return non_empty / total if total else 0.0


def _score_extraction(data: list[list[str | None]]) -> float:
    """Quality score for a cell text extraction result.

    Higher is better. Penalises decimal displacement artifacts heavily,
    rewards fill rate and numeric integrity.
    """
    if not data:
        return -999.0

    displacement = _count_decimal_displacement(data)
    fill = _compute_fill_rate(data)
    valid_dec, cells_with_period = _count_numeric_integrity(data)
    integrity_rate = valid_dec / cells_with_period if cells_with_period else 1.0

    score = (
        -40 * displacement
        + 10 * fill
        + 15 * integrity_rate
    )
    return score


def _extract_cell_text_multi_strategy(
    page: pymupdf.Page,
    tab,
) -> tuple[list[list[str | None]], str, list[str | None] | None]:
    """Run multiple extraction strategies and return the best result.

    Tries three approaches:
      A) rawdict 50% overlap via pymupdf.table.extract_cells
      B) tab.extract() — the original midpoint containment
      C) page.get_text('words') with center-point cell assignment

    Scores each with _score_extraction and returns the winner.

    Returns (data_grid, strategy_name, words_row0).
    words_row0 is the first row from the words strategy (Strategy C) when
    a non-words strategy wins — used to fix merged-word headers (e.g.
    "Samplesize" → "Sample size"). None when words won or wasn't available.
    """
    strategies: list[tuple[str, list[list[str | None]]]] = []

    # Strategy A: rawdict
    data_a = _extract_via_rawdict(tab)
    if data_a:
        strategies.append(("rawdict", data_a))

    # Strategy B: original tab.extract()
    data_b = tab.extract()
    if data_b:
        strategies.append(("midpoint", data_b))

    # Strategy C: word-level assembly
    data_c = _extract_via_words(page, tab)
    if data_c:
        strategies.append(("words", data_c))

    if not strategies:
        return [], "none", None

    # Score and select
    best_name = strategies[0][0]
    best_data = strategies[0][1]
    best_score = _score_extraction(best_data)

    for name, data in strategies[1:]:
        s = _score_extraction(data)
        if s > best_score:
            best_score = s
            best_data = data
            best_name = name

    logger.debug(
        "Multi-strategy extraction: winner=%s (score=%.1f) from %d strategies",
        best_name, best_score, len(strategies),
    )

    # If Strategy B won, run garbled-cell repair (word API fixup)
    if best_name == "midpoint":
        _repair_garbled_cells(page, tab, best_data)

    # Capture words row 0 for header cross-check when a non-words strategy won
    words_row0: list[str | None] | None = None
    if best_name != "words" and data_c and data_c[0]:
        words_row0 = data_c[0]

    return best_data, best_name, words_row0


def _assign_heading_captions(
    doc: pymupdf.Document,
    tables: list[ExtractedTable],
) -> None:
    """Assign captions to orphan tables from bold/italic headings above them.

    Some tables (e.g. "Abbreviations", glossary-style) have a heading above
    that is not formatted as "Table N" but is visually a title.  Scans
    ``page.get_text("dict")`` blocks in the zone above each orphan table
    for short bold or italic text and uses it as the caption.

    The scan zone is adaptive: computed from the page's actual median line
    spacing (median * 4 lines).
    """
    for t in tables:
        if t.caption and not t.caption.startswith(SYNTHETIC_CAPTION_PREFIX):
            continue  # already has a real caption

        page = doc[t.page_num - 1]
        table_top = t.bbox[1]

        # Adaptive scan zone: compute from page's median line spacing
        text_dict = page.get_text("dict", flags=pymupdf.TEXT_PRESERVE_WHITESPACE)
        blocks = text_dict["blocks"]

        line_spacings = []
        for block in blocks:
            if block.get("type") != 0:
                continue
            block_lines = block.get("lines", [])
            for li in range(1, len(block_lines)):
                spacing = block_lines[li]["bbox"][1] - block_lines[li - 1]["bbox"][3]
                if 0 < spacing < 50:
                    line_spacings.append(spacing)

        if line_spacings:
            line_spacings.sort()
            median_spacing = line_spacings[len(line_spacings) // 2]
            # Compute median line height too
            line_heights = []
            for block in blocks:
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    h = line["bbox"][3] - line["bbox"][1]
                    if h > 0:
                        line_heights.append(h)
            if line_heights:
                line_heights.sort()
                median_height = line_heights[len(line_heights) // 2]
            else:
                median_height = 12
            scan_distance = (median_spacing + median_height) * 4
        else:
            scan_distance = 60  # fallback

        scan_top = max(0, table_top - scan_distance)

        best_text = None
        best_y = -1.0

        for block in blocks:
            if block.get("type") != 0:  # text block only
                continue
            for line in block.get("lines", []):
                line_y = line["bbox"][3]  # bottom of line
                if line_y < scan_top or line_y > table_top:
                    continue

                spans = line.get("spans", [])
                if not spans:
                    continue

                text = "".join(s["text"] for s in spans).strip()
                if not text or len(text) > 120:
                    continue
                if len(text.split()) > 15:
                    continue

                # Check if bold or italic via font name patterns
                is_styled = False
                for s in spans:
                    font = s.get("font", "")
                    flags = s.get("flags", 0)
                    if any(p in font for p in (".B", "-Bold", "-bd", "Bold")):
                        is_styled = True
                        break
                    if flags & 2:  # italic flag
                        is_styled = True
                        break

                # Skip running heads / page headers (e.g. "Author Journal 2014, 18:650"
                # or "Sensors 2019, 19, 959")
                if re.search(r"\d{4},?\s*\d+[,:(]\s*\d+", text):
                    continue

                if is_styled and line_y > best_y:
                    best_text = text
                    best_y = line_y

        if best_text:
            # Strip markdown bold markers if present
            cleaned = best_text.strip("*").strip()
            t.caption = cleaned
            logger.debug(
                "Assigned heading caption to orphan table on page %d: '%s'",
                t.page_num, cleaned[:60],
            )


def _assign_continuation_captions(tables: list[ExtractedTable]) -> None:
    """Detect continuation tables and assign inherited captions.

    A table with no caption whose column headers match a captioned table
    on a nearby page (within 2 pages) is treated as a continuation.
    """
    for t in tables:
        if t.caption and not t.caption.startswith(SYNTHETIC_CAPTION_PREFIX):
            continue
        if not t.headers or len(t.headers) < 2:
            continue

        t_key = tuple(h.strip().lower() for h in t.headers if h.strip())
        if not t_key:
            continue

        # Search for a captioned table with matching headers
        for other in tables:
            if other is t:
                continue
            if not other.caption or other.caption.startswith(SYNTHETIC_CAPTION_PREFIX):
                continue
            if abs(other.page_num - t.page_num) > 2:
                continue

            o_key = tuple(h.strip().lower() for h in other.headers if h.strip())
            if t_key == o_key:
                t.caption = f"{other.caption} (continued)"
                logger.debug(
                    "Assigned continuation caption on page %d from page %d: '%s'",
                    t.page_num, other.page_num, t.caption[:60],
                )
                break


def _adaptive_row_tolerance(words: list) -> float:
    """Compute row-clustering tolerance from the y-gap distribution.

    Sorts word y-midpoints, computes consecutive gaps, and finds the
    natural break between intra-row gaps (small) and inter-row gaps
    (large) using a ratio-break method.  Falls back to median word
    height * 0.3 when the gap distribution lacks a clear break.
    """
    _ASSUMED_WORD_HEIGHT = 12.0  # typical body-text height in pts
    if not words:
        return _ASSUMED_WORD_HEIGHT * 0.3
    heights = [w[3] - w[1] for w in words if (w[3] - w[1]) > 0]
    if not heights:
        return _ASSUMED_WORD_HEIGHT * 0.3
    heights.sort()
    median_h = heights[len(heights) // 2]

    # Compute y-gaps between consecutive unique word midpoints
    y_mids = sorted(set(round((w[1] + w[3]) / 2, 1) for w in words))
    if len(y_mids) < 3:
        return median_h * 0.3

    gaps = sorted(
        y_mids[i + 1] - y_mids[i]
        for i in range(len(y_mids) - 1)
        if y_mids[i + 1] - y_mids[i] > 0
    )
    if len(gaps) < 2:
        return median_h * 0.3

    # Ratio-break: first gap pair where the jump exceeds 2×
    for i in range(len(gaps) - 1):
        if gaps[i] > 0 and gaps[i + 1] / gaps[i] > 2.0:
            return gaps[i]

    # No clear break — fall back to word-height-based
    return median_h * 0.3



def _strip_absorbed_caption(
    headers: list[str],
    rows: list[list[str]],
) -> tuple[str | None, list[str], list[list[str]]]:
    """Check if the first header or first row cell is an absorbed caption.

    If the first cell of headers (or first row) matches a table caption
    pattern, strip it out and return the caption text. If removing the
    caption leaves a row with all other cells empty, remove the row.

    Returns (caption_or_None, headers, rows).
    """
    # Check headers first
    if headers and headers[0] and any(p.match(headers[0]) for p in _CAP_PATTERNS):
        caption = headers[0]
        headers = list(headers)
        headers[0] = ""
        # If all headers are now empty, drop them
        if all(not h.strip() for h in headers):
            headers = []
        return caption, headers, rows

    # Check first row
    if rows and rows[0] and rows[0][0] and any(p.match(rows[0][0]) for p in _CAP_PATTERNS):
        caption = rows[0][0]
        row = list(rows[0])
        row[0] = ""
        if all(not c.strip() for c in row):
            # Entire row was just the caption — remove it
            rows = rows[1:]
        else:
            rows = [row] + rows[1:]
        return caption, headers, rows

    return None, headers, rows


def _strip_known_caption_from_table(
    caption: str,
    headers: list[str],
    rows: list[list[str]],
) -> tuple[list[str], list[list[str]]]:
    """Remove a known caption that leaked into the table grid.

    When a caption IS matched externally but find_tables() also absorbed it
    into the first header or first few rows, this function removes it using
    substring containment rather than regex patterns.

    Returns (headers, rows) — possibly with caption text removed.
    """
    # Normalize caption for comparison
    cap_norm = " ".join(caption.split()).lower()
    if not cap_norm:
        return headers, rows

    # Build a significant prefix: enough words to be unambiguous
    cap_words = cap_norm.split()
    prefix_len = min(len(cap_words), max(3, len(cap_words) // 2))
    cap_prefix = " ".join(cap_words[:prefix_len])

    def _row_matches_caption(row: list[str]) -> bool:
        """Check if a row's concatenated text is a substring of the caption."""
        row_text = " ".join(c.strip() for c in row if c.strip())
        row_norm = " ".join(row_text.split()).lower()
        if not row_norm:
            return False
        # Row text is substring of caption, or caption prefix is in row
        return row_norm in cap_norm or cap_prefix in row_norm

    def _cell_contains_caption(cell: str) -> bool:
        """Check if a single cell contains the caption prefix."""
        cell_norm = " ".join(cell.split()).lower()
        return bool(cell_norm) and cap_prefix in cell_norm

    # Check headers first
    if headers:
        header_text = " ".join(h.strip() for h in headers if h.strip())
        header_norm = " ".join(header_text.split()).lower()
        if header_norm and (header_norm in cap_norm or cap_prefix in header_norm):
            # All header cells map into the caption — clear the whole header
            if all(not h.strip() or h.strip().lower() in cap_norm for h in headers):
                headers = []
            elif _cell_contains_caption(headers[0]):
                # Only first cell has caption text, others have real data
                headers = list(headers)
                headers[0] = ""

    # Check first few rows
    cleaned_rows = list(rows)
    remove_count = 0
    for ri, row in enumerate(cleaned_rows):
        if ri > 2:
            break  # stop scanning after first few rows
        if _row_matches_caption(row):
            # Entire row is caption text — mark for removal
            remove_count = ri + 1
        elif row and _cell_contains_caption(row[0]):
            # Only first cell has caption text but other cells have data — clear it
            other_filled = sum(1 for c in row[1:] if c.strip())
            if other_filled > 0:
                cleaned_rows[ri] = list(row)
                cleaned_rows[ri][0] = ""
            else:
                remove_count = ri + 1
        else:
            break  # stop at first non-matching row

    if remove_count > 0:
        cleaned_rows = cleaned_rows[remove_count:]

    return headers, cleaned_rows


# Skip-list for header cells that legitimately end with numbers
_HEADER_NUM_SKIP_RE = re.compile(
    r"^(?:Model|Wave|Phase|Group|Arm|Block|Step|Trial|Level|Stage|"
    r"Study|Experiment|Sample|Condition|Factor|Time|Day|Week|Month|Year|"
    r"Round|Session|Visit|Dose|Cohort)\s+\d+$",
    re.IGNORECASE,
)


def _separate_header_data(
    headers: list[str],
    rows: list[list[str]],
    *,
    min_fused_fraction: float = 0.30,
) -> tuple[list[str], list[list[str]]]:
    """Detect and fix header cells that contain fused header+data text.

    When find_tables() absorbs the first data row into header cells,
    each header looks like "ZTA R1(Ohm) 9982." — a label followed by
    a numeric value.  This function detects the pattern and splits the
    numeric suffixes into a new first data row.

    Only triggers when >= *min_fused_fraction* of headers show the
    pattern.  Headers matching the skip-list (e.g. "Model 1", "Wave 2")
    are not counted as fused.
    """
    if not headers or len(headers) < 2:
        return headers, rows

    # Detect: for each header, check if the last whitespace-separated
    # token is numeric
    fused_indices: list[int] = []
    for i, h in enumerate(headers):
        h = h.strip()
        if not h:
            continue
        # Skip legitimate "Label N" headers
        if _HEADER_NUM_SKIP_RE.match(h):
            continue
        parts = h.split()
        if len(parts) >= 2 and _looks_numeric(parts[-1]):
            fused_indices.append(i)

    # Only trigger when a meaningful fraction of headers are fused
    fused_fraction = len(fused_indices) / len(headers)
    if fused_fraction < min_fused_fraction:
        return headers, rows

    # Split: extract numeric suffixes into a new data row.
    # Use re.finditer to locate token positions in the original string so
    # that characters between tokens (including \n) are preserved in the
    # data portion — _clean_cell_text relies on \n. patterns.
    new_headers = list(headers)
    data_row = [""] * len(headers)

    for i in fused_indices:
        h = headers[i].strip()
        tokens = list(re.finditer(r"\S+", h))
        if len(tokens) < 2:
            continue
        # Find where the numeric suffix starts (scan from right)
        split_at = len(tokens)
        for j in range(len(tokens) - 1, 0, -1):
            if _looks_numeric(tokens[j].group()):
                split_at = j
            else:
                break
        if split_at < len(tokens):
            # Split at the whitespace boundary before the first numeric token
            boundary = tokens[split_at].start()
            new_headers[i] = h[:boundary].rstrip()
            data_row[i] = h[boundary:]

    return new_headers, [data_row] + list(rows)


def _split_at_internal_captions(
    headers: list[str],
    rows: list[list[str]],
    bbox: tuple,
    caption: str | None,
    *,
    min_rows: int = 4,
    min_rows_before_split: int = 2,
) -> list[dict]:
    """Split a table at internal caption rows.

    When find_tables() merges adjacent tables into one grid, the caption
    of the second table appears as a data row.  This function scans rows
    for caption-pattern matches in sparse rows and splits the table at
    each match.

    A "see Table N" reference embedded in a dense data row does NOT
    trigger a split — only sparse rows that look like standalone captions.

    Returns a list of segment dicts: [{headers, rows, caption, bbox}, ...].
    If no splits are found, returns a single-element list with the
    original data.
    """
    if len(rows) < min_rows:
        return [{"headers": headers, "rows": rows, "caption": caption, "bbox": bbox}]

    ncols = max((len(r) for r in rows), default=0)

    # Extract the caption number from the table's own caption (if any)
    own_cap_num = None
    if caption:
        m = _CAPTION_NUM_RE.search(caption)
        if m:
            own_cap_num = m.group(1)

    # Find split points: row indices where a sparse row matches a caption pattern
    split_indices: list[tuple[int, str]] = []  # (row_index, caption_text)
    for ri, row in enumerate(rows):
        if ri == 0:
            continue  # first row is likely header, not a split point
        non_empty = [c.strip() for c in row if c.strip()]
        if len(non_empty) > max(2, ncols // 2):
            continue  # dense row — not a standalone caption
        if not non_empty:
            continue
        # Check first non-empty cell for caption pattern
        candidate = non_empty[0]
        if any(p.match(candidate) for p in _CAP_PATTERNS):
            # Skip if this caption matches the table's own caption number
            # (it's an absorbed copy, not a separate table)
            m_cand = _CAPTION_NUM_RE.search(candidate)
            if m_cand and own_cap_num and m_cand.group(1) == own_cap_num:
                continue
            if ri >= min_rows_before_split:
                split_indices.append((ri, candidate))

    if not split_indices:
        return [{"headers": headers, "rows": rows, "caption": caption, "bbox": bbox}]

    # Build segments
    segments: list[dict] = []
    prev_start = 0
    prev_caption = caption

    for split_ri, split_caption in split_indices:
        seg_rows = rows[prev_start:split_ri]
        if len(seg_rows) >= 2:
            segments.append({
                "headers": headers if prev_start == 0 else [],
                "rows": seg_rows,
                "caption": prev_caption,
                "bbox": bbox,
            })
        prev_start = split_ri + 1  # skip the caption row itself
        prev_caption = split_caption

    # Final segment (after last split)
    final_rows = rows[prev_start:]
    if len(final_rows) >= 2:
        segments.append({
            "headers": [],
            "rows": final_rows,
            "caption": prev_caption,
            "bbox": bbox,
        })

    # If splitting produced nothing valid, return original
    if not segments:
        return [{"headers": headers, "rows": rows, "caption": caption, "bbox": bbox}]

    return segments


def _word_based_column_detection(
    page: pymupdf.Page,
    bbox: tuple,
) -> list[list[str]] | None:
    """Build a table grid from word positions clipped to *bbox*.

    Uses the same adaptive row clustering and column gap detection as
    ``_repair_low_fill_table`` but returns the raw grid (headers + rows)
    so the caller can compare column counts against find_tables() output.

    Returns a list of rows (each a list of cell strings), or None if no
    columnar structure is found.
    """
    clip = pymupdf.Rect(bbox)
    words = page.get_text("words", clip=clip)
    if len(words) < 3:
        return None

    words.sort(key=lambda w: (w[1], w[0]))

    # Cluster words into rows
    row_tol = _adaptive_row_tolerance(words)
    rows_of_words: list[list] = []
    current_row = [words[0]]
    for w in words[1:]:
        if w[1] - current_row[-1][1] > row_tol:
            rows_of_words.append(current_row)
            current_row = [w]
        else:
            current_row.append(w)
    rows_of_words.append(current_row)

    if len(rows_of_words) < 2:
        return None

    # Detect column boundaries from x-gaps
    all_gaps: list[float] = []
    for row_words in rows_of_words:
        row_words.sort(key=lambda w: w[0])
        for i in range(1, len(row_words)):
            all_gaps.append(row_words[i][0] - row_words[i - 1][2])
    if not all_gaps:
        return None

    col_threshold = _find_column_gap_threshold(all_gaps)

    # Split each row into cells at column gaps
    result_rows: list[list[str]] = []
    for row_words in rows_of_words:
        row_words.sort(key=lambda w: w[0])
        cells: list[str] = []
        cell_words = [row_words[0][4]]
        for i in range(1, len(row_words)):
            gap = row_words[i][0] - row_words[i - 1][2]
            if gap > col_threshold:
                cells.append(" ".join(cell_words))
                cell_words = [row_words[i][4]]
            else:
                cell_words.append(row_words[i][4])
        cells.append(" ".join(cell_words))
        result_rows.append(cells)

    # Pad rows to uniform width
    max_cols = max(len(r) for r in result_rows)
    if max_cols < 2:
        return None
    for r in result_rows:
        while len(r) < max_cols:
            r.append("")

    return result_rows


def _extract_tables_native(
    doc: pymupdf.Document,
    sections: list[SectionSpan] | None = None,
    pages: list[PageExtraction] | None = None,
) -> list[ExtractedTable]:
    """Extract tables using PyMuPDF's native find_tables() API.

    Captions are found by scanning ALL text blocks on each page for
    "Table N" patterns, then matching to tables by vertical order.
    """
    from ._figure_extraction import find_all_captions_on_page

    tables: list[ExtractedTable] = []
    table_idx = 0

    for page_num_0, page in enumerate(doc):
        page_num = page_num_0 + 1

        # Determine section label for this page (used for ref/appendix skip and phantom scoring)
        page_label = None
        if sections and pages:
            for p in pages:
                if p.page_num == page_num:
                    from .section_classifier import assign_section
                    page_label = assign_section(p.char_start, sections)
                    break
            if page_label in ("references", "appendix"):
                continue

        tab_finder = page.find_tables()
        if not tab_finder.tables:
            continue

        # Find all "Table N" caption blocks on this page
        caption_hits = find_all_captions_on_page(
            page, _TABLE_CAPTION_RE,
            relaxed_re=_TABLE_CAPTION_RE_RELAXED,
            label_only_re=_TABLE_LABEL_ONLY_RE,
        )
        # caption_hits is list of (y_center, text, bbox) sorted by y

        # Sort tables by vertical position
        page_tables = []
        for tab in tab_finder.tables:
            data, strategy_name, words_row0 = _extract_cell_text_multi_strategy(page, tab)

            cleaned_rows = [
                [cell if cell is not None else "" for cell in row]
                for row in data
            ]
            if not cleaned_rows:
                continue

            if tab.header and not tab.header.external:
                # Internal header: row 0 of cleaned_rows IS the header,
                # already extracted via the winning strategy (rawdict etc.)
                headers = [cell if cell is not None else "" for cell in cleaned_rows[0]]
                rows = cleaned_rows[1:]
            elif tab.header and tab.header.external:
                # External header: re-extract via rawdict path for consistency
                textpage = _table_mod.TEXTPAGE
                if textpage is not None and tab.header.cells:
                    headers = []
                    for cell_bbox in tab.header.cells:
                        if cell_bbox is None:
                            headers.append("")
                        else:
                            text = _table_mod.extract_cells(textpage, cell_bbox)
                            headers.append(text if text else "")
                else:
                    header_names = tab.header.names
                    headers = [h if h is not None else "" for h in header_names]
                rows = cleaned_rows
            else:
                headers = []
                rows = cleaned_rows

            # Fix 5: Cross-check rawdict headers against words strategy
            # for merged-word artifacts (e.g. "Samplesize" → "Sample size")
            if strategy_name != "words" and words_row0 and headers:
                for hi in range(min(len(headers), len(words_row0))):
                    rh = (headers[hi] or "").strip()
                    wh = (words_row0[hi] if words_row0[hi] else "").strip()
                    if rh and wh and ' ' not in rh and ' ' in wh:
                        headers[hi] = wh

            if not rows:
                continue

            max_cols = max(len(r) for r in rows) if rows else 0
            if max_cols < 2 and len(headers) < 2:
                continue

            # Fix 6: Compare native column count with word-based detection.
            # find_tables() sometimes creates one column per word, producing
            # many empty cells. Word-based detection can recover fewer, more
            # correct columns. Only replace when BOTH conditions hold:
            #   1) word-based finds fewer columns
            #   2) word-based has better fill rate (proves fewer cols = denser)
            word_grid = _word_based_column_detection(page, tab.bbox)
            if word_grid is not None:
                n_cols_word = max(len(r) for r in word_grid)
                n_cols_native = max(len(r) for r in rows) if rows else 0
                if n_cols_word < n_cols_native:
                    native_fill = (
                        sum(1 for r in rows for c in r if c.strip())
                        / max(1, sum(len(r) for r in rows))
                    )
                    word_fill = (
                        sum(1 for r in word_grid for c in r if c.strip())
                        / max(1, sum(len(r) for r in word_grid))
                    )
                    if word_fill > native_fill:
                        headers = word_grid[0]
                        rows = word_grid[1:]
                        strategy_name = "words-column"
                        if not rows:
                            continue

            y_center = (tab.bbox[1] + tab.bbox[3]) / 2
            page_tables.append((y_center, tab.bbox, headers, rows, strategy_name))

        page_tables.sort(key=lambda x: x[0])

        # Match tables to captions by proximity (not positional index)
        from ._figure_extraction import _match_by_proximity
        table_bboxes = [bbox for _, bbox, _, _, _ in page_tables]
        matched_captions = _match_by_proximity(table_bboxes, caption_hits)

        for i, (_, bbox, headers, rows, strat_name) in enumerate(page_tables):
            caption = matched_captions[i]

            # Absorbed caption handling:
            # - No external match: use regex fallback to find "Table N" in grid
            # - External match exists: use substring match to strip leaked caption
            if not caption:
                absorbed, headers, rows = _strip_absorbed_caption(headers, rows)
                if absorbed:
                    caption = absorbed
            else:
                headers, rows = _strip_known_caption_from_table(caption, headers, rows)

            # Detect header/data fusion (T4): first data row absorbed
            # into header cells, e.g. "ZTA R1(Ohm) 9982."
            headers, rows = _separate_header_data(headers, rows)

            # Re-extract low-fill tables using word positions (before merge,
            # so the merge can consolidate the repaired output).
            headers, rows = _repair_low_fill_table(page, bbox, headers, rows)

            # Merge over-divided rows (pymupdf wraps multi-line cells into
            # separate rows, producing very sparse tables).
            rows = _merge_over_divided_rows(rows)
            rows, headers = _remove_empty_columns(rows, headers)

            # Split at internal captions (T2/T3: merged tables)
            segments = _split_at_internal_captions(headers, rows, bbox, caption)

            for seg in segments:
                seg_rows = seg["rows"]
                seg_headers = seg["headers"]
                seg_caption = seg["caption"]

                # Strip footnote rows from each segment
                seg_rows, footnote_text = _strip_footnote_rows(seg_rows, seg_headers)

                tables.append(ExtractedTable(
                    page_num=page_num,
                    table_index=table_idx,
                    bbox=tuple(seg["bbox"]),
                    headers=seg_headers,
                    rows=seg_rows,
                    caption=seg_caption,
                    footnotes=footnote_text,
                    extraction_strategy=strat_name,
                ))
                table_idx += 1

    # --- Pass 2: Prose/lineless table extraction ---
    # find_tables() can't detect tables formatted as prose definition lists.
    # Scan for "Table N" captions that have no corresponding extracted table,
    # then capture the text blocks below the caption as table content.
    tables = _extract_prose_tables(doc, tables, table_idx, sections, pages)

    return tables


def _parse_prose_rows(content: str) -> list[list[str]]:
    """Try to split prose table content into structured rows.

    If content looks like a definition list (multiple lines, most with
    colon/dash delimiters), parse into 2-column rows.  Otherwise return
    as single cell.
    """
    lines = [l.strip() for l in content.split("\n") if l.strip()]
    if len(lines) < 2:
        return [[content]]
    delim_lines = sum(1 for l in lines if re.search(r"[:\u2013\u2014]", l))
    if delim_lines / len(lines) < 0.4:
        return [[content]]
    rows: list[list[str]] = []
    for line in lines:
        m = re.match(r"^(.+?)\s*[:\u2013\u2014]\s*(.+)$", line)
        if m:
            rows.append([m.group(1).strip(), m.group(2).strip()])
        else:
            rows.append([line])
    return rows if rows else [[content]]


def _repair_low_fill_table(
    page: pymupdf.Page,
    bbox: tuple,
    headers: list[str],
    rows: list[list[str]],
    *,
    skip_above_fill: float = 0.90,
) -> tuple[list[str], list[list[str]]]:
    """Re-extract a table via word positions if fill rate is low.

    pymupdf's find_tables() sometimes misdetects column boundaries, producing
    many empty cells.  Re-extracting from raw word positions with gap-based
    column detection often recovers a much denser table.

    Skips tables with fill >= *skip_above_fill*. Accepts any improvement
    in fill rate.

    Returns (headers, rows) — either repaired or original if no improvement.
    """
    # Compute current fill rate
    total = sum(len(r) for r in rows) + len(headers)
    non_empty = sum(1 for r in rows for c in r if c.strip()) + sum(1 for h in headers if h.strip())
    if total == 0:
        return headers, rows
    old_fill = non_empty / total
    # Skip re-extraction for already-dense tables
    if old_fill >= skip_above_fill:
        return headers, rows

    # Get words within the table bbox
    clip = pymupdf.Rect(bbox)
    words = page.get_text("words", clip=clip)
    if len(words) < 3:
        return headers, rows

    words.sort(key=lambda w: (w[1], w[0]))

    # Cluster words into rows by y-position (adaptive tolerance)
    row_tol = _adaptive_row_tolerance(words)
    rows_of_words: list[list] = []
    current_row = [words[0]]
    for w in words[1:]:
        if w[1] - current_row[-1][1] > row_tol:
            rows_of_words.append(current_row)
            current_row = [w]
        else:
            current_row.append(w)
    rows_of_words.append(current_row)

    if len(rows_of_words) < 2:
        return headers, rows

    # Detect column boundaries from x-gaps
    all_gaps: list[float] = []
    for row_words in rows_of_words:
        row_words.sort(key=lambda w: w[0])
        for i in range(1, len(row_words)):
            all_gaps.append(row_words[i][0] - row_words[i - 1][2])
    if not all_gaps:
        return headers, rows

    col_threshold = _find_column_gap_threshold(all_gaps)

    # Split each row into cells at column gaps
    result_rows: list[list[str]] = []
    for row_words in rows_of_words:
        row_words.sort(key=lambda w: w[0])
        cells: list[str] = []
        cell_words = [row_words[0][4]]
        for i in range(1, len(row_words)):
            gap = row_words[i][0] - row_words[i - 1][2]
            if gap > col_threshold:
                cells.append(" ".join(cell_words))
                cell_words = [row_words[i][4]]
            else:
                cell_words.append(row_words[i][4])
        cells.append(" ".join(cell_words))
        result_rows.append(cells)

    # Pad rows to uniform width
    max_cols = max(len(r) for r in result_rows)
    if max_cols < 2:
        return headers, rows
    for r in result_rows:
        while len(r) < max_cols:
            r.append("")

    new_headers = result_rows[0]
    new_rows = result_rows[1:]
    if not new_rows:
        return headers, rows

    # Accept repair if fill rate improved at all
    new_total = sum(len(r) for r in new_rows) + len(new_headers)
    new_non_empty = sum(1 for r in new_rows for c in r if c.strip()) + sum(1 for h in new_headers if h.strip())
    new_fill = new_non_empty / new_total if new_total else 0.0

    if new_fill > old_fill:
        logger.debug(
            "Repaired low-fill table on page %d: %.0f%% → %.0f%%",
            page.number + 1, old_fill * 100, new_fill * 100,
        )
        return new_headers, new_rows
    return headers, rows


def _extract_table_from_words(
    page: pymupdf.Page,
    caption_y_bottom: float,
    next_boundary_y: float,
) -> list[list[str]] | None:
    """Build a structured table from word positions in a page region.

    Used when ``find_tables()`` merges multiple tables into one grid,
    swallowing orphan captions.  ``page.get_text("words")`` can still
    see the individual words with correct positions.

    Returns structured rows (list of lists) or *None* if no columnar
    structure is found.
    """
    clip = pymupdf.Rect(0, caption_y_bottom, page.rect.width, next_boundary_y)
    words = page.get_text("words", clip=clip)
    if len(words) < 3:
        return None

    words.sort(key=lambda w: (w[1], w[0]))

    # --- Cluster words into rows by y-position (adaptive tolerance) ---
    row_tol = _adaptive_row_tolerance(words)
    rows_of_words: list[list] = []
    current_row = [words[0]]
    for w in words[1:]:
        if w[1] - current_row[-1][1] > row_tol:
            rows_of_words.append(current_row)
            current_row = [w]
        else:
            current_row.append(w)
    rows_of_words.append(current_row)

    if len(rows_of_words) < 2:
        return None

    # --- Filter out body-text rows (two-pass) ---
    # Pass 1: use median max-gap from the first few rows as the reference.
    # Table rows have large x-gaps between columns; body-text rows don't.
    # Compute reference from first 5 rows to avoid body-text contamination.
    reference_max_gaps = []
    for row_words in rows_of_words[:5]:
        row_words.sort(key=lambda w: w[0])
        if len(row_words) >= 2:
            gaps = [row_words[i][0] - row_words[i - 1][2]
                    for i in range(1, len(row_words))]
            reference_max_gaps.append(max(gaps))

    if reference_max_gaps:
        reference_max_gaps.sort()
        ref_gap = reference_max_gaps[len(reference_max_gaps) // 2]
    else:
        ref_gap = 10.0

    # Adaptive gap threshold for body-text filter (50% of reference gap)
    gap_threshold = ref_gap * 0.5

    table_rows: list[list] = []
    for row_words in rows_of_words:
        row_words.sort(key=lambda w: w[0])
        if len(row_words) < 2:
            table_rows.append(row_words)
            continue
        gaps = [row_words[i][0] - row_words[i - 1][2]
                for i in range(1, len(row_words))]
        max_gap = max(gaps)
        if max_gap > gap_threshold:        # has a significant column gap
            table_rows.append(row_words)
        elif len(row_words) <= 8:          # short row, likely table
            table_rows.append(row_words)
        else:                              # long dense row = body text
            break

    if len(table_rows) < 2:
        return None

    # --- Detect column boundaries from filtered table rows ---
    all_gaps: list[float] = []
    for row_words in table_rows:
        for i in range(1, len(row_words)):
            all_gaps.append(row_words[i][0] - row_words[i - 1][2])
    if not all_gaps:
        return None

    col_threshold = _find_column_gap_threshold(all_gaps)

    # --- Split each row into cells at column gaps ---
    result_rows: list[list[str]] = []
    for row_words in table_rows:
        row_words.sort(key=lambda w: w[0])
        cells: list[str] = []
        cell_words = [row_words[0][4]]
        for i in range(1, len(row_words)):
            gap = row_words[i][0] - row_words[i - 1][2]
            if gap > col_threshold:
                cells.append(" ".join(cell_words))
                cell_words = [row_words[i][4]]
            else:
                cell_words.append(row_words[i][4])
        cells.append(" ".join(cell_words))
        result_rows.append(cells)

    max_cols = max(len(r) for r in result_rows)
    if max_cols < 2:
        return None

    # --- Trim trailing body-text rows ---
    # Establish expected column count from the first rows that have
    # the maximum number of cells.  Rows with fewer cells (before
    # padding) that also have long text are body text leaking in.
    # Adaptive cell length limit: derive from region width / column count.
    region_width = next_boundary_y - caption_y_bottom  # approximate char budget
    cell_len_limit = max(30, int(region_width / max(max_cols, 1)))
    trimmed: list[list[str]] = []
    for r in result_rows:
        raw_cols = len(r)
        if raw_cols < max_cols and trimmed:
            # Fewer columns AND we already have data → body text
            break
        max_cell_len = max(len(c) for c in r) if r else 0
        if raw_cols < max_cols and max_cell_len > cell_len_limit:
            break
        trimmed.append(r)
    if len(trimmed) < 2:
        return None

    max_cols = max(len(r) for r in trimmed)
    for r in trimmed:
        while len(r) < max_cols:
            r.append("")

    return trimmed


def _extract_prose_tables(
    doc: pymupdf.Document,
    tables: list[ExtractedTable],
    table_idx: int,
    sections: list[SectionSpan] | None,
    pages: list[PageExtraction] | None,
) -> list[ExtractedTable]:
    """Find table captions with no extracted table and capture prose content."""
    from ._figure_extraction import find_all_captions_on_page

    # Collect caption numbers already matched to tables
    matched_nums: set[str] = set()
    for t in tables:
        if t.caption:
            m = _CAPTION_NUM_RE.search(t.caption)
            if m:
                matched_nums.add(m.group(1))

    for page_num_0, page in enumerate(doc):
        page_num = page_num_0 + 1

        # Skip references/appendix
        if sections and pages:
            from ._figure_extraction import _is_in_references
            page_label = None
            for p in pages:
                if p.page_num == page_num:
                    from .section_classifier import assign_section
                    page_label = assign_section(p.char_start, sections)
                    break
            if page_label in ("references", "appendix"):
                continue

        caption_hits = find_all_captions_on_page(
            page, _TABLE_CAPTION_RE,
            relaxed_re=_TABLE_CAPTION_RE_RELAXED,
            label_only_re=_TABLE_LABEL_ONLY_RE,
        )

        for cap_idx, (y_center, caption_text, bbox) in enumerate(caption_hits):
            m = _CAPTION_NUM_RE.search(caption_text)
            if not m:
                continue
            num = m.group(1)
            if num in matched_nums:
                continue  # already have a table for this caption

            # --- Try word-based extraction first ---
            # When a caption falls inside a detected table's bbox,
            # find_tables() merged multiple tables into one grid.
            # page.get_text("words") can still recover the data.
            inside_table = any(
                t.page_num == page_num
                and t.bbox[1] < y_center < t.bbox[3]
                for t in tables
            )
            if inside_table:
                cap_bottom = bbox[3] if bbox else y_center + 10
                # Next boundary: next caption on this page, or page bottom
                next_y = page.rect.height
                for future_y, _, _ in caption_hits[cap_idx + 1:]:
                    next_y = future_y - 5
                    break
                word_rows = _extract_table_from_words(
                    page, cap_bottom, next_y,
                )
                if word_rows and len(word_rows) >= 2:
                    # Strip absorbed caption from word-extracted rows
                    absorbed_cap, _, word_rows = _strip_absorbed_caption([], word_rows)
                    if absorbed_cap and not caption_text:
                        caption_text = absorbed_cap

                    # Compute actual table bbox from word positions
                    clip = pymupdf.Rect(0, cap_bottom, page.rect.width, next_y)
                    words = page.get_text("words", clip=clip)
                    if words:
                        t_x0 = min(w[0] for w in words)
                        t_y0 = min(w[1] for w in words)
                        t_x1 = max(w[2] for w in words)
                        t_y1 = max(w[3] for w in words)
                        table_bbox = (t_x0, t_y0, t_x1, t_y1)
                    else:
                        table_bbox = bbox
                    tables.append(ExtractedTable(
                        page_num=page_num,
                        table_index=table_idx,
                        bbox=table_bbox,
                        headers=[],
                        rows=word_rows,
                        caption=caption_text,
                    ))
                    matched_nums.add(num)
                    table_idx += 1
                    logger.debug(
                        "Word-based table '%s' on page %d (%d rows)",
                        caption_text[:60], page_num, len(word_rows),
                    )
                    continue

            # --- Fall back to prose extraction ---
            content = _collect_prose_table_content(page, y_center, bbox)
            if not content:
                continue

            parsed_rows = _parse_prose_rows(content)
            # Strip absorbed caption from prose rows
            absorbed_cap, _, parsed_rows = _strip_absorbed_caption([], parsed_rows)
            if absorbed_cap and not caption_text:
                caption_text = absorbed_cap
            tables.append(ExtractedTable(
                page_num=page_num,
                table_index=table_idx,
                bbox=bbox,
                headers=[],
                rows=parsed_rows,
                caption=caption_text,
            ))
            matched_nums.add(num)
            table_idx += 1
            logger.debug(
                "Prose table '%s' extracted on page %d (%d chars)",
                caption_text[:60], page_num, len(content),
            )

    return tables


def _collect_prose_table_content(
    page: pymupdf.Page,
    caption_y: float,
    caption_bbox: tuple[float, float, float, float] | None = None,
) -> str:
    """Collect text blocks below a caption until body text resumes.

    Heuristic: collect blocks whose top edge is below the caption y-center,
    stopping when we encounter a block that looks like body text (long
    paragraph without definition-list structure) or another caption.

    When *caption_bbox* is provided, only blocks with meaningful horizontal
    overlap (>30 pt) with the caption are considered.  This prevents
    collecting body-text from the wrong column in multi-column layouts.
    """
    _MIN_X_OVERLAP = 30  # pts

    text_dict = page.get_text("dict")
    candidates: list[tuple[float, str]] = []

    for block in text_dict.get("blocks", []):
        if block.get("type") != 0:
            continue
        block_bbox = block.get("bbox", (0, 0, 0, 0))
        block_top = block_bbox[1]

        # Only consider blocks below the caption
        if block_top < caption_y + 5:
            continue

        # x-overlap filter: reject blocks from a different column
        if caption_bbox is not None:
            x_overlap = min(caption_bbox[2], block_bbox[2]) - max(caption_bbox[0], block_bbox[0])
            if x_overlap < _MIN_X_OVERLAP:
                continue

        block_text = ""
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                block_text += span.get("text", "")
            block_text += " "
        block_text = block_text.strip()

        if not block_text:
            continue

        candidates.append((block_top, block_text))

    # Sort by y-position (pymupdf block order is not guaranteed visual order)
    candidates.sort(key=lambda t: t[0])

    blocks_below: list[tuple[float, str]] = []
    for block_top, block_text in candidates:
        # Stop at another caption or section heading
        if _TABLE_CAPTION_RE.match(block_text) or _FIG_CAPTION_RE_COMP.match(block_text):
            break

        # Stop at long body-text paragraphs (>500 chars without
        # definition-list markers like ":", "=", ";")
        if len(block_text) > 500:
            def_markers = block_text.count(":") + block_text.count("=") + block_text.count(";")
            if def_markers < 3:
                break  # looks like body text, not a table

        # After the first block, reject body-text bleed: >300 chars, no
        # definition markers, starts with a lowercase letter
        if blocks_below and len(block_text) > 300:
            def_markers = block_text.count(":") + block_text.count("=") + block_text.count(";")
            if def_markers < 2 and block_text[0].islower():
                break

        blocks_below.append((block_top, block_text))

    if not blocks_below:
        return ""

    blocks_below = blocks_below[:20]
    return "\n".join(text for _, text in blocks_below)


# ---------------------------------------------------------------------------
# Content quality detection
# ---------------------------------------------------------------------------

_MATH_GREEK_RE = re.compile(r"[\u0391-\u03C9\u2200-\u22FF=±×÷²³∑∏∫∂∇]")

def _detect_garbled_spacing(text: str) -> tuple[bool, str]:
    """Flag text where average word length > 25 chars (missing word spaces).

    Skips cells containing Greek letters or math operators — these are
    legitimate technical content, not garbled extraction artifacts.
    Also excludes hyphenated words from the average computation, since
    compound technical terms (e.g. "sulfamethoxazole-trimethoprim") are
    legitimate long words.

    Returns (is_garbled, reason).
    """
    if not text or not text.strip():
        return False, ""
    if _MATH_GREEK_RE.search(text):
        return False, ""
    words = text.split()
    if not words:
        return False, ""
    # Exclude hyphenated words from average (they're compound terms, not garbled)
    non_hyphenated = [w for w in words if "-" not in w]
    if not non_hyphenated:
        return False, ""
    avg_len = sum(len(w) for w in non_hyphenated) / len(non_hyphenated)
    if avg_len > 25:
        return True, f"avg word length {avg_len:.0f} chars (likely merged words)"
    return False, ""


def _normalize_ligatures(text: str | None) -> str | None:
    """Replace common ligature codepoints with their ASCII equivalents."""
    if not text:
        return text
    for lig, replacement in _LIGATURE_MAP.items():
        text = text.replace(lig, replacement)
    return text


def _detect_interleaved_chars(text: str) -> tuple[bool, str]:
    """Flag text where >40% of tokens are single alphabetic characters.

    Only counts alphabetic single-char tokens.  Digits, punctuation,
    and decimal numbers (e.g. ".906", ",") are not interleaving signals.

    Min token count scales with cell size: max(5, len(text)//10).

    Returns (is_interleaved, reason).
    """
    if not text or not text.strip():
        return False, ""
    tokens = text.split()
    min_tokens = max(5, len(text) // 10)
    if len(tokens) < min_tokens:
        return False, ""
    single_chars = sum(1 for t in tokens if len(t) == 1 and t.isalpha())
    ratio = single_chars / len(tokens)
    if ratio > 0.4:
        return True, f"{ratio:.0%} of tokens are single alpha chars (likely interleaved columns)"
    return False, ""


def _detect_encoding_artifacts(text: str) -> tuple[bool, list[str]]:
    """Detect ligature glyphs that indicate encoding problems.

    Returns (has_artifacts, list of found artifact strings).
    """
    # Common ligature codepoints that appear when PDF text extraction
    # fails to decompose ligatures
    _LIGATURES = [
        "\ufb00",  # ff
        "\ufb01",  # fi
        "\ufb02",  # fl
        "\ufb03",  # ffi
        "\ufb04",  # ffl
    ]
    if not text:
        return False, []
    found = [lig for lig in _LIGATURES if lig in text]
    return bool(found), found


def _check_content_readability(table: "ExtractedTable") -> dict:
    """Combine all quality checks into a per-table report.

    Returns dict with keys: garbled_cells, interleaved_cells,
    encoding_artifacts (bool), details (list[str]).
    """
    garbled = 0
    interleaved = 0
    has_encoding = False
    details: list[str] = []

    for ri, row in enumerate(table.rows):
        for ci, cell in enumerate(row):
            g, g_reason = _detect_garbled_spacing(cell)
            if g:
                garbled += 1
                details.append(f"row {ri} col {ci}: {g_reason}")
            i, i_reason = _detect_interleaved_chars(cell)
            if i:
                interleaved += 1
                details.append(f"row {ri} col {ci}: {i_reason}")

    if table.caption:
        enc, enc_list = _detect_encoding_artifacts(table.caption)
        if enc:
            has_encoding = True
            details.append(f"caption encoding artifacts: {enc_list}")

    return {
        "garbled_cells": garbled,
        "interleaved_cells": interleaved,
        "encoding_artifacts": has_encoding,
        "details": details,
    }


# ---------------------------------------------------------------------------
# Stats and quality grading
# ---------------------------------------------------------------------------

def _compute_stats(
    pages: list[PageExtraction], page_chunks: list[dict],
    doc: pymupdf.Document | None = None,
) -> dict:
    """Compute extraction statistics.

    If doc is provided, detects OCR pages by comparing native text
    (page.get_text()) with the markdown output. Pages where native
    text is empty but markdown has content were processed by OCR.
    """
    total_pages = len(pages)
    text_pages = 0
    empty_pages = 0
    ocr_pages = 0

    for i, page in enumerate(pages):
        md = page.markdown.strip()
        if md:
            text_pages += 1
            # Check if this page needed OCR
            if doc and i < len(doc):
                native_text = doc[i].get_text().strip()
                if len(native_text) < 20 and len(md) > 20:
                    ocr_pages += 1
        else:
            empty_pages += 1

    return {
        "total_pages": total_pages,
        "text_pages": text_pages,
        "ocr_pages": ocr_pages,
        "empty_pages": empty_pages,
    }


def _compute_completeness(
    doc: pymupdf.Document,
    pages: list[PageExtraction],
    sections: list[SectionSpan],
    tables: list[ExtractedTable],
    figures: list[ExtractedFigure],
    stats: dict,
) -> "ExtractionCompleteness":
    from .models import ExtractionCompleteness
    from ._figure_extraction import find_all_captions_on_page, _FIG_LABEL_ONLY_RE

    fig_nums: set[str] = set()
    tab_nums: set[str] = set()

    for page in doc:
        for _, caption_text, _ in find_all_captions_on_page(
            page, _FIG_CAPTION_RE_COMP,
            relaxed_re=_FIG_CAPTION_RE_COMP_RELAXED,
            label_only_re=_FIG_LABEL_ONLY_RE,
        ):
            m = _CAPTION_NUM_RE.search(caption_text)
            if m:
                fig_nums.add(m.group(1))
        for _, caption_text, _ in find_all_captions_on_page(
            page, _TABLE_CAPTION_RE_COMP,
            relaxed_re=_TABLE_CAPTION_RE_COMP_RELAXED,
            label_only_re=_TABLE_LABEL_ONLY_RE,
        ):
            m = _CAPTION_NUM_RE.search(caption_text)
            if m:
                tab_nums.add(m.group(1))

    # Exclude artifact-tagged tables from all completeness counts
    real_tables = [t for t in tables if not t.artifact_type]

    figures_with_captions = sum(1 for f in figures if f.caption)
    tables_with_captions = sum(1 for t in real_tables if t.caption)

    # --- Content quality signals ---
    garbled_cells = 0
    interleaved_cells = 0
    encoding_artifact_captions = 0
    tables_1x1 = 0
    for t in real_tables:
        report = _check_content_readability(t)
        garbled_cells += report["garbled_cells"]
        interleaved_cells += report["interleaved_cells"]
        if report["encoding_artifacts"]:
            encoding_artifact_captions += 1
        if t.num_rows <= 1 and t.num_cols <= 1:
            tables_1x1 += 1

    # Duplicate captions: count caption texts that appear more than once.
    # Exclude "(continued)" captions — multi-page tables legitimately
    # produce multiple continuation captions with the same text.
    _CONTINUED_RE = re.compile(r"\(continued\)", re.IGNORECASE)
    all_captions: list[str] = []
    for f in figures:
        if f.caption and not _CONTINUED_RE.search(f.caption):
            all_captions.append(f.caption.strip())
    for t in real_tables:
        if t.caption and not _CONTINUED_RE.search(t.caption):
            all_captions.append(t.caption.strip())
    seen_captions: set[str] = set()
    duplicate_captions = 0
    for cap in all_captions:
        if cap in seen_captions:
            duplicate_captions += 1
        seen_captions.add(cap)

    # Caption number gaps: find missing integers in 1..max sequences
    def _find_gaps(nums: set[str]) -> list[str]:
        int_nums = set()
        for n in nums:
            try:
                int_nums.add(int(n))
            except ValueError:
                pass  # skip non-integer like "A.1", "S1"
        if not int_nums:
            return []
        full_range = set(range(1, max(int_nums) + 1))
        missing = sorted(full_range - int_nums)
        return [str(m) for m in missing]

    # Compute gaps from caption numbers found on pages
    figure_number_gaps = _find_gaps(fig_nums)
    table_number_gaps = _find_gaps(tab_nums)

    # Unmatched captions: caption numbers found on pages but not on any
    # extracted object's caption.  This is a set-level check (not just count).
    _cap_num_re = re.compile(r"(?:Table|Tab\.?|Figure|Fig\.?)\s+(\d+)", re.IGNORECASE)

    matched_fig_nums: set[str] = set()
    for f in figures:
        if f.caption:
            m = _cap_num_re.search(f.caption)
            if m:
                matched_fig_nums.add(m.group(1))

    matched_tab_nums: set[str] = set()
    for t in real_tables:
        if t.caption:
            m = _cap_num_re.search(t.caption)
            if m:
                matched_tab_nums.add(m.group(1))

    unmatched_fig = sorted(fig_nums - matched_fig_nums, key=lambda x: (len(x), x))
    unmatched_tab = sorted(tab_nums - matched_tab_nums, key=lambda x: (len(x), x))

    return ExtractionCompleteness(
        text_pages=stats.get("text_pages", 0),
        empty_pages=stats.get("empty_pages", 0),
        ocr_pages=stats.get("ocr_pages", 0),
        figures_found=len(figures),
        figure_captions_found=len(fig_nums),
        figures_missing=max(0, len(fig_nums) - len(figures)),
        tables_found=len(real_tables),
        table_captions_found=len(tab_nums),
        tables_missing=max(0, len(tab_nums) - len(real_tables)),
        figures_with_captions=figures_with_captions,
        tables_with_captions=tables_with_captions,
        sections_identified=len([s for s in sections if s.label != "preamble"]),
        unknown_sections=len([s for s in sections if s.label == "unknown"]),
        has_abstract=any(s.label == "abstract" for s in sections),
        garbled_table_cells=garbled_cells,
        interleaved_table_cells=interleaved_cells,
        encoding_artifact_captions=encoding_artifact_captions,
        tables_1x1=tables_1x1,
        duplicate_captions=duplicate_captions,
        figure_number_gaps=figure_number_gaps,
        table_number_gaps=table_number_gaps,
        unmatched_figure_captions=unmatched_fig,
        unmatched_table_captions=unmatched_tab,
    )
