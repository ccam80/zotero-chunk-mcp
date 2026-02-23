"""Post-processor: strip table/figure captions absorbed into the cell grid.

Detects caption patterns in the first few rows and headers, removing them
so downstream processing sees only data.  Caption regex is imported from
``captions.py`` (single source of truth).
"""
from __future__ import annotations

import re

from ..captions import _FIG_CAPTION_RE, _TABLE_CAPTION_RE
from ..models import CellGrid, TableContext

_CAPTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    _TABLE_CAPTION_RE,
    _FIG_CAPTION_RE,
)


def _cell_matches_caption(text: str) -> bool:
    """Return True if *text* matches any caption pattern."""
    text = text.strip()
    if not text:
        return False
    return any(p.match(text) for p in _CAPTION_PATTERNS)


class AbsorbedCaptionStrip:
    """Remove table/figure captions that leaked into the first rows or headers."""

    @property
    def name(self) -> str:
        return "absorbed_caption_strip"

    def process(self, grid: CellGrid, ctx: TableContext) -> CellGrid:
        try:
            return self._process(grid, ctx)
        except Exception:
            return grid

    def _process(self, grid: CellGrid, ctx: TableContext) -> CellGrid:
        new_headers = grid.headers
        new_rows = list(grid.rows)
        changed = False

        # --- Check headers ---
        if new_headers:
            caption_hits = sum(1 for h in new_headers if _cell_matches_caption(h))
            non_empty = sum(1 for h in new_headers if h.strip())
            if non_empty > 0 and caption_hits > 0:
                if caption_hits > non_empty * 0.5:
                    # Predominantly caption — clear all headers
                    new_headers = tuple("" for _ in new_headers)
                    changed = True
                else:
                    # Clear only matching cells
                    hdr_list = list(new_headers)
                    for i, h in enumerate(hdr_list):
                        if _cell_matches_caption(h):
                            hdr_list[i] = ""
                            changed = True
                    new_headers = tuple(hdr_list)

            # If all headers now empty, drop them
            if all(not h.strip() for h in new_headers):
                new_headers = ()

        # --- Check first N rows (no early exit) ---
        scan_limit = min(5, len(new_rows))
        rows_to_remove: set[int] = set()

        for i in range(scan_limit):
            row = new_rows[i]
            caption_hits = sum(1 for c in row if _cell_matches_caption(c))
            non_empty = sum(1 for c in row if c.strip())

            if caption_hits == 0:
                continue  # No early exit — keep scanning

            if non_empty > 0 and caption_hits > non_empty * 0.5:
                # Predominantly caption row — mark for removal
                rows_to_remove.add(i)
                changed = True
            else:
                # Clear only matching cells (row stays)
                row_list = list(row)
                for j, c in enumerate(row_list):
                    if _cell_matches_caption(c):
                        row_list[j] = ""
                        changed = True
                new_rows[i] = tuple(row_list)

        if not changed:
            return grid

        # Remove marked rows (in reverse order to preserve indices)
        for i in sorted(rows_to_remove, reverse=True):
            new_rows.pop(i)

        return CellGrid(
            headers=new_headers,
            rows=tuple(tuple(r) for r in new_rows),
            col_boundaries=grid.col_boundaries,
            row_boundaries=grid.row_boundaries,
            method=grid.method,
        )
