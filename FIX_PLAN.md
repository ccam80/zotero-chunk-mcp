# Stress Test Fix Plan

Concrete implementation plan for fixes identified by real-life stress test
(`real_life_test.py`). All decisions finalized. Each fix is self-contained
with exact file paths, function signatures, and test specifications.

**Test fixtures**: `tests/fixtures/papers/noname{1,2,3}.pdf`
**Roland paper** (not a test fixture — used in `real_life_test.py` only):
`C:\Users\cca79\Zotero\storage\IG8ZALE8\Roland et al. - 2019 - ...pdf` (Z9X4JVZ5)

---

## Fix 1: `_apply_text_filters` crash — DONE

**Files changed**: `server.py`, `models.py`, `retriever.py`

- Added `_meta_get()` helper — uses `.metadata.get()` for StoredChunk, `getattr()` for RetrievalResult
- Added missing `tags`/`collections` fields to RetrievalResult dataclass
- Populated those fields in retriever construction
- Verified: 120 tests pass, targeted test confirms both code paths

---

## Fix 6c: Caption regex tightening + multi-figure page splitting + bbox validation

**Status**: Approved — implement first (unblocks accurate figure/table counts)
**Modified files**: `src/zotero_chunk_rag/_figure_extraction.py`, `src/zotero_chunk_rag/pdf_processor.py`

### Part 1: Tighten caption regex (all 4 regexes)

The current caption regex matches body-text sentences starting with "Figure N"
(e.g. "Figure 9 shows the resulting..."). Add a required delimiter after the
number to only match real captions like "Figure 9. Transfer function...".

**File `src/zotero_chunk_rag/_figure_extraction.py` line 27-30**:

Change:
```python
_FIG_CAPTION_RE = re.compile(
    r"^(?:Figure|Fig\.?)\s+(\d+|[IVXLCDM]+)",
    re.IGNORECASE,
)
```
To:
```python
_FIG_CAPTION_RE = re.compile(
    r"^(?:Figure|Fig\.?)\s+(\d+|[IVXLCDM]+)\s*[.:()\u2014\u2013-]",
    re.IGNORECASE,
)
```

**File `src/zotero_chunk_rag/pdf_processor.py` lines 33-36, 39-44**:

Change `_TABLE_CAPTION_RE` (line 33):
```python
_TABLE_CAPTION_RE = re.compile(
    r"^(?:\*\*)?(?:Table|Tab\.)\s+(\d+|[IVXLCDM]+)\s*[.:()\u2014\u2013-]",
    re.IGNORECASE,
)
```

Change `_FIG_CAPTION_RE_COMP` (line 39):
```python
_FIG_CAPTION_RE_COMP = re.compile(
    r"^(?:Figure|Fig\.?)\s+(\d+|[IVXLCDM]+)\s*[.:()\u2014\u2013-]", re.IGNORECASE,
)
```

Change `_TABLE_CAPTION_RE_COMP` (line 42):
```python
_TABLE_CAPTION_RE_COMP = re.compile(
    r"^(?:\*\*)?(?:Table|Tab\.)\s+(\d+|[IVXLCDM]+)\s*[.:()\u2014\u2013-]", re.IGNORECASE,
)
```

### Part 2: Multi-figure page splitting

**Problem**: When the layout ML groups two figures into one picture box, only
one figure is created (the second caption is silently dropped). This happens
when an internal caption falls INSIDE the picture box's y-range — confirmed
on roland pages 5 and 17.

**Changes to `_figure_extraction.py`**:

**Step A — Change `_find_captions_on_page` return type** (line 158):

Current signature returns `list[str]`. Change to return y-positions too:
```python
def _find_captions_on_page(
    page: pymupdf.Page,
    prefix_re: re.Pattern,
) -> list[tuple[float, str]]:
    """Find caption text blocks matching prefix_re, sorted by y-position.

    Returns list of (y_center, caption_text).
    """
```

