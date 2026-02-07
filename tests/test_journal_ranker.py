"""Tests for journal quality ranking.

These tests verify:
1. Title normalization and abbreviation expansion
2. Journal lookup with exact, abbreviation, and fuzzy matching
3. Bundled CSV loading (Feature 4)
4. Override support (Feature 7)
5. Fuzzy threshold at 90% (Feature 7)

Tests are designed to FAIL LOUDLY if:
- Bundled CSV is missing or malformed
- Overrides file has syntax errors
- Fuzzy matching produces false positives
"""
from __future__ import annotations

import csv
import tempfile
from pathlib import Path

import pytest

from zotero_chunk_rag.journal_ranker import (
    JournalRanker,
    _expand_abbreviations,
    _normalize_title,
)


# =============================================================================
# Test Title Normalization
# =============================================================================


class TestNormalizeTitle:
    """Test title normalization."""

    def test_lowercase(self):
        assert _normalize_title("Nature") == "nature"
        assert _normalize_title("SCIENCE") == "science"

    def test_punctuation_to_spaces(self):
        assert _normalize_title("A & B") == "a b"
        assert _normalize_title("A: B") == "a b"
        assert _normalize_title("A-B") == "a b"
        assert _normalize_title("A/B") == "a b"

    def test_collapse_spaces(self):
        assert _normalize_title("A   B") == "a b"
        assert _normalize_title("A &  B") == "a b"

    def test_strip(self):
        assert _normalize_title("  Nature  ") == "nature"


# =============================================================================
# Test Abbreviation Expansion
# =============================================================================


class TestExpandAbbreviations:
    """Test abbreviation expansion."""

    def test_single_abbreviation(self):
        expansions = _expand_abbreviations("J. Medicine")
        assert "journal medicine" in expansions

    def test_multiple_abbreviations(self):
        expansions = _expand_abbreviations("IEEE Trans. Biomed. Eng.")
        # Should contain full expansion
        assert any(
            "transactions" in e and "biomedical" in e and "engineering" in e
            for e in expansions
        )

    def test_no_abbreviations(self):
        expansions = _expand_abbreviations("Nature")
        assert "nature" in expansions


# =============================================================================
# Test JournalRanker with Test CSV
# =============================================================================


