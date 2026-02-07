"""Tests for boolean full-text search (Feature 3).

These tests verify:
1. AND/OR boolean logic on Zotero's full-text index
2. Case-insensitive word matching
3. Empty query handling
4. SQL injection prevention
5. Integration with year filtering

Tests are designed to FAIL LOUDLY if:
- Boolean logic is incorrect (AND returns OR results or vice versa)
- SQL injection vulnerabilities exist
- Missing words cause crashes instead of empty results
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_zotero_db_with_fulltext(tmp_path: Path) -> Path:
    """Create a mock Zotero database with full-text search data.

    This creates a more complete Zotero schema than conftest.py,
    specifically designed for testing boolean search.
    """
    db_path = tmp_path / "zotero.sqlite"
    conn = sqlite3.connect(db_path)

    conn.executescript("""
        -- Core item tables
        CREATE TABLE items (
            itemID INTEGER PRIMARY KEY,
            itemTypeID INTEGER,
            key TEXT UNIQUE,
            libraryID INTEGER DEFAULT 1,
            dateAdded TEXT,
            dateModified TEXT
        );

        -- Deleted items (for filtering)
        CREATE TABLE deletedItems (itemID INTEGER PRIMARY KEY);

        -- Attachment relationship
        CREATE TABLE itemAttachments (
            itemID INTEGER PRIMARY KEY,
            parentItemID INTEGER,
            path TEXT,
            contentType TEXT,
            linkMode INTEGER DEFAULT 0
        );

        -- Full-text search tables (Zotero's custom FTS)
        CREATE TABLE fulltextWords (
            wordID INTEGER PRIMARY KEY,
            word TEXT UNIQUE
        );

        CREATE TABLE fulltextItemWords (
            wordID INTEGER,
            itemID INTEGER,
            PRIMARY KEY (wordID, itemID)
        );

        CREATE TABLE fulltextItems (
            itemID INTEGER PRIMARY KEY,
            indexedPages INTEGER,
            totalPages INTEGER,
            indexedChars INTEGER,
            version INTEGER
        );

        -- Item metadata (EAV pattern)
        CREATE TABLE fields (
            fieldID INTEGER PRIMARY KEY,
            fieldName TEXT UNIQUE
        );

        CREATE TABLE itemData (
            itemID INTEGER,
            fieldID INTEGER,
            valueID INTEGER,
            PRIMARY KEY (itemID, fieldID)
        );

        CREATE TABLE itemDataValues (
            valueID INTEGER PRIMARY KEY,
            value TEXT
        );

        -- Creators
        CREATE TABLE creators (
            creatorID INTEGER PRIMARY KEY,
            firstName TEXT,
            lastName TEXT
        );

        CREATE TABLE itemCreators (
            itemID INTEGER,
            creatorID INTEGER,
            orderIndex INTEGER
        );

        -- Insert field definitions
        INSERT INTO fields (fieldID, fieldName) VALUES (1, 'title');
        INSERT INTO fields (fieldID, fieldName) VALUES (2, 'date');
        INSERT INTO fields (fieldID, fieldName) VALUES (3, 'publicationTitle');
        INSERT INTO fields (fieldID, fieldName) VALUES (4, 'DOI');

        -- Insert test items (parent items - not attachments)
        -- Item 1: Paper about heart rate variability
        INSERT INTO items (itemID, itemTypeID, key) VALUES (1, 4, 'HRV_PAPER');

        -- Item 2: Paper about ECG electrodes
        INSERT INTO items (itemID, itemTypeID, key) VALUES (2, 4, 'ECG_PAPER');

        -- Item 3: Paper about both HRV and ECG
        INSERT INTO items (itemID, itemTypeID, key) VALUES (3, 4, 'BOTH_PAPER');

        -- Item 4: Paper with no relevant words (control)
        INSERT INTO items (itemID, itemTypeID, key) VALUES (4, 4, 'OTHER_PAPER');

        -- Attachment items (itemTypeID=14 for attachments)
        INSERT INTO items (itemID, itemTypeID, key) VALUES (101, 14, 'ATT_HRV');
        INSERT INTO items (itemID, itemTypeID, key) VALUES (102, 14, 'ATT_ECG');
        INSERT INTO items (itemID, itemTypeID, key) VALUES (103, 14, 'ATT_BOTH');
        INSERT INTO items (itemID, itemTypeID, key) VALUES (104, 14, 'ATT_OTHER');

        -- Link attachments to parent items
        INSERT INTO itemAttachments (itemID, parentItemID, path, contentType, linkMode)
        VALUES (101, 1, 'storage:hrv.pdf', 'application/pdf', 0);
        INSERT INTO itemAttachments (itemID, parentItemID, path, contentType, linkMode)
        VALUES (102, 2, 'storage:ecg.pdf', 'application/pdf', 0);
        INSERT INTO itemAttachments (itemID, parentItemID, path, contentType, linkMode)
        VALUES (103, 3, 'storage:both.pdf', 'application/pdf', 0);
        INSERT INTO itemAttachments (itemID, parentItemID, path, contentType, linkMode)
        VALUES (104, 4, 'storage:other.pdf', 'application/pdf', 0);

        -- Insert full-text words
        INSERT INTO fulltextWords (wordID, word) VALUES (1, 'heart');
        INSERT INTO fulltextWords (wordID, word) VALUES (2, 'rate');
        INSERT INTO fulltextWords (wordID, word) VALUES (3, 'variability');
        INSERT INTO fulltextWords (wordID, word) VALUES (4, 'ecg');
        INSERT INTO fulltextWords (wordID, word) VALUES (5, 'electrode');
        INSERT INTO fulltextWords (wordID, word) VALUES (6, 'signal');
        INSERT INTO fulltextWords (wordID, word) VALUES (7, 'processing');
        INSERT INTO fulltextWords (wordID, word) VALUES (8, 'machine');
        INSERT INTO fulltextWords (wordID, word) VALUES (9, 'learning');

        -- HRV paper (attachment 101): heart, rate, variability, signal
        INSERT INTO fulltextItemWords (wordID, itemID) VALUES (1, 101);  -- heart
        INSERT INTO fulltextItemWords (wordID, itemID) VALUES (2, 101);  -- rate
        INSERT INTO fulltextItemWords (wordID, itemID) VALUES (3, 101);  -- variability
        INSERT INTO fulltextItemWords (wordID, itemID) VALUES (6, 101);  -- signal

        -- ECG paper (attachment 102): ecg, electrode, signal
        INSERT INTO fulltextItemWords (wordID, itemID) VALUES (4, 102);  -- ecg
        INSERT INTO fulltextItemWords (wordID, itemID) VALUES (5, 102);  -- electrode
        INSERT INTO fulltextItemWords (wordID, itemID) VALUES (6, 102);  -- signal

        -- Both paper (attachment 103): heart, rate, variability, ecg, electrode
        INSERT INTO fulltextItemWords (wordID, itemID) VALUES (1, 103);  -- heart
        INSERT INTO fulltextItemWords (wordID, itemID) VALUES (2, 103);  -- rate
        INSERT INTO fulltextItemWords (wordID, itemID) VALUES (3, 103);  -- variability
        INSERT INTO fulltextItemWords (wordID, itemID) VALUES (4, 103);  -- ecg
        INSERT INTO fulltextItemWords (wordID, itemID) VALUES (5, 103);  -- electrode

        -- Other paper (attachment 104): machine, learning
        INSERT INTO fulltextItemWords (wordID, itemID) VALUES (8, 104);  -- machine
        INSERT INTO fulltextItemWords (wordID, itemID) VALUES (9, 104);  -- learning

        -- Mark PDFs as indexed
        INSERT INTO fulltextItems (itemID, indexedPages, totalPages) VALUES (101, 10, 10);
        INSERT INTO fulltextItems (itemID, indexedPages, totalPages) VALUES (102, 8, 8);
        INSERT INTO fulltextItems (itemID, indexedPages, totalPages) VALUES (103, 15, 15);
        INSERT INTO fulltextItems (itemID, indexedPages, totalPages) VALUES (104, 5, 5);
    """)

    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def zotero_client_with_fulltext(mock_zotero_db_with_fulltext: Path):
    """Create a ZoteroClient with the mock database."""
    from zotero_chunk_rag.zotero_client import ZoteroClient

    # ZoteroClient expects a data_dir, not db_path
    data_dir = mock_zotero_db_with_fulltext.parent
    return ZoteroClient(data_dir)


# =============================================================================
# Test AND Query Logic
# =============================================================================


class TestBooleanAND:
    """Test AND boolean logic."""

    def test_and_all_words_present(self, zotero_client_with_fulltext):
        """AND query should return items containing ALL words."""
        results = zotero_client_with_fulltext.search_fulltext("heart rate", "AND")

        # HRV_PAPER and BOTH_PAPER have both "heart" and "rate"
        assert "HRV_PAPER" in results
        assert "BOTH_PAPER" in results

        # ECG_PAPER only has "ecg" and "electrode", not "heart" or "rate"
        assert "ECG_PAPER" not in results

    def test_and_missing_word_returns_empty(self, zotero_client_with_fulltext):
        """AND query with any missing word should return empty set."""
        # "nonexistent" is not in any document
        results = zotero_client_with_fulltext.search_fulltext(
            "heart nonexistent", "AND"
        )
        assert len(results) == 0

    def test_and_single_word(self, zotero_client_with_fulltext):
        """AND with single word should work like exact search."""
        results = zotero_client_with_fulltext.search_fulltext("ecg", "AND")

        # ECG_PAPER and BOTH_PAPER have "ecg"
        assert "ECG_PAPER" in results
        assert "BOTH_PAPER" in results
        assert len(results) == 2

    def test_and_three_words(self, zotero_client_with_fulltext):
        """AND with three words requires all three present."""
        results = zotero_client_with_fulltext.search_fulltext(
            "heart rate variability", "AND"
        )

        # HRV_PAPER and BOTH_PAPER have all three
        assert "HRV_PAPER" in results
        assert "BOTH_PAPER" in results
        assert len(results) == 2


# =============================================================================
# Test OR Query Logic
# =============================================================================


class TestBooleanOR:
    """Test OR boolean logic."""

    def test_or_any_word_matches(self, zotero_client_with_fulltext):
        """OR query should return items containing ANY word."""
        results = zotero_client_with_fulltext.search_fulltext("heart electrode", "OR")

        # HRV_PAPER has "heart", ECG_PAPER has "electrode", BOTH_PAPER has both
        assert "HRV_PAPER" in results
        assert "ECG_PAPER" in results
        assert "BOTH_PAPER" in results

        # OTHER_PAPER has neither
        assert "OTHER_PAPER" not in results

    def test_or_one_word_missing(self, zotero_client_with_fulltext):
        """OR should return results even if one word is missing from index."""
        results = zotero_client_with_fulltext.search_fulltext(
            "heart nonexistent", "OR"
        )

        # Should find items with "heart"
        assert "HRV_PAPER" in results
        assert "BOTH_PAPER" in results
        assert len(results) >= 2

    def test_or_all_words_missing(self, zotero_client_with_fulltext):
        """OR with all words missing should return empty set."""
        results = zotero_client_with_fulltext.search_fulltext(
            "nonexistent1 nonexistent2", "OR"
        )
        assert len(results) == 0


# =============================================================================
# Test Case Insensitivity
# =============================================================================


class TestCaseInsensitivity:
    """Test case-insensitive matching."""

    def test_uppercase_query(self, zotero_client_with_fulltext):
        """Uppercase queries should match lowercase words."""
        results = zotero_client_with_fulltext.search_fulltext("HEART", "AND")
        assert "HRV_PAPER" in results

    def test_mixed_case_query(self, zotero_client_with_fulltext):
        """Mixed case queries should work."""
        results = zotero_client_with_fulltext.search_fulltext("HeArT RaTe", "AND")
        assert "HRV_PAPER" in results


# =============================================================================
# Test Edge Cases
# =============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_query_returns_empty(self, zotero_client_with_fulltext):
        """Empty query should return empty set, not error."""
        results = zotero_client_with_fulltext.search_fulltext("", "AND")
        assert results == set()

    def test_whitespace_only_query(self, zotero_client_with_fulltext):
        """Whitespace-only query should return empty set."""
        results = zotero_client_with_fulltext.search_fulltext("   ", "AND")
        assert results == set()

    def test_operator_case_insensitive(self, zotero_client_with_fulltext):
        """Operator should be case-insensitive."""
        results_upper = zotero_client_with_fulltext.search_fulltext("heart", "AND")
        results_lower = zotero_client_with_fulltext.search_fulltext("heart", "and")
        assert results_upper == results_lower

    def test_default_operator_is_and(self, zotero_client_with_fulltext):
        """Default operator should be AND."""
        results_default = zotero_client_with_fulltext.search_fulltext("heart rate")
        results_explicit = zotero_client_with_fulltext.search_fulltext(
            "heart rate", "AND"
        )
        assert results_default == results_explicit


# =============================================================================
# Test SQL Injection Prevention
# =============================================================================


class TestSQLInjectionPrevention:
    """Test that SQL injection is prevented.

    THESE TESTS FAIL LOUDLY if SQL injection is possible.
    """

    def test_sql_injection_in_query(self, zotero_client_with_fulltext):
        """SQL injection in query should be safely handled."""
        # This should not cause SQL errors or return unexpected results
        malicious = "'; DROP TABLE items; --"
        results = zotero_client_with_fulltext.search_fulltext(malicious, "AND")

        # Should return empty (word not found), not crash
        assert results == set()

    def test_sql_injection_in_operator(self, zotero_client_with_fulltext):
        """Malicious operator should be treated as OR (non-AND)."""
        results = zotero_client_with_fulltext.search_fulltext(
            "heart", "'; DROP TABLE items; --"
        )

        # Should still work (treated as OR since it's not "AND")
        assert "HRV_PAPER" in results

    def test_quotes_in_query(self, zotero_client_with_fulltext):
        """Quotes in query should be safely handled."""
        results = zotero_client_with_fulltext.search_fulltext('heart "rate"', "AND")
        # The quotes should be treated as part of a word (which won't match)
        # or stripped - either way, should not crash
        assert isinstance(results, set)


# =============================================================================
# Integration Test
# =============================================================================


class TestBooleanSearchIntegration:
    """Integration tests for boolean search."""

    def test_signal_shared_across_papers(self, zotero_client_with_fulltext):
        """Test word that appears in multiple papers."""
        results = zotero_client_with_fulltext.search_fulltext("signal", "AND")

        # "signal" is in HRV_PAPER and ECG_PAPER
        assert "HRV_PAPER" in results
        assert "ECG_PAPER" in results
        assert len(results) == 2

    def test_complex_and_query(self, zotero_client_with_fulltext):
        """Test complex AND query narrowing results."""
        # "signal" alone matches HRV and ECG papers
        signal_results = zotero_client_with_fulltext.search_fulltext("signal", "AND")
        assert len(signal_results) == 2

        # Adding "heart" narrows to just HRV paper
        heart_signal = zotero_client_with_fulltext.search_fulltext(
            "signal heart", "AND"
        )
        assert len(heart_signal) == 1
        assert "HRV_PAPER" in heart_signal

    def test_or_expands_results(self, zotero_client_with_fulltext):
        """Test OR query expanding results."""
        # "variability" alone matches HRV and BOTH papers
        var_results = zotero_client_with_fulltext.search_fulltext(
            "variability", "AND"
        )

        # "variability OR machine" should add OTHER_PAPER
        var_or_machine = zotero_client_with_fulltext.search_fulltext(
            "variability machine", "OR"
        )

        assert len(var_or_machine) > len(var_results)
        assert "OTHER_PAPER" in var_or_machine
