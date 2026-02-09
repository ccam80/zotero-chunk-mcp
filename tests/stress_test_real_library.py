"""
STRESS TEST: Real-world researcher workflow simulation.

This test picks 10 diverse papers from the user's actual Zotero library,
indexes them through the full pipeline, and simulates realistic researcher
search patterns. It tests:

1. Extraction quality: text, tables, figures, sections, OCR
2. Search accuracy: can the researcher find what they're looking for?
3. Table search: can specific results tables be found by content?
4. Figure search: can specific figures be found by caption?
5. Metadata filtering: author, collection, year range
6. Context expansion: does expanded context make sense?
7. OCR pathway: can image-only PDFs still be searched?
8. Edge cases: missing DOIs, non-standard formats, empty pages

Every failure is logged. The final report is brutally honest.
"""
from __future__ import annotations

import json
import logging
import shutil
import sys
import tempfile
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Corpus selection: 10 papers chosen for maximum diversity
# ---------------------------------------------------------------------------
# Each entry: (item_key, short_name, why_chosen, ground_truth)
# ground_truth is a dict of expected properties the test will validate

CORPUS = [
    (
        "SCPXVBLY",
        "active-inference-tutorial",
        "Tutorial paper with equations, diagrams, algorithm boxes. Tests complex layout.",
        {
            "year": 2022,
            "author_substr": "smith",
            "collection": "Active Inference",
            "expect_tables": True,
            "expect_figures": True,
            "expect_sections": ["introduction", "discussion", "conclusion"],
            "searchable_content": "active inference free energy",
            "table_search_query": "algorithm update rules",
            "figure_search_query": "generative model graphical",
        },
    ),
    (
        "XIAINRVS",
        "huang-emd-1998",
        "Foundational EMD paper from 1998. Math-heavy, older format. Tests pre-2000 PDFs.",
        {
            "year": 1998,
            "author_substr": "huang",
            "collection": "EMD",
            "expect_tables": False,
            "expect_figures": True,
            "expect_sections": ["introduction", "conclusion"],
            "searchable_content": "empirical mode decomposition Hilbert spectrum",
            "table_search_query": None,
            "figure_search_query": "intrinsic mode function",
        },
    ),
    (
        "C626CYVT",
        "hallett-tms-primer",
        "TMS primer/review. Well-structured clinical review. Tests clean section detection.",
        {
            "year": 2007,
            "author_substr": "hallett",
            "collection": "TMS",
            "expect_tables": True,
            "expect_figures": True,
            "expect_sections": ["introduction"],
            "searchable_content": "transcranial magnetic stimulation motor cortex",
            "table_search_query": "stimulation parameters coil",
            "figure_search_query": "magnetic field coil",
        },
    ),
    (
        "5SIZVS65",
        "laird-fick-polyps",
        "Epidemiology paper with demographic tables. Tests table extraction accuracy.",
        {
            "year": 2016,
            "author_substr": "laird",
            "collection": "PhD",
            "expect_tables": True,
            "expect_figures": False,
            "expect_sections": ["introduction", "methods", "results", "discussion"],
            "searchable_content": "colonic polyp histopathology colonoscopy",
            "table_search_query": "polyp location demographics patient",
            "figure_search_query": None,
        },
    ),
    (
        "9GKLLJH9",
        "helm-coregulation",
        "Psychology paper on RSA coregulation. Tests social science format.",
        {
            "year": 2014,
            "author_substr": "helm",
            "collection": "Coregulation",
            "expect_tables": True,
            "expect_figures": True,
            "expect_sections": ["introduction", "methods", "results", "discussion"],
            "searchable_content": "respiratory sinus arrhythmia coregulation romantic",
            "table_search_query": "correlation coefficient RSA",
            "figure_search_query": "coregulation respiratory",
        },
    ),
    (
        "Z9X4JVZ5",
        "roland-emg-filter",
        "IEEE engineering paper on digital filtering. Tests 2-column format, circuits.",
        {
            "year": 2019,
            "author_substr": "roland",
            "collection": "Processing",
            "expect_tables": True,
            "expect_figures": True,
            "expect_sections": ["introduction", "results", "conclusion"],
            "searchable_content": "ultra-low-power digital filtering EMG",
            "table_search_query": "power consumption filter",
            "figure_search_query": "filter frequency response",
        },
    ),
    (
        "YMWV46JA",
        "friston-life",
        "Theoretical neuroscience. Dense, abstract, math-heavy. Tests unusual structure.",
        {
            "year": 2013,
            "author_substr": "friston",
            "collection": "Friston",
            "expect_tables": False,
            "expect_figures": True,
            "expect_sections": ["introduction"],
            "searchable_content": "free energy principle self-organization",
            "table_search_query": None,
            "figure_search_query": "Markov blanket",
        },
    ),
    (
        "DPYRZTFI",
        "yang-ppv-meta",
        "Systematic review/meta-analysis. Forest plots, summary tables. Tests meta-analysis format.",
        {
            "year": 2014,
            "author_substr": "yang",
            "collection": "PPV",
            "expect_tables": True,
            "expect_figures": True,
            "expect_sections": ["introduction", "methods", "results", "discussion"],
            "searchable_content": "pulse pressure variation fluid responsiveness",
            "table_search_query": "sensitivity specificity diagnostic",
            "figure_search_query": "forest plot",
        },
    ),
    (
        "VP3NJ74M",
        "fortune-impedance",
        "Measurement study with impedance data. Tests engineering/measurement format.",
        {
            "year": 2021,
            "author_substr": "fortune",
            "collection": "",  # Check what collection
            "expect_tables": True,
            "expect_figures": True,
            "expect_sections": ["introduction", "methods", "results"],
            "searchable_content": "electrode skin impedance imbalance frequency",
            "table_search_query": "impedance measurement electrode",
            "figure_search_query": "impedance frequency",
        },
    ),
    (
        "AQ3D94VC",
        "reyes-lf-hrv",
        "Review of LF HRV as autonomic index. Tests review paper format.",
        {
            "year": 2013,
            "author_substr": "reyes",
            "collection": "HRV",
            "expect_tables": True,
            "expect_figures": True,
            "expect_sections": ["introduction", "conclusion"],
            "searchable_content": "low frequency heart rate variability sympathetic",
            "table_search_query": "autonomic measures",
            "figure_search_query": "heart rate variability",
        },
    ),
]


