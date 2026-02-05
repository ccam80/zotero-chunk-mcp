# Limitation Fixes: MVP Launch Remediation Plan

This document outlines how to address the limitations documented in [LIMITATIONS.md](LIMITATIONS.md), prioritized for a hypothetical MVP launch.

---

## Tier 1: Fix Before Launch (Critical)

| Issue | Fix Approach | Effort | Why Critical |
|-------|--------------|--------|--------------|
| **No structured metadata search** | Add Zotero metadata to ChromaDB as filterable fields. Expose `author`, `year`, `tags`, `collections` as query parameters. ChromaDB already supports `where` clauses — just need to populate the metadata. | 2-3 days | Table-stakes feature. Users will immediately ask "show me Smith's papers" and be frustrated. |
| **SCImago data not bundled** | Ship a compressed CSV in `src/zotero_chunk_rag/data/`. Update annually. Add a CI job to refresh from SCImago. | 1 day | Zero-config experience is essential. Users shouldn't run prep scripts. |
| **OCR installation UX** | Bundle `tesseract.js` (WASM-based OCR) as fallback when system Tesseract unavailable. Slower but works everywhere. | 2-3 days | First scanned PDF shouldn't fail. Graceful degradation is better than hard failure. |
| **Silent indexing failures** | Add a `--report` flag that outputs a JSON/markdown summary: papers indexed, papers failed, papers skipped, extraction quality scores. | 1 day | Users need visibility into what's in their index. |

---

## Tier 2: Fix Soon After Launch (Important)

| Issue | Fix Approach | Effort | Notes |
|-------|--------------|--------|-------|
| **Section detection unreliable** | Add ML-based fallback using a small fine-tuned classifier (distilbert-base). Train on 1000 labeled academic sections. Use rule-based as primary, ML as tiebreaker. | 1-2 weeks | The current heuristics are good for ~70% of papers. ML can catch the rest. |
| **No modified PDF detection** | Store file hash (MD5/SHA256) in ChromaDB metadata. On incremental index, compare hashes. If changed, re-index. | 1 day | Easy fix, just wasn't implemented. |
| **Fuzzy journal matching too aggressive** | Raise threshold to 90%, add manual override file for known mismatches. Log fuzzy matches for review. | 0.5 day | Conservative matching is better than false positives affecting ranking. |
| **Table continuation merging naive** | Change heuristic: only merge if continuation is on page N+1 of primary AND has matching column structure (header alignment check). Uncaptioned tables on same page stay separate. | 1 day | Structural matching is more reliable than "no caption = continuation". |

---

## Tier 3: Post-Launch Roadmap (Nice to Have)

| Issue | Fix Approach | Effort | Notes |
|-------|--------------|--------|-------|
| **No citation graph** | Integrate OpenAlex API. On index, lookup DOI → get citing/cited papers. Store as graph edges. Add `find_citing(doc_id)` and `find_cited_by(doc_id)` tools. | 1-2 weeks | OpenAlex is free and has excellent coverage. This is the right approach. |
| **Gemini API lock-in** | Add `embedding_provider` config option. Implement `LocalEmbedder` using `sentence-transformers` with `all-MiniLM-L6-v2` as default. Same interface as `Embedder`. | 3-5 days | Important for privacy-conscious users and those without API budget. |
| **No quality metrics** | Add extraction quality score: (text chars / page count) ratio, OCR confidence if applicable, gibberish detection (entropy check). Store in metadata, expose in `get_index_stats()`. | 2-3 days | Helps users identify problematic papers. |
| **Figure extraction** | Use PyMuPDF to extract images, run through BLIP-2 or similar for captioning, embed captions. Add `search_figures` tool. | 1-2 weeks | Lower priority than tables, but valuable for methodology papers. |

---

## Tier 4: Won't Fix / Out of Scope

| Issue | Recommendation |
|-------|----------------|
| **Multi-user support** | Out of scope for personal tool. If needed, fork and build a proper backend service. |
| **Web UI** | Claude Code is the UI. A web UI would be a separate product. |
| **Zotero plugin** | Complex, requires Zotero extension development. Better to improve CLI/MCP experience. |

---

## Implementation Details

### Structured Metadata Search (Highest Priority)

This is surprisingly easy because ChromaDB already supports it:

```python
# Current: only semantic search
results = collection.query(query_embeddings=[emb], n_results=10)

# With metadata filters (already supported):
results = collection.query(
    query_embeddings=[emb],
    n_results=10,
    where={
        "$and": [
            {"author": {"$contains": "Smith"}},  # Need to add this field
            {"year": {"$gte": 2020}},
            {"tags": {"$contains": "HRV"}}       # Need to add this field
        ]
    }
)
```

The fix is:
1. Extend `add_chunks()` to include `authors_list`, `tags`, `collections` in metadata
2. Add filter parameters to `search_papers()` and `search_topic()`
3. Done.

**Files to modify:**
- `src/zotero_chunk_rag/vector_store.py` — add fields to metadata dict
- `src/zotero_chunk_rag/server.py` — add filter parameters to tools
- `src/zotero_chunk_rag/zotero_client.py` — extract tags/collections from Zotero DB

---

### ML Section Detection Fallback

The architecture would be:

```python
def detect_section(text: str, heading: str) -> tuple[str, float]:
    # Try rule-based first
    rule_result, rule_conf = rule_based_detect(heading)
    if rule_conf > 0.8:
        return rule_result, rule_conf

    # Fall back to ML
    ml_result, ml_conf = ml_classifier.predict(text[:512])

    # Ensemble: prefer rule-based if confident, else ML
    if rule_conf > 0.5 and ml_conf < 0.7:
        return rule_result, rule_conf
    return ml_result, ml_conf
```

