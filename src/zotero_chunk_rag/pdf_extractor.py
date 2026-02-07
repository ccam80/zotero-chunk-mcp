"""PDF text extraction with page boundaries and optional OCR fallback."""
from __future__ import annotations
import math
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING
import pymupdf
from .models import PageText

if TYPE_CHECKING:
    from .config import Config


def compute_quality_score(
    pages: list[PageText],
    extraction_stats: dict,
    config: Config
) -> dict:
    """Compute extraction quality metrics with configurable thresholds.

    Args:
        pages: List of extracted page texts
        extraction_stats: Stats from PDFExtractor.extract()
        config: Config with quality threshold settings

    Returns:
        Dict with quality metrics:
        - chars_per_page: Average characters per page
        - ocr_fraction: Fraction of pages requiring OCR
        - empty_fraction: Fraction of empty pages
        - entropy_score: Text entropy (higher = more varied content)
        - quality_grade: Letter grade A-F
    """
    num_pages = len(pages)
    if num_pages == 0:
        return {
            "chars_per_page": 0.0,
            "ocr_fraction": 0.0,
            "empty_fraction": 1.0,
            "entropy_score": 0.0,
            "quality_grade": "F",
        }

    total_chars = sum(len(p.text) for p in pages)
    chars_per_page = total_chars / num_pages

    ocr_fraction = extraction_stats.get("ocr_pages", 0) / num_pages
    empty_fraction = extraction_stats.get("empty_pages", 0) / num_pages

    # Compute entropy (limit to first 100K chars for performance)
    sample_text = "".join(p.text for p in pages)[:100000].lower()
    char_counts = Counter(sample_text)
    total = len(sample_text)
    entropy = 0.0
    if total > 0:
        for count in char_counts.values():
            p = count / total
            entropy -= p * math.log2(p)

    # Grade based on configurable thresholds
    if (chars_per_page > config.quality_threshold_a and
            empty_fraction < 0.1 and
            entropy > config.quality_entropy_min):
        grade = "A"
    elif chars_per_page > config.quality_threshold_b and empty_fraction < 0.2:
        grade = "B"
    elif chars_per_page > config.quality_threshold_c:
        grade = "C"
    elif chars_per_page > config.quality_threshold_d:
        grade = "D"
    else:
        grade = "F"

    return {
        "chars_per_page": round(chars_per_page, 1),
        "ocr_fraction": round(ocr_fraction, 2),
        "empty_fraction": round(empty_fraction, 2),
        "entropy_score": round(entropy, 2),
        "quality_grade": grade,
    }


class PDFExtractor:
    """Extract text from PDFs preserving page structure.

    Supports optional OCR fallback for scanned/image-only pages.
    """

    def __init__(self, ocr_extractor=None):
        """
        Initialize PDF extractor.

        Args:
            ocr_extractor: Optional OCRExtractor for image-only pages.
                          If None, image-only pages return empty text.
        """
        self.ocr_extractor = ocr_extractor

    def extract(self, pdf_path: Path) -> tuple[list[PageText], dict]:
        """
        Extract text from PDF, returning per-page content.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Tuple of:
            - List of PageText objects with page numbers and character offsets
            - Extraction stats dict with keys:
              - "total_pages": int
              - "text_pages": int (pages with native text)
              - "ocr_pages": int (pages processed with OCR)
              - "empty_pages": int (pages with no text even after OCR)
        """
        doc = pymupdf.open(pdf_path)
        pages = []
        char_offset = 0

        stats = {
            "total_pages": len(doc),
            "text_pages": 0,
            "ocr_pages": 0,
            "empty_pages": 0,
            "scanned_skipped": 0,  # Pages detected as scanned but OCR unavailable
        }

        try:
            for i, page in enumerate(doc):
                text = page.get_text(sort=True)
                used_ocr = False
                is_scanned = False

                # Check if page appears to be scanned (image-only)
                if len(text.strip()) < 50 and page.get_images():
                    is_scanned = True

                # Try OCR if available and page needs it
                if is_scanned and self.ocr_extractor is not None:
                    ocr_text = self.ocr_extractor.ocr_page(page)
                    if ocr_text.strip():
                        text = ocr_text
                        used_ocr = True

                # Update stats
                if text.strip():
                    if used_ocr:
                        stats["ocr_pages"] += 1
                    else:
                        stats["text_pages"] += 1
                elif is_scanned and self.ocr_extractor is None:
                    # Scanned page but no OCR available
                    stats["scanned_skipped"] += 1
                else:
                    stats["empty_pages"] += 1

                pages.append(PageText(
                    page_num=i + 1,  # 1-indexed
                    text=text,
                    char_start=char_offset,
                ))
                char_offset += len(text) + 1  # +1 for newline between pages
        finally:
            doc.close()

        return pages, stats
