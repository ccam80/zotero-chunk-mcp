"""Camelot structure methods — lattice and hybrid flavors.

Wraps Camelot's ``read_pdf()`` as two ``StructureMethod`` implementations.
Both require the PDF file path (from ``ctx.pdf_path``) and convert Camelot's
bottom-left coordinate system to pymupdf's top-left coordinates.
"""

from __future__ import annotations

import logging
import shutil
from typing import TYPE_CHECKING

import camelot

from ..models import BoundaryHypothesis, BoundaryPoint, TableContext

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bbox_to_camelot_area(
    bbox: tuple[float, float, float, float],
    page_height: float,
) -> str:
    """Convert pymupdf bbox to Camelot table_areas string.

    pymupdf bbox: (x0, y0_top, x1, y1_bottom) with origin at top-left.
    Camelot area: "x0,y_top,x1,y_bottom" in PDF coordinates where
    origin is at bottom-left and y_top > y_bottom.
    """
    x0, y0_top, x1, y1_bottom = bbox
    # Convert: pdf_y = page_height - pymupdf_y
    camelot_y_top = page_height - y0_top
    camelot_y_bottom = page_height - y1_bottom
    return f"{x0},{camelot_y_top},{x1},{camelot_y_bottom}"


def _camelot_to_pymupdf_y(pdf_y: float, page_height: float) -> float:
    """Convert a PDF-coordinate y value to pymupdf y (top-left origin)."""
    return page_height - pdf_y


def _has_ghostscript() -> bool:
    """Check whether Ghostscript is available on the system."""
    gs_name = "gswin64c" if shutil.which("gswin64c") else "gs"
    return shutil.which(gs_name) is not None


def _detect_camelot(
    ctx: TableContext,
    flavor: str,
    method_name: str,
) -> BoundaryHypothesis | None:
    """Shared detection logic for Camelot lattice and hybrid."""
    if flavor == "lattice" and not _has_ghostscript():
        logger.warning(
            "%s: Ghostscript not available, returning None", method_name
        )
        return None

    area_str = _bbox_to_camelot_area(ctx.bbox, ctx.page_height)
    page_str = str(ctx.page_num)  # ctx.page_num is already 1-indexed

    try:
        tables = camelot.read_pdf(
            str(ctx.pdf_path),
            pages=page_str,
            flavor=flavor,
            table_areas=[area_str],
        )
    except Exception:
        logger.warning(
            "%s: camelot.read_pdf failed", method_name, exc_info=True,
        )
        return None

    if not tables or len(tables) == 0:
        return None

    # Collect all cell bboxes across found tables, converting coordinates
    all_cells_pymupdf: list[tuple[float, float, float, float]] = []

    for tab in tables:
        accuracy = tab.accuracy if hasattr(tab, "accuracy") else 0.0

        if not hasattr(tab, "cells") or not tab.cells:
            continue

        # tab.cells may be a flat list of Cell objects/tuples, or a list
        # of rows where each row is a list of Cell objects.
        flat_cells = []
        for item in tab.cells:
            if isinstance(item, list):
                flat_cells.extend(item)
            else:
                flat_cells.append(item)

        for cell in flat_cells:
            try:
                if hasattr(cell, "x1"):
                    cx0 = float(cell.x1)
                    cy0 = float(cell.y1)
                    cx1 = float(cell.x2)
                    cy1 = float(cell.y2)
                else:
                    cx0, cy0, cx1, cy1 = (float(v) for v in cell[:4])
            except (AttributeError, TypeError, ValueError, IndexError):
                continue
            py0 = _camelot_to_pymupdf_y(cy1, ctx.page_height)  # top in pymupdf
            py1 = _camelot_to_pymupdf_y(cy0, ctx.page_height)  # bottom in pymupdf
            all_cells_pymupdf.append((cx0, py0, cx1, py1))

    if not all_cells_pymupdf:
        return None

    # Derive boundaries from converted cells
    x0_values = sorted({c[0] for c in all_cells_pymupdf})
    y0_values = sorted({c[1] for c in all_cells_pymupdf})

    col_boundaries = tuple(x0_values[1:]) if len(x0_values) > 1 else ()
    row_boundaries = tuple(y0_values[1:]) if len(y0_values) > 1 else ()

    # Use Camelot's accuracy as confidence
    best_accuracy = max(
        (tab.accuracy for tab in tables if hasattr(tab, "accuracy")),
        default=0.0,
    )
    confidence = best_accuracy / 100.0

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
            "flavor": flavor,
            "num_tables": len(tables),
            "accuracy": best_accuracy,
            "total_cells": len(all_cells_pymupdf),
        },
    )


# ---------------------------------------------------------------------------
# StructureMethod implementations
# ---------------------------------------------------------------------------

class CamelotLattice:
    """StructureMethod using Camelot lattice flavor (requires Ghostscript)."""

    @property
    def name(self) -> str:
        return "camelot_lattice"

    def detect(self, ctx: TableContext) -> BoundaryHypothesis | None:
        return _detect_camelot(ctx, "lattice", self.name)


class CamelotHybrid:
    """StructureMethod using Camelot hybrid flavor."""

    @property
    def name(self) -> str:
        return "camelot_hybrid"

    def detect(self, ctx: TableContext) -> BoundaryHypothesis | None:
        return _detect_camelot(ctx, "hybrid", self.name)