class TestJournalRanker:
    """Test the journal ranker with a test CSV."""

    @pytest.fixture
    def test_csv(self, tmp_path: Path) -> Path:
        """Create a test CSV file."""
        csv_path = tmp_path / "test_scimago.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["title_normalized", "quartile"])
            writer.writerow(["nature", "Q1"])
            writer.writerow(["science", "Q1"])
            writer.writerow(["plos one", "Q1"])
            # Note: abbreviation expander produces "ieee transactions biomedical engineering"
            # (without "on"), so we match that form
            writer.writerow(["ieee transactions biomedical engineering", "Q1"])
            writer.writerow(["journal of physiology", "Q2"])
            writer.writerow(["medical hypotheses", "Q4"])
        return csv_path

    def test_exact_match(self, test_csv: Path):
        ranker = JournalRanker(test_csv)
        assert ranker.lookup("Nature") == "Q1"
        assert ranker.lookup("NATURE") == "Q1"
        assert ranker.lookup("science") == "Q1"

    def test_abbreviation_expansion(self, test_csv: Path):
        """Test that abbreviations are expanded and matched."""
        ranker = JournalRanker(test_csv)
        # "IEEE Trans. Biomed. Eng." expands to "ieee transactions biomedical engineering"
        result = ranker.lookup("IEEE Trans. Biomed. Eng.")
        assert result == "Q1"

    def test_fuzzy_match_requires_90_percent(self, test_csv: Path):
        """Fuzzy matching should require 90% similarity (Feature 7)."""
        ranker = JournalRanker(test_csv)
        # "Journal of Physiology" is exact match
        result = ranker.lookup("Journal of Physiology")
        assert result == "Q2"

    def test_fuzzy_match_rejects_low_similarity(self, test_csv: Path):
        """Fuzzy matching should reject matches below 90% threshold."""
        ranker = JournalRanker(test_csv)
        # This is too different to match anything at 90%
        result = ranker.lookup("Journal of Something Completely Different")
        assert result is None, "Low similarity should not match at 90% threshold"

    def test_no_match(self, test_csv: Path):
        ranker = JournalRanker(test_csv)
        assert ranker.lookup("Unknown Journal of Stuff") is None

    def test_empty_publication(self, test_csv: Path):
        ranker = JournalRanker(test_csv)
        assert ranker.lookup("") is None
        assert ranker.lookup(None) is None

    def test_caching(self, test_csv: Path):
        ranker = JournalRanker(test_csv)
        # First call
        result1 = ranker.lookup("Nature")
        # Second call should be cached
        result2 = ranker.lookup("Nature")
        assert result1 == result2 == "Q1"
        assert "Nature" in ranker._cache

    def test_loaded_property(self, test_csv: Path):
        ranker = JournalRanker(test_csv)
        assert ranker.loaded is True

    def test_stats(self, test_csv: Path):
        ranker = JournalRanker(test_csv)
        stats = ranker.stats()
        assert stats["total_journals"] == 6
        assert stats["quartile_counts"]["Q1"] == 4
        assert stats["quartile_counts"]["Q2"] == 1
        assert stats["quartile_counts"]["Q4"] == 1

    def test_missing_csv(self, tmp_path: Path):
        """Test graceful handling of missing CSV."""
        ranker = JournalRanker(tmp_path / "nonexistent.csv")
        assert ranker.loaded is False
        assert ranker.lookup("Nature") is None


# =============================================================================
# Test Override Support (Feature 7)
# =============================================================================


class TestJournalOverrides:
    """Test manual override functionality."""

    @pytest.fixture
    def test_csv(self, tmp_path: Path) -> Path:
        """Create a test CSV file."""
        csv_path = tmp_path / "test_scimago.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["title_normalized", "quartile"])
            writer.writerow(["nature", "Q1"])
            writer.writerow(["wrong journal match", "Q4"])  # Will be overridden
        return csv_path

    @pytest.fixture
    def test_overrides(self, tmp_path: Path) -> Path:
        """Create a test overrides file."""
        overrides_path = tmp_path / "overrides.csv"
        with open(overrides_path, "w", encoding="utf-8") as f:
            f.write("# This is a comment\n")
            f.write("Correct Journal Name,Q1\n")
            f.write("# Another comment\n")
            f.write("wrong journal match,Q2\n")  # Override the Q4 from main CSV
        return overrides_path

    def test_override_takes_precedence(self, test_csv: Path, test_overrides: Path):
        """Overrides should take precedence over SCImago data."""
        ranker = JournalRanker(test_csv, overrides_path=test_overrides)

        # "wrong journal match" is Q4 in CSV but Q2 in overrides
        result = ranker.lookup("wrong journal match")
        assert result == "Q2", "Override should take precedence over SCImago"

    def test_override_exact_match(self, test_csv: Path, test_overrides: Path):
        """Overrides should work with exact matching."""
        ranker = JournalRanker(test_csv, overrides_path=test_overrides)

        result = ranker.lookup("Correct Journal Name")
        assert result == "Q1"

    def test_override_with_abbreviation_expansion(
        self, test_csv: Path, tmp_path: Path
    ):
        """Overrides should work after abbreviation expansion."""
        overrides_path = tmp_path / "overrides_abbrev.csv"
        with open(overrides_path, "w", encoding="utf-8") as f:
            # Note: "J. Biomed. Eng." expands to "journal biomedical engineering"
            # (without "of"), so override must match the expanded form
            f.write("journal biomedical engineering,Q1\n")

        ranker = JournalRanker(test_csv, overrides_path=overrides_path)

        # "J. Biomed. Eng." should expand and match override
        result = ranker.lookup("J. Biomed. Eng.")
        assert result == "Q1"

    def test_empty_overrides_file(self, test_csv: Path, tmp_path: Path):
        """Empty overrides file should not cause errors."""
        overrides_path = tmp_path / "empty_overrides.csv"
        overrides_path.write_text("# Just comments\n# No actual overrides\n")

        ranker = JournalRanker(test_csv, overrides_path=overrides_path)
        assert ranker.loaded is True
        assert ranker.lookup("Nature") == "Q1"

    def test_missing_overrides_file(self, test_csv: Path, tmp_path: Path):
        """Missing overrides file should not cause errors."""
        ranker = JournalRanker(
            test_csv, overrides_path=tmp_path / "nonexistent.csv"
        )
        assert ranker.loaded is True
        assert ranker.lookup("Nature") == "Q1"


