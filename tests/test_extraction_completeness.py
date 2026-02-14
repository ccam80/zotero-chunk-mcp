"""Extraction completeness tests — verify nothing is missed."""


def test_noname1_no_missing_figures(extracted_papers):
    ex = extracted_papers["noname1.pdf"]
    assert ex.completeness is not None
    assert ex.completeness.figures_missing == 0, (
        f"noname1: {ex.completeness.figures_missing} figures missing. "
        f"Found {ex.completeness.figures_found}, "
        f"caption blocks found {ex.completeness.figure_captions_found}"
    )


def test_noname2_no_missing_figures(extracted_papers):
    ex = extracted_papers["noname2.pdf"]
    assert ex.completeness is not None
    assert ex.completeness.figures_missing == 0, (
        f"noname2: {ex.completeness.figures_missing} figures missing. "
        f"Found {ex.completeness.figures_found}, "
        f"caption blocks found {ex.completeness.figure_captions_found}"
    )


def test_noname3_no_missing_figures(extracted_papers):
    ex = extracted_papers["noname3.pdf"]
    assert ex.completeness is not None
    assert ex.completeness.figures_missing == 0, (
        f"noname3: {ex.completeness.figures_missing} figures missing. "
        f"Found {ex.completeness.figures_found}, "
        f"caption blocks found {ex.completeness.figure_captions_found}"
    )


def test_noname1_no_missing_tables(extracted_papers):
    assert extracted_papers["noname1.pdf"].completeness.tables_missing == 0


def test_noname2_no_missing_tables(extracted_papers):
    assert extracted_papers["noname2.pdf"].completeness.tables_missing == 0


def test_noname3_no_missing_tables(extracted_papers):
    assert extracted_papers["noname3.pdf"].completeness.tables_missing == 0


def test_noname1_has_sections(extracted_papers):
    ex = extracted_papers["noname1.pdf"]
    assert ex.completeness.sections_identified > 0, (
        "noname1.pdf: no sections identified at all"
    )


def test_noname2_has_sections(extracted_papers):
    ex = extracted_papers["noname2.pdf"]
    assert ex.completeness.sections_identified > 0, (
        "noname2.pdf: no sections identified at all"
    )


def test_noname3_has_sections(extracted_papers):
    ex = extracted_papers["noname3.pdf"]
    assert ex.completeness.sections_identified > 0, (
        "noname3.pdf: no sections identified at all"
    )


def test_noname1_grade(extracted_papers):
    """noname1 should achieve grade A or B (complete extraction)."""
    ex = extracted_papers["noname1.pdf"]
    assert ex.completeness.grade in ("A", "B"), (
        f"noname1.pdf: grade {ex.completeness.grade}. "
        f"Completeness: figures_missing={ex.completeness.figures_missing}, "
        f"tables_missing={ex.completeness.tables_missing}, "
        f"unknown_sections={ex.completeness.unknown_sections}"
    )


def test_noname2_grade(extracted_papers):
    """noname2 should achieve grade A or B (complete extraction)."""
    ex = extracted_papers["noname2.pdf"]
    assert ex.completeness.grade in ("A", "B"), (
        f"noname2.pdf: grade {ex.completeness.grade}. "
        f"Completeness: figures_missing={ex.completeness.figures_missing}, "
        f"tables_missing={ex.completeness.tables_missing}, "
        f"unknown_sections={ex.completeness.unknown_sections}"
    )


def test_noname3_grade(extracted_papers):
    """noname3 should achieve grade A or B (complete extraction)."""
    ex = extracted_papers["noname3.pdf"]
    assert ex.completeness.grade in ("A", "B"), (
        f"noname3.pdf: grade {ex.completeness.grade}. "
        f"Completeness: figures_missing={ex.completeness.figures_missing}, "
        f"tables_missing={ex.completeness.tables_missing}, "
        f"unknown_sections={ex.completeness.unknown_sections}"
    )


# --- Quality signal fields exist and have sane defaults ---


def test_quality_fields_exist(extracted_papers):
    """New quality signal fields must exist on ExtractionCompleteness."""
    for pdf_name in ("noname1.pdf", "noname2.pdf", "noname3.pdf"):
        comp = extracted_papers[pdf_name].completeness
        assert hasattr(comp, "garbled_table_cells")
        assert hasattr(comp, "interleaved_table_cells")
        assert hasattr(comp, "encoding_artifact_captions")
        assert hasattr(comp, "tables_1x1")
        assert hasattr(comp, "duplicate_captions")
        assert hasattr(comp, "figure_number_gaps")
        assert hasattr(comp, "table_number_gaps")


def test_noname_papers_no_duplicate_captions(extracted_papers):
    """Fixture papers should have no duplicate captions."""
    for pdf_name in ("noname1.pdf", "noname2.pdf", "noname3.pdf"):
        comp = extracted_papers[pdf_name].completeness
        assert comp.duplicate_captions == 0, (
            f"{pdf_name}: {comp.duplicate_captions} duplicate captions"
        )


def test_noname_papers_no_figure_gaps(extracted_papers):
    """Fixture papers should have no gaps in figure numbering."""
    for pdf_name in ("noname1.pdf", "noname2.pdf", "noname3.pdf"):
        comp = extracted_papers[pdf_name].completeness
        assert comp.figure_number_gaps == [], (
            f"{pdf_name}: figure number gaps: {comp.figure_number_gaps}"
        )


def test_noname_papers_no_table_gaps(extracted_papers):
    """Fixture papers should have no gaps in table numbering."""
    for pdf_name in ("noname1.pdf", "noname2.pdf", "noname3.pdf"):
        comp = extracted_papers[pdf_name].completeness
        assert comp.table_number_gaps == [], (
            f"{pdf_name}: table number gaps: {comp.table_number_gaps}"
        )


def test_noname_papers_no_1x1_tables(extracted_papers):
    """Fixture papers should have no degenerate 1x1 tables."""
    for pdf_name in ("noname1.pdf", "noname2.pdf", "noname3.pdf"):
        comp = extracted_papers[pdf_name].completeness
        assert comp.tables_1x1 == 0, (
            f"{pdf_name}: {comp.tables_1x1} degenerate 1x1 tables"
        )
