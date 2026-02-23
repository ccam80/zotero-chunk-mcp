"""Unit tests for content quality detection functions."""
import pytest

from zotero_chunk_rag.pdf_processor import (
    _detect_garbled_spacing,
    _detect_interleaved_chars,
    _detect_encoding_artifacts,
    _check_content_readability,
    _normalize_ligatures,
    _classify_artifact,
    _parse_prose_rows,
    _find_column_gap_threshold,
    SYNTHETIC_CAPTION_PREFIX,
)
from zotero_chunk_rag.feature_extraction.postprocessors.cell_cleaning import (
    _looks_numeric,
)
from zotero_chunk_rag.feature_extraction.methods._row_clustering import (
    adaptive_row_tolerance as _adaptive_row_tolerance,
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


# ---- _classify_artifact ----

class TestClassifyArtifact:
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
        assert _classify_artifact(table) is not None
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
        assert _classify_artifact(table) is not None
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
        assert _classify_artifact(table) is not None
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
        assert _classify_artifact(table) is not None
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
        assert _classify_artifact(table) is None
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
        assert _classify_artifact(table) is None

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
        assert _classify_artifact(table) is None

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
        assert _classify_artifact(table) is None
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
        assert _classify_artifact(table) is None


# ---- SYNTHETIC_CAPTION_PREFIX ----

class TestSyntheticCaptionPrefix:

    def test_prefix_value(self):
        """Ensure the prefix is stable for downstream checks."""
        assert SYNTHETIC_CAPTION_PREFIX == "Uncaptioned "
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

    def test_empty_returns_inf(self):
        """Empty gap list returns infinity (no column splits possible)."""
        assert _find_column_gap_threshold([]) == float("inf")

    def test_single_gap(self):
        """Single gap value doesn't crash."""
        threshold = _find_column_gap_threshold([10.0])
        assert threshold > 0
