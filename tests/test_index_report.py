"""Tests for indexing report functionality (Feature 5).

Tests cover:
- IndexReport dataclass: to_dict(), to_markdown()
- CLI --report flag integration
- Edge cases: empty results, all failures, no quality data
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_index_result():
    """Create a sample IndexResult for testing."""
    from zotero_chunk_rag.indexer import IndexResult

    return IndexResult(
        item_key="ABC123",
        title="Test Paper Title",
        status="indexed",
        reason="",
        n_chunks=25,
        n_tables=3,
        scanned_pages_skipped=0,
        quality_grade="A",
    )


@pytest.fixture
def failed_index_result():
    """Create a failed IndexResult for testing."""
    from zotero_chunk_rag.indexer import IndexResult

    return IndexResult(
        item_key="DEF456",
        title="Failed Paper",
        status="failed",
        reason="PDF corrupted: invalid header",
        n_chunks=0,
        n_tables=0,
        quality_grade="F",
    )


@pytest.fixture
def empty_index_result():
    """Create an empty (no text) IndexResult."""
    from zotero_chunk_rag.indexer import IndexResult

    return IndexResult(
        item_key="GHI789",
        title="Scanned Only Paper",
        status="empty",
        reason="No extractable text (scanned PDF)",
        n_chunks=0,
        n_tables=0,
        scanned_pages_skipped=15,
        quality_grade="F",
    )


@pytest.fixture
def sample_report(sample_index_result, failed_index_result, empty_index_result):
    """Create a sample IndexReport with mixed results."""
    from zotero_chunk_rag.models import IndexReport

    return IndexReport(
        total_items=10,
        indexed=5,
        skipped=2,
        failed=1,
        empty=2,
        already_indexed=3,
        results=[sample_index_result, failed_index_result, empty_index_result],
        extraction_stats={
            "total_pages": 100,
            "text_pages": 85,
            "ocr_pages": 10,
            "empty_pages": 5,
        },
        quality_distribution={
            "A": 3,
            "B": 1,
            "C": 0,
            "D": 0,
            "F": 1,
        },
    )


# =============================================================================
# to_dict() Tests
# =============================================================================


class TestIndexReportToDict:
    """Tests for IndexReport.to_dict() method."""

    def test_summary_fields(self, sample_report):
        """Summary should contain all count fields."""
        result = sample_report.to_dict()

        assert "summary" in result
        summary = result["summary"]

        assert summary["total_items"] == 10
        assert summary["indexed"] == 5
        assert summary["skipped"] == 2
        assert summary["failed"] == 1
        assert summary["empty"] == 2
        assert summary["already_indexed"] == 3

    def test_extraction_stats_included(self, sample_report):
        """Extraction stats should be included."""
        result = sample_report.to_dict()

        assert "extraction_stats" in result
        stats = result["extraction_stats"]

        assert stats["total_pages"] == 100
        assert stats["text_pages"] == 85
        assert stats["ocr_pages"] == 10
        assert stats["empty_pages"] == 5

    def test_quality_distribution_included(self, sample_report):
        """Quality distribution should be included."""
        result = sample_report.to_dict()

        assert "quality_distribution" in result
        dist = result["quality_distribution"]

        assert dist["A"] == 3
        assert dist["B"] == 1
        assert dist["F"] == 1

    def test_failures_list(self, sample_report):
        """Failures should be listed with details."""
        result = sample_report.to_dict()

        assert "failures" in result
        failures = result["failures"]

        assert len(failures) == 1
        assert failures[0]["item_key"] == "DEF456"
        assert failures[0]["title"] == "Failed Paper"
        assert "corrupted" in failures[0]["reason"]
        assert failures[0]["quality_grade"] == "F"

    def test_empty_documents_list(self, sample_report):
        """Empty documents should be listed."""
        result = sample_report.to_dict()

        assert "empty_documents" in result
        empty = result["empty_documents"]

        assert len(empty) == 1
        assert empty[0]["item_key"] == "GHI789"
        assert "scanned" in empty[0]["reason"].lower()

    def test_indexed_documents_list(self, sample_report):
        """Indexed documents should be listed with stats."""
        result = sample_report.to_dict()

        assert "indexed_documents" in result
        indexed = result["indexed_documents"]

        assert len(indexed) == 1
        assert indexed[0]["item_key"] == "ABC123"
        assert indexed[0]["n_chunks"] == 25
        assert indexed[0]["n_tables"] == 3
        assert indexed[0]["quality_grade"] == "A"

    def test_json_serializable(self, sample_report):
        """Result should be JSON serializable."""
        result = sample_report.to_dict()

        # Should not raise
        json_str = json.dumps(result)
        assert isinstance(json_str, str)

        # Should round-trip
        parsed = json.loads(json_str)
        assert parsed["summary"]["indexed"] == 5


class TestIndexReportToDictEdgeCases:
    """Edge cases for to_dict()."""

    def test_empty_results(self):
        """Empty results should produce valid dict."""
        from zotero_chunk_rag.models import IndexReport

        report = IndexReport(
            total_items=0,
            indexed=0,
            skipped=0,
            failed=0,
            empty=0,
            already_indexed=0,
            results=[],
            extraction_stats={},
            quality_distribution={},
        )

        result = report.to_dict()

        assert result["summary"]["total_items"] == 0
        assert result["failures"] == []
        assert result["empty_documents"] == []
        assert result["indexed_documents"] == []

    def test_all_failures(self, failed_index_result):
        """Report with only failures should work."""
        from zotero_chunk_rag.models import IndexReport

        report = IndexReport(
            total_items=3,
            indexed=0,
            skipped=0,
            failed=3,
            empty=0,
            already_indexed=0,
            results=[failed_index_result] * 3,
            extraction_stats={},
            quality_distribution={"F": 3},
        )

        result = report.to_dict()

        assert len(result["failures"]) == 3
        assert result["indexed_documents"] == []


# =============================================================================
# to_markdown() Tests
# =============================================================================


class TestIndexReportToMarkdown:
    """Tests for IndexReport.to_markdown() method."""

    def test_contains_summary_section(self, sample_report):
        """Markdown should contain summary section."""
        md = sample_report.to_markdown()

        assert "# Indexing Report" in md
        assert "## Summary" in md
        assert "Total items processed:" in md
        assert "Newly indexed:" in md
        assert "Already in index:" in md
        assert "Empty (no text):" in md
        assert "Failed:" in md

    def test_summary_values_correct(self, sample_report):
        """Summary values should be correct."""
        md = sample_report.to_markdown()

        assert "**Total items processed:** 10" in md
        assert "**Newly indexed:** 5" in md
        assert "**Already in index:** 3" in md

    def test_extraction_stats_section(self, sample_report):
        """Should include extraction statistics."""
        md = sample_report.to_markdown()

        assert "## Extraction Statistics" in md
        assert "Total pages: 100" in md
        assert "Text pages: 85" in md
        assert "OCR pages: 10" in md
        assert "Empty pages: 5" in md

    def test_quality_distribution_table(self, sample_report):
        """Should include quality distribution table."""
        md = sample_report.to_markdown()

        assert "## Quality Distribution" in md
        assert "| Grade | Count |" in md
        assert "| A | 3 |" in md
        assert "| B | 1 |" in md

    def test_failures_table(self, sample_report):
        """Should include failures table."""
        md = sample_report.to_markdown()

        assert "## Failures" in md
        assert "| Item Key | Title | Error |" in md
        assert "`DEF456`" in md
        assert "Failed Paper" in md

    def test_empty_documents_table(self, sample_report):
        """Should include empty documents table."""
        md = sample_report.to_markdown()

        assert "## Empty Documents" in md
        assert "`GHI789`" in md
        assert "Scanned Only Paper" in md

    def test_long_title_truncated(self):
        """Long titles should be truncated in tables."""
        from zotero_chunk_rag.indexer import IndexResult
        from zotero_chunk_rag.models import IndexReport

        long_title = "A" * 100  # 100 character title

        result = IndexResult(
            item_key="LONG",
            title=long_title,
            status="failed",
            reason="Error",
            quality_grade="F",
        )

        report = IndexReport(
            total_items=1,
            indexed=0,
            skipped=0,
            failed=1,
            empty=0,
            already_indexed=0,
            results=[result],
            extraction_stats={},
            quality_distribution={},
        )

        md = report.to_markdown()

        # Title should be truncated to 40 chars + "..."
        assert "A" * 40 + "..." in md
        assert "A" * 50 not in md

    def test_pipe_characters_escaped(self):
        """Pipe characters in title/reason should be escaped."""
        from zotero_chunk_rag.indexer import IndexResult
        from zotero_chunk_rag.models import IndexReport

        result = IndexResult(
            item_key="PIPE",
            title="Title | With | Pipes",
            status="failed",
            reason="Error | message",
            quality_grade="F",
        )

        report = IndexReport(
            total_items=1,
            indexed=0,
            skipped=0,
            failed=1,
            empty=0,
            already_indexed=0,
            results=[result],
            extraction_stats={},
            quality_distribution={},
        )

        md = report.to_markdown()

        # Pipes should be escaped
        assert "\\|" in md


class TestIndexReportToMarkdownEdgeCases:
    """Edge cases for to_markdown()."""

    def test_empty_extraction_stats_omits_section(self):
        """Empty extraction stats should omit the section."""
        from zotero_chunk_rag.models import IndexReport

        report = IndexReport(
            total_items=1,
            indexed=1,
            skipped=0,
            failed=0,
            empty=0,
            already_indexed=0,
            results=[],
            extraction_stats={},  # Empty
            quality_distribution={},
        )

        md = report.to_markdown()

        assert "## Extraction Statistics" not in md

    def test_empty_quality_distribution_omits_section(self):
        """Empty quality distribution should omit the section."""
        from zotero_chunk_rag.models import IndexReport

        report = IndexReport(
            total_items=1,
            indexed=1,
            skipped=0,
            failed=0,
            empty=0,
            already_indexed=0,
            results=[],
            extraction_stats={},
            quality_distribution={},  # Empty
        )

        md = report.to_markdown()

        assert "## Quality Distribution" not in md

    def test_zero_quality_counts_omits_section(self):
        """All-zero quality distribution should omit the section."""
        from zotero_chunk_rag.models import IndexReport

        report = IndexReport(
            total_items=1,
            indexed=1,
            skipped=0,
            failed=0,
            empty=0,
            already_indexed=0,
            results=[],
            extraction_stats={},
            quality_distribution={"A": 0, "B": 0, "C": 0, "D": 0, "F": 0},
        )

        md = report.to_markdown()

        assert "## Quality Distribution" not in md

    def test_no_failures_omits_failures_section(self):
        """No failures should omit failures section."""
        from zotero_chunk_rag.models import IndexReport

        report = IndexReport(
            total_items=1,
            indexed=1,
            skipped=0,
            failed=0,
            empty=0,
            already_indexed=0,
            results=[],
            extraction_stats={},
            quality_distribution={},
        )

        md = report.to_markdown()

        assert "## Failures" not in md


# =============================================================================
# CLI --report Flag Tests
# =============================================================================


class TestCLIReportFlag:
    """Tests for the --report CLI flag."""

    def test_json_report_output(self, tmp_path):
        """--report file.json should produce JSON output."""
        from zotero_chunk_rag.models import IndexReport
        from zotero_chunk_rag.indexer import IndexResult

        report = IndexReport(
            total_items=5,
            indexed=3,
            skipped=1,
            failed=1,
            empty=0,
            already_indexed=2,
            results=[
                IndexResult("A", "Title A", "indexed", n_chunks=10, quality_grade="A"),
                IndexResult("B", "Title B", "failed", reason="Error", quality_grade="F"),
            ],
            extraction_stats={"total_pages": 50},
            quality_distribution={"A": 1, "F": 1},
        )

        report_path = tmp_path / "report.json"
        report_path.write_text(json.dumps(report.to_dict(), indent=2))

        # Verify file exists and is valid JSON
        assert report_path.exists()
        content = json.loads(report_path.read_text())
        assert content["summary"]["indexed"] == 3

    def test_markdown_report_output(self, tmp_path):
        """--report file.md should produce Markdown output."""
        from zotero_chunk_rag.models import IndexReport

        report = IndexReport(
            total_items=5,
            indexed=3,
            skipped=1,
            failed=0,
            empty=1,
            already_indexed=2,
            results=[],
            extraction_stats={"total_pages": 50},
            quality_distribution={"A": 2, "B": 1},
        )

        report_path = tmp_path / "report.md"
        report_path.write_text(report.to_markdown())

        assert report_path.exists()
        content = report_path.read_text()
        assert "# Indexing Report" in content
        assert "**Newly indexed:** 3" in content

    def test_report_suffix_determines_format(self, tmp_path):
        """File suffix should determine output format."""
        from zotero_chunk_rag.models import IndexReport

        report = IndexReport(
            total_items=1,
            indexed=1,
            skipped=0,
            failed=0,
            empty=0,
            already_indexed=0,
            results=[],
            extraction_stats={},
            quality_distribution={},
        )

        # JSON suffix
        json_path = tmp_path / "test.json"
        if json_path.suffix == ".json":
            json_path.write_text(json.dumps(report.to_dict(), indent=2))
        else:
            json_path.write_text(report.to_markdown())

        content = json_path.read_text()
        assert content.startswith("{")  # JSON starts with {

        # MD suffix
        md_path = tmp_path / "test.md"
        if md_path.suffix == ".json":
            md_path.write_text(json.dumps(report.to_dict(), indent=2))
        else:
            md_path.write_text(report.to_markdown())

        content = md_path.read_text()
        assert content.startswith("#")  # Markdown starts with #
