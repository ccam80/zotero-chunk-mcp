"""
Shared pytest fixtures for zotero-chunk-rag tests.

All fixtures that need to be shared across test modules should be defined here.
"""
from __future__ import annotations

import csv
import sqlite3
import tempfile
from pathlib import Path

import pytest


# =============================================================================
# Path fixtures
# =============================================================================

@pytest.fixture
def sample_pdf_path() -> Path:
    """Path to a sample PDF for testing."""
    path = Path(__file__).parent / "fixtures" / "sample.pdf"
    assert path.exists(), (
        f"CRITICAL: Test PDF not found: {path}. "
        "Run 'python tests/fixtures/create_test_pdfs.py' to generate fixtures."
    )
    return path


@pytest.fixture
def sample_pdf_with_figures() -> Path:
    """Path to a PDF containing figures for extraction testing."""
    path = Path(__file__).parent / "fixtures" / "sample_with_figures.pdf"
    assert path.exists(), (
        f"CRITICAL: Test PDF not found: {path}. "
        "Run 'python tests/fixtures/create_test_pdfs.py' to generate fixtures."
    )
    return path


@pytest.fixture
def sample_pdf_scanned() -> Path:
    """Path to a scanned PDF (image-based) for OCR testing."""
    path = Path(__file__).parent / "fixtures" / "sample_scanned.pdf"
    assert path.exists(), (
        f"CRITICAL: Test PDF not found: {path}. "
        "Run 'python tests/fixtures/create_test_pdfs.py' to generate fixtures."
    )
    return path


# =============================================================================
# Database fixtures
# =============================================================================

@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Temporary directory for ChromaDB during tests."""
    db_path = tmp_path / "chroma"
    db_path.mkdir(parents=True, exist_ok=True)
    return db_path


@pytest.fixture
def mock_zotero_db(tmp_path: Path) -> Path:
    """Create a mock Zotero database with sample data for testing.

    This creates a minimal Zotero SQLite schema with the tables needed
    for full-text search testing.
    """
    db_path = tmp_path / "zotero.sqlite"
    conn = sqlite3.connect(db_path)

    # Create minimal Zotero schema
    conn.executescript("""
        -- Core item tables
        CREATE TABLE items (
            itemID INTEGER PRIMARY KEY,
            itemTypeID INTEGER,
            key TEXT UNIQUE,
            libraryID INTEGER,
            dateAdded TEXT,
            dateModified TEXT
        );

        -- Attachment relationship
        CREATE TABLE itemAttachments (
            itemID INTEGER PRIMARY KEY,
            parentItemID INTEGER,
            path TEXT,
            contentType TEXT,
            FOREIGN KEY (itemID) REFERENCES items(itemID),
            FOREIGN KEY (parentItemID) REFERENCES items(itemID)
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

        -- Item metadata
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

        CREATE TABLE fields (
            fieldID INTEGER PRIMARY KEY,
            fieldName TEXT
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

        -- Insert some test data
        INSERT INTO items (itemID, key) VALUES (1, 'ABC12345');
        INSERT INTO items (itemID, key) VALUES (2, 'DEF67890');
        INSERT INTO items (itemID, key) VALUES (3, 'GHI11111');

        -- Attachment items
        INSERT INTO items (itemID, key) VALUES (101, 'ATT00001');
        INSERT INTO items (itemID, key) VALUES (102, 'ATT00002');

        INSERT INTO itemAttachments (itemID, parentItemID, path)
        VALUES (101, 1, 'storage:test1.pdf');
        INSERT INTO itemAttachments (itemID, parentItemID, path)
        VALUES (102, 2, 'storage:test2.pdf');

        -- Full-text words for testing boolean search
        INSERT INTO fulltextWords (wordID, word) VALUES (1, 'heart');
        INSERT INTO fulltextWords (wordID, word) VALUES (2, 'rate');
        INSERT INTO fulltextWords (wordID, word) VALUES (3, 'variability');
        INSERT INTO fulltextWords (wordID, word) VALUES (4, 'ecg');
        INSERT INTO fulltextWords (wordID, word) VALUES (5, 'electrode');

        -- Item 1 (ABC12345) contains: heart, rate, variability, ecg
        INSERT INTO fulltextItemWords (wordID, itemID) VALUES (1, 101);
        INSERT INTO fulltextItemWords (wordID, itemID) VALUES (2, 101);
        INSERT INTO fulltextItemWords (wordID, itemID) VALUES (3, 101);
        INSERT INTO fulltextItemWords (wordID, itemID) VALUES (4, 101);

        -- Item 2 (DEF67890) contains: heart, electrode
        INSERT INTO fulltextItemWords (wordID, itemID) VALUES (1, 102);
        INSERT INTO fulltextItemWords (wordID, itemID) VALUES (5, 102);

        INSERT INTO fulltextItems (itemID, indexedPages, totalPages) VALUES (101, 10, 10);
        INSERT INTO fulltextItems (itemID, indexedPages, totalPages) VALUES (102, 5, 5);
    """)

    conn.commit()
    conn.close()
    return db_path


# =============================================================================
# Config fixtures
# =============================================================================

@pytest.fixture
def mock_config(temp_db_path: Path):
    """Create a test configuration.

    Uses local embeddings to avoid needing API keys in tests.
    """
    from zotero_chunk_rag.config import Config

    # Create a minimal config for testing
    # Use local embeddings so tests don't require API keys
    return Config(
        chroma_db_path=temp_db_path,
        embedding_provider="local",
    )


# =============================================================================
# Journal ranker fixtures
# =============================================================================

@pytest.fixture
def test_scimago_csv(tmp_path: Path) -> Path:
    """Create a test SCImago CSV file with known journals."""
    csv_path = tmp_path / "test_scimago.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["title_normalized", "quartile"])
        # Q1 journals
        writer.writerow(["nature", "Q1"])
        writer.writerow(["science", "Q1"])
        writer.writerow(["cell", "Q1"])
        writer.writerow(["the lancet", "Q1"])
        writer.writerow(["new england journal of medicine", "Q1"])
        writer.writerow(["ieee transactions on biomedical engineering", "Q1"])
        writer.writerow(["circulation", "Q1"])
        writer.writerow(["plos one", "Q1"])
        # Q2 journals
        writer.writerow(["journal of physiology", "Q2"])
        writer.writerow(["physiological measurement", "Q2"])
        writer.writerow(["medical engineering physics", "Q2"])
        # Q3 journals
        writer.writerow(["journal of medical systems", "Q3"])
        writer.writerow(["biomedical signal processing and control", "Q3"])
        # Q4 journals
        writer.writerow(["medical hypotheses", "Q4"])
        writer.writerow(["journal of low power electronics", "Q4"])
    return csv_path


@pytest.fixture
def test_overrides_csv(tmp_path: Path) -> Path:
    """Create a test journal overrides CSV file."""
    csv_path = tmp_path / "journal_overrides.csv"
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("# Manual corrections for fuzzy matching mistakes\n")
        f.write("# Format: input_title,correct_quartile\n")
        f.write("IEEE Transactions on Biomedical Circuits and Systems,Q1\n")
        f.write("Journal of Neural Engineering,Q1\n")
    return csv_path
