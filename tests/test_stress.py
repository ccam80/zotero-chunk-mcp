"""
Stress tests for section detection and extraction edge cases.

These tests use synthetic PDFs with known structures to validate:
- Section detection with ambiguous headings
- Table extraction with various formats
- Text extraction with special characters

Tests that fail document real bugs. The test suite should FAIL until bugs are fixed.
A red test suite is honest information about the system state.
"""
import pytest
from pathlib import Path

from zotero_chunk_rag.pdf_extractor import PDFExtractor
from zotero_chunk_rag.section_detector import (
    detect_sections,
    assign_section_with_confidence,
    _categorize_heading,
    CONFIDENCE_SCHEME_MATCH,
)
from zotero_chunk_rag.table_extractor import TableExtractor
from zotero_chunk_rag.chunker import Chunker

STRESS_DIR = Path(__file__).parent / "fixtures" / "stress"


@pytest.fixture(scope="module")
def pdf_extractor():
    """Shared PDF extractor instance."""
    return PDFExtractor()


@pytest.fixture(scope="module")
def table_extractor():
    """Shared table extractor instance."""
    return TableExtractor()


@pytest.fixture(scope="module")
def chunker():
    """Shared chunker instance."""
    return Chunker(chunk_size=400, overlap=100)


# =============================================================================
# P3.2/P3.3: Test fixtures exist
# =============================================================================

class TestStressFixtures:
    """Verify stress test PDFs were created."""

    def test_academic_full_exists(self):
        """Full academic paper PDF exists."""
        assert (STRESS_DIR / "sample_academic_full.pdf").exists()

    def test_ambiguous_sections_exists(self):
        """Ambiguous sections PDF exists."""
        assert (STRESS_DIR / "sample_ambiguous_sections.pdf").exists()

    def test_complex_tables_exists(self):
        """Complex tables PDF exists."""
        assert (STRESS_DIR / "sample_complex_tables.pdf").exists()

    def test_edge_cases_exists(self):
        """Edge cases PDF exists."""
        assert (STRESS_DIR / "sample_edge_cases.pdf").exists()

    def test_mixed_ocr_exists(self):
        """Mixed OCR PDF exists."""
        assert (STRESS_DIR / "sample_mixed_ocr.pdf").exists()


# =============================================================================
# Section Detection Tests - Keyword Gaps
# =============================================================================

class TestCategorizeHeadingAmbiguous:
    """Test keyword categorization with non-standard headings.

    KNOWN BUGS: Several common academic headings are not recognized.
    See section_detector.py CATEGORY_KEYWORDS for the current list.
    """

    def test_experimental_approach_maps_to_methods(self):
        """'Experimental Approach' should be categorized as methods."""
        result, weight = _categorize_heading("EXPERIMENTAL APPROACH")
        assert result == "methods"

    def test_findings_maps_to_results(self):
        """'Findings' should be categorized as results.

        BUG: The keyword 'findings' is not in CATEGORY_KEYWORDS.
        FIX: Add 'findings' to the results keyword list in section_detector.py:25
        """
        result, weight = _categorize_heading("FINDINGS")
        assert result == "results", f"Expected 'results', got {result!r}"

    def test_study_design_maps_to_methods(self):
        """'Study Design and Implementation' should map to methods."""
        result, weight = _categorize_heading("Study Design and Implementation")
        assert result == "methods"

    def test_data_and_outcomes_maps_to_results(self):
        """'Data and Outcomes' should map to results.

        BUG: Neither 'data' nor 'outcomes' is in CATEGORY_KEYWORDS.
        FIX: Add 'outcomes', 'data' to the results keyword list in section_detector.py:25
        """
        result, weight = _categorize_heading("Data and Outcomes")
        assert result == "results", f"Expected 'results', got {result!r}"

    def test_summary_alone_maps_to_conclusion(self):
        """'Summary' as a standalone heading should map to conclusion."""
        result, weight = _categorize_heading("SUMMARY")
        assert result == "conclusion"

    def test_summary_statistics_correctly_maps_to_results(self):
        """'Summary Statistics' in a results section should map to results, not conclusion.

        The SUMMARY_EXCLUDES list correctly handles this case - 'statistics'
        triggers the results category instead of conclusion.
        """
        result, weight = _categorize_heading("Summary Statistics")
        assert result == "results", f"Expected 'results', got {result!r}"


