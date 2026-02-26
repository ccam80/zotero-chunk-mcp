"""Pipeline class -- runs structure methods, extracts cells, selects best grid, post-processes.

Orchestrates the extraction flow:
1. Activate methods (check activation rules)
2. Run structure detection (produce BoundaryHypotheses)
3. Run cell extraction per hypothesis (produce CellGrids)
4. Select best grid by fill rate (with decimal displacement sanity check)
5. Run post-processors in order

Also defines named pipeline configurations (DEFAULT_CONFIG, FAST_CONFIG, etc.).
"""

from __future__ import annotations

import logging
import re
import time
import traceback
from pathlib import Path
from typing import TYPE_CHECKING

from .captions import DetectedCaption, find_all_captions
from .methods.cell_rawdict import RawdictExtraction
from .methods.cell_words import WordAssignment
from .methods.figure_detection import detect_figures, render_figure
from .methods.pymupdf_tables import PyMuPDFLines, PyMuPDFLinesStrict
from .models import (
    BoundaryHypothesis,
    CellGrid,
    ExtractionResult,
    PageFeatures,
    PipelineConfig,
    TableContext,
)
from .postprocessors.absorbed_caption import AbsorbedCaptionStrip
from .postprocessors.cell_cleaning import CellCleaning
from .postprocessors.continuation_merge import ContinuationMerge
from .postprocessors.footnote_strip import FootnoteStrip
from .postprocessors.header_data_split import HeaderDataSplit
from .postprocessors.header_detection import HeaderDetection
from .postprocessors.inline_headers import InlineHeaderFill

if TYPE_CHECKING:
    import pymupdf

logger = logging.getLogger(__name__)

_DECIMAL_DISPLACEMENT_RE = re.compile(r"^\.\d+")

# ---------------------------------------------------------------------------
# All post-processors in canonical order
# ---------------------------------------------------------------------------

_ALL_POSTPROCESSORS = (
    AbsorbedCaptionStrip(),
    HeaderDetection(),
    HeaderDataSplit(),
    ContinuationMerge(),
    InlineHeaderFill(),
    FootnoteStrip(),
    CellCleaning(),
)

# ---------------------------------------------------------------------------
# All structure methods
# ---------------------------------------------------------------------------

_ALL_STRUCTURE_METHODS = (
    PyMuPDFLines(),
    PyMuPDFLinesStrict(),
)

# ---------------------------------------------------------------------------
# All cell extraction methods
# ---------------------------------------------------------------------------

_ALL_CELL_METHODS = (
    RawdictExtraction(),
    WordAssignment(),
)

# ---------------------------------------------------------------------------
# Named pipeline configurations
# ---------------------------------------------------------------------------

DEFAULT_CONFIG: PipelineConfig = PipelineConfig(
    structure_methods=_ALL_STRUCTURE_METHODS,
    cell_methods=_ALL_CELL_METHODS,
    postprocessors=_ALL_POSTPROCESSORS,
    activation_rules={},
)

FAST_CONFIG: PipelineConfig = PipelineConfig(
    structure_methods=(
        PyMuPDFLines(),
    ),
    cell_methods=(
        RawdictExtraction(),
        WordAssignment(),
    ),
    postprocessors=_ALL_POSTPROCESSORS,
    activation_rules={},
)

RULED_CONFIG: PipelineConfig = PipelineConfig(
    structure_methods=_ALL_STRUCTURE_METHODS,
    cell_methods=_ALL_CELL_METHODS,
    postprocessors=_ALL_POSTPROCESSORS,
    activation_rules={},
)

MINIMAL_CONFIG: PipelineConfig = PipelineConfig(
    structure_methods=(
        PyMuPDFLines(),
    ),
    cell_methods=(
        RawdictExtraction(),
    ),
    postprocessors=(
        AbsorbedCaptionStrip(),
        CellCleaning(),
    ),
    activation_rules={},
)


def _compute_fill_rate(grid: CellGrid) -> float:
    """Fraction of non-empty cells. Returns 1.0 for grids with no cells."""
    all_cells: list[str] = list(grid.headers)
    for row in grid.rows:
        all_cells.extend(row)
    if not all_cells:
        return 1.0
    non_empty = sum(1 for c in all_cells if c.strip())
    return non_empty / len(all_cells)


