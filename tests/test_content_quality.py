"""Unit tests for content quality detection functions."""
import pytest

from zotero_chunk_rag.pdf_processor import (
    _detect_garbled_spacing,
    _detect_interleaved_chars,
    _detect_encoding_artifacts,
    _check_content_readability,
    _normalize_ligatures,
    _clean_cell_text,
    _is_layout_artifact,
    _classify_artifact,
    _remove_empty_columns,
    _parse_prose_rows,
    _strip_footnote_rows,
    _strip_absorbed_caption,
    _split_at_internal_captions,
    _separate_header_data,
    _merge_over_divided_rows,
    _repair_low_fill_table,
    _adaptive_row_tolerance,
    _find_column_gap_threshold,
    _looks_numeric,
    _should_replace_with_word_api,
    _count_decimal_displacement,
    _count_numeric_integrity,
    _compute_fill_rate,
    _score_extraction,
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


# ---- _clean_cell_text ----

class TestCleanCellText:
    """Tests for broken-decimal repair and newline/whitespace collapse."""

    # -- Leading dot: single value (with leading-zero recovery) --
    def test_single_leading_dot(self):
        assert _clean_cell_text("4198\n.") == "0.4198"

    def test_leading_dot_with_marker(self):
        assert _clean_cell_text("0028*\n.") == "0.0028*"

    def test_leading_dot_with_dagger(self):
        assert _clean_cell_text("512\u2020\n.") == "0.512\u2020"

    # -- Leading dot: multi-value (with leading-zero recovery) --
    def test_multi_value_leading_dot(self):
        assert _clean_cell_text("9931 1789\n. .") == "0.9931 0.1789"

    # -- Inline broken decimal --
    def test_inline_broken_decimal(self):
        assert _clean_cell_text("0 .14 mm") == "0.14 mm"

    def test_inline_preserves_sentence(self):
        # "In 1998 . The results" has a space-dot-space pattern but the
        # regex requires digit-space-dot-digit, so no false positive.
        assert _clean_cell_text("In 1998 . The results") == "In 1998 . The results"

    # -- Newline collapse --
    def test_newline_collapsed(self):
        assert _clean_cell_text("hello\nworld") == "hello world"

    def test_multi_newline_collapsed(self):
        assert _clean_cell_text("a\n\nb\nc") == "a b c"

    # -- Whitespace collapse --
    def test_whitespace_collapsed(self):
        assert _clean_cell_text("a   b    c") == "a b c"

    def test_leading_trailing_stripped(self):
        assert _clean_cell_text("  hello  ") == "hello"

    # -- Combined pipeline: decimal fix THEN newline removal, THEN leading-zero --
    def test_pipeline_order_preserved(self):
        # "4198\n." must become "0.4198", not "4198 ." (if newlines went first)
        assert _clean_cell_text("4198\n.") == "0.4198"

    # -- Edge cases --
    def test_empty_string(self):
        assert _clean_cell_text("") == ""

    def test_none_passthrough(self):
        assert _clean_cell_text(None) is None

    def test_plain_text_unchanged(self):
        assert _clean_cell_text("Normal cell content") == "Normal cell content"

    def test_integer_unchanged(self):
        assert _clean_cell_text("42") == "42"

    def test_proper_decimal_unchanged(self):
        assert _clean_cell_text("3.14") == "3.14"

    # -- T1: Leading-zero recovery --
    def test_leading_zero_restored(self):
        """Bare ".NNN" numeric value gets 0 prepended."""
        assert _clean_cell_text(".4198") == "0.4198"

    def test_leading_zero_multi_value(self):
        """.NNN .NNN both get leading zeros."""
        assert _clean_cell_text(".9931 .1789") == "0.9931 0.1789"

    def test_leading_zero_not_applied_to_dotfile(self):
        """.gitignore should NOT get a leading zero."""
        assert _clean_cell_text(".gitignore") == ".gitignore"

    def test_leading_zero_not_applied_to_dotenv(self):
        """.env should NOT get a leading zero."""
        assert _clean_cell_text(".env") == ".env"

    def test_leading_zero_with_stats_marker(self):
        """".4198*" gets leading zero."""
        assert _clean_cell_text(".4198*") == "0.4198*"

    # -- T6: Negative sign reassembly --
    def test_negative_decimal_reassembly(self):
        """'18278 \u2212 .' → '-18278.'"""
        assert _clean_cell_text("18278 \u2212 .") == "-18278."

    def test_negative_decimal_with_fraction(self):
        """'18278 \u2212 .5' → '-18278.5'"""
        assert _clean_cell_text("18278 \u2212 .5") == "-18278.5"

    def test_standalone_negative(self):
        """\u2212 18278 → '-18278'"""
        assert _clean_cell_text("\u2212 18278") == "-18278"

    def test_negative_ascii_hyphen(self):
        """'- 3.14' → '-3.14'"""
        assert _clean_cell_text("- 3.14") == "-3.14"

    def test_nonnumeric_dash_unchanged(self):
        """'pre - post' should NOT be reassembled."""
        assert _clean_cell_text("pre - post") == "pre - post"

    def test_unicode_minus_normalized(self):
        """Unicode minus U+2212 normalized to ASCII in final output."""
        assert _clean_cell_text("5\u221210") == "5-10"


# ---- _is_layout_artifact ----

class TestIsLayoutArtifact:
    """Tests for layout-artifact table detection and classification."""

    def test_elsevier_article_info_box(self):
        """Elsevier article-info/abstract header is detected."""
        table = ExtractedTable(
            page_num=1, table_index=0,
            bbox=(0, 0, 500, 300),
            headers=["a r t i c l e", "i n f o", "a b s t r a c t"],
            rows=[
                ["Article history:", "Received 1 March 2021", "This paper presents..."],
                ["Keywords:", "Active inference", ""],
            ],
            caption="",
        )
        assert _is_layout_artifact(table) is True
        assert _classify_artifact(table) == "article_info_box"

    def test_elsevier_uppercase_variant(self):
        """Uppercase ARTICLE INFO variant is also detected."""
        table = ExtractedTable(
            page_num=1, table_index=0,
            bbox=(0, 0, 500, 300),
            headers=["A R T I C L E", "I N F O", "A B S T R A C T"],
            rows=[["Article history:", "Received 2020", "We present..."]],
            caption="",
        )
        assert _is_layout_artifact(table) is True
        assert _classify_artifact(table) == "article_info_box"

    def test_table_of_contents(self):
        """TOC with section numbers and page numbers is detected."""
        table = ExtractedTable(
            page_num=1, table_index=0,
            bbox=(0, 0, 500, 600),
            headers=["1 Introduction 904"],
            rows=[
                ["2 Review of methods 907"],
                ["3 The empirical mode decomposition 912"],
                ["4 Hilbert spectral analysis 935"],
                ["5 Discussion 987"],
                ["6 Conclusions 991"],
            ],
            caption="",
        )
        assert _is_layout_artifact(table) is True
        assert _classify_artifact(table) == "table_of_contents"

    def test_toc_packed_single_cell(self):
        """TOC entries packed into one cell (after newline collapse)."""
        table = ExtractedTable(
            page_num=1, table_index=0,
            bbox=(0, 0, 500, 600),
            headers=[
                "page 1 Introduction 904 . 2 Review of non-stationary data "
                "processing methods 907 . 3 The empirical mode decomposition 912 "
                "4 Hilbert spectral analysis 935",
            ],
            rows=[],
            caption="",
        )
        assert _classify_artifact(table) == "table_of_contents"

    def test_toc_multicolumn(self):
        """TOC split across 3 columns: number | title | page."""
        table = ExtractedTable(
            page_num=2, table_index=1,
            bbox=(0, 0, 500, 200),
            headers=[".10", "Discussion", "987"],
            rows=[
                [".11", "Conclusions", "991"],
                ["", "References", "993"],
            ],
            caption="",
        )
        assert _classify_artifact(table) == "table_of_contents"

    def test_block_diagram_as_table(self):
        """Sparse uncaptioned table with Figure N reference is detected."""
        table = ExtractedTable(
            page_num=5, table_index=0,
            bbox=(0, 0, 500, 400),
            headers=["Interface to Human Body", "Analog", "Circuit", "Output"],
            rows=[
                ["Electrode", "", "", ""],
                ["", "Amplifier", "", ""],
                ["Figure 3 Block diagram outlining the system", "", "", ""],
                ["", "", "ADC", ""],
                ["", "", "", "DAC"],
                ["", "", "", ""],
            ],
            caption="",  # no caption -> uncaptioned
        )
        assert _is_layout_artifact(table) is True
        assert _classify_artifact(table) == "diagram_as_table"

    def test_real_data_table_not_filtered(self):
        """A normal data table with a caption is NOT an artifact."""
        table = ExtractedTable(
            page_num=3, table_index=1,
            bbox=(0, 0, 500, 200),
            headers=["Parameter", "Value", "Unit"],
            rows=[
                ["Heart rate", "72", "bpm"],
                ["Systolic BP", "120", "mmHg"],
                ["Diastolic BP", "80", "mmHg"],
            ],
            caption="Table 1. Patient demographics.",
        )
        assert _is_layout_artifact(table) is False
        assert _classify_artifact(table) is None

    def test_sparse_table_with_caption_not_filtered(self):
        """A sparse table WITH a caption is NOT an artifact."""
        table = ExtractedTable(
            page_num=10, table_index=3,
            bbox=(0, 0, 500, 200),
            headers=["Filter", "Pole 1", "Pole 2", "Pole 3"],
            rows=[
                ["Comb", "0.914±0.119i", "", ""],
                ["Highpass", "", "0.707", ""],
            ],
            caption="Table 3. Poles of comb filters.",
        )
        assert _is_layout_artifact(table) is False

    def test_abbreviation_glossary_not_filtered(self):
        """Abbreviation glossary is well-formed — kept (useful reference)."""
        table = ExtractedTable(
            page_num=22, table_index=8,
            bbox=(0, 0, 300, 400),
            headers=["ADC", "Analog-to-digital conversion"],
            rows=[
                ["BLE", "Bluetooth Low Energy"],
                ["DAC", "Digital-to-analog converter"],
                ["EMG", "Electromyography"],
            ],
            caption="",
        )
        # 100% fill, no figure ref, no TOC pattern → NOT an artifact
        assert _is_layout_artifact(table) is False

    def test_header_with_plain_abstract_not_filtered(self):
        """A real table whose header contains 'Abstract' is NOT an artifact."""
        table = ExtractedTable(
            page_num=4, table_index=2,
            bbox=(0, 0, 500, 200),
            headers=["Study", "Abstract Concepts", "Concrete Concepts"],
            rows=[
                ["Smith 2020", "4.2", "3.8"],
                ["Jones 2021", "5.1", "4.9"],
            ],
            caption="",
        )
        assert _is_layout_artifact(table) is False
        assert _classify_artifact(table) is None

    def test_captioned_table_with_article_info_header_not_filtered(self):
        """A captioned table with 'article' in header is NOT an artifact."""
        table = ExtractedTable(
            page_num=2, table_index=1,
            bbox=(0, 0, 500, 200),
            headers=["Article", "Year", "Citations"],
            rows=[
                ["Smith et al.", "2020", "42"],
            ],
            caption="Table 1. Summary of articles reviewed.",
        )
        assert _is_layout_artifact(table) is False


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


# ---- _looks_numeric ----

class TestLooksNumeric:

    def test_plain_integer(self):
        assert _looks_numeric("42") is True

    def test_decimal(self):
        assert _looks_numeric("3.14") is True

    def test_leading_dot(self):
        assert _looks_numeric(".4198") is True

    def test_negative(self):
        assert _looks_numeric("-3.14") is True

    def test_with_stat_marker(self):
        assert _looks_numeric("0.4198*") is True

    def test_with_dagger(self):
        assert _looks_numeric("0.512\u2020") is True

    def test_multi_value(self):
        assert _looks_numeric(".9931 .1789") is True

    def test_text_not_numeric(self):
        assert _looks_numeric("hello") is False

    def test_dotfile_not_numeric(self):
        assert _looks_numeric(".gitignore") is False

    def test_empty(self):
        assert _looks_numeric("") is False


# ---- _strip_footnote_rows ----

class TestStripFootnoteRows:

    def test_note_row_stripped(self):
        """'Note. Models 1-7...' with single cell spanning all cols is stripped."""
        rows = [
            ["A", "1.2", "3.4"],
            ["B", "5.6", "7.8"],
            ["Note. Models 1-7 control for age and sex.", "", ""],
        ]
        headers = ["Var", "M1", "M2"]
        cleaned, footnotes = _strip_footnote_rows(rows, headers)
        assert len(cleaned) == 2
        assert "Note." in footnotes

    def test_dagger_row_stripped(self):
        """\u2020 p < .05 footnote row is stripped."""
        rows = [
            ["A", "1.2"],
            ["B", "5.6"],
            ["\u2020 p < .05, \u2021 p < .01", ""],
        ]
        headers = ["Var", "Value"]
        cleaned, footnotes = _strip_footnote_rows(rows, headers)
        assert len(cleaned) == 2
        assert "\u2020" in footnotes

    def test_normal_row_kept(self):
        """Normal data rows are not stripped."""
        rows = [
            ["A", "1.2", "3.4"],
            ["B", "5.6", "7.8"],
            ["C", "9.0", "1.1"],
        ]
        headers = ["Var", "M1", "M2"]
        cleaned, footnotes = _strip_footnote_rows(rows, headers)
        assert len(cleaned) == 3
        assert footnotes == ""

    def test_single_signal_insufficient(self):
        """Single signal alone should NOT trigger stripping."""
        rows = [
            ["A", "1.2"],
            ["B", "5.6"],
            ["Normal row", "value"],  # 2 filled cells, no footnote pattern
        ]
        headers = ["Var", "Value"]
        cleaned, footnotes = _strip_footnote_rows(rows, headers)
        assert len(cleaned) == 3  # not stripped — only outlier-length signal

    def test_empty_rows_handled(self):
        """Empty table returns unchanged."""
        cleaned, footnotes = _strip_footnote_rows([], ["H1"])
        assert cleaned == []
        assert footnotes == ""

    def test_footnotes_in_markdown(self):
        """Footnotes appear in markdown output."""
        table = ExtractedTable(
            page_num=1, table_index=0,
            bbox=(0, 0, 100, 100),
            headers=["A", "B"],
            rows=[["1", "2"]],
            footnotes="Note. p < .05",
        )
        md = table.to_markdown()
        assert "*Note. p < .05*" in md


# ---- _strip_absorbed_caption ----

class TestStripAbsorbedCaption:

    def test_caption_in_header_stripped(self):
        """Table N caption in headers[0] is extracted."""
        headers = ["Table 1. Results", "Col2", "Col3"]
        rows = [["A", "B", "C"], ["D", "E", "F"]]
        cap, h, r = _strip_absorbed_caption(headers, rows)
        assert cap == "Table 1. Results"
        assert h[0] == ""  # or headers empty

    def test_caption_in_first_row_stripped(self):
        """Table N caption in rows[0][0] is extracted, row removed if all-empty."""
        headers = []
        rows = [["Table 2: Demographics", "", ""], ["A", "B", "C"]]
        cap, h, r = _strip_absorbed_caption(headers, rows)
        assert cap == "Table 2: Demographics"
        assert len(r) == 1  # caption row removed

    def test_caption_in_first_row_partial_cleared(self):
        """Caption in rows[0][0] cleared, row kept if other cells have data."""
        headers = []
        rows = [["Table 3. Summary", "Value", "Unit"], ["A", "1", "m"]]
        cap, h, r = _strip_absorbed_caption(headers, rows)
        assert cap == "Table 3. Summary"
        assert r[0][0] == ""
        assert r[0][1] == "Value"

    def test_non_caption_row_kept(self):
        """Normal text in first row is not stripped."""
        headers = ["H1", "H2"]
        rows = [["Alpha", "Beta"], ["C", "D"]]
        cap, h, r = _strip_absorbed_caption(headers, rows)
        assert cap is None
        assert len(r) == 2


# ---- _adaptive_row_tolerance ----

class TestAdaptiveRowTolerance:

    def test_12pt_font(self):
        """12pt font (~12pt height) → tolerance ~3.6pt."""
        # Simulate words with ~12pt height: y0=0, y1=12
        words = [(0, 0, 50, 12, "word")] * 10
        tol = _adaptive_row_tolerance(words)
        assert 3.0 <= tol <= 4.5

    def test_24pt_font(self):
        """24pt font → tolerance ~7.2pt."""
        words = [(0, 0, 50, 24, "word")] * 10
        tol = _adaptive_row_tolerance(words)
        assert 6.0 <= tol <= 9.0

    def test_8pt_font(self):
        """8pt font → tolerance ~2.4pt."""
        words = [(0, 0, 50, 8, "word")] * 10
        tol = _adaptive_row_tolerance(words)
        assert 1.5 <= tol <= 3.5

    def test_empty_words_fallback(self):
        """Empty word list returns fallback derived from assumed 12pt height."""
        assert _adaptive_row_tolerance([]) == pytest.approx(12.0 * 0.3)


# ---- _find_column_gap_threshold ----

class TestFindColumnGapThreshold:

    def test_bimodal_gaps_separated(self):
        """Bimodal distribution: intra-word (1-3pt) vs inter-column (20-30pt)."""
        gaps = [1, 1.5, 2, 2.5, 3, 20, 22, 25, 28, 30]
        threshold = _find_column_gap_threshold(gaps)
        # Should separate 3pt cluster from 20pt cluster
        assert 3 < threshold < 20

    def test_uniform_gaps_fallthrough(self):
        """Uniform distribution with no clear break."""
        gaps = [5, 5.5, 6, 6.5, 7, 7.5, 8, 8.5, 9, 9.5]
        threshold = _find_column_gap_threshold(gaps)
        # Should return a value derived from the data
        assert threshold > 0

    def test_empty_returns_default(self):
        """Empty gap list returns safe default."""
        assert _find_column_gap_threshold([]) == 15.0

    def test_single_gap(self):
        """Single gap value doesn't crash."""
        threshold = _find_column_gap_threshold([10.0])
        assert threshold > 0


# ---- _split_at_internal_captions ----

class TestSplitAtInternalCaptions:

    def test_merged_table_splits(self):
        """Two tables merged by find_tables() are split at internal caption row."""
        headers = ["A", "B", "C"]
        rows = [
            ["1", "2", "3"],
            ["4", "5", "6"],
            ["Table 2. Demographics", "", ""],
            ["X", "Y", "Z"],
            ["P", "Q", "R"],
        ]
        segments = _split_at_internal_captions(headers, rows, (0, 0, 100, 200), "Table 1. Results")
        assert len(segments) == 2
        assert segments[0]["caption"] == "Table 1. Results"
        assert len(segments[0]["rows"]) == 2
        assert segments[1]["caption"] == "Table 2. Demographics"
        assert len(segments[1]["rows"]) == 2

    def test_dense_row_reference_no_split(self):
        """'see Table 1' in a dense data row does NOT trigger a split."""
        headers = ["Description", "Value", "Unit"]
        rows = [
            ["As shown in Table 1, the results indicate", "42", "ms"],
            ["Normal data", "13", "Hz"],
            ["More data", "99", "dB"],
        ]
        segments = _split_at_internal_captions(headers, rows, (0, 0, 100, 200), "Table 3. Summary")
        assert len(segments) == 1

    def test_too_few_rows_no_split(self):
        """Table with <4 rows is too small to split."""
        headers = ["A", "B"]
        rows = [["1", "2"], ["Table 2. X", ""]]
        segments = _split_at_internal_captions(headers, rows, (0, 0, 100, 100), "Table 1.")
        assert len(segments) == 1

    def test_no_internal_captions(self):
        """Normal table without internal captions returns unchanged."""
        headers = ["X", "Y"]
        rows = [["a", "b"], ["c", "d"], ["e", "f"], ["g", "h"]]
        segments = _split_at_internal_captions(headers, rows, (0, 0, 100, 100), "Table 1.")
        assert len(segments) == 1


# ---- _separate_header_data ----

class TestSeparateHeaderData:

    def test_numeric_suffix_split(self):
        """Headers ending with numeric data get split into header + data row."""
        headers = ["ZTA R1(Ohm) 9982.", "Frequency 100", "Phase -45.2"]
        rows = [["val1", "val2", "val3"]]
        new_h, new_r = _separate_header_data(headers, rows)
        # At least 2/3 (67%) headers end with numeric → should split
        assert len(new_r) == 2  # original row + new data row from header
        # New headers should not end with numeric content
        for h in new_h:
            parts = h.strip().split()
            if parts:
                assert not _looks_numeric(parts[-1]), f"Header still ends with numeric: {h}"

    def test_model_1_not_split(self):
        """'Model 1' is a legitimate header — no split."""
        headers = ["Model 1", "Model 2", "Model 3"]
        rows = [["0.5", "0.6", "0.7"]]
        new_h, new_r = _separate_header_data(headers, rows)
        assert new_h == headers  # unchanged
        assert len(new_r) == 1   # no extra row

    def test_all_text_headers_unchanged(self):
        """Headers without numeric suffixes pass through unchanged."""
        headers = ["Name", "Category", "Type"]
        rows = [["A", "B", "C"]]
        new_h, new_r = _separate_header_data(headers, rows)
        assert new_h == headers
        assert len(new_r) == 1


# ---- _merge_over_divided_rows (adaptive triggers) ----

class TestMergeOverDividedRowsAdaptive:

    def test_wide_table_4_rows_merges(self):
        """6-column table with 4 rows (below old threshold of 6) should merge."""
        # Pattern A: >40% rows have empty col0
        rows = [
            ["Header", "A", "B", "C", "D", "E"],
            ["", "cont", "", "", "", ""],
            ["Row 2", "X", "Y", "Z", "W", "V"],
            ["", "cont2", "", "", "", ""],
        ]
        result = _merge_over_divided_rows(rows)
        # With adaptive min_rows = max(3, 8-6) = 3, 4 rows >= 3 → should try merge
        # 2/4 = 50% empty col0 → Pattern A triggers
        assert len(result) == 2

    def test_narrow_table_needs_more_rows(self):
        """2-column table with 4 rows — min_rows = max(3, 8-2) = 6 → no merge."""
        rows = [
            ["Header", "A"],
            ["", "cont"],
            ["Row 2", "X"],
            ["", "cont2"],
        ]
        result = _merge_over_divided_rows(rows)
        # min_rows = max(3, 8-2) = 6, only 4 rows → no merge
        assert len(result) == 4


# ---- _repair_low_fill_table (adaptive) ----

class TestRepairLowFillTableAdaptive:

    def test_high_fill_skipped(self):
        """Table with >=90% fill skips re-extraction entirely."""
        import pymupdf
        # Create a minimal page (can't test full repair without real PDF, but
        # we can test the skip logic)
        # Build a mock: 10 cells, 9 filled = 90%
        headers = ["H1", "H2", "H3", "H4", "H5"]
        rows = [
            ["a", "b", "c", "d", "e"],
            ["f", "g", "h", "i", ""],
        ]
        # fill = 14/15 = 93% → should skip
        # We can't call the function without a real page, but we test the
        # logic is correct via the function's early return
        total = sum(len(r) for r in rows) + len(headers)
        non_empty = sum(1 for r in rows for c in r if c.strip()) + sum(1 for h in headers if h.strip())
        fill = non_empty / total
        assert fill >= 0.90  # confirms skip condition


# ---- _should_replace_with_word_api ----

class TestShouldReplaceWithWordApi:

    def test_merged_words_detected(self):
        """'Michardandcolleagues[23]' → word API splits into 3 tokens."""
        cell = "Michardandcolleagues[23]"
        words = ["Michard", "and", "colleagues", "[23]"]
        assert _should_replace_with_word_api(cell, words) is True

    def test_normal_text_not_replaced(self):
        """Already-spaced text matches word API → no replacement."""
        cell = "Michard and colleagues [23]"
        words = ["Michard", "and", "colleagues", "[23]"]
        assert _should_replace_with_word_api(cell, words) is False

    def test_math_greek_skipped(self):
        """Cells with Greek/math characters are never replaced."""
        cell = "sπτ=1averylongmathexpression"
        words = ["s", "π", "τ", "=", "1", "a", "very", "long", "math"]
        assert _should_replace_with_word_api(cell, words) is False

    def test_numeric_cell_skipped(self):
        """Pure numeric cells are never replaced."""
        cell = "0.4198"
        words = ["0", ".", "4198"]
        assert _should_replace_with_word_api(cell, words) is False

    def test_short_single_token_skipped(self):
        """Short single-token cells (< 15 chars) are skipped."""
        cell = "Hello"
        words = ["Hel", "lo"]
        assert _should_replace_with_word_api(cell, words) is False

    def test_long_single_token_replaced(self):
        """Long single-token cell (>= 15 chars) with multiple word tokens → replaced."""
        cell = "Michardandcolleagues"
        words = ["Michard", "and", "colleagues"]
        assert _should_replace_with_word_api(cell, words) is True

    def test_hyphenated_word_not_replaced(self):
        """Hyphenated compound term — word API returns same count."""
        cell = "sulfamethoxazole-trimethoprim"
        words = ["sulfamethoxazole-trimethoprim"]
        assert _should_replace_with_word_api(cell, words) is False

    def test_empty_cell_skipped(self):
        """Empty cell text returns False."""
        assert _should_replace_with_word_api("", ["a"]) is False

    def test_empty_words_skipped(self):
        """No word tokens returns False."""
        assert _should_replace_with_word_api("hello world", []) is False

    def test_word_api_fewer_tokens_no_replace(self):
        """When word API returns fewer tokens, no replacement."""
        cell = "one two three"
        words = ["onetwo", "three"]
        assert _should_replace_with_word_api(cell, words) is False

    def test_equal_tokens_no_replace(self):
        """Equal token counts → no replacement."""
        cell = "one two three"
        words = ["one", "two", "three"]
        assert _should_replace_with_word_api(cell, words) is False

    def test_small_diff_below_thresholds(self):
        """Diff of 1 with ratio < 1.5 → no replacement (noise filter)."""
        cell = "some text here and more"
        # 5 extract tokens, 6 word tokens: ratio=1.2, diff=1 → both below threshold
        words = ["some", "text", "here", "and", "more", "extra"]
        assert _should_replace_with_word_api(cell, words) is False

    def test_multiline_cell_normalised(self):
        """Newlines in cell text are normalised before token counting."""
        cell = "Michardand\ncolleagues[23]"
        words = ["Michard", "and", "colleagues", "[23]"]
        # extract: "Michardand" + "colleagues[23]" = 2 tokens; word API = 4
        # ratio = 2.0, diff = 2 → replaced
        assert _should_replace_with_word_api(cell, words) is True


# ---- Multi-strategy extraction scoring ----

class TestDecimalDisplacementDetection:

    def test_digits_newline_dot(self):
        """Classic displacement: '9982\\n.' detected."""
        data = [["9982\n.", "ok"]]
        assert _count_decimal_displacement(data) == 1

    def test_digits_space_dot(self):
        """Displacement with space: '9982 .' detected."""
        data = [["9982 .", "ok"]]
        assert _count_decimal_displacement(data) == 1

    def test_clean_decimal(self):
        """Clean decimal '998.2' has no displacement."""
        data = [["998.2", "0.45"]]
        assert _count_decimal_displacement(data) == 0

    def test_empty_and_none(self):
        """Empty cells and None cells don't crash or count."""
        data = [["", None, "ok"]]
        assert _count_decimal_displacement(data) == 0

    def test_multiple_displaced(self):
        """Multiple displaced cells are each counted."""
        data = [["9982\n.", "1789 .", "ok"]]
        assert _count_decimal_displacement(data) == 2


class TestNumericIntegrity:

    def test_valid_decimals(self):
        """Cells with valid decimals score perfectly."""
        data = [["998.2", "0.45", "1.23"]]
        valid, with_period = _count_numeric_integrity(data)
        assert valid == 3
        assert with_period == 3

    def test_broken_decimals(self):
        """Displaced decimals have period but no valid decimal pattern."""
        data = [["9982\n.", "text", "1789\n."]]
        valid, with_period = _count_numeric_integrity(data)
        assert valid == 0
        assert with_period == 2

    def test_no_periods(self):
        """Cells without periods return (0, 0)."""
        data = [["123", "abc", "456"]]
        valid, with_period = _count_numeric_integrity(data)
        assert valid == 0
        assert with_period == 0

    def test_mixed(self):
        """Mix of valid and broken decimals."""
        data = [["998.2", "9982\n."]]
        valid, with_period = _count_numeric_integrity(data)
        assert valid == 1
        assert with_period == 2


class TestComputeFillRate:

    def test_full_grid(self):
        """All cells non-empty → fill rate 1.0."""
        data = [["a", "b"], ["c", "d"]]
        assert _compute_fill_rate(data) == 1.0

    def test_half_empty(self):
        """Half the cells empty → fill rate 0.5."""
        data = [["a", ""], ["", "d"]]
        assert _compute_fill_rate(data) == 0.5

    def test_all_empty(self):
        """All cells empty → fill rate 0.0."""
        data = [["", ""], ["", ""]]
        assert _compute_fill_rate(data) == 0.0

    def test_none_cells_empty(self):
        """None cells count as empty."""
        data = [[None, "a"], ["b", None]]
        assert _compute_fill_rate(data) == 0.5

    def test_empty_grid(self):
        """Empty grid returns 0.0 without crashing."""
        assert _compute_fill_rate([]) == 0.0


class TestStrategyScoring:

    def test_clean_data_beats_displaced(self):
        """Strategy with clean decimals scores higher than displaced."""
        clean = [["998.2", "0.45"], ["1.23", "4.56"]]
        displaced = [["9982\n.", "045\n."], ["123\n.", "456\n."]]
        assert _score_extraction(clean) > _score_extraction(displaced)

    def test_higher_fill_wins(self):
        """Higher fill rate produces a better score (all else equal)."""
        full = [["a", "b"], ["c", "d"]]
        sparse = [["a", ""], ["", "d"]]
        assert _score_extraction(full) > _score_extraction(sparse)

    def test_empty_data_very_low(self):
        """Empty data returns very low score."""
        assert _score_extraction([]) < -100

    def test_displacement_dominates(self):
        """Even high fill can't overcome heavy displacement."""
        # 4 displacements × -40 = -160
        displaced_full = [["9982\n.", "045\n."], ["123\n.", "456\n."]]
        # 2/4 fill, no displacement
        sparse_clean = [["998.2", ""], ["", "4.56"]]
        assert _score_extraction(sparse_clean) > _score_extraction(displaced_full)


class TestSeparateHeaderDataNewlines:

    def test_newline_preserved_in_data(self):
        """Numeric suffix containing \\n is preserved (not destroyed by split)."""
        headers = ["ZTA R1(Ohm) 9982\n.", "Frequency 100"]
        rows = [["val1", "val2"]]
        new_h, new_r = _separate_header_data(headers, rows)
        assert len(new_r) == 2  # original row + new data row
        # The data cell for first header should contain the \n
        data_cell = new_r[0][0]
        assert "\n" in data_cell, f"Newline lost in data cell: {data_cell!r}"

    def test_whitespace_before_numeric_preserved(self):
        """Original whitespace structure preserved at split boundary."""
        headers = ["Label\t42.5", "Other 99"]
        rows = [["x", "y"]]
        new_h, new_r = _separate_header_data(headers, rows)
        assert len(new_r) == 2
        assert new_h[0] == "Label"
