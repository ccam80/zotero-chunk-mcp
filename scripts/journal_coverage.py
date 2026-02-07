#!/usr/bin/env python3
"""
Report journal quartile coverage for indexed documents.

Shows what percentage of documents have journal quartile metadata,
and lists the most common unmatched publications.

Usage:
    python -m scripts.journal_coverage [--config PATH]
"""
import argparse
import json
import sys
from pathlib import Path
from collections import Counter

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from zotero_chunk_rag.journal_ranker import JournalRanker
from zotero_chunk_rag.zotero_client import ZoteroClient
from zotero_chunk_rag.config import Config


def main():
    parser = argparse.ArgumentParser(
        description="Report journal quartile coverage"
    )
    parser.add_argument(
        "--config", "-c",
        help="Path to config file"
    )
    args = parser.parse_args()

    # Load config
    config = Config.load(args.config)
    errors = config.validate()
    if errors:
        for e in errors:
            print(f"Config error: {e}", file=sys.stderr)
        sys.exit(1)

    # Initialize components
    ranker = JournalRanker()
    if not ranker.loaded:
        print("Warning: SCImago data not loaded. Run prepare_scimago.py first.")
        print(f"Expected file: src/zotero_chunk_rag/data/scimago_quartiles.csv")
        return

    client = ZoteroClient(config.zotero_data_dir)

    # Get all items
    print("Loading Zotero library...")
    items = client.get_all_items_with_pdfs()
    print(f"Found {len(items)} items with PDFs")

    # Check coverage
    quartile_counts = Counter()
    unmatched_publications = Counter()
    matched_examples = {}

    for item in items:
        pub = item.publication
        if not pub:
            quartile_counts["(no publication)"] += 1
            continue

        quartile = ranker.lookup(pub)

        if quartile:
            quartile_counts[quartile] += 1
            if quartile not in matched_examples:
                matched_examples[quartile] = pub
        else:
            quartile_counts["(unknown)"] += 1
            unmatched_publications[pub] += 1

    # Report
    total = len(items)
    print(f"\nJournal quartile coverage:")
    for q in ["Q1", "Q2", "Q3", "Q4", "(unknown)", "(no publication)"]:
        count = quartile_counts[q]
        pct = 100 * count / total if total > 0 else 0
        print(f"  {q:16s}: {count:4d} documents ({pct:5.1f}%)")

    # Show matched examples
    print(f"\nExample matches:")
    for q in ["Q1", "Q2", "Q3", "Q4"]:
        if q in matched_examples:
            print(f"  {q}: \"{matched_examples[q][:60]}\"")

    # Show top unmatched
    if unmatched_publications:
        print(f"\nTop unmatched publications:")
        for pub, count in unmatched_publications.most_common(15):
            print(f"  ({count:3d}x) \"{pub[:60]}\"")

    # Show ranker stats
    stats = ranker.stats()
    print(f"\nSCImago data: {stats['total_journals']:,} journals loaded")


if __name__ == "__main__":
    main()
