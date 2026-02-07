"""Figure extraction from PDF using PyMuPDF."""
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import pymupdf

logger = logging.getLogger(__name__)

FIGURE_CAPTION_PATTERNS = [
    # "Fig. 1", "Fig 1", "Figure 1", "FIG. 1"
    re.compile(r"^Fig(?:ure)?\.?\s*\d+", re.IGNORECASE),
    # Roman numerals: "FIGURE IV"
    re.compile(r"^FIGURE\s+[IVXLCDM]+", re.IGNORECASE),
    # Scheme (chemistry papers): "Scheme 1"
    re.compile(r"^Scheme\s*\d+", re.IGNORECASE),
    # Chart (business papers): "Chart 1"
    re.compile(r"^Chart\s*\d+", re.IGNORECASE),
    # Plate (microscopy): "Plate 1"
    re.compile(r"^Plate\s*\d+", re.IGNORECASE),
    # Graph (some papers): "Graph 1"
    re.compile(r"^Graph\s*\d+", re.IGNORECASE),
]


@dataclass
class ExtractedFigure:
    """A figure extracted from a PDF."""

    page_num: int
    figure_index: int
    bbox: tuple[float, float, float, float]
    caption: str | None  # None for orphaned figures (no caption found)
    image_path: Path | None = None  # Path to saved PNG

    def to_searchable_text(self) -> str:
        """Return text for embedding."""
        if self.caption:
            return self.caption
        return f"Figure on page {self.page_num}"


