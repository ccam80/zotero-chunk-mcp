"""Figure extraction quality tests against real papers."""
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures" / "papers"

EXPECTED = {
    "noname1.pdf": {
        "min_figures": 4,
        "caption_prefixes": ["Figure 1.", "Figure 2.", "Figure 3.", "Figure 4."],
    },
    "noname2.pdf": {
        "min_figures": 4,
        "caption_prefixes": ["Figure 1.","Figure 2.","Figure 3.","Figure 4."],
    },
    "noname3.pdf": {
        # 10+ raster images on pages 2,4,6,7,8,9,10,11,12,14.
        # Page 14 is references-section artefact (filtered when sections passed).
        # Without sections, all 10+ detected.
        "min_figures": 9,
        "caption_prefixes": [
            "Fig. 1.", "Fig. 2.", "Fig. 3.", "Fig. 4.",
            "Fig. 5.", "Fig. 6.", "Fig. 7.", "Fig. 8.", "Fig. 9.",
        ],
    },
}


def _get_figures(pdf_name):
    """Extract figures using the new native extraction."""
    import pymupdf
    from zotero_chunk_rag._figure_extraction import _extract_figures_native

    doc = pymupdf.open(str(FIXTURES / pdf_name))
    figures = _extract_figures_native(doc, min_size=100, write_images=False)
    doc.close()
    return figures


def test_noname1_figure_count():
    figures = _get_figures("noname1.pdf")
    assert len(figures) >= EXPECTED["noname1.pdf"]["min_figures"], (
        f"Expected >= {EXPECTED['noname1.pdf']['min_figures']} figures, "
        f"got {len(figures)}"
    )


def test_noname2_figure_count():
    figures = _get_figures("noname2.pdf")
    assert len(figures) >= EXPECTED["noname2.pdf"]["min_figures"], (
        f"Expected >= {EXPECTED['noname2.pdf']['min_figures']} figures, "
        f"got {len(figures)}"
    )


def test_noname3_figure_count():
    figures = _get_figures("noname3.pdf")
    assert len(figures) >= EXPECTED["noname3.pdf"]["min_figures"], (
        f"Expected >= {EXPECTED['noname3.pdf']['min_figures']} figures, "
        f"got {len(figures)}"
    )


def test_noname1_figure_captions():
    figures = _get_figures("noname1.pdf")
    _assert_caption_prefixes(
        figures,
        EXPECTED["noname1.pdf"]["caption_prefixes"],
        "noname1"
    )


def test_noname2_figure_captions():
    figures = _get_figures("noname2.pdf")
    _assert_caption_prefixes(
        figures,
        EXPECTED["noname2.pdf"]["caption_prefixes"],
        "noname2"
    )


def test_noname3_figure_captions():
    figures = _get_figures("noname3.pdf")
    _assert_caption_prefixes(
        figures,
        EXPECTED["noname3.pdf"]["caption_prefixes"],
        "noname3"
    )


def _assert_caption_prefixes(figures, expected_prefixes, paper_name):
    """Assert that for each expected prefix, at least one figure's caption starts with it."""
    captions = [f.caption or "" for f in figures]
    for prefix in expected_prefixes:
        matches = [c for c in captions if c.startswith(prefix)]
        assert len(matches) >= 1, (
            f"{paper_name}: no figure caption starts with {prefix!r}. "
            f"Actual captions: {captions}"
        )


def test_no_body_text_figure_captions():
    """No figure caption should be >2000 chars. Academic captions can be long but not THIS long."""
    for pdf_name in EXPECTED:
        figures = _get_figures(pdf_name)
        for fig in figures:
            if fig.caption:
                assert len(fig.caption) < 2000, (
                    f"{pdf_name}: figure {fig.figure_index} caption is "
                    f"{len(fig.caption)} chars — likely body text: "
                    f"{fig.caption[:80]!r}..."
                )


def test_image_extraction_writes_files(tmp_path):
    """When write_images=True, figures with xref>0 must have real files."""
    import pymupdf
    from zotero_chunk_rag._figure_extraction import _extract_figures_native

    doc = pymupdf.open(str(FIXTURES / "noname1.pdf"))
    figures = _extract_figures_native(
        doc,
        min_size=100,
        write_images=True,
        images_dir=tmp_path / "images",
    )
    doc.close()

    figures_with_images = [f for f in figures if f.image_path is not None]
    assert len(figures_with_images) >= 1, (
        f"No figures have image_path set. Total figures: {len(figures)}"
    )
    for fig in figures_with_images:
        assert fig.image_path.exists(), (
            f"Figure {fig.figure_index} image_path does not exist: {fig.image_path}"
        )
        assert fig.image_path.stat().st_size > 100, (
            f"Figure {fig.figure_index} image file is suspiciously small: "
            f"{fig.image_path.stat().st_size} bytes"
        )
