"""Integration tests for the pipeline wired into pdf_processor.extract_document().

Tests verify that extract_document() uses the new feature_extraction pipeline
for both table and figure extraction, while retaining all cross-page
coordination (gap fill, heading/continuation captions, artifact tagging,
completeness grading, synthetic captions).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from zotero_chunk_rag.feature_extraction.models import CellGrid, ExtractionResult, TableContext
from zotero_chunk_rag.feature_extraction.pipeline import FAST_CONFIG, Pipeline
from zotero_chunk_rag.pdf_processor import (
    _apply_prose_postprocessors,
    _result_to_extracted_table,
    extract_document,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "papers"
NONAME1 = FIXTURES_DIR / "noname1.pdf"
NONAME2 = FIXTURES_DIR / "noname2.pdf"


class TestIntegration:
    """End-to-end integration tests using fixture PDFs."""

    def test_extract_document_returns_tables(self) -> None:
        """extract_document() on noname1 should find at least 1 table."""
        result = extract_document(NONAME1)
        assert len(result.tables) >= 1, (
            f"Expected at least 1 table, got {len(result.tables)}"
        )

    def test_extract_document_returns_figures(self) -> None:
        """extract_document() on noname1 should find at least 1 figure."""
        result = extract_document(NONAME1)
        assert len(result.figures) >= 1, (
            f"Expected at least 1 figure, got {len(result.figures)}"
        )

    def test_result_to_extracted_table(self) -> None:
        """_result_to_extracted_table converts ExtractionResult to ExtractedTable."""
        grid = CellGrid(
            headers=("Col A", "Col B", "Col C"),
            rows=(
                ("1", "2", "3"),
                ("4", "5", "6"),
            ),
            col_boundaries=(100.0, 200.0),
            row_boundaries=(50.0,),
            method="test_method",
        )
        result = ExtractionResult(
            table_id="p1_t0",
            bbox=(10.0, 20.0, 300.0, 400.0),
        )
        result.post_processed = grid
        result.caption = "Table 1. Test table"
        result.footnotes = "Note: test footnote"

        et = _result_to_extracted_table(result, page_num=1, table_index=0)
        assert et is not None
        assert et.headers == ["Col A", "Col B", "Col C"]
        assert et.rows == [["1", "2", "3"], ["4", "5", "6"]]
        assert et.bbox == (10.0, 20.0, 300.0, 400.0)
        assert et.page_num == 1
        assert et.table_index == 0
        assert et.caption == "Table 1. Test table"
        assert et.footnotes == "Note: test footnote"
        assert et.extraction_strategy == "test_method"
        assert et.artifact_type is None

    def test_result_to_extracted_table_artifact(self) -> None:
        """_result_to_extracted_table detects artifact from table_id."""
        grid = CellGrid(
            headers=("A",),
            rows=(("1",),),
            col_boundaries=(),
            row_boundaries=(),
            method="m",
        )
        result = ExtractionResult(
            table_id="p1_t0_artifact",
            bbox=(0.0, 0.0, 100.0, 100.0),
        )
        result.post_processed = grid
        et = _result_to_extracted_table(result, page_num=1, table_index=0)
        assert et is not None
        assert et.artifact_type == "figure_data_table"

    def test_result_to_extracted_table_none_grid(self) -> None:
        """_result_to_extracted_table returns None when no grid."""
        result = ExtractionResult(
            table_id="p1_t0",
            bbox=(0.0, 0.0, 100.0, 100.0),
        )
        et = _result_to_extracted_table(result, page_num=1, table_index=0)
        assert et is None

    def test_result_to_extracted_table_empty_grid(self) -> None:
        """_result_to_extracted_table returns None for empty grid."""
        grid = CellGrid(
            headers=(),
            rows=(),
            col_boundaries=(),
            row_boundaries=(),
            method="m",
        )
        result = ExtractionResult(
            table_id="p1_t0",
            bbox=(0.0, 0.0, 100.0, 100.0),
        )
        result.post_processed = grid
        et = _result_to_extracted_table(result, page_num=1, table_index=0)
        assert et is None

    def test_synthetic_captions_assigned(self) -> None:
        """Orphan tables/figures get synthetic captions after grading."""
        result = extract_document(NONAME1)
        for t in result.tables:
            assert t.caption is not None and t.caption != "", (
                f"Table on page {t.page_num} has no caption"
            )
        for f in result.figures:
            assert f.caption is not None and f.caption != "", (
                f"Figure on page {f.page_num} has no caption"
            )

    def test_completeness_grades(self) -> None:
        """extract_document() computes a completeness grade."""
        result = extract_document(NONAME1)
        assert result.quality_grade is not None
        assert result.completeness is not None
        assert result.completeness.text_pages > 0

    def test_document_extraction_interface(self) -> None:
        """extract_document() returns the standard DocumentExtraction interface."""
        result = extract_document(NONAME1)
        assert hasattr(result, "pages")
        assert hasattr(result, "full_markdown")
        assert hasattr(result, "sections")
        assert hasattr(result, "tables")
        assert hasattr(result, "figures")
        assert hasattr(result, "stats")
        assert hasattr(result, "quality_grade")
        assert hasattr(result, "completeness")
        assert len(result.pages) > 0
        assert len(result.full_markdown) > 0


class TestProseTable:
    """Tests for prose table extraction with shared post-processors."""

    def test_prose_tables_extracted(self) -> None:
        """Extract a paper and verify prose table detection still works.

        noname1 has 1 table. All tables should have non-empty content
        (headers or rows) after extraction.
        """
        result = extract_document(NONAME1)
        for t in result.tables:
            assert t.num_rows > 0 or len(t.headers) > 0, (
                f"Table on page {t.page_num} has no content"
            )

    def test_prose_table_cell_cleaning(self) -> None:
        """Verify that prose table cells have ligatures normalized and
        leading zeros recovered via the shared CellCleaning post-processor.
        """
        import pymupdf

        doc = pymupdf.open(str(NONAME1))
        page = doc[0]

        # Test with synthetic rows containing ligatures and leading-dot numerics
        rows = [
            ["E\ufb03ciency", "0.5"],
            [".047", "e\ufb00ect"],
        ]
        bbox = (0.0, 0.0, page.rect.width, page.rect.height)

        _, _, cleaned_rows = _apply_prose_postprocessors(
            page, bbox, [], rows,
        )
        doc.close()

        # Ligatures should be normalized
        assert "ffi" in cleaned_rows[0][0], (
            f"Expected ligature normalization, got {cleaned_rows[0][0]!r}"
        )
        assert "ff" in cleaned_rows[1][1], (
            f"Expected ligature normalization, got {cleaned_rows[1][1]!r}"
        )
        # Leading zeros should be recovered
        assert cleaned_rows[1][0] == "0.047", (
            f"Expected leading zero recovery, got {cleaned_rows[1][0]!r}"
        )


class TestCleanup:
    """Tests verifying old extraction code has been removed."""

    def test_old_functions_removed(self) -> None:
        """Functions replaced by the pipeline are no longer accessible."""
        import zotero_chunk_rag.pdf_processor as pp

        dead_functions = [
            "_extract_tables_native",
            "_extract_cell_text_multi_strategy",
            "_extract_via_rawdict",
            "_extract_via_words",
            "_repair_low_fill_table",
            "_merge_over_divided_rows",
            "_repair_garbled_cells",
            "_score_extraction",
            "_count_decimal_displacement",
            "_count_numeric_integrity",
            "_compute_fill_rate",
            "_strip_footnote_rows",
            "_split_at_internal_captions",
            "_separate_header_data",
            "_strip_absorbed_caption",
            "_strip_known_caption_from_table",
            "_word_based_column_detection",
            "_remove_empty_columns",
            "_should_replace_with_word_api",
            "_clean_cell_text",
            "_looks_numeric",
            "_is_layout_artifact",
        ]
        for name in dead_functions:
            assert not hasattr(pp, name), (
                f"Dead function {name} still accessible on pdf_processor module"
            )

    def test_figure_module_removed(self) -> None:
        """The old _figure_extraction module is no longer importable."""
        import importlib
        import sys

        # Ensure clean state (remove cached module if any)
        mod_name = "zotero_chunk_rag._figure_extraction"
        sys.modules.pop(mod_name, None)

        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(mod_name)

    def test_extract_document_still_works(self) -> None:
        """extract_document() still returns a valid DocumentExtraction."""
        result = extract_document(NONAME1)
        assert result is not None
        assert hasattr(result, "pages")
        assert hasattr(result, "full_markdown")
        assert hasattr(result, "tables")
        assert hasattr(result, "figures")
        assert hasattr(result, "quality_grade")
        assert len(result.pages) > 0
        assert len(result.full_markdown) > 0


@pytest.fixture(scope="module")
def _pipeline_result():
    """Run FAST_CONFIG pipeline on noname1.pdf's single table."""
    import pymupdf

    doc = pymupdf.open(str(NONAME1))
    try:
        for pi in range(len(doc)):
            page = doc[pi]
            tabs = page.find_tables(strategy="text")
            if tabs.tables:
                tab = tabs.tables[0]
                ctx = TableContext(
                    page=page,
                    page_num=pi + 1,
                    bbox=tab.bbox,
                    pdf_path=NONAME1,
                )
                pipeline = Pipeline(FAST_CONFIG)
                result = pipeline.extract(ctx)
                assert result.cell_grids, (
                    f"Pipeline produced no grids for noname1.pdf page {pi + 1}"
                )
                return result
    finally:
        doc.close()

    pytest.fail("No tables found in noname1.pdf")


