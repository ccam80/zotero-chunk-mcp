"""Test extraction features against real academic papers.

Tests:
1. Find a figure of modelled vs measured HR data in response to pressure changes
2. Find a table of model-specific parameters
3. Confirm/refute: baseline sympathetic response increases with age (statistically significant)
"""
import sys
import tempfile
import shutil
import io
from pathlib import Path

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add source to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from zotero_chunk_rag.config import Config
from zotero_chunk_rag.pdf_extractor import PDFExtractor
from zotero_chunk_rag.chunker import Chunker
from zotero_chunk_rag.embedder import create_embedder
from zotero_chunk_rag.vector_store import VectorStore
from zotero_chunk_rag.retriever import Retriever
from zotero_chunk_rag.table_extractor import TableExtractor
from zotero_chunk_rag.figure_extractor import FigureExtractor
from zotero_chunk_rag.models import ZoteroItem


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "papers"


def create_test_config(tmp_dir: Path) -> Config:
    """Create a test config with local embeddings."""
    return Config(
        zotero_data_dir=Path("~/Zotero").expanduser(),  # Not used directly
        chroma_db_path=tmp_dir / "chroma",
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
        section_gap_fill_min_chars=2000,
        section_gap_fill_min_fraction=0.30,
        ocr_enabled="auto",
        ocr_language="eng",
        ocr_dpi=300,
        ocr_timeout=30.0,
        ocr_min_text_chars=50,
        tables_enabled=True,
        tables_min_rows=2,
        tables_min_cols=2,
        tables_caption_distance=50.0,
        figures_enabled=True,
        figures_min_size=100,
        quality_threshold_a=2000,
        quality_threshold_b=1000,
        quality_threshold_c=500,
        quality_threshold_d=100,
        quality_entropy_min=4.0,
        openalex_email=None,
    )


def create_mock_items() -> list[ZoteroItem]:
    """Create mock ZoteroItem objects for test PDFs."""
    items = []
    for i, pdf_path in enumerate(sorted(FIXTURES_DIR.glob("*.pdf")), 1):
        items.append(ZoteroItem(
            item_key=f"test_paper_{i}",
            title=f"Test Paper {i} ({pdf_path.stem})",
            authors="Unknown Authors",
            year=2020 + i,
            pdf_path=pdf_path,
            citation_key=f"testpaper{i}",
            publication="Test Journal",
        ))
    return items


def index_papers(config: Config, items: list[ZoteroItem]) -> tuple[VectorStore, int, int, int]:
    """Index papers directly without Zotero client.

    Returns: (store, total_chunks, total_tables, total_figures)
    """
    extractor = PDFExtractor()
    chunker = Chunker(
        chunk_size=config.chunk_size,
        overlap=config.chunk_overlap,
        gap_fill_min_chars=config.section_gap_fill_min_chars,
        gap_fill_min_fraction=config.section_gap_fill_min_fraction,
    )
    embedder = create_embedder(config)
    store = VectorStore(config.chroma_db_path, embedder)

    table_extractor = TableExtractor(
        min_rows=config.tables_min_rows,
        min_cols=config.tables_min_cols,
    )

    figures_dir = config.chroma_db_path.parent / "figures"
    figure_extractor = FigureExtractor(images_dir=figures_dir)

    total_chunks = 0
    total_tables = 0
    total_figures = 0

    for item in items:
        print(f"\nIndexing: {item.pdf_path.name}")

        # Extract text
        pages, stats = extractor.extract(item.pdf_path)
        print(f"  Pages: {len(pages)}, Stats: {stats}")

        if not pages:
            print(f"  SKIP: No pages extracted")
            continue

        total_chars = sum(len(p.text) for p in pages)
        print(f"  Total chars: {total_chars}")

        if total_chars == 0:
            print(f"  SKIP: No text extracted")
            continue

        # Chunk
        chunks = chunker.chunk(pages)
        print(f"  Chunks: {len(chunks)}")

        if not chunks:
            print(f"  SKIP: No chunks created")
            continue

        # Store text chunks
        doc_meta = {
            "title": item.title,
            "authors": item.authors,
            "year": item.year,
            "citation_key": item.citation_key,
            "publication": item.publication,
            "journal_quartile": "",
            "doi": "",
            "tags": "",
            "collections": "",
            "pdf_hash": "test",
            "quality_grade": "B",
        }
        store.add_chunks(item.item_key, doc_meta, chunks)
        total_chunks += len(chunks)

        # Extract tables
        try:
            # First check raw table count
            raw_count = table_extractor.get_table_count(item.pdf_path)
            print(f"  Raw tables found (before filtering): {raw_count}")

            tables = table_extractor.extract_tables(item.pdf_path)
            if tables:
                store.add_tables(item.item_key, doc_meta, tables)
                total_tables += len(tables)
                print(f"  Tables after filtering: {len(tables)}")
                for t in tables:
                    cap = t.caption[:50] if t.caption else 'None'
                    print(f"    - Page {t.page_num}: {t.num_rows}x{t.num_cols}, caption={cap}...")
            else:
                print(f"  Tables after filtering: 0 (all filtered out or no captions)")
        except Exception as e:
            import traceback
            print(f"  Table extraction error: {e}")
            traceback.print_exc()

        # Extract figures
        try:
            figures = figure_extractor.extract_figures(item.pdf_path, item.item_key)
            if figures:
                store.add_figures(item.item_key, doc_meta, figures)
                total_figures += len(figures)
                print(f"  Figures: {len(figures)}")
                for f in figures:
                    cap = f.caption[:50] if f.caption else 'No caption'
                    print(f"    - Page {f.page_num}: {cap}...")
        except Exception as e:
            import traceback
            print(f"  Figure extraction error: {e}")
            traceback.print_exc()

    return store, total_chunks, total_tables, total_figures