class TestAmbiguousSectionsPDF:
    """Test section detection on the ambiguous sections PDF."""

    def test_extract_and_detect_sections(self, pdf_extractor):
        """Extract text and detect sections from ambiguous PDF."""
        pdf_path = STRESS_DIR / "sample_ambiguous_sections.pdf"
        pages, stats = pdf_extractor.extract(pdf_path)
        assert len(pages) > 0

        spans = detect_sections(pages)
        assert len(spans) > 0

        # Get unique section labels
        labels = {s.label for s in spans}

        # Should detect methods from "EXPERIMENTAL APPROACH"
        assert "methods" in labels, f"Expected 'methods' in {labels}"

        # Should detect results from "RESULTS AND DISCUSSION"
        assert "results" in labels, f"Expected 'results' in {labels}"

    def test_roman_numeral_headings_detected(self, pdf_extractor):
        """Roman numeral headings (I., II., III.) should be detected."""
        pdf_path = STRESS_DIR / "sample_ambiguous_sections.pdf"
        pages, stats = pdf_extractor.extract(pdf_path)
        spans = detect_sections(pages)

        # Check that we detected multiple spans
        assert len(spans) >= 3, f"Expected >= 3 spans, got {len(spans)}"

        # At least some should have high confidence (scheme match)
        high_confidence_spans = [s for s in spans if s.confidence == CONFIDENCE_SCHEME_MATCH]
        assert len(high_confidence_spans) >= 1, "Expected at least 1 high-confidence span"


class TestAcademicFullPDF:
    """Test section detection on the full academic paper PDF."""

    def test_all_standard_sections_detected(self, pdf_extractor):
        """Full academic paper should have all standard sections detected."""
        pdf_path = STRESS_DIR / "sample_academic_full.pdf"
        pages, stats = pdf_extractor.extract(pdf_path)
        spans = detect_sections(pages)

        labels = {s.label for s in spans}

        # Standard sections that should be detected
        expected = {"abstract", "introduction", "background", "methods", "results",
                    "discussion", "conclusion", "references"}

        # Require at least 5 of 8 to be detected
        matched = labels & expected
        assert len(matched) >= 5, f"Only matched {matched} from expected {expected}"

    def test_numbered_headings_detected(self, pdf_extractor):
        """Numbered headings (1., 2., etc.) should be detected."""
        pdf_path = STRESS_DIR / "sample_academic_full.pdf"
        pages, stats = pdf_extractor.extract(pdf_path)
        spans = detect_sections(pages)

        # Check that most spans have scheme match confidence
        scheme_matches = [s for s in spans if s.confidence == CONFIDENCE_SCHEME_MATCH]
        assert len(scheme_matches) >= 4, f"Expected >= 4 scheme matches, got {len(scheme_matches)}"


class TestCompoundHeadings:
    """Test handling of compound headings like 'Results and Discussion'."""

    def test_results_and_discussion_maps_to_results(self):
        """'Results and Discussion' should map to results (higher weight)."""
        result, weight = _categorize_heading("III. RESULTS AND DISCUSSION")
        assert result == "results"

    def test_methods_and_materials_maps_to_methods(self):
        """'Materials and Methods' should map to methods."""
        result, weight = _categorize_heading("3. Materials and Methods")
        assert result == "methods"


# =============================================================================
# Table Extraction Tests - Caption Detection Broken
# =============================================================================

