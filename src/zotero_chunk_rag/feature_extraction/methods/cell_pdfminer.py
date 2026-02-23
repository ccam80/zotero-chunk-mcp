"""PDFMiner cell extraction method (via pdfplumber).

Uses pdfplumber to extract cell text by cropping each cell bbox from the
pdfplumber page and calling extract_text(). Provides a third independent
text extraction engine alongside pymupdf's rawdict and word methods.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..models import CellGrid

if TYPE_CHECKING:
    from ..models import TableContext

logger = logging.getLogger(__name__)


class PdfMinerExtraction:
    """Cell extraction using pdfplumber's PDFMiner-based text extraction.

    For each cell bbox derived from consensus boundaries, crops the pdfplumber
    page and calls extract_text(). The PDF is opened once per table and the
    page object is reused across all cells.
    """

    @property
    def name(self) -> str:
        return "pdfminer"

    def extract(
        self,
        ctx: TableContext,
        col_boundaries: tuple[float, ...],
        row_boundaries: tuple[float, ...],
    ) -> CellGrid | None:
        """Extract cell text using pdfplumber's PDFMiner engine.

        Parameters
        ----------
        ctx:
            Lazily-computed context about the table region.
        col_boundaries:
            Resolved column boundary positions (ascending floats).
        row_boundaries:
            Resolved row boundary positions (ascending floats).

        Returns
        -------
        CellGrid | None
            Extracted cell content, or None on any pdfplumber error.
        """
        try:
            import pdfplumber
        except ImportError:
            logger.warning("pdfplumber not available for PDFMiner extraction")
            return None

        try:
            pdf = pdfplumber.open(str(ctx.pdf_path))
        except Exception:
            logger.debug("pdfplumber failed to open PDF", exc_info=True)
            return None

        try:
            plumber_page = pdf.pages[ctx.page_num]

            tx0, ty0, tx1, ty1 = ctx.bbox

            # Build column and row edges from boundaries + table bbox edges
            col_edges = [tx0, *col_boundaries, tx1]
            row_edges = [ty0, *row_boundaries, ty1]

            num_cols = len(col_edges) - 1
            num_rows = len(row_edges) - 1

            rows_raw: list[tuple[str, ...]] = []
            for ri in range(num_rows):
                row: list[str] = []
                for ci in range(num_cols):
                    cell_bbox = (
                        col_edges[ci],
                        row_edges[ri],
                        col_edges[ci + 1],
                        row_edges[ri + 1],
                    )
                    try:
                        cropped = plumber_page.crop(cell_bbox)
                        text = cropped.extract_text()
                    except Exception:
                        text = None

                    # pdfplumber returns None for empty regions
                    row.append(text if text is not None else "")
                rows_raw.append(tuple(row))

            # First row is headers
            headers = rows_raw[0] if rows_raw else ()
            data_rows = tuple(rows_raw[1:]) if len(rows_raw) > 1 else ()

            return CellGrid(
                headers=headers,
                rows=data_rows,
                col_boundaries=col_boundaries,
                row_boundaries=row_boundaries,
                method="pdfminer",
            )
        except Exception:
            logger.debug("pdfplumber extraction failed", exc_info=True)
            return None
        finally:
            pdf.close()