class TestCellGridProvenance:
    """Tests for the CellGrid.structure_method field."""

    def test_structure_method_field_exists(self) -> None:
        """CellGrid has a structure_method attribute of type str."""
        grid = CellGrid(
            headers=("A",), rows=(("1",),),
            col_boundaries=(0.0,), row_boundaries=(0.0,),
            method="test",
        )
        assert isinstance(grid.structure_method, str)

    def test_default_structure_method_is_consensus(self) -> None:
        """CellGrid constructed without explicit structure_method defaults to 'consensus'."""
        grid = CellGrid(
            headers=("A",), rows=(("1",),),
            col_boundaries=(0.0,), row_boundaries=(0.0,),
            method="test",
        )
        assert grid.structure_method == "consensus"

    def test_with_structure_method_returns_copy(self) -> None:
        """with_structure_method() returns a new CellGrid with only structure_method changed."""
        grid = CellGrid(
            headers=("A", "B"), rows=(("1", "2"),),
            col_boundaries=(10.0,), row_boundaries=(20.0,),
            method="rawdict",
        )
        copy = grid.with_structure_method("hotspot")
        assert copy.structure_method == "hotspot"
        assert copy.method == "rawdict"
        assert copy.headers == grid.headers
        assert copy.rows == grid.rows
        assert copy is not grid

    def test_to_dict_includes_structure_method(self) -> None:
        """to_dict() output includes the structure_method key."""
        grid = CellGrid(
            headers=("A",), rows=(("1",),),
            col_boundaries=(0.0,), row_boundaries=(0.0,),
            method="test", structure_method="ruled_lines",
        )
        d = grid.to_dict()
        assert "structure_method" in d
        assert d["structure_method"] == "ruled_lines"