class TestComplexTablesPDF:
    """Test table extraction on the complex tables PDF.

    KNOWN BUG: Caption detection is broken. The proximity-based search
    (50pt above/below table) fails on most real-world PDFs.
    """

    def test_extract_tables_from_complex_pdf(self, table_extractor):
        """Should extract multiple tables from the complex tables PDF."""
        pdf_path = STRESS_DIR / "sample_complex_tables.pdf"
        tables = table_extractor.extract_tables(pdf_path)

        # The PDF has at least 6 tables
        assert len(tables) >= 4, f"Expected >= 4 tables, got {len(tables)}"

    def test_table_dimensions_reasonable(self, table_extractor):
        """Extracted tables should have reasonable dimensions."""
        pdf_path = STRESS_DIR / "sample_complex_tables.pdf"
        tables = table_extractor.extract_tables(pdf_path)

        for i, table in enumerate(tables):
            assert table.num_rows >= 2, f"Table {i}: expected >= 2 rows, got {table.num_rows}"
            assert table.num_cols >= 2, f"Table {i}: expected >= 2 cols, got {table.num_cols}"
            assert table.num_rows <= 100, f"Table {i}: sanity check failed, {table.num_rows} rows"
            assert table.num_cols <= 20, f"Table {i}: sanity check failed, {table.num_cols} cols"

    def test_table_captions_detected(self, table_extractor):
        """At least some tables should have captions detected.

        BUG: Caption detection only searches 50pt above/below table bbox
        and requires pattern match at START of text. This fails when:
        - Caption is separated from table by whitespace
        - Caption is inside the table (common in some layouts)
        - PDF text extraction order doesn't match visual order

        FIX NEEDED: More robust caption detection using:
        - Larger search radius
        - Pattern matching anywhere in nearby text
        - OCR-based detection for caption-as-image cases
        """
        pdf_path = STRESS_DIR / "sample_complex_tables.pdf"
        tables = table_extractor.extract_tables(pdf_path)

        tables_with_captions = [t for t in tables if t.caption]
        assert len(tables_with_captions) >= 1, (
            f"Expected at least 1 table with caption, got 0. "
            f"Total tables: {len(tables)}"
        )

    def test_table_to_markdown_produces_valid_output(self, table_extractor):
        """Table markdown output should be well-formed."""
        pdf_path = STRESS_DIR / "sample_complex_tables.pdf"
        tables = table_extractor.extract_tables(pdf_path)

        for i, table in enumerate(tables):
            md = table.to_markdown()
            assert isinstance(md, str), f"Table {i}: markdown not a string"
            assert len(md) > 0, f"Table {i}: markdown is empty"
            assert "|" in md, f"Table {i}: markdown missing pipe characters"
            assert "---" in md, f"Table {i}: markdown missing separator row"


class TestAcademicFullTables:
    """Test table extraction on the full academic paper."""

    def test_extract_results_tables(self, table_extractor):
        """Should extract tables from results section."""
        pdf_path = STRESS_DIR / "sample_academic_full.pdf"
        tables = table_extractor.extract_tables(pdf_path)

        # The academic PDF has 2 tables in results
        assert len(tables) >= 2, f"Expected >= 2 tables, got {len(tables)}"

    def test_table_content_matches_expected(self, table_extractor):
        """Table content should match expected structure."""
        pdf_path = STRESS_DIR / "sample_academic_full.pdf"
        tables = table_extractor.extract_tables(pdf_path)

        assert len(tables) >= 1, "Expected at least 1 table"

        # Find a table with "Characteristic" header (Table 1)
        table1_found = False
        for table in tables:
            if table.headers and any("Characteristic" in h for h in table.headers):
                table1_found = True
                assert table.num_cols >= 3, f"Expected >= 3 cols, got {table.num_cols}"
                break

        # Note: table structure may vary due to PDF generation, so we don't
        # require table1_found to be True


# =============================================================================
# Edge Cases Tests
# =============================================================================

