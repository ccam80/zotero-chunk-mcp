"""Post-processor: detect inline sub-headers and forward-fill.

Academic tables often contain inline sub-group headers like "Panel A: Males"
that occupy only column 0 while every other column is empty.  This
post-processor detects columns with an exclusive-or population pattern
(populated only when no other data columns are) and forward-fills the
header values into the empty positions of subsequent data rows.
"""
from __future__ import annotations

from ..models import CellGrid, TableContext


def _find_exclusive_or_column(rows: tuple[tuple[str, ...], ...]) -> int | None:
    """Find a column that is populated exclusively when other columns are not.

    Returns the column index or ``None`` if no such column exists.
    """
    if not rows:
        return None

    ncols = max(len(r) for r in rows) if rows else 0
    if ncols < 2:
        return None

    # For each column, check if it has the exclusive-or pattern
    for candidate in range(ncols):
        header_rows = 0  # rows where only this col is populated
        data_rows = 0    # rows where other cols are populated
        conflict_rows = 0  # rows where both this col and others are populated

        for row in rows:
            cell_val = row[candidate].strip() if candidate < len(row) else ""
            other_populated = any(
                row[j].strip() for j in range(min(len(row), ncols)) if j != candidate
            )

            if cell_val and not other_populated:
                header_rows += 1
            elif cell_val and other_populated:
                conflict_rows += 1
            elif not cell_val and other_populated:
                data_rows += 1

        # The column must have at least 1 header row, some data rows,
        # and no conflict rows (exclusive-or)
        if header_rows >= 1 and data_rows >= 1 and conflict_rows == 0:
            return candidate

    return None


class InlineHeaderFill:
    """Detect inline sub-headers and forward-fill into data rows."""

    @property
    def name(self) -> str:
        return "inline_header_fill"

    def process(self, grid: CellGrid, ctx: TableContext) -> CellGrid:
        try:
            return self._process(grid, ctx)
        except Exception:
            return grid

    def _process(self, grid: CellGrid, ctx: TableContext) -> CellGrid:
        if len(grid.rows) < 2:
            return grid

        xor_col = _find_exclusive_or_column(grid.rows)
        if xor_col is None:
            return grid

        # Forward-fill: for each header row, fill its value into subsequent
        # data rows and remove the header row.
        new_rows: list[tuple[str, ...]] = []
        current_header_value = ""

        for row in grid.rows:
            cell_val = row[xor_col].strip() if xor_col < len(row) else ""
            other_populated = any(
                row[j].strip() for j in range(len(row)) if j != xor_col
            )

            if cell_val and not other_populated:
                # This is an inline header row — update fill value, skip row
                current_header_value = cell_val
            else:
                # Data row — fill the xor column with current header value
                row_list = list(row)
                if xor_col < len(row_list) and current_header_value:
                    row_list[xor_col] = current_header_value
                new_rows.append(tuple(row_list))

        if len(new_rows) == len(grid.rows):
            return grid  # Nothing changed

        return CellGrid(
            headers=grid.headers,
            rows=tuple(new_rows),
            col_boundaries=grid.col_boundaries,
            row_boundaries=grid.row_boundaries,
            method=grid.method,
        )
