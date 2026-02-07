# Implementation Plan: Figure Caption Recovery, Dead Code Removal, and Diagnostics

## Context

The previous implementation plan (use pymupdf4llm properly, remove DIY code) has been completed. The layout engine's `page_boxes` are now used for sections, tables, and figures. **224/226 tests pass.** However, a review of extraction quality on the three fixture papers reveals a major gap: **figure captions are missing on ~50% of figures** because the code only checks `caption`-class boxes and ignores captions that the layout engine misclassifies as `text`-class boxes.

### Diagnostic Evidence

**noname1.pdf** — 4 figures, 1 caption found (25%):
- Page 3: Figure 1 — `caption`-class box exists, caption extracted correctly
- Page 6: Figure 2 — NO `caption` box. But a `text`-class box at `bbox=(166,655,561,729)` starts with `**Figure 2.** Examples of ischemic regions...`
- Page 8: Figure 3 — NO `caption` box. But a `text`-class box at `bbox=(166,368,561,417)` starts with `**Figure 3.** Modeling of ectopic beats...`
- Page 10: Figure 4 — NO `caption` box. But a `text`-class box at `bbox=(167,359,560,407)` starts with `**Figure 4.** Examples of simulated AFlut...`

**noname2.pdf** — 3 figures, 3 captions found (100%):
- All three have `caption`-class boxes. Working correctly.
- Figure 3 (page 12): layout engine classifies as `table`-class box containing axis labels. No `Figure 3` caption text exists anywhere in the text layer. Genuinely unrecoverable.

**noname3.pdf** — 10 figures, 4 captions found (40%):
- Pages 2, 4, 10, 12: have `caption`-class boxes — captions extracted correctly
- Page 6: `text` box starts with `Fig. 3. The graphs show the afferent baroreceptor...`
- Page 7: `text` box starts with `Fig. 4. The graphs show afferent baroreflex...`
- Page 8: `text` box starts with `Fig. 5. Graphs of the parasympathetic...`
- Page 9: `text` box starts with `Fig. 6. Graphs of the T_p...`
- Page 11: `text` box starts with `Fig. 8. HR model predictions...`
- Page 14: picture box (118x187) sits in references section — publisher artefact, no caption exists

### Additional Issues Found

1. `_find_nearest_caption()` (lines 583-623) is dead code — defined but never called
2. No logging when figures have no caption (silent orphans)
3. `test_no_body_text_figure_captions` uses a flat 300-char threshold that rejects legitimate captions from `caption`-class boxes
4. noname3 page 14 "figure" is a publisher artefact in the references section

---

## Fix 1: Text-box Caption Fallback

**File:** `src/zotero_chunk_rag/pdf_processor.py`

Add a new function and integrate it as a fallback in `_extract_figures`.

### New constants and function (add before `_extract_figures`):

```python
# Regex matching figure caption leading words
_FIG_CAPTION_RE = re.compile(
    r"^(?:\*\*)?(?:Figure|Fig\.)\s+\d+",
    re.IGNORECASE,
)

_MAX_TEXT_BOX_CAPTION_LEN = 500  # Guard against body-text ingestion


def _caption_from_text_boxes(
    picture_box: dict,
    text_boxes: list[dict],
    page_text: str,
    max_distance: float = 80.0,
) -> str | None:
    """Find a caption in text-class boxes near a picture box.

    Scans text boxes that start with 'Figure N' / 'Fig. N' and are
    vertically adjacent (within max_distance points) to the picture.
    Prefers boxes below the picture, then above.
    """
    pic_bbox = picture_box.get("bbox", (0, 0, 0, 0))
    if not (isinstance(pic_bbox, (list, tuple)) and len(pic_bbox) == 4):
        return None

    candidates: list[tuple[float, str]] = []  # (distance, caption_text)

    for tbox in text_boxes:
        pos = tbox.get("pos")
        if not (pos and isinstance(pos, (list, tuple)) and len(pos) == 2):
            continue
        raw = page_text[pos[0]:pos[1]].strip()
        # Strip markdown bold markers for the regex check
        clean = raw.replace("**", "").replace("*", "").replace("_", "").strip()
        if not _FIG_CAPTION_RE.match(clean):
            continue
        if len(clean) > _MAX_TEXT_BOX_CAPTION_LEN:
            continue

        tb_bbox = tbox.get("bbox", (0, 0, 0, 0))
        if not (isinstance(tb_bbox, (list, tuple)) and len(tb_bbox) == 4):
            continue

        # Vertical distance: below picture or above picture
        dist_below = tb_bbox[1] - pic_bbox[3]   # positive = below
        dist_above = pic_bbox[1] - tb_bbox[3]    # positive = above

        if 0 <= dist_below <= max_distance:
            candidates.append((dist_below, clean))
        elif 0 <= dist_above <= max_distance:
            candidates.append((dist_above + max_distance, clean))  # Prefer below

    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]
```

### Modify `_extract_figures` to use the fallback:

In the existing per-page loop, after the `_assign_captions_to_elements` call, add a text-box scan:

```python
        # Fallback: scan text-class boxes for captions the layout engine missed
        text_boxes = [b for b in boxes if b.get("class") == "text"]

        for i, pbox in enumerate(valid_pboxes):
            bbox = pbox.get("bbox", (0, 0, 0, 0))
            caption = fig_captions.get(i)

            # If no caption from caption-class boxes, try text-class boxes
            if not caption:
                caption = _caption_from_text_boxes(pbox, text_boxes, text)
                if caption:
                    caption_source = "text_box"
                    logger.debug(
                        "Page %d: recovered figure caption from text box: %s",
                        page_num, caption[:60],
                    )
                else:
                    caption_source = ""
            else:
                caption_source = "caption_box"

            figures.append(ExtractedFigure(
                page_num=page_num,
                figure_index=fig_idx,
                bbox=tuple(bbox),
                caption=caption,
                image_path=None,
                caption_source=caption_source,
            ))
            fig_idx += 1
```

