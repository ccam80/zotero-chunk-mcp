"""Figure extraction using pymupdf-layout picture boxes + pixmap rendering.

Strategy:
1. Collect picture-class and table-class boxes from pymupdf4llm page_chunks
2. Filter out small boxes (logos, icons) by area threshold
3. Find figure captions via regex on each page's text
4. For caption pages with no picture box, use table-class boxes as fallback
   (layout engine sometimes misclassifies figures as tables, but the bbox
   is still correct)
5. Merge adjacent/overlapping boxes on the same page into one region
6. Render each figure region to PNG via page.get_pixmap(clip=rect)
7. Pair figures with captions by vertical position order
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

import pymupdf

from .models import ExtractedFigure, SectionSpan, PageExtraction
from .section_classifier import assign_section

logger = logging.getLogger(__name__)

_FIG_CAPTION_RE = re.compile(
    r"^(?:Figure|Fig\.?)\s+(\d+|[IVXLCDM]+)\s*[.:()\u2014\u2013-]",
    re.IGNORECASE,
)

# Relaxed figure caption regex — no delimiter required after the number.
# Only used when font-change detection confirms a distinct label font.
_FIG_CAPTION_RE_RELAXED = re.compile(
    r"^(?:Figure|Fig\.?)\s+(\d+|[IVXLCDM]+)\s+\S",
    re.IGNORECASE,
)

_FIG_LABEL_ONLY_RE = re.compile(
    r"^(?:Figure|Fig\.?)\s+(\d+|[IVXLCDM]+)\s*$",
    re.IGNORECASE,
)

_MAX_CAPTION_LEN = 2000
_SUPP_PREFIX_RE = re.compile(r"^(?:supplementary|suppl?\.?)\s+", re.IGNORECASE)
_MIN_FIGURE_AREA = 15000    # ~120x125 pts; filters logos/icons
_MERGE_GAP_PTS = 50         # merge boxes within 50 pts (bridges multi-panel figure gaps)
_DEFAULT_DPI = 150


def extract_figures(
    doc: pymupdf.Document,
    page_chunks: list[dict],
    *,
    write_images: bool = False,
    images_dir: Path | None = None,
    sections: list[SectionSpan] | None = None,
    pages: list[PageExtraction] | None = None,
) -> list[ExtractedFigure]:
    """Extract figures from a PDF using layout-engine picture boxes.

    Args:
        doc: Open pymupdf.Document (same PDF that produced page_chunks).
        page_chunks: Output of pymupdf4llm.to_markdown(page_chunks=True).
        write_images: Whether to save figure images to disk.
        images_dir: Directory to write images into (required if write_images).
        sections: Section spans for filtering references-section figures.
        pages: Page extractions for section lookup.

    Returns:
        List of ExtractedFigure, sorted by (page_num, vertical position).
    """
    if write_images and images_dir:
        images_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Collect picture boxes and table boxes per page
    page_figures: dict[int, list[pymupdf.Rect]] = {}       # page_num -> [rect]
    page_table_boxes: dict[int, list[pymupdf.Rect]] = {}   # page_num -> [rect] (fallback)
    page_captions: dict[int, list[tuple[float, str]]] = {}

    for chunk in page_chunks:
        page_num = chunk.get("metadata", {}).get("page_number", 1)

        # Skip references section
        if sections and pages:
            if _is_in_references(page_num, sections, pages):
                continue

        # Collect picture and table boxes (table boxes used as fallback
        # when layout engine misclassifies a figure as a table)
        for box in chunk.get("page_boxes", []):
            bbox = box.get("bbox")
            if not bbox or len(bbox) != 4:
                continue
            x0, y0, x1, y1 = bbox
            area = abs(x1 - x0) * abs(y1 - y0)
            if area < _MIN_FIGURE_AREA:
                continue
            rect = pymupdf.Rect(x0, y0, x1, y1)
            # Clip to page bounds — layout ML sometimes produces out-of-bounds boxes
            page_rect = doc[page_num - 1].rect
            rect = rect & page_rect  # pymupdf Rect intersection
            if rect.is_empty:
                continue
            if box.get("class") == "picture":
                page_figures.setdefault(page_num, []).append(rect)
            elif box.get("class") == "table":
                page_table_boxes.setdefault(page_num, []).append(rect)

    # Step 2: Find captions on every page (not just pages with picture boxes)
    for page_num_0, page in enumerate(doc):
        page_num = page_num_0 + 1
        captions = _find_captions_on_page(
            page, _FIG_CAPTION_RE,
            relaxed_re=_FIG_CAPTION_RE_RELAXED,
            label_only_re=_FIG_LABEL_ONLY_RE,
        )
        if captions:
            page_captions[page_num] = captions

    # Step 3: Caption-driven fallback — if a page has captions but no
    # picture boxes, use table-class boxes from the layout engine.
    # The layout engine sometimes misclassifies figures as tables
    # (e.g. noname2 p12 Figure 3), but the bbox is still correct.
    for page_num, captions in page_captions.items():
        if page_num in page_figures:
            continue  # already have picture boxes
        if sections and pages:
            if _is_in_references(page_num, sections, pages):
                continue
        if page_num in page_table_boxes:
            page_figures[page_num] = list(page_table_boxes[page_num])

    # Step 4: Merge overlapping/adjacent boxes on each page
    for page_num in page_figures:
        page_figures[page_num] = _merge_rects(page_figures[page_num])

    # Step 4.5: Split picture boxes that contain multiple figures.
    # Detection: a caption's y-center falls INSIDE a picture box's y-range.
    # When found, split the box at each internal caption boundary.
    for page_num in list(page_figures.keys()):
        rects = page_figures[page_num]
        captions = page_captions.get(page_num, [])
        if len(captions) <= len(rects):
            continue  # enough boxes for all captions, no split needed

        new_rects: list[pymupdf.Rect] = []
        used_captions: set[int] = set()

        for rect in sorted(rects, key=lambda r: r.y0):
            # Find captions whose y_center falls inside this rect
            internal: list[tuple[int, float, str]] = []
            for ci, (cy, ctext) in enumerate(captions):
                if rect.y0 < cy < rect.y1:
                    internal.append((ci, cy, ctext))

            if not internal:
                new_rects.append(rect)
                continue

            # Split the box at each internal caption position.
            internal.sort(key=lambda x: x[1])
            split_y = rect.y0
            for ci, cy, ctext in internal:
                used_captions.add(ci)
                sub = pymupdf.Rect(rect.x0, split_y, rect.x1, cy)
                if not sub.is_empty and abs(sub.y1 - sub.y0) > 20:
                    new_rects.append(sub)
                split_y = cy + 40

            # Final region: from last split to bottom of original box
            final = pymupdf.Rect(rect.x0, split_y, rect.x1, rect.y1)
            if not final.is_empty and abs(final.y1 - final.y0) > 20:
                new_rects.append(final)

        if new_rects:
            page_figures[page_num] = new_rects

    # Step 5: Build ExtractedFigure list
    figures: list[ExtractedFigure] = []
    fig_idx = 0

    for page_num in sorted(page_figures.keys()):
        rects = sorted(page_figures[page_num], key=lambda r: r.y0)
        captions_with_y = page_captions.get(page_num, [])
        caption_texts = [text for _, text in captions_with_y]

        for i, rect in enumerate(rects):
            caption = caption_texts[i] if i < len(caption_texts) else None

            image_path = None
            if write_images and images_dir:
                image_path = _render_to_png(
                    doc, page_num, rect, images_dir, fig_idx
                )

            figures.append(ExtractedFigure(
                page_num=page_num,
                figure_index=fig_idx,
                bbox=(rect.x0, rect.y0, rect.x1, rect.y1),
                caption=caption,
                image_path=image_path,
            ))
            fig_idx += 1

    orphans = [f for f in figures if not f.caption]
    if orphans:
        logger.info(
            "%d/%d figures have no caption: pages %s",
            len(orphans), len(figures),
            ", ".join(str(f.page_num) for f in orphans),
        )

    return figures


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _block_has_label_font_change(block: dict) -> bool:
    """Check if a block starts with a caption label in a distinct font.

    Many papers (e.g. medical meta-analyses) format captions as bold or italic
    "Figure N" followed by normal-weight description text, without any
    punctuation delimiter. The font change between the label and the body
    is the only signal distinguishing a caption from a body-text reference.

    Returns True when the first non-whitespace span uses a different font
    from the second non-whitespace span.
    """
    spans: list[dict] = []
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            if span.get("text", "").strip():
                spans.append(span)
    if len(spans) < 2:
        return False
    return spans[0].get("font") != spans[1].get("font")


def _block_label_on_own_line(block: dict, label_only_re: re.Pattern) -> bool:
    """Check if the block's first line is just a caption label (e.g. 'Table 1').

    Detects captions where label and description are separated by a newline
    rather than punctuation:
        Table 1
        Summary of results...
    """
    lines = block.get("lines", [])
    if len(lines) < 2:
        return False
    first_line = ""
    for span in lines[0].get("spans", []):
        first_line += span.get("text", "")
    first_line = first_line.strip()
    return bool(label_only_re.match(first_line))


def _font_name_is_bold(name: str) -> bool:
    """Check if a font name indicates bold weight."""
    if name.endswith('.B') or name.endswith('.b'):
        return True
    lower = name.lower()
    return 'bold' in lower or '-bd' in lower


def _block_is_bold(block: dict) -> bool:
    """Check if a block's text is primarily in a bold font.

    Detects bold via flags (bit 4) or font name patterns (.B, -Bold, etc.).
    Some PDFs encode bold only in the font name, not in flags.
    """
    total_chars = 0
    bold_chars = 0
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            n = len(span.get("text", "").strip())
            if n == 0:
                continue
            total_chars += n
            flags = span.get("flags", 0)
            font_name = span.get("font", "")
            if (flags & 16) or _font_name_is_bold(font_name):
                bold_chars += n
    return total_chars > 0 and bold_chars > total_chars * 0.5


def _find_captions_on_page(
    page: pymupdf.Page,
    prefix_re: re.Pattern,
    *,
    relaxed_re: re.Pattern | None = None,
    label_only_re: re.Pattern | None = None,
) -> list[tuple[float, str]]:
    """Find caption text blocks matching prefix_re, sorted by y-position.

    Returns list of (y_center, caption_text).

    When relaxed_re is provided, blocks that don't match prefix_re are
    tested against relaxed_re (no delimiter required). A match is accepted
    when any of these structural signals confirm it's a caption:
    - Font change between label and body text (bold/italic label)
    - Label on its own line (newline after "Table N" / "Figure N")
    - Entire block is in bold font (single-font bold captions)
    """
    text_dict = page.get_text("dict")
    hits: list[tuple[float, str]] = []

    for block in text_dict.get("blocks", []):
        if block.get("type") != 0:
            continue
        block_bbox = block.get("bbox", (0, 0, 0, 0))
        y_center = (block_bbox[1] + block_bbox[3]) / 2

        block_text = ""
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                block_text += span.get("text", "")
            block_text += " "
        block_text = block_text.strip()

        if not block_text or len(block_text) > _MAX_CAPTION_LEN:
            continue
        # Strip supplementary prefixes for matching; keep original as caption
        check_text = _SUPP_PREFIX_RE.sub("", block_text)
        if prefix_re.match(check_text):
            hits.append((y_center, block_text))
        elif relaxed_re and relaxed_re.match(check_text):
            if (_block_has_label_font_change(block)
                    or (label_only_re
                        and _block_label_on_own_line(block, label_only_re))
                    or _block_is_bold(block)):
                hits.append((y_center, block_text))

    hits.sort(key=lambda x: x[0])
    return hits  # list of (y_center, text)


def find_all_captions_on_page(
    page: pymupdf.Page,
    prefix_re: re.Pattern,
    *,
    relaxed_re: re.Pattern | None = None,
    label_only_re: re.Pattern | None = None,
) -> list[tuple[float, str, tuple]]:
    """Public API used by table extraction in pdf_processor.py.

    Returns list of (y_center, caption_text, bbox) sorted by y-position.

    When relaxed_re is provided, blocks that don't match prefix_re are
    tested against relaxed_re. A match is accepted when any structural
    signal confirms it's a caption (font change, label on own line, or
    bold block).
    """
    text_dict = page.get_text("dict")
    hits: list[tuple[float, str, tuple]] = []

    for block in text_dict.get("blocks", []):
        if block.get("type") != 0:
            continue
        block_bbox = block.get("bbox", (0, 0, 0, 0))
        y_center = (block_bbox[1] + block_bbox[3]) / 2

        block_text = ""
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                block_text += span.get("text", "")
            block_text += " "
        block_text = block_text.strip()

        if not block_text or len(block_text) > _MAX_CAPTION_LEN:
            continue
        # Strip supplementary prefixes for matching; keep original as caption
        check_text = _SUPP_PREFIX_RE.sub("", block_text)
        if prefix_re.match(check_text):
            hits.append((y_center, block_text, tuple(block_bbox)))
        elif relaxed_re and relaxed_re.match(check_text):
            if (_block_has_label_font_change(block)
                    or (label_only_re
                        and _block_label_on_own_line(block, label_only_re))
                    or _block_is_bold(block)):
                hits.append((y_center, block_text, tuple(block_bbox)))

    hits.sort(key=lambda x: x[0])
    return hits



def _merge_rects(rects: list[pymupdf.Rect]) -> list[pymupdf.Rect]:
    """Merge overlapping or nearby rectangles.

    Two rects merge if they overlap or are within _MERGE_GAP_PTS of each other.
    """
    if not rects:
        return []

    # Sort by y0 then x0
    rects = sorted(rects, key=lambda r: (r.y0, r.x0))
    merged: list[pymupdf.Rect] = [pymupdf.Rect(rects[0])]

    for rect in rects[1:]:
        last = merged[-1]
        # Expand last by gap for overlap check
        expanded = pymupdf.Rect(
            last.x0 - _MERGE_GAP_PTS,
            last.y0 - _MERGE_GAP_PTS,
            last.x1 + _MERGE_GAP_PTS,
            last.y1 + _MERGE_GAP_PTS,
        )
        if expanded.intersects(rect):
            # Merge: union of the two rects
            merged[-1] = last | rect
        else:
            merged.append(pymupdf.Rect(rect))

    return merged


def _render_to_png(
    doc: pymupdf.Document,
    page_num: int,
    rect: pymupdf.Rect,
    images_dir: Path,
    fig_idx: int,
) -> Path | None:
    """Render a page region to a PNG file."""
    try:
        page = doc[page_num - 1]
        pix = page.get_pixmap(clip=rect, dpi=_DEFAULT_DPI)
        fname = f"fig_p{page_num:03d}_{fig_idx:02d}.png"
        out_path = images_dir / fname
        pix.save(str(out_path))
        return out_path
    except Exception as e:
        logger.warning("Failed to render figure %d on page %d: %s",
                       fig_idx, page_num, e)
        return None


def _is_in_references(
    page_num: int,
    sections: list[SectionSpan],
    pages: list[PageExtraction],
) -> bool:
    """Check if a page falls within the references section."""
    for p in pages:
        if p.page_num == page_num:
            label = assign_section(p.char_start, sections)
            return label == "references"
    return False
