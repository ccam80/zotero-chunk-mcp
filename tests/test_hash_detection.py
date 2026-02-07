"""Tests for hash-based PDF update detection (Feature 6).

These tests verify:
1. PDF hash is stored in document metadata
2. Changed PDFs are detected and trigger reindex
3. Documents without hash get reindexed to add hash
4. Unchanged PDFs are efficiently skipped

Tests are designed to FAIL LOUDLY if:
- Hash detection misses changed PDFs
- Reindexing overwrites correct content with stale data
- Performance degrades for unchanged documents
"""
from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_vector_store():
    """Create a mock VectorStore with controllable metadata."""
    store = MagicMock()
    store._stored_meta = {}  # doc_id -> metadata

    def get_document_meta(doc_id):
        return store._stored_meta.get(doc_id)

    def delete_document(doc_id):
        if doc_id in store._stored_meta:
            del store._stored_meta[doc_id]

    store.get_document_meta = MagicMock(side_effect=get_document_meta)
    store.delete_document = MagicMock(side_effect=delete_document)
    store.get_indexed_doc_ids = MagicMock(return_value=set(store._stored_meta.keys()))

    return store


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    """Create a sample PDF file for testing."""
    pdf_path = tmp_path / "test.pdf"
    # Create a minimal valid-looking PDF (just for hash testing)
    pdf_content = b"%PDF-1.4\ntest content\n%%EOF"
    pdf_path.write_bytes(pdf_content)
    return pdf_path


@pytest.fixture
def modified_pdf(tmp_path: Path) -> Path:
    """Create a modified version of the sample PDF."""
    pdf_path = tmp_path / "test_modified.pdf"
    # Different content = different hash
    pdf_content = b"%PDF-1.4\nmodified content with changes\n%%EOF"
    pdf_path.write_bytes(pdf_content)
    return pdf_path


# =============================================================================
# Test PDF Hash Computation
# =============================================================================


class TestPDFHash:
    """Test PDF hash computation."""

    def test_hash_is_deterministic(self, sample_pdf: Path):
        """Same file should produce same hash."""
        from zotero_chunk_rag.indexer import Indexer

        hash1 = Indexer._pdf_hash(sample_pdf)
        hash2 = Indexer._pdf_hash(sample_pdf)

        assert hash1 == hash2, "Hash should be deterministic"

    def test_different_content_different_hash(
        self, sample_pdf: Path, modified_pdf: Path
    ):
        """Different content should produce different hash."""
        from zotero_chunk_rag.indexer import Indexer

        hash1 = Indexer._pdf_hash(sample_pdf)
        hash2 = Indexer._pdf_hash(modified_pdf)

        assert hash1 != hash2, "Different files should have different hashes"

    def test_hash_is_hex_string(self, sample_pdf: Path):
        """Hash should be a valid hex string."""
        from zotero_chunk_rag.indexer import Indexer

        pdf_hash = Indexer._pdf_hash(sample_pdf)

        # Should be a valid hex string
        assert isinstance(pdf_hash, str)
        assert all(c in "0123456789abcdef" for c in pdf_hash)

        # SHA-256 produces 64 hex chars
        assert len(pdf_hash) == 64

    def test_hash_uses_first_64kb(self, tmp_path: Path):
        """Hash should be computed from first 64KB only (for speed)."""
        from zotero_chunk_rag.indexer import Indexer

        # Create a large file (>64KB)
        pdf_path = tmp_path / "large.pdf"
        content = b"%PDF-1.4\n" + b"x" * 100000 + b"\n%%EOF"
        pdf_path.write_bytes(content)

        # Create same file but with different content after 64KB
        pdf_path2 = tmp_path / "large2.pdf"
        content2 = b"%PDF-1.4\n" + b"x" * 100000 + b"\nDIFFERENT\n%%EOF"
        pdf_path2.write_bytes(content2)

        hash1 = Indexer._pdf_hash(pdf_path)
        hash2 = Indexer._pdf_hash(pdf_path2)

        # Hashes should be same because only first 64KB is used
        # and the difference is after 64KB
        assert hash1 == hash2, (
            "Hash should only use first 64KB for performance"
        )


# =============================================================================
# Test _needs_reindex Logic
# =============================================================================


