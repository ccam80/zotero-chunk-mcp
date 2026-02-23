"""Word assignment cell extraction method.

Assigns whole words to cells based on x-position relative to column boundaries
and y-position relative to row boundaries. Adapts the existing
_extract_via_words() logic from pdf_processor.py as a CellExtractionMethod.
"""
from __future__ import annotations

import bisect
import logging
from typing import TYPE_CHECKING

from ..models import CellGrid

if TYPE_CHECKING:
    from ..models import TableContext

logger = logging.getLogger(__name__)


def _assign_word_to_column(word_x_center: float, col_boundaries: tuple[float, ...]) -> int:
    """Return column index for a word based on its x-center position.

    Words before the first column boundary go to column 0, words between
    boundary[i-1] and boundary[i] go to column i, and words after the
    last boundary go to the last column.

    Parameters
    ----------
    word_x_center:
        The horizontal center of the word.
    col_boundaries:
        Internal column boundary x-positions (ascending floats).

    Returns
    -------
    int
        Zero-based column index.
    """
    return bisect.bisect_right(col_boundaries, word_x_center)


def _assign_word_to_row(word_y_center: float, row_boundaries: tuple[float, ...]) -> int:
    """Return row index for a word based on its y-center position.

    Words above the first row boundary go to row 0, words between
    boundary[i-1] and boundary[i] go to row i, and words below the
    last boundary go to the last row.

    Parameters
    ----------
    word_y_center:
        The vertical center of the word.
    row_boundaries:
        Internal row boundary y-positions (ascending floats).

    Returns
    -------
    int
        Zero-based row index.
    """
    return bisect.bisect_right(row_boundaries, word_y_center)


class WordAssignment:
    """Cell extraction by assigning whole words to cells via boundary positions.

    For each word in the table bbox, determines the cell by the word's x-center
    relative to column boundaries and y-center relative to row boundaries.
    Multiple words per cell are concatenated with spaces, sorted left-to-right.
    """

    @property
    def name(self) -> str:
        return "word_assignment"

    def extract(
        self,
        ctx: TableContext,
        col_boundaries: tuple[float, ...],
        row_boundaries: tuple[float, ...],
    ) -> CellGrid | None:
        """Extract cell text by assigning words to cells via boundary positions.

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
            Extracted cell content, or None if no words found.
        """
        words = ctx.words
        if not words:
            return None

        num_cols = len(col_boundaries) + 1
        num_rows = len(row_boundaries) + 1

        # Assign each word to a cell
        # cell_words maps (row_idx, col_idx) -> list of (x0, text) for sorting
        cell_words: dict[tuple[int, int], list[tuple[float, str]]] = {}

        for w in words:
            # w = (x0, y0, x1, y1, text, block_no, line_no, word_no)
            x_center = (w[0] + w[2]) / 2
            y_center = (w[1] + w[3]) / 2

            col_idx = _assign_word_to_column(x_center, col_boundaries)
            row_idx = _assign_word_to_row(y_center, row_boundaries)

            # Clamp to valid range
            col_idx = min(col_idx, num_cols - 1)
            row_idx = min(row_idx, num_rows - 1)

            cell_words.setdefault((row_idx, col_idx), []).append((w[0], w[4]))

        # Build grid: concatenate words sorted left-to-right
        rows_raw: list[tuple[str, ...]] = []
        for ri in range(num_rows):
            row: list[str] = []
            for ci in range(num_cols):
                words_in_cell = cell_words.get((ri, ci), [])
                if words_in_cell:
                    # Sort by x0 position (left-to-right)
                    words_in_cell.sort(key=lambda wt: wt[0])
                    row.append(" ".join(text for _, text in words_in_cell))
                else:
                    row.append("")
            rows_raw.append(tuple(row))

        # First row is headers
        headers = rows_raw[0] if rows_raw else ()
        data_rows = tuple(rows_raw[1:]) if len(rows_raw) > 1 else ()

        return CellGrid(
            headers=headers,
            rows=data_rows,
            col_boundaries=col_boundaries,
            row_boundaries=row_boundaries,
            method="word_assignment",
        )
