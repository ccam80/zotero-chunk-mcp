"""Tests for table extraction."""
import pytest
from zotero_chunk_rag.models import ExtractedTable
from zotero_chunk_rag.table_extractor import TableExtractor


class TestExtractedTable:
    """Tests for the ExtractedTable dataclass."""

    def test_num_rows(self):
        """num_rows should count data rows only."""
        table = ExtractedTable(
            page_num=1,
            table_index=0,
            bbox=(0, 0, 100, 100),
            headers=["A", "B"],
            rows=[["1", "2"], ["3", "4"], ["5", "6"]],
        )
        assert table.num_rows == 3

    def test_num_cols_from_headers(self):
        """num_cols should use headers when available."""
        table = ExtractedTable(
            page_num=1,
            table_index=0,
            bbox=(0, 0, 100, 100),
            headers=["A", "B", "C"],
            rows=[["1", "2"]],  # Shorter row
        )
        assert table.num_cols == 3

    def test_num_cols_from_rows(self):
        """num_cols should use first row when no headers."""
        table = ExtractedTable(
            page_num=1,
            table_index=0,
            bbox=(0, 0, 100, 100),
            headers=[],
            rows=[["1", "2", "3", "4"]],
        )
        assert table.num_cols == 4

    def test_num_cols_empty(self):
        """num_cols should be 0 for empty table."""
        table = ExtractedTable(
            page_num=1,
            table_index=0,
            bbox=(0, 0, 100, 100),
            headers=[],
            rows=[],
        )
        assert table.num_cols == 0

    def test_to_markdown_basic(self):
        """to_markdown should produce valid markdown table."""
        table = ExtractedTable(
            page_num=1,
            table_index=0,
            bbox=(0, 0, 100, 100),
            headers=["A", "B", "C"],
            rows=[["1", "2", "3"], ["4", "5", "6"]],
        )
        md = table.to_markdown()
        assert "| A | B | C |" in md
        assert "| --- | --- | --- |" in md
        assert "| 1 | 2 | 3 |" in md
        assert "| 4 | 5 | 6 |" in md

    def test_to_markdown_with_caption(self):
        """to_markdown should include caption."""
        table = ExtractedTable(
            page_num=1,
            table_index=0,
            bbox=(0, 0, 100, 100),
            headers=["X"],
            rows=[["Y"]],
            caption="Table 1: Results",
        )
        md = table.to_markdown()
        assert "**Table 1: Results**" in md

    def test_to_markdown_pads_short_rows(self):
        """to_markdown should pad rows shorter than headers."""
        table = ExtractedTable(
            page_num=1,
            table_index=0,
            bbox=(0, 0, 100, 100),
            headers=["A", "B", "C"],
            rows=[["1"]],  # Only one value
        )
        md = table.to_markdown()
        # Row should be padded to 3 columns
        assert "| 1 |  |  |" in md

    def test_to_dict(self):
        """to_dict should return serializable dict."""
        table = ExtractedTable(
            page_num=5,
            table_index=2,
            bbox=(0, 0, 100, 100),
            headers=["Col1"],
            rows=[["Val1"]],
            caption="Test",
        )
        d = table.to_dict()
        assert d["page"] == 5
        assert d["table_index"] == 2
        assert d["headers"] == ["Col1"]
        assert d["rows"] == [["Val1"]]
        assert d["caption"] == "Test"
        assert d["num_rows"] == 1
        assert d["num_cols"] == 1