Change the last two lines from:
```python
    hits.sort(key=lambda x: x[0])
    return [text for _, text in hits]
```
To:
```python
    hits.sort(key=lambda x: x[0])
    return hits  # list of (y_center, text)
```

**Step B — Update `extract_figures()` to use new return type**:

In Step 2 (line 93-98), `page_captions` changes type from
`dict[int, list[str]]` to `dict[int, list[tuple[float, str]]]`:
```python
    page_captions: dict[int, list[tuple[float, str]]] = {}
    # ...
    for page_num_0, page in enumerate(doc):
        page_num = page_num_0 + 1
        captions = _find_captions_on_page(page, _FIG_CAPTION_RE)
        if captions:
            page_captions[page_num] = captions
```

**Step C — Add bbox clipping in Step 1** (inside the picture-box loop, after
creating the `rect` at line 87):
```python
            rect = pymupdf.Rect(x0, y0, x1, y1)
            # Clip to page bounds — layout ML sometimes produces
            # out-of-bounds boxes (e.g. roland p17: x=-1389..2045)
            page_rect = doc[page_num - 1].rect
            rect = rect & page_rect  # pymupdf Rect intersection
            if rect.is_empty:
                continue
```

**Step D — Add multi-figure split step** between Step 4 (merge) and Step 5
(build). Insert a new Step 4.5:

```python
    # Step 4.5: Split picture boxes that contain multiple figures.
    # Detection: a caption's y-center falls INSIDE a picture box's y-range.
    # When found, split the box at each internal caption boundary.
    for page_num in list(page_figures.keys()):
        rects = page_figures[page_num]
        captions = page_captions.get(page_num, [])
        if len(captions) <= len(rects):
            continue  # enough boxes for all captions, no split needed

        new_rects: list[pymupdf.Rect] = []
        used_captions: set[int] = set()  # indices of captions used as split points

        for rect in sorted(rects, key=lambda r: r.y0):
            # Find captions whose y_center falls inside this rect
            internal: list[tuple[int, float, str]] = []
            for ci, (cy, ctext) in enumerate(captions):
                if rect.y0 < cy < rect.y1:
                    internal.append((ci, cy, ctext))

            if not internal:
                new_rects.append(rect)
                continue

            # Split the box at each internal caption position.
            # Internal caption belongs to the region ABOVE it.
            internal.sort(key=lambda x: x[1])  # sort by y
            split_y = rect.y0
            for ci, cy, ctext in internal:
                used_captions.add(ci)
                # Find the caption's full bbox to get its bottom edge
                # Use cy as approximate split — region above caption
                # is one figure, region below is the next.
                # Split point: caption y_center (top of caption block)
                sub = pymupdf.Rect(rect.x0, split_y, rect.x1, cy)
                if not sub.is_empty and abs(sub.y1 - sub.y0) > 20:
                    new_rects.append(sub)
                # Next region starts below the caption.
                # Estimate caption height as ~40pts and skip past it.
                split_y = cy + 40

            # Final region: from last split to bottom of original box
            final = pymupdf.Rect(rect.x0, split_y, rect.x1, rect.y1)
            if not final.is_empty and abs(final.y1 - final.y0) > 20:
                new_rects.append(final)

        if new_rects:
            page_figures[page_num] = new_rects
```

**Step E — Update Step 5 caption pairing** to extract text from tuples:

Change line 123:
```python
        captions = page_captions.get(page_num, [])
```
To:
```python
        captions_with_y = page_captions.get(page_num, [])
        caption_texts = [text for _, text in captions_with_y]
```

And change line 126:
```python
            caption = captions[i] if i < len(captions) else None
```
To:
```python
            caption = caption_texts[i] if i < len(caption_texts) else None
```

### Tests for Fix 6c

