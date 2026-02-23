"""PyMuPDF find_tables structure methods — lines, lines_strict, text strategies.

Wraps ``page.find_tables(clip=bbox, strategy=...)`` for three different
strategies. Each extracts cell bboxes from the result and derives row/column
boundary positions from the cell coordinates.
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import TYPE_CHECKING

import pymupdf

from ..models import BoundaryHypothesis, BoundaryPoint, TableContext

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_tables_for_strategy(
    page: pymupdf.Page,
    bbox: tuple[float, float, float, float],
    strategy: str,
) -> list:
    """Call page.find_tables with the given strategy, clipped to bbox.

    Returns list of Table objects found within the bbox.
    Returns empty list on error.
    """
    try:
        result = page.find_tables(clip=pymupdf.Rect(bbox), strategy=strategy)
        return list(result.tables)
    except Exception:
        logger.warning(
            "find_tables(strategy=%r) failed for bbox %s", strategy, bbox,
            exc_info=True,
        )
        return []


def _boundaries_from_cells(
    cells: list[tuple[float, float, float, float]],
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Derive (col_boundaries, row_boundaries) from cell bboxes.

    Column boundaries = sorted unique x0 values (excluding the leftmost table edge).
    Row boundaries = sorted unique y0 values (excluding the topmost table edge).
    """
    if not cells:
        return ((), ())

    x0_values = sorted({c[0] for c in cells})
    y0_values = sorted({c[1] for c in cells})

    # Exclude outermost edges (first element is the table edge)
    col_boundaries = tuple(x0_values[1:]) if len(x0_values) > 1 else ()
    row_boundaries = tuple(y0_values[1:]) if len(y0_values) > 1 else ()

    return col_boundaries, row_boundaries


def _grid_regularity(
    cells: list[tuple[float, float, float, float]],
) -> float:
    """Fraction of rows with modal column count.

    Rows are identified by unique y0 values. For each row, the column count
    is the number of cells sharing that y0. The modal column count is the
    most common count. Regularity = fraction of rows with modal count.

    Returns 0.0 if no cells.
    """
    if not cells:
        return 0.0

    # Group cells by y0 to identify rows
    row_counts: Counter[float] = Counter()
    cells_per_y0: dict[float, int] = {}
    for c in cells:
        y0 = c[1]
        cells_per_y0[y0] = cells_per_y0.get(y0, 0) + 1

    if not cells_per_y0:
        return 0.0

    # Count how many rows have each column count
    count_freq: Counter[int] = Counter(cells_per_y0.values())
    modal_count = count_freq.most_common(1)[0][1]
    total_rows = len(cells_per_y0)

    return modal_count / total_rows


# ---------------------------------------------------------------------------
# StructureMethod implementations
# ---------------------------------------------------------------------------

def _detect_for_strategy(
    ctx: TableContext, strategy: str, method_name: str,
) -> BoundaryHypothesis | None:
    """Shared detection logic for all three PyMuPDF strategies."""
    tables = _find_tables_for_strategy(ctx.page, ctx.bbox, strategy)
    if not tables:
        return None

    # Collect all cells across all found tables
    all_cells: list[tuple[float, float, float, float]] = []
    for tab in tables:
        if tab.cells:
            all_cells.extend(tab.cells)

    if not all_cells:
        return None

    col_boundaries, row_boundaries = _boundaries_from_cells(all_cells)
    confidence = _grid_regularity(all_cells)

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
            "num_tables_found": len(tables),
            "total_cells": len(all_cells),
            "grid_regularity": confidence,
        },
    )


class PyMuPDFLines:
    """StructureMethod using find_tables with strategy='lines'."""

    @property
    def name(self) -> str:
        return "pymupdf_lines"

    def detect(self, ctx: TableContext) -> BoundaryHypothesis | None:
        return _detect_for_strategy(ctx, "lines", self.name)


class PyMuPDFLinesStrict:
    """StructureMethod using find_tables with strategy='lines_strict'."""

    @property
    def name(self) -> str:
        return "pymupdf_lines_strict"

    def detect(self, ctx: TableContext) -> BoundaryHypothesis | None:
        return _detect_for_strategy(ctx, "lines_strict", self.name)


class PyMuPDFText:
    """StructureMethod using find_tables with strategy='text'."""

    @property
    def name(self) -> str:
        return "pymupdf_text"

    def detect(self, ctx: TableContext) -> BoundaryHypothesis | None:
        return _detect_for_strategy(ctx, "text", self.name)
