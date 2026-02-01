"""MCP server with search tools."""
from collections import defaultdict
from fastmcp import FastMCP
from .config import Config
from .embedder import Embedder
from .vector_store import VectorStore
from .retriever import Retriever

mcp = FastMCP("zotero-chunk-rag")

# Lazy initialization
_retriever = None
_store = None


def _get_retriever() -> Retriever:
    global _retriever, _store
    if _retriever is None:
        config = Config.load()
        embedder = Embedder(
            model=config.embedding_model,
            dimensions=config.embedding_dimensions,
            api_key=config.gemini_api_key
        )
        _store = VectorStore(config.chroma_db_path, embedder)
        _retriever = Retriever(_store)
    return _retriever


def _get_store() -> VectorStore:
    _get_retriever()  # Ensure initialized
    return _store


def _build_year_filters(year_min: int | None, year_max: int | None) -> dict | None:
    if not year_min and not year_max:
        return None
    conditions = []
    if year_min:
        conditions.append({"year": {"$gte": year_min}})
    if year_max:
        conditions.append({"year": {"$lte": year_max}})
    return {"$and": conditions} if len(conditions) > 1 else conditions[0]


def _result_to_dict(r) -> dict:
    return {
        "doc_title": r.doc_title,
        "authors": r.authors,
        "year": r.year,
        "citation_key": r.citation_key,
        "publication": r.publication,
        "page": r.page_num,
        "relevance_score": round(r.score, 3),
        "passage": r.text,
        "context_before": r.context_before,
        "context_after": r.context_after,
        "full_context": r.full_context(),
        "doc_id": r.doc_id,
        "chunk_index": r.chunk_index,
    }


@mcp.tool()
def search_papers(
    query: str,
    top_k: int = 10,
    context_chunks: int = 1,
    year_min: int | None = None,
    year_max: int | None = None
) -> list[dict]:
    """
    Semantic search over research paper chunks.

    Returns relevant passages with surrounding context.

    Args:
        query: Natural language search query
        top_k: Number of results (1-50)
        context_chunks: Adjacent chunks to include (0-3)
        year_min: Minimum publication year filter
        year_max: Maximum publication year filter

    Returns:
        List of results with passage text, context, and metadata
    """
    retriever = _get_retriever()
    results = retriever.search(
        query=query,
        top_k=min(top_k, 50),
        context_window=min(context_chunks, 3),
        filters=_build_year_filters(year_min, year_max)
    )
    return [_result_to_dict(r) for r in results]


@mcp.tool()
def search_topic(
    query: str,
    num_papers: int = 10,
    year_min: int | None = None,
    year_max: int | None = None
) -> list[dict]:
    """
    Find the most relevant papers for a topic, deduplicated by document.

    Searches across all chunks, then groups by paper. Each paper is scored
    by both its average chunk relevance (overall topical fit) and its best
    single chunk (strongest individual passage). Results are sorted by
    average score.

    Args:
        query: Natural language topic description
        num_papers: Number of distinct papers to return (1-50)
        year_min: Minimum publication year filter
        year_max: Maximum publication year filter

    Returns:
        List of per-paper results with scores and best passage
    """
    retriever = _get_retriever()
    # Fetch more chunks than papers requested to ensure enough docs
    results = retriever.search(
        query=query,
        top_k=min(num_papers * 5, 200),
        context_window=1,
        filters=_build_year_filters(year_min, year_max)
    )

    # Group by document
    by_doc: dict[str, list] = defaultdict(list)
    for r in results:
        by_doc[r.doc_id].append(r)

    # Score and rank papers
    paper_results = []
    for doc_id, hits in by_doc.items():
        scores = [h.score for h in hits]
        avg_score = sum(scores) / len(scores)
        best_hit = max(hits, key=lambda h: h.score)

        paper_results.append({
            "doc_id": doc_id,
            "doc_title": best_hit.doc_title,
            "authors": best_hit.authors,
            "year": best_hit.year,
            "citation_key": best_hit.citation_key,
            "publication": best_hit.publication,
            "avg_score": round(avg_score, 3),
            "best_chunk_score": round(best_hit.score, 3),
            "num_relevant_chunks": len(hits),
            "best_passage": best_hit.text,
            "best_passage_page": best_hit.page_num,
            "best_passage_context": best_hit.full_context(),
        })

    paper_results.sort(key=lambda p: p["avg_score"], reverse=True)
    return paper_results[:num_papers]


@mcp.tool()
def get_passage_context(
    doc_id: str,
    chunk_index: int,
    window: int = 2
) -> dict:
    """
    Expand context around a specific passage.

    Use after search_papers to get more context.

    Args:
        doc_id: Document ID from search results
        chunk_index: Chunk index from search results
        window: Chunks before/after to include (1-5)
    """
    window = max(1, min(window, 5))
    store = _get_store()

    chunks = store.get_adjacent_chunks(doc_id, chunk_index, window=window)

    if not chunks:
        return {"error": f"No chunks found for doc_id={doc_id}"}

    return {
        "doc_id": doc_id,
        "doc_title": chunks[0].metadata.get("doc_title", "Unknown"),
        "citation_key": chunks[0].metadata.get("citation_key", ""),
        "center_chunk_index": chunk_index,
        "window": window,
        "passages": [
            {
                "chunk_index": c.metadata["chunk_index"],
                "page": c.metadata["page_num"],
                "text": c.text,
                "is_center": c.metadata["chunk_index"] == chunk_index,
            }
            for c in chunks
        ],
        "merged_text": "\n\n".join(c.text for c in chunks),
    }


@mcp.tool()
def get_index_stats() -> dict:
    """Get statistics about the indexed collection."""
    store = _get_store()
    doc_ids = store.get_indexed_doc_ids()
    total_chunks = store.count()

    return {
        "total_documents": len(doc_ids),
        "total_chunks": total_chunks,
        "avg_chunks_per_doc": round(total_chunks / len(doc_ids), 1) if doc_ids else 0,
    }


if __name__ == "__main__":
    mcp.run()
