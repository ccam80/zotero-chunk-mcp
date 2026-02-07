# Extraction Pipeline Overhaul Plan

## Target Stack
```python
import pymupdf.layout  # Must be first - enables layout analysis
import pymupdf4llm     # Markdown extraction with layout awareness
```

**Key capabilities:**
- Layout-aware text extraction (handles multi-column)
- Font-based heading detection → markdown `#` headers
- Figure extraction with `![](path)` references
- OCR via Tesseract (when language data installed)
- Table extraction (lined tables only)

---

## File Manifest

### Phase 1: Core Extraction (Replace)

| File | Lines | Action | Replacement |
|------|-------|--------|-------------|
| `pdf_extractor.py` | 166 | **Replace** | Thin wrapper around `pymupdf4llm.to_markdown()` |
| `ocr_extractor.py` | 197 | **Remove** | pymupdf.layout handles OCR natively |

**Tests to update:**
- `test_integration_extraction.py` - Update expectations for markdown output
- `test_ocr_extractor.py` - Remove or convert to layout OCR tests
- `test_ocr_autodetect.py` - Remove or convert

### Phase 2: Figure Handling (Simplify)

| File | Lines | Action | Replacement |
|------|-------|--------|-------------|
| `figure_extractor.py` | 300 | **Replace** | Markdown parser for `![](...)` patterns |

**New logic:**
```python
def extract_figures_from_markdown(md_text: str) -> list[Figure]:
    # Find all ![...](path) references
    # Caption = text block immediately before image reference
    # Image path = from the markdown reference
```

**Tests to update:**
- `test_figure_extractor.py` - Rewrite for markdown parsing

### Phase 3: Section Detection (Simplify)

| File | Lines | Action | Replacement |
|------|-------|--------|-------------|
| `section_detector.py` | 594 | **Replace** | Parse markdown `#` headers |

**New logic:**
```python
def detect_sections_from_markdown(md_text: str) -> list[Section]:
    # Parse # and ## headers
    # Map to canonical section names (intro, methods, results, etc.)
    # Font-based detection already done by pymupdf4llm
```

**Tests to update:**
- `test_section_detector.py` - Rewrite for markdown headers

### Phase 4: Table Handling (Evaluate)

| File | Lines | Action | Replacement |
|------|-------|--------|-------------|
| `table_extractor.py` | 643 | **Evaluate** | pymupdf4llm handles lined tables |

**Decision needed:**
- If lined tables sufficient → Remove module
- If gridless tables needed → Keep but document limitation
- Alternative: Accept tables won't be extracted, rely on text search

**Tests to update:**
- `test_table_extractor.py` - Update or remove based on decision

### Phase 5: Chunker (Modify)

| File | Lines | Action | Replacement |
|------|-------|--------|-------------|
| `chunker.py` | 104 | **Modify** | Handle markdown syntax |

**Changes needed:**
- Don't split inside `![](...)` references
- Preserve `#` headers at chunk boundaries
- Handle markdown tables if present

**Tests to update:**
- Existing tests may still pass, add markdown-specific cases

---

## Unchanged Files

| File | Lines | Reason |
|------|-------|--------|
| `embedder.py` | - | Operates on text, format-agnostic |
| `vector_store.py` | - | Operates on chunks, format-agnostic |
| `retriever.py` | - | Operates on search results |
| `reranker.py` | - | Operates on search results |
| `server.py` | - | MCP interface, calls extractors |
| `indexer.py` | - | Orchestration, calls extractors |
| `zotero_client.py` | - | Zotero API, unrelated |
| `config.py` | - | May need new config options |
| `models.py` | - | Data classes, may need updates |

---

## Implementation Order

### Step 1: pdf_extractor.py
1. Create new `markdown_extractor.py` using pymupdf4llm
2. Update `indexer.py` to use new extractor
3. Run real paper tests to verify output quality
4. Remove old `pdf_extractor.py`

### Step 2: ocr_extractor.py
1. Verify Tesseract integration in pymupdf.layout
2. Install Tesseract language data if needed
3. Test on scanned PDF fixture
4. Remove `ocr_extractor.py`

### Step 3: figure_extractor.py
1. Create `markdown_figure_parser.py`
2. Parse `![](...)` references and preceding text
3. Compare figure detection with current approach on real papers
4. Replace if quality is equal or better

### Step 4: section_detector.py
1. Create `markdown_section_parser.py`
2. Parse `#` headers and map to canonical names
3. Compare section detection with current approach
4. Replace if quality is equal or better

### Step 5: table_extractor.py
1. Test pymupdf4llm table output on real papers
2. Document limitation with gridless tables
3. Decide: remove module or keep for validation

### Step 6: chunker.py
1. Add markdown-aware chunking rules
2. Test chunk boundaries don't break markdown syntax
3. Verify embeddings still work correctly

---

## Quality Verification

**Test fixtures:** `tests/fixtures/papers/noname1.pdf`, `noname2.pdf`, `noname3.pdf`

**Verification criteria:**
| Feature | Metric | Current | Target |
|---------|--------|---------|--------|
| Figure detection | Figures found / actual | 5/19 (26%) | >80% |
| Figure captions | Clean captions / found | 5/15 (33%) | >90% |
| Section detection | Sections found / actual | ~25% | >70% |
| Table detection | Tables found / actual | 0/9 | Accept limitation |
| Text quality | Manual review | Multi-column broken | Clean paragraphs |

---

## Dependencies

**Required:**
```
pymupdf>=1.26.6
pymupdf-layout>=1.26.6
pymupdf4llm>=0.2.9
```

**Optional (for OCR):**
```
tesseract-ocr (system package)
tesseract language data (eng.traineddata)
```

---

## Estimated Effort

| Phase | Files | Effort |
|-------|-------|--------|
| 1. Core extraction | 2 | 1-2 hours |
| 2. Figure handling | 1 | 1-2 hours |
| 3. Section detection | 1 | 1-2 hours |
| 4. Table evaluation | 1 | 1 hour |
| 5. Chunker update | 1 | 1 hour |
| 6. Test updates | ~10 | 2-3 hours |
| **Total** | | **8-12 hours** |

**Code reduction:** ~1700 lines → ~300 lines (82% reduction)
