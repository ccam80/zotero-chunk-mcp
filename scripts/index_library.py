#!/usr/bin/env python
"""CLI for indexing Zotero library."""
import argparse
import logging
from zotero_chunk_rag.config import Config
from zotero_chunk_rag.indexer import Indexer


def main():
    parser = argparse.ArgumentParser(description="Index Zotero library for semantic search")
    parser.add_argument("--config", type=str, help="Path to config file")
    parser.add_argument("--force", action="store_true", help="Force re-index all")
    parser.add_argument("--limit", type=int, help="Limit documents to index")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

    config = Config.load(args.config)
    errors = config.validate()
    if errors:
        for e in errors:
            logging.error(e)
        return 1

    indexer = Indexer(config)
    stats = indexer.index_all(force_reindex=args.force, limit=args.limit)

    print(f"\nIndexing complete:")
    print(f"  Indexed: {stats['indexed']}")
    print(f"  Skipped: {stats['skipped']}")
    print(f"  Failed: {stats['failed']}")

    final_stats = indexer.get_stats()
    print(f"\nIndex stats:")
    print(f"  Total documents: {final_stats['total_documents']}")
    print(f"  Total chunks: {final_stats['total_chunks']}")
    print(f"  Avg chunks/doc: {final_stats['avg_chunks_per_doc']}")

    return 0


if __name__ == "__main__":
    exit(main())