def _count_decimal_displacement(grid: CellGrid) -> int:
    """Count cells matching ``^\\.\\d+`` (leading dot without zero)."""
    count = 0
    all_cells: list[str] = list(grid.headers)
    for row in grid.rows:
        all_cells.extend(row)
    for cell in all_cells:
        if _DECIMAL_DISPLACEMENT_RE.match(cell.strip()):
            count += 1
    return count


def _select_best_grid(grids: list[CellGrid]) -> tuple[CellGrid | None, dict[str, float]]:
    """Select the best grid by fill rate with decimal displacement sanity check.

    Returns (winning_grid, scores_dict) where scores_dict maps grid key to fill rate.
    """
    if not grids:
        return None, {}

    if len(grids) == 1:
        key = f"{grids[0].structure_method}:{grids[0].method}"
        return grids[0], {key: _compute_fill_rate(grids[0])}

    scores: dict[str, float] = {}
    best_grid: CellGrid | None = None
    best_fill: float = -1.0

    for grid in grids:
        key = f"{grid.structure_method}:{grid.method}"
        fill = _compute_fill_rate(grid)
        displacement = _count_decimal_displacement(grid)
        total_cells = len(grid.headers) + sum(len(row) for row in grid.rows)
        displacement_ratio = displacement / max(total_cells, 1)

        effective_fill = fill
        if displacement_ratio > 0.1:
            effective_fill *= (1.0 - displacement_ratio)

        scores[key] = fill

        if effective_fill > best_fill:
            best_fill = effective_fill
            best_grid = grid

    return best_grid, scores


