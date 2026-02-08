"""Native PyMuPDF figure extraction.

Strategy:
1. Find all raster images on page via page.get_image_info(xrefs=True)
2. Find all caption text blocks on page via page.get_text("dict")
   that match "Figure N" / "Fig. N" patterns — ANYWHERE on the page
3. Sort both lists by vertical position, pair them in order
4. Extract image bytes via doc.extract_image(xref) when requested
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
    r"^(?:Figure|Fig\.?)\s+(\d+|[IVXLCDM]+)",
    re.IGNORECASE,
)

_MAX_CAPTION_LEN = 2000  # Academic captions can be very long (multi-panel figure descriptions)


def _extract_figures_native(
    doc: pymupdf.Document,
    *,
    min_size: int = 100,
    write_images: bool = False,
    images_dir: Path | None = None,
    sections: list[SectionSpan] | None = None,
    pages: list[PageExtraction] | None = None,
) -> list[ExtractedFigure]:
    """Extract figures using PyMuPDF native APIs."""
    figures: list[ExtractedFigure] = []
    fig_idx = 0

    if write_images and images_dir:
        images_dir.mkdir(parents=True, exist_ok=True)

    for page_num_0, page in enumerate(doc):
        page_num = page_num_0 + 1
        page_rect = page.rect

        # --- Step 1: Find all raster images on this page ---
        image_infos = page.get_image_info(xrefs=True)
        image_bboxes: list[tuple[tuple, int]] = []  # (bbox, xref)

        seen_bboxes: set[tuple] = set()
        for img_info in image_infos:
            bbox = img_info.get("bbox")
            if not bbox or len(bbox) != 4:
                continue
            # Round bbox for deduplication (same image placed multiple times)
            rounded = (round(bbox[0], 1), round(bbox[1], 1),
                       round(bbox[2], 1), round(bbox[3], 1))
            if rounded in seen_bboxes:
                continue
            seen_bboxes.add(rounded)

            xref = img_info.get("xref", 0)
            width = abs(bbox[2] - bbox[0])
            height = abs(bbox[3] - bbox[1])

            if width < min_size or height < min_size:
                continue

            # Skip full-page backgrounds
            page_w, page_h = page_rect.width, page_rect.height
            if page_w > 0 and page_h > 0:
                if (width * height) / (page_w * page_h) > 0.95:
                    continue

            # Skip references-section images
            if sections and pages:
                if _is_in_references_section(page_num, sections, pages):
                    logger.debug("Page %d: skipping image in references section", page_num)
                    continue

            image_bboxes.append((tuple(bbox), xref))

        if not image_bboxes:
            continue

        # --- Step 2: Find ALL caption text blocks on this page ---
        page_captions = _find_all_captions_on_page(page, _FIG_CAPTION_RE)

        # --- Step 3: Match figures to captions ---
        # Sort images by vertical center (reading order)
        image_bboxes.sort(key=lambda x: (x[0][1] + x[0][3]) / 2)
        # Captions already sorted by y-position from _find_all_captions_on_page

        # Assign captions to images by order: first image gets first caption, etc.
        for i, (bbox, xref) in enumerate(image_bboxes):
            caption = page_captions[i] if i < len(page_captions) else None

            # Extract image if requested
            image_path = None
            if write_images and images_dir and xref > 0:
                try:
                    img_data = doc.extract_image(xref)
                    if img_data and img_data.get("image"):
                        ext = img_data.get("ext", "png")
                        fname = f"fig_p{page_num:03d}_{fig_idx:02d}.{ext}"
                        out_path = images_dir / fname
                        out_path.write_bytes(img_data["image"])
                        image_path = out_path
                except Exception as e:
                    logger.warning(
                        "Page %d: failed to extract image xref=%d: %s",
                        page_num, xref, e,
                    )

            figures.append(ExtractedFigure(
                page_num=page_num,
                figure_index=fig_idx,
                bbox=bbox,
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


def _find_all_captions_on_page(
    page: pymupdf.Page,
    prefix_re: re.Pattern,
) -> list[str]:
    """Find all caption text blocks on a page matching prefix_re.

    Scans EVERY text block on the page (not just near images).
    Returns captions sorted by vertical position (top to bottom).
    This handles two-column layouts where caption is beside the figure.
    """
    text_dict = page.get_text("dict")
    hits: list[tuple[float, str]] = []  # (y_center, caption_text)

    for block in text_dict.get("blocks", []):
        if block.get("type") != 0:
            continue

        block_bbox = block.get("bbox", (0, 0, 0, 0))
        y_center = (block_bbox[1] + block_bbox[3]) / 2

        # Extract full text from spans
        block_text = ""
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                block_text += span.get("text", "")
            block_text += " "
        block_text = block_text.strip()

        if not block_text or len(block_text) > _MAX_CAPTION_LEN:
            continue

        if prefix_re.match(block_text):
            hits.append((y_center, block_text))

    hits.sort(key=lambda x: x[0])
    return [text for _, text in hits]


def _is_in_references_section(
    page_num: int,
    sections: list[SectionSpan],
    pages: list[PageExtraction],
) -> bool:
    """Check if a page is within the references section."""
    for p in pages:
        if p.page_num == page_num:
            label = assign_section(p.char_start, sections)
            return label == "references"
    return False


# --- Shared caption finder for tables (used by pdf_processor.py) ---

def find_all_captions_on_page(
    page: pymupdf.Page,
    prefix_re: re.Pattern,
) -> list[tuple[float, str, tuple]]:
    """Public API: find all caption blocks matching prefix_re.

    Returns list of (y_center, caption_text, bbox) sorted by y-position.
    Used by both figure and table extraction.
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

        if prefix_re.match(block_text):
            hits.append((y_center, block_text, tuple(block_bbox)))

    hits.sort(key=lambda x: x[0])
    return hits
