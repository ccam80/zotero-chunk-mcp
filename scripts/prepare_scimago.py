#!/usr/bin/env python3
"""
Prepare SCImago journal rankings CSV for use with journal_ranker.

Downloads or processes a raw SCImago CSV export and produces a slim
two-column lookup file: title_normalized, quartile

Usage:
    python -m scripts.prepare_scimago --input scimagojr_2024.csv --output src/zotero_chunk_rag/data/scimago_quartiles.csv

The raw SCImago CSV can be downloaded from:
    https://www.scimagojr.com/journalrank.php (click "Download data")
"""
import argparse
import csv
import re
import sys
from pathlib import Path
from collections import defaultdict


def normalize_title(title: str) -> str:
    """Normalize a journal title for lookup."""
    title = title.lower()
    title = re.sub(r"[&:\-/]", " ", title)
    title = re.sub(r"\s+", " ", title)
    return title.strip()


def quartile_rank(q: str) -> int:
    """Convert quartile to numeric rank (lower is better)."""
    return {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}.get(q, 5)


def main():
    parser = argparse.ArgumentParser(
        description="Prepare SCImago journal rankings CSV"
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to raw SCImago CSV download"
    )
    parser.add_argument(
        "--output", "-o",
        required=True,
        help="Path for output CSV (title_normalized,quartile)"
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    # Read raw CSV and collect best quartile per journal
    # (journals may appear in multiple subject areas)
    journal_quartiles: dict[str, str] = {}
    total_rows = 0
    duplicate_journals = 0

    print(f"Reading {input_path}...")

    with open(input_path, "r", encoding="utf-8") as f:
        # Try to detect the CSV format
        sample = f.read(2048)
        f.seek(0)

        # SCImago uses semicolon delimiter
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        reader = csv.DictReader(f, delimiter=dialect.delimiter)

        # Find the title and quartile columns
        # SCImago uses "Title" and "SJR Best Quartile"
        title_col = None
        quartile_col = None

        for col in reader.fieldnames or []:
            col_lower = col.lower()
            if "title" in col_lower and title_col is None:
                title_col = col
            if "quartile" in col_lower:
                quartile_col = col

        if not title_col or not quartile_col:
            print(f"Error: Could not find title and quartile columns", file=sys.stderr)
            print(f"Found columns: {reader.fieldnames}", file=sys.stderr)
            sys.exit(1)

        print(f"Using columns: title='{title_col}', quartile='{quartile_col}'")

        for row in reader:
            total_rows += 1
            title = row.get(title_col, "").strip()
            quartile = row.get(quartile_col, "").strip().upper()

            if not title or quartile not in ("Q1", "Q2", "Q3", "Q4"):
                continue

            normalized = normalize_title(title)

            if normalized in journal_quartiles:
                duplicate_journals += 1
                # Keep the better (lower) quartile
                existing = journal_quartiles[normalized]
                if quartile_rank(quartile) < quartile_rank(existing):
                    journal_quartiles[normalized] = quartile
            else:
                journal_quartiles[normalized] = quartile

    # Write output CSV
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["title_normalized", "quartile"])

        for title, quartile in sorted(journal_quartiles.items()):
            writer.writerow([title, quartile])

    # Report statistics
    counts = defaultdict(int)
    for q in journal_quartiles.values():
        counts[q] += 1

    print(f"\nProcessed {total_rows:,} rows")
    print(f"Found {len(journal_quartiles):,} unique journals")
    print(f"Resolved {duplicate_journals:,} duplicates (kept best quartile)")
    print(f"\nQuartile distribution:")
    for q in ["Q1", "Q2", "Q3", "Q4"]:
        pct = 100 * counts[q] / len(journal_quartiles) if journal_quartiles else 0
        print(f"  {q}: {counts[q]:,} ({pct:.1f}%)")

    print(f"\nOutput written to: {output_path}")


if __name__ == "__main__":
    main()
