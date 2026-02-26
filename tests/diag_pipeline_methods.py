"""Diagnostic: reproduce _test_pipeline_methods 0-results bug across all 10 papers."""
import json
import sys
import traceback
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from zotero_chunk_rag.config import Config
from zotero_chunk_rag.zotero_client import ZoteroClient
from zotero_chunk_rag.pdf_processor import extract_document
from zotero_chunk_rag.feature_extraction.pipeline import (
    DEFAULT_CONFIG, Pipeline, _compute_fill_rate,
)
from zotero_chunk_rag.feature_extraction.models import TableContext
from zotero_chunk_rag.feature_extraction.ground_truth import (
    GROUND_TRUTH_DB_PATH, compare_extraction, make_table_id,
)

CORPUS_KEYS = [
    ("SCPXVBLY", "active-inference-tutorial"),
    ("XIAINRVS", "huang-emd-1998"),
    ("C626CYVT", "hallett-tms-primer"),
    ("5SIZVS65", "laird-fick-polyps"),
    ("9GKLLJH9", "helm-coregulation"),
    ("Z9X4JVZ5", "roland-emg-filter"),
    ("YMWV46JA", "friston-life"),
    ("DPYRZTFI", "yang-ppv-meta"),
    ("VP3NJ74M", "fortune-impedance"),
    ("AQ3D94VC", "reyes-lf-hrv"),
]

config = Config.load()
zotero = ZoteroClient(config.zotero_data_dir)
all_items = zotero.get_all_items_with_pdfs()
items_by_key = {i.item_key: i for i in all_items}

import pymupdf

pipeline = Pipeline(DEFAULT_CONFIG)
gt_db_exists = Path(GROUND_TRUTH_DB_PATH).exists()

grand_total_tables = 0
grand_total_grids = 0

for item_key, short_name in CORPUS_KEYS:
    item = items_by_key.get(item_key)
    if item is None:
        print(f"\n[{short_name}] NOT FOUND IN LIBRARY")
        continue

    print(f"\n{'='*60}")
    print(f"[{short_name}] Extracting...")
    try:
        extraction = extract_document(item.pdf_path, write_images=False)
    except Exception as e:
        print(f"  EXTRACTION CRASH: {e}")
        continue

    real_tables = [t for t in extraction.tables if not t.artifact_type]
    print(f"  {len(extraction.tables)} tables ({len(real_tables)} real)")

    try:
        doc = pymupdf.open(str(item.pdf_path))
    except Exception as e:
        print(f"  DOC OPEN CRASH: {e}")
        continue

    try:
        for tab in real_tables:
            grand_total_tables += 1
            table_id = make_table_id(item_key, tab.caption, tab.page_num, tab.table_index)

            page_idx = tab.page_num - 1
            if page_idx < 0 or page_idx >= len(doc):
                print(f"  {table_id}: page out of range")
                continue

            page = doc[page_idx]
            ctx = TableContext(
                page=page,
                page_num=tab.page_num,
                bbox=tab.bbox,
                pdf_path=item.pdf_path,
            )

            try:
                t0 = time.perf_counter()
                result = pipeline.extract(ctx)
                elapsed = time.perf_counter() - t0
            except Exception as e:
                print(f"  {table_id}: PIPELINE CRASH: {e}")
                traceback.print_exc()
                continue

            n_grids = len(result.cell_grids)
            grand_total_grids += n_grids
            w = result.winning_grid
            print(f"  {table_id}: {n_grids} grids, "
                  f"winning={'YES' if w else 'NO'}, {elapsed:.2f}s"
                  + (f", errors={[e[0] for e in result.method_errors]}" if result.method_errors else ""))
    except Exception as e:
        print(f"  OUTER CRASH for [{short_name}]: {e}")
        traceback.print_exc()
    finally:
        doc.close()

print(f"\n{'='*60}")
print(f"GRAND TOTAL: {grand_total_tables} tables, {grand_total_grids} grids")
if grand_total_grids == 0:
    print("*** BUG REPRODUCED: 0 grids ***")
else:
    print(f"Average grids per table: {grand_total_grids / max(grand_total_tables, 1):.1f}")
