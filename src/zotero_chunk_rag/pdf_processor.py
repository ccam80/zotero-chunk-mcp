"""PDF extraction via pymupdf4llm with pymupdf-layout.

pymupdf-layout MUST be imported before pymupdf4llm to activate
ML-based layout detection (tables, figures, headers, footers, OCR).
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

import pymupdf.layout  # noqa: F401 — activates layout engine, MUST be before pymupdf4llm
import pymupdf4llm
import pymupdf

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

    # --- Normalize ligatures in extracted table/figure content ---
    for t in tables:
        t.caption = _normalize_ligatures(t.caption)
        t.headers = [_normalize_ligatures(h) or "" for h in t.headers]
        t.rows = [[_normalize_ligatures(c) or "" for c in row] for row in t.rows]
    for f in figures:
        f.caption = _normalize_ligatures(f.caption)

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

def _merge_over_divided_rows(
    rows: list[list[str]],
) -> list[list[str]]:
    """Merge continuation rows produced by pymupdf's find_tables().

    pymupdf often treats each wrapped text line as a separate table row,
    producing e.g. 59 rows where ~10 logical rows exist.  Pattern: a
    "continuation" row has an empty first cell, meaning it continues the
    content of the previous row.  We merge by appending each cell's text
    (space-separated) into the anchor row.

    Only triggers when >40% of rows have an empty first cell (clear
    over-division signal) and there are at least 6 rows.
    """
    if not rows or len(rows) < 6:
        return rows

    ncols = max(len(r) for r in rows)

    # Check if the table is over-divided: count rows with empty first cell
    empty_col0 = sum(
        1 for r in rows
        if len(r) == 0 or not r[0].strip()
    )
    if empty_col0 / len(rows) < 0.40:
        return rows  # most rows have col-0 content, not over-divided

    merged: list[list[str]] = []
    for row in rows:
        # Pad row to ncols
        padded = list(row) + [""] * (ncols - len(row))

        if merged and not padded[0].strip():
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

    Only touches cells detected as garbled by ``_detect_garbled_spacing``
    (avg word length > 25 chars, no Greek/math characters).  Math cells
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
            is_garbled, _ = _detect_garbled_spacing(cell_text)
            if not is_garbled:
                continue
            words = page.get_text("words", clip=pymupdf.Rect(cell_bbox))
            if not words:
                continue
            words.sort(key=lambda w: (w[1], w[0]))
            new_text = " ".join(w[4] for w in words)
            if new_text.strip():
                data[ri][ci] = new_text


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
            data = tab.extract()
            _repair_garbled_cells(page, tab, data)

            cleaned_rows = [
                [cell if cell is not None else "" for cell in row]
                for row in data
            ]
            if not cleaned_rows:
                continue

            header_names = tab.header.names if tab.header else []
            if tab.header and not tab.header.external:
                headers = [h if h is not None else "" for h in header_names]
                rows = cleaned_rows[1:]
            else:
                headers = [h if h is not None else "" for h in header_names]
                rows = cleaned_rows

            if not rows:
                continue

            max_cols = max(len(r) for r in rows) if rows else 0
            if max_cols < 2 and len(headers) < 2:
                continue

            y_center = (tab.bbox[1] + tab.bbox[3]) / 2
            page_tables.append((y_center, tab.bbox, headers, rows))

        page_tables.sort(key=lambda x: x[0])

        # Match tables to captions by proximity (not positional index)
        from ._figure_extraction import _match_by_proximity
        table_bboxes = [bbox for _, bbox, _, _ in page_tables]
        matched_captions = _match_by_proximity(table_bboxes, caption_hits)

        for i, (_, bbox, headers, rows) in enumerate(page_tables):
            caption = matched_captions[i]

            # Merge over-divided rows (pymupdf wraps multi-line cells into
            # separate rows, producing very sparse tables).
            rows = _merge_over_divided_rows(rows)
            rows, headers = _remove_empty_columns(rows, headers)

            tables.append(ExtractedTable(
                page_num=page_num,
                table_index=table_idx,
                bbox=tuple(bbox),
                headers=headers,
                rows=rows,
                caption=caption,
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

        for y_center, caption_text, bbox in caption_hits:
            m = _CAPTION_NUM_RE.search(caption_text)
            if not m:
                continue
            num = m.group(1)
            if num in matched_nums:
                continue  # already have a table for this caption

            # Capture text blocks below this caption on the same page
            content = _collect_prose_table_content(page, y_center, bbox)
            if not content:
                continue

            parsed_rows = _parse_prose_rows(content)
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

    # Cap at 20 blocks — existing stop conditions (next caption, body-text
    # paragraphs >500 chars) prevent runaway; 5 was too restrictive.
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

    Returns (is_garbled, reason).
    """
    if not text or not text.strip():
        return False, ""
    if _MATH_GREEK_RE.search(text):
        return False, ""
    words = text.split()
    if not words:
        return False, ""
    avg_len = sum(len(w) for w in words) / len(words)
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

    Returns (is_interleaved, reason).
    """
    if not text or not text.strip():
        return False, ""
    tokens = text.split()
    if len(tokens) < 5:
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

    figures_with_captions = sum(1 for f in figures if f.caption)
    tables_with_captions = sum(1 for t in tables if t.caption)

    # --- Content quality signals ---
    garbled_cells = 0
    interleaved_cells = 0
    encoding_artifact_captions = 0
    tables_1x1 = 0
    for t in tables:
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
    for t in tables:
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
    for t in tables:
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
        tables_found=len(tables),
        table_captions_found=len(tab_nums),
        tables_missing=max(0, len(tab_nums) - len(tables)),
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


