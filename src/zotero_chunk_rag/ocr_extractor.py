"""OCR extraction for scanned/image-only PDF pages."""
import io
import logging
import sys
from pathlib import Path

import pymupdf

from .models import PageText

logger = logging.getLogger(__name__)

# Windows default Tesseract installation path
_TESSERACT_WINDOWS_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Lazy-loaded to avoid import cost when OCR not used
_pytesseract = None
_PIL_Image = None


def _get_pil_image():
    """Lazy import PIL.Image."""
    global _PIL_Image
    if _PIL_Image is None:
        try:
            from PIL import Image
            _PIL_Image = Image
        except ImportError:
            raise ImportError(
                "Pillow required for OCR. Install with:\n"
                "  pip install Pillow"
            )
    return _PIL_Image


def _get_pytesseract():
    """Lazy import pytesseract and configure Tesseract path."""
    global _pytesseract
    if _pytesseract is None:
        try:
            import pytesseract
            _pytesseract = pytesseract

            # On Windows, set the Tesseract path to standard install location
            if sys.platform == "win32":
                if Path(_TESSERACT_WINDOWS_PATH).exists():
                    _pytesseract.pytesseract.tesseract_cmd = _TESSERACT_WINDOWS_PATH

        except ImportError:
            raise ImportError(
                "pytesseract required for OCR. Install with:\n"
                "  pip install pytesseract Pillow\n"
                "Also install Tesseract OCR engine:\n"
                "  Windows: https://github.com/UB-Mannheim/tesseract/wiki\n"
                "  macOS: brew install tesseract\n"
                "  Linux: sudo apt install tesseract-ocr"
            )
    return _pytesseract


class OCRExtractor:
    """OCR extraction for PDF pages lacking extractable text."""

    def __init__(
        self,
        language: str = "eng",
        dpi: int = 300,
        timeout: float = 30.0,
        min_text_chars: int = 50,
    ):
        """
        Initialize OCR extractor.

        Args:
            language: Tesseract language code(s), e.g., "eng" or "eng+deu"
            dpi: Resolution for rendering PDF pages (higher = better OCR, slower)
            timeout: Per-page timeout in seconds
            min_text_chars: Pages with fewer chars are considered image-only
        """
        self.language = language
        self.dpi = dpi
        self.timeout = timeout
        self.min_text_chars = min_text_chars
        self._tesseract = None

    def _ensure_tesseract(self):
        """Ensure pytesseract is loaded."""
        if self._tesseract is None:
            self._tesseract = _get_pytesseract()

    def is_image_only_page(self, page: pymupdf.Page) -> bool:
        """Check if a page lacks extractable text but has images.

        Args:
            page: PyMuPDF page object

        Returns:
            True if page has insufficient text and contains images
        """
        text = page.get_text().strip()
        if len(text) < self.min_text_chars:
            # Check if page has embedded images
            return bool(page.get_images())
        return False

    def ocr_page(self, page: pymupdf.Page) -> str:
        """Extract text from a PDF page using OCR.

        Args:
            page: PyMuPDF page object

        Returns:
            Extracted text, or empty string if OCR fails.
        """
        self._ensure_tesseract()
        Image = _get_pil_image()

        # Render page to image at specified DPI
        mat = pymupdf.Matrix(self.dpi / 72, self.dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        img_data = pix.tobytes("png")
        image = Image.open(io.BytesIO(img_data))

        try:
            text = self._tesseract.image_to_string(
                image,
                lang=self.language,
                timeout=self.timeout
            )
            return text
        except Exception as e:
            logger.warning(f"OCR failed for page: {e}")
            return ""

    def get_image_only_pages(self, pdf_path: Path) -> list[int]:
        """Get indices of pages that need OCR (0-indexed).

        Args:
            pdf_path: Path to PDF file

        Returns:
            List of 0-indexed page numbers that need OCR
        """
        doc = pymupdf.open(pdf_path)
        try:
            return [i for i, page in enumerate(doc) if self.is_image_only_page(page)]
        finally:
            doc.close()

    def ocr_pages(
        self,
        pdf_path: Path,
        page_indices: list[int] | None = None
    ) -> dict[int, str]:
        """OCR specific pages of a PDF.

        Args:
            pdf_path: Path to PDF file
            page_indices: 0-indexed page numbers to OCR, or None for all

        Returns:
            Dict mapping page index to extracted text
        """
        self._ensure_tesseract()
        doc = pymupdf.open(pdf_path)
        results = {}

        try:
            indices = page_indices if page_indices is not None else range(len(doc))
            for i in indices:
                if 0 <= i < len(doc):
                    logger.debug(f"OCR processing page {i + 1}/{len(doc)}")
                    results[i] = self.ocr_page(doc[i])
        finally:
            doc.close()

        return results

    @staticmethod
    def is_available() -> bool:
        """Check if OCR dependencies are available.

        Returns:
            True if pytesseract, Pillow, and Tesseract binary are all installed
        """
        try:
            pytesseract = _get_pytesseract()
            _get_pil_image()
            # Actually check that Tesseract binary is accessible
            pytesseract.get_tesseract_version()
            return True
        except ImportError:
            return False
        except Exception:
            # Tesseract binary not found or not working
            return False
