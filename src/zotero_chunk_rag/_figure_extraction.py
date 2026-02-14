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

_NUM_GROUP = r"(\d+|[IVXLCDM]+|[A-Z]\.\d+|S\d+)"

_FIG_CAPTION_RE = re.compile(
    rf"^(?:Figure|Fig\.?)\s+{_NUM_GROUP}\s*[.:()\u2014\u2013-]",
    re.IGNORECASE,
)

# Relaxed figure caption regex — no delimiter required after the number.
# Only used when font-change detection confirms a distinct label font.
_FIG_CAPTION_RE_RELAXED = re.compile(
    rf"^(?:Figure|Fig\.?)\s+{_NUM_GROUP}\s+\S",
    re.IGNORECASE,
)

_FIG_LABEL_ONLY_RE = re.compile(
    rf"^(?:Figure|Fig\.?)\s+{_NUM_GROUP}\s*$",
    re.IGNORECASE,
)

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
    # Uses find_all_captions_on_page to get bbox for x-overlap checks in Step 4.5
    for page_num_0, page in enumerate(doc):
        page_num = page_num_0 + 1
        captions = find_all_captions_on_page(
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

    # Step 4.5: Split picture boxes when there are more captions than boxes.
    # Phase 1: Split boxes that have captions INSIDE their y-range.
    # Phase 2: When still outnumbered, use caption y-positions to create
    #          synthetic figure regions (handles captions below the box).
    for page_num in list(page_figures.keys()):
        rects = page_figures[page_num]
        captions = page_captions.get(page_num, [])
        if len(captions) <= len(rects):
            continue  # enough boxes for all captions, no split needed

        new_rects: list[pymupdf.Rect] = []

        for rect in sorted(rects, key=lambda r: r.y0):
            # Find captions whose y_center falls inside this rect AND
            # whose x-range overlaps (prevents 2-column false splits)
            internal: list[tuple[int, float, str]] = []
            for ci, cap in enumerate(captions):
                cy = cap[0]
                cap_bbox = cap[2] if len(cap) >= 3 else None
                if rect.y0 < cy < rect.y1:
                    # Check x-overlap if bbox available
                    if cap_bbox:
                        cap_x0, cap_x1 = cap_bbox[0], cap_bbox[2]
                        x_overlap = min(rect.x1, cap_x1) - max(rect.x0, cap_x0)
                        if x_overlap < 20:
                            continue  # different column
                    internal.append((ci, cy, cap[1]))

            if not internal:
                new_rects.append(rect)
                continue

            # Split the box at each internal caption position.
            internal.sort(key=lambda x: x[1])
            split_y = rect.y0
            for ci, cy, ctext in internal:
                sub = pymupdf.Rect(rect.x0, split_y, rect.x1, cy)
                if not sub.is_empty and abs(sub.y1 - sub.y0) > 100:
                    new_rects.append(sub)
                split_y = cy + 40

            # Final region: from last split to bottom of original box
            final = pymupdf.Rect(rect.x0, split_y, rect.x1, rect.y1)
            if not final.is_empty and abs(final.y1 - final.y0) > 100:
                new_rects.append(final)

        # Phase 2: Still more captions than rects? The extra captions are
        # outside all boxes (typically below). Only create synthetic rects
        # when the existing box region is large enough to plausibly contain
        # multiple figures (total height > 250pt per expected figure).
        if len(captions) > len(new_rects) and new_rects:
            total_height = sum(r.y1 - r.y0 for r in new_rects)
            min_height = 250 * len(captions)
            if total_height >= min_height:
                x0 = min(r.x0 for r in new_rects)
                x1 = max(r.x1 for r in new_rects)
                for cap in sorted(captions, key=lambda c: c[0]):
                    cy = cap[0]
                    covered = any(r.y0 - 30 <= cy <= r.y1 + 30 for r in new_rects)
                    if covered:
                        continue
                    fig_top = max(cy - 200, 0)
                    fig_bot = cy - 10
                    if fig_bot > fig_top + 20:
                        new_rects.append(pymupdf.Rect(x0, fig_top, x1, fig_bot))

        if new_rects:
            page_figures[page_num] = new_rects

    # Step 5: Build ExtractedFigure list — proximity-based caption matching
    figures: list[ExtractedFigure] = []
    fig_idx = 0

    for page_num in sorted(page_figures.keys()):
        rects = sorted(page_figures[page_num], key=lambda r: r.y0)
        captions_with_y = page_captions.get(page_num, [])

        # Match captions to figure boxes by proximity (not positional index)
        rect_bboxes = [(r.x0, r.y0, r.x1, r.y1) for r in rects]
        matched_captions = _match_by_proximity(rect_bboxes, captions_with_y)

        for i, rect in enumerate(rects):
            caption = matched_captions[i]

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



def _scan_lines_for_caption(
    block: dict,
    prefix_re: re.Pattern,
    relaxed_re: re.Pattern | None,
    label_only_re: re.Pattern | None,
) -> str | None:
    """Scan individual lines of a block for a caption pattern.

    When PyMuPDF merges preceding text (axis labels, column headers) into
    the same block as a caption, the block-start regex fails. This scans
    each line and returns text from the first matching line onward.

    Returns caption text or None.
    """
    lines = block.get("lines", [])
    if len(lines) < 2:
        return None  # single-line block already tested at block level

    # Only scan first 5 lines — captions merged with axis labels are
    # always near block start. Body text "Fig. N" references buried
    # deep in a paragraph (line 20+) are not captions.
    max_scan = min(5, len(lines))
    for line_idx in range(1, max_scan):  # skip line 0 (already tested)
        line = lines[line_idx]
        line_text = ""
        for span in line.get("spans", []):
            line_text += span.get("text", "")
        line_text = line_text.strip()
        if not line_text:
            continue

        check_line = _SUPP_PREFIX_RE.sub("", line_text)
        if prefix_re.match(check_line):
            # Build text from this line onward
            return _text_from_line_onward(block, line_idx)
        if relaxed_re and relaxed_re.match(check_line):
            # For mid-block relaxed matches, require font change or bold
            # (same structural checks as block-level)
            sub_block = {"lines": lines[line_idx:]}
            if (_block_has_label_font_change(sub_block)
                    or _block_is_bold(sub_block)):
                return _text_from_line_onward(block, line_idx)

    return None


def _text_from_line_onward(block: dict, start_line_idx: int) -> str:
    """Extract text from a specific line index onward in a block."""
    text = ""
    for line in block.get("lines", [])[start_line_idx:]:
        for span in line.get("spans", []):
            text += span.get("text", "")
        text += " "
    return text.strip()


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

        if not block_text:
            continue

        # Strip supplementary prefixes for matching
        check_text = _SUPP_PREFIX_RE.sub("", block_text)
        matched = False
        caption_text = block_text  # default: full block
        if prefix_re.match(check_text):
            matched = True
        elif relaxed_re and relaxed_re.match(check_text):
            if (_block_has_label_font_change(block)
                    or (label_only_re
                        and _block_label_on_own_line(block, label_only_re))
                    or _block_is_bold(block)):
                matched = True

        # A2 fallback: if block didn't match at start, scan individual lines.
        # PyMuPDF sometimes merges axis labels or column headers into the
        # same block as the caption (e.g. "Time (s)\nFigure 5. ...").
        if not matched:
            caption_text = _scan_lines_for_caption(
                block, prefix_re, relaxed_re, label_only_re,
            )
            if caption_text:
                matched = True

        if matched:
            hits.append((y_center, caption_text))

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

        if not block_text:
            continue

        # Strip supplementary prefixes for matching
        check_text = _SUPP_PREFIX_RE.sub("", block_text)
        matched = False
        caption_text = block_text  # default: full block
        if prefix_re.match(check_text):
            matched = True
        elif relaxed_re and relaxed_re.match(check_text):
            if (_block_has_label_font_change(block)
                    or (label_only_re
                        and _block_label_on_own_line(block, label_only_re))
                    or _block_is_bold(block)):
                matched = True

        # A2 fallback: line-by-line scan for mid-block captions
        if not matched:
            caption_text = _scan_lines_for_caption(
                block, prefix_re, relaxed_re, label_only_re,
            )
            if caption_text:
                matched = True

        if matched:
            hits.append((y_center, caption_text, tuple(block_bbox)))

    hits.sort(key=lambda x: x[0])
    return hits



_CAPTION_NUM_RE = re.compile(r"(\d+)")


def _match_by_proximity(
    objects: list[tuple[float, float, float, float]],
    captions: list[tuple[float, str]] | list[tuple[float, str, tuple]],
) -> list[str | None]:
    """Match captions to objects by number ordering, with proximity fallback.

    Primary strategy: parse caption numbers, sort by number, match to objects
    sorted by y-position. This preserves the logical ordering (Table 1 → first
    table, Table 2 → second table).

    Fallback (when numbers aren't available): greedy nearest-first by
    edge-to-caption y-distance.

    Args:
        objects: List of bboxes (x0, y0, x1, y1) for each figure/table.
        captions: List of (y_center, text, ...) for each caption.

    Returns:
        List parallel to objects, with caption text or None.
    """
    if not objects:
        return []
    if not captions:
        return [None] * len(objects)

    # Try number-ordered matching first
    numbered: list[tuple[str, int, str]] = []  # (num_key, cap_idx, text)
    unnumbered: list[tuple[int, str]] = []
    for ci, cap in enumerate(captions):
        text = cap[1]
        m = _CAPTION_NUM_RE.search(text)
        if m:
            numbered.append((m.group(1), ci, text))
        else:
            unnumbered.append((ci, text))

    if numbered:
        # Sort captions by number, objects by y-position
        def num_sort_key(item):
            num_str = item[0]
            try:
                return (0, int(num_str))
            except ValueError:
                return (1, num_str)  # non-numeric appendix numbers sort after

        numbered.sort(key=num_sort_key)
        obj_order = sorted(range(len(objects)), key=lambda i: objects[i][1])

        result = [None] * len(objects)
        for i, oi in enumerate(obj_order):
            if i < len(numbered):
                result[oi] = numbered[i][2]

        return result

    # Fallback: y-distance matching for captions without numbers
    obj_order = sorted(range(len(objects)), key=lambda i: objects[i][1])
    cap_order = sorted(range(len(captions)), key=lambda i: captions[i][0])
    result = [None] * len(objects)
    for i, oi in enumerate(obj_order):
        if i < len(cap_order):
            result[oi] = captions[cap_order[i]][1]
    return result


def _merge_rects(rects: list[pymupdf.Rect]) -> list[pymupdf.Rect]:
    """Merge overlapping or nearby rectangles.

    Two rects merge if they overlap or are within _MERGE_GAP_PTS of each other,
    BUT only when they share meaningful horizontal overlap (>20% of the smaller
    rect's width).  This prevents side-by-side figures in 2-column layouts from
    being incorrectly merged.
    """
    if not rects:
        return []

    # Sort by y0 then x0
    rects = sorted(rects, key=lambda r: (r.y0, r.x0))
    merged: list[pymupdf.Rect] = [pymupdf.Rect(rects[0])]

    for rect in rects[1:]:
        last = merged[-1]

        # Check horizontal overlap BEFORE expanding.  Side-by-side rects
        # (different columns) have near-zero x-overlap and must not merge.
        x_overlap = min(last.x1, rect.x1) - max(last.x0, rect.x0)
        min_width = min(last.width, rect.width)
        if min_width > 0 and x_overlap / min_width < 0.2:
            merged.append(pymupdf.Rect(rect))
            continue

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
