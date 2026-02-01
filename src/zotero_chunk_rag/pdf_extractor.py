"""PDF text extraction with page boundaries."""
from pathlib import Path
import pymupdf
from .models import PageText


class PDFExtractor:
    """Extract text from PDFs preserving page structure."""

    def extract(self, pdf_path: Path) -> list[PageText]:
        """
        Extract text from PDF, returning per-page content.

        Args:
            pdf_path: Path to PDF file

        Returns:
            List of PageText objects with page numbers and character offsets
        """
        doc = pymupdf.open(pdf_path)
        pages = []
        char_offset = 0

        try:
            for i, page in enumerate(doc):
                text = page.get_text()
                pages.append(PageText(
                    page_num=i + 1,  # 1-indexed
                    text=text,
                    char_start=char_offset,
                ))
                char_offset += len(text) + 1  # +1 for newline between pages
        finally:
            doc.close()

        return pages
