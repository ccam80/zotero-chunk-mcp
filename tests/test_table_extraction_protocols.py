"""Tests for method protocols in zotero_chunk_rag.feature_extraction.protocols."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from zotero_chunk_rag.feature_extraction.models import (
    BoundaryHypothesis,
    BoundaryPoint,
    CellGrid,
    TableContext,
)
from zotero_chunk_rag.feature_extraction.protocols import (
    CellExtractionMethod,
    PostProcessor,
    StructureMethod,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ctx() -> TableContext:
    """Create a minimal TableContext with a mock page."""
    page = MagicMock()
    page.get_text = MagicMock(return_value=[])
    page.get_drawings = MagicMock(return_value=[])
    rect = MagicMock()
    rect.height = 842.0
    rect.width = 595.0
    page.rect = rect
    return TableContext(
        page=page,
        page_num=0,
        bbox=(0.0, 0.0, 500.0, 300.0),
        pdf_path=Path("/tmp/test.pdf"),
    )


def _make_hypothesis() -> BoundaryHypothesis:
    """Create a minimal BoundaryHypothesis for testing."""
    return BoundaryHypothesis(
        col_boundaries=(BoundaryPoint(100.0, 100.0, 0.9, "test"),),
        row_boundaries=(BoundaryPoint(50.0, 50.0, 0.8, "test"),),
        method="test_method",
        metadata={},
    )


def _make_grid() -> CellGrid:
    """Create a minimal CellGrid for testing."""
    return CellGrid(
        headers=("A", "B"),
        rows=(("1", "2"), ("3", "4")),
        col_boundaries=(0.0, 100.0, 200.0),
        row_boundaries=(0.0, 50.0, 100.0),
        method="test_method",
    )


# ---------------------------------------------------------------------------
# TestStructureMethodProtocol
# ---------------------------------------------------------------------------


class TestStructureMethodProtocol:
    def test_conformance(self) -> None:
        """A plain class with `name` property and `detect(ctx)` method satisfies the protocol."""

        class MyStructureMethod:
            @property
            def name(self) -> str:
                return "my_structure"

            def detect(self, ctx: TableContext) -> BoundaryHypothesis | None:
                return _make_hypothesis()

        obj = MyStructureMethod()
        assert isinstance(obj, StructureMethod)

    def test_nonconformance(self) -> None:
        """A class missing `detect` does NOT satisfy the protocol."""

        class NotAStructureMethod:
            @property
            def name(self) -> str:
                return "incomplete"

        obj = NotAStructureMethod()
        assert not isinstance(obj, StructureMethod)


# ---------------------------------------------------------------------------
# TestCellExtractionProtocol
# ---------------------------------------------------------------------------


class TestCellExtractionProtocol:
    def test_conformance(self) -> None:
        """A plain class with `name` and `extract(ctx, col_bounds, row_bounds)` satisfies the protocol."""

        class MyCellMethod:
            @property
            def name(self) -> str:
                return "my_cell"

            def extract(
                self,
                ctx: TableContext,
                col_boundaries: tuple[float, ...],
                row_boundaries: tuple[float, ...],
            ) -> CellGrid | None:
                return _make_grid()

        obj = MyCellMethod()
        assert isinstance(obj, CellExtractionMethod)


# ---------------------------------------------------------------------------
# TestPostProcessorProtocol
# ---------------------------------------------------------------------------


class TestPostProcessorProtocol:
    def test_conformance(self) -> None:
        """A plain class with `name` and `process(grid, ctx)` satisfies the protocol."""

        class MyPostProcessor:
            @property
            def name(self) -> str:
                return "my_postprocessor"

            def process(self, grid: CellGrid, ctx: TableContext) -> CellGrid:
                return grid

        obj = MyPostProcessor()
        assert isinstance(obj, PostProcessor)

    def test_passthrough(self) -> None:
        """A no-op post-processor that returns the grid unchanged satisfies the contract."""

        class NoOpPostProcessor:
            @property
            def name(self) -> str:
                return "noop"

            def process(self, grid: CellGrid, ctx: TableContext) -> CellGrid:
                return grid

        obj = NoOpPostProcessor()
        assert isinstance(obj, PostProcessor)

        ctx = _make_ctx()
        grid = _make_grid()
        result = obj.process(grid, ctx)
        assert result is grid
        assert result.headers == ("A", "B")
        assert result.rows == (("1", "2"), ("3", "4"))