class FigureExtractor:
    """Extract figures and captions from PDF.

    Extracts images from PDFs, finds associated captions,
    and saves the images to disk for later reference.
    """

    # Minimum size to filter out icons/logos
    MIN_WIDTH = 100
    MIN_HEIGHT = 100

    def __init__(self, images_dir: Path):
        """Initialize extractor.

        Args:
            images_dir: Directory to save extracted images (alongside DB)
        """
        self.images_dir = Path(images_dir)
        self.images_dir.mkdir(parents=True, exist_ok=True)

    def extract_figures(self, pdf_path: Path, doc_id: str) -> list[ExtractedFigure]:
        """Extract all figures from PDF, saving images to disk.

        Args:
            pdf_path: Path to the PDF file
            doc_id: Document identifier (used for naming saved images)

        Returns:
            List of ExtractedFigure objects
        """
        doc = pymupdf.open(pdf_path)
        figures = []

        try:
            for page_num, page in enumerate(doc, start=1):
                page_figures = self._extract_page_figures(page, page_num, doc_id)
                figures.extend(page_figures)
        finally:
            doc.close()

        logger.debug(f"Extracted {len(figures)} figures from {pdf_path.name}")
        return figures

    def _extract_page_figures(
        self, page, page_num: int, doc_id: str
    ) -> list[ExtractedFigure]:
        """Extract figures from a single page."""
        figures = []
        image_list = page.get_images()

        for img_idx, img in enumerate(image_list):
            xref = img[0]
            rects = page.get_image_rects(xref)
            if not rects:
                continue

            bbox = rects[0]

            # Skip tiny images (icons/logos)
            width = bbox.x1 - bbox.x0
            height = bbox.y1 - bbox.y0
            if width < self.MIN_WIDTH or height < self.MIN_HEIGHT:
                continue

            # Look for caption
            caption = self._find_caption(page, bbox)

            # Save image
            try:
                image_path = self._save_image(page.parent, xref, doc_id, page_num, img_idx)
            except Exception as e:
                logger.warning(
                    f"Failed to save image {doc_id} p{page_num} f{img_idx}: {e}"
                )
                image_path = None

            figures.append(
                ExtractedFigure(
                    page_num=page_num,
                    figure_index=img_idx,
                    bbox=(bbox.x0, bbox.y0, bbox.x1, bbox.y1),
                    caption=caption,  # None if no caption found (orphan)
                    image_path=image_path,
                )
            )

        return figures

    def _save_image(
        self, doc, xref: int, doc_id: str, page_num: int, img_idx: int
    ) -> Path:
        """Save image to disk.

        Args:
            doc: PyMuPDF Document object
            xref: Image cross-reference number
            doc_id: Document identifier
            page_num: Page number (1-indexed)
            img_idx: Image index on the page

        Returns:
            Path to the saved PNG file
        """
        filename = f"{doc_id}_p{page_num:03d}_f{img_idx:02d}.png"
        image_path = self.images_dir / filename

        # Try extract_image first - it handles more formats and returns raw bytes
        img_info = doc.extract_image(xref)
        if img_info and img_info.get("image"):
            # Got raw image bytes - can save directly if it's a common format
            ext = img_info.get("ext", "").lower()
            if ext in ("png", "jpeg", "jpg"):
                # Direct save - already in a usable format
                image_path.write_bytes(img_info["image"])
                return image_path

        # Fall back to Pixmap approach for conversion
        pix = pymupdf.Pixmap(doc, xref)

        # Handle NULL colorspace (some PDFs have images with no colorspace)
        if pix.colorspace is None:
            # Try to render using page instead of direct extraction
            # This handles problematic images by rendering them at their location
            logger.debug(f"NULL colorspace for xref {xref}, skipping save")
            raise ValueError(f"Cannot handle NULL colorspace image (n={pix.n})")

        # Convert CMYK to RGB if needed
        if pix.n - pix.alpha > 3:
            pix = pymupdf.Pixmap(pymupdf.csRGB, pix)

        # Handle alpha channel for PNG
        if pix.alpha:
            pix = pymupdf.Pixmap(pix, 0)  # Remove alpha

        pix.save(str(image_path))
        return image_path

    def _find_caption(self, page, image_bbox) -> str | None:
        """Find caption text near image.

        Uses multiple strategies:
        1. Direct region search below/above image
        2. Text block proximity search for multi-column layouts

        Args:
            page: PyMuPDF Page object
            image_bbox: Bounding box of the image

        Returns:
            Caption text if found, None otherwise (orphan figure)
        """
        x0, y0, x1, y1 = image_bbox
        img_center_x = (x0 + x1) / 2

        # Strategy 1: Direct region search (expanded regions)
        # Search below image - expand to 150pt
        page_rect = page.rect
        caption_rect = pymupdf.Rect(
            max(0, x0 - 50), y1, min(page_rect.width, x1 + 50), min(page_rect.height, y1 + 150)
        )
        text = page.get_text("text", clip=caption_rect).strip()

        for pattern in FIGURE_CAPTION_PATTERNS:
            if pattern.match(text):
                return self._extract_caption_text(text)

        # Search above image (expanded to 120pt)
        above_rect = pymupdf.Rect(
            max(0, x0 - 50), max(0, y0 - 120), min(page_rect.width, x1 + 50), y0
        )
        text_above = page.get_text("text", clip=above_rect).strip()

        for pattern in FIGURE_CAPTION_PATTERNS:
            if pattern.match(text_above):
                return self._extract_caption_text(text_above)

        # Strategy 2: Text block proximity search
        # Get all text blocks and find nearest caption-like block
        # Only matches patterns at START of block to avoid prose references
        blocks = page.get_text("dict", flags=pymupdf.TEXT_PRESERVE_WHITESPACE)["blocks"]
        caption_candidates = []

        for block in blocks:
            if block.get("type") != 0:  # Skip non-text blocks
                continue

            block_text = ""
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    block_text += span.get("text", "")
                block_text += " "
            block_text = block_text.strip()

            if not block_text:
                continue

            # Check if this block STARTS with caption pattern (not mid-text)
            is_caption = False
            for pattern in FIGURE_CAPTION_PATTERNS:
                if pattern.match(block_text):
                    is_caption = True
                    break

            if is_caption:
                # Calculate distance from image
                bx0, by0, bx1, by1 = block["bbox"]
                block_center_x = (bx0 + bx1) / 2

                # Prefer blocks below or above the image (vertical proximity)
                # Penalize blocks that are horizontally far away
                vert_dist = min(abs(by0 - y1), abs(y0 - by1))  # Distance to nearest edge
                horiz_dist = abs(block_center_x - img_center_x)

                # Only consider blocks within reasonable range
                if vert_dist < 200 and horiz_dist < 300:
                    # Weight vertical distance more heavily (captions usually directly below/above)
                    distance = vert_dist + horiz_dist * 0.3
                    caption_candidates.append((distance, block_text))

        # Return nearest caption candidate
        if caption_candidates:
            caption_candidates.sort(key=lambda x: x[0])
            return self._extract_caption_text(caption_candidates[0][1])

        return None  # Orphan figure

    def _extract_caption_text(self, text: str) -> str:
        """Extract first paragraph of caption.

        Takes raw text near an image and extracts just the
        caption paragraph, stopping at the first blank line.

        Args:
            text: Raw text from the caption region

        Returns:
            Cleaned caption text
        """
        lines = text.split("\n")
        caption_lines = []
        for line in lines:
            line = line.strip()
            if not line:
                break
            caption_lines.append(line)
        return " ".join(caption_lines)

    @staticmethod
    def is_available() -> bool:
        """Check if figure extraction is available (requires PyMuPDF)."""
        try:
            import pymupdf

            return True
        except ImportError:
            return False
