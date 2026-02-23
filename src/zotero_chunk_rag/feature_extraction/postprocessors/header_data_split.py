"""Post-processor: split fused header+data cells.

When PDF extraction absorbs the first data row into headers, each header
cell looks like ``"Col A 0.5"`` — a label followed by a numeric value.
This post-processor detects the pattern and splits the numeric suffixes
into a new first data row.
"""
from __future__ import annotations

import re

from ..models import CellGrid, TableContext

# Statistical markers stripped before numeric check
_STAT_MARKERS = re.compile(r"[*\u2020\u2021\u00a7\u2016]+")

# Skip-list for header cells that legitimately end with numbers
_HEADER_NUM_SKIP_RE = re.compile(
    r"^(?:Model|Wave|Phase|Group|Arm|Block|Step|Trial|Level|Stage|"
    r"Study|Experiment|Sample|Condition|Factor|Time|Day|Week|Month|Year|"
    r"Round|Session|Visit|Dose|Cohort)\s+\d+$",
    re.IGNORECASE,
)


def _looks_numeric(text: str) -> bool:
    """Check if *text* is purely numeric (with statistical markers stripped)."""
    stripped = _STAT_MARKERS.sub("", text).strip()
    if not stripped:
        return False
    return all(c in "0123456789.\u2212-+, " for c in stripped)


class HeaderDataSplit:
    """Split numeric suffixes fused into header cells into a new data row."""

    @property
    def name(self) -> str:
        return "header_data_split"

    def process(self, grid: CellGrid, ctx: TableContext) -> CellGrid:
        try:
            return self._process(grid, ctx)
        except Exception:
            return grid

    def _process(self, grid: CellGrid, ctx: TableContext) -> CellGrid:
        headers = grid.headers
        if not headers or len(headers) < 2:
            return grid

        # Detect fused headers
        fused_indices: list[int] = []
        for i, h in enumerate(headers):
            h = h.strip()
            if not h:
                continue
            if _HEADER_NUM_SKIP_RE.match(h):
                continue
            tokens = list(re.finditer(r"\S+", h))
            if len(tokens) >= 2 and _looks_numeric(tokens[-1].group()):
                fused_indices.append(i)

        # Trigger threshold: 30% of headers must be fused
        fused_fraction = len(fused_indices) / len(headers)
        if fused_fraction < 0.30:
            return grid

        # Split: extract numeric suffixes into a new data row
        new_headers = list(headers)
        data_row = [""] * len(headers)

        for i in fused_indices:
            h = headers[i].strip()
            tokens = list(re.finditer(r"\S+", h))
            if len(tokens) < 2:
                continue
            # Find where numeric suffix starts (scan from right)
            split_at = len(tokens)
            for j in range(len(tokens) - 1, 0, -1):
                if _looks_numeric(tokens[j].group()):
                    split_at = j
                else:
                    break
            if split_at < len(tokens):
                boundary = tokens[split_at].start()
                new_headers[i] = h[:boundary].rstrip()
                # Preserve original characters (including \n) from boundary onward
                data_row[i] = h[boundary:]

        return CellGrid(
            headers=tuple(new_headers),
            rows=(tuple(data_row),) + grid.rows,
            col_boundaries=grid.col_boundaries,
            row_boundaries=grid.row_boundaries,
            method=grid.method,
        )
