"""PDF extraction via pymupdf4llm with pymupdf-layout.

pymupdf-layout MUST be imported before pymupdf4llm to activate
ML-based layout detection (tables, figures, headers, footers, OCR).
"""
from __future__ import annotations

import logging
import math
import re
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING

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
from .section_classifier import categorize_heading, categorize_by_position

if TYPE_CHECKING:
    from .config import Config

logger = logging.getLogger(__name__)

# Pattern for filtering page identifiers from section-header boxes (e.g. "R1356")
_PAGE_ID_RE = re.compile(r"^R?\d+$")

# Pattern for matching table captions
_TABLE_CAPTION_RE = re.compile(
    r"^(?:\*\*)?(?:Table|Tab\.)\s+(\d+|[IVXLCDM]+)",
    re.IGNORECASE,
)


def extract_document(
    pdf_path: Path | str,
    *,
    write_images: bool = False,
    images_dir: Path | str | None = None,
    table_strategy: str = "lines_strict",
    image_size_limit: float = 0.05,
    figures_min_size: int = 100,
    ocr_language: str = "eng",
    config: Config | None = None,
) -> DocumentExtraction:
    """Extract a PDF document using pymupdf4llm with layout detection."""
    pdf_path = Path(pdf_path)

    kwargs: dict = dict(
        page_chunks=True,
        write_images=False,
        table_strategy=table_strategy,
        image_size_limit=image_size_limit,
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

    tables = _extract_tables_native(doc)

    from ._figure_extraction import _extract_figures_native
    figures = _extract_figures_native(
        doc,
        min_size=figures_min_size,
        write_images=write_images,
        images_dir=Path(images_dir) if images_dir else None,
        sections=sections,
        pages=pages,
    )

    doc.close()

    # Compute extraction stats
    stats = _compute_stats(pages, page_chunks)

    # Compute quality grade
    quality_grade = _compute_quality_grade(pages, stats, config)

    return DocumentExtraction(
        pages=pages,
        full_markdown=full_markdown,
        sections=sections,
        tables=tables,
        figures=figures,
        stats=stats,
        quality_grade=quality_grade,
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

    # Three-pass classification:
    # Pass 1: Keyword-match all entries
    # Pass 2: Resolve deferred level-1 entries by position (using keyword-matched neighbours)
    # Pass 3: Inherit level-2 entries from their resolved level-1 parent

    # Build parallel lists: classified labels and the matched entry info
    entries: list[tuple[int, int, str, str]] = matched  # (offset, level, toc_title, heading_text)
    labels: list[str] = []
    confs: list[float] = []

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

    # Pass 2: resolve deferred level-1 entries iteratively
    # Process in order so each resolution informs the next
    for i in range(len(entries)):
        if labels[i] != "__deferred__" or entries[i][1] != 1:
            continue
        prev_cat = _find_resolved_neighbour(labels, i, direction=-1)
        next_keyword_cat = _find_keyword_neighbour(labels, confs, i, direction=1)
        frac = entries[i][0] / total_len if total_len > 0 else 0
        # Use keyword-matched next neighbour for position heuristic, but
        # if the prev is "methods" and next is "conclusion" (no explicit results),
        # stay in methods rather than jumping to discussion
        if prev_cat == "methods" and next_keyword_cat in ("conclusion", "references", None):
            labels[i] = "methods"
        else:
            labels[i] = categorize_by_position(frac, prev_cat, next_keyword_cat)

    # Pass 3: resolve remaining deferred entries
    # Level-2 entries try to inherit from their level-1 parent first.
    # If no useful parent, use iterative position-based resolution with
    # the same "stay in methods" heuristic.
    for i in range(len(entries)):
        if labels[i] != "__deferred__":
            continue

        # Try level-1 parent inheritance for level-2 entries
        if entries[i][1] == 2:
            parent_label = None
            for j in range(i - 1, -1, -1):
                if entries[j][1] == 1 and labels[j] not in ("__deferred__", "unknown", "preamble"):
                    parent_label = labels[j]
                    break
            if parent_label:
                labels[i] = parent_label
                continue

        # Iterative position-based resolution with momentum
        prev_cat = _find_resolved_neighbour(labels, i, direction=-1)
        next_keyword_cat = _find_keyword_neighbour(labels, confs, i, direction=1)
        frac = entries[i][0] / total_len if total_len > 0 else 0

        if prev_cat == "methods" and next_keyword_cat in ("conclusion", "references", "discussion", None):
            labels[i] = "methods"
        else:
            labels[i] = categorize_by_position(frac, prev_cat, next_keyword_cat)

    # Build classified tuples
    classified: list[tuple[int, str, str, float]] = []
    for i in range(len(entries)):
        classified.append((entries[i][0], labels[i], entries[i][3], confs[i]))

    return _build_spans(classified, total_len)


def _find_keyword_neighbour(
    labels: list[str], confs: list[float], idx: int, direction: int
) -> str | None:
    """Find the nearest keyword-matched (confidence=1.0) label in the given direction."""
    j = idx + direction
    while 0 <= j < len(labels):
        if labels[j] != "__deferred__" and confs[j] == CONFIDENCE_SCHEME_MATCH:
            return labels[j]
        j += direction
    return None


def _find_resolved_neighbour(labels: list[str], idx: int, direction: int) -> str | None:
    """Find the nearest non-deferred label in the given direction (-1 or +1)."""
    j = idx + direction
    while 0 <= j < len(labels):
        if labels[j] != "__deferred__":
            return labels[j]
        j += direction
    return None


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

    # Resolve deferred
    for i, (offset, label, heading_text, conf) in enumerate(classified):
        if label != "__deferred__":
            continue
        prev_cat = None
        for j in range(i - 1, -1, -1):
            if classified[j][1] != "__deferred__":
                prev_cat = classified[j][1]
                break
        next_cat = None
        for j in range(i + 1, len(classified)):
            if classified[j][1] != "__deferred__":
                next_cat = classified[j][1]
                break
        frac = offset / total_len if total_len > 0 else 0
        resolved = categorize_by_position(frac, prev_cat, next_cat)
        classified[i] = (offset, resolved, heading_text, CONFIDENCE_GAP_FILL)

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


# ---------------------------------------------------------------------------
# Table extraction
# ---------------------------------------------------------------------------

def _extract_tables_native(doc: pymupdf.Document) -> list[ExtractedTable]:
    """Extract tables using PyMuPDF's native find_tables() API.

    Captions are found by scanning ALL text blocks on each page for
    "Table N" patterns, then matching to tables by vertical order.
    """
    from ._figure_extraction import find_all_captions_on_page

    tables: list[ExtractedTable] = []
    table_idx = 0

    for page_num_0, page in enumerate(doc):
        page_num = page_num_0 + 1

        tab_finder = page.find_tables()
        if not tab_finder.tables:
            continue

        # Find all "Table N" caption blocks on this page
        caption_hits = find_all_captions_on_page(page, _TABLE_CAPTION_RE)
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
    pages: list[PageExtraction], page_chunks: list[dict]
) -> dict:
    """Compute extraction statistics."""
    total_pages = len(pages)
    text_pages = 0
    empty_pages = 0

    for page in pages:
        if page.markdown.strip():
            text_pages += 1
        else:
            empty_pages += 1

    return {
        "total_pages": total_pages,
        "text_pages": text_pages,
        "ocr_pages": 0,
        "empty_pages": empty_pages,
    }


def _compute_quality_grade(
    pages: list[PageExtraction],
    stats: dict,
    config: Config | None = None,
) -> str:
    """Compute quality grade for the extraction."""
    num_pages = len(pages)
    if num_pages == 0:
        return "F"

    total_chars = sum(len(p.markdown) for p in pages)
    chars_per_page = total_chars / num_pages
    empty_fraction = stats.get("empty_pages", 0) / num_pages

    sample_text = "".join(p.markdown for p in pages)[:100000].lower()
    char_counts = Counter(sample_text)
    total = len(sample_text)
    entropy = 0.0
    if total > 0:
        for count in char_counts.values():
            p = count / total
            entropy -= p * math.log2(p)

    threshold_a = config.quality_threshold_a if config else 2000
    threshold_b = config.quality_threshold_b if config else 1000
    threshold_c = config.quality_threshold_c if config else 500
    threshold_d = config.quality_threshold_d if config else 100
    entropy_min = config.quality_entropy_min if config else 4.0

    if chars_per_page > threshold_a and empty_fraction < 0.1 and entropy > entropy_min:
        return "A"
    elif chars_per_page > threshold_b and empty_fraction < 0.2:
        return "B"
    elif chars_per_page > threshold_c:
        return "C"
    elif chars_per_page > threshold_d:
        return "D"
    else:
        return "F"
