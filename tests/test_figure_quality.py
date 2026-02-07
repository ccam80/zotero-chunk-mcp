"""Figure extraction quality tests against real papers."""
from pathlib import Path
from zotero_chunk_rag.pdf_processor import extract_document

FIXTURES = Path(__file__).parent / "fixtures" / "papers"

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


def test_noname1_figure_count():
    ex = extract_document(FIXTURES / "noname1.pdf", write_images=False)
    assert len(ex.figures) == EXPECTED["noname1.pdf"]["count"]


def test_noname2_figure_count():
    ex = extract_document(FIXTURES / "noname2.pdf", write_images=False)
    assert len(ex.figures) == EXPECTED["noname2.pdf"]["count"]


def test_noname3_figure_count():
    ex = extract_document(FIXTURES / "noname3.pdf", write_images=False)
    assert len(ex.figures) == EXPECTED["noname3.pdf"]["count"]


def test_noname1_figure_captions():
    ex = extract_document(FIXTURES / "noname1.pdf", write_images=False)
    _assert_caption_prefixes(ex.figures, EXPECTED["noname1.pdf"]["caption_prefixes"], "noname1")


def test_noname2_figure_captions():
    ex = extract_document(FIXTURES / "noname2.pdf", write_images=False)
    _assert_caption_prefixes(ex.figures, EXPECTED["noname2.pdf"]["caption_prefixes"], "noname2")


def test_noname3_figure_captions():
    ex = extract_document(FIXTURES / "noname3.pdf", write_images=False)
    _assert_caption_prefixes(ex.figures, EXPECTED["noname3.pdf"]["caption_prefixes"], "noname3")


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
    """Captions from text-box fallback must be <800 chars. Caption-box captions are trusted."""
    for pdf_name in EXPECTED:
        ex = extract_document(FIXTURES / pdf_name, write_images=False)
        for fig in ex.figures:
            if fig.caption and fig.caption_source == "text_box":
                assert len(fig.caption) < 800, (
                    f"{pdf_name}: figure {fig.figure_index} text-box caption is "
                    f"{len(fig.caption)} chars — likely body text: {fig.caption[:80]!r}..."
                )
