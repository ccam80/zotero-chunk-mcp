"""Unit tests for content quality detection functions."""
import pytest

from zotero_chunk_rag.pdf_processor import (
    _detect_garbled_spacing,
    _detect_interleaved_chars,
    _detect_encoding_artifacts,
    _check_content_readability,
    _normalize_ligatures,
    _remove_empty_columns,
    _parse_prose_rows,
    SYNTHETIC_CAPTION_PREFIX,
)
from zotero_chunk_rag.models import ExtractedTable


# ---- _detect_garbled_spacing ----

class TestDetectGarbledSpacing:

    def test_normal_text_not_garbled(self):
        ok, _ = _detect_garbled_spacing("The quick brown fox jumps over the lazy dog")
        assert not ok

    def test_merged_words_flagged(self):
        # Simulate merged words (no spaces) — avg word length >> 25
        ok, reason = _detect_garbled_spacing(
            "ThisisaveryverylongstringwithnospacesthatrepresentsgarbageextractedPDFtext"
        )
        assert ok
        assert "avg word length" in reason

    def test_empty_text_not_garbled(self):
        ok, _ = _detect_garbled_spacing("")
        assert not ok

    def test_whitespace_only_not_garbled(self):
        ok, _ = _detect_garbled_spacing("   \n\t  ")
        assert not ok

    def test_short_words_pass(self):
        ok, _ = _detect_garbled_spacing("a b c d e f g h i j")
        assert not ok

    def test_borderline_passes(self):
        # 24 char word — just under threshold
        ok, _ = _detect_garbled_spacing("abcdefghijklmnopqrstuvwx normal words here")
        assert not ok

    def test_greek_letters_not_flagged(self):
        """Cells with Greek characters are technical content, not garbled."""
        ok, _ = _detect_garbled_spacing("sπ,τ=1averylongmathexpressionwithgreek")
        assert not ok

    def test_math_operators_not_flagged(self):
        """Cells with math operators (=, ±, ×) are technical content."""
        ok, _ = _detect_garbled_spacing("0992±0013iverylongconcatenatedfiltercoeff")
        assert not ok

    def test_superscripts_not_flagged(self):
        ok, _ = _detect_garbled_spacing("thisIsAVeryLongCellWith²exponents³")
        assert not ok


# ---- _detect_interleaved_chars ----

class TestDetectInterleavedChars:

    def test_normal_text_not_interleaved(self):
        ok, _ = _detect_interleaved_chars("The quick brown fox jumps over the lazy dog")
        assert not ok

    def test_interleaved_flagged(self):
        # >40% single alpha-char tokens
        ok, reason = _detect_interleaved_chars("a b c d e f g h real word here")
        assert ok
        assert "single alpha chars" in reason

    def test_leading_decimals_not_flagged(self):
        """Cells with leading-decimal numbers should not be flagged."""
        ok, _ = _detect_interleaved_chars(".906 .870 , . .432 .123 .456 .789")
        assert not ok

    def test_math_notation_sparse_not_flagged(self):
        """Single-letter variables diluted by normal words pass."""
        ok, _ = _detect_interleaved_chars("C × A × V → R states of the world")
        assert not ok

    def test_empty_not_interleaved(self):
        ok, _ = _detect_interleaved_chars("")
        assert not ok

    def test_too_few_tokens_not_flagged(self):
        # <5 tokens — not flagged even if all single chars
        ok, _ = _detect_interleaved_chars("a b c d")
        assert not ok

    def test_normal_sentence_passes(self):
        ok, _ = _detect_interleaved_chars("Heart rate variability is a measure of autonomic function")
        assert not ok


# ---- _detect_encoding_artifacts ----

class TestDetectEncodingArtifacts:

    def test_clean_text_no_artifacts(self):
        ok, found = _detect_encoding_artifacts("Figure 1. Normal caption text")
        assert not ok
        assert found == []

    def test_fi_ligature_detected(self):
        ok, found = _detect_encoding_artifacts("The \ufb01rst finding shows")
        assert ok
        assert "\ufb01" in found

    def test_fl_ligature_detected(self):
        ok, found = _detect_encoding_artifacts("The \ufb02ow rate was")
        assert ok
        assert "\ufb02" in found

    def test_ffi_ligature_detected(self):
        ok, found = _detect_encoding_artifacts("The e\ufb03cient method")
        assert ok
        assert "\ufb03" in found

    def test_empty_text_no_artifacts(self):
        ok, found = _detect_encoding_artifacts("")
        assert not ok
        assert found == []

    def test_multiple_ligatures(self):
        ok, found = _detect_encoding_artifacts("The \ufb01rst \ufb02ow was e\ufb03cient")
        assert ok
        assert len(found) == 3


# ---- _check_content_readability ----

class TestCheckContentReadability:

    def _make_table(self, rows, caption=None, headers=None):
        return ExtractedTable(
            page_num=1,
            table_index=0,
            bbox=(0, 0, 100, 100),
            headers=headers or [],
            rows=rows,
            caption=caption,
        )

    def test_clean_table_passes(self):
        table = self._make_table(
            [["Cell A", "Cell B"], ["Value 1", "Value 2"]],
            caption="Table 1. Results",
        )
        rpt = _check_content_readability(table)
        assert rpt["garbled_cells"] == 0
        assert rpt["interleaved_cells"] == 0
        assert not rpt["encoding_artifacts"]
        assert rpt["details"] == []

    def test_garbled_cell_detected(self):
        table = self._make_table(
            [["ThisisaveryverylongstringwithnospacesthatrepresentsgarbageextractedPDFtext", "OK"]],
        )
        rpt = _check_content_readability(table)
        assert rpt["garbled_cells"] >= 1

    def test_interleaved_cell_detected(self):
        table = self._make_table(
            [["a b c d e f g h real word", "OK"]],
        )
        rpt = _check_content_readability(table)
        assert rpt["interleaved_cells"] >= 1

    def test_encoding_artifact_in_caption(self):
        table = self._make_table(
            [["Cell", "Cell"]],
            caption="Table 1. The \ufb01rst finding",
        )
        rpt = _check_content_readability(table)
        assert rpt["encoding_artifacts"]

    def test_no_caption_no_encoding_check(self):
        table = self._make_table(
            [["Cell", "Cell"]],
            caption=None,
        )
        rpt = _check_content_readability(table)
        assert not rpt["encoding_artifacts"]