**No existing tests should break** — the regex tightening only removes false
positives, and the fixture papers don't have "Figure N shows..." body text
blocks. Verify by running:
```
pytest tests/test_figure_quality.py tests/test_table_quality.py tests/test_extraction_completeness.py -v
```

**New test** — add to `tests/test_figure_quality.py`:

```python
def test_no_body_text_as_figure_caption():
    """Figure captions must start with 'Figure N.' or 'Fig. N.', never
    body text like 'Figure 9 shows...'."""
    import re
    body_text_re = re.compile(
        r"^(?:Figure|Fig\.?)\s+\d+\s+(?:show|depict|illustrat|present|display)",
        re.IGNORECASE,
    )
    for pdf_name in EXPECTED:
        figures = _get_figures(pdf_name)
        for fig in figures:
            if fig.caption:
                assert not body_text_re.match(fig.caption), (
                    f"{pdf_name}: fig {fig.figure_index} caption is body text: "
                    f"{fig.caption[:80]!r}"
                )
```

---

## Fix 6a: Garbage table filter

**Status**: Approved
**File**: `src/zotero_chunk_rag/pdf_processor.py`, function `_extract_tables_native()`

### Implementation

Add a fill-rate filter after table construction, before appending to the
`tables` list. At line 538 (inside the `for i, (_, bbox, headers, rows)`
loop), add a check before the `tables.append(...)`:

```python
            # Filter garbage tables: very low fill + no caption = misclassified
            # layout element (block diagrams, reference lists parsed as grids)
            total_cells = len(rows) * max(len(r) for r in rows) if rows else 0
            filled_cells = sum(1 for r in rows for c in r if c.strip())
            fill_rate = filled_cells / max(1, total_cells)
            if fill_rate < 0.15 and caption is None:
                logger.debug(
                    "Skipping garbage table on page %d: %dx%d fill=%.0f%% no caption",
                    page_num, len(rows), max(len(r) for r in rows) if rows else 0,
                    fill_rate * 100,
                )
                continue
```

### Tests

**Existing tests should still pass** — the 3 fixture papers don't have
garbage tables (all tables have captions and reasonable fill).

**New test** — add to `tests/test_table_quality.py`:

```python
def test_no_uncaptioned_low_fill_tables():
    """Tables with <15% fill and no caption are garbage — should be filtered."""
    for pdf_name in EXPECTED:
        ex = extract_document(FIXTURES / pdf_name)
        for table in ex.tables:
            if table.caption is None:
                total = table.num_rows * table.num_cols
                filled = sum(1 for r in table.rows for c in r if c.strip())
                fill_rate = filled / max(1, total)
                assert fill_rate >= 0.15, (
                    f"{pdf_name}: uncaptioned table {table.table_index} on p{table.page_num} "
                    f"has {fill_rate:.0%} fill — should have been filtered"
                )
```

---

## Fix 6d: Section-based table filtering

**Status**: Approved
**File**: `src/zotero_chunk_rag/pdf_processor.py`

### Implementation

**Step 1 — Change `_extract_tables_native` signature** (line 481):

From:
```python
def _extract_tables_native(doc: pymupdf.Document) -> list[ExtractedTable]:
```
To:
```python
def _extract_tables_native(
    doc: pymupdf.Document,
    sections: list[SectionSpan] | None = None,
    pages: list[PageExtraction] | None = None,
) -> list[ExtractedTable]:
```

**Step 2 — Add section skip** at the start of the page loop (line 492), after
`page_num = page_num_0 + 1`:

```python
        # Skip references/appendix sections (abbreviation lists, reference
        # lists get parsed as tables)
        if sections and pages:
            from ._figure_extraction import _is_in_references
            page_label = None
            for p in pages:
                if p.page_num == page_num:
                    from .section_classifier import assign_section
                    page_label = assign_section(p.char_start, sections)
                    break
            if page_label in ("references", "appendix"):
                continue
```

**Step 3 — Pass sections to the call site** in `extract_document()` (line 108):

