"""Quick diagnostic: what does VL put in block.content for table blocks?"""
from __future__ import annotations
import os, sys
from pathlib import Path

os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT / "tests"))

# Apply Paddle int() fix
import numpy as np, paddle
def _safe_int(var):
    numel = np.prod(var.shape)
    assert numel == 1
    assert var._is_initialized()
    return int(np.array(var).item())
paddle.Tensor.__int__ = _safe_int

from stress_test_real_library import CORPUS
from zotero_chunk_rag.config import Config
from zotero_chunk_rag.zotero_client import ZoteroClient

config = Config.load()
zotero = ZoteroClient(config.zotero_data_dir)
all_items = zotero.get_all_items_with_pdfs()
items_by_key = {i.item_key: i for i in all_items}

# Use laird-fick-polyps (has 5 tables)
item_key, short_name = CORPUS[3][:2]
item = items_by_key[item_key]
print(f"Paper: {short_name} ({item_key})")

from paddleocr import PaddleOCRVL
pipeline = PaddleOCRVL(pipeline_version="v1.5", device="gpu:0", use_queues=False)
results = pipeline.predict(str(item.pdf_path))
restructured = pipeline.restructure_pages(results, merge_tables=True)

for page_result in restructured:
    page_idx = page_result.get("page_index", 0)
    for block in page_result.get("parsing_res_list", []):
        label = getattr(block, "label", "")
        if "table" not in label.lower():
            continue
        content = getattr(block, "content", "")
        bbox = getattr(block, "bbox", [])
        print(f"\n{'='*60}")
        print(f"Page {page_idx+1}, label={label}, bbox={bbox}")
        print(f"Content type: {type(content).__name__}, len={len(content)}")
        print(f"First 500 chars:")
        print(content[:500])
        print(f"{'='*60}")
