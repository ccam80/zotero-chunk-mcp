"""Indexing pipeline orchestration."""
import logging
from pathlib import Path
from tqdm import tqdm
from .config import Config
from .zotero_client import ZoteroClient
from .pdf_extractor import PDFExtractor
from .chunker import Chunker
from .embedder import Embedder
from .vector_store import VectorStore
from .models import ZoteroItem

logger = logging.getLogger(__name__)


class Indexer:
    """
    Orchestrates the full indexing pipeline.

    Pipeline: Zotero -> PDF -> Chunks -> Embeddings -> VectorStore
    """

    def __init__(self, config: Config):
        self.config = config
        self.zotero = ZoteroClient(config.zotero_data_dir)
        self.extractor = PDFExtractor()
        self.chunker = Chunker(
            chunk_size=config.chunk_size,
            overlap=config.chunk_overlap
        )
        self.embedder = Embedder(
            model=config.embedding_model,
            dimensions=config.embedding_dimensions,
            api_key=config.gemini_api_key
        )
        self.store = VectorStore(config.chroma_db_path, self.embedder)

    def index_all(self, force_reindex: bool = False, limit: int | None = None) -> dict:
        """
        Index all PDFs in Zotero library.

        Args:
            force_reindex: If True, reindex all documents
            limit: Max documents to index (for testing)

        Returns:
            Stats dict with counts
        """
        items = self.zotero.get_all_items_with_pdfs()

        # Filter to items with valid PDFs
        items = [i for i in items if i.pdf_path and i.pdf_path.exists()]

        if limit:
            items = items[:limit]

        if force_reindex:
            existing = self.store.get_indexed_doc_ids()
            item_keys = {i.item_key for i in items}
            for doc_id in existing & item_keys:
                self.store.delete_document(doc_id)
            indexed = set()
        else:
            indexed = self.store.get_indexed_doc_ids()
        to_index = [i for i in items if i.item_key not in indexed]

        logger.info(f"Found {len(items)} items with PDFs")
        logger.info(f"Already indexed: {len(indexed)}, to index: {len(to_index)}")

        stats = {"indexed": 0, "failed": 0, "skipped": len(indexed)}

        for item in tqdm(to_index, desc="Indexing"):
            try:
                self.index_document(item)
                stats["indexed"] += 1
            except Exception as e:
                logger.error(f"Failed to index {item.item_key}: {e}")
                stats["failed"] += 1

        return stats

    def index_document(self, item: ZoteroItem) -> int:
        """
        Index a single document.

        Returns:
            Number of chunks created
        """
        if item.pdf_path is None or not item.pdf_path.exists():
            raise FileNotFoundError(f"PDF not found for {item.item_key}")

        # Extract text
        pages = self.extractor.extract(item.pdf_path)
        if not pages:
            logger.warning(f"No text extracted from {item.item_key}")
            return 0

        # Chunk
        chunks = self.chunker.chunk(pages)
        if not chunks:
            logger.warning(f"No chunks created for {item.item_key}")
            return 0

        # Store
        doc_meta = {
            "title": item.title,
            "authors": item.authors,
            "year": item.year,
            "citation_key": item.citation_key,
            "publication": item.publication,
        }
        self.store.add_chunks(item.item_key, doc_meta, chunks)

        logger.debug(f"Indexed {item.item_key}: {len(chunks)} chunks")
        return len(chunks)

    def reindex_document(self, item_key: str) -> int:
        """Re-index a specific document."""
        self.store.delete_document(item_key)
        item = self.zotero.get_item(item_key)
        if item:
            return self.index_document(item)
        return 0

    def get_stats(self) -> dict:
        """Get index statistics."""
        doc_ids = self.store.get_indexed_doc_ids()
        total_chunks = self.store.count()
        return {
            "total_documents": len(doc_ids),
            "total_chunks": total_chunks,
            "avg_chunks_per_doc": round(total_chunks / len(doc_ids), 1) if doc_ids else 0,
        }