Change:
```python
    tables = _extract_tables_native(doc)
```
To:
```python
    tables = _extract_tables_native(doc, sections=sections, pages=pages)
```

### Tests

**Existing tests should still pass** — `sections` defaults to `None` (no
filtering), so direct calls to `_extract_tables_native(doc)` in any other
test continue to work unchanged.

---

## Fix 6e: Header/footer filtering + dead parameter cleanup

**Status**: Approved
**File**: `src/zotero_chunk_rag/pdf_processor.py`, `src/zotero_chunk_rag/config.py`,
`src/zotero_chunk_rag/indexer.py`, `real_life_test.py`,
`tests/stress_test_real_library.py`

### Part 1: Header/footer filtering

In `extract_document()` (pdf_processor.py line 60-66), change the kwargs dict:

From:
```python
    kwargs: dict = dict(
        page_chunks=True,
        write_images=False,
        table_strategy=table_strategy,
        image_size_limit=image_size_limit,
        show_progress=False,
    )
```
To:
```python
    kwargs: dict = dict(
        page_chunks=True,
        write_images=False,
        header=False,
        footer=False,
        show_progress=False,
    )
```

### Part 2: Remove dead parameters from `extract_document` signature

In `pdf_processor.py` lines 48-56, change:
```python
def extract_document(
    pdf_path: Path | str,
    *,
    write_images: bool = False,
    images_dir: Path | str | None = None,
    table_strategy: str = "lines_strict",
    image_size_limit: float = 0.05,
    ocr_language: str = "eng",
) -> DocumentExtraction:
```
To:
```python
def extract_document(
    pdf_path: Path | str,
    *,
    write_images: bool = False,
    images_dir: Path | str | None = None,
    ocr_language: str = "eng",
) -> DocumentExtraction:
```

### Part 3: Remove dead parameters from callers

**`src/zotero_chunk_rag/indexer.py`** lines 293-299 — remove `table_strategy`
and `image_size_limit` from the `extract_document()` call:
```python
        extraction = extract_document(
            item.pdf_path,
            write_images=True,
            images_dir=figures_dir,
            ocr_language=self.config.ocr_language,
        )
```

**`src/zotero_chunk_rag/indexer.py`** line 25-33 — remove `table_strategy`
from the config hash:
```python
    data = (
        f"{config.chunk_size}:"
        f"{config.chunk_overlap}:"
        f"{config.embedding_provider}:"
        f"{config.embedding_dimensions}:"
        f"{config.embedding_model}:"
        f"{config.ocr_language}"
    )
```
(Note: removing `table_strategy` from the hash means existing indexes won't
match and will be re-indexed. This is intentional — the extraction output
changes with header/footer filtering.)

**`src/zotero_chunk_rag/config.py`** — remove these lines:
- Line 34: `table_strategy: str  # pymupdf4llm table detection strategy`
- Line 35: `image_size_limit: float  # minimum image size as page fraction`
- Line 75-76: `# Table extraction settings` comment
- Line 76: `table_strategy=data.get("table_strategy", "lines_strict"),`
- Line 77: `image_size_limit=data.get("image_size_limit", 0.05),`

**`real_life_test.py`** — remove from test config (line ~420-421) and from
`extract_document()` calls (line ~444-445). Search for `table_strategy` and
`image_size_limit` in the file and remove all occurrences.

**`tests/stress_test_real_library.py`** — same removals as `real_life_test.py`.

### Tests

Run the full test suite after changes:
```
pytest tests/ -v --ignore=tests/test_local_embeddings.py
```
(The `test_local_embeddings.py` test has a pre-existing failure using removed
`tables_enabled` kwarg — ignore it.)

---

## Fix 6b: Layout mode status — CORRECTED DIAGNOSIS (no code changes)

