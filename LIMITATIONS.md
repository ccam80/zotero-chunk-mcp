# Known Limitations

This document provides an honest assessment of the current state of zotero-chunk-rag as a research tool. Understanding these limitations will help you decide if this tool is appropriate for your use case and set realistic expectations.

## Who This Tool Is For

This tool is appropriate for:
- Researchers comfortable with CLI tools and debugging
- PhD students or academics who want semantic search over their personal library
- Users who understand its limitations and can work around them

This tool is **not** appropriate for:
- General academic users expecting "install and go"
- Teams who need shared access to a library
- Anyone who needs citation graphs or structured metadata queries
- Production environments requiring high reliability

---

## Critical Weaknesses

### 1. Section Detection is Unreliable

The section detection pipeline uses keyword matching and structural heuristics. It will fail on:

- **Non-English papers** — keywords are English-only
- **Unusual section names** — "Observations", "Key Insights", "Empirical Analysis" won't match
- **Papers without numbered headings** — the scheme detection relies on patterns like "1.", "I.", etc.
- **Two-column layouts** — where headings span columns or appear in unusual positions

**Impact:** Section weights become meaningless for an estimated 20-30% of papers. A result from "Introduction" might actually be from "Results" but was misclassified, affecting reranking accuracy.

### 2. Table Continuation Merging is Naive

The table extraction assumes that uncaptioned tables are continuations of the previous table. This is incorrect for:

- Supplementary tables intentionally left unlabeled
- Papers that use visual separation instead of captions
- Nested tables or sub-tables within a section

**Impact:** False merges can corrupt table data. A standalone subgroup analysis table might be incorrectly appended to an unrelated table.

### 3. No Structured Metadata Search

You cannot filter by:
- Author name
- DOI or ISBN
- Keywords from Zotero tags
- Collection membership
- Date added to library

All searches are semantic. Want "all papers by Smith 2020-2024"? That's a semantic query that may return irrelevant results.

**Impact:** Researchers often want exact author or keyword filters. This is table-stakes functionality for most research tools.

### 4. No Citation Graph

There is no way to:
- Find papers that cite a given paper
- Find papers cited by a given paper
- Explore citation networks or influence

**Impact:** Citation relationships are fundamental to research workflows. "What cites Heathers 2014?" is a basic question this tool cannot answer.

### 5. Gemini API Lock-in

- No local embedding option (SentenceTransformers, ONNX models, etc.)
- API calls cost money and have latency
- Library-wide re-indexing on config changes is expensive

**Impact:** Users without budget for Gemini API cannot use this tool. Privacy-conscious users cannot keep embeddings local.

### 6. SCImago Journal Data is Static

The journal ranking depends on a pre-processed CSV that:
- Is not bundled with the package (must be generated manually)
- Requires running `scripts/prepare_scimago.py` with downloaded SCImago data
- Gets stale as new journals appear or rankings change

**Impact:** Journal weights are meaningless until user runs a preparation script. New journals in fast-moving fields (ML, biotech) won't have quartile data.

### 7. OCR Requires External Installation

- Tesseract must be installed separately at the system level
- Windows installation requires manual download and PATH configuration
- Tests fail if Tesseract isn't present

**Impact:** Many users will hit OCR errors on their first scanned PDF. The fix requires leaving the tool to install system software.

### 8. No Update Detection for Modified PDFs

Incremental indexing only checks "does this doc_id exist in the index?" It does not detect:
- Re-downloaded PDFs with corrections or updated versions
- PDFs replaced with different files
- Metadata changes in Zotero (title corrections, added authors)

**Impact:** Users must `--force` re-index after replacing a PDF, or live with stale chunks from the old version.

### 9. Aggressive Fuzzy Journal Matching

The fuzzy matching threshold of 85% can cause false positives:
- "IEEE Transactions on Biomedical Engineering" might match "IEEE Transactions on Biomedical Circuits and Systems"
- These are different journals with potentially different quartiles

**Impact:** False positive quartile assignments can boost or penalize the wrong papers in reranking.

### 10. No Quality Metrics or Extraction Visibility

No visibility into:
- PDF extraction quality (OCR confidence, gibberish detection)
- Chunk embedding quality or anomalies
- Papers that failed indexing silently
- Overall index health

**Impact:** Poor-quality PDFs silently pollute results. Users have no way to identify problematic papers in their library.

---

## Missing Features

| Feature | Status | Notes |
|---------|--------|-------|
| Full-text boolean search | Missing | AND/OR/NOT operators, phrase matching |
| Author/year/DOI filters | Missing | Structured queries on metadata fields |
| Citation graph | Missing | Would require OpenAlex or Semantic Scholar integration |
| Figure extraction | Missing | Only tables are extracted, not figures |
| Local embedding models | Missing | Gemini API is the only option |
| Batch export (BibTeX, RIS) | Missing | No way to export search results |
| Web UI | Missing | CLI and MCP tools only |
| Zotero plugin | Missing | No bidirectional sync or in-app integration |
| Multi-user support | Missing | Single-user, single-library only |

---

## Deployment Concerns

### First-Run Experience

The initial setup requires multiple manual steps:
1. Install Tesseract OCR (optional but recommended)
2. Download and process SCImago data
3. Run the indexing script
4. Configure the MCP server in Claude Code settings

### Index Versioning

There is no versioning or migration for the ChromaDB index. If you change `chunk_size` or `embedding_dimensions` mid-project, old chunks are incompatible. The only option is a full re-index.

### Memory Usage

ChromaDB loads the index into memory for queries. The memory footprint at scale (10,000+ papers) has not been characterized. Large libraries may experience performance issues.

### Silent Failures

Indexing failures are logged but not surfaced to the user. There is no summary of failed papers or incomplete documents after an indexing run.

---

## Recommendations

If you choose to use this tool despite its limitations:

1. **Review indexed papers periodically** — use `get_index_stats()` to check coverage
2. **Don't trust section labels blindly** — verify important results manually
3. **Use year filters** — they're the only structured filter available
4. **Keep expectations modest** — this is semantic search, not a full research management system
5. **Report issues** — the tool is under active development

---

## Contributing

If you'd like to help address these limitations, contributions are welcome. Priority areas:

1. Structured metadata search (author, keyword, DOI filters)
2. Local embedding model support
3. Citation graph integration (OpenAlex API)
4. Improved section detection for non-standard papers
5. Index health and quality metrics
