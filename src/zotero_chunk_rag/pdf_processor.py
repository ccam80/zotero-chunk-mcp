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

from .feature_extraction.captions import (
    _TABLE_CAPTION_RE,
    _TABLE_CAPTION_RE_RELAXED,
    _TABLE_LABEL_ONLY_RE,
    _FIG_CAPTION_RE as _FIG_CAPTION_RE_COMP,
)
_CAP_PATTERNS = (_TABLE_CAPTION_RE, _TABLE_CAPTION_RE_RELAXED, _TABLE_LABEL_ONLY_RE)


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


def _extract_figures_for_page(
    page: "pymupdf.Page",
    page_num: int,
    page_chunk: dict,
    write_images: bool,
    images_dir: "Path | None",
    doc: "pymupdf.Document",
) -> "list[ExtractedFigure]":
    """Detect and optionally render figures on a page."""
    from .feature_extraction.captions import find_all_captions
    from .feature_extraction.methods.figure_detection import detect_figures, render_figure

    figure_captions = [c for c in find_all_captions(page) if c.caption_type == "figure"]
    figure_results = detect_figures(page, page_chunk, figure_captions) if page_chunk else []

    figures = []
    for fi, (fbbox, fcaption) in enumerate(figure_results):
        image_path = None
        if write_images and doc is not None and images_dir is not None:
            img = render_figure(doc, page_num, fbbox, Path(images_dir), fi)
            image_path = str(img) if img else None
        figures.append(ExtractedFigure(
            page_num=page_num,
            figure_index=fi,
            bbox=tuple(fbbox),
            caption=fcaption,
            image_path=Path(image_path) if image_path else None,
        ))
    return figures



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

    tables: list[ExtractedTable] = []
    figures: list[ExtractedFigure] = []
    fig_idx = 0

    for chunk in page_chunks:
        pnum = chunk.get("metadata", {}).get("page_number", 1)
        page = doc[pnum - 1]

        page_label = None
        if sections and pages:
            from .section_classifier import assign_section
            for p in pages:
                if p.page_num == pnum:
                    page_label = assign_section(p.char_start, sections)
                    break
            if page_label in ("references", "appendix"):
                continue

        page_figs = _extract_figures_for_page(
            page, pnum, chunk, write_images, images_dir, doc,
        )
        for f in page_figs:
            f.figure_index = fig_idx
            figures.append(f)
            fig_idx += 1

    # Heading-based caption fallback for orphan tables (e.g. "Abbreviations")
    _assign_heading_captions(doc, tables)

    # Continuation table detection — orphan tables with same headers
    # as a captioned table on a nearby page get "Caption (continued)".
    _assign_continuation_captions(tables)

    # --- Normalize ligatures in captions ---
    # Captions need ligature normalization.
    for t in tables:
        t.caption = _normalize_ligatures(t.caption)
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

    # Remove false-positive figures: after all recovery passes (gap-fill,
    # heading fallback, continuation), figures still without captions are
    # layout engine misclassifications (logos, decorative elements, headers).
    figures = [f for f in figures if f.caption is not None]

    # Remove artifact tables (TOC, article-info boxes, diagram-as-table,
    # figure-data overlaps) from the returned list.
    tables = [t for t in tables if not t.artifact_type]

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
    from .feature_extraction.postprocessors.cell_cleaning import _normalize_ligatures as _impl
    return _impl(text)


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
    from .feature_extraction.captions import find_all_captions

    fig_nums: set[str] = set()
    tab_nums: set[str] = set()

    for page in doc:
        for cap in find_all_captions(page, include_figures=True, include_tables=True):
            if cap.number:
                if cap.caption_type == "figure":
                    fig_nums.add(cap.number)
                elif cap.caption_type == "table":
                    tab_nums.add(cap.number)

    # At this point, artifacts and false-positive figures have already been
    # removed by extract_document(). Work directly with the cleaned lists.
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
        figures_with_captions=len(figures),
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
