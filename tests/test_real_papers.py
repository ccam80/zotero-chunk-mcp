"""End-to-end tests against real academic papers."""
from pathlib import Path
from zotero_chunk_rag.pdf_processor import extract_document
from zotero_chunk_rag.chunker import Chunker
from zotero_chunk_rag.config import Config
from zotero_chunk_rag.embedder import create_embedder
from zotero_chunk_rag.vector_store import VectorStore
from zotero_chunk_rag.retriever import Retriever

FIXTURES = Path(__file__).parent / "fixtures" / "papers"


def _create_test_config(tmp_path: Path) -> Config:
    zotero_dir = tmp_path / "zotero"
    zotero_dir.mkdir(exist_ok=True)
    (zotero_dir / "zotero.sqlite").touch()
    return Config(
        zotero_data_dir=zotero_dir,
        chroma_db_path=tmp_path / "chroma",
        embedding_model="all-MiniLM-L6-v2",
        embedding_dimensions=384,
        chunk_size=400,
        chunk_overlap=100,
        gemini_api_key=None,
        embedding_provider="local",
        embedding_timeout=120.0,
        embedding_max_retries=3,
        rerank_alpha=0.7,
        rerank_section_weights=None,
        rerank_journal_weights=None,
        rerank_enabled=True,
        oversample_multiplier=3,
        oversample_topic_factor=5,
        stats_sample_limit=10000,
        ocr_language="eng",
        tables_enabled=True,
        table_strategy="lines_strict",
        image_size_limit=0.05,
        figures_enabled=True,
        figures_min_size=100,
        quality_threshold_a=2000,
        quality_threshold_b=1000,
        quality_threshold_c=500,
        quality_threshold_d=100,
        quality_entropy_min=4.0,
        openalex_email=None,
    )


def test_all_papers_produce_multiple_sections():
    for pdf_name in ["noname1.pdf", "noname2.pdf", "noname3.pdf"]:
        ex = extract_document(FIXTURES / pdf_name)
        chunker = Chunker(chunk_size=400, overlap=100)
        chunks = chunker.chunk(ex.full_markdown, ex.pages, ex.sections)
        sections_found = set(c.section for c in chunks)
        assert len(sections_found) >= 3, f"{pdf_name}: only {len(sections_found)} sections in chunks: {sections_found}"


def test_all_papers_produce_enough_chunks():
    for pdf_name in ["noname1.pdf", "noname2.pdf", "noname3.pdf"]:
        ex = extract_document(FIXTURES / pdf_name)
        chunker = Chunker(chunk_size=400, overlap=100)
        chunks = chunker.chunk(ex.full_markdown, ex.pages, ex.sections)
        assert len(chunks) > 20, f"{pdf_name}: only {len(chunks)} chunks"


def test_full_pipeline_retriever(tmp_path):
    """Full pipeline: extract -> chunk -> embed -> store -> retriever.search() returns results."""
    config = _create_test_config(tmp_path)
    ex = extract_document(FIXTURES / "noname1.pdf")
    chunker = Chunker(chunk_size=400, overlap=100)
    chunks = chunker.chunk(ex.full_markdown, ex.pages, ex.sections)

    embedder = create_embedder(config)
    store = VectorStore(config.chroma_db_path, embedder)
    doc_meta = {
        "title": "Test Paper", "authors": "Test Author", "year": 2020,
        "citation_key": "test2020", "publication": "Test Journal",
        "journal_quartile": "", "doi": "", "tags": "", "collections": "",
        "pdf_hash": "test", "quality_grade": ex.quality_grade,
    }
    store.add_chunks("test_noname1", doc_meta, chunks)

    retriever = Retriever(store)
    results = retriever.search("ECG modeling", top_k=5)
    assert len(results) > 0
