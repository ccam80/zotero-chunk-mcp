"""Method protocols: StructureMethod, CellExtractionMethod, PostProcessor.

Structural typing contracts for the three method types in the extraction
pipeline. Any class with the right method signatures qualifies — no
inheritance required.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .models import BoundaryHypothesis, CellGrid, TableContext


@runtime_checkable
class StructureMethod(Protocol):
    """Detects table structure (column/row boundaries) from page content.

    Implementations analyse words, ruled lines, whitespace gaps, or other
    signals to produce a ``BoundaryHypothesis``.  Returning ``None`` means
    the method found nothing.  Raising an exception is allowed — the pipeline
    catches and logs it.
    """

    @property
    def name(self) -> str:
        """Unique identifier for this method (e.g. ``"word_gap_hotspot"``)."""
        ...

    def detect(self, ctx: TableContext) -> BoundaryHypothesis | None:
        """Detect boundaries for a single table region.

        Parameters
        ----------
        ctx:
            Lazily-computed context about the table region.

        Returns
        -------
        BoundaryHypothesis | None
            Hypothesis with detected boundaries, or ``None`` if the method
            found nothing useful.
        """
        ...


@runtime_checkable
class CellExtractionMethod(Protocol):
    """Extracts cell text given resolved column/row boundaries.

    Implementations read PDF content within the boundary grid and return
    a ``CellGrid`` with the extracted text.  Returning ``None`` means
    extraction failed.
    """

    @property
    def name(self) -> str:
        """Unique identifier for this method."""
        ...

    def extract(
        self,
        ctx: TableContext,
        col_boundaries: tuple[float, ...],
        row_boundaries: tuple[float, ...],
    ) -> CellGrid | None:
        """Extract cell text from the table region using the given boundaries.

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
            Extracted cell content, or ``None`` if extraction failed.
        """
        ...


@runtime_checkable
class PostProcessor(Protocol):
    """Transforms a ``CellGrid`` in place (actually returns a new frozen instance).

    Post-processors handle cleanup tasks such as header/data separation,
    footnote stripping, empty-column removal, etc.  They must never raise —
    if the processing doesn't apply, return the input grid unchanged.
    """

    @property
    def name(self) -> str:
        """Unique identifier for this post-processor."""
        ...

    def process(self, grid: CellGrid, ctx: TableContext) -> CellGrid:
        """Transform the grid and return a new frozen ``CellGrid``.

        Parameters
        ----------
        grid:
            The current cell grid (frozen — do not mutate).
        ctx:
            Lazily-computed context about the table region.

        Returns
        -------
        CellGrid
            A new (or the same) frozen ``CellGrid``.  Must not raise.
        """
        ...
