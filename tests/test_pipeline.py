"""Tests for the Pipeline class in zotero_chunk_rag.feature_extraction.pipeline."""

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
from zotero_chunk_rag.feature_extraction.pipeline import Pipeline


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ctx() -> TableContext:
    """Create a minimal TableContext with a mock page."""
    page = MagicMock()

    def get_text_side_effect(fmt: str, **kwargs):  # noqa: ANN001
        if fmt == "words":
            return []
        if fmt == "dict":
            return {"blocks": []}
        return ""

    page.get_text = MagicMock(side_effect=get_text_side_effect)
    page.get_drawings = MagicMock(return_value=[])
    rect = MagicMock()
    rect.height = 842.0
    rect.width = 595.0
    page.rect = rect
    return TableContext(
        page=page,
        page_num=3,
        bbox=(50.0, 100.0, 500.0, 400.0),
        pdf_path=Path("/tmp/test.pdf"),
    )


def _make_hypothesis(method: str = "mock_struct") -> BoundaryHypothesis:
    """Create a BoundaryHypothesis with col and row boundaries."""
    return BoundaryHypothesis(
        col_boundaries=(
            BoundaryPoint(100.0, 102.0, 0.9, method),
            BoundaryPoint(250.0, 252.0, 0.85, method),
        ),
        row_boundaries=(
            BoundaryPoint(150.0, 151.0, 0.8, method),
            BoundaryPoint(200.0, 201.0, 0.75, method),
        ),
        method=method,
        metadata={"source": "test"},
    )


def _make_grid(method: str = "mock_cell") -> CellGrid:
    """Create a CellGrid for testing."""
    return CellGrid(
        headers=("Col1", "Col2"),
        rows=(("a", "b"), ("c", "d")),
        col_boundaries=(101.0, 251.0),
        row_boundaries=(150.5, 200.5),
        method=method,
    )


def _make_structure_method(
    name: str,
    hypothesis: BoundaryHypothesis | None = None,
    raise_exc: Exception | None = None,
) -> MagicMock:
    """Create a mock structure method."""
    mock = MagicMock()
    mock.name = name
    if raise_exc is not None:
        mock.detect = MagicMock(side_effect=raise_exc)
    elif hypothesis is not None:
        mock.detect = MagicMock(return_value=hypothesis)
    else:
        mock.detect = MagicMock(return_value=None)
    return mock


def _make_cell_method(
    name: str,
    grid: CellGrid | None = None,
    raise_exc: Exception | None = None,
) -> MagicMock:
    """Create a mock cell extraction method."""
    mock = MagicMock()
    mock.name = name
    if raise_exc is not None:
        mock.extract = MagicMock(side_effect=raise_exc)
    elif grid is not None:
        mock.extract = MagicMock(return_value=grid)
    else:
        mock.extract = MagicMock(return_value=None)
    return mock


def _make_postprocessor(name: str, transform_fn=None) -> MagicMock:
    """Create a mock post-processor."""
    mock = MagicMock()
    mock.name = name
    if transform_fn is not None:
        mock.process = MagicMock(side_effect=transform_fn)
    else:
        mock.process = MagicMock(side_effect=lambda grid, ctx: grid)
    return mock


def _make_config(
    structure_methods=(),
    cell_methods=(),
    postprocessors=(),
    activation_rules=None,
) -> PipelineConfig:
    """Create a PipelineConfig with sensible defaults."""
    return PipelineConfig(
        structure_methods=tuple(structure_methods),
        cell_methods=tuple(cell_methods),
        postprocessors=tuple(postprocessors),
        activation_rules=activation_rules or {},
    )


# ---------------------------------------------------------------------------
# TestPipeline
# ---------------------------------------------------------------------------