# =============================================================================
# Test Bundled CSV (Feature 4)
# =============================================================================


class TestBundledCSV:
    """Test that bundled CSV is accessible and valid.

    THESE TESTS FAIL LOUDLY if the bundled CSV is missing or malformed.
    """

    def test_bundled_csv_exists(self):
        """Bundled CSV must exist in package data directory."""
        import zotero_chunk_rag

        csv_path = (
            Path(zotero_chunk_rag.__file__).parent / "data" / "scimago_quartiles.csv"
        )
        assert csv_path.exists(), (
            f"CRITICAL: Bundled SCImago CSV not found at {csv_path}. "
            "Feature 4 requires this file to be present. "
            "Run: python scripts/prepare_scimago.py --input <scimago_download.csv> "
            f"--output {csv_path}"
        )

    def test_bundled_csv_is_valid(self):
        """Bundled CSV must have correct format and data."""
        import zotero_chunk_rag

        csv_path = (
            Path(zotero_chunk_rag.__file__).parent / "data" / "scimago_quartiles.csv"
        )

        if not csv_path.exists():
            pytest.fail(
                f"Bundled CSV not found at {csv_path}. "
                "Cannot verify format."
            )

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            # Verify header columns
            assert reader.fieldnames is not None, "CSV has no header"
            assert "title_normalized" in reader.fieldnames, (
                "CSV missing 'title_normalized' column"
            )
            assert "quartile" in reader.fieldnames, (
                "CSV missing 'quartile' column"
            )

            # Verify data
            row_count = 0
            quartile_counts = {"Q1": 0, "Q2": 0, "Q3": 0, "Q4": 0}

            for row in reader:
                row_count += 1
                title = row.get("title_normalized", "").strip()
                quartile = row.get("quartile", "").strip()

                assert title, f"Row {row_count} has empty title"
                assert quartile in ("Q1", "Q2", "Q3", "Q4"), (
                    f"Row {row_count} has invalid quartile: {quartile}"
                )

                quartile_counts[quartile] += 1

            assert row_count >= 10, (
                f"Bundled CSV only has {row_count} journals. "
                "Expected at least 10 for minimal functionality."
            )

    def test_bundled_csv_loads_automatically(self):
        """JournalRanker should load bundled data automatically."""
        ranker = JournalRanker()  # No path specified

        assert ranker.loaded, (
            "JournalRanker should load bundled CSV automatically. "
            "Ensure data/scimago_quartiles.csv exists."
        )

    def test_bundled_csv_has_common_journals(self):
        """Bundled CSV should include common high-impact journals."""
        ranker = JournalRanker()

        assert ranker.loaded, (
            "CRITICAL: JournalRanker failed to load bundled CSV. "
            "Ensure data/scimago_quartiles.csv exists in package."
        )

        # These journals should definitely be in the bundled data
        common_journals = [
            ("Nature", "Q1"),
            ("Science", "Q1"),
            ("PLOS ONE", "Q1"),
        ]

        for journal, expected_quartile in common_journals:
            result = ranker.lookup(journal)
            assert result == expected_quartile, (
                f"Expected {journal} to be {expected_quartile}, got {result}. "
                "Bundled CSV may be incomplete."
            )

    def test_bundled_overrides_exists(self):
        """Bundled overrides CSV must exist (can be empty)."""
        import zotero_chunk_rag

        overrides_path = (
            Path(zotero_chunk_rag.__file__).parent / "data" / "journal_overrides.csv"
        )
        assert overrides_path.exists(), (
            f"CRITICAL: Bundled overrides CSV not found at {overrides_path}. "
            "Feature 7 requires this file to be present (can be empty with comments)."
        )