# ---- _normalize_ligatures ----

class TestNormalizeLigatures:

    def test_fi_ligature(self):
        assert _normalize_ligatures("The \ufb01rst \ufb01nding") == "The first finding"

    def test_fl_ligature(self):
        assert _normalize_ligatures("The \ufb02ow rate") == "The flow rate"

    def test_ffi_ligature(self):
        assert _normalize_ligatures("e\ufb03cient") == "efficient"

    def test_ffl_ligature(self):
        assert _normalize_ligatures("ba\ufb04e") == "baffle"

    def test_ff_ligature(self):
        assert _normalize_ligatures("co\ufb00ee") == "coffee"

    def test_multiple_ligatures(self):
        assert _normalize_ligatures("The \ufb01rst \ufb02ow was e\ufb03cient") == "The first flow was efficient"

    def test_none_passthrough(self):
        assert _normalize_ligatures(None) is None

    def test_empty_passthrough(self):
        assert _normalize_ligatures("") == ""

    def test_clean_text_unchanged(self):
        text = "Normal text without ligatures"
        assert _normalize_ligatures(text) == text


# ---- SYNTHETIC_CAPTION_PREFIX ----

class TestSyntheticCaptionPrefix:

    def test_prefix_value(self):
        """Ensure the prefix is stable for downstream checks."""
        assert SYNTHETIC_CAPTION_PREFIX == "Uncaptioned "


# ---- _remove_empty_columns ----

class TestRemoveEmptyColumns:

    def test_removes_fully_empty_columns(self):
        rows = [["a", "", "c"], ["d", "", "f"]]
        headers = ["H1", "", "H3"]
        new_rows, new_headers = _remove_empty_columns(rows, headers)
        # Middle column is empty in all rows AND has no header → removed
        # Wait — header is "" so it should be removed
        assert new_rows == [["a", "c"], ["d", "f"]]
        assert new_headers == ["H1", "H3"]

    def test_keeps_column_with_header(self):
        rows = [["a", "", "c"], ["d", "", "f"]]
        headers = ["H1", "H2", "H3"]
        new_rows, new_headers = _remove_empty_columns(rows, headers)
        # Middle column is empty but has header H2 → kept
        assert new_rows == rows
        assert new_headers == headers

    def test_keeps_column_with_data(self):
        rows = [["a", "b", "c"], ["d", "", "f"]]
        headers = ["H1", "", "H3"]
        new_rows, new_headers = _remove_empty_columns(rows, headers)
        # Middle column has data in row 0 → kept
        assert new_rows == rows
        assert new_headers == headers

    def test_no_empty_columns_unchanged(self):
        rows = [["a", "b"], ["c", "d"]]
        headers = ["H1", "H2"]
        new_rows, new_headers = _remove_empty_columns(rows, headers)
        assert new_rows == rows
        assert new_headers == headers

    def test_empty_rows_returns_unchanged(self):
        new_rows, new_headers = _remove_empty_columns([], ["H1"])
        assert new_rows == []
        assert new_headers == ["H1"]

    def test_multiple_empty_columns_removed(self):
        rows = [["a", "", "", "d"], ["e", "", "", "h"]]
        headers = ["", "", "", ""]
        new_rows, new_headers = _remove_empty_columns(rows, headers)
        assert new_rows == [["a", "d"], ["e", "h"]]


# ---- _parse_prose_rows ----

class TestParseProseRows:

    def test_definition_list_parsed(self):
        content = "ACC: Accuracy\nAUC: Area Under Curve\nPPV: Positive Predictive Value"
        rows = _parse_prose_rows(content)
        assert len(rows) == 3
        assert rows[0] == ["ACC", "Accuracy"]
        assert rows[1] == ["AUC", "Area Under Curve"]

    def test_em_dash_delimiter(self):
        content = "Term1 \u2014 Definition1\nTerm2 \u2014 Definition2"
        rows = _parse_prose_rows(content)
        assert len(rows) == 2
        assert rows[0] == ["Term1", "Definition1"]

    def test_plain_paragraph_single_cell(self):
        content = "This is a regular paragraph with no definition structure at all."
        rows = _parse_prose_rows(content)
        assert len(rows) == 1
        assert rows[0] == [content]

    def test_single_line_single_cell(self):
        content = "Just one line"
        rows = _parse_prose_rows(content)
        assert len(rows) == 1
        assert rows[0] == [content]

    def test_mixed_content_handled(self):
        content = "Section header\nTerm1: Def1\nTerm2: Def2\nTerm3: Def3"
        rows = _parse_prose_rows(content)
        # 3/4 lines have colons = 75% > 40% threshold
        assert len(rows) == 4
        # First line has no delimiter, stays as single-cell
        assert rows[0] == ["Section header"]
        assert rows[1] == ["Term1", "Def1"]

    def test_below_threshold_stays_single_cell(self):
        content = "Line one\nLine two\nLine three\nTerm: Definition"
        rows = _parse_prose_rows(content)
        # Only 1/4 = 25% have delimiters, below 40% threshold
        assert len(rows) == 1
        assert rows[0] == [content]