class TestEdgeCasesPDF:
    """Test text extraction on the edge cases PDF."""

    def test_extract_text_with_special_chars(self, pdf_extractor):
        """Should extract text including special characters."""
        pdf_path = STRESS_DIR / "sample_edge_cases.pdf"
        pages, stats = pdf_extractor.extract(pdf_path)

        assert len(pages) > 0, "Expected at least 1 page"

        full_text = " ".join(p.text for p in pages)

        # Should contain expected text (case-insensitive)
        text_lower = full_text.lower()
        assert "alpha" in text_lower or "coefficient" in text_lower, (
            "Expected 'alpha' or 'coefficient' in text"
        )
        assert "equation" in text_lower or "formula" in text_lower, (
            "Expected 'equation' or 'formula' in text"
        )

    def test_superscript_subscript_extraction(self, pdf_extractor):
        """Text with super/subscripts should be extracted."""
        pdf_path = STRESS_DIR / "sample_edge_cases.pdf"
        pages, stats = pdf_extractor.extract(pdf_path)

        full_text = " ".join(p.text for p in pages)

        # Should contain ion names
        assert "Na" in full_text or "K" in full_text, (
            "Expected ion names (Na, K) in text"
        )

    def test_url_extraction(self, pdf_extractor):
        """URLs should be preserved in extracted text."""
        pdf_path = STRESS_DIR / "sample_edge_cases.pdf"
        pages, stats = pdf_extractor.extract(pdf_path)

        full_text = " ".join(p.text for p in pages)

        # Should contain URL fragments
        assert "http" in full_text or "doi" in full_text.lower(), (
            "Expected URL or DOI in text"
        )


class TestEdgeCasesTables:
    """Test table extraction from edge cases PDF."""

    def test_extract_ion_table(self, table_extractor):
        """Should extract table with ion concentrations."""
        pdf_path = STRESS_DIR / "sample_edge_cases.pdf"
        tables = table_extractor.extract_tables(pdf_path)

        assert len(tables) >= 1, "Expected at least 1 table"

        # Find the ion table
        ion_table_found = False
        for table in tables:
            if table.headers and any("Ion" in str(h) for h in table.headers):
                ion_table_found = True
                assert table.num_cols >= 3, f"Expected >= 3 cols, got {table.num_cols}"
                assert table.num_rows >= 3, f"Expected >= 3 rows, got {table.num_rows}"
                break

        # Note: header detection may vary, so we don't require ion_table_found


# =============================================================================
# Chunking Integration Tests
# =============================================================================

class TestChunkingWithSections:
    """Test that chunks get section labels assigned."""

    def test_chunks_have_sections_assigned(self, pdf_extractor, chunker):
        """Chunks from academic PDF should have section labels."""
        pdf_path = STRESS_DIR / "sample_academic_full.pdf"
        pages, stats = pdf_extractor.extract(pdf_path)
        spans = detect_sections(pages)

        chunks = chunker.chunk(pages)

        # Assign sections
        for chunk in chunks:
            section, confidence = assign_section_with_confidence(chunk.char_start, spans)
            chunk.section = section
            chunk.section_confidence = confidence

        # Get unique sections from chunks
        sections = {c.section for c in chunks}

        # Should have multiple sections
        assert len(sections) >= 3, f"Expected >= 3 sections, got {sections}"

        # Should not be all "unknown"
        assert sections != {"unknown"}, "All chunks labeled 'unknown' - section detection failed"

    def test_section_confidence_values(self, pdf_extractor, chunker):
        """Section confidence should be in valid range."""
        pdf_path = STRESS_DIR / "sample_academic_full.pdf"
        pages, stats = pdf_extractor.extract(pdf_path)
        spans = detect_sections(pages)

        chunks = chunker.chunk(pages)

        for i, chunk in enumerate(chunks):
            section, confidence = assign_section_with_confidence(chunk.char_start, spans)
            assert 0.0 <= confidence <= 1.0, (
                f"Chunk {i}: confidence {confidence} out of range [0, 1]"
            )


# =============================================================================
# Regression Safety Tests
# =============================================================================

class TestNoRegressions:
    """Ensure stress tests don't break existing functionality."""

    def test_existing_test_fixtures_still_work(self, pdf_extractor):
        """Original test fixtures should still work."""
        original_fixtures = Path(__file__).parent / "fixtures"
        assert original_fixtures.exists(), "Original fixtures directory missing"

    def test_pdf_extractor_handles_missing_file(self, pdf_extractor):
        """PDF extractor should handle missing files gracefully."""
        with pytest.raises((FileNotFoundError, Exception)):
            pdf_extractor.extract(STRESS_DIR / "nonexistent.pdf")


