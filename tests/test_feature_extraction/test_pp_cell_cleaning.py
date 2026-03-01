"""Tests for CellCleaning post-processor."""
from __future__ import annotations

import pytest

from zotero_chunk_rag.feature_extraction.models import CellGrid
from zotero_chunk_rag.feature_extraction.postprocessors.cell_cleaning import (
    CellCleaning,
    _map_control_chars,
    _normalize_ligatures,
    _reassemble_negative_signs,
    _recover_leading_zeros,
)


def _make_grid(
    rows: tuple[tuple[str, ...], ...],
    headers: tuple[str, ...] = ("Col A", "Col B"),
) -> CellGrid:
    return CellGrid(
        headers=headers,
        rows=rows,
        col_boundaries=(0.0, 100.0),
        row_boundaries=(50.0,),
        method="test",
    )


class TestCellCleaning:
    def test_ligature_normalization(self) -> None:
        """ffi ligature -> 'ffi'."""
        grid = _make_grid(
            rows=(("\ufb03cient", "e\ufb00ect"),),
            headers=("e\ufb03ciency", "Col B"),
        )
        pp = CellCleaning()
        result = pp.process(grid)

        assert result.headers[0] == "efficiency"
        assert result.rows[0][0] == "fficient"
        assert result.rows[0][1] == "effect"

    def test_leading_zero(self) -> None:
        """'.047' -> '0.047'."""
        grid = _make_grid(
            rows=((".047", ".95"),),
        )
        pp = CellCleaning()
        result = pp.process(grid)

        assert result.rows[0][0] == "0.047"
        assert result.rows[0][1] == "0.95"

    def test_leading_zero_guard(self) -> None:
        """'.txt' unchanged — not numeric."""
        grid = _make_grid(
            rows=((".txt", "normal"),),
        )
        pp = CellCleaning()
        result = pp.process(grid)

        assert result.rows[0][0] == ".txt"

    def test_negative_reassembly(self) -> None:
        """Reassembled correctly."""
        grid = _make_grid(
            rows=(("\u2212 0.45", "1234 \u2212 .56"),),
        )
        pp = CellCleaning()
        result = pp.process(grid)

        assert result.rows[0][0] == "-0.45"

    def test_whitespace_normalization(self) -> None:
        """Collapsed and stripped."""
        grid = _make_grid(
            rows=(("  hello   world  ", "a\nb\nc"),),
        )
        pp = CellCleaning()
        result = pp.process(grid)

        assert result.rows[0][0] == "hello world"
        assert result.rows[0][1] == "a b c"

    def test_control_char_greek_font(self) -> None:
        """\x06 in Greek font -> preserved/mapped."""
        dict_blocks = [{
            "type": 0,
            "lines": [{
                "spans": [{
                    "bbox": (40.0, 40.0, 60.0, 60.0),
                    "font": "Symbol",
                    "size": 10.0,
                    "flags": 0,
                    "text": "\x06",
                }],
            }],
        }]
        grid = _make_grid(
            rows=(("alpha\x06beta", "normal"),),
        )
        pp = CellCleaning()
        result = pp.process(grid, dict_blocks)

        # Control char preserved in Symbol font
        assert "\x06" in result.rows[0][0]

    def test_control_char_text_font(self) -> None:
        """\x06 in text font -> stripped."""
        dict_blocks = [{
            "type": 0,
            "lines": [{
                "spans": [{
                    "bbox": (40.0, 40.0, 60.0, 60.0),
                    "font": "TimesNewRoman",
                    "size": 10.0,
                    "flags": 0,
                    "text": "hello",
                }],
            }],
        }]
        grid = _make_grid(
            rows=(("alpha\x06beta", "normal"),),
        )
        pp = CellCleaning()
        result = pp.process(grid, dict_blocks)

        # Control char stripped in text font
        assert "\x06" not in result.rows[0][0]
        assert "alphabeta" in result.rows[0][0]

    def test_name(self) -> None:
        """CellCleaning has expected name."""
        pp = CellCleaning()
        assert pp.name == "cell_cleaning"
