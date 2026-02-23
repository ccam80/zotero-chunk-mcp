"""Tests for word assignment cell extraction method."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from zotero_chunk_rag.feature_extraction.methods.cell_words import (
    WordAssignment,
    _assign_word_to_column,
    _assign_word_to_row,
)
from zotero_chunk_rag.feature_extraction.models import CellGrid, TableContext
from zotero_chunk_rag.feature_extraction.protocols import CellExtractionMethod


class TestAssignColumn:
    """Tests for _assign_word_to_column helper."""

    def test_before_first_boundary(self) -> None:
        """x_center < first boundary -> col 0."""
        col_bounds = (100.0, 200.0, 300.0)
        assert _assign_word_to_column(50.0, col_bounds) == 0

    def test_after_last_boundary(self) -> None:
        """x_center > last boundary -> last col."""
        col_bounds = (100.0, 200.0, 300.0)
        assert _assign_word_to_column(350.0, col_bounds) == 3

    def test_between_boundaries(self) -> None:
        """x_center between boundary[0] and boundary[1] -> col 1."""
        col_bounds = (100.0, 200.0, 300.0)
        assert _assign_word_to_column(150.0, col_bounds) == 1

    def test_exactly_on_boundary(self) -> None:
        """x_center exactly on a boundary -> assigned to the right column.

        bisect_right places exact matches to the right, so boundary value
        goes to the next column.
        """
        col_bounds = (100.0, 200.0, 300.0)
        assert _assign_word_to_column(200.0, col_bounds) == 2

    def test_empty_boundaries(self) -> None:
        """No boundaries -> always col 0."""
        assert _assign_word_to_column(150.0, ()) == 0


class TestAssignRow:
    """Tests for _assign_word_to_row helper."""

    def test_above_first_boundary(self) -> None:
        """y_center < first boundary -> row 0."""
        row_bounds = (50.0, 100.0)
        assert _assign_word_to_row(25.0, row_bounds) == 0

    def test_below_last_boundary(self) -> None:
        """y_center > last boundary -> last row."""
        row_bounds = (50.0, 100.0)
        assert _assign_word_to_row(150.0, row_bounds) == 2

    def test_between_boundaries(self) -> None:
        """y_center between boundary[0] and boundary[1] -> row 1."""
        row_bounds = (50.0, 100.0)
        assert _assign_word_to_row(75.0, row_bounds) == 1


class TestWordAssignment:
    """Tests for WordAssignment class."""

    def test_protocol_conformance(self) -> None:
        """WordAssignment satisfies CellExtractionMethod protocol."""
        method = WordAssignment()
        assert isinstance(method, CellExtractionMethod)

    def test_simple_grid(self) -> None:
        """2x3 grid of words with clear boundaries. Each word in correct cell."""
        method = WordAssignment()
        ctx = MagicMock(spec=TableContext)

        # 2 rows, 3 cols. Boundaries at x=100, x=200 and y=50
        # Words: (x0, y0, x1, y1, text, block, line, word)
        ctx.words = [
            # Row 0 (y < 50)
            (10.0, 10.0, 40.0, 20.0, "H1", 0, 0, 0),    # col 0 (x_center=25)
            (110.0, 10.0, 140.0, 20.0, "H2", 0, 0, 1),   # col 1 (x_center=125)
            (210.0, 10.0, 240.0, 20.0, "H3", 0, 0, 2),   # col 2 (x_center=225)
            # Row 1 (y > 50)
            (10.0, 60.0, 40.0, 70.0, "A", 0, 1, 0),      # col 0 (x_center=25)
            (110.0, 60.0, 140.0, 70.0, "B", 0, 1, 1),    # col 1 (x_center=125)
            (210.0, 60.0, 240.0, 70.0, "C", 0, 1, 2),    # col 2 (x_center=225)
        ]
        ctx.bbox = (0.0, 0.0, 300.0, 100.0)

        result = method.extract(
            ctx,
            col_boundaries=(100.0, 200.0),
            row_boundaries=(50.0,),
        )

        assert result is not None
        assert isinstance(result, CellGrid)
        assert result.method == "word_assignment"
        assert result.headers == ("H1", "H2", "H3")
        assert result.rows == (("A", "B", "C"),)

    def test_words_concatenated_with_spaces(self) -> None:
        """Two words in same cell joined with single space."""
        method = WordAssignment()
        ctx = MagicMock(spec=TableContext)

        # Single row, single col, two words
        ctx.words = [
            (10.0, 10.0, 30.0, 20.0, "Hello", 0, 0, 0),
            (35.0, 10.0, 60.0, 20.0, "World", 0, 0, 1),
        ]
        ctx.bbox = (0.0, 0.0, 100.0, 50.0)

        result = method.extract(
            ctx,
            col_boundaries=(),  # 1 col
            row_boundaries=(),  # 1 row
        )

        assert result is not None
        # With no boundaries, everything is in a single cell (row 0, col 0)
        # That single row becomes the headers
        assert result.headers == ("Hello World",)
        assert result.rows == ()

    def test_empty_cells(self) -> None:
        """Column with no words in some rows produces empty string."""
        method = WordAssignment()
        ctx = MagicMock(spec=TableContext)

        # 2 rows, 2 cols. Only first column has words in both rows
        ctx.words = [
            (10.0, 10.0, 40.0, 20.0, "Name", 0, 0, 0),      # row 0, col 0
            (110.0, 10.0, 140.0, 20.0, "Value", 0, 0, 1),    # row 0, col 1
            (10.0, 60.0, 40.0, 70.0, "Alice", 0, 1, 0),      # row 1, col 0
            # row 1, col 1 has no words
        ]
        ctx.bbox = (0.0, 0.0, 200.0, 100.0)

        result = method.extract(
            ctx,
            col_boundaries=(100.0,),
            row_boundaries=(50.0,),
        )

        assert result is not None
        assert result.headers == ("Name", "Value")
        assert result.rows == (("Alice", ""),)

    def test_word_on_boundary(self) -> None:
        """Word centered exactly on a column boundary gets deterministic assignment.

        bisect_right assigns exact matches to the right column.
        """
        method = WordAssignment()
        ctx = MagicMock(spec=TableContext)

        # Word x-center at exactly 100.0 (the boundary)
        # x0=90, x1=110 -> center=100.0
        ctx.words = [
            (90.0, 10.0, 110.0, 20.0, "OnBoundary", 0, 0, 0),
        ]
        ctx.bbox = (0.0, 0.0, 200.0, 50.0)

        result = method.extract(
            ctx,
            col_boundaries=(100.0,),  # boundary at 100
            row_boundaries=(),
        )

        assert result is not None
        # bisect_right(100.0) on (100.0,) = 1, so col 1
        # Single row becomes headers
        assert result.headers == ("", "OnBoundary")

    def test_name_property(self) -> None:
        """The name property returns 'word_assignment'."""
        method = WordAssignment()
        assert method.name == "word_assignment"

    def test_returns_none_no_words(self) -> None:
        """No words in context -> returns None."""
        method = WordAssignment()
        ctx = MagicMock(spec=TableContext)
        ctx.words = []
        ctx.bbox = (0.0, 0.0, 200.0, 100.0)

        result = method.extract(
            ctx,
            col_boundaries=(100.0,),
            row_boundaries=(50.0,),
        )

        assert result is None