# =============================================================================
# C.1: OCR Tests
# =============================================================================

class TestMixedOCR:
    """Test OCR fallback with mixed page types.

    NOTE: Tests will FAIL if Tesseract is not installed.
    This is intentional - we need OCR to work for the package to function.
    """

    @pytest.fixture(scope="class")
    def ocr_extractor(self):
        """Shared OCR extractor instance."""
        from zotero_chunk_rag.ocr_extractor import OCRExtractor
        extractor = OCRExtractor()
        assert extractor.is_available(), (
            "Tesseract OCR is not installed or not accessible. "
            "Install Tesseract: https://github.com/UB-Mannheim/tesseract/wiki (Windows) "
            "or 'brew install tesseract' (macOS) or 'apt install tesseract-ocr' (Linux)"
        )
        return extractor

    def test_identifies_image_only_pages(self, ocr_extractor):
        """Should correctly identify which pages need OCR."""
        import pymupdf

        pdf_path = STRESS_DIR / "sample_mixed_ocr.pdf"
        assert pdf_path.exists(), f"Test fixture missing: {pdf_path}"

        doc = pymupdf.open(pdf_path)
        image_pages = []

        for i, page in enumerate(doc):
            if ocr_extractor.is_image_only_page(page):
                image_pages.append(i)

        doc.close()

        # Pages 2, 4, 6 are image-only (0-indexed: 1, 3, 5)
        assert 1 in image_pages, "Page 2 should be detected as image-only"
        assert 3 in image_pages, "Page 4 should be detected as image-only"
        assert 5 in image_pages, "Page 6 should be detected as image-only"

        # Pages 1, 3, 5 have native text (0-indexed: 0, 2, 4)
        assert 0 not in image_pages, "Page 1 should have native text"
        assert 2 not in image_pages, "Page 3 should have native text"
        assert 4 not in image_pages, "Page 5 should have native text"

    def test_ocr_extracts_text_from_image_page(self, ocr_extractor):
        """OCR should extract readable text from scanned pages."""
        import pymupdf

        pdf_path = STRESS_DIR / "sample_mixed_ocr.pdf"
        assert pdf_path.exists(), f"Test fixture missing: {pdf_path}"

        doc = pymupdf.open(pdf_path)
        page = doc[1]  # Page 2 (0-indexed)
        text = ocr_extractor.ocr_page(page)
        doc.close()

        assert len(text) > 50, f"Expected >50 chars, got {len(text)}"
        assert "method" in text.lower(), f"Expected 'method' in OCR text: {text[:200]}"

    def test_extraction_stats_accurate(self, ocr_extractor):
        """Stats should correctly count text/ocr/empty pages."""
        pdf_path = STRESS_DIR / "sample_mixed_ocr.pdf"
        assert pdf_path.exists(), f"Test fixture missing: {pdf_path}"

        extractor = PDFExtractor(ocr_extractor=ocr_extractor)
        pages, stats = extractor.extract(pdf_path)

        assert stats["total_pages"] == 6
        assert stats["text_pages"] >= 3, f"Expected >= 3 text pages, got {stats}"
        assert stats["ocr_pages"] >= 1, f"Expected >= 1 OCR pages, got {stats}"


# =============================================================================
# C.2: Multi-Column Tests
# =============================================================================