class TestPipeline:
    def test_full_flow_mock(self) -> None:
        """Full flow: 2 structure methods (1 returns hypothesis, 1 None),
        1 cell method, 1 post-processor. Verify all result fields."""
        ctx = _make_ctx()
        hyp = _make_hypothesis("struct_a")
        grid = _make_grid("cell_a")

        struct_a = _make_structure_method("struct_a", hypothesis=hyp)
        struct_b = _make_structure_method("struct_b", hypothesis=None)
        cell_a = _make_cell_method("cell_a", grid=grid)
        pp = _make_postprocessor("clean_up")

        config = _make_config(
            structure_methods=[struct_a, struct_b],
            cell_methods=[cell_a],
            postprocessors=[pp],
        )
        pipeline = Pipeline(config)
        result = pipeline.extract(ctx)

        assert len(result.boundary_hypotheses) == 1
        assert result.boundary_hypotheses[0] is hyp
        struct_a.detect.assert_called_once_with(ctx)
        struct_b.detect.assert_called_once_with(ctx)

        assert len(result.cell_grids) >= 1
        assert result.winning_grid is not None
        assert result.post_processed is not None
        assert len(result.snapshots) == 1
        assert result.snapshots[0][0] == "clean_up"
        pp.process.assert_called_once()

    def test_method_crash_captured(self) -> None:
        """A structure method that raises ValueError is captured in method_errors.
        Other methods still run."""
        ctx = _make_ctx()
        hyp = _make_hypothesis("good_struct")

        crashing = _make_structure_method(
            "crash_struct", raise_exc=ValueError("bad data"),
        )
        good = _make_structure_method("good_struct", hypothesis=hyp)

        config = _make_config(structure_methods=[crashing, good])
        pipeline = Pipeline(config)
        result = pipeline.extract(ctx)

        assert len(result.method_errors) == 1
        assert result.method_errors[0][0] == "crash_struct"
        assert "bad data" in result.method_errors[0][1]

        good.detect.assert_called_once_with(ctx)
        assert len(result.boundary_hypotheses) == 1

    def test_activation_rules_skip(self) -> None:
        """When an activation rule returns False, the method's detect() is never called."""
        ctx = _make_ctx()
        method = _make_structure_method("skip_me", hypothesis=_make_hypothesis())

        config = _make_config(
            structure_methods=[method],
            activation_rules={"skip_me": lambda ctx: False},
        )
        pipeline = Pipeline(config)
        result = pipeline.extract(ctx)

        method.detect.assert_not_called()
        assert len(result.boundary_hypotheses) == 0

    def test_no_hypotheses_early_return(self) -> None:
        """All structure methods return None -> early return with empty result."""
        ctx = _make_ctx()
        method_a = _make_structure_method("a", hypothesis=None)
        method_b = _make_structure_method("b", hypothesis=None)

        config = _make_config(structure_methods=[method_a, method_b])
        pipeline = Pipeline(config)
        result = pipeline.extract(ctx)

        assert result.consensus_boundaries is None
        assert result.cell_grids == []
        assert result.post_processed is None
        assert result.winning_grid is None

    def test_timing_recorded(self) -> None:
        """Timing entries exist for each method that ran."""
        ctx = _make_ctx()
        hyp = _make_hypothesis("s1")
        grid = _make_grid("c1")

        struct = _make_structure_method("s1", hypothesis=hyp)
        cell = _make_cell_method("c1", grid=grid)
        pp = _make_postprocessor("pp1")

        config = _make_config(
            structure_methods=[struct],
            cell_methods=[cell],
            postprocessors=[pp],
        )
        pipeline = Pipeline(config)
        result = pipeline.extract(ctx)

        assert "structure:s1" in result.timing
        assert "cell:c1:s1" in result.timing
        assert "postprocess:pp1" in result.timing
        for key, val in result.timing.items():
            assert isinstance(val, float)
            assert val >= 0.0

    def test_grid_scores_populated(self) -> None:
        """grid_scores has entries keyed by structure:cell method."""
        ctx = _make_ctx()
        hyp = _make_hypothesis("s1")
        grid_a = _make_grid("cell_a")
        grid_b = _make_grid("cell_b")

        struct = _make_structure_method("s1", hypothesis=hyp)
        cell_a = _make_cell_method("cell_a", grid=grid_a)
        cell_b = _make_cell_method("cell_b", grid=grid_b)

        config = _make_config(
            structure_methods=[struct],
            cell_methods=[cell_a, cell_b],
        )
        pipeline = Pipeline(config)
        result = pipeline.extract(ctx)

        assert len(result.grid_scores) >= 1
        for v in result.grid_scores.values():
            assert isinstance(v, (int, float))

    def test_snapshot_ordering(self) -> None:
        """3 post-processors run in order; snapshots preserve order and names."""
        ctx = _make_ctx()
        hyp = _make_hypothesis("s1")
        grid = _make_grid("c1")

        struct = _make_structure_method("s1", hypothesis=hyp)
        cell = _make_cell_method("c1", grid=grid)

        grid_after_1 = CellGrid(
            headers=("A",), rows=(("step1",),),
            col_boundaries=(101.0,), row_boundaries=(150.5,),
            method="c1",
        )
        grid_after_2 = CellGrid(
            headers=("A",), rows=(("step2",),),
            col_boundaries=(101.0,), row_boundaries=(150.5,),
            method="c1",
        )
        grid_after_3 = CellGrid(
            headers=("A",), rows=(("step3",),),
            col_boundaries=(101.0,), row_boundaries=(150.5,),
            method="c1",
        )

        pp1 = _make_postprocessor("first", transform_fn=lambda g, c: grid_after_1)
        pp2 = _make_postprocessor("second", transform_fn=lambda g, c: grid_after_2)
        pp3 = _make_postprocessor("third", transform_fn=lambda g, c: grid_after_3)

        config = _make_config(
            structure_methods=[struct],
            cell_methods=[cell],
            postprocessors=[pp1, pp2, pp3],
        )
        pipeline = Pipeline(config)
        result = pipeline.extract(ctx)

        assert len(result.snapshots) == 3
        assert result.snapshots[0][0] == "first"
        assert result.snapshots[1][0] == "second"
        assert result.snapshots[2][0] == "third"

        assert result.snapshots[0][1] is grid_after_1
        assert result.snapshots[1][1] is grid_after_2
        assert result.snapshots[2][1] is grid_after_3

        assert result.post_processed is grid_after_3
