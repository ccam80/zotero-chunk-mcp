"""Core data models: CellGrid."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CellGrid:
    """Immutable cell content with the boundary positions that produced it.

    Post-processors return new CellGrid instances.
    """

    headers: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    col_boundaries: tuple[float, ...]
    row_boundaries: tuple[float, ...]
    method: str
    structure_method: str = "consensus"

    def with_structure_method(self, name: str) -> CellGrid:
        """Return a copy with ``structure_method`` replaced."""
        return CellGrid(
            headers=self.headers,
            rows=self.rows,
            col_boundaries=self.col_boundaries,
            row_boundaries=self.row_boundaries,
            method=self.method,
            structure_method=name,
        )

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable dict."""
        return {
            "headers": list(self.headers),
            "rows": [list(row) for row in self.rows],
            "col_boundaries": list(self.col_boundaries),
            "row_boundaries": list(self.row_boundaries),
            "method": self.method,
            "structure_method": self.structure_method,
        }
