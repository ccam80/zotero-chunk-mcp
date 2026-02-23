"""Figure extraction quality tests against real papers."""
from pathlib import Path

import pymupdf.layout  # noqa: F401
import pymupdf4llm
import pymupdf

FIXTURES = Path(__file__).parent / "fixtures" / "papers"

# EXACT expected figure counts and caption prefixes.
# These are not minimums — the extraction must find exactly this many.
EXPECTED = {
    "noname1.pdf": {
        "count": 4,
        "caption_prefixes": ["Figure 1.", "Figure 2.", "Figure 3.", "Figure 4."],
    },
    "noname2.pdf": {
        "count": 4,
        "caption_prefixes": ["Figure 1.", "Figure 2.", "Figure 3.", "Figure 4."],
    },
    "noname3.pdf": {
        "count": 9,
        "caption_prefixes": [
            "Fig. 1.", "Fig. 2.", "Fig. 3.", "Fig. 4.",
            "Fig. 5.", "Fig. 6.", "Fig. 7.", "Fig. 8.", "Fig. 9.",
        ],
    },
}


# --- Count tests (exact) ---

def test_noname1_figure_count(extracted_papers):
    figures = extracted_papers["noname1.pdf"].figures
    assert len(figures) == EXPECTED["noname1.pdf"]["count"], (
        f"Expected {EXPECTED['noname1.pdf']['count']} figures, got {len(figures)}. "
        f"Pages: {[f.page_num for f in figures]}"
    )


def test_noname2_figure_count(extracted_papers):
    figures = extracted_papers["noname2.pdf"].figures
    assert len(figures) == EXPECTED["noname2.pdf"]["count"], (
        f"Expected {EXPECTED['noname2.pdf']['count']} figures, got {len(figures)}. "
        f"Pages: {[f.page_num for f in figures]}"
    )


def test_noname3_figure_count(extracted_papers):
    figures = extracted_papers["noname3.pdf"].figures
    assert len(figures) == EXPECTED["noname3.pdf"]["count"], (
        f"Expected {EXPECTED['noname3.pdf']['count']} figures, got {len(figures)}. "
        f"Pages: {[f.page_num for f in figures]}"
    )


# --- Caption tests (1:1 match) ---

def test_noname1_figure_captions(extracted_papers):
    figures = extracted_papers["noname1.pdf"].figures
    _assert_caption_prefixes(figures, EXPECTED["noname1.pdf"]["caption_prefixes"], "noname1")


def test_noname2_figure_captions(extracted_papers):
    figures = extracted_papers["noname2.pdf"].figures
    _assert_caption_prefixes(figures, EXPECTED["noname2.pdf"]["caption_prefixes"], "noname2")


def test_noname3_figure_captions(extracted_papers):
    figures = extracted_papers["noname3.pdf"].figures
    _assert_caption_prefixes(figures, EXPECTED["noname3.pdf"]["caption_prefixes"], "noname3")


def _assert_caption_prefixes(figures, expected_prefixes, paper_name):
    """Each expected prefix must match exactly one figure's caption."""
    captions = [f.caption or "" for f in figures]
    for prefix in expected_prefixes:
        matches = [c for c in captions if c.startswith(prefix)]
        assert len(matches) >= 1, (
            f"{paper_name}: no figure caption starts with {prefix!r}. "
            f"Actual captions: {captions}"
        )


# --- Quality guards ---

def test_no_body_text_figure_captions(extracted_papers):
    """No figure caption should be >2000 chars (would be body text, not a caption)."""
    for pdf_name in EXPECTED:
        figures = extracted_papers[pdf_name].figures
        for fig in figures:
            if fig.caption:
                assert len(fig.caption) < 2000, (
                    f"{pdf_name}: figure {fig.figure_index} caption is "
                    f"{len(fig.caption)} chars — likely body text: "
                    f"{fig.caption[:80]!r}..."
                )


def test_no_body_text_as_figure_caption(extracted_papers):
    """Figure captions must start with 'Figure N.' or 'Fig. N.', never
    body text like 'Figure 9 shows...'."""
    import re
    body_text_re = re.compile(
        r"^(?:Figure|Fig\.?)\s+\d+\s+(?:show|depict|illustrat|present|display)",
        re.IGNORECASE,
    )
    for pdf_name in EXPECTED:
        figures = extracted_papers[pdf_name].figures
        for fig in figures:
            if fig.caption:
                assert not body_text_re.match(fig.caption), (
                    f"{pdf_name}: fig {fig.figure_index} caption is body text: "
                    f"{fig.caption[:80]!r}"
                )


def test_image_extraction_writes_files(tmp_path):
    """When write_images=True, figures must have real PNG files on disk."""
    from zotero_chunk_rag.pdf_processor import extract_document

    pdf_path = FIXTURES / "noname1.pdf"
    result = extract_document(
        pdf_path,
        write_images=True,
        images_dir=tmp_path / "images",
    )

    figures_with_images = [f for f in result.figures if f.image_path is not None]
    assert len(figures_with_images) >= 1, (
        f"No figures have image_path set. Total figures: {len(result.figures)}"
    )
    for fig in figures_with_images:
        assert fig.image_path.exists(), (
            f"Figure {fig.figure_index} image_path does not exist: {fig.image_path}"
        )
        assert fig.image_path.stat().st_size > 500, (
            f"Figure {fig.figure_index} image file is suspiciously small: "
            f"{fig.image_path.stat().st_size} bytes"
        )


def test_noname2_vector_figures_captured(extracted_papers):
    """noname2 has figures made of narrow raster sub-images.
    The extraction must capture them even though individual sub-images
    are smaller than 100px in one dimension."""
    figures = extracted_papers["noname2.pdf"].figures
    figure_pages = {f.page_num for f in figures}
    # Figures are on pages 9, 11, 12, 13
    for expected_page in [9, 11, 12, 13]:
        assert expected_page in figure_pages, (
            f"noname2: no figure found on page {expected_page}. "
            f"Found on pages: {sorted(figure_pages)}"
        )
