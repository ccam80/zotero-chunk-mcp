"""Core data models: BoundaryPoint, BoundaryHypothesis, CellGrid, TableContext, ExtractionResult, PipelineConfig, PageFeatures, CombinationTrace."""

from __future__ import annotations

import enum
import statistics
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    import pymupdf

    from .captions import DetectedCaption


# ---------------------------------------------------------------------------
# Frozen dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BoundaryPoint:
    """A boundary as a range. For exact boundaries (ruled lines), min_pos == max_pos.

    For gap-based boundaries, min_pos = left edge of gap, max_pos = right edge.
    """

    min_pos: float
    max_pos: float
    confidence: float
    provenance: str

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable dict."""
        return {
            "min_pos": self.min_pos,
            "max_pos": self.max_pos,
            "confidence": self.confidence,
            "provenance": self.provenance,
        }


@dataclass(frozen=True)
class BoundaryHypothesis:
    """One per structure method per table.

    Either axis can be empty tuple if the method doesn't detect it.
    metadata holds method-specific debug info.
    """

    col_boundaries: tuple[BoundaryPoint, ...]
    row_boundaries: tuple[BoundaryPoint, ...]
    method: str
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable dict."""
        return {
            "col_boundaries": [bp.to_dict() for bp in self.col_boundaries],
            "row_boundaries": [bp.to_dict() for bp in self.row_boundaries],
            "method": self.method,
            "metadata": self.metadata,
        }


@dataclass
class PointExpansion:
    """Record of a single boundary point's expansion during combination."""

    original: BoundaryPoint
    expanded_min: float
    expanded_max: float
    was_expanded: bool


@dataclass
class ClusterRecord:
    """Record of a merged cluster of boundary points."""

    points: list[BoundaryPoint]
    total_confidence: float
    distinct_methods: int
    weighted_position: float
    accepted: bool
    acceptance_threshold: float


@dataclass
class AxisTrace:
    """Full trace of _combine_axis() for one axis (cols or rows)."""

    input_points: list[BoundaryPoint]
    expansions: list[PointExpansion]
    clusters: list[ClusterRecord]
    median_confidence: float
    acceptance_threshold: float
    accepted_positions: list[float]


@dataclass
class CombinationTrace:
    """Diagnostic trace from combine_hypotheses() when trace=True."""

    col_trace: AxisTrace
    row_trace: AxisTrace
    spatial_precision: float
    source_methods: list[str]