def search_text(store: VectorStore, query: str, top_k: int = 5) -> list:
    """Search text chunks."""
    retriever = Retriever(store)
    results = retriever.search(query, top_k=top_k, context_window=1)
    return results


def search_tables(store: VectorStore, query: str, top_k: int = 5) -> list:
    """Search tables."""
    filters = {"chunk_type": {"$eq": "table"}}
    results = store.search(query, top_k=top_k, filters=filters)
    return results


def search_figures(store: VectorStore, query: str, top_k: int = 5) -> list:
    """Search figures by caption."""
    filters = {"chunk_type": {"$eq": "figure"}}
    results = store.search(query, top_k=top_k, filters=filters)
    return results


def run_tests():
    """Run all tests."""
    # Check fixtures exist
    pdfs = list(FIXTURES_DIR.glob("*.pdf"))
    if not pdfs:
        print(f"ERROR: No PDFs found in {FIXTURES_DIR}")
        print("Please add real academic papers to tests/fixtures/papers/")
        return

    print(f"Found {len(pdfs)} PDFs to test:")
    for p in pdfs:
        print(f"  - {p.name}")

    # Create temp directory
    tmp_dir = Path(tempfile.mkdtemp(prefix="zotero_rag_test_"))
    print(f"\nUsing temp directory: {tmp_dir}")

    try:
        # Setup
        config = create_test_config(tmp_dir)
        items = create_mock_items()

        # Index
        print("\n" + "="*60)
        print("INDEXING PAPERS")
        print("="*60)
        store, total_chunks, total_tables, total_figures = index_papers(config, items)

        print(f"\n--- Index Summary ---")
        print(f"Total text chunks: {total_chunks}")
        print(f"Total tables: {total_tables}")
        print(f"Total figures: {total_figures}")

        # Test 1: Find figure of modelled vs measured HR data
        print("\n" + "="*60)
        print("TEST 1: Find figure of modelled vs measured HR data")
        print("="*60)
        query1 = "figure showing modelled versus measured heart rate data in response to pressure changes"
        fig_results = search_figures(store, query1)

        if fig_results:
            print(f"Found {len(fig_results)} matching figures:")
            for r in fig_results[:3]:
                print(f"\n  Score: {r.score:.3f}")
                caption_preview = r.text[:200].encode('utf-8', errors='replace').decode('utf-8')
                print(f"  Caption: {caption_preview}...")
                print(f"  Image: {r.metadata.get('image_path', 'N/A')}")
        else:
            print("No figures found. Trying text search for figure references...")
            text_results = search_text(store, query1)
            for r in text_results[:3]:
                print(f"\n  Score: {r.score:.3f}")
                print(f"  Section: {r.section}")
                text_preview = r.text[:300].encode('utf-8', errors='replace').decode('utf-8')
                print(f"  Text: {text_preview}...")

        # Test 2: Find table of model-specific parameters
        print("\n" + "="*60)
        print("TEST 2: Find table of model-specific parameters")
        print("="*60)
        query2 = "table of model parameters values coefficients settings"
        tbl_results = search_tables(store, query2)

        if tbl_results:
            print(f"Found {len(tbl_results)} matching tables:")
            for r in tbl_results[:3]:
                print(f"\n  Score: {r.score:.3f}")
                print(f"  Caption: {r.metadata.get('table_caption', 'N/A')}")
                print(f"  Size: {r.metadata.get('table_num_rows', '?')}x{r.metadata.get('table_num_cols', '?')}")
                print(f"  Content preview:")
                # Show first few lines of markdown
                lines = r.text.split('\n')[:6]
                for line in lines:
                    line_clean = line.encode('utf-8', errors='replace').decode('utf-8')
                    print(f"    {line_clean}")
        else:
            print("No tables found in index. Trying text search for table references...")
            text_results = search_text(store, query2)
            for r in text_results[:3]:
                print(f"\n  Score: {r.score:.3f}")
                print(f"  Section: {r.section}")
                # Truncate and encode safely
                text_preview = r.text[:300].encode('utf-8', errors='replace').decode('utf-8')
                print(f"  Text: {text_preview}...")

        # Test 3: Sympathetic response and age
        print("\n" + "="*60)
        print("TEST 3: Baseline sympathetic response vs age")
        print("="*60)
        query3 = "baseline sympathetic response age statistically significant increased"
        text_results = search_text(store, query3, top_k=10)

        print(f"Found {len(text_results)} relevant passages:")
        for r in text_results[:5]:
            print(f"\n  Score: {r.score:.3f}")
            print(f"  Section: {r.section} (confidence: {r.section_confidence:.2f})")
            print(f"  Doc: {r.doc_title}")
            text_preview = r.text[:400].encode('utf-8', errors='replace').decode('utf-8')
            print(f"  Text: {text_preview}...")

        # Look for statistical evidence - broader search
        print("\n--- Analysis ---")
        evidence_passages = []
        for r in text_results:
            text_lower = r.text.lower()

            # Check for statistical terms
            has_stats = any(term in text_lower for term in [
                "p <", "p=", "p =", "significant", "p-value", "p value",
                "0.05", "0.01", "0.001", "table 2", "table 3"
            ])

            # Check for age-related terms
            has_age = any(term in text_lower for term in [
                "age", "aging", "ageing", "older", "elderly", "young"
            ])

            # Check for sympathetic terms
            has_sympathetic = any(term in text_lower for term in [
                "sympathetic", "sns", "autonomic", "baroreﬂex", "baroreflex",
                "baseline", "response"
            ])

            if has_age and has_sympathetic:
                evidence_passages.append((r, has_stats))

        if evidence_passages:
            print(f"Found {len(evidence_passages)} passages discussing sympathetic response and age:")
            for r, has_stats in evidence_passages[:5]:
                stat_marker = "[STATISTICAL]" if has_stats else ""
                print(f"\n  {stat_marker} Score: {r.score:.3f}, Section: {r.section}")
                text_preview = r.text[:400].encode('utf-8', errors='replace').decode('utf-8')
                print(f"  {text_preview}...")

            # Summarize findings
            stat_count = sum(1 for _, has_stats in evidence_passages if has_stats)
            print(f"\n--- Summary ---")
            print(f"Total relevant passages: {len(evidence_passages)}")
            print(f"Passages with statistical terms: {stat_count}")

            # Look for specific claims
            for r, _ in evidence_passages:
                text_lower = r.text.lower()
                if "increased with age" in text_lower or "increase with age" in text_lower:
                    print("\nFOUND: Claim that something INCREASES with age")
                    text_preview = r.text[:300].encode('utf-8', errors='replace').decode('utf-8')
                    print(f"  {text_preview}...")
                if "diminished" in text_lower or "decreased" in text_lower:
                    print("\nFOUND: Claim about DIMINISHED/DECREASED response")
                    text_preview = r.text[:300].encode('utf-8', errors='replace').decode('utf-8')
                    print(f"  {text_preview}...")
        else:
            print("No passages found discussing sympathetic response and age.")

        print("\n" + "="*60)
        print("TESTS COMPLETE")
        print("="*60)

    finally:
        # Cleanup
        print(f"\nCleaning up temp directory: {tmp_dir}")
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    run_tests()