class Pipeline:
    """Orchestrates table extraction for a single table region.

    Parameters
    ----------
    config:
        Immutable pipeline configuration specifying which methods to run,
        activation predicates, and strategy names.
    """

    def __init__(self, config: PipelineConfig) -> None:
        self._config = config

    def extract(self, ctx: TableContext) -> ExtractionResult:
        """Run the full extraction pipeline for a single table region.

        Parameters
        ----------
        ctx:
            Lazily-computed context about the table region on a PDF page.

        Returns
        -------
        ExtractionResult
            Mutable accumulator with all intermediate data: hypotheses,
            grids, scores, snapshots, errors, and timing.
        """
        result = ExtractionResult(
            table_id=f"p{ctx.page_num}_t0",
            bbox=ctx.bbox,
        )

        # ------------------------------------------------------------------
        # Step 1 + 2: Activation & structure detection
        # ------------------------------------------------------------------
        for method in self._config.structure_methods:
            predicate = self._config.activation_rules.get(method.name)
            if predicate is not None and not predicate(ctx):
                logger.debug("Skipping structure method %s (activation rule)", method.name)
                continue

            t0 = time.perf_counter()
            try:
                hypothesis = method.detect(ctx)
            except Exception as exc:
                elapsed = time.perf_counter() - t0
                result.timing[f"structure:{method.name}"] = elapsed
                tb = traceback.format_exc()
                result.method_errors.append((method.name, tb))
                logger.warning(
                    "Structure method %s crashed: %s", method.name, exc,
                )
                continue

            elapsed = time.perf_counter() - t0
            result.timing[f"structure:{method.name}"] = elapsed

            if hypothesis is not None:
                result.boundary_hypotheses.append(hypothesis)

        # ------------------------------------------------------------------
        # Step 3: Per-hypothesis cell extraction
        # ------------------------------------------------------------------
        if not result.boundary_hypotheses:
            result.consensus_boundaries = None
            return result

        for hypothesis in result.boundary_hypotheses:
            self._extract_cells_for_hypothesis(
                hypothesis, hypothesis.method, ctx, result,
            )

        # ------------------------------------------------------------------
        # Step 4: Select best grid
        # ------------------------------------------------------------------
        if not result.cell_grids:
            return result

        winning_grid, scores_dict = _select_best_grid(result.cell_grids)
        result.grid_scores = scores_dict
        result.winning_grid = winning_grid

        if result.winning_grid is None:
            return result

        # ------------------------------------------------------------------
        # Step 5: Post-processing
        # ------------------------------------------------------------------
        current_grid: CellGrid = result.winning_grid
        for pp in self._config.postprocessors:
            t0 = time.perf_counter()
            current_grid = pp.process(current_grid, ctx)
            elapsed = time.perf_counter() - t0
            result.timing[f"postprocess:{pp.name}"] = elapsed
            result.snapshots.append((pp.name, current_grid))

        result.post_processed = current_grid

        return result

    def _extract_cells_for_hypothesis(
        self,
        hypothesis: BoundaryHypothesis,
        structure_name: str,
        ctx: TableContext,
        result: ExtractionResult,
    ) -> None:
        """Run all cell methods against one hypothesis's boundaries.

        Grids are tagged with ``structure_name`` via ``with_structure_method()``
        and appended to ``result.cell_grids``.
        """
        if not hypothesis.col_boundaries and not hypothesis.row_boundaries:
            return

        col_positions = tuple(
            (bp.min_pos + bp.max_pos) / 2
            for bp in hypothesis.col_boundaries
        )
        row_positions = tuple(
            (bp.min_pos + bp.max_pos) / 2
            for bp in hypothesis.row_boundaries
        )

        for method in self._config.cell_methods:
            predicate = self._config.activation_rules.get(method.name)
            if predicate is not None and not predicate(ctx):
                continue

            t0 = time.perf_counter()
            try:
                grid = method.extract(ctx, col_positions, row_positions)
            except Exception as exc:
                elapsed = time.perf_counter() - t0
                result.timing[f"cell:{method.name}:{structure_name}"] = elapsed
                tb = traceback.format_exc()
                result.method_errors.append((method.name, tb))
                logger.warning(
                    "Cell method %s crashed on %s boundaries: %s",
                    method.name, structure_name, exc,
                )
                continue

            elapsed = time.perf_counter() - t0
            result.timing[f"cell:{method.name}:{structure_name}"] = elapsed

            if grid is not None:
                result.cell_grids.append(grid.with_structure_method(structure_name))

    def extract_batch(
        self, contexts: list[TableContext],
    ) -> list[ExtractionResult]:
        """Run extraction for multiple table regions sequentially.

        Parameters
        ----------
        contexts:
            List of table contexts to extract.

        Returns
        -------
        list[ExtractionResult]
            One result per context, in the same order.
        """
        return [self.extract(ctx) for ctx in contexts]

    def extract_page(
        self,
        page: pymupdf.Page,
        page_num: int,
        pdf_path: str | None = None,
        page_chunk: dict | None = None,
        *,
        write_images: bool = False,
        images_dir: str | None = None,
        doc: pymupdf.Document | None = None,
    ) -> PageFeatures:
        """Detect and extract all features (tables + figures) on a page.

        Parameters
        ----------
        page:
            A pymupdf Page object.
        page_num:
            1-indexed page number.
        pdf_path:
            Path to the PDF file (needed for cell extraction methods).
        page_chunk:
            The page chunk dict from pymupdf4llm layout engine. Contains
            page_boxes used for figure detection. If None, figure detection
            is skipped.
        write_images:
            If True, render figure regions to PNG files.
        images_dir:
            Directory to save figure images when write_images is True.
        doc:
            Open pymupdf.Document for figure rendering.

        Returns
        -------
        PageFeatures
            All tables and figures detected on the page.
        """
        # ------------------------------------------------------------------
        # Step 1: Find all captions on the page
        # ------------------------------------------------------------------
        all_captions = find_all_captions(page, include_figures=True, include_tables=True)
        table_captions = [c for c in all_captions if c.caption_type == "table"]
        figure_captions = [c for c in all_captions if c.caption_type == "figure"]

        # ------------------------------------------------------------------
        # Step 2: Find table bboxes via page.find_tables()
        # ------------------------------------------------------------------
        table_bboxes: list[tuple[float, float, float, float]] = []
        for strategy in ("lines", "lines_strict", "text"):
            try:
                finder = page.find_tables(strategy=strategy)
                for tab in finder.tables:
                    bbox = (tab.bbox[0], tab.bbox[1], tab.bbox[2], tab.bbox[3])
                    is_duplicate = False
                    for existing in table_bboxes:
                        overlap = _bbox_overlap_fraction(bbox, existing)
                        if overlap > 0.5:
                            is_duplicate = True
                            break
                    if not is_duplicate:
                        table_bboxes.append(bbox)
            except Exception:
                pass

        # ------------------------------------------------------------------
        # Step 3: Find figure bboxes
        # ------------------------------------------------------------------
        figure_results: list[tuple[tuple[float, float, float, float], str | None]] = []
        if page_chunk is not None:
            figure_results = detect_figures(page, page_chunk, figure_captions)

        # ------------------------------------------------------------------
        # Step 4: Match captions to table bboxes
        # ------------------------------------------------------------------
        table_caption_map: dict[int, DetectedCaption] = {}
        if table_captions and table_bboxes:
            sorted_tables_by_y = sorted(
                range(len(table_bboxes)),
                key=lambda i: table_bboxes[i][1],
            )
            numbered_captions: list[tuple[int, DetectedCaption]] = []
            for cap in table_captions:
                if cap.number is not None:
                    try:
                        num = int(cap.number)
                    except ValueError:
                        num = 0
                    numbered_captions.append((num, cap))
                else:
                    numbered_captions.append((0, cap))

            numbered_captions.sort(key=lambda x: x[0])

            for i, ti in enumerate(sorted_tables_by_y):
                if i < len(numbered_captions):
                    table_caption_map[ti] = numbered_captions[i][1]

        # ------------------------------------------------------------------
        # Step 5: Classify figure-data-table overlaps
        # ------------------------------------------------------------------
        figure_bboxes = [fb[0] for fb in figure_results]
        artifact_table_indices: set[int] = set()
        for ti, tbbox in enumerate(table_bboxes):
            for fbbox in figure_bboxes:
                overlap = _bbox_overlap_fraction(tbbox, fbbox)
                if overlap > 0.5:
                    artifact_table_indices.add(ti)
                    break

        # ------------------------------------------------------------------
        # Step 6: Extract each table
        # ------------------------------------------------------------------
        pdf_path_obj = Path(pdf_path) if pdf_path else Path(".")
        tables: list[ExtractionResult] = []
        for ti, tbbox in enumerate(table_bboxes):
            caption = table_caption_map.get(ti)
            ctx = TableContext(
                page=page,
                page_num=page_num,
                bbox=tbbox,
                pdf_path=pdf_path_obj,
                caption=caption,
            )
            result = self.extract(ctx)
            result.table_id = f"p{page_num}_t{ti}"
            if ti in artifact_table_indices:
                result.table_id = f"p{page_num}_t{ti}_artifact"
            result.caption = caption.text if caption else None
            result.footnotes = _extract_footnotes_from_snapshots(result)
            tables.append(result)

        # ------------------------------------------------------------------
        # Step 7: Build figure dicts
        # ------------------------------------------------------------------
        figures: list[dict] = []
        for fi, (fbbox, fcaption) in enumerate(figure_results):
            fig_dict: dict = {
                "bbox": fbbox,
                "caption": fcaption,
                "page_num": page_num,
                "image_path": None,
            }
            if write_images and doc is not None and images_dir is not None:
                img_path = render_figure(
                    doc,
                    page_num,
                    fbbox,
                    Path(images_dir),
                    fi,
                )
                fig_dict["image_path"] = str(img_path) if img_path else None
            figures.append(fig_dict)

        return PageFeatures(tables=tables, figures=figures)