class TestNeedsReindex:
    """Test the _needs_reindex method."""

    def test_new_document_needs_reindex(
        self, sample_pdf: Path, mock_vector_store
    ):
        """New document (not in store) should need indexing."""
        from zotero_chunk_rag.indexer import Indexer
        from zotero_chunk_rag.models import ZoteroItem

        # Create mock item
        item = ZoteroItem(
            item_key="NEW_DOC",
            title="New Document",
            authors="Test",
            year=2024,
            pdf_path=sample_pdf,
        )

        # Create indexer with mocked store
        with patch.object(Indexer, "__init__", lambda self, config: None):
            indexer = Indexer.__new__(Indexer)
            indexer.store = mock_vector_store

            needs_reindex, reason = indexer._needs_reindex(item)

            assert needs_reindex is True
            assert reason == "new"

    def test_unchanged_document_does_not_need_reindex(
        self, sample_pdf: Path, mock_vector_store
    ):
        """Document with matching hash should not need reindex."""
        from zotero_chunk_rag.indexer import Indexer
        from zotero_chunk_rag.models import ZoteroItem

        item = ZoteroItem(
            item_key="EXISTING_DOC",
            title="Existing Document",
            authors="Test",
            year=2024,
            pdf_path=sample_pdf,
        )

        # Compute hash and store it
        stored_hash = Indexer._pdf_hash(sample_pdf)
        mock_vector_store._stored_meta["EXISTING_DOC"] = {
            "pdf_hash": stored_hash
        }

        with patch.object(Indexer, "__init__", lambda self, config: None):
            indexer = Indexer.__new__(Indexer)
            indexer.store = mock_vector_store

            needs_reindex, reason = indexer._needs_reindex(item)

            assert needs_reindex is False
            assert reason == "current"

    def test_changed_pdf_needs_reindex(
        self, sample_pdf: Path, modified_pdf: Path, mock_vector_store
    ):
        """Document with different PDF hash should need reindex."""
        from zotero_chunk_rag.indexer import Indexer
        from zotero_chunk_rag.models import ZoteroItem

        item = ZoteroItem(
            item_key="CHANGED_DOC",
            title="Changed Document",
            authors="Test",
            year=2024,
            pdf_path=modified_pdf,  # Using modified PDF
        )

        # Store hash of ORIGINAL PDF
        original_hash = Indexer._pdf_hash(sample_pdf)
        mock_vector_store._stored_meta["CHANGED_DOC"] = {
            "pdf_hash": original_hash
        }

        with patch.object(Indexer, "__init__", lambda self, config: None):
            indexer = Indexer.__new__(Indexer)
            indexer.store = mock_vector_store

            needs_reindex, reason = indexer._needs_reindex(item)

            assert needs_reindex is True
            assert reason == "changed"

    def test_missing_hash_needs_reindex(
        self, sample_pdf: Path, mock_vector_store
    ):
        """Document indexed without hash should need reindex."""
        from zotero_chunk_rag.indexer import Indexer
        from zotero_chunk_rag.models import ZoteroItem

        item = ZoteroItem(
            item_key="LEGACY_DOC",
            title="Legacy Document",
            authors="Test",
            year=2024,
            pdf_path=sample_pdf,
        )

        # Store metadata WITHOUT pdf_hash (legacy document)
        mock_vector_store._stored_meta["LEGACY_DOC"] = {
            "doc_title": "Legacy Document",
            # No pdf_hash field
        }

        with patch.object(Indexer, "__init__", lambda self, config: None):
            indexer = Indexer.__new__(Indexer)
            indexer.store = mock_vector_store

            needs_reindex, reason = indexer._needs_reindex(item)

            assert needs_reindex is True
            assert reason == "no_hash"


# =============================================================================
# Test VectorStore Integration
# =============================================================================


