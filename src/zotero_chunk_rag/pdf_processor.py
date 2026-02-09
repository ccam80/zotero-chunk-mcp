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

# Pattern for matching table captions
_TABLE_CAPTION_RE = re.compile(
    r"^(?:\*\*)?(?:Table|Tab\.)\s+(\d+|[IVXLCDM]+)\s*[.:()\u2014\u2013-]",
    re.IGNORECASE,
)

# Relaxed table caption regex — no delimiter required after the number.
# Only used when font-change detection confirms a distinct label font.
_TABLE_CAPTION_RE_RELAXED = re.compile(
    r"^(?:\*\*)?(?:Table|Tab\.)\s+(\d+|[IVXLCDM]+)\s+\S",
    re.IGNORECASE,
)

# Label-only regex — matches "Table N" on its own line (no description).
_TABLE_LABEL_ONLY_RE = re.compile(
    r"^(?:\*\*)?(?:Table|Tab\.?)\s+(\d+|[IVXLCDM]+)\s*$",
    re.IGNORECASE,
)

# Patterns for caption completeness counting
_FIG_CAPTION_RE_COMP = re.compile(
    r"^(?:Figure|Fig\.?)\s+(\d+|[IVXLCDM]+)\s*[.:()\u2014\u2013-]", re.IGNORECASE,
)
_FIG_CAPTION_RE_COMP_RELAXED = re.compile(
    r"^(?:Figure|Fig\.?)\s+(\d+|[IVXLCDM]+)\s+\S", re.IGNORECASE,
)
_TABLE_CAPTION_RE_COMP = re.compile(
    r"^(?:\*\*)?(?:Table|Tab\.)\s+(\d+|[IVXLCDM]+)\s*[.:()\u2014\u2013-]", re.IGNORECASE,
)
_TABLE_CAPTION_RE_COMP_RELAXED = re.compile(
    r"^(?:\*\*)?(?:Table|Tab\.)\s+(\d+|[IVXLCDM]+)\s+\S", re.IGNORECASE,
)
_CAPTION_NUM_RE = re.compile(r"(\d+)")


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

    # Compute extraction stats (needs open doc for OCR detection)
    stats = _compute_stats(pages, page_chunks, doc)
    completeness = _compute_completeness(doc, pages, sections, tables, figures, stats)
    doc.close()

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

        # Skip references/appendix sections (abbreviation lists, reference
        # lists get parsed as tables)
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

        # Match tables to captions by order
        for i, (_, bbox, headers, rows) in enumerate(page_tables):
            caption = caption_hits[i][1] if i < len(caption_hits) else None

            # Filter garbage tables: very low fill + no caption = misclassified
            # layout element (block diagrams, reference lists parsed as grids)
            total_cells = len(rows) * max(len(r) for r in rows) if rows else 0
            filled_cells = sum(1 for r in rows for c in r if c.strip())
            fill_rate = filled_cells / max(1, total_cells)
            if fill_rate < 0.15 and caption is None:
                logger.debug(
                    "Skipping garbage table on page %d: %dx%d fill=%.0f%% no caption",
                    page_num, len(rows), max(len(r) for r in rows) if rows else 0,
                    fill_rate * 100,
                )
                continue

            tables.append(ExtractedTable(
                page_num=page_num,
                table_index=table_idx,
                bbox=tuple(bbox),
                headers=headers,
                rows=rows,
                caption=caption,
            ))
            table_idx += 1

    return tables


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
    )


