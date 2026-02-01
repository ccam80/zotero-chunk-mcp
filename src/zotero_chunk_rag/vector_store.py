"""ChromaDB vector storage with chunk management."""
import chromadb
from chromadb.config import Settings
from pathlib import Path
from .models import Chunk, StoredChunk
from .interfaces import EmbedderProtocol


class VectorStore:
    """
    ChromaDB-backed vector store for document chunks.

    Handles:
    - Adding chunks with metadata
    - Semantic search with filters
    - Adjacent chunk retrieval for context expansion
    - Document-level operations (delete, list)
    """

    def __init__(self, db_path: Path, embedder: EmbedderProtocol):
        self.db_path = Path(db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=str(self.db_path),
            settings=Settings(anonymized_telemetry=False)
        )
        self.collection = self.client.get_or_create_collection(
            name="chunks",
            metadata={"hnsw:space": "cosine"}
        )
        self.embedder = embedder

    def add_chunks(self, doc_id: str, doc_meta: dict, chunks: list[Chunk]) -> None:
        """
        Add all chunks for a document.

        Args:
            doc_id: Unique document identifier (Zotero item key)
            doc_meta: Document metadata (title, authors, year)
            chunks: List of Chunk objects to store
        """
        if not chunks:
            return

        ids = [f"{doc_id}_chunk_{c.chunk_index:04d}" for c in chunks]
        texts = [c.text for c in chunks]

        # Use RETRIEVAL_DOCUMENT task type
        embeddings = self.embedder.embed(texts, task_type="RETRIEVAL_DOCUMENT")

        metadatas = [
            {
                "doc_id": doc_id,
                "doc_title": doc_meta.get("title", ""),
                "authors": doc_meta.get("authors", ""),
                "year": doc_meta.get("year") or 0,
                "citation_key": doc_meta.get("citation_key", ""),
                "publication": doc_meta.get("publication", ""),
                "page_num": c.page_num,
                "chunk_index": c.chunk_index,
                "total_chunks": len(chunks),
                "char_start": c.char_start,
                "char_end": c.char_end,
            }
            for c in chunks
        ]

        self.collection.add(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas
        )

    def search(
        self,
        query: str,
        top_k: int = 10,
        filters: dict | None = None
    ) -> list[StoredChunk]:
        """
        Search for similar chunks.

        Args:
            query: Search query text
            top_k: Number of results to return
            filters: Optional ChromaDB where clause

        Returns:
            List of StoredChunk objects sorted by similarity
        """
        # Use RETRIEVAL_QUERY task type for asymmetric search
        query_embedding = self.embedder.embed_query(query)

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=filters,
            include=["documents", "metadatas", "distances"]
        )

        chunks = []
        if results['ids'] and results['ids'][0]:
            for i, chunk_id in enumerate(results['ids'][0]):
                chunks.append(StoredChunk(
                    id=chunk_id,
                    text=results['documents'][0][i],
                    metadata=results['metadatas'][0][i],
                    score=1 - results['distances'][0][i]  # Convert distance to similarity
                ))
        return chunks

    def get_adjacent_chunks(
        self,
        doc_id: str,
        chunk_index: int,
        window: int = 2
    ) -> list[StoredChunk]:
        """
        Get chunks adjacent to a given chunk for context expansion.

        Args:
            doc_id: Document ID
            chunk_index: Center chunk index
            window: Number of chunks before/after to include

        Returns:
            List of chunks sorted by chunk_index
        """
        results = self.collection.get(
            where={
                "$and": [
                    {"doc_id": {"$eq": doc_id}},
                    {"chunk_index": {"$gte": chunk_index - window}},
                    {"chunk_index": {"$lte": chunk_index + window}}
                ]
            },
            include=["documents", "metadatas"]
        )

        chunks = []
        if results['ids']:
            for i, chunk_id in enumerate(results['ids']):
                chunks.append(StoredChunk(
                    id=chunk_id,
                    text=results['documents'][i],
                    metadata=results['metadatas'][i]
                ))

        return sorted(chunks, key=lambda c: c.metadata['chunk_index'])

    def delete_document(self, doc_id: str) -> None:
        """Remove all chunks for a document."""
        self.collection.delete(where={"doc_id": {"$eq": doc_id}})

    def get_indexed_doc_ids(self) -> set[str]:
        """Get set of all indexed document IDs."""
        results = self.collection.get(include=["metadatas"])
        if not results['metadatas']:
            return set()
        return {m['doc_id'] for m in results['metadatas']}

    def count(self) -> int:
        """Return total number of chunks."""
        return self.collection.count()
