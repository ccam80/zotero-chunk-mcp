"""pdfplumber structure methods — lines and text vertical strategies.

Wraps pdfplumber's table detection as two ``StructureMethod`` implementations.
pdfplumber uses top-left coordinates matching pymupdf — no coordinate
conversion needed.
"""

from __future__ import annotations

import logging
from collections import Counter

import pdfplumber

from ..models import BoundaryHypothesis, BoundaryPoint, TableContext

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _grid_regularity_from_cells(
    cells: list[tuple[float, float, float, float]],
) -> float:
    """Fraction of rows with modal column count.

    Rows are identified by unique y0 (top) values. For each row, the column
    count is the number of cells sharing that y0. Regularity = fraction of
    rows with modal count.
    """
    if not cells:
        return 0.0

    cells_per_y0: dict[float, int] = {}
    for c in cells:
        y0 = c[1]
        cells_per_y0[y0] = cells_per_y0.get(y0, 0) + 1

    if not cells_per_y0:
        return 0.0

    count_freq: Counter[int] = Counter(cells_per_y0.values())
    modal_count = count_freq.most_common(1)[0][1]
    total_rows = len(cells_per_y0)

    return modal_count / total_rows


def _detect_with_strategy(
    ctx: TableContext, strategy: str,
) -> BoundaryHypothesis | None:
    """Detect table boundaries using pdfplumber with the given vertical strategy.

    Parameters
    ----------
    ctx:
        Table context with page info and bbox.
    strategy:
        pdfplumber vertical_strategy value ("lines" or "text").

    Returns
    -------
    BoundaryHypothesis | None
        Detected boundaries, or None if no tables found.
    """
    method_name = f"pdfplumber_{strategy}"

    try:
        pdf = pdfplumber.open(str(ctx.pdf_path))
    except Exception:
        logger.warning(
            "%s: failed to open PDF %s", method_name, ctx.pdf_path,
            exc_info=True,
        )
        return None

    try:
        # pdfplumber uses 0-indexed pages
        if ctx.page_num >= len(pdf.pages):
            logger.warning(
                "%s: page %d out of range (PDF has %d pages)",
                method_name, ctx.page_num, len(pdf.pages),
            )
            return None

        page = pdf.pages[ctx.page_num]

        # Crop to bbox - pdfplumber uses top-left coordinates like pymupdf
        x0, y0, x1, y1 = ctx.bbox
        cropped = page.within_bbox((x0, y0, x1, y1))

        table_settings = {
            "vertical_strategy": strategy,
            "horizontal_strategy": strategy,
        }

        tables = cropped.find_tables(table_settings=table_settings)

        if not tables:
            return None

        # Collect all cell bboxes
        all_cells: list[tuple[float, float, float, float]] = []
        for tab in tables:
            if tab.cells:
                all_cells.extend(tab.cells)

        if not all_cells:
            return None

        # Derive boundaries
        x0_values = sorted({c[0] for c in all_cells})
        y0_values = sorted({c[1] for c in all_cells})

        col_boundaries = tuple(x0_values[1:]) if len(x0_values) > 1 else ()
        row_boundaries = tuple(y0_values[1:]) if len(y0_values) > 1 else ()

        confidence = _grid_regularity_from_cells(all_cells)

        col_points = tuple(
            BoundaryPoint(
                min_pos=x, max_pos=x, confidence=confidence, provenance=method_name,
            )
            for x in col_boundaries
        )
        row_points = tuple(
            BoundaryPoint(
                min_pos=y, max_pos=y, confidence=confidence, provenance=method_name,
            )
            for y in row_boundaries
        )

        return BoundaryHypothesis(
            col_boundaries=col_points,
            row_boundaries=row_points,
            method=method_name,
            metadata={
                "strategy": strategy,
                "num_tables": len(tables),
                "total_cells": len(all_cells),
                "grid_regularity": confidence,
            },
        )

    except Exception:
        logger.warning(
            "%s: table detection failed", method_name, exc_info=True,
        )
        return None
    finally:
        pdf.close()


# ---------------------------------------------------------------------------
# StructureMethod implementations
# ---------------------------------------------------------------------------

class PdfplumberLines:
    """StructureMethod using pdfplumber with vertical_strategy='lines'."""

    @property
    def name(self) -> str:
        return "pdfplumber_lines"

    def detect(self, ctx: TableContext) -> BoundaryHypothesis | None:
        return _detect_with_strategy(ctx, "lines")


class PdfplumberText:
    """StructureMethod using pdfplumber with vertical_strategy='text'."""

    @property
    def name(self) -> str:
        return "pdfplumber_text"

    def detect(self, ctx: TableContext) -> BoundaryHypothesis | None:
        return _detect_with_strategy(ctx, "text")