`import pymupdf.layout` has been in `pdf_processor.py` since its first commit.
Layout mode IS active and working. The previous session tested
`pymupdf._get_layout` in a bare Python shell (not through the library import
path) and incorrectly concluded layout was not activated.

Layout features we use vs ignore:

| Layout class | Used? | Notes |
|-------------|-------|-------|
| `section-header` | Yes | `_detect_sections()` |
| `picture` | Yes | `_figure_extraction.py` |
| `table` | Partially | Fallback for misclassified figures; `find_tables()` for data |
| `caption` | No | DIY regex is more complete (misses 30-60% of captions) |
| `page-header/footer` | Fixed by 6e | `header=False, footer=False` |

---

## Fix 2: Reference-anchored table/figure placement

**New file**: `src/zotero_chunk_rag/_reference_matcher.py`
**Modified files**: `src/zotero_chunk_rag/vector_store.py`,
`src/zotero_chunk_rag/indexer.py`

### What it does

Tables and figures currently stored with `chunk_index=-1`. This disconnects
them from the text that discusses them and causes `get_adjacent_chunks` to
leak all tables/figures when expanding context near chunk 0.

After this fix, each table/figure is stored at the `chunk_index` where it's
first referenced in body text.

### Implementation

**`_reference_matcher.py`** — new module:

```python
"""Map tables/figures to the chunks that first reference them."""
from __future__ import annotations
import re
from bisect import bisect_right
from .models import Chunk, ExtractedTable, ExtractedFigure


def match_references(
    full_markdown: str,
    chunks: list[Chunk],
    tables: list[ExtractedTable],
    figures: list[ExtractedFigure],
) -> dict[tuple[str, int], int]:
    """Map (element_type, caption_number) -> chunk_index of first reference.

    Scans full_markdown for patterns like "Table 1", "Fig. 3", "Figure 12".
    Parses caption numbers from ExtractedTable.caption and
    ExtractedFigure.caption. Returns mapping for matched items.

    Fallback for unreferenced items: page-based estimate — the chunk whose
    page_num matches the table/figure's page_num. If multiple, use the first.
    """


def get_reference_context(
    full_markdown: str,
    chunks: list[Chunk],
    ref_map: dict[tuple[str, int], int],
    element_type: str,
    caption_num: int,
) -> str | None:
    """Return the text of the chunk containing the first reference.

    Used by Fix 5 to enrich figure/table embeddings.
    """
```

Steps inside `match_references()`:
1. Parse caption numbers from `.caption` using `re.search(r"(\d+)")`.
2. Scan `full_markdown` for `(?:Table|Tab\.?)\s+(\d+)` and
   `(?:Figure|Fig\.?)\s+(\d+)`, case-insensitive. Record char offset of first
   match for each number.
3. Map char offset -> chunk_index using `bisect_right` on sorted
   `chunk.char_start` values.
4. Fallback for unmatched: find chunk where `chunk.page_num == item.page_num`.

**`vector_store.py` changes** — `add_tables()` and `add_figures()`:
- Add optional `ref_map: dict[tuple[str, int], int] | None = None` parameter
- Use `ref_map.get(("table", caption_num), -1)` for `chunk_index`

**`indexer.py` changes** — in `_index_single_document()`, after chunking:
- Call `match_references(extraction.full_markdown, chunks, extraction.tables, extraction.figures)`
- Pass `ref_map` to `store.add_tables()` and `store.add_figures()`

### Tests

New file `tests/test_reference_matcher.py`:
```python
def test_match_references_finds_table():
    """match_references maps Table 1 to the chunk containing 'Table 1'."""

def test_match_references_finds_figure():
    """match_references maps Figure 1 to the chunk containing 'Figure 1'."""

def test_fallback_uses_page_number():
    """Unreferenced items fall back to page-based chunk estimate."""
```

---

## Fix 5: Figure/table search enrichment