def _extract_footnotes_from_snapshots(result: ExtractionResult) -> str:
    """Extract footnote text by diffing pre- and post-FootnoteStrip snapshots."""
    pre_grid: CellGrid | None = None
    post_grid: CellGrid | None = None
    for i, (name, grid) in enumerate(result.snapshots):
        if name == "footnote_strip":
            post_grid = grid
            if i > 0:
                pre_grid = result.snapshots[i - 1][1]
            elif result.winning_grid is not None:
                pre_grid = result.winning_grid
            break

    if pre_grid is None or post_grid is None:
        return ""

    pre_row_count = len(pre_grid.rows)
    post_row_count = len(post_grid.rows)
    if pre_row_count <= post_row_count:
        return ""

    removed_rows = pre_grid.rows[post_row_count:]
    footnote_parts = []
    for row in removed_rows:
        non_empty = [cell.strip() for cell in row if cell.strip()]
        if non_empty:
            footnote_parts.append(" ".join(non_empty))

    return " ".join(footnote_parts)


def _bbox_overlap_fraction(
    bbox_a: tuple[float, float, float, float],
    bbox_b: tuple[float, float, float, float],
) -> float:
    """Compute the fraction of bbox_a that overlaps with bbox_b."""
    x0 = max(bbox_a[0], bbox_b[0])
    y0 = max(bbox_a[1], bbox_b[1])
    x1 = min(bbox_a[2], bbox_b[2])
    y1 = min(bbox_a[3], bbox_b[3])

    if x1 <= x0 or y1 <= y0:
        return 0.0

    intersection_area = (x1 - x0) * (y1 - y0)
    area_a = (bbox_a[2] - bbox_a[0]) * (bbox_a[3] - bbox_a[1])
    if area_a <= 0:
        return 0.0
    return intersection_area / area_a
