"""Post-processor: detect header rows from font metadata.

Uses ``ctx.dict_blocks`` to find font properties (size, bold) for each row's
y-range and promotes data rows with distinct header-font characteristics to
``grid.headers``.
"""
from __future__ import annotations

import statistics

from ..models import CellGrid, TableContext


def _row_font_properties(
    dict_blocks: list[dict],
    row_y_range: tuple[float, float],
) -> dict:
    """Extract dominant font properties for spans whose y-center falls in *row_y_range*.

    Returns ``{"size": float, "bold": bool, "char_count": int}`` or an empty
    dict if no spans are found.
    """
    y_lo, y_hi = row_y_range
    sizes: list[float] = []
    bold_chars = 0
    total_chars = 0

    for block in dict_blocks:
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                span_bbox = span.get("bbox", (0, 0, 0, 0))
                span_y_center = (span_bbox[1] + span_bbox[3]) / 2
                if span_y_center < y_lo or span_y_center > y_hi:
                    continue
                text = span.get("text", "").strip()
                n = len(text)
                if n == 0:
                    continue

                sizes.append(span.get("size", 0.0))
                total_chars += n

                flags = span.get("flags", 0)
                font_name = span.get("font", "")
                is_bold = bool(flags & 16) or _font_name_is_bold(font_name)
                if is_bold:
                    bold_chars += n

    if total_chars == 0:
        return {}

    return {
        "size": statistics.median(sizes) if sizes else 0.0,
        "bold": bold_chars > total_chars * 0.5,
        "char_count": total_chars,
    }


def _font_name_is_bold(name: str) -> bool:
    """Check if a font name indicates bold weight."""
    if name.endswith(".B") or name.endswith(".b"):
        return True
    lower = name.lower()
    return "bold" in lower or "-bd" in lower


class HeaderDetection:
    """Detect header rows via font metadata and move them to ``grid.headers``."""

    @property
    def name(self) -> str:
        return "header_detection"

    def process(self, grid: CellGrid, ctx: TableContext) -> CellGrid:
        try:
            return self._process(grid, ctx)
        except Exception:
            return grid

    def _process(self, grid: CellGrid, ctx: TableContext) -> CellGrid:
        # Only operate when headers are not already set
        if grid.headers and any(h.strip() for h in grid.headers):
            return grid

        if len(grid.rows) < 2:
            return grid

        row_bounds = grid.row_boundaries
        dict_blocks = ctx.dict_blocks
        if not dict_blocks:
            return grid

        # Compute y-ranges for each row from row_boundaries
        # row_boundaries are the dividers between rows.
        # Row 0: from bbox top (or first row_boundary - tolerance) to row_boundaries[0]
        # Row i: from row_boundaries[i-1] to row_boundaries[i]
        # Last row: from row_boundaries[-1] to bbox bottom
        bbox = ctx.bbox
        y_ranges: list[tuple[float, float]] = []
        n_rows = len(grid.rows)

        if row_bounds:
            for i in range(n_rows):
                y_lo = row_bounds[i - 1] if i > 0 else bbox[1]
                y_hi = row_bounds[i] if i < len(row_bounds) else bbox[3]
                y_ranges.append((y_lo, y_hi))
        else:
            # No boundaries — single range
            y_ranges.append((bbox[1], bbox[3]))

        # Get font properties for each row
        row_props: list[dict] = []
        for yr in y_ranges:
            props = _row_font_properties(dict_blocks, yr)
            row_props.append(props)

        # Need at least one row with font info and at least 2 rows total
        if not any(rp for rp in row_props):
            return grid

        # Find the "data font" — median size across all rows with data
        all_sizes = [rp["size"] for rp in row_props if rp]
        if not all_sizes:
            return grid
        data_size = statistics.median(all_sizes)

        # Determine how many leading rows are "header-like"
        header_count = 0
        for i, rp in enumerate(row_props):
            if not rp:
                break

            size_diff = abs(rp["size"] - data_size) > 0.5
            is_bold_header = rp["bold"] and not all(
                p.get("bold", False) for p in row_props if p
            )

            if i == 0 and (size_diff or is_bold_header):
                header_count = 1
            elif i > 0 and header_count == i:
                # Continuation of header block
                if size_diff or is_bold_header:
                    header_count = i + 1
                else:
                    break
            else:
                break

        if header_count == 0:
            return grid

        # Move header rows to headers
        # If there's a single header row, its cells become grid.headers
        # If multiple, join them with newlines per column
        header_rows = grid.rows[:header_count]
        data_rows = grid.rows[header_count:]

        if len(header_rows) == 1:
            new_headers = header_rows[0]
        else:
            # Merge multiple header rows: join each column with newline
            ncols = max(len(r) for r in header_rows) if header_rows else 0
            merged: list[str] = []
            for col_idx in range(ncols):
                parts = []
                for hr in header_rows:
                    if col_idx < len(hr) and hr[col_idx].strip():
                        parts.append(hr[col_idx].strip())
                merged.append("\n".join(parts))
            new_headers = tuple(merged)

        # Update row boundaries — remove boundaries consumed by header rows
        new_row_bounds = row_bounds[header_count:] if row_bounds else ()

        return CellGrid(
            headers=new_headers,
            rows=data_rows,
            col_boundaries=grid.col_boundaries,
            row_boundaries=new_row_bounds,
            method=grid.method,
        )