class TestExtractAllGrids:
    """Tests for restructured Pipeline.extract() producing multi-method grids."""

    def test_cell_grids_from_multiple_structure_methods(self, _pipeline_result) -> None:
        """result.cell_grids has more grids than just consensus would produce."""
        result = _pipeline_result
        # FAST_CONFIG has 2 cell methods; consensus alone would produce 2 grids
        assert len(result.cell_grids) > len(FAST_CONFIG.cell_methods)

    def test_grids_have_distinct_structure_methods(self, _pipeline_result) -> None:
        """Grids come from at least 2 distinct structure methods."""
        result = _pipeline_result
        struct_methods = {g.structure_method for g in result.cell_grids}
        assert len(struct_methods) >= 2

    def test_consensus_grids_present(self, _pipeline_result) -> None:
        """At least one grid has structure_method == 'consensus'."""
        result = _pipeline_result
        assert any(g.structure_method == "consensus" for g in result.cell_grids)

    def test_scores_dict_uses_composite_keys(self, _pipeline_result) -> None:
        """All keys in grid_scores contain a colon separator."""
        result = _pipeline_result
        for key in result.grid_scores:
            assert ":" in key, f"Expected composite key, got {key!r}"

    def test_winning_grid_has_provenance(self, _pipeline_result) -> None:
        """Winning grid has a non-empty structure_method."""
        result = _pipeline_result
        assert result.winning_grid is not None, "No winning grid selected"
        assert isinstance(result.winning_grid.structure_method, str)
        assert result.winning_grid.structure_method.strip(), (
            f"Winning grid has blank structure_method: "
            f"{result.winning_grid.structure_method!r}"
        )


class TestExtractWithAllBoundariesRemoved:
    """Verify extract_with_all_boundaries() has been removed."""

    def test_no_extract_with_all_boundaries(self) -> None:
        """Pipeline has no extract_with_all_boundaries attribute."""
        pipeline = Pipeline(FAST_CONFIG)
        assert not hasattr(pipeline, "extract_with_all_boundaries")


class TestDocs:
    """Tests verifying documentation is up to date."""

    def test_claude_md_no_table_extraction_refs(self) -> None:
        """CLAUDE.md should not reference old table_extraction package name."""
        claude_md = Path(__file__).resolve().parent.parent.parent / "CLAUDE.md"
        content = claude_md.read_text(encoding="utf-8")
        matches = [
            line for line in content.splitlines()
            if "table_extraction" in line
        ]
        assert len(matches) == 0, (
            f"Found {len(matches)} references to table_extraction in CLAUDE.md: "
            + "; ".join(matches[:3])
        )

    def test_claude_md_no_figure_extraction_ref(self) -> None:
        """CLAUDE.md should not reference deleted _figure_extraction module."""
        claude_md = Path(__file__).resolve().parent.parent.parent / "CLAUDE.md"
        content = claude_md.read_text(encoding="utf-8")
        matches = [
            line for line in content.splitlines()
            if "_figure_extraction" in line
        ]
        assert len(matches) == 0, (
            f"Found {len(matches)} references to _figure_extraction in CLAUDE.md: "
            + "; ".join(matches[:3])
        )
