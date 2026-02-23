"""Tests for the quality scoring framework in zotero_chunk_rag.feature_extraction.scoring."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from zotero_chunk_rag.feature_extraction.models import (
    CellGrid,
    TableContext,
)
from zotero_chunk_rag.feature_extraction.scoring import (
    decimal_displacement_count,
    fill_rate,
    garbled_text_score,
    numeric_coherence,
    rank_and_select,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ctx() -> TableContext:
    """Create a minimal TableContext with a mock page."""
    page = MagicMock()

    def get_text_side_effect(fmt: str, **kwargs):  # noqa: ANN001
        if fmt == "words":
            return []
        if fmt == "dict":
            return {"blocks": []}
        return ""

    page.get_text = MagicMock(side_effect=get_text_side_effect)
    page.get_drawings = MagicMock(return_value=[])
    rect = MagicMock()
    rect.height = 842.0
    rect.width = 595.0
    page.rect = rect
    return TableContext(
        page=page,
        page_num=0,
        bbox=(0.0, 0.0, 595.0, 842.0),
        pdf_path=Path("/tmp/test.pdf"),
    )


def _make_grid(
    headers: tuple[str, ...],
    rows: tuple[tuple[str, ...], ...],
    method: str = "test",
) -> CellGrid:
    """Create a CellGrid with the given content."""
    return CellGrid(
        headers=headers,
        rows=rows,
        col_boundaries=(0.0, 100.0, 200.0),
        row_boundaries=(0.0, 20.0, 40.0),
        method=method,
    )


# ---------------------------------------------------------------------------
# TestFillRate
# ---------------------------------------------------------------------------


class TestFillRate:
    def test_full_grid(self) -> None:
        """All cells non-empty gives fill_rate = 1.0."""
        grid = _make_grid(
            headers=("A", "B", "C"),
            rows=(("1", "2", "3"), ("4", "5", "6")),
        )
        assert fill_rate(grid) == 1.0

    def test_half_empty(self) -> None:
        """Half cells empty gives fill_rate ~= 0.5."""
        grid = _make_grid(
            headers=("A", "B"),
            rows=(("1", ""), ("", "4")),
        )
        # 4 non-empty (A, B, 1, 4) out of 6 total
        # Headers: A, B (2 non-empty)
        # Rows: 1, "", "", 4 (2 non-empty)
        # Total: 4 non-empty / 6 total
        result = fill_rate(grid)
        assert abs(result - 4.0 / 6.0) < 1e-9

    def test_whitespace_is_empty(self) -> None:
        """Cells with only spaces/tabs count as empty."""
        grid = _make_grid(
            headers=("A", "   ", "\t"),
            rows=(("value", "  ", "\t\t"),),
        )
        # Non-empty: A, value = 2 out of 6
        result = fill_rate(grid)
        assert abs(result - 2.0 / 6.0) < 1e-9


# ---------------------------------------------------------------------------
# TestDecimalDisplacement
# ---------------------------------------------------------------------------


class TestDecimalDisplacement:
    def test_no_displacement(self) -> None:
        """Cells like '0.047', '1.23' have no displacement."""
        grid = _make_grid(
            headers=("Col",),
            rows=(("0.047",), ("1.23",), ("42",)),
        )
        assert decimal_displacement_count(grid) == 0

    def test_with_displacement(self) -> None:
        """Cells like '.047', '.23' are displaced."""
        grid = _make_grid(
            headers=("Col",),
            rows=((".047",), (".23",), ("0.5",)),
        )
        assert decimal_displacement_count(grid) == 2


# ---------------------------------------------------------------------------
# TestGarbledText
# ---------------------------------------------------------------------------


class TestGarbledText:
    def test_normal_text(self) -> None:
        """Typical academic text has garbled score near 0.0."""
        grid = _make_grid(
            headers=("Variable", "Coefficient", "P-value"),
            rows=(
                ("Age", "0.045", "0.023"),
                ("Gender", "-0.12", "0.001"),
            ),
        )
        assert garbled_text_score(grid) == 0.0

    def test_garbled_cells(self) -> None:
        """Cells with 30+ char 'words' are garbled."""
        long_word = "a" * 35
        grid = _make_grid(
            headers=("Normal",),
            rows=((long_word,), ("fine text",)),
        )
        score = garbled_text_score(grid)
        assert score > 0

    def test_greek_excluded(self) -> None:
        """Cells with Greek characters are not flagged as garbled even with long tokens."""
        # A long token that contains Greek letters
        greek_text = "\u03b1" * 30  # 30 alpha characters
        grid = _make_grid(
            headers=("Formula",),
            rows=((greek_text,), ("normal",)),
        )
        score = garbled_text_score(grid)
        assert score == 0.0


# ---------------------------------------------------------------------------
# TestNumericCoherence
# ---------------------------------------------------------------------------


class TestNumericCoherence:
    def test_coherent_columns(self) -> None:
        """Column of all numbers and column of all text gives coherence = 1.0."""
        grid = _make_grid(
            headers=("Name", "Value"),
            rows=(
                ("Alice", "1.5"),
                ("Bob", "2.3"),
                ("Carol", "3.1"),
            ),
        )
        result = numeric_coherence(grid)
        assert result == 1.0

    def test_mixed_column(self) -> None:
        """Column mixing numbers and text gives coherence < 1.0."""
        grid = _make_grid(
            headers=("Mixed",),
            rows=(
                ("1.5",),
                ("text",),
                ("2.3",),
                ("more text",),
                ("3.1",),
            ),
        )
        # Column is >50% numeric (3/5 = 60%) but not all numeric -> not coherent
        result = numeric_coherence(grid)
        assert result < 1.0


# ---------------------------------------------------------------------------
# TestRankAndSelect
# ---------------------------------------------------------------------------


class TestRankAndSelect:
    def test_better_grid_wins(self) -> None:
        """Grid A (fill=0.9, no displacement) beats Grid B (fill=0.5, displacement=3)."""
        ctx = _make_ctx()
        grid_a = _make_grid(
            headers=("A", "B", "C"),
            rows=(("1", "2", "3"), ("4", "5", "6"), ("7", "8", "9")),
            method="strategy_a",
        )
        grid_b = _make_grid(
            headers=("A", "", ""),
            rows=((".047", "", ""), (".23", "x", ""), (".5", "", "")),
            method="strategy_b",
        )
        winner, scores = rank_and_select([grid_a, grid_b], ctx)
        assert winner is grid_a
        assert scores["consensus:strategy_a"] < scores["consensus:strategy_b"]

    def test_single_grid_returned(self) -> None:
        """One grid is returned as winner with score 0."""
        ctx = _make_ctx()
        grid = _make_grid(
            headers=("X",),
            rows=(("1",),),
            method="only_method",
        )
        winner, scores = rank_and_select([grid], ctx)
        assert winner is grid
        assert len(scores) == 1
        assert scores["consensus:only_method"] == 0.0

    def test_empty_list_returns_none(self) -> None:
        """Empty list returns (None, {})."""
        ctx = _make_ctx()
        winner, scores = rank_and_select([], ctx)
        assert winner is None
        assert scores == {}

    def test_scores_dict_populated(self) -> None:
        """scores_dict has one entry per grid, keyed by method, values are rank sums."""
        ctx = _make_ctx()
        grid_a = _make_grid(
            headers=("A", "B"),
            rows=(("1", "2"), ("3", "4")),
            method="m1",
        )
        grid_b = _make_grid(
            headers=("A", "B"),
            rows=(("1", "2"), ("3", "4")),
            method="m2",
        )
        _winner, scores = rank_and_select([grid_a, grid_b], ctx)
        assert "consensus:m1" in scores
        assert "consensus:m2" in scores
        assert len(scores) == 2
        # Values should be floats (rank sums)
        for v in scores.values():
            assert isinstance(v, (int, float))

    def test_ground_truth_mode(self) -> None:
        """Ground truth function makes grid A win even if other metrics are slightly worse."""
        ctx = _make_ctx()
        # Grid A: slightly worse fill but high ground truth
        grid_a = _make_grid(
            headers=("A", ""),
            rows=(("1", ""), ("3", "")),
            method="gt_winner",
        )
        # Grid B: better fill, no displacement, but low ground truth
        grid_b = _make_grid(
            headers=("A", "B"),
            rows=(("1", "2"), ("3", "4")),
            method="gt_loser",
        )

        def ground_truth_fn(headers, rows):  # noqa: ANN001
            # grid_a has method "gt_winner" -- but we check by content
            # The function receives headers and rows, not the grid object.
            # We'll use the fill level to distinguish.
            all_cells = list(headers)
            for r in rows:
                all_cells.extend(r)
            non_empty = sum(1 for c in all_cells if c.strip())
            if non_empty < len(all_cells):
                return 0.95  # grid_a (has empty cells)
            return 0.50  # grid_b (all full)

        winner, scores = rank_and_select([grid_a, grid_b], ctx, ground_truth_fn=ground_truth_fn)
        assert winner is grid_a

    def test_tie_breaking(self) -> None:
        """Two identical grids: either can be selected, no crash."""
        ctx = _make_ctx()
        grid_a = _make_grid(
            headers=("A", "B"),
            rows=(("1", "2"), ("3", "4")),
            method="tied_a",
        )
        grid_b = _make_grid(
            headers=("A", "B"),
            rows=(("1", "2"), ("3", "4")),
            method="tied_b",
        )
        winner, scores = rank_and_select([grid_a, grid_b], ctx)
        assert winner is not None
        assert winner.method in ("tied_a", "tied_b")
        # Scores should be equal for tied grids
        assert scores["consensus:tied_a"] == scores["consensus:tied_b"]
