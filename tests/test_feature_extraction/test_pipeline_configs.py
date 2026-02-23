"""Tests for named pipeline configurations (DEFAULT_CONFIG, FAST_CONFIG, etc.)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from zotero_chunk_rag.feature_extraction.models import (
    BoundaryHypothesis,
    BoundaryPoint,
    CellGrid,
    PipelineConfig,
    TableContext,
)
from zotero_chunk_rag.feature_extraction.pipeline import (
    DEFAULT_CONFIG,
    FAST_CONFIG,
    MINIMAL_CONFIG,
    Pipeline,
    RULED_CONFIG,
)
from zotero_chunk_rag.feature_extraction.postprocessors.absorbed_caption import (
    AbsorbedCaptionStrip,
)
from zotero_chunk_rag.feature_extraction.postprocessors.cell_cleaning import (
    CellCleaning,
)


class TestConfigs:
    """Verify named pipeline configurations have the correct contents."""

    def test_default_config_complete(self):
        assert len(DEFAULT_CONFIG.structure_methods) == 13
        assert len(DEFAULT_CONFIG.cell_methods) == 3
        assert len(DEFAULT_CONFIG.postprocessors) == 7

    def test_fast_config_subset(self):
        assert len(FAST_CONFIG.structure_methods) == 2
        assert len(FAST_CONFIG.cell_methods) == 2

    def test_ruled_config_weights(self):
        assert RULED_CONFIG.confidence_multipliers["ruled_lines"] == 3.0

    def test_minimal_config_baseline(self):
        assert len(MINIMAL_CONFIG.structure_methods) == 1
        assert len(MINIMAL_CONFIG.cell_methods) == 1

    def test_all_configs_valid(self):
        for config in (DEFAULT_CONFIG, FAST_CONFIG, RULED_CONFIG, MINIMAL_CONFIG):
            assert isinstance(config, PipelineConfig)
            assert len(config.structure_methods) > 0
            assert len(config.cell_methods) > 0
            assert len(config.postprocessors) > 0

    def test_postprocessor_ordering(self):
        pp = DEFAULT_CONFIG.postprocessors
        assert isinstance(pp[0], AbsorbedCaptionStrip)
        assert isinstance(pp[-1], CellCleaning)


def _make_mock_ctx() -> TableContext:
    """Build a minimal mocked TableContext for testing."""
    mock_page = MagicMock()
    mock_page.get_text.return_value = []
    mock_page.get_drawings.return_value = []
    mock_page.rect = MagicMock()
    mock_page.rect.height = 800.0
    mock_page.rect.width = 600.0
    ctx = TableContext(
        page=mock_page,
        page_num=1,
        bbox=(50.0, 50.0, 550.0, 750.0),
        pdf_path=Path("test.pdf"),
    )
    return ctx


class _FakeStructureMethod:
    """Fake structure method that returns fixed boundaries."""

    def __init__(self, method_name: str, col_points: tuple[BoundaryPoint, ...], row_points: tuple[BoundaryPoint, ...]):
        self._name = method_name
        self._cols = col_points
        self._rows = row_points

    @property
    def name(self) -> str:
        return self._name

    def detect(self, ctx: TableContext) -> BoundaryHypothesis | None:
        return BoundaryHypothesis(
            col_boundaries=self._cols,
            row_boundaries=self._rows,
            method=self._name,
            metadata={},
        )


class _FakeCellMethod:
    """Fake cell extraction method that returns a grid based on boundary count."""

    def __init__(self, method_name: str):
        self._name = method_name

    @property
    def name(self) -> str:
        return self._name

    def extract(self, ctx: TableContext, col_boundaries: tuple[float, ...], row_boundaries: tuple[float, ...]) -> CellGrid | None:
        n_cols = len(col_boundaries) + 1
        n_rows = len(row_boundaries) + 1
        headers = tuple(f"H{i}" for i in range(n_cols))
        rows = tuple(
            tuple(f"R{r}C{c}" for c in range(n_cols))
            for r in range(n_rows)
        )
        return CellGrid(
            headers=headers,
            rows=rows,
            col_boundaries=col_boundaries,
            row_boundaries=row_boundaries,
            method=self._name,
        )


class TestMultiMethodExtraction:
    """Tests for Pipeline.extract() producing grids from multiple structure methods."""

    def test_extract_produces_multi_method_grids(self):
        """Two structure methods x two cell methods + consensus = 6 grids."""
        bp_col = BoundaryPoint(min_pos=100.0, max_pos=100.0, confidence=0.9, provenance="test")
        bp_row = BoundaryPoint(min_pos=200.0, max_pos=200.0, confidence=0.9, provenance="test")

        struct_a = _FakeStructureMethod("struct_a", (bp_col,), (bp_row,))
        struct_b = _FakeStructureMethod("struct_b", (bp_col,), (bp_row,))
        cell_x = _FakeCellMethod("cell_x")
        cell_y = _FakeCellMethod("cell_y")

        config = PipelineConfig(
            structure_methods=(struct_a, struct_b),
            cell_methods=(cell_x, cell_y),
            postprocessors=(),
            activation_rules={},
            combination_strategy="expand_overlap",
            selection_strategy="rank_based",
        )

        pipeline = Pipeline(config)
        ctx = _make_mock_ctx()
        result = pipeline.extract(ctx)

        # 2 struct × 2 cell + 1 consensus × 2 cell = 6 grids
        assert len(result.cell_grids) == 6

        # Verify structure_method provenance
        struct_methods = {g.structure_method for g in result.cell_grids}
        assert "struct_a" in struct_methods
        assert "struct_b" in struct_methods
        assert "consensus" in struct_methods

        # Verify cell methods per structure method
        struct_a_cells = {g.method for g in result.cell_grids if g.structure_method == "struct_a"}
        assert struct_a_cells == {"cell_x", "cell_y"}

    def test_extract_no_detection_returns_empty(self):
        """Structure method returning None produces no grids."""

        class _NoneStructure:
            @property
            def name(self) -> str:
                return "none_method"

            def detect(self, ctx: TableContext) -> BoundaryHypothesis | None:
                return None

        config = PipelineConfig(
            structure_methods=(_NoneStructure(),),
            cell_methods=(_FakeCellMethod("cell_x"),),
            postprocessors=(),
            activation_rules={},
            combination_strategy="expand_overlap",
            selection_strategy="rank_based",
        )

        pipeline = Pipeline(config)
        ctx = _make_mock_ctx()
        result = pipeline.extract(ctx)

        assert len(result.cell_grids) == 0
        assert result.winning_grid is None

    def test_extract_crash_recovery(self):
        """Crashing structure method is skipped; good method still produces grids."""

        class _CrashStructure:
            @property
            def name(self) -> str:
                return "crash_method"

            def detect(self, ctx: TableContext) -> BoundaryHypothesis | None:
                raise RuntimeError("boom")

        bp_col = BoundaryPoint(min_pos=100.0, max_pos=100.0, confidence=0.9, provenance="test")
        bp_row = BoundaryPoint(min_pos=200.0, max_pos=200.0, confidence=0.9, provenance="test")
        good_struct = _FakeStructureMethod("good_method", (bp_col,), (bp_row,))

        config = PipelineConfig(
            structure_methods=(_CrashStructure(), good_struct),
            cell_methods=(_FakeCellMethod("cell_x"),),
            postprocessors=(),
            activation_rules={},
            combination_strategy="expand_overlap",
            selection_strategy="rank_based",
        )

        pipeline = Pipeline(config)
        ctx = _make_mock_ctx()
        result = pipeline.extract(ctx)

        # good_method(1 grid) + consensus(1 grid) = 2
        assert len(result.cell_grids) >= 1
        assert any(g.structure_method == "good_method" for g in result.cell_grids)
        assert len(result.method_errors) == 1