class TestTableExtractor:
    """Tests for TableExtractor class."""

    def test_init_defaults(self):
        """Should initialize with default values."""
        extractor = TableExtractor()
        assert extractor.min_rows == 2
        assert extractor.min_cols == 2
        assert extractor.caption_search_distance == 50.0

    def test_init_custom_values(self):
        """Should accept custom values."""
        extractor = TableExtractor(
            min_rows=3,
            min_cols=4,
            caption_search_distance=100.0
        )
        assert extractor.min_rows == 3
        assert extractor.min_cols == 4
        assert extractor.caption_search_distance == 100.0

    def test_clean_cell_none(self):
        """_clean_cell should handle None."""
        extractor = TableExtractor()
        assert extractor._clean_cell(None) == ""

    def test_clean_cell_whitespace(self):
        """_clean_cell should normalize whitespace."""
        extractor = TableExtractor()
        assert extractor._clean_cell("  hello  world  ") == "hello world"

    def test_clean_cell_numeric(self):
        """_clean_cell should convert numbers to strings."""
        extractor = TableExtractor()
        assert extractor._clean_cell(123) == "123"
        assert extractor._clean_cell(45.67) == "45.67"

    def test_clean_cell_multiline(self):
        """_clean_cell should collapse newlines."""
        extractor = TableExtractor()
        assert extractor._clean_cell("line1\nline2\tline3") == "line1 line2 line3"

    def test_is_available(self):
        """is_available should return boolean based on PyMuPDF version."""
        result = TableExtractor.is_available()
        assert isinstance(result, bool)


class TestTableExtractorCaptionPatterns:
    """Tests for caption pattern matching."""

    def test_extract_caption_text_single_line(self):
        """Should extract single line caption."""
        extractor = TableExtractor()
        result = extractor._extract_caption_text("Table 1: Results summary")
        assert result == "Table 1: Results summary"

    def test_extract_caption_text_multiline(self):
        """Should extract first paragraph only."""
        extractor = TableExtractor()
        text = "Table 1: Results\n\nThis is body text."
        result = extractor._extract_caption_text(text)
        assert result == "Table 1: Results"

    def test_extract_caption_text_joined_lines(self):
        """Should join consecutive lines."""
        extractor = TableExtractor()
        text = "Table 1: Patient demographics\nand baseline characteristics"
        result = extractor._extract_caption_text(text)
        assert result == "Table 1: Patient demographics and baseline characteristics"