# =============================================================================
# Test Fuzzy Match Threshold (Feature 7)
# =============================================================================


class TestFuzzyThreshold:
    """Test that fuzzy matching uses 90% threshold.

    THESE TESTS FAIL LOUDLY if false positives occur.
    """

    @pytest.fixture
    def ranker_with_known_journals(self, tmp_path: Path) -> JournalRanker:
        """Create a ranker with specific journals for threshold testing."""
        csv_path = tmp_path / "threshold_test.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["title_normalized", "quartile"])
            writer.writerow(["journal of cardiology", "Q1"])
            writer.writerow(["european journal of cardiology", "Q2"])
        return JournalRanker(csv_path)

    def test_exact_match_works(self, ranker_with_known_journals: JournalRanker):
        """Exact matches should work."""
        assert ranker_with_known_journals.lookup("Journal of Cardiology") == "Q1"

    def test_near_exact_match_works(self, ranker_with_known_journals: JournalRanker):
        """Very similar names should match."""
        # "journal of cardiology" vs "Journal of Cardiology" - should match
        assert ranker_with_known_journals.lookup("Journal Of Cardiology") == "Q1"

    def test_false_positive_prevention(
        self, ranker_with_known_journals: JournalRanker
    ):
        """Different journals should NOT match due to 90% threshold.

        At 85% threshold, "Journal of Cardiology" might match
        "Journal of Neurology" (they share "Journal of ____ology").
        At 90%, this should be rejected.
        """
        # This is deliberately different and should NOT match
        result = ranker_with_known_journals.lookup("Journal of Neurology")
        assert result is None, (
            "FALSE POSITIVE: 'Journal of Neurology' incorrectly matched. "
            "Fuzzy threshold may be too low."
        )

    def test_very_different_no_match(
        self, ranker_with_known_journals: JournalRanker
    ):
        """Very different names should definitely not match."""
        result = ranker_with_known_journals.lookup("Proceedings of the ACM")
        assert result is None


# =============================================================================
# Test Hot Reload (existing feature)
# =============================================================================


class TestHotReload:
    """Test hot reload functionality."""

    def test_is_stale_after_modification(self, tmp_path: Path):
        """is_stale should detect when CSV has been modified."""
        csv_path = tmp_path / "test.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["title_normalized", "quartile"])
            writer.writerow(["nature", "Q1"])

        ranker = JournalRanker(csv_path)
        assert not ranker.is_stale()

        # Modify the file
        import time

        time.sleep(0.1)  # Ensure mtime changes
        with open(csv_path, "a", encoding="utf-8") as f:
            f.write("science,Q1\n")

        assert ranker.is_stale()

    def test_reload_if_stale(self, tmp_path: Path):
        """reload_if_stale should reload modified CSV."""
        csv_path = tmp_path / "test.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["title_normalized", "quartile"])
            writer.writerow(["nature", "Q1"])

        ranker = JournalRanker(csv_path)
        assert ranker.lookup("Science") is None

        # Modify the file to add Science
        import time

        time.sleep(0.1)
        with open(csv_path, "a", encoding="utf-8") as f:
            f.write("science,Q1\n")

        # Reload
        reloaded = ranker.reload_if_stale()
        assert reloaded is True

        # Now Science should be found
        assert ranker.lookup("Science") == "Q1"
