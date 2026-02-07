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
        write_images=write_images,
        table_strategy=table_strategy,
        image_size_limit=image_size_limit,
        show_progress=False,
    )
    if images_dir is not None:
        kwargs["image_path"] = str(images_dir)

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

    # Extract tables using page_boxes
    tables = _extract_tables(page_chunks, pages)

    # Extract figures using page_boxes
    figures = _extract_figures(page_chunks, figures_min_size)

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

def _extract_tables(
    page_chunks: list[dict],
    pages: list[PageExtraction],
) -> list[ExtractedTable]:
    """Extract tables using page_boxes (class=table, class=caption)."""
    tables = []
    table_idx = 0

    for chunk in page_chunks:
        page_num = chunk.get("metadata", {}).get("page_number", 1)
        text = chunk.get("text", "")
        boxes = chunk.get("page_boxes", [])

        table_boxes = [b for b in boxes if b.get("class") == "table"]
        caption_boxes = [b for b in boxes if b.get("class") == "caption"]

        # Pre-assign captions to tables on this page using ordered matching
        table_captions = _assign_captions_to_elements(
            table_boxes, caption_boxes, text, prefix="table"
        )

        for i, tbox in enumerate(table_boxes):
            pos = tbox.get("pos")
            bbox = tuple(tbox.get("bbox", (0, 0, 0, 0)))

            if not (pos and isinstance(pos, (list, tuple)) and len(pos) == 2):
                continue
            table_md = text[pos[0]:pos[1]]

            parsed = _parse_pipe_table_from_md(table_md)
            if parsed is None:
                continue
            headers, rows = parsed

            # Skip header-only tables
            if not rows:
                continue

            caption = table_captions.get(i)

            tables.append(ExtractedTable(
                page_num=page_num,
                table_index=table_idx,
                bbox=bbox,
                headers=headers,
                rows=rows,
                caption=caption,
            ))
            table_idx += 1

    return tables


def _parse_pipe_table_from_md(table_md: str) -> tuple[list[str], list[list[str]]] | None:
    """Parse a pipe-table markdown string into (headers, rows)."""
    lines = [line for line in table_md.split("\n")
             if line.strip().startswith("|") and "|" in line.strip()[1:]]

    if len(lines) < 2:
        return None

    header_cells = [c.strip() for c in lines[0].strip("|").split("|")]

    sep_line = lines[1].strip()
    has_separator = bool(re.match(r"^\|[\s:]*-+", sep_line))

    if has_separator:
        headers = header_cells
        data_start = 2
    else:
        headers = []
        data_start = 0

    rows: list[list[str]] = []
    for line in lines[data_start:]:
        if re.match(r"^\|[\s:]*-+", line.strip()):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        rows.append(cells)

    if not headers and not rows:
        return None

    return headers, rows


def _assign_captions_to_elements(
    element_boxes: list[dict],
    caption_boxes: list[dict],
    page_text: str,
    prefix: str = "",
) -> dict[int, str]:
    """Assign captions to elements using ordered matching.

    Sorts both elements and matching captions by vertical position (y-coordinate),
    then pairs them in order. This avoids the problem where a caption for element N+1
    is physically closer to element N's bounding box.

    Returns: dict mapping element index (in element_boxes) to caption text.
    """
    # Filter captions that match the prefix
    matching_captions: list[tuple[float, str]] = []  # (y_center, caption_text)
    for cb in caption_boxes:
        pos = cb.get("pos")
        if not (pos and isinstance(pos, (list, tuple)) and len(pos) == 2):
            continue
        cap_text = page_text[pos[0]:pos[1]].strip()
        cap_clean = cap_text.replace("**", "").replace("*", "").replace("_", "").strip()
        if prefix and not cap_clean.lower().startswith(prefix.lower()):
            continue
        cb_bbox = cb.get("bbox", (0, 0, 0, 0))
        if isinstance(cb_bbox, (list, tuple)) and len(cb_bbox) == 4:
            y_center = (cb_bbox[1] + cb_bbox[3]) / 2
        else:
            y_center = 0
        matching_captions.append((y_center, cap_clean))

    # Sort captions by y position
    matching_captions.sort(key=lambda x: x[0])

    # Sort elements by y position, keeping track of original indices
    elem_y: list[tuple[float, int]] = []
    for i, ebox in enumerate(element_boxes):
        bbox = ebox.get("bbox", (0, 0, 0, 0))
        if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
            y_center = (bbox[1] + bbox[3]) / 2
        else:
            y_center = 0
        elem_y.append((y_center, i))
    elem_y.sort(key=lambda x: x[0])

    # Pair in order: first element gets first caption, second gets second, etc.
    result: dict[int, str] = {}
    cap_idx = 0
    for _, orig_idx in elem_y:
        if cap_idx < len(matching_captions):
            result[orig_idx] = matching_captions[cap_idx][1]
            cap_idx += 1

    return result


