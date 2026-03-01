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
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

from zotero_chunk_rag.feature_extraction.debug_db import (
    create_extended_tables,
    write_ground_truth_diff,
    write_method_result,
    write_pipeline_run,
    write_vision_agent_result,
    write_vision_consensus,
)
from zotero_chunk_rag.feature_extraction.ground_truth import (
    GROUND_TRUTH_DB_PATH,
    compare_extraction,
    make_table_id,
)
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
            "figure_search_query": "RSA dynamics time series",
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
            "figure_search_query": "sensitivity specificity receiver operating",
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
    """Run the full stress test and return the report and extractions."""
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    # Suppress noisy loggers
    logging.getLogger("chromadb").setLevel(logging.ERROR)
    logging.getLogger("httpx").setLevel(logging.ERROR)

    report = StressTestReport()
    extractions: dict[str, tuple] = {}

    # Temp dir for ephemeral data (chroma index, OCR scratch).
    # Figures go to a persistent directory alongside the report/audit.
    test_dir = Path(tempfile.mkdtemp(prefix="stress_test_"))
    chroma_path = test_dir / "chroma"
    ocr_path = test_dir / "ocr_images"

    base_dir = Path(__file__).parent.parent
    figures_path = base_dir / "_stress_test_figures"

    print(f"Test directory: {test_dir}")
    print(f"Figures directory: {figures_path}")
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
            vision_enabled=False,
            vision_model="claude-haiku-4-5-20251001",
            vision_num_agents=3,
            vision_dpi=300,
            vision_consensus_threshold=0.6,
            vision_padding_px=20,
            anthropic_api_key=None,
        )

        embedder = create_embedder(test_config)
        store = VectorStore(chroma_path, embedder)
        chunker = Chunker(chunk_size=400, overlap=100)
        journal_ranker = JournalRanker()
        reranker = Reranker(alpha=0.7)
        retriever = Retriever(store)

        t_start = time.perf_counter()

        for item, short_name, gt in corpus_items:
            print(f"\n  Extracting [{short_name}]...", end=" ", flush=True)
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

            # Build reference map and enrich tables/figures with body-text context
            # (mirrors production indexer pipeline)
            from zotero_chunk_rag._reference_matcher import match_references, get_reference_context
            from zotero_chunk_rag.pdf_processor import SYNTHETIC_CAPTION_PREFIX
            ref_map = match_references(extraction.full_markdown, chunks, extraction.tables, extraction.figures)
            _TAB_NUM_RE = re.compile(r"(?:Table|Tab\.?)\s+(\d+)", re.IGNORECASE)
            _FIG_NUM_RE = re.compile(r"(?:Figure|Fig\.?)\s+(\d+)", re.IGNORECASE)
            for table in extraction.tables:
                if table.caption and not table.caption.startswith(SYNTHETIC_CAPTION_PREFIX):
                    m_cap = _TAB_NUM_RE.search(table.caption)
                    if m_cap:
                        ctx = get_reference_context(extraction.full_markdown, chunks, ref_map, "table", int(m_cap.group(1)))
                        table.reference_context = ctx
            for fig in extraction.figures:
                if fig.caption and not fig.caption.startswith(SYNTHETIC_CAPTION_PREFIX):
                    m_cap = _FIG_NUM_RE.search(fig.caption)
                    if m_cap:
                        ctx = get_reference_context(extraction.full_markdown, chunks, ref_map, "figure", int(m_cap.group(1)))
                        fig.reference_context = ctx

            # Store tables
            if extraction.tables:
                store.add_tables(item.item_key, doc_meta, extraction.tables, ref_map=ref_map)

            # Store figures
            if extraction.figures:
                store.add_figures(item.item_key, doc_meta, extraction.figures, ref_map=ref_map)

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

            n_real_tables = sum(1 for t in extraction.tables if not t.artifact_type)
            n_artifact_tables = sum(1 for t in extraction.tables if t.artifact_type)
            table_str = str(n_real_tables)
            if n_artifact_tables:
                table_str += f" (+{n_artifact_tables} artifacts)"

            report.extraction_summaries.append({
                "name": short_name,
                "pages": len(extraction.pages),
                "sections": n_sections,
                "tables": table_str,
                "figures": len(extraction.figures),
                "grade": extraction.quality_grade,
                "issues": "; ".join(issues_parts) if issues_parts else "none",
            })

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
            real_tables = [t for t in extraction.tables if not t.artifact_type]
            artifact_tables = [t for t in extraction.tables if t.artifact_type]

            # Report artifact tables (informational — always passes)
            if artifact_tables:
                tags = [t.artifact_type for t in artifact_tables]
                report.add(
                    "artifact-tables-tagged",
                    short_name,
                    True,
                    f"{len(artifact_tables)} layout artifact(s) tagged and excluded: {tags}",
                )

            if gt.get("expect_tables"):
                has_tables = len(real_tables) > 0
                report.add(
                    "table-extraction",
                    short_name,
                    has_tables,
                    f"Expected tables — found {len(real_tables)}",
                    severity="MAJOR",
                )
                # Check table content quality (non-empty cells) — skip artifacts
                for i, tab in enumerate(extraction.tables):
                    if tab.artifact_type:
                        continue
                    non_empty = sum(1 for row in tab.rows for cell in row if cell.strip())
                    total_cells = sum(len(row) for row in tab.rows)
                    if total_cells > 0:
                        fill_rate = non_empty / total_cells
                        report.add(
                            "table-content-quality",
                            f"{short_name}/table-{i}",
                            fill_rate > 0.5,
                            f"Table {i}: {non_empty}/{total_cells} cells non-empty ({fill_rate:.0%}). "
                            f"Caption: '{(tab.caption or 'NONE')[:60]}'",
                            severity="MAJOR" if fill_rate < 0.2 else "MINOR",
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
                # Caption rate (informational — orphans are caught as MAJOR by 3d.3)
                captioned = [f for f in extraction.figures if f.caption]
                if extraction.figures:
                    caption_rate = len(captioned) / len(extraction.figures)
                    report.add(
                        "figure-caption-rate",
                        short_name,
                        caption_rate == 1.0,
                        f"{len(captioned)}/{len(extraction.figures)} figures have captions ({caption_rate:.0%})",
                        severity="MAJOR",
                    )

            # --- 3d: Completeness grade ---
            comp = extraction.completeness
            if comp:
                n_artifacts = len(artifact_tables)
                artifact_note = f" | Artifacts: {n_artifacts} tagged" if n_artifacts else ""
                report.add(
                    "completeness-grade",
                    short_name,
                    comp.grade in ("A", "B"),
                    f"Grade: {comp.grade} | "
                    f"Figs: {comp.figures_found} found / {comp.figure_captions_found} captioned / {comp.figures_missing} missing | "
                    f"Tables: {comp.tables_found} found / {comp.table_captions_found} captioned / {comp.tables_missing} missing"
                    + artifact_note,
                    severity="MAJOR" if comp.grade in ("D", "F") else "MINOR",
                )

                # --- 3d.1: Missing figures (captions found, no image extracted) ---
                if comp.figures_missing > 0:
                    report.add(
                        "missing-figures",
                        short_name,
                        False,
                        f"{comp.figures_missing} figure(s) have captions but no extracted image. "
                        f"Captions found: {comp.figure_captions_found}, figures extracted: {comp.figures_found}",
                        severity="MAJOR",
                    )

                # --- 3d.2: Missing tables (captions found, no table extracted) ---
                if comp.tables_missing > 0:
                    report.add(
                        "missing-tables",
                        short_name,
                        False,
                        f"{comp.tables_missing} table(s) have captions but no extracted content. "
                        f"Captions found: {comp.table_captions_found}, tables extracted: {comp.tables_found}",
                        severity="MAJOR",
                    )

                # --- 3d.3: Orphan figures (extracted but no caption matched) ---
                orphan_figs = comp.figures_found - comp.figures_with_captions
                if orphan_figs > 0:
                    report.add(
                        "orphan-figures",
                        short_name,
                        False,
                        f"{orphan_figs} figure(s) extracted without a real caption. "
                        f"Unmatched caption numbers: {comp.unmatched_figure_captions or 'none'}",
                        severity="MAJOR",
                    )

                # --- 3d.4: Orphan tables (extracted but no caption matched) ---
                orphan_tabs = comp.tables_found - comp.tables_with_captions
                if orphan_tabs > 0:
                    report.add(
                        "orphan-tables",
                        short_name,
                        False,
                        f"{orphan_tabs} table(s) extracted without a real caption. "
                        f"Unmatched caption numbers: {comp.unmatched_table_captions or 'none'}",
                        severity="MAJOR",
                    )

                # --- 3d.5: Unmatched captions (caption on page, not on any object) ---
                unmatched = comp.unmatched_figure_captions + comp.unmatched_table_captions
                if unmatched:
                    report.add(
                        "unmatched-captions",
                        short_name,
                        False,
                        f"Caption numbers found on pages but not matched to any extracted object: "
                        f"figures={comp.unmatched_figure_captions or 'none'}, "
                        f"tables={comp.unmatched_table_captions or 'none'}",
                        severity="MAJOR",
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

            # --- 3h: Content readability (garbled/interleaved cells) ---
            if comp and extraction.tables:
                from zotero_chunk_rag.pdf_processor import _check_content_readability
                readability_issues = []
                for ti, tab in enumerate(extraction.tables):
                    rpt = _check_content_readability(tab)
                    if rpt["garbled_cells"] or rpt["interleaved_cells"]:
                        readability_issues.append(
                            f"table {ti}: garbled={rpt['garbled_cells']}, "
                            f"interleaved={rpt['interleaved_cells']}"
                        )
                report.add(
                    "content-readability",
                    short_name,
                    len(readability_issues) == 0,
                    f"{len(readability_issues)} tables with readability issues"
                    + (f": {'; '.join(readability_issues[:3])}" if readability_issues else ""),
                    severity="MAJOR",
                )

            # --- 3i: 1x1 table dimensions ---
            if comp:
                report.add(
                    "table-dimensions-sanity",
                    short_name,
                    comp.tables_1x1 == 0,
                    f"{comp.tables_1x1} tables are 1x1 (degenerate)",
                    severity="MAJOR",
                )

            # --- 3j: Caption encoding quality ---
            if comp:
                report.add(
                    "caption-encoding-quality",
                    short_name,
                    comp.encoding_artifact_captions == 0,
                    f"{comp.encoding_artifact_captions} captions with encoding artifacts",
                    severity="MINOR",
                )

            # --- 3k: Caption number continuity ---
            if comp:
                gaps = comp.figure_number_gaps + comp.table_number_gaps
                report.add(
                    "caption-number-continuity",
                    short_name,
                    len(gaps) == 0,
                    f"Figure gaps: {comp.figure_number_gaps or 'none'}, "
                    f"Table gaps: {comp.table_number_gaps or 'none'}",
                    severity="MAJOR",
                )

            # --- 3l: Duplicate captions ---
            if comp:
                report.add(
                    "duplicate-captions",
                    short_name,
                    comp.duplicate_captions == 0,
                    f"{comp.duplicate_captions} duplicate caption(s) found",
                    severity="MAJOR",
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
            raise RuntimeError("No suitable paper found for OCR test")

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
            nonsense_results[0].score < 0.5 if nonsense_results else False,
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
                order_changed,
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

    finally:
        shutil.rmtree(test_dir, ignore_errors=True)

    return report, extractions


# ---------------------------------------------------------------------------
# Debug database — structured SQLite for agent-friendly artifact inspection
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS run_metadata (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS papers (
    item_key              TEXT PRIMARY KEY,
    short_name            TEXT NOT NULL,
    title                 TEXT,
    num_pages             INTEGER,
    num_chunks            INTEGER,
    quality_grade         TEXT,
    -- completeness fields (NULL when completeness unavailable)
    figures_found         INTEGER,
    figures_with_captions INTEGER,
    figures_missing       INTEGER,
    figure_captions_found INTEGER,
    tables_found          INTEGER,
    tables_with_captions  INTEGER,
    tables_missing        INTEGER,
    table_captions_found  INTEGER,
    tables_1x1            INTEGER,
    encoding_artifact_captions INTEGER,
    duplicate_captions    INTEGER,
    figure_number_gaps    TEXT,   -- JSON array of gap strings
    table_number_gaps     TEXT,   -- JSON array of gap strings
    unmatched_figure_captions TEXT, -- JSON array
    unmatched_table_captions  TEXT, -- JSON array
    completeness_grade    TEXT,
    full_markdown         TEXT,   -- full extracted document text
    pdf_path              TEXT    -- path to source PDF (for debug viewer)
);

CREATE TABLE IF NOT EXISTS sections (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    item_key       TEXT NOT NULL,
    section_index  INTEGER,
    label          TEXT,
    heading_text   TEXT,
    char_start     INTEGER,
    char_end       INTEGER,
    confidence     REAL,
    FOREIGN KEY (item_key) REFERENCES papers(item_key)
);

CREATE TABLE IF NOT EXISTS pages (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    item_key  TEXT NOT NULL,
    page_num  INTEGER,
    markdown  TEXT,
    FOREIGN KEY (item_key) REFERENCES papers(item_key)
);

CREATE TABLE IF NOT EXISTS extracted_tables (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    item_key          TEXT NOT NULL,
    table_index       INTEGER,
    page_num          INTEGER,
    caption           TEXT,
    caption_position  TEXT,
    num_rows          INTEGER,
    num_cols          INTEGER,
    non_empty_cells   INTEGER,
    total_cells       INTEGER,
    fill_rate         REAL,
    headers_json      TEXT,   -- JSON array of header strings
    rows_json         TEXT,   -- JSON array of arrays (full cell data)
    markdown          TEXT,   -- rendered markdown table
    reference_context TEXT,
    bbox              TEXT,   -- JSON [x0, y0, x1, y1]
    artifact_type     TEXT,   -- NULL=real data, else layout artifact tag
    extraction_strategy TEXT, -- which multi-strategy winner produced cell text
    table_id            TEXT,   -- stable table ID for linking to method_results/GT
    FOREIGN KEY (item_key) REFERENCES papers(item_key)
);

CREATE TABLE IF NOT EXISTS extracted_figures (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    item_key          TEXT NOT NULL,
    figure_index      INTEGER,
    page_num          INTEGER,
    caption           TEXT,
    bbox              TEXT,   -- JSON [x0, y0, x1, y1]
    image_path        TEXT,
    has_image         INTEGER,
    reference_context TEXT,
    FOREIGN KEY (item_key) REFERENCES papers(item_key)
);

CREATE TABLE IF NOT EXISTS chunks (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    item_key             TEXT NOT NULL,
    chunk_index          INTEGER,
    page_num             INTEGER,
    section              TEXT,
    section_confidence   REAL,
    char_start           INTEGER,
    char_end             INTEGER,
    text                 TEXT,
    FOREIGN KEY (item_key) REFERENCES papers(item_key)
);

CREATE TABLE IF NOT EXISTS test_results (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    test_name TEXT,
    paper     TEXT,
    passed    INTEGER,
    detail    TEXT,
    severity  TEXT
);
"""


def write_debug_database(
    extractions: dict[str, tuple],
    report: StressTestReport,
    db_path: Path,
) -> None:
    """Write all extraction artifacts and test results to a SQLite database.

    Replaces the old text-file audit.  Agents can then query specific papers,
    tables, figures, chunks, or test failures via SQL instead of reading a
    giant text dump.
    """
    # Remove stale DB so each run is a clean snapshot
    if db_path.exists():
        db_path.unlink()

    con = sqlite3.connect(str(db_path))
    con.executescript(_SCHEMA)
    create_extended_tables(con)

    # --- run metadata ---
    meta_rows = [
        ("generated", time.strftime("%Y-%m-%d %H:%M:%S")),
        ("corpus_size", str(len(CORPUS))),
        ("papers_extracted", str(len(extractions))),
        ("tests_total", str(len(report.results))),
        ("tests_passed", str(report.passed)),
        ("tests_failed", str(report.failed)),
        ("major_failures", str(report.major_failures)),
    ]
    for k, v in report.timings.items():
        meta_rows.append((f"timing_{k}", f"{v:.1f}s"))
    con.executemany(
        "INSERT INTO run_metadata (key, value) VALUES (?, ?)", meta_rows,
    )

    for item_key, (extraction, chunks, item, gt, short_name) in extractions.items():
        comp = extraction.completeness

        # --- paper row ---
        con.execute(
            """INSERT INTO papers VALUES (
                ?,?,?,?,?,?,  ?,?,?,?,  ?,?,?,?,  ?,?,?,  ?,?,?,?,  ?,?,?
            )""",
            (
                item_key,
                short_name,
                item.title,
                len(extraction.pages),
                len(chunks),
                extraction.quality_grade,
                # completeness (may be None)
                comp.figures_found if comp else None,
                comp.figures_with_captions if comp else None,
                comp.figures_missing if comp else None,
                comp.figure_captions_found if comp else None,
                comp.tables_found if comp else None,
                comp.tables_with_captions if comp else None,
                comp.tables_missing if comp else None,
                comp.table_captions_found if comp else None,
                comp.tables_1x1 if comp else None,
                comp.encoding_artifact_captions if comp else None,
                comp.duplicate_captions if comp else None,
                json.dumps(comp.figure_number_gaps) if comp else None,
                json.dumps(comp.table_number_gaps) if comp else None,
                json.dumps(comp.unmatched_figure_captions) if comp else None,
                json.dumps(comp.unmatched_table_captions) if comp else None,
                comp.grade if comp else None,
                extraction.full_markdown,
                str(item.pdf_path) if item.pdf_path else None,
            ),
        )

        # --- sections ---
        for si, sec in enumerate(extraction.sections):
            con.execute(
                "INSERT INTO sections (item_key, section_index, label, heading_text, "
                "char_start, char_end, confidence) VALUES (?,?,?,?,?,?,?)",
                (item_key, si, sec.label, sec.heading_text,
                 sec.char_start, sec.char_end, sec.confidence),
            )

        # --- pages ---
        for pg in extraction.pages:
            con.execute(
                "INSERT INTO pages (item_key, page_num, markdown) VALUES (?,?,?)",
                (item_key, pg.page_num, pg.markdown),
            )

        # --- tables ---
        for tab in extraction.tables:
            non_empty = sum(1 for row in tab.rows for cell in row if cell.strip())
            total_cells = sum(len(row) for row in tab.rows)
            fill_rate = non_empty / total_cells if total_cells else 0.0
            table_id = make_table_id(
                item_key, tab.caption, tab.page_num, tab.table_index
            )
            con.execute(
                "INSERT INTO extracted_tables (item_key, table_index, page_num, "
                "caption, caption_position, num_rows, num_cols, non_empty_cells, "
                "total_cells, fill_rate, headers_json, rows_json, markdown, "
                "reference_context, bbox, artifact_type, extraction_strategy, "
                "table_id) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    item_key,
                    tab.table_index,
                    tab.page_num,
                    tab.caption,
                    tab.caption_position,
                    tab.num_rows,
                    tab.num_cols,
                    non_empty,
                    total_cells,
                    fill_rate,
                    json.dumps(tab.headers),
                    json.dumps(tab.rows),
                    tab.to_markdown(),
                    tab.reference_context,
                    json.dumps(list(tab.bbox)),
                    tab.artifact_type,
                    tab.extraction_strategy,
                    table_id,
                ),
            )

        # --- ground truth diffs ---
        if Path(GROUND_TRUTH_DB_PATH).exists():
            run_id = time.strftime("%Y-%m-%dT%H:%M:%S")
            for tab in extraction.tables:
                if tab.artifact_type is not None:
                    continue
                table_id = make_table_id(
                    item_key, tab.caption, tab.page_num, tab.table_index
                )
                try:
                    result = compare_extraction(
                        GROUND_TRUTH_DB_PATH, table_id, tab.headers, tab.rows
                    )
                except KeyError:
                    continue
                write_ground_truth_diff(con, table_id, run_id, result)

        # --- figures ---
        for fig in extraction.figures:
            has_img = 1 if (fig.image_path and fig.image_path.exists()) else 0
            con.execute(
                "INSERT INTO extracted_figures (item_key, figure_index, page_num, "
                "caption, bbox, image_path, has_image, reference_context) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    item_key,
                    fig.figure_index,
                    fig.page_num,
                    fig.caption,
                    json.dumps(list(fig.bbox)),
                    str(fig.image_path) if fig.image_path else None,
                    has_img,
                    fig.reference_context,
                ),
            )

        # --- chunks ---
        for ch in chunks:
            con.execute(
                "INSERT INTO chunks (item_key, chunk_index, page_num, section, "
                "section_confidence, char_start, char_end, text) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    item_key,
                    ch.chunk_index,
                    ch.page_num,
                    ch.section,
                    ch.section_confidence,
                    ch.char_start,
                    ch.char_end,
                    ch.text,
                ),
            )

    # --- test results (pre-pipeline-analysis) ---
    for r in report.results:
        con.execute(
            "INSERT INTO test_results (test_name, paper, passed, detail, severity) "
            "VALUES (?,?,?,?,?)",
            (r.test_name, r.paper, 1 if r.passed else 0, r.detail, r.severity),
        )
    con.commit()

    con.commit()
    con.close()


# ---------------------------------------------------------------------------
# Ground truth summary helper
# ---------------------------------------------------------------------------


def _build_gt_summary_markdown(db_path: Path) -> list[str]:
    """Query ground_truth_diffs from the debug DB and return markdown lines.

    Returns an empty list when no ground truth diffs have been recorded
    (e.g. because ground_truth.db does not exist).
    """
    con = sqlite3.connect(str(db_path))
    try:
        rows = con.execute(
            "SELECT gtd.table_id, p.short_name, gtd.fuzzy_accuracy_pct, "
            "gtd.fuzzy_precision_pct, gtd.fuzzy_recall_pct, "
            "gtd.num_splits, gtd.num_merges, gtd.num_cell_diffs "
            "FROM ground_truth_diffs gtd "
            "LEFT JOIN papers p ON p.item_key = substr(gtd.table_id, 1, "
            "  CASE WHEN instr(gtd.table_id, '_table_') > 0 "
            "       THEN instr(gtd.table_id, '_table_') - 1 "
            "       ELSE instr(gtd.table_id, '_orphan_') - 1 END) "
            "ORDER BY gtd.table_id"
        ).fetchall()
    finally:
        con.close()

    if not rows:
        return []

    lines: list[str] = []
    lines.append("## Ground Truth Comparison")
    lines.append("")
    lines.append("| Paper | Table ID | Fuzzy Accuracy | Precision | Recall | Splits | Merges | Cell Diffs |")
    lines.append("|-------|----------|----------------|-----------|--------|--------|--------|------------|")
    accuracy_values: list[float] = []
    for table_id, short_name, fuzzy_acc, fuzzy_prec, fuzzy_rec, num_splits, num_merges, num_cell_diffs in rows:
        paper_label = short_name if short_name else table_id.split("_")[0]
        lines.append(
            f"| {paper_label} | {table_id} | {fuzzy_acc:.1f}% "
            f"| {fuzzy_prec:.1f}% | {fuzzy_rec:.1f}% "
            f"| {num_splits} | {num_merges} | {num_cell_diffs} |"
        )
        accuracy_values.append(fuzzy_acc)

    if accuracy_values:
        overall = sum(accuracy_values) / len(accuracy_values)
        lines.append("")
        lines.append(
            f"**Overall corpus fuzzy accuracy**: {overall:.1f}% "
            f"({len(accuracy_values)} tables compared)"
        )
    lines.append("")
    return lines


# ---------------------------------------------------------------------------
# Vision eval DB writer (keeps _vision_stage_eval.db in sync for the viewer)
# ---------------------------------------------------------------------------

_EVAL_DB_PATH = Path(__file__).resolve().parent.parent / "_vision_stage_eval.db"
_EVAL_ROLE_NAMES = ["transcriber", "y_verifier", "x_verifier", "synthesizer"]
_EVAL_STAGE_PAIRS = [
    ("transcriber", "y_verifier", 0, 1),
    ("transcriber", "x_verifier", 0, 2),
    ("transcriber", "synthesizer", 0, 3),
    ("y_verifier", "synthesizer", 1, 3),
    ("x_verifier", "synthesizer", 2, 3),
]

_EVAL_SCHEMA = """\
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY, timestamp TEXT,
    num_papers INTEGER, num_tables INTEGER,
    total_cost_usd REAL, vision_time_s REAL
);
CREATE TABLE IF NOT EXISTS agent_outputs (
    run_id TEXT, table_id TEXT, agent_role TEXT,
    headers_json TEXT, rows_json TEXT, footnotes TEXT,
    corrections_json TEXT, shape TEXT, parse_success INTEGER,
    num_corrections INTEGER, raw_response TEXT,
    PRIMARY KEY (run_id, table_id, agent_role)
);
CREATE TABLE IF NOT EXISTS gt_comparisons (
    run_id TEXT, table_id TEXT, agent_role TEXT,
    cell_accuracy_pct REAL, structural_coverage_pct REAL,
    gt_shape TEXT, ext_shape TEXT,
    num_matched_cols INTEGER, num_extra_cols INTEGER, num_missing_cols INTEGER,
    num_col_splits INTEGER, num_col_merges INTEGER,
    num_matched_rows INTEGER, num_extra_rows INTEGER, num_missing_rows INTEGER,
    num_row_splits INTEGER, num_row_merges INTEGER, num_cell_diffs INTEGER,
    PRIMARY KEY (run_id, table_id, agent_role)
);
CREATE TABLE IF NOT EXISTS stage_diffs (
    run_id TEXT, table_id TEXT, from_role TEXT, to_role TEXT,
    shape_changed INTEGER, num_header_diffs INTEGER, num_cell_diffs INTEGER,
    cells_added INTEGER, cells_removed INTEGER, accuracy_delta REAL,
    PRIMARY KEY (run_id, table_id, from_role, to_role)
);
CREATE TABLE IF NOT EXISTS correction_log (
    run_id TEXT, table_id TEXT, agent_role TEXT,
    correction_index INTEGER, correction_text TEXT
);
"""


def _eval_cell_diff(a, b) -> dict:
    """Compare two AgentResponses cell-by-cell for stage diffs."""
    if not a.parse_success or not b.parse_success:
        return {"shape_changed": 1, "num_header_diffs": 0,
                "num_cell_diffs": 0, "cells_added": 0, "cells_removed": 0}
    shape_changed = int(a.raw_shape != b.raw_shape)
    h_diffs = sum(1 for i in range(min(len(a.headers), len(b.headers)))
                  if a.headers[i].strip() != b.headers[i].strip())
    h_diffs += abs(len(a.headers) - len(b.headers))
    cell_diffs = cells_added = cells_removed = 0
    min_rows = min(len(a.rows), len(b.rows))
    for r in range(min_rows):
        mc = min(len(a.rows[r]), len(b.rows[r]))
        cell_diffs += sum(1 for c in range(mc)
                          if a.rows[r][c].strip() != b.rows[r][c].strip())
        diff = len(b.rows[r]) - len(a.rows[r])
        if diff > 0:
            cells_added += diff
        elif diff < 0:
            cells_removed -= diff
    for r in range(min_rows, len(b.rows)):
        cells_added += len(b.rows[r])
    for r in range(min_rows, len(a.rows)):
        cells_removed += len(a.rows[r])
    return {"shape_changed": shape_changed, "num_header_diffs": h_diffs,
            "num_cell_diffs": cell_diffs, "cells_added": cells_added,
            "cells_removed": cells_removed}


def _update_vision_eval_db(
    vision_results: list,
    session_cost: float,
    vision_time: float,
    num_papers: int,
    gt_db_exists: bool,
) -> None:
    """Write vision results to _vision_stage_eval.db for the viewer."""
    from zotero_chunk_rag.feature_extraction.vision_extract import (
        AgentResponse, _parse_agent_json,
    )

    eval_conn = sqlite3.connect(str(_EVAL_DB_PATH))
    eval_conn.executescript(_EVAL_SCHEMA)

    run_id = time.strftime("%Y%m%d_%H%M%S")
    n_specs = sum(1 for _, r in vision_results if r.error is None)

    eval_conn.execute(
        "INSERT OR REPLACE INTO runs VALUES (?, ?, ?, ?, ?, ?)",
        (run_id, time.strftime("%Y-%m-%dT%H:%M:%SZ"),
         num_papers, n_specs, session_cost, vision_time),
    )

    gt_tables: set[str] = set()
    if gt_db_exists:
        gt_conn = sqlite3.connect(str(GROUND_TRUTH_DB_PATH))
        gt_tables = {r[0] for r in gt_conn.execute(
            "SELECT table_id FROM ground_truth_tables"
        ).fetchall()}
        gt_conn.close()

    for spec, result in vision_results:
        if result.error or not result.agent_responses:
            continue

        responses = list(result.agent_responses)
        while len(responses) < 4:
            responses.append(AgentResponse(
                headers=[], rows=[], footnotes="",
                table_label=None, is_incomplete=False,
                incomplete_reason="", raw_shape=(0, 0),
                parse_success=False, raw_response="",
            ))

        for i, role in enumerate(_EVAL_ROLE_NAMES):
            resp = responses[i]
            corrections = []
            if resp.parse_success and resp.raw_response:
                parsed = _parse_agent_json(resp.raw_response)
                if parsed:
                    corrections = parsed.get("corrections") or []

            eval_conn.execute(
                "INSERT OR REPLACE INTO agent_outputs VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (run_id, spec.table_id, role,
                 json.dumps(resp.headers, ensure_ascii=False),
                 json.dumps(resp.rows, ensure_ascii=False),
                 resp.footnotes,
                 json.dumps(corrections, ensure_ascii=False),
                 f"{resp.raw_shape[0]}x{resp.raw_shape[1]}",
                 int(resp.parse_success),
                 len(corrections),
                 resp.raw_response),
            )

            for ci, ct in enumerate(corrections):
                eval_conn.execute(
                    "INSERT INTO correction_log VALUES (?,?,?,?,?)",
                    (run_id, spec.table_id, role, ci, ct),
                )

            # GT comparison
            if spec.table_id in gt_tables and resp.parse_success and resp.headers:
                try:
                    cmp = compare_extraction(
                        GROUND_TRUTH_DB_PATH, spec.table_id,
                        resp.headers, resp.rows, resp.footnotes or "",
                    )
                    eval_conn.execute(
                        "INSERT OR REPLACE INTO gt_comparisons "
                        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (run_id, spec.table_id, role,
                         cmp.cell_accuracy_pct,
                         cmp.structural_coverage_pct,
                         f"{cmp.gt_shape[0]}x{cmp.gt_shape[1]}",
                         f"{cmp.ext_shape[0]}x{cmp.ext_shape[1]}",
                         len(cmp.matched_columns),
                         len(cmp.extra_columns),
                         len(cmp.missing_columns),
                         len(cmp.column_splits),
                         len(cmp.column_merges),
                         len(cmp.matched_rows),
                         len(cmp.extra_rows),
                         len(cmp.missing_rows),
                         len(cmp.row_splits),
                         len(cmp.row_merges),
                         len(cmp.cell_diffs)),
                    )
                except (KeyError, Exception):
                    pass

        # Stage-to-stage diffs
        for from_role, to_role, fi, ti in _EVAL_STAGE_PAIRS:
            diff = _eval_cell_diff(responses[fi], responses[ti])
            acc_delta = None
            if spec.table_id in gt_tables:
                row_from = eval_conn.execute(
                    "SELECT cell_accuracy_pct FROM gt_comparisons "
                    "WHERE run_id=? AND table_id=? AND agent_role=?",
                    (run_id, spec.table_id, from_role),
                ).fetchone()
                row_to = eval_conn.execute(
                    "SELECT cell_accuracy_pct FROM gt_comparisons "
                    "WHERE run_id=? AND table_id=? AND agent_role=?",
                    (run_id, spec.table_id, to_role),
                ).fetchone()
                if (row_from and row_to
                        and row_from[0] is not None and row_to[0] is not None):
                    acc_delta = row_to[0] - row_from[0]

            eval_conn.execute(
                "INSERT OR REPLACE INTO stage_diffs VALUES (?,?,?,?,?,?,?,?,?,?)",
                (run_id, spec.table_id, from_role, to_role,
                 diff["shape_changed"], diff["num_header_diffs"],
                 diff["num_cell_diffs"], diff["cells_added"],
                 diff["cells_removed"], acc_delta),
            )

    eval_conn.commit()
    eval_conn.close()
    print(f"  [Vision] Updated {_EVAL_DB_PATH.name} (run {run_id})")


# ---------------------------------------------------------------------------
# Pipeline depth report builder
# ---------------------------------------------------------------------------


def _build_pipeline_depth_report(db_path: Path) -> list[str]:
    """Query the debug DB for all method results, GT diffs, and pipeline runs.

    Builds a markdown report showing:
    - Per-method win rates (how often each cell/structure method is best)
    - Combination value (best-single-method vs consensus accuracy)
    - Post-processing improvement (winning grid vs post-processed GT accuracy)
    - Per-table accuracy chain (raw method accuracies -> winning -> post-processed -> GT)

    Returns an empty list when no method_results data exists.
    """
    con = sqlite3.connect(str(db_path))
    try:
        # Check if method_results has data
        count_row = con.execute("SELECT COUNT(*) FROM method_results").fetchone()
        if count_row[0] == 0:
            return []

        lines: list[str] = []
        lines.append("## Pipeline Depth Report")
        lines.append("")

        # --- 1. Per-method win rates ---
        lines.append("### Per-Method Win Rates")
        lines.append("")

        # For each table_id, find which structure+cell combo had the best quality_score
        table_ids = [
            r[0] for r in con.execute(
                "SELECT DISTINCT table_id FROM method_results"
            ).fetchall()
        ]

        structure_wins: dict[str, int] = {}
        cell_wins: dict[str, int] = {}
        structure_totals: dict[str, int] = {}
        cell_totals: dict[str, int] = {}

        for tid in table_ids:
            rows = con.execute(
                "SELECT method_name, quality_score FROM method_results "
                "WHERE table_id = ? AND quality_score IS NOT NULL "
                "ORDER BY quality_score DESC LIMIT 1",
                (tid,),
            ).fetchone()
            if rows:
                best_method = rows[0]
                parts = best_method.split("+", 1)
                if len(parts) == 2:
                    struct_name, cell_name = parts
                    structure_wins[struct_name] = structure_wins.get(struct_name, 0) + 1
                    cell_wins[cell_name] = cell_wins.get(cell_name, 0) + 1

            # Count participation
            all_methods = con.execute(
                "SELECT DISTINCT method_name FROM method_results WHERE table_id = ?",
                (tid,),
            ).fetchall()
            for (method_name,) in all_methods:
                parts = method_name.split("+", 1)
                if len(parts) == 2:
                    structure_totals[parts[0]] = structure_totals.get(parts[0], 0) + 1
                    cell_totals[parts[1]] = cell_totals.get(parts[1], 0) + 1

        if structure_wins:
            lines.append("**Structure method wins** (how often each method's boundaries produce the best cell accuracy):")
            lines.append("")
            lines.append("| Structure Method | Wins | Participated | Win Rate |")
            lines.append("|-----------------|------|-------------|----------|")
            for name in sorted(structure_wins.keys(), key=lambda n: structure_wins[n], reverse=True):
                total = structure_totals.get(name, 0)
                wr = structure_wins[name] / total if total > 0 else 0
                lines.append(f"| {name} | {structure_wins[name]} | {total} | {wr:.0%} |")
            lines.append("")

        if cell_wins:
            lines.append("**Cell method wins** (how often each method is selected as best):")
            lines.append("")
            lines.append("| Cell Method | Wins | Participated | Win Rate |")
            lines.append("|------------|------|-------------|----------|")
            for name in sorted(cell_wins.keys(), key=lambda n: cell_wins[n], reverse=True):
                total = cell_totals.get(name, 0)
                wr = cell_wins[name] / total if total > 0 else 0
                lines.append(f"| {name} | {cell_wins[name]} | {total} | {wr:.0%} |")
            lines.append("")

        # --- 2. Combination value ---
        lines.append("### Combination Value")
        lines.append("")
        lines.append("Comparison of best-single-method accuracy vs pipeline (consensus boundaries) accuracy:")
        lines.append("")

        # For each table, find best single-method accuracy and pipeline accuracy
        best_single_accs: list[float] = []
        pipeline_accs: list[float] = []
        combo_table_ids: list[str] = []

        for tid in table_ids:
            # Best single method accuracy
            best_row = con.execute(
                "SELECT MAX(quality_score) FROM method_results "
                "WHERE table_id = ? AND quality_score IS NOT NULL",
                (tid,),
            ).fetchone()
            # Pipeline accuracy (from ground_truth_diffs)
            pipeline_row = con.execute(
                "SELECT fuzzy_accuracy_pct FROM ground_truth_diffs "
                "WHERE table_id = ? ORDER BY rowid DESC LIMIT 1",
                (tid,),
            ).fetchone()

            if best_row and best_row[0] is not None and pipeline_row:
                best_single_accs.append(best_row[0])
                pipeline_accs.append(pipeline_row[0])
                combo_table_ids.append(tid)

        if best_single_accs:
            avg_best = sum(best_single_accs) / len(best_single_accs)
            avg_pipeline = sum(pipeline_accs) / len(pipeline_accs)
            delta = avg_pipeline - avg_best
            lines.append(f"- **Avg best-single-method accuracy**: {avg_best:.1f}%")
            lines.append(f"- **Avg pipeline (consensus) accuracy**: {avg_pipeline:.1f}%")
            lines.append(f"- **Delta (positive = combination helps)**: {delta:+.1f}%")
            lines.append(f"- **Tables compared**: {len(best_single_accs)}")
        else:
            lines.append("_(No tables with both per-method and GT data available)_")
        lines.append("")

        # --- 3. Per-table accuracy chain ---
        lines.append("### Per-Table Accuracy Chain")
        lines.append("")
        lines.append("| Table ID | Best Single Method | Best Accuracy | Pipeline Accuracy | Delta |")
        lines.append("|----------|-------------------|---------------|-------------------|-------|")

        for i, tid in enumerate(combo_table_ids):
            # Find best single method name and accuracy
            best_row = con.execute(
                "SELECT method_name, quality_score FROM method_results "
                "WHERE table_id = ? AND quality_score IS NOT NULL "
                "ORDER BY quality_score DESC LIMIT 1",
                (tid,),
            ).fetchone()
            if best_row:
                best_name = best_row[0]
                best_acc = best_single_accs[i]
                pipe_acc = pipeline_accs[i]
                delta = pipe_acc - best_acc
                lines.append(
                    f"| {tid[:40]} | {best_name} | {best_acc:.1f}% "
                    f"| {pipe_acc:.1f}% | {delta:+.1f}% |"
                )

        lines.append("")
        return lines
    finally:
        con.close()




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

    report, extractions = run_stress_test()

    # Print report
    md = report.to_markdown()
    print("\n" + "=" * 70)
    print(md)

    # Save report
    base_dir = Path(__file__).parent.parent
    report_path = base_dir / "STRESS_TEST_REPORT.md"
    report_path.write_text(md, encoding="utf-8")
    print(f"\nReport saved to: {report_path}")

    # Write debug database (all figures, tables, chunks, sections, test results)
    if extractions:
        db_path = base_dir / "_stress_test_debug.db"
        write_debug_database(extractions, report, db_path)
        print(f"Debug database saved to: {db_path} ({db_path.stat().st_size:,} bytes)")
        print(f"  Query with: sqlite3 {db_path} \"SELECT short_name, quality_grade FROM papers\"")
        print(f"  Tables: run_metadata, papers, sections, pages, extracted_tables, extracted_figures, chunks, test_results")

        # Append ground truth comparison summary to the report file if any diffs exist
        gt_md_lines = _build_gt_summary_markdown(db_path)
        if gt_md_lines:
            gt_section = "\n".join(gt_md_lines)
            with open(report_path, "a", encoding="utf-8") as fh:
                fh.write("\n" + gt_section + "\n")
            print(gt_section)

        # Append pipeline depth report to the report file if method data exists
        depth_md_lines = _build_pipeline_depth_report(db_path)
        if depth_md_lines:
            depth_section = "\n".join(depth_md_lines)
            with open(report_path, "a", encoding="utf-8") as fh:
                fh.write("\n" + depth_section + "\n")
            print(depth_section)


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
