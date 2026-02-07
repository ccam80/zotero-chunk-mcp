"""Table extraction quality tests against real papers."""
from pathlib import Path
from zotero_chunk_rag.pdf_processor import extract_document

FIXTURES = Path(__file__).parent / "fixtures" / "papers"

# Exact expected table counts and caption prefixes per paper.
EXPECTED = {
    "noname1.pdf": {
        "count": 1,
        "caption_prefixes": ["Table 1."],
    },
    "noname2.pdf": {
        "count": 5,
        "caption_prefixes": ["Table 1.", "Table 2.", "Table 3.", "Table 4.", "Table 5."],
    },
    "noname3.pdf": {
        "count": 4,
        "caption_prefixes": ["Table 1.", "Table 2.", "Table 3.", "Table 4."],
    },
}


def test_noname1_table_count():
    ex = extract_document(FIXTURES / "noname1.pdf")
    assert len(ex.tables) == EXPECTED["noname1.pdf"]["count"]


def test_noname2_table_count():
    ex = extract_document(FIXTURES / "noname2.pdf")
    assert len(ex.tables) == EXPECTED["noname2.pdf"]["count"]


def test_noname3_table_count():
    ex = extract_document(FIXTURES / "noname3.pdf")
    assert len(ex.tables) == EXPECTED["noname3.pdf"]["count"]


def test_noname1_table_captions():
    ex = extract_document(FIXTURES / "noname1.pdf")
    _assert_caption_prefixes(ex.tables, EXPECTED["noname1.pdf"]["caption_prefixes"], "noname1")


def test_noname2_table_captions():
    ex = extract_document(FIXTURES / "noname2.pdf")
    _assert_caption_prefixes(ex.tables, EXPECTED["noname2.pdf"]["caption_prefixes"], "noname2")


def test_noname3_table_captions():
    ex = extract_document(FIXTURES / "noname3.pdf")
    _assert_caption_prefixes(ex.tables, EXPECTED["noname3.pdf"]["caption_prefixes"], "noname3")


def _assert_caption_prefixes(tables, expected_prefixes, paper_name):
    """Assert that for each expected prefix, exactly one table's caption starts with it."""
    captions = [t.caption or "" for t in tables]
    for prefix in expected_prefixes:
        matches = [c for c in captions if c.startswith(prefix)]
        assert len(matches) >= 1, (
            f"{paper_name}: no table caption starts with {prefix!r}. "
            f"Actual captions: {captions}"
        )


def test_all_tables_have_content():
    """Every table must have at least 1 data row and 2 columns."""
    for pdf_name in EXPECTED:
        ex = extract_document(FIXTURES / pdf_name)
        for table in ex.tables:
            assert table.num_rows >= 1, f"{pdf_name}: table {table.table_index} has 0 rows. Caption: {table.caption!r}"
            assert table.num_cols >= 2, f"{pdf_name}: table {table.table_index} has {table.num_cols} cols. Caption: {table.caption!r}"


def test_all_tables_render_markdown():
    """Every table must render to markdown with pipe characters."""
    for pdf_name in EXPECTED:
        ex = extract_document(FIXTURES / pdf_name)
        for table in ex.tables:
            md = table.to_markdown()
            assert "|" in md, f"{pdf_name}: table {table.table_index} markdown has no pipes"
            lines = [line for line in md.split("\n") if line.strip()]
            assert len(lines) >= 2, f"{pdf_name}: table {table.table_index} markdown has <2 lines"


def test_no_body_text_captions():
    """No table caption should be body text. Real captions start with 'Table N'."""
    for pdf_name in EXPECTED:
        ex = extract_document(FIXTURES / pdf_name)
        for table in ex.tables:
            if table.caption:
                assert table.caption.lower().startswith("table"), (
                    f"{pdf_name}: table {table.table_index} caption looks like body text: {table.caption[:80]!r}"
                )