class TestTableContinuationMerging:
    """Tests for table continuation detection and merging (Feature 8).

    These tests verify the improved merging logic:
    - Continuations require consecutive pages (N+1 only)
    - Column count must match for merge
    - Header similarity must be >= 70% if both tables have headers
    - Orphaned continuations kept as standalone with caption=None
    - Same-page uncaptioned tables are NOT merged
    """

    @pytest.fixture
    def extractor(self):
        return TableExtractor()

    def _make_table(
        self,
        page_num: int,
        caption: str | None = "",
        headers: list[str] | None = None,
        rows: list[list[str]] | None = None,
        table_index: int = 0,
    ) -> ExtractedTable:
        """Helper to create test tables."""
        return ExtractedTable(
            page_num=page_num,
            table_index=table_index,
            bbox=(0, 0, 100, 100),
            headers=headers or ["A", "B", "C"],
            rows=rows or [["1", "2", "3"]],
            caption=caption,
            caption_position="above" if caption else "",
        )

    # -------------------------------------------------------------------------
    # Same-page rejection tests
    # -------------------------------------------------------------------------

    def test_same_page_uncaptioned_tables_not_merged(self, extractor):
        """Uncaptioned tables on the SAME page should NOT be merged.

        This is critical: before the fix, any uncaptioned table was
        considered a continuation. Now we require page N+1.
        """
        # Primary table on page 1
        primary = self._make_table(page_num=1, caption="Table 1: Results")

        # Uncaptioned table on SAME page 1 (should NOT merge)
        same_page_uncaptioned = self._make_table(
            page_num=1, caption="", table_index=1
        )

        tables = [primary, same_page_uncaptioned]
        merged = extractor._merge_continuations(tables)

        # Should have 2 tables: primary + orphan
        assert len(merged) == 2, (
            f"Expected 2 tables (same-page uncaptioned should NOT merge), "
            f"got {len(merged)}"
        )

        # Primary should have original row count
        primary_result = next(t for t in merged if t.caption == "Table 1: Results")
        assert len(primary_result.rows) == 1, "Primary should not have merged rows"

        # Orphan should have caption=None
        orphan = next((t for t in merged if t.caption is None), None)
        assert orphan is not None, "Expected an orphan table with caption=None"
        assert orphan.page_num == 1, "Orphan should be from page 1"

    def test_page_gap_prevents_merge(self, extractor):
        """Tables on non-consecutive pages should NOT be merged.

        Continuation must be on page N+1, not N+2 or later.
        """
        primary = self._make_table(page_num=1, caption="Table 1: Data")
        # Gap: page 3 instead of page 2
        continuation = self._make_table(page_num=3, caption="")

        tables = [primary, continuation]
        merged = extractor._merge_continuations(tables)

        assert len(merged) == 2, "Tables with page gap should not merge"
        assert len(merged[0].rows) == 1, "Primary should have original rows only"

    # -------------------------------------------------------------------------
    # Column matching tests
    # -------------------------------------------------------------------------

    def test_column_count_mismatch_prevents_merge(self, extractor):
        """Tables with different column counts should NOT be merged."""
        primary = self._make_table(
            page_num=1,
            caption="Table 1: Three columns",
            headers=["A", "B", "C"],
            rows=[["1", "2", "3"]],
        )
        # Different column count
        continuation = self._make_table(
            page_num=2,
            caption="",
            headers=["X", "Y"],  # Only 2 columns
            rows=[["a", "b"]],
        )

        tables = [primary, continuation]
        merged = extractor._merge_continuations(tables)

        assert len(merged) == 2, "Column mismatch should prevent merge"
        # Primary unchanged
        assert merged[0].num_cols == 3
        assert len(merged[0].rows) == 1

    def test_columns_match_same_count(self, extractor):
        """_columns_match should return True for same column count."""
        primary = self._make_table(page_num=1, headers=["A", "B", "C"])
        continuation = self._make_table(page_num=2, headers=["A", "B", "C"])

        assert extractor._columns_match(primary, continuation) is True

    def test_columns_match_different_count(self, extractor):
        """_columns_match should return False for different column count."""
        primary = self._make_table(page_num=1, headers=["A", "B", "C"])
        continuation = self._make_table(page_num=2, headers=["A", "B"])

        assert extractor._columns_match(primary, continuation) is False

    def test_header_similarity_below_threshold_prevents_merge(self, extractor):
        """Headers with <70% similarity should prevent merge."""
        primary = self._make_table(
            page_num=1,
            caption="Table 1: Patient Data",
            headers=["Patient ID", "Age", "Gender"],
            rows=[["001", "45", "M"]],
        )
        # Same column count but very different headers
        continuation = self._make_table(
            page_num=2,
            caption="",
            headers=["Compound", "Dose", "Response"],  # Completely different
            rows=[["ABC", "10mg", "Positive"]],
        )

        tables = [primary, continuation]
        merged = extractor._merge_continuations(tables)

        # Should NOT merge due to header dissimilarity
        assert len(merged) == 2, "Dissimilar headers should prevent merge"

    def test_header_similarity_above_threshold_allows_merge(self, extractor):
        """Headers with >=70% similarity should allow merge."""
        primary = self._make_table(
            page_num=1,
            caption="Table 1: Results",
            headers=["Subject", "Value", "Notes"],
            rows=[["S1", "100", "OK"]],
        )
        # Similar headers (continuation often has same or very similar headers)
        continuation = self._make_table(
            page_num=2,
            caption="",
            headers=["Subject", "Value", "Notes"],  # Identical
            rows=[["S2", "200", "Good"]],
        )

        tables = [primary, continuation]
        merged = extractor._merge_continuations(tables)

        assert len(merged) == 1, "Similar headers should allow merge"
        assert len(merged[0].rows) == 2, "Rows should be merged"

    # -------------------------------------------------------------------------
    # Orphan handling tests
    # -------------------------------------------------------------------------

    def test_orphan_continuation_gets_caption_none(self, extractor):
        """Orphaned continuation should have caption set to None."""
        # Continuation with no matching primary
        orphan_continuation = self._make_table(
            page_num=5,
            caption="Table 3 (continued)",  # Has continuation marker
        )

        tables = [orphan_continuation]
        merged = extractor._merge_continuations(tables)

        assert len(merged) == 1, "Orphan should be kept as standalone"
        assert merged[0].caption is None, (
            f"Orphan caption should be None, got {merged[0].caption!r}"
        )

    def test_orphan_from_column_mismatch_gets_caption_none(self, extractor):
        """Orphan created by column mismatch should have caption=None."""
        primary = self._make_table(
            page_num=1,
            caption="Table 1: Data",
            headers=["A", "B"],
        )
        # Would match page-wise but columns don't match
        would_be_continuation = self._make_table(
            page_num=2,
            caption="",
            headers=["X", "Y", "Z"],  # 3 cols vs 2
        )

        tables = [primary, would_be_continuation]
        merged = extractor._merge_continuations(tables)

        orphan = next((t for t in merged if t.page_num == 2), None)
        assert orphan is not None, "Orphan should exist"
        assert orphan.caption is None, "Orphan should have caption=None"

    # -------------------------------------------------------------------------
    # Successful merge tests
    # -------------------------------------------------------------------------

    def test_consecutive_page_continuation_merges(self, extractor):
        """Continuation on page N+1 with matching columns should merge."""
        primary = self._make_table(
            page_num=1,
            caption="Table 1: Multi-page data",
            rows=[["row1", "data", "here"]],
        )
        continuation = self._make_table(
            page_num=2,
            caption="",  # Uncaptioned = continuation
            rows=[["row2", "more", "data"], ["row3", "even", "more"]],
        )

        tables = [primary, continuation]
        merged = extractor._merge_continuations(tables)

        assert len(merged) == 1, "Should merge into single table"
        assert len(merged[0].rows) == 3, "All rows should be merged"
        assert merged[0].caption == "Table 1: Multi-page data"

    def test_explicit_continued_caption_merges(self, extractor):
        """Table with '(continued)' in caption should merge."""
        primary = self._make_table(
            page_num=1,
            caption="Table 1: Large dataset",
            rows=[["A", "B", "C"]],
        )
        continuation = self._make_table(
            page_num=2,
            caption="Table 1 (continued)",  # Explicit continuation
            rows=[["D", "E", "F"]],
        )

        tables = [primary, continuation]
        merged = extractor._merge_continuations(tables)

        assert len(merged) == 1, "Explicit continuation should merge"
        assert len(merged[0].rows) == 2

    # -------------------------------------------------------------------------
    # _is_continuation tests
    # -------------------------------------------------------------------------

    def test_is_continuation_no_caption(self, extractor):
        """Table with no caption is a continuation."""
        table = self._make_table(page_num=2, caption="")
        assert extractor._is_continuation(table) is True

    def test_is_continuation_with_continued_keyword(self, extractor):
        """Table with '(continued)' in caption is a continuation."""
        table = self._make_table(page_num=2, caption="Table 1 (continued)")
        assert extractor._is_continuation(table) is True

        table2 = self._make_table(page_num=2, caption="(cont.) Table data")
        assert extractor._is_continuation(table2) is True

    def test_is_continuation_normal_caption_is_not(self, extractor):
        """Table with normal caption is NOT a continuation."""
        table = self._make_table(page_num=2, caption="Table 2: New Results")
        assert extractor._is_continuation(table) is False

    # -------------------------------------------------------------------------
    # _find_matching_primary tests
    # -------------------------------------------------------------------------

    def test_find_matching_primary_consecutive_page(self, extractor):
        """Should find primary on page N when continuation is on N+1."""
        primary = self._make_table(page_num=5, caption="Table 1: Data")
        primaries = {1: primary}  # table_num -> table

        continuation = self._make_table(page_num=6, caption="")

        match = extractor._find_matching_primary(continuation, primaries)
        assert match is primary

    def test_find_matching_primary_no_match_same_page(self, extractor):
        """Should NOT find primary if continuation is on same page."""
        primary = self._make_table(page_num=5, caption="Table 1: Data")
        primaries = {1: primary}

        same_page = self._make_table(page_num=5, caption="")

        match = extractor._find_matching_primary(same_page, primaries)
        assert match is None

    def test_find_matching_primary_no_match_page_gap(self, extractor):
        """Should NOT find primary if there's a page gap."""
        primary = self._make_table(page_num=5, caption="Table 1: Data")
        primaries = {1: primary}

        far_page = self._make_table(page_num=7, caption="")  # Gap of 2

        match = extractor._find_matching_primary(far_page, primaries)
        assert match is None