**Training data sources:**
- PubMed Central open access subset (has section labels in XML)
- arXiv papers (different structure, good for generalization)
- ~1000 manually labeled examples from diverse fields

**Model options:**
- `distilbert-base-uncased` fine-tuned on section classification (~66MB)
- `all-MiniLM-L6-v2` with classification head (~22MB, faster)
- Ship as ONNX for cross-platform inference

---

### Citation Graph via OpenAlex

OpenAlex is free, has excellent coverage, and requires no API key:

```python
import httpx

def get_citations(doi: str) -> dict:
    # Get paper metadata including citations
    resp = httpx.get(f"https://api.openalex.org/works/doi:{doi}")
    work = resp.json()

    return {
        "cited_by_count": work["cited_by_count"],
        "cited_by_api_url": work["cited_by_api_url"],  # Paginated list
        "references": [ref["id"] for ref in work.get("referenced_works", [])]
    }
```

**Implementation approach:**
1. During indexing, lookup DOI in OpenAlex
2. Store `cited_by_count` and `references` list in document metadata
3. Create separate `citations` collection with edges: `(source_doi, target_doi, relationship)`
4. Add tools: `find_papers_citing(doc_id)`, `find_papers_cited_by(doc_id)`
5. For papers not in Zotero, fetch minimal metadata from OpenAlex on demand

**Rate limits:** OpenAlex allows 100k requests/day without API key, 10 requests/second.

---

### Local Embedding Support

Add a provider abstraction:

```python
# config.json
{
    "embedding_provider": "local",  // or "gemini"
    "local_embedding_model": "all-MiniLM-L6-v2"
}

# New file: src/zotero_chunk_rag/local_embedder.py
from sentence_transformers import SentenceTransformer

class LocalEmbedder:
    def __init__(self, model: str = "all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model)

    def embed(self, texts: list[str], task_type: str = None) -> list[list[float]]:
        # task_type ignored for local models (symmetric embeddings)
        return self.model.encode(texts).tolist()

    def embed_query(self, query: str) -> list[float]:
        return self.model.encode(query).tolist()
```

**Considerations:**
- First run downloads model (~90MB for MiniLM)
- CPU inference is slow for large batches — consider batching with progress bar
- Embedding dimensions differ between models — document this clearly

---

### Hash-Based Update Detection

Simple addition to incremental indexing:

```python
import hashlib

def get_file_hash(path: Path) -> str:
    """Compute MD5 hash of file contents."""
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()

# In indexer.py, add to document metadata:
doc_meta = {
    ...
    "pdf_hash": get_file_hash(pdf_path),
}

# In incremental check:
def needs_reindex(doc_id: str, pdf_path: Path) -> bool:
    existing = store.get_document_meta(doc_id)
    if not existing:
        return True  # New document
    current_hash = get_file_hash(pdf_path)
    return current_hash != existing.get("pdf_hash")
```

---

### Indexing Report

Add `--report` flag to index script:

```python
@dataclass
class IndexReport:
    total_items: int
    indexed: int
    skipped: int  # Already in index
    failed: list[tuple[str, str]]  # (doc_id, error_message)
    warnings: list[tuple[str, str]]  # (doc_id, warning)

    def to_markdown(self) -> str:
        lines = [
            f"# Indexing Report",
            f"",
            f"- **Total items:** {self.total_items}",
            f"- **Indexed:** {self.indexed}",
            f"- **Skipped (already indexed):** {self.skipped}",
            f"- **Failed:** {len(self.failed)}",
            f"",
        ]
        if self.failed:
            lines.append("## Failures")
            for doc_id, error in self.failed:
                lines.append(f"- `{doc_id}`: {error}")
        if self.warnings:
            lines.append("## Warnings")
            for doc_id, warning in self.warnings:
                lines.append(f"- `{doc_id}`: {warning}")
        return "\n".join(lines)
```

---

## Priority Matrix

```
                    HIGH IMPACT
                         │
    ┌────────────────────┼────────────────────┐
    │                    │                    │
    │  Structured        │  Citation Graph    │
    │  Metadata Search   │                    │
    │                    │                    │
    │  SCImago Bundling  │  Local Embeddings  │
    │                    │                    │
LOW ├────────────────────┼────────────────────┤ HIGH
EFFORT                   │                    │ EFFORT
    │  Hash-based        │  ML Section        │
    │  Update Detection  │  Detection         │
    │                    │                    │
    │  Fuzzy Match       │  Figure            │
    │  Threshold         │  Extraction        │
    │                    │                    │
    └────────────────────┼────────────────────┘
                         │
                    LOW IMPACT
```

---

## Launch Checklist

### Must Have (Week 1)
- [ ] Structured metadata search (author, year, tags filters)
- [ ] Bundle SCImago CSV in package data
- [ ] Indexing report with `--report` flag

### Should Have (Week 2)
- [ ] WASM OCR fallback (tesseract.js)
- [ ] Hash-based PDF update detection
- [ ] Raise fuzzy match threshold to 90%

### Nice to Have (Month 1)
- [ ] Citation graph via OpenAlex
- [ ] Local embedding option
- [ ] Improved table continuation detection

### Future Roadmap
- [ ] ML section detection
- [ ] Figure extraction
- [ ] Quality metrics dashboard
