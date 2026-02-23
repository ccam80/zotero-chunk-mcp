"""Rawdict cell extraction method.

Uses pymupdf's get_text("rawdict") for character-level extraction with 50%
bbox overlap for cell assignment. Adapts the existing _extract_via_rawdict()
logic from pdf_processor.py as a CellExtractionMethod.
"""
from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING, Any

from ..models import CellGrid

if TYPE_CHECKING:
    from ..models import TableContext

logger = logging.getLogger(__name__)


def _get_table_module() -> Any:
    """Get pymupdf.table module from sys.modules, importing if needed."""
    mod = sys.modules.get("pymupdf.table")
    if mod is not None:
        return mod
    try:
        import pymupdf.table as _table_mod
        return _table_mod
    except ImportError:
        return None


def _build_cell_bboxes(
    col_bounds: tuple[float, ...],
    row_bounds: tuple[float, ...],
    table_bbox: tuple[float, float, float, float],
) -> list[tuple[float, float, float, float]]:
    """Construct cell bboxes from boundary positions and table bbox edges.

    Column boundaries are *internal* dividers between columns. The leftmost
    column starts at table_bbox[0] (x0) and the rightmost ends at
    table_bbox[2] (x1). Similarly, the topmost row starts at table_bbox[1]
    (y0) and the bottommost ends at table_bbox[3] (y1).

    Parameters
    ----------
    col_bounds:
        Internal column boundary x-positions (ascending floats).
    row_bounds:
        Internal row boundary y-positions (ascending floats).
    table_bbox:
        The overall table bounding box (x0, y0, x1, y1).

    Returns
    -------
    list[tuple[float, float, float, float]]
        Cell bboxes in row-major order, each as (x0, y0, x1, y1).
    """
    tx0, ty0, tx1, ty1 = table_bbox

    # Build column edges: table left edge, then internal boundaries, then table right edge
    col_edges = [tx0, *col_bounds, tx1]

    # Build row edges: table top edge, then internal boundaries, then table bottom edge
    row_edges = [ty0, *row_bounds, ty1]

    bboxes: list[tuple[float, float, float, float]] = []
    for ri in range(len(row_edges) - 1):
        for ci in range(len(col_edges) - 1):
            bboxes.append((
                col_edges[ci],
                row_edges[ri],
                col_edges[ci + 1],
                row_edges[ri + 1],
            ))
    return bboxes


class RawdictExtraction:
    """Cell extraction using pymupdf.table.extract_cells with rawdict overlap.

    Uses the TEXTPAGE global set during page processing and the 50% bbox
    overlap algorithm to correctly assign characters to cells.
    """

    @property
    def name(self) -> str:
        return "rawdict"

    def extract(
        self,
        ctx: TableContext,
        col_boundaries: tuple[float, ...],
        row_boundaries: tuple[float, ...],
    ) -> CellGrid | None:
        """Extract cell text using rawdict character-level assignment.

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
            Extracted cell content, or None if TEXTPAGE unavailable or
            extraction fails.
        """
        _table_mod = _get_table_module()
        if _table_mod is None:
            logger.warning("pymupdf.table not available for rawdict extraction")
            return None

        textpage = getattr(_table_mod, "TEXTPAGE", None)
        if textpage is None:
            logger.debug("TEXTPAGE not set — rawdict extraction unavailable")
            return None

        num_cols = len(col_boundaries) + 1
        num_rows = len(row_boundaries) + 1

        cell_bboxes = _build_cell_bboxes(col_boundaries, row_boundaries, ctx.bbox)

        # Extract text for each cell bbox using the 50% overlap algorithm
        try:
            all_cells: list[str] = []
            for bbox in cell_bboxes:
                text = _table_mod.extract_cells(textpage, bbox)
                all_cells.append(text if text else "")
        except Exception:
            logger.debug("rawdict extract_cells failed", exc_info=True)
            return None

        # Reshape flat list into rows
        rows_raw: list[tuple[str, ...]] = []
        for ri in range(num_rows):
            start = ri * num_cols
            end = start + num_cols
            rows_raw.append(tuple(all_cells[start:end]))

        # First row is headers
        headers = rows_raw[0] if rows_raw else ()
        data_rows = tuple(rows_raw[1:]) if len(rows_raw) > 1 else ()

        return CellGrid(
            headers=headers,
            rows=data_rows,
            col_boundaries=col_boundaries,
            row_boundaries=row_boundaries,
            method="rawdict",
        )
