"""Post-processor: merge continuation rows into their anchor rows.

A continuation row is one whose populated columns are a *strict subset* of
the anchor row's populated columns AND are adjacent (no gaps in populated
positions).  Text is appended with a space separator.
"""
from __future__ import annotations

from ..models import CellGrid, TableContext


def _populated_cols(row: tuple[str, ...] | list[str]) -> set[int]:
    """Return the set of column indices that have non-empty text."""
    return {i for i, c in enumerate(row) if c.strip()}


def _cols_are_adjacent(cols: set[int]) -> bool:
    """Return True if all column indices in *cols* are contiguous."""
    if len(cols) <= 1:
        return True
    sorted_cols = sorted(cols)
    return sorted_cols[-1] - sorted_cols[0] == len(sorted_cols) - 1


def _is_continuation(
    row: tuple[str, ...] | list[str],
    anchor_row: tuple[str, ...] | list[str],
) -> bool:
    """Return True if *row* is a continuation of *anchor_row*.

    Criteria:
    1. Row has at least one populated cell.
    2. Populated columns are a strict subset of anchor's populated columns.
    3. Populated columns are adjacent (no gaps).
    """
    row_cols = _populated_cols(row)
    if not row_cols:
        return False
    anchor_cols = _populated_cols(anchor_row)
    if not anchor_cols:
        return False
    # Strict subset — cannot be equal
    if row_cols == anchor_cols:
        return False
    if not row_cols.issubset(anchor_cols):
        return False
    return _cols_are_adjacent(row_cols)


class ContinuationMerge:
    """Merge continuation rows into their anchor row."""

    @property
    def name(self) -> str:
        return "continuation_merge"

    def process(self, grid: CellGrid, ctx: TableContext) -> CellGrid:
        try:
            return self._process(grid, ctx)
        except Exception:
            return grid

    def _process(self, grid: CellGrid, ctx: TableContext) -> CellGrid:
        if len(grid.rows) < 2:
            return grid

        merged_rows: list[list[str]] = []
        anchor_idx: int | None = None

        for row in grid.rows:
            if anchor_idx is not None and _is_continuation(row, merged_rows[anchor_idx]):
                # Merge into anchor
                anchor = merged_rows[anchor_idx]
                new_anchor = list(anchor)
                for j, cell in enumerate(row):
                    if j < len(new_anchor) and cell.strip():
                        if new_anchor[j].strip():
                            new_anchor[j] = new_anchor[j].rstrip() + " " + cell.strip()
                        else:
                            new_anchor[j] = cell.strip()
                merged_rows[anchor_idx] = new_anchor
            else:
                # New anchor row
                merged_rows.append(list(row))
                anchor_idx = len(merged_rows) - 1

        if len(merged_rows) == len(grid.rows):
            return grid  # Nothing merged

        return CellGrid(
            headers=grid.headers,
            rows=tuple(tuple(r) for r in merged_rows),
            col_boundaries=grid.col_boundaries,
            row_boundaries=grid.row_boundaries,
            method=grid.method,
        )
