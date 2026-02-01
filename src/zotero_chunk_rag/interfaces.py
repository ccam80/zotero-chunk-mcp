"""
Protocol definitions for all major components.
Allows parallel development against interfaces.
"""
from typing import Protocol
from pathlib import Path
from .models import ZoteroItem, PageText, Chunk, StoredChunk, RetrievalResult


class ZoteroClientProtocol(Protocol):
    """Interface for Zotero database access."""

    def get_all_items_with_pdfs(self) -> list[ZoteroItem]:
        """Get all Zotero items that have PDF attachments."""
        ...

    def get_item(self, item_key: str) -> ZoteroItem | None:
        """Get a specific item by key."""
        ...


class PDFExtractorProtocol(Protocol):
    """Interface for PDF text extraction."""

    def extract(self, pdf_path: Path) -> list[PageText]:
        """Extract text from PDF, returning per-page content."""
        ...


class ChunkerProtocol(Protocol):
    """Interface for document chunking."""

    def chunk(self, pages: list[PageText]) -> list[Chunk]:
        """Split pages into overlapping chunks."""
        ...


class EmbedderProtocol(Protocol):
    """Interface for text embedding."""

    def embed(self, texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
        """Embed multiple texts."""
        ...

    def embed_query(self, query: str) -> list[float]:
        """Embed a search query (uses RETRIEVAL_QUERY task type)."""
        ...


class VectorStoreProtocol(Protocol):
    """Interface for vector storage and retrieval."""

    def add_chunks(self, doc_id: str, doc_meta: dict, chunks: list[Chunk]) -> None:
        """Add chunks for a document."""
        ...

    def search(self, query: str, top_k: int = 10, filters: dict | None = None) -> list[StoredChunk]:
        """Search for similar chunks."""
        ...

    def get_adjacent_chunks(self, doc_id: str, chunk_index: int, window: int = 2) -> list[StoredChunk]:
        """Get chunks adjacent to a given chunk."""
        ...

    def delete_document(self, doc_id: str) -> None:
        """Delete all chunks for a document."""
        ...

    def get_indexed_doc_ids(self) -> set[str]:
        """Get IDs of all indexed documents."""
        ...

    def count(self) -> int:
        """Count total chunks."""
        ...


class RetrieverProtocol(Protocol):
    """Interface for search with context expansion."""

    def search(
        self,
        query: str,
        top_k: int = 10,
        context_window: int = 1,
        filters: dict | None = None
    ) -> list[RetrievalResult]:
        """Search and expand context."""
        ...