### Expected impact:
- noname1: 1/4 → 4/4 captions
- noname3: 4/10 → 9/10 captions (page 14 orphan stays — no caption text exists)

---

## Fix 2: Delete Dead `_find_nearest_caption`

**File:** `src/zotero_chunk_rag/pdf_processor.py`

Delete lines 583-623 entirely. The function `_find_nearest_caption` is defined but never called — it was replaced by `_assign_captions_to_elements` but never cleaned up.

---

## Fix 3: Add `caption_source` Field to `ExtractedFigure`

**File:** `src/zotero_chunk_rag/models.py`

Add a field to distinguish caption provenance:

```python
@dataclass
class ExtractedFigure:
    page_num: int
    figure_index: int
    bbox: tuple[float, float, float, float]
    caption: str | None
    image_path: Path | None = None
    caption_source: str = ""  # "caption_box" | "text_box" | "" (no caption)
```

---

## Fix 4: Log Orphan Figures

**File:** `src/zotero_chunk_rag/pdf_processor.py`

At the end of `_extract_figures`, after the per-page loop, before `return figures`:

```python
    orphans = [f for f in figures if not f.caption]
    if orphans:
        logger.info(
            "%d/%d figures have no caption: pages %s",
            len(orphans),
            len(figures),
            ", ".join(str(f.page_num) for f in orphans),
        )
```

---

## Fix 5: Filter References-Section Artefacts

**File:** `src/zotero_chunk_rag/pdf_processor.py`

The section data is already computed before figures in `extract_document` (line 89 vs 95). Pass `sections` and `pages` into `_extract_figures` and filter out pictures located in the `references` section.

### Update call site in `extract_document`:

```python
    figures = _extract_figures(page_chunks, figures_min_size, pages, sections)
```

### Update `_extract_figures` signature and add filter:

```python
def _extract_figures(
    page_chunks: list[dict],
    min_size: int = 100,
    pages: list[PageExtraction] | None = None,
    sections: list[SectionSpan] | None = None,
) -> list[ExtractedFigure]:
```

Inside the per-page loop, after building `valid_pboxes` and before assigning captions, filter out references-section pictures:

```python
        if sections and pages:
            page_obj = None
            for p in pages:
                if p.page_num == page_num:
                    page_obj = p
                    break
            if page_obj:
                filtered_pboxes = []
                for pbox in valid_pboxes:
                    pos = pbox.get("pos", [0, 0])
                    fig_char_start = page_obj.char_start + (pos[0] if isinstance(pos, (list, tuple)) and pos else 0)
                    section_label = assign_section(fig_char_start, sections)
                    if section_label == "references":
                        logger.debug("Page %d: skipping picture in references section", page_num)
                        continue
                    filtered_pboxes.append(pbox)
                valid_pboxes = filtered_pboxes
```

Add import at top of function body: `from .section_classifier import assign_section`

---

## Fix 6: Update Test Expectations

**File:** `tests/test_figure_quality.py`

### Update EXPECTED:

```python
EXPECTED = {
    "noname1.pdf": {
        "count": 4,
        "caption_prefixes": ["Figure 1.", "Figure 2.", "Figure 3.", "Figure 4."],
    },
    "noname2.pdf": {
        # Figure 3 (page 12): layout engine classifies as table-class box.
        # No "Figure 3" caption text exists in the text layer — unrecoverable.
        "count": 3,
        "caption_prefixes": ["Figure 1.", "Figure 2.", "Figure 4."],
    },
    "noname3.pdf": {
        # 9 figures after filtering page 14 publisher artefact from references section.
        "count": 9,
        "caption_prefixes": [
            "Fig. 1.", "Fig. 2.", "Fig. 3.", "Fig. 4.",
            "Fig. 5.", "Fig. 6.", "Fig. 7.", "Fig. 8.", "Fig. 9.",
        ],
    },
}
```

### Update `test_no_body_text_figure_captions`:

```python
def test_no_body_text_figure_captions():
    """Captions from text-box fallback must be <500 chars. Caption-box captions are trusted."""
    for pdf_name in EXPECTED:
        ex = extract_document(FIXTURES / pdf_name, write_images=False)
        for fig in ex.figures:
            if fig.caption and fig.caption_source == "text_box":
                assert len(fig.caption) < 500, (
                    f"{pdf_name}: figure {fig.figure_index} text-box caption is "
                    f"{len(fig.caption)} chars — likely body text: {fig.caption[:80]!r}..."
                )
```

---

## Summary of Changes

| File | Change | Lines |
|---|---|---|
| `pdf_processor.py` | Add `_FIG_CAPTION_RE`, `_MAX_TEXT_BOX_CAPTION_LEN`, `_caption_from_text_boxes()` | +35 |
| `pdf_processor.py` | Call fallback in `_extract_figures` loop, set `caption_source` | ~10 modified |
| `pdf_processor.py` | Add orphan logging at end of `_extract_figures` | +5 |
| `pdf_processor.py` | Delete `_find_nearest_caption` | -41 |
| `pdf_processor.py` | Pass `sections`/`pages` to `_extract_figures`, filter references-section pictures | +15 |
| `models.py` | Add `caption_source: str = ""` to `ExtractedFigure` | +1 |
| `test_figure_quality.py` | Update EXPECTED for all 3 papers, fix threshold test | ~20 modified |

**Net: ~55 new lines, 41 deleted, ~30 test lines updated.**

### Expected Test Outcome After Implementation

All 226 tests should pass (224 currently passing + 2 currently failing fixed).
