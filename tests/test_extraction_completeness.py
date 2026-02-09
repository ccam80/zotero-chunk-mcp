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