def _find_nearest_caption(
    element_box: dict,
    caption_boxes: list[dict],
    page_text: str,
    prefix: str = "",
) -> str | None:
    """Find the nearest caption box matching the prefix and extract its text."""
    best_text = None
    best_dist = float("inf")

    elem_bbox = element_box.get("bbox", (0, 0, 0, 0))
    if not (isinstance(elem_bbox, (list, tuple)) and len(elem_bbox) == 4):
        elem_bbox = (0, 0, 0, 0)

    for cb in caption_boxes:
        pos = cb.get("pos")
        if not (pos and isinstance(pos, (list, tuple)) and len(pos) == 2):
            continue

        cap_text = page_text[pos[0]:pos[1]].strip()
        # Strip markdown formatting for prefix check
        cap_clean = cap_text.replace("**", "").replace("*", "").replace("_", "").strip()

        if prefix and not cap_clean.lower().startswith(prefix.lower()):
            continue

        cb_bbox = cb.get("bbox", (0, 0, 0, 0))
        if not (isinstance(cb_bbox, (list, tuple)) and len(cb_bbox) == 4):
            continue

        # Vertical distance: check both above and below
        dist_below = abs(cb_bbox[1] - elem_bbox[3])  # caption below element
        dist_above = abs(elem_bbox[1] - cb_bbox[3])   # caption above element
        dist = min(dist_below, dist_above)

        if dist < best_dist:
            best_dist = dist
            # Clean up the caption text
            best_text = cap_clean

    return best_text


# ---------------------------------------------------------------------------
# Figure extraction
# ---------------------------------------------------------------------------

def _extract_figures(
    page_chunks: list[dict],
    min_size: int = 100,
) -> list[ExtractedFigure]:
    """Extract figures using page_boxes (class=picture, class=caption)."""
    figures = []
    fig_idx = 0

    for chunk in page_chunks:
        page_num = chunk.get("metadata", {}).get("page_number", 1)
        text = chunk.get("text", "")
        boxes = chunk.get("page_boxes", [])

        picture_boxes = [b for b in boxes if b.get("class") == "picture"]
        caption_boxes = [b for b in boxes if b.get("class") == "caption"]

        # Filter picture boxes first, then assign captions
        valid_pboxes = []
        for pbox in picture_boxes:
            bbox = pbox.get("bbox", (0, 0, 0, 0))
            if not (isinstance(bbox, (list, tuple)) and len(bbox) == 4):
                continue
            width = abs(bbox[2] - bbox[0])
            height = abs(bbox[3] - bbox[1])
            if width < min_size or height < min_size:
                continue
            valid_pboxes.append(pbox)

        # Use nearest-caption matching for figures (usually 1 per page)
        fig_captions = _assign_captions_to_elements(
            valid_pboxes, caption_boxes, text, prefix="fig"
        )

        for i, pbox in enumerate(valid_pboxes):
            bbox = pbox.get("bbox", (0, 0, 0, 0))
            caption = fig_captions.get(i)

            figures.append(ExtractedFigure(
                page_num=page_num,
                figure_index=fig_idx,
                bbox=tuple(bbox),
                caption=caption,
                image_path=None,
            ))
            fig_idx += 1

    return figures


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
