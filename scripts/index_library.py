#!/usr/bin/env python
"""CLI for indexing Zotero library."""
import argparse
import json
import logging
from pathlib import Path
from zotero_chunk_rag.config import Config
from zotero_chunk_rag.indexer import Indexer


def _truncate(s: str, maxlen: int = 60) -> str:
    return s[:maxlen - 1] + "…" if len(s) > maxlen else s


def main():
    parser = argparse.ArgumentParser(description="Index Zotero library for semantic search")
    parser.add_argument("--config", type=str, help="Path to config file")
    parser.add_argument("--force", action="store_true", help="Force re-index all")
    parser.add_argument("--limit", type=int, help="Limit documents to index")
    parser.add_argument("--item-key", type=str, help="Index only the item with this Zotero key")
    parser.add_argument("--title-pattern", type=str, help="Index only items whose title matches this regex pattern")
    parser.add_argument("--no-ocr", action="store_true", help="Disable OCR even if Tesseract is available")
    parser.add_argument("--tables", action="store_true", help="Enable table extraction and indexing (requires PyMuPDF 1.23+)")
    parser.add_argument("--report", type=str, metavar="FILE", help="Output indexing report to FILE (.json or .md)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

    config = Config.load(args.config)

    # Override config from CLI flags
    if args.no_ocr:
        config.ocr_enabled = False
    if args.tables:
        config.tables_enabled = True

    errors = config.validate()
    if errors:
        for e in errors:
            logging.error(e)
        return 1

    indexer = Indexer(config)

    # -- Library diagnostics --
    diag = indexer.get_library_diagnostics()
    print(f"\nZotero library: {diag['total_items']} items")
    print(f"  No attachment:        {diag['no_attachment']}")
    if diag["non_pdf_attachment_types"]:
        for ctype, count in sorted(diag["non_pdf_attachment_types"].items()):
            print(f"  Non-PDF only ({ctype}): {count}")
    print(f"  PDF (file on disk):   {diag['pdf_resolved']}")
    if diag["pdf_unresolved"]:
        print(f"  PDF (file missing):   {len(diag['pdf_unresolved'])}")
        for key, title, reason in diag["pdf_unresolved"]:
            print(f"    {key}  {_truncate(title)}  — {reason}")

    # -- Indexing --
    stats = indexer.index_all(
        force_reindex=args.force,
        limit=args.limit,
        item_key=args.item_key,
        title_pattern=args.title_pattern,
    )

    results = stats["results"]
    for category, label in [
        ("indexed", "Indexed"),
        ("empty", "Empty (no text)"),
        ("failed", "Failed"),
        ("skipped", "Skipped (unchanged)"),
    ]:
        items = [r for r in results if r.status == category]
        if not items:
            continue
        print(f"\n{label} ({len(items)}):")
        for r in items:
            detail = f"  {r.item_key}  {_truncate(r.title)}"
            if r.n_chunks or r.n_tables:
                parts = []
                if r.n_chunks:
                    parts.append(f"{r.n_chunks} chunks")
                if r.n_tables:
                    parts.append(f"{r.n_tables} tables")
                detail += f"  [{', '.join(parts)}]"
            if r.scanned_pages_skipped:
                detail += f"  [⚠ {r.scanned_pages_skipped} scanned page(s) skipped]"
            if r.reason:
                detail += f"  — {r.reason}"
            print(detail)

    # -- Summary --
    print(f"\nIndexing summary:")
    print(f"  Already in index: {stats['already_indexed']}")
    print(f"  Newly indexed:    {stats['indexed']}")
    print(f"  Empty (no text):  {stats['empty']}")
    print(f"  Skipped (cached): {stats['skipped']}")
    print(f"  Failed:           {stats['failed']}")

    # Report scanned pages skipped
    scanned_skipped = stats.get('scanned_pages_skipped', 0)
    if scanned_skipped > 0:
        print(f"\n⚠ {scanned_skipped} scanned page(s) could not be processed (no OCR available).")
        print(f"  Install Tesseract for OCR support: https://github.com/tesseract-ocr/tesseract")

    final_stats = indexer.get_stats()
    print(f"\nIndex totals:")
    print(f"  Documents: {final_stats['total_documents']}")
    print(f"  Chunks:    {final_stats['total_chunks']}")
    print(f"  Avg chunks/doc: {final_stats['avg_chunks_per_doc']}")

    # Show quality distribution if available
    quality_dist = stats.get('quality_distribution', {})
    if any(quality_dist.values()):
        print(f"\nQuality distribution:")
        for grade in ["A", "B", "C", "D", "F"]:
            count = quality_dist.get(grade, 0)
            if count > 0:
                print(f"  Grade {grade}: {count}")

    # Generate report if requested
    if args.report:
        from zotero_chunk_rag.models import IndexReport

        report = IndexReport(
            total_items=len(results),
            indexed=stats["indexed"],
            skipped=stats["skipped"],
            failed=stats["failed"],
            empty=stats["empty"],
            already_indexed=stats["already_indexed"],
            results=results,
            extraction_stats=stats.get("extraction_stats", {}),
            quality_distribution=stats.get("quality_distribution", {}),
        )

        report_path = Path(args.report)
        if report_path.suffix == ".json":
            report_path.write_text(json.dumps(report.to_dict(), indent=2))
        else:
            report_path.write_text(report.to_markdown())

        print(f"\nReport written to: {report_path}")

    return 0


if __name__ == "__main__":
    exit(main())