@dataclass(frozen=True)
class CellGrid:
    """Immutable cell content with the boundary positions that produced it.

    Post-processors return new CellGrid instances. Quality scores are comparative
    (rank-based) and stored externally in ExtractionResult.grid_scores, not on
    the grid itself.
    """

    headers: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    col_boundaries: tuple[float, ...]
    row_boundaries: tuple[float, ...]
    method: str
    structure_method: str = "consensus"

    def with_structure_method(self, name: str) -> CellGrid:
        """Return a copy with ``structure_method`` replaced."""
        return CellGrid(
            headers=self.headers,
            rows=self.rows,
            col_boundaries=self.col_boundaries,
            row_boundaries=self.row_boundaries,
            method=self.method,
            structure_method=name,
        )

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable dict."""
        return {
            "headers": list(self.headers),
            "rows": [list(row) for row in self.rows],
            "col_boundaries": list(self.col_boundaries),
            "row_boundaries": list(self.row_boundaries),
            "method": self.method,
            "structure_method": self.structure_method,
        }


# ---------------------------------------------------------------------------
# TableContext — mutable class with cached_property fields
# ---------------------------------------------------------------------------

class TableContext:
    """Lazily-computed context about a single table region on a PDF page.

    Not a dataclass: uses cached_property for lazy computation.
    """

    def __init__(
        self,
        page: pymupdf.Page,
        page_num: int,
        bbox: tuple[float, float, float, float],
        pdf_path: Path,
        caption: DetectedCaption | None = None,
    ) -> None:
        self.page = page
        self.page_num = page_num
        self.bbox = bbox
        self.pdf_path = pdf_path
        self.caption = caption

    @cached_property
    def words(self) -> list[tuple]:
        """Words within the table bbox, from page.get_text('words', clip=bbox)."""
        return self.page.get_text("words", clip=self.bbox)

    @cached_property
    def drawings(self) -> list[dict]:
        """Drawing objects filtered to those intersecting the table bbox."""
        x0, y0, x1, y1 = self.bbox
        result = []
        for d in self.page.get_drawings():
            drect = d.get("rect")
            if drect is None:
                continue
            dx0, dy0, dx1, dy1 = drect
            if dx1 >= x0 and dx0 <= x1 and dy1 >= y0 and dy0 <= y1:
                result.append(d)
        return result

    @cached_property
    def dict_blocks(self) -> list[dict]:
        """Text blocks from page.get_text('dict', clip=bbox)['blocks']."""
        return self.page.get_text("dict", clip=self.bbox)["blocks"]

    @cached_property
    def page_height(self) -> float:
        """Page height from page.rect.height."""
        return self.page.rect.height

    @cached_property
    def page_width(self) -> float:
        """Page width from page.rect.width."""
        return self.page.rect.width

    @cached_property
    def median_word_height(self) -> float:
        """Median height of words in the table bbox.

        Returns 0.0 if no words are present.
        """
        heights = [w[3] - w[1] for w in self.words if len(w) >= 4]
        if not heights:
            return 0.0
        return statistics.median(heights)

    @cached_property
    def median_word_gap(self) -> float:
        """Median horizontal gap between consecutive words in the same row cluster.

        Words are grouped into rows by y-position (tolerance = median_word_height * 0.3).
        Within each row, words are sorted by x0 and the gap between consecutive
        word x0 and prior word x1 is measured.

        Returns 0.0 if fewer than 2 words or no measurable gaps.
        """
        if len(self.words) < 2:
            return 0.0

        word_height = self.median_word_height
        if word_height == 0.0:
            return 0.0

        tolerance = word_height * 0.3

        # Cluster words into rows by y-midpoint
        sorted_words = sorted(self.words, key=lambda w: (w[1] + w[3]) / 2)
        rows: list[list[tuple]] = []
        current_row: list[tuple] = [sorted_words[0]]
        current_y = (sorted_words[0][1] + sorted_words[0][3]) / 2

        for w in sorted_words[1:]:
            y_mid = (w[1] + w[3]) / 2
            if abs(y_mid - current_y) <= tolerance:
                current_row.append(w)
            else:
                rows.append(current_row)
                current_row = [w]
                current_y = y_mid
        rows.append(current_row)

        # Measure gaps within each row
        gaps: list[float] = []
        for row in rows:
            row_sorted = sorted(row, key=lambda w: w[0])
            for i in range(1, len(row_sorted)):
                gap = row_sorted[i][0] - row_sorted[i - 1][2]
                if gap > 0:
                    gaps.append(gap)

        if not gaps:
            return 0.0
        return statistics.median(gaps)

    @cached_property
    def median_ruled_line_thickness(self) -> float | None:
        """Median thickness of vertical/horizontal ruled lines from drawings.

        Returns None if no ruled lines are found.
        """
        thicknesses: list[float] = []
        for d in self.drawings:
            width = d.get("width") or 0
            if width > 0:
                thicknesses.append(width)
        if not thicknesses:
            return None
        return statistics.median(thicknesses)

    @cached_property
    def word_rows(self) -> list[list[tuple]]:
        """Words clustered into rows using adaptive tolerance.

        Each row is a list of word tuples sorted by x-position (left to right).
        Rows sorted by y-position (top to bottom).
        """
        from .methods._row_clustering import cluster_words_into_rows

        return cluster_words_into_rows(self.words)

    @cached_property
    def data_word_rows(self) -> list[list[tuple]]:
        """Word rows excluding any row overlapping the caption bbox.

        If no caption is set, returns word_rows unchanged. Otherwise,
        filters out rows whose y-center falls within the caption's
        bbox y-range.
        """
        if self.caption is None:
            return self.word_rows

        cap_y0 = self.caption.bbox[1]
        cap_y1 = self.caption.bbox[3]

        result = []
        for row in self.word_rows:
            # Compute row y-center from average of word y-midpoints
            y_mids = [(w[1] + w[3]) / 2 for w in row]
            row_y_center = sum(y_mids) / len(y_mids) if y_mids else 0.0
            if cap_y0 <= row_y_center <= cap_y1:
                continue  # skip rows overlapping caption
            result.append(row)
        return result


# ---------------------------------------------------------------------------
# ExtractionResult — mutable accumulator
# ---------------------------------------------------------------------------

@dataclass
class ExtractionResult:
    """Mutable accumulator for extraction pipeline results."""

    table_id: str
    bbox: tuple[float, float, float, float]
    boundary_hypotheses: list[BoundaryHypothesis] = field(default_factory=list)
    consensus_boundaries: BoundaryHypothesis | None = None
    cell_grids: list[CellGrid] = field(default_factory=list)
    grid_scores: dict[str, float] = field(default_factory=dict)
    winning_grid: CellGrid | None = None
    post_processed: CellGrid | None = None
    snapshots: list[tuple[str, CellGrid]] = field(default_factory=list)
    method_errors: list[tuple[str, str]] = field(default_factory=list)
    timing: dict[str, float] = field(default_factory=dict)
    caption: str | None = None
    footnotes: str = ""


# ---------------------------------------------------------------------------
# FeatureType, DetectedFeature, PageFeatures — page-level detection models
# ---------------------------------------------------------------------------


class FeatureType(enum.Enum):
    """Type of detected feature on a page."""

    TABLE = "table"
    FIGURE = "figure"


@dataclass(frozen=True)
class DetectedFeature:
    """A feature (table or figure) detected on a PDF page before extraction."""

    bbox: tuple[float, float, float, float]
    feature_type: FeatureType
    page_num: int
    caption: str | None
    confidence: float


@dataclass(frozen=True)
class PageFeatures:
    """All features extracted from a single page."""

    tables: list[ExtractionResult]
    figures: list[dict]


# ---------------------------------------------------------------------------
# PipelineConfig — frozen dataclass
# ---------------------------------------------------------------------------

# Forward-reference protocol types via TYPE_CHECKING to avoid circular imports.
# At runtime these are just stored as-is; the protocol check is structural.
if TYPE_CHECKING:
    from .protocols import CellExtractionMethod, PostProcessor, StructureMethod


@dataclass(frozen=True)
class PipelineConfig:
    """Immutable pipeline configuration.

    structure_methods, cell_methods, postprocessors: tuples of protocol-conforming objects.
    activation_rules: maps method name to predicate. Methods not in the dict are
    always activated. Methods whose predicate returns False are skipped.
    """

    structure_methods: tuple[StructureMethod, ...]
    cell_methods: tuple[CellExtractionMethod, ...]
    postprocessors: tuple[PostProcessor, ...]
    activation_rules: dict[str, Callable[[TableContext], bool]]
    combination_strategy: str
    selection_strategy: str
    confidence_multipliers: dict[str, float] = field(default_factory=dict)

    def with_overrides(self, **kwargs: Any) -> PipelineConfig:
        """Return a new PipelineConfig with specified fields replaced."""
        current = {
            "structure_methods": self.structure_methods,
            "cell_methods": self.cell_methods,
            "postprocessors": self.postprocessors,
            "activation_rules": self.activation_rules,
            "combination_strategy": self.combination_strategy,
            "selection_strategy": self.selection_strategy,
            "confidence_multipliers": self.confidence_multipliers,
        }
        current.update(kwargs)
        return PipelineConfig(**current)

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable dict.

        Methods and activation rules are represented by their names/keys
        since callables and protocol objects are not JSON-serializable.
        """
        return {
            "structure_methods": [m.name for m in self.structure_methods],
            "cell_methods": [m.name for m in self.cell_methods],
            "postprocessors": [p.name for p in self.postprocessors],
            "activation_rules": list(self.activation_rules.keys()),
            "combination_strategy": self.combination_strategy,
            "selection_strategy": self.selection_strategy,
            "confidence_multipliers": dict(self.confidence_multipliers),
        }