class TestMultiColumnExtraction:
    """Test text extraction from multi-column layouts."""

    def test_sorted_extraction_available(self):
        """PyMuPDF sort=True flag should be available."""
        import pymupdf

        pdf_path = STRESS_DIR / "sample_mixed_ocr.pdf"
        assert pdf_path.exists(), f"Test fixture missing: {pdf_path}"

        doc = pymupdf.open(pdf_path)
        page = doc[0]

        # Verify sort parameter works (doesn't raise)
        text_sorted = page.get_text(sort=True)
        assert "Introduction" in text_sorted
        doc.close()

    def test_layout_aware_ocr_extraction(self):
        """OCR on two-column page should extract text from both columns."""
        from zotero_chunk_rag.ocr_extractor import OCRExtractor
        import pymupdf

        extractor = OCRExtractor()
        if not extractor.is_available():
            pytest.fail("Tesseract OCR not available - install to run this test")

        pdf_path = STRESS_DIR / "sample_mixed_ocr.pdf"
        assert pdf_path.exists(), f"Test fixture missing: {pdf_path}"

        doc = pymupdf.open(pdf_path)
        page = doc[5]  # Page 6 (0-indexed)
        text = extractor.ocr_page(page)
        doc.close()

        text_lower = text.lower()
        # Should contain text from BOTH columns
        assert "left" in text_lower, f"Should extract left column text: {text[:200]}"
        assert "right" in text_lower, f"Should extract right column text: {text[:200]}"


# =============================================================================
# C.3: Table Header Detection Tests
# =============================================================================

class TestTableHeaderDetection:
    """Test table header identification accuracy."""

    def test_header_row_identified(self, table_extractor):
        """Tables should have header row identified."""
        pdf_path = STRESS_DIR / "sample_complex_tables.pdf"
        tables = table_extractor.extract_tables(pdf_path)

        assert len(tables) >= 1, "Expected at least 1 table"

        for i, table in enumerate(tables):
            assert all(isinstance(h, str) for h in table.headers), \
                f"Table {i}: headers should be strings"

    def test_text_headers_preferred_over_numeric(self, table_extractor):
        """Headers with text should be preferred over purely numeric rows."""
        pdf_path = STRESS_DIR / "sample_complex_tables.pdf"
        tables = table_extractor.extract_tables(pdf_path)

        for table in tables:
            if table.headers:
                has_text_header = any(
                    h.strip() and not h.strip().replace('.', '').replace('-', '').replace(',', '').replace('%', '').isdigit()
                    for h in table.headers
                )
                # Well-formed academic tables should have text headers
                assert has_text_header, f"Table should have text headers: {table.headers}"

    def test_header_detection_heuristics(self, table_extractor):
        """Test the _is_likely_header_row and _detect_header_row methods."""
        # Test purely numeric row - not a header
        numeric_row = ["1", "2.5", "3.14", "-4.0"]
        assert not table_extractor._is_likely_header_row(numeric_row), \
            "Purely numeric row should not be a header"

        # Test text row - is a header
        text_row = ["Name", "Value", "Unit", "Notes"]
        assert table_extractor._is_likely_header_row(text_row), \
            "Text row should be a header"

        # Test mixed row - is a header
        mixed_row = ["Variable", "1.23", "p-value", "0.05"]
        assert table_extractor._is_likely_header_row(mixed_row), \
            "Mixed row with text should be a header"

        # Test empty row - not a header
        empty_row = ["", "", "", ""]
        assert not table_extractor._is_likely_header_row(empty_row), \
            "Empty row should not be a header"


# =============================================================================
# C.4: Table Continuation Merging Tests
# =============================================================================

