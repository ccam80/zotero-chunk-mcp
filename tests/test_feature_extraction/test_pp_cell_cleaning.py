"""Tests for cell_cleaning standalone functions and clean_cells()."""
from __future__ import annotations

import pytest

from zotero_chunk_rag.feature_extraction.postprocessors.cell_cleaning import (
    clean_cells,
    _map_control_chars,
    _normalize_ligatures,
    _reassemble_negative_signs,
    _recover_leading_zeros,
)


class TestCleanCells:
    def test_ligature_normalization(self) -> None:
        """Ligature codepoints in headers and rows are expanded."""
        headers, rows = clean_cells(["e\ufb03ciency"], [["\ufb03cient", "e\ufb00ect"]])
        assert headers == ["efficiency"]
        assert rows[0] == ["fficient", "effect"]

    def test_leading_zero(self) -> None:
        """'.047' and '.95' gain leading zeros."""
        _, rows = clean_cells(["A", "B"], [[".047", ".95"]])
        assert rows[0] == ["0.047", "0.95"]

    def test_leading_zero_guard(self) -> None:
        """'.txt' is not numeric so it is left unchanged."""
        _, rows = clean_cells(["A"], [[".txt"]])
        assert rows[0][0] == ".txt"

    def test_negative_reassembly(self) -> None:
        """Unicode minus followed by space and digits is reassembled."""
        _, rows = clean_cells(["A"], [["\u2212 0.45"]])
        assert rows[0][0] == "-0.45"

    def test_whitespace(self) -> None:
        """Multiple spaces collapsed; newlines converted to spaces."""
        _, rows = clean_cells(["A"], [["  hello   world  ", "a\nb"]])
        assert rows[0] == ["hello world", "a b"]

    def test_unicode_minus(self) -> None:
        """Bare Unicode minus becomes ASCII hyphen-minus."""
        _, rows = clean_cells(["A"], [["\u2212"]])
        assert rows[0][0] == "-"

    def test_dimensions_preserved(self) -> None:
        """Output shape matches input shape exactly."""
        headers = ["X", "Y", "Z"]
        rows = [["a", "b", "c"], ["d", "e", "f"]]
        out_headers, out_rows = clean_cells(headers, rows)
        assert len(out_headers) == 3
        assert len(out_rows) == 2
        assert all(len(r) == 3 for r in out_rows)

    def test_empty_input(self) -> None:
        """clean_cells with empty lists returns empty lists."""
        out_headers, out_rows = clean_cells([], [])
        assert out_headers == []
        assert out_rows == []


class TestNormalizeLigatures:
    def test_ffi(self) -> None:
        assert _normalize_ligatures("\ufb03cient") == "fficient"

    def test_ff(self) -> None:
        assert _normalize_ligatures("e\ufb00ect") == "effect"

    def test_no_ligature(self) -> None:
        assert _normalize_ligatures("hello") == "hello"


class TestRecoverLeadingZeros:
    def test_dot_digits(self) -> None:
        assert _recover_leading_zeros(".047") == "0.047"

    def test_not_numeric(self) -> None:
        assert _recover_leading_zeros(".txt") == ".txt"


class TestReassembleNegativeSigns:
    def test_unicode_minus_space_number(self) -> None:
        assert _reassemble_negative_signs("\u2212 0.45") == "-0.45"

    def test_already_correct(self) -> None:
        assert _reassemble_negative_signs("-0.45") == "-0.45"

    def test_non_numeric_unchanged(self) -> None:
        assert _reassemble_negative_signs("hello") == "hello"


class TestMapControlChars:
    def test_symbol_font_preserved(self) -> None:
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
        result = _map_control_chars("alpha\x06beta", None, dict_blocks)
        assert "\x06" in result

    def test_text_font_stripped(self) -> None:
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
        result = _map_control_chars("alpha\x06beta", None, dict_blocks)
        assert "\x06" not in result
        assert "alphabeta" in result
