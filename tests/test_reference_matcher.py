"""Tests for reference matcher."""
from zotero_chunk_rag._reference_matcher import match_references, get_reference_context
from zotero_chunk_rag.models import Chunk, ExtractedTable, ExtractedFigure


def _make_chunks(texts_with_pages):
    """Helper to build chunks from (text, page_num) pairs."""
    chunks = []
    offset = 0
    for i, (text, page_num) in enumerate(texts_with_pages):
        chunks.append(Chunk(
            text=text,
            chunk_index=i,
            page_num=page_num,
            char_start=offset,
            char_end=offset + len(text),
        ))
        offset += len(text) + 1  # +1 for join newline
    return chunks, "\n".join(t for t, _ in texts_with_pages)


def test_match_references_finds_table():
    """match_references maps Table 1 to the chunk containing 'Table 1'."""
    chunks, full_md = _make_chunks([
        ("Introduction to the paper.", 1),
        ("As shown in Table 1, the results are significant.", 2),
        ("Conclusion of the paper.", 3),
    ])
    tables = [ExtractedTable(
        page_num=2, table_index=0, bbox=(0, 0, 1, 1),
        headers=["A"], rows=[["1"]], caption="Table 1. Results summary",
    )]
    ref_map = match_references(full_md, chunks, tables, [])
    assert ("table", 1) in ref_map
    assert ref_map[("table", 1)] == 1  # chunk_index 1 contains "Table 1"


def test_match_references_finds_figure():
    """match_references maps Figure 1 to the chunk containing 'Figure 1'."""
    chunks, full_md = _make_chunks([
        ("Introduction.", 1),
        ("Figure 1 shows the architecture.", 2),
        ("Methods section.", 3),
    ])
    figures = [ExtractedFigure(
        page_num=2, figure_index=0, bbox=(0, 0, 1, 1),
        caption="Figure 1. System architecture",
    )]
    ref_map = match_references(full_md, chunks, [], figures)
    assert ("figure", 1) in ref_map
    assert ref_map[("figure", 1)] == 1


def test_fallback_uses_page_number():
    """Unreferenced items fall back to page-based chunk estimate."""
    chunks, full_md = _make_chunks([
        ("Page one content.", 1),
        ("Page two content.", 2),
        ("Page three content.", 3),
    ])
    # Table on page 2, but no "Table 1" text anywhere in markdown
    tables = [ExtractedTable(
        page_num=2, table_index=0, bbox=(0, 0, 1, 1),
        headers=["A"], rows=[["1"]], caption="Table 1. Data",
    )]
    ref_map = match_references(full_md, chunks, tables, [])
    assert ("table", 1) in ref_map
    assert ref_map[("table", 1)] == 1  # chunk_index 1 is on page 2


def test_get_reference_context_returns_chunk_text():
    """get_reference_context returns the text of the referencing chunk."""
    chunks, full_md = _make_chunks([
        ("Introduction.", 1),
        ("As shown in Table 1, results are great.", 2),
    ])
    ref_map = {("table", 1): 1}
    ctx = get_reference_context(full_md, chunks, ref_map, "table", 1)
    assert ctx is not None
    assert "Table 1" in ctx


def test_empty_chunks_returns_empty_map():
    """Empty chunks list returns empty map."""
    ref_map = match_references("some text", [], [], [])
    assert ref_map == {}


def test_figure_searchable_text_includes_context():
    """to_searchable_text includes reference_context when set."""
    fig = ExtractedFigure(
        page_num=1, figure_index=0, bbox=(0, 0, 1, 1),
        caption="Figure 1. Architecture diagram",
        reference_context="The architecture shown in Figure 1 demonstrates the layered approach.",
    )
    text = fig.to_searchable_text()
    assert "Figure 1. Architecture diagram" in text
    assert "layered approach" in text


def test_figure_searchable_text_without_context():
    """to_searchable_text works normally without reference_context."""
    fig = ExtractedFigure(
        page_num=1, figure_index=0, bbox=(0, 0, 1, 1),
        caption="Figure 1. Architecture diagram",
    )
    text = fig.to_searchable_text()
    assert text == "Figure 1. Architecture diagram"


def test_table_has_reference_context_field():
    """ExtractedTable should have reference_context field."""
    table = ExtractedTable(
        page_num=1, table_index=0, bbox=(0, 0, 1, 1),
        headers=["A"], rows=[["1"]],
        caption="Table 1. Results",
        reference_context="Table 1 summarizes the key findings.",
    )
    assert table.reference_context == "Table 1 summarizes the key findings."