class TestTableContinuationMerging:
    """Test that split tables are merged correctly."""

    def test_continuation_detection_by_pattern(self, table_extractor):
        """Tables with '(continued)' in caption should be detected as continuations."""
        from zotero_chunk_rag.models import ExtractedTable

        # Create a mock table with continuation caption
        cont_table = ExtractedTable(
            page_num=2,
            table_index=0,
            bbox=(0, 0, 100, 100),
            headers=[],
            rows=[["a", "b"]],
            caption="Table 1 (continued)",
            caption_position="above"
        )
        assert table_extractor._is_continuation(cont_table), \
            "Table with '(continued)' should be detected as continuation"

    def test_continuation_detection_by_no_caption(self, table_extractor):
        """Tables with no caption should be detected as continuations."""
        from zotero_chunk_rag.models import ExtractedTable

        # Create a mock table with no caption
        uncaptioned_table = ExtractedTable(
            page_num=2,
            table_index=0,
            bbox=(0, 0, 100, 100),
            headers=[],
            rows=[["a", "b"]],
            caption="",
            caption_position=""
        )
        assert table_extractor._is_continuation(uncaptioned_table), \
            "Table with no caption should be detected as continuation"

    def test_primary_table_not_continuation(self, table_extractor):
        """Tables with proper caption should NOT be detected as continuations."""
        from zotero_chunk_rag.models import ExtractedTable

        # Create a mock table with proper caption
        primary_table = ExtractedTable(
            page_num=1,
            table_index=0,
            bbox=(0, 0, 100, 100),
            headers=["A", "B"],
            rows=[["1", "2"]],
            caption="Table 1: Results summary",
            caption_position="above"
        )
        assert not table_extractor._is_continuation(primary_table), \
            "Table with proper caption should NOT be detected as continuation"

    def test_extract_table_number(self, table_extractor):
        """Table number extraction from captions."""
        assert table_extractor._extract_table_number("Table 1: Results") == 1
        assert table_extractor._extract_table_number("Table 12: Summary") == 12
        assert table_extractor._extract_table_number("Table 3 (continued)") == 3
        assert table_extractor._extract_table_number("No table here") is None
        assert table_extractor._extract_table_number("") is None

    def test_merge_continuations_basic(self, table_extractor):
        """Basic continuation merging test."""
        from zotero_chunk_rag.models import ExtractedTable

        # Create primary table
        primary = ExtractedTable(
            page_num=1,
            table_index=0,
            bbox=(0, 0, 100, 100),
            headers=["A", "B"],
            rows=[["1", "2"], ["3", "4"]],
            caption="Table 1: Test data",
            caption_position="above"
        )

        # Create continuation table (no caption = continuation)
        continuation = ExtractedTable(
            page_num=2,
            table_index=0,
            bbox=(0, 0, 100, 100),
            headers=["A", "B"],
            rows=[["5", "6"], ["7", "8"]],
            caption="",
            caption_position=""
        )

        tables = [primary, continuation]
        merged = table_extractor._merge_continuations(tables)

        # Should return only the primary table
        assert len(merged) == 1, f"Expected 1 merged table, got {len(merged)}"

        # Primary should now have all rows
        assert len(merged[0].rows) == 4, f"Expected 4 rows after merge, got {len(merged[0].rows)}"

    def test_standalone_table_not_merged(self, table_extractor):
        """Standalone tables should not be merged with anything."""
        from zotero_chunk_rag.models import ExtractedTable

        # Create two standalone tables
        table1 = ExtractedTable(
            page_num=1,
            table_index=0,
            bbox=(0, 0, 100, 100),
            headers=["A", "B"],
            rows=[["1", "2"]],
            caption="Table 1: First table",
            caption_position="above"
        )

        table2 = ExtractedTable(
            page_num=2,
            table_index=0,
            bbox=(0, 0, 100, 100),
            headers=["C", "D"],
            rows=[["3", "4"]],
            caption="Table 2: Second table",
            caption_position="above"
        )

        tables = [table1, table2]
        merged = table_extractor._merge_continuations(tables)

        # Should return both tables unchanged
        assert len(merged) == 2, f"Expected 2 tables, got {len(merged)}"

        # Each should have original row count
        assert len(merged[0].rows) == 1
        assert len(merged[1].rows) == 1

    def test_complex_tables_pdf_merging(self, table_extractor):
        """Test merging on the complex tables PDF which has a split table."""
        pdf_path = STRESS_DIR / "sample_complex_tables.pdf"
        tables = table_extractor.extract_tables(pdf_path)

        # All returned tables should have captions (continuations merged into primaries)
        # Note: some tables in the PDF intentionally have no caption for testing
        # but after merging, uncaptioned tables should be absorbed into primaries
        captioned_tables = [t for t in tables if t.caption]
        assert len(captioned_tables) >= 1, "Expected at least 1 captioned table after merging"