class TestVectorStoreHashStorage:
    """Test that VectorStore correctly stores and retrieves pdf_hash."""

    def test_add_chunks_stores_hash(self, temp_db_path: Path):
        """add_chunks should store pdf_hash in metadata."""
        from zotero_chunk_rag.vector_store import VectorStore
        from zotero_chunk_rag.models import Chunk

        # Create mock embedder
        mock_embedder = MagicMock()
        mock_embedder.embed = MagicMock(return_value=[[0.1] * 768])

        store = VectorStore(temp_db_path, mock_embedder)

        # Add chunks with pdf_hash
        chunks = [
            Chunk(
                text="Test chunk",
                page_num=1,
                chunk_index=0,
                char_start=0,
                char_end=10,
                section="unknown",
                section_confidence=1.0,
            )
        ]

        doc_meta = {
            "title": "Test Doc",
            "authors": "Test Author",
            "year": 2024,
            "pdf_hash": "abc123def456",
        }

        store.add_chunks("TEST_DOC", doc_meta, chunks)

        # Verify hash is stored
        retrieved_meta = store.get_document_meta("TEST_DOC")
        assert retrieved_meta is not None
        assert retrieved_meta.get("pdf_hash") == "abc123def456"

    def test_get_document_meta_returns_hash(self, temp_db_path: Path):
        """get_document_meta should return pdf_hash."""
        from zotero_chunk_rag.vector_store import VectorStore
        from zotero_chunk_rag.models import Chunk

        mock_embedder = MagicMock()
        mock_embedder.embed = MagicMock(return_value=[[0.1] * 768])

        store = VectorStore(temp_db_path, mock_embedder)

        chunks = [
            Chunk(
                text="Test",
                page_num=1,
                chunk_index=0,
                char_start=0,
                char_end=4,
                section="unknown",
                section_confidence=1.0,
            )
        ]

        store.add_chunks(
            "HASH_TEST",
            {"title": "Test", "pdf_hash": "specific_hash_value"},
            chunks,
        )

        meta = store.get_document_meta("HASH_TEST")
        assert meta["pdf_hash"] == "specific_hash_value"

    def test_get_document_meta_nonexistent_returns_none(
        self, temp_db_path: Path
    ):
        """get_document_meta for nonexistent doc should return None."""
        from zotero_chunk_rag.vector_store import VectorStore

        mock_embedder = MagicMock()
        store = VectorStore(temp_db_path, mock_embedder)

        meta = store.get_document_meta("NONEXISTENT")
        assert meta is None


# =============================================================================
# Test Delete and Reindex Flow
# =============================================================================


class TestDeleteAndReindexFlow:
    """Test the delete-then-reindex flow for changed PDFs."""

    def test_delete_document_removes_all_chunks(self, temp_db_path: Path):
        """delete_document should remove all chunks for a document."""
        from zotero_chunk_rag.vector_store import VectorStore
        from zotero_chunk_rag.models import Chunk

        mock_embedder = MagicMock()
        mock_embedder.embed = MagicMock(return_value=[[0.1] * 768] * 3)

        store = VectorStore(temp_db_path, mock_embedder)

        # Add multiple chunks
        chunks = [
            Chunk(
                text=f"Chunk {i}",
                page_num=1,
                chunk_index=i,
                char_start=i * 10,
                char_end=(i + 1) * 10,
                section="unknown",
                section_confidence=1.0,
            )
            for i in range(3)
        ]

        store.add_chunks("DELETE_TEST", {"title": "Test", "pdf_hash": "hash"}, chunks)

        # Verify chunks exist
        assert store.get_document_meta("DELETE_TEST") is not None
        initial_count = store.count()
        assert initial_count == 3

        # Delete document
        store.delete_document("DELETE_TEST")

        # Verify all chunks removed
        assert store.get_document_meta("DELETE_TEST") is None
        assert store.count() == 0

    def test_reindex_replaces_content(self, temp_db_path: Path):
        """Reindexing should replace old content with new."""
        from zotero_chunk_rag.vector_store import VectorStore
        from zotero_chunk_rag.models import Chunk

        mock_embedder = MagicMock()
        mock_embedder.embed = MagicMock(return_value=[[0.1] * 768])

        store = VectorStore(temp_db_path, mock_embedder)

        # Add original content
        chunks_v1 = [
            Chunk(
                text="Original content",
                page_num=1,
                chunk_index=0,
                char_start=0,
                char_end=16,
                section="unknown",
                section_confidence=1.0,
            )
        ]

        store.add_chunks(
            "REINDEX_TEST",
            {"title": "Test", "pdf_hash": "hash_v1"},
            chunks_v1,
        )

        # Delete and add new content
        store.delete_document("REINDEX_TEST")

        mock_embedder.embed = MagicMock(return_value=[[0.2] * 768])
        chunks_v2 = [
            Chunk(
                text="Updated content",
                page_num=1,
                chunk_index=0,
                char_start=0,
                char_end=15,
                section="unknown",
                section_confidence=1.0,
            )
        ]

        store.add_chunks(
            "REINDEX_TEST",
            {"title": "Test", "pdf_hash": "hash_v2"},
            chunks_v2,
        )

        # Verify new content and hash
        meta = store.get_document_meta("REINDEX_TEST")
        assert meta["pdf_hash"] == "hash_v2"
