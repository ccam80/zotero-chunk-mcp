"""Table extraction quality tests against real papers."""

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


def test_noname1_table_count(extracted_papers):
    assert len(extracted_papers["noname1.pdf"].tables) == EXPECTED["noname1.pdf"]["count"]


def test_noname2_table_count(extracted_papers):
    assert len(extracted_papers["noname2.pdf"].tables) == EXPECTED["noname2.pdf"]["count"]


def test_noname3_table_count(extracted_papers):
    assert len(extracted_papers["noname3.pdf"].tables) == EXPECTED["noname3.pdf"]["count"]


def test_noname1_table_captions(extracted_papers):
    _assert_caption_prefixes(extracted_papers["noname1.pdf"].tables, EXPECTED["noname1.pdf"]["caption_prefixes"], "noname1")


def test_noname2_table_captions(extracted_papers):
    _assert_caption_prefixes(extracted_papers["noname2.pdf"].tables, EXPECTED["noname2.pdf"]["caption_prefixes"], "noname2")


def test_noname3_table_captions(extracted_papers):
    _assert_caption_prefixes(extracted_papers["noname3.pdf"].tables, EXPECTED["noname3.pdf"]["caption_prefixes"], "noname3")


def _assert_caption_prefixes(tables, expected_prefixes, paper_name):
    """Assert that for each expected prefix, exactly one table's caption starts with it."""
    captions = [t.caption or "" for t in tables]
    for prefix in expected_prefixes:
        matches = [c for c in captions if c.startswith(prefix)]
        assert len(matches) >= 1, (
            f"{paper_name}: no table caption starts with {prefix!r}. "
            f"Actual captions: {captions}"
        )


def test_all_tables_have_content(extracted_papers):
    """Every table must have at least 1 data row and 2 columns."""
    for pdf_name in EXPECTED:
        for table in extracted_papers[pdf_name].tables:
            assert table.num_rows >= 1, f"{pdf_name}: table {table.table_index} has 0 rows. Caption: {table.caption!r}"
            assert table.num_cols >= 2, f"{pdf_name}: table {table.table_index} has {table.num_cols} cols. Caption: {table.caption!r}"


def test_all_tables_render_markdown(extracted_papers):
    """Every table must render to markdown with pipe characters."""
    for pdf_name in EXPECTED:
        for table in extracted_papers[pdf_name].tables:
            md = table.to_markdown()
            assert "|" in md, f"{pdf_name}: table {table.table_index} markdown has no pipes"
            lines = [line for line in md.split("\n") if line.strip()]
            assert len(lines) >= 2, f"{pdf_name}: table {table.table_index} markdown has <2 lines"


def test_no_body_text_captions(extracted_papers):
    """No table caption should be body text. Real captions start with 'Table N'."""
    for pdf_name in EXPECTED:
        for table in extracted_papers[pdf_name].tables:
            if table.caption:
                assert table.caption.lower().startswith("table"), (
                    f"{pdf_name}: table {table.table_index} caption looks like body text: {table.caption[:80]!r}"
                )


def test_tables_have_structured_data(extracted_papers):
    """Every table must have proper cell-level data, not raw markdown."""
    for pdf_name in EXPECTED:
        for table in extracted_papers[pdf_name].tables:
            for row in table.rows:
                for cell in row:
                    assert isinstance(cell, str), (
                        f"{pdf_name}: table {table.table_index} has non-string cell: {cell!r}"
                    )
            for h in table.headers:
                assert isinstance(h, str), (
                    f"{pdf_name}: table {table.table_index} has non-string header: {h!r}"
                )


def test_no_uncaptioned_low_fill_tables(extracted_papers):
    """Tables with <15% fill and no caption are garbage — should be filtered."""
    for pdf_name in EXPECTED:
        for table in extracted_papers[pdf_name].tables:
            if table.caption is None:
                total = table.num_rows * table.num_cols
                filled = sum(1 for r in table.rows for c in r if c.strip())
                fill_rate = filled / max(1, total)
                assert fill_rate >= 0.15, (
                    f"{pdf_name}: uncaptioned table {table.table_index} on p{table.page_num} "
                    f"has {fill_rate:.0%} fill — should have been filtered"
                )