**Modified files**: `src/zotero_chunk_rag/models.py`,
`src/zotero_chunk_rag/vector_store.py`
**Depends on**: Fix 2 (reference matcher provides the context)

### Implementation

**`models.py`** — add field to `ExtractedFigure` (after line 72):
```python
    reference_context: str | None = None
```

Add field to `ExtractedTable` (after line 163):
```python
    reference_context: str | None = None
```

Update `ExtractedFigure.to_searchable_text()` (line 74-78):
```python
    def to_searchable_text(self) -> str:
        """Return text for embedding."""
        if self.caption:
            text = self.caption
        else:
            text = f"Figure on page {self.page_num}"
        if self.reference_context:
            text += f"\n{self.reference_context}"
        return text
```

**`vector_store.py`** — store `reference_context` in metadata in both
`add_figures()` and `add_tables()`.

**`indexer.py`** — after building ref map (Fix 2), call
`get_reference_context()` for each figure/table and populate
`item.reference_context` before passing to store.

### Tests

Add to existing test files — verify `to_searchable_text()` includes context:
```python
def test_figure_searchable_text_includes_context():
    fig = ExtractedFigure(1, 0, (0,0,1,1), "Figure 1.", reference_context="The plot shows...")
    assert "The plot shows" in fig.to_searchable_text()
```

---

## Fix 4: Section honesty + reranking guard

**Modified files**: `src/zotero_chunk_rag/reranker.py`, `README.md`

### Implementation

**`reranker.py`** — change `"unknown": 0.7` to `"unknown": 0.85` in
`DEFAULT_SECTION_WEIGHTS`. Add comment above explaining why.

**`real_life_test.py`** — update ground truth:
- `active-inference-tutorial`: remove `"methods"` from `expect_sections`
- `roland-emg-filter`: remove `"methods"` from `expect_sections`

**`README.md`** — add a "Limitations" section noting keyword-based section
detection and the unknown weight.

### Tests

Existing reranker tests should still pass. No new tests needed.

---

## Fix 3: Abstract detection (three-tier)

**Modified file**: `src/zotero_chunk_rag/pdf_processor.py`

### Implementation

Change `_detect_abstract` signature from:
```python
def _detect_abstract(first_page: PageExtraction, full_markdown: str) -> SectionSpan | None:
```
To:
```python
def _detect_abstract(
    pages: list[PageExtraction],
    full_markdown: str,
    doc: pymupdf.Document,
    sections: list[SectionSpan],
) -> SectionSpan | None:
```

Three-tier detection:
1. **Tier 2 (TOC)**: If any section already has `label == "abstract"`, return `None`.
2. **Tier 1 (keyword)**: Search pages 0-2 for "abstract" keyword (existing regex).
3. **Tier 3 (font)**: Compute body font from pages 3+. Scan pages 0-2 for
   differently-styled prose blocks. Exclude affiliations. Accept if exactly
   one qualifying block.

Update the call site in `extract_document()` (line 100-103):
```python
    if not has_abstract and pages:
        abstract_span = _detect_abstract(pages, full_markdown, doc, sections)
```

### Tests

Add `test_abstract_detected_on_page_2` and `test_abstract_detected_via_toc`
to `tests/test_section_quality.py`.

---

## Implementation Order

1. ~~Fix 1~~ — DONE
2. **Fix 6c** — Caption regex + multi-figure split + bbox clip
3. **Fix 6a** — Garbage table filter
4. **Fix 6d** — Section-based table filter
5. **Fix 6e** — Header/footer + dead param cleanup
6. **Fix 2** — Reference matcher
7. **Fix 5** — Search enrichment (depends on Fix 2)
8. **Fix 4** — Reranking guard + docs
9. **Fix 3** — Abstract detection

**After each fix**: run `pytest tests/ -v --ignore=tests/test_local_embeddings.py`
to verify no regressions.

**After all fixes**: run `real_life_test.py` to measure improvement on the
10-paper corpus.