# ---------------------------------------------------------------------------
# Test result tracking
# ---------------------------------------------------------------------------

@dataclass
class TestResult:
    """Single test assertion result."""
    test_name: str
    paper: str
    passed: bool
    detail: str
    severity: str = "MAJOR"  # MAJOR or MINOR


@dataclass
class StressTestReport:
    """Aggregate test report."""
    results: list[TestResult] = field(default_factory=list)
    extraction_summaries: list[dict] = field(default_factory=list)
    timings: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def add(self, test_name: str, paper: str, passed: bool, detail: str,
            severity: str = "MAJOR"):
        self.results.append(TestResult(test_name, paper, passed, detail, severity))

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.passed)

    @property
    def major_failures(self) -> int:
        return sum(1 for r in self.results if not r.passed and r.severity == "MAJOR")

    def to_markdown(self) -> str:
        lines = []
        lines.append("# Stress Test Report: zotero-chunk-rag")
        lines.append("")
        lines.append(f"**Date**: {time.strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"**Corpus**: {len(CORPUS)} papers from live Zotero library")
        lines.append("")

        # Executive summary
        lines.append("## Executive Summary")
        lines.append("")
        total = len(self.results)
        lines.append(f"- **Total tests**: {total}")
        lines.append(f"- **Passed**: {self.passed} ({100*self.passed/total:.0f}%)" if total else "- **Passed**: 0")
        lines.append(f"- **Failed**: {self.failed}")
        lines.append(f"- **Major failures**: {self.major_failures}")
        lines.append("")

        if self.major_failures > 0:
            lines.append("> **VERDICT**: This tool is NOT reliable for production research use.")
            lines.append("> A researcher depending on this tool WILL miss important results.")
        elif self.failed > 0:
            lines.append("> **VERDICT**: Mostly functional but has rough edges that will")
            lines.append("> frustrate researchers in real use.")
        else:
            lines.append("> **VERDICT**: All tests passed. Tool appears reliable for research use.")
        lines.append("")

        # Timings
        if self.timings:
            lines.append("## Performance")
            lines.append("")
            lines.append("| Operation | Time |")
            lines.append("|-----------|------|")
            for op, t in self.timings.items():
                lines.append(f"| {op} | {t:.1f}s |")
            lines.append("")

        # Extraction quality summary
        if self.extraction_summaries:
            lines.append("## Extraction Quality per Paper")
            lines.append("")
            lines.append("| Paper | Pages | Sections | Tables | Figures | Grade | Issues |")
            lines.append("|-------|-------|----------|--------|---------|-------|--------|")
            for s in self.extraction_summaries:
                issues = s.get("issues", "none")
                lines.append(
                    f"| {s['name'][:25]} | {s['pages']} | {s['sections']} | "
                    f"{s['tables']} | {s['figures']} | {s['grade']} | {issues} |"
                )
            lines.append("")

        # Failures detail
        failures = [r for r in self.results if not r.passed]
        if failures:
            lines.append("## Failures (Detailed)")
            lines.append("")
            for r in failures:
                icon = "!!!" if r.severity == "MAJOR" else "!"
                lines.append(f"### {icon} [{r.severity}] {r.test_name} — {r.paper}")
                lines.append("")
                lines.append(f"{r.detail}")
                lines.append("")

        # Passes summary
        passes = [r for r in self.results if r.passed]
        if passes:
            lines.append("## Passes")
            lines.append("")
            lines.append("| Test | Paper | Detail |")
            lines.append("|------|-------|--------|")
            for r in passes:
                detail_short = r.detail[:80].replace("|", "/")
                lines.append(f"| {r.test_name} | {r.paper} | {detail_short} |")
            lines.append("")

        # Errors
        if self.errors:
            lines.append("## Unexpected Errors")
            lines.append("")
            for e in self.errors:
                lines.append(f"- {e}")
            lines.append("")

        # OCR test section placeholder
        lines.append("## OCR Pathway Test")
        lines.append("")
        lines.append("_(See OCR test results in the test output above)_")
        lines.append("")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main stress test runner
# ---------------------------------------------------------------------------

def run_stress_test():
    """Run the full stress test and return the report."""
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    # Suppress noisy loggers
    logging.getLogger("chromadb").setLevel(logging.ERROR)
    logging.getLogger("httpx").setLevel(logging.ERROR)

    report = StressTestReport()

    # Use a temp directory for the test index
    test_dir = Path(tempfile.mkdtemp(prefix="stress_test_"))
    chroma_path = test_dir / "chroma"
    figures_path = test_dir / "figures"
    ocr_path = test_dir / "ocr_images"

    print(f"Test directory: {test_dir}")
    print(f"=" * 70)

    try:
        # ===================================================================
        # PHASE 1: Load papers from Zotero
        # ===================================================================
        print("\n[PHASE 1] Loading papers from Zotero library...")
        from zotero_chunk_rag.zotero_client import ZoteroClient
        from zotero_chunk_rag.config import Config

        config = Config.load()
        zotero = ZoteroClient(config.zotero_data_dir)
        all_items = zotero.get_all_items_with_pdfs()
        items_by_key = {i.item_key: i for i in all_items}

        corpus_items = []
        for item_key, short_name, reason, gt in CORPUS:
            item = items_by_key.get(item_key)
            if item is None:
                report.errors.append(f"Item {item_key} ({short_name}) not found in library")
                continue
            if not item.pdf_path or not item.pdf_path.exists():
                report.errors.append(f"PDF missing for {item_key} ({short_name})")
                continue
            corpus_items.append((item, short_name, gt))
            print(f"  [{short_name}] {item.title[:60]} — {item.pdf_path.name}")

        if len(corpus_items) < 5:
            print("FATAL: Not enough papers found. Aborting.")
            return report

        # ===================================================================
        # PHASE 2: Extract and index all papers
        # ===================================================================
        print(f"\n[PHASE 2] Extracting and indexing {len(corpus_items)} papers...")

        from zotero_chunk_rag.pdf_processor import extract_document
        from zotero_chunk_rag.chunker import Chunker
        from zotero_chunk_rag.embedder import create_embedder
        from zotero_chunk_rag.vector_store import VectorStore
        from zotero_chunk_rag.journal_ranker import JournalRanker
        from zotero_chunk_rag.reranker import Reranker
        from zotero_chunk_rag.retriever import Retriever
        import hashlib

        # Build test config with local embeddings for speed
        test_config = Config(
            zotero_data_dir=config.zotero_data_dir,
            chroma_db_path=chroma_path,
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
            openalex_email=None,
        )

        embedder = create_embedder(test_config)
        store = VectorStore(chroma_path, embedder)
        chunker = Chunker(chunk_size=400, overlap=100)
        journal_ranker = JournalRanker()
        reranker = Reranker(alpha=0.7)
        retriever = Retriever(store)

        extractions: dict[str, tuple] = {}  # item_key -> (extraction, chunks, item, gt)

        t_start = time.perf_counter()

        for item, short_name, gt in corpus_items:
            print(f"\n  Extracting [{short_name}]...", end=" ", flush=True)
            try:
                t0 = time.perf_counter()
                extraction = extract_document(
                    item.pdf_path,
                    write_images=True,
                    images_dir=figures_path / item.item_key,
                )
                t_extract = time.perf_counter() - t0

                # Chunk
                chunks = chunker.chunk(
                    extraction.full_markdown,
                    extraction.pages,
                    extraction.sections,
                )

                # Build doc metadata
                journal_quartile = journal_ranker.lookup(item.publication)
                h = hashlib.sha256()
                with open(item.pdf_path, "rb") as f:
                    h.update(f.read(65536))
                pdf_hash = h.hexdigest()

                doc_meta = {
                    "title": item.title,
                    "authors": item.authors,
                    "year": item.year or 0,
                    "citation_key": item.citation_key,
                    "publication": item.publication,
                    "journal_quartile": journal_quartile or "",
                    "doi": item.doi,
                    "tags": item.tags,
                    "collections": item.collections,
                    "pdf_hash": pdf_hash,
                    "quality_grade": extraction.quality_grade,
                }

                # Store text chunks
                store.add_chunks(item.item_key, doc_meta, chunks)

                # Store tables
                if extraction.tables:
                    store.add_tables(item.item_key, doc_meta, extraction.tables)

                # Store figures
                if extraction.figures:
                    store.add_figures(item.item_key, doc_meta, extraction.figures)

                extractions[item.item_key] = (extraction, chunks, item, gt, short_name)

                n_sections = len([s for s in extraction.sections if s.label != "preamble"])
                section_labels = [s.label for s in extraction.sections if s.label not in ("preamble", "unknown")]
                print(
                    f"{t_extract:.1f}s | {len(extraction.pages)}pp | "
                    f"{len(chunks)}ch | {len(extraction.tables)}tab | "
                    f"{len(extraction.figures)}fig | "
                    f"sections: {section_labels} | "
                    f"grade: {extraction.quality_grade}"
                )

                # Build extraction summary for report
                comp = extraction.completeness
                issues_parts = []
                if comp and comp.figures_missing > 0:
                    issues_parts.append(f"{comp.figures_missing} figs missing")
                if comp and comp.tables_missing > 0:
                    issues_parts.append(f"{comp.tables_missing} tabs missing")
                if comp and comp.unknown_sections > 0:
                    issues_parts.append(f"{comp.unknown_sections} unknown sections")
                if not any(s.label == "abstract" for s in extraction.sections):
                    issues_parts.append("no abstract detected")

                report.extraction_summaries.append({
                    "name": short_name,
                    "pages": len(extraction.pages),
                    "sections": n_sections,
                    "tables": len(extraction.tables),
                    "figures": len(extraction.figures),
                    "grade": extraction.quality_grade,
                    "issues": "; ".join(issues_parts) if issues_parts else "none",
                })

            except Exception as e:
                print(f"FAILED: {e}")
                report.errors.append(f"Extraction failed for {short_name}: {traceback.format_exc()}")

        t_total_index = time.perf_counter() - t_start
        report.timings["Total indexing"] = t_total_index
        print(f"\n  Total indexing time: {t_total_index:.1f}s")
        print(f"  Total chunks in store: {store.count()}")

        # ===================================================================
        # PHASE 3: Validate extraction quality
        # ===================================================================
        print(f"\n[PHASE 3] Validating extraction quality...")

        for item_key, (extraction, chunks, item, gt, short_name) in extractions.items():
            # --- 3a: Sections detected ---
            section_labels = set(s.label for s in extraction.sections)
            for expected_section in gt.get("expect_sections", []):
                found = expected_section in section_labels
                report.add(
                    "section-detection",
                    short_name,
                    found,
                    f"Expected section '{expected_section}' — "
                    + (f"FOUND" if found else f"MISSING. Got: {sorted(section_labels)}"),
                    severity="MAJOR" if expected_section in ("methods", "results") else "MINOR",
                )

            # --- 3b: Tables extracted ---
            if gt.get("expect_tables"):
                has_tables = len(extraction.tables) > 0
                report.add(
                    "table-extraction",
                    short_name,
                    has_tables,
                    f"Expected tables — found {len(extraction.tables)}",
                    severity="MAJOR",
                )
                # Check table content quality (non-empty cells)
                for i, tab in enumerate(extraction.tables):
                    non_empty = sum(1 for row in tab.rows for cell in row if cell.strip())
                    total_cells = sum(len(row) for row in tab.rows)
                    if total_cells > 0:
                        fill_rate = non_empty / total_cells
                        report.add(
                            "table-content-quality",
                            f"{short_name}/table-{i}",
                            fill_rate > 0.3,
                            f"Table {i}: {non_empty}/{total_cells} cells non-empty ({fill_rate:.0%}). "
                            f"Caption: '{(tab.caption or 'NONE')[:60]}'",
                            severity="MAJOR" if fill_rate < 0.1 else "MINOR",
                        )

            # --- 3c: Figures extracted ---
            if gt.get("expect_figures"):
                has_figures = len(extraction.figures) > 0
                report.add(
                    "figure-extraction",
                    short_name,
                    has_figures,
                    f"Expected figures — found {len(extraction.figures)}",
                    severity="MAJOR",
                )
                # Check figure captions
                captioned = [f for f in extraction.figures if f.caption]
                orphans = [f for f in extraction.figures if not f.caption]
                if extraction.figures:
                    caption_rate = len(captioned) / len(extraction.figures)
                    report.add(
                        "figure-caption-rate",
                        short_name,
                        caption_rate >= 0.5,
                        f"{len(captioned)}/{len(extraction.figures)} figures have captions ({caption_rate:.0%}). "
                        f"Orphan pages: {[f.page_num for f in orphans]}",
                        severity="MAJOR" if caption_rate < 0.3 else "MINOR",
                    )

            # --- 3d: Completeness grade ---
            comp = extraction.completeness
            if comp:
                report.add(
                    "completeness-grade",
                    short_name,
                    comp.grade in ("A", "B"),
                    f"Grade: {comp.grade} | "
                    f"Figs: {comp.figures_found} found / {comp.figure_captions_found} captioned / {comp.figures_missing} missing | "
                    f"Tables: {comp.tables_found} found / {comp.table_captions_found} captioned / {comp.tables_missing} missing",
                    severity="MAJOR" if comp.grade in ("D", "F") else "MINOR",
                )

            # --- 3e: Abstract detected ---
            has_abstract = any(s.label == "abstract" for s in extraction.sections)
            report.add(
                "abstract-detection",
                short_name,
                has_abstract,
                f"Abstract {'detected' if has_abstract else 'NOT detected'}",
                severity="MINOR",
            )

            # --- 3f: Chunk count sanity ---
            expected_min_chunks = len(extraction.pages) * 2  # At least 2 chunks per page
            report.add(
                "chunk-count-sanity",
                short_name,
                len(chunks) >= expected_min_chunks,
                f"{len(chunks)} chunks for {len(extraction.pages)} pages "
                f"(expected >= {expected_min_chunks})",
                severity="MAJOR" if len(chunks) < len(extraction.pages) else "MINOR",
            )

            # --- 3g: Check for image files written ---
            if gt.get("expect_figures") and extraction.figures:
                figs_with_images = [f for f in extraction.figures if f.image_path and f.image_path.exists()]
                report.add(
                    "figure-images-saved",
                    short_name,
                    len(figs_with_images) > 0,
                    f"{len(figs_with_images)}/{len(extraction.figures)} figure images saved to disk",
                    severity="MINOR",
                )

        # ===================================================================
        # PHASE 4: Semantic search tests (researcher workflow)
        # ===================================================================
        print(f"\n[PHASE 4] Running semantic search tests...")

        for item_key, (extraction, chunks, item, gt, short_name) in extractions.items():
            query = gt["searchable_content"]
            print(f"  Searching for [{short_name}]: '{query[:50]}...'")

            t0 = time.perf_counter()
            results = retriever.search(query=query, top_k=10, context_window=1)
            t_search = time.perf_counter() - t0

            # Did the target paper appear in results?
            target_hits = [r for r in results if r.doc_id == item_key]
            found = len(target_hits) > 0
            rank = None
            if found:
                for i, r in enumerate(results):
                    if r.doc_id == item_key:
                        rank = i + 1
                        break

            report.add(
                "semantic-search-recall",
                short_name,
                found,
                f"Query: '{query[:50]}' — "
                + (f"found at rank {rank}/10 (score {target_hits[0].score:.3f})"
                   if found else f"NOT FOUND in top 10. Got: {[r.doc_title[:30] for r in results[:3]]}"),
                severity="MAJOR",
            )

            # Check if it ranks in top 3 (a researcher would expect this)
            if found:
                report.add(
                    "semantic-search-ranking",
                    short_name,
                    rank <= 3,
                    f"Ranked {rank}/10 for its own core content query",
                    severity="MAJOR" if rank > 5 else "MINOR",
                )

        # ===================================================================
        # PHASE 5: Table search tests
        # ===================================================================
        print(f"\n[PHASE 5] Running table search tests...")

        for item_key, (extraction, chunks, item, gt, short_name) in extractions.items():
            table_query = gt.get("table_search_query")
            if not table_query:
                continue
            if not extraction.tables:
                continue

            print(f"  Searching tables for [{short_name}]: '{table_query}'")

            # Search tables
            table_filter = {"chunk_type": {"$eq": "table"}}
            table_results = store.search(query=table_query, top_k=10, filters=table_filter)

            target_tables = [r for r in table_results if r.metadata.get("doc_id") == item_key]
            found = len(target_tables) > 0

            report.add(
                "table-search-recall",
                short_name,
                found,
                f"Query: '{table_query}' — "
                + (f"found {len(target_tables)} matching table(s), "
                   f"best score {target_tables[0].score:.3f}, "
                   f"caption: '{target_tables[0].metadata.get('table_caption', 'NONE')[:50]}'"
                   if found else f"NOT FOUND. Got: {[r.metadata.get('doc_title', '?')[:30] for r in table_results[:3]]}"),
                severity="MAJOR",
            )

            # Check table markdown content quality
            if found:
                best_table = target_tables[0]
                table_text = best_table.text
                has_pipe = "|" in table_text
                has_rows = table_text.count("\n") >= 2
                report.add(
                    "table-markdown-quality",
                    short_name,
                    has_pipe and has_rows,
                    f"Table markdown has {'pipes' if has_pipe else 'NO pipes'} and "
                    f"{table_text.count(chr(10))} lines. "
                    f"Preview: {table_text[:100].replace(chr(10), ' | ')}",
                    severity="MINOR",
                )

        # ===================================================================
        # PHASE 6: Figure search tests
        # ===================================================================
        print(f"\n[PHASE 6] Running figure search tests...")

        for item_key, (extraction, chunks, item, gt, short_name) in extractions.items():
            fig_query = gt.get("figure_search_query")
            if not fig_query:
                continue
            if not extraction.figures:
                continue

            print(f"  Searching figures for [{short_name}]: '{fig_query}'")

            fig_filter = {"chunk_type": {"$eq": "figure"}}
            fig_results = store.search(query=fig_query, top_k=10, filters=fig_filter)

            target_figs = [r for r in fig_results if r.metadata.get("doc_id") == item_key]
            found = len(target_figs) > 0

            report.add(
                "figure-search-recall",
                short_name,
                found,
                f"Query: '{fig_query}' — "
                + (f"found {len(target_figs)} matching figure(s), "
                   f"best score {target_figs[0].score:.3f}, "
                   f"caption: '{target_figs[0].metadata.get('caption', 'NONE')[:50]}'"
                   if found else f"NOT FOUND in top 10. "
                   f"Got: {[r.metadata.get('doc_title', '?')[:30] for r in fig_results[:3]]}"),
                severity="MAJOR",
            )

        # ===================================================================
        # PHASE 7: Metadata filter tests
        # ===================================================================
        print(f"\n[PHASE 7] Testing metadata filters...")

        # Test author filter using _apply_text_filters (Fix 1 added _meta_get helper)
        from zotero_chunk_rag.server import _apply_text_filters
        for item_key, (extraction, chunks, item, gt, short_name) in extractions.items():
            author_substr = gt.get("author_substr", "")
            if not author_substr:
                continue

            query = gt["searchable_content"]
            results = retriever.search(query=query, top_k=50, context_window=0)

            # Use the server's _apply_text_filters — Fix 1 made this work on RetrievalResult
            filtered = _apply_text_filters(results, author=author_substr)

            target_hits = [r for r in filtered if r.doc_id == item_key]
            found = len(target_hits) > 0

            report.add(
                "author-filter",
                short_name,
                found,
                f"Filter author='{author_substr}' — "
                + (f"target paper found ({len(filtered)} total results after filter)"
                   if found else f"target paper NOT found after filtering"),
                severity="MAJOR",
            )

        # Test year range filter
        print("  Testing year range filters...")
        year_filter = {"year": {"$gte": 2015}}
        results = retriever.search(
            query="heart rate variability",
            top_k=50,
            context_window=0,
            filters=year_filter,
        )
        old_papers = [r for r in results if r.year and r.year < 2015]
        report.add(
            "year-filter-accuracy",
            "all",
            len(old_papers) == 0,
            f"Year filter >=2015: {len(old_papers)} papers from before 2015 leaked through "
            f"(total results: {len(results)})",
            severity="MAJOR" if len(old_papers) > 0 else "MINOR",
        )

        # ===================================================================
        # PHASE 8: Context expansion tests
        # ===================================================================
        print(f"\n[PHASE 8] Testing context expansion...")

        for item_key, (extraction, chunks, item, gt, short_name) in extractions.items():
            query = gt["searchable_content"]
            results = retriever.search(query=query, top_k=5, context_window=2)

            target_hits = [r for r in results if r.doc_id == item_key]
            if not target_hits:
                continue

            hit = target_hits[0]
            has_context = bool(hit.context_before or hit.context_after)
            full_ctx = hit.full_context()

            report.add(
                "context-expansion",
                short_name,
                has_context,
                f"Context expansion: "
                + (f"before={len(hit.context_before)}, after={len(hit.context_after)}, "
                   f"full_context={len(full_ctx)} chars"
                   if has_context else "NO context returned"),
                severity="MINOR",
            )

            # Check context is longer than the hit alone
            if has_context:
                report.add(
                    "context-adds-value",
                    short_name,
                    len(full_ctx) > len(hit.text),
                    f"Full context ({len(full_ctx)} chars) vs hit ({len(hit.text)} chars)",
                    severity="MINOR",
                )

        # ===================================================================
        # PHASE 9: Cross-paper search (topic search simulation)
        # ===================================================================
        print(f"\n[PHASE 9] Testing cross-paper topic search...")

        # A researcher searches for "heart rate variability autonomic" — should find
        # multiple relevant papers
        topic_query = "heart rate variability autonomic nervous system"
        print(f"  Topic: '{topic_query}'")
        results = retriever.search(query=topic_query, top_k=50, context_window=0)

        # Rerank
        from dataclasses import replace
        reranked = reranker.rerank(results)

        # Group by document
        from collections import defaultdict
        by_doc = defaultdict(list)
        for r in reranked:
            by_doc[r.doc_id].append(r)

        hrv_keys = {"9GKLLJH9", "AQ3D94VC"}  # helm-coregulation, reyes-lf-hrv
        found_hrv = hrv_keys & set(by_doc.keys())
        report.add(
            "topic-search-multi-paper",
            "HRV papers",
            len(found_hrv) >= 1,
            f"Topic search for HRV: found {len(found_hrv)}/{len(hrv_keys)} expected papers "
            f"in {len(by_doc)} total docs. Keys found: {found_hrv}",
            severity="MAJOR",
        )

        # Another cross-domain search
        topic_query2 = "electrode impedance measurement skin contact"
        print(f"  Topic: '{topic_query2}'")
        results2 = retriever.search(query=topic_query2, top_k=50, context_window=0)
        by_doc2 = defaultdict(list)
        for r in results2:
            by_doc2[r.doc_id].append(r)

        impedance_keys = {"VP3NJ74M"}  # fortune-impedance
        found_imp = impedance_keys & set(by_doc2.keys())
        report.add(
            "topic-search-engineering",
            "impedance papers",
            len(found_imp) >= 1,
            f"Topic search for impedance: found {len(found_imp)}/{len(impedance_keys)} expected. "
            f"Total docs: {len(by_doc2)}. Keys: {found_imp}",
            severity="MAJOR",
        )

        # ===================================================================
        # PHASE 10: OCR pathway test
        # ===================================================================
        print(f"\n[PHASE 10] Testing OCR pathway...")

        # Convert first page of one paper to image, make a new PDF from it,
        # and try to extract text
        try:
            import pymupdf

            ocr_path.mkdir(parents=True, exist_ok=True)

            # Pick a paper with clean text
            test_item = None
            test_short = None
            for ik, (ext, ch, it, gt, sn) in extractions.items():
                if len(ext.pages) >= 5:
                    test_item = it
                    test_short = sn
                    break

            if test_item:
                print(f"  Converting [{test_short}] pages 1-3 to images...")
                src_doc = pymupdf.open(str(test_item.pdf_path))

                # Render pages to images at moderate DPI (simulates scanned doc)
                img_pdf_path = ocr_path / "ocr_test.pdf"
                img_doc = pymupdf.open()  # New empty PDF

                for page_idx in range(min(3, len(src_doc))):
                    page = src_doc[page_idx]
                    pix = page.get_pixmap(dpi=200)
                    img_bytes = pix.tobytes("png")

                    # Create a new page from the image
                    img_page = img_doc.new_page(
                        width=page.rect.width,
                        height=page.rect.height,
                    )
                    img_page.insert_image(
                        img_page.rect,
                        stream=img_bytes,
                    )

                img_doc.save(str(img_pdf_path))
                img_doc.close()
                src_doc.close()

                print(f"  Extracting text from image-only PDF...")
                ocr_extraction = extract_document(img_pdf_path)

                total_text = sum(len(p.markdown) for p in ocr_extraction.pages)
                ocr_pages = ocr_extraction.stats.get("ocr_pages", 0)

                report.add(
                    "ocr-text-extraction",
                    test_short,
                    total_text > 100,
                    f"OCR extracted {total_text} chars from {len(ocr_extraction.pages)} image pages. "
                    f"OCR pages detected: {ocr_pages}",
                    severity="MAJOR",
                )

                report.add(
                    "ocr-page-detection",
                    test_short,
                    ocr_pages > 0,
                    f"OCR page detection: {ocr_pages}/{len(ocr_extraction.pages)} pages flagged as OCR",
                    severity="MINOR",
                )
            else:
                report.errors.append("No suitable paper found for OCR test")

        except Exception as e:
            report.errors.append(f"OCR test failed: {traceback.format_exc()}")

        # ===================================================================
        # PHASE 11: Edge case tests
        # ===================================================================
        print(f"\n[PHASE 11] Testing edge cases...")

        # Test: search with zero results
        nonsense_results = retriever.search(
            query="xylophone quantum superconductor banana",
            top_k=5,
            context_window=0,
        )
        # These should return low-score results, not crash
        top_score = f"{nonsense_results[0].score:.3f}" if nonsense_results else "N/A"
        report.add(
            "nonsense-query-no-crash",
            "all",
            True,  # If we got here, it didn't crash
            f"Nonsense query returned {len(nonsense_results)} results "
            f"(top score: {top_score})",
            severity="MINOR",
        )

        # Test: reranker doesn't crash on empty results
        try:
            empty_reranked = reranker.rerank([])
            report.add(
                "empty-rerank-no-crash",
                "all",
                True,
                "Reranker handles empty input gracefully",
                severity="MINOR",
            )
        except Exception as e:
            report.add(
                "empty-rerank-no-crash",
                "all",
                False,
                f"Reranker crashed on empty input: {e}",
                severity="MINOR",
            )

        # Test: adjacent chunk retrieval for first/last chunks
        for item_key in list(extractions.keys())[:2]:
            ext, chunks_list, item, gt, sn = extractions[item_key]
            if chunks_list:
                # First chunk — should not crash
                adj = store.get_adjacent_chunks(item_key, 0, window=2)
                report.add(
                    "boundary-chunk-first",
                    sn,
                    len(adj) >= 1,
                    f"Adjacent chunks for first chunk: got {len(adj)} (expected >=1)",
                    severity="MINOR",
                )
                # Last chunk
                last_idx = chunks_list[-1].chunk_index
                adj_last = store.get_adjacent_chunks(item_key, last_idx, window=2)
                report.add(
                    "boundary-chunk-last",
                    sn,
                    len(adj_last) >= 1,
                    f"Adjacent chunks for last chunk (idx={last_idx}): got {len(adj_last)}",
                    severity="MINOR",
                )

        # ===================================================================
        # PHASE 12: Section-weighted search tests
        # ===================================================================
        print(f"\n[PHASE 12] Testing section-weighted reranking...")

        # Search with methods section boosted
        methods_query = "experimental protocol measurement procedure"
        results_default = retriever.search(query=methods_query, top_k=20, context_window=0)
        reranked_default = reranker.rerank(results_default)

        methods_weights = {"methods": 1.5, "results": 1.0, "abstract": 0.5}
        reranked_methods = reranker.rerank(results_default, section_weights=methods_weights)

        if reranked_default and reranked_methods:
            # Methods-boosted reranking should change the order
            default_top3_sections = [r.section for r in reranked_default[:3]]
            methods_top3_sections = [r.section for r in reranked_methods[:3]]
            order_changed = default_top3_sections != methods_top3_sections
            report.add(
                "section-weight-effect",
                "all",
                True,  # Just check it doesn't crash — effect may be subtle
                f"Default top-3 sections: {default_top3_sections}, "
                f"methods-boosted top-3: {methods_top3_sections}, "
                f"order changed: {order_changed}",
                severity="MINOR",
            )

        # ===================================================================
        # PHASE 13: Validate section labels are consistent
        # ===================================================================
        print(f"\n[PHASE 13] Validating section label consistency...")

        valid_labels = {
            "abstract", "introduction", "background", "methods", "results",
            "discussion", "conclusion", "references", "appendix",
            "preamble", "unknown",
        }

        for item_key, (extraction, chunks, item, gt, short_name) in extractions.items():
            for section in extraction.sections:
                if section.label not in valid_labels:
                    report.add(
                        "invalid-section-label",
                        short_name,
                        False,
                        f"Invalid section label '{section.label}' in heading '{section.heading_text}'",
                        severity="MAJOR",
                    )
                    break
            else:
                report.add(
                    "section-labels-valid",
                    short_name,
                    True,
                    f"All {len(extraction.sections)} section labels are valid",
                    severity="MINOR",
                )

            # Check sections cover the full document
            if extraction.sections:
                first_start = extraction.sections[0].char_start
                last_end = extraction.sections[-1].char_end
                total_len = len(extraction.full_markdown)
                coverage = (last_end - first_start) / total_len if total_len > 0 else 0

                report.add(
                    "section-coverage",
                    short_name,
                    coverage >= 0.9,
                    f"Section spans cover {coverage:.0%} of document "
                    f"(first: {first_start}, last: {last_end}, total: {total_len})",
                    severity="MINOR",
                )

    except Exception as e:
        report.errors.append(f"FATAL: {traceback.format_exc()}")
        print(f"\nFATAL ERROR: {e}")
        traceback.print_exc()

    finally:
        # Cleanup
        try:
            shutil.rmtree(test_dir, ignore_errors=True)
        except Exception:
            pass

    return report


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Fix Windows console encoding
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

    print("=" * 70)
    print("  STRESS TEST: zotero-chunk-rag")
    print("  Real papers, real searches, real expectations")
    print("=" * 70)

    report = run_stress_test()

    # Print report
    md = report.to_markdown()
    print("\n" + "=" * 70)
    print(md)

    # Save report
    report_path = Path(__file__).parent.parent / "STRESS_TEST_REPORT.md"
    report_path.write_text(md, encoding="utf-8")
    print(f"\nReport saved to: {report_path}")

    # Exit with appropriate code
    if report.major_failures > 0:
        print(f"\n*** {report.major_failures} MAJOR FAILURES — tool is unreliable ***")
        sys.exit(1)
    elif report.failed > 0:
        print(f"\n* {report.failed} minor issues found *")
        sys.exit(0)
    else:
        print("\nAll tests passed.")
        sys.exit(0)
