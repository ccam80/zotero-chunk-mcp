"""Pipeline class — runs structure methods, combines boundaries, extracts cells, post-processes.

Orchestrates the full extraction flow:
1. Activate methods (check activation rules)
2. Run structure detection (produce BoundaryHypotheses)
3. Combine boundaries (consensus voting)
4. Run cell extraction (produce CellGrids)
5. Score and select the best grid
6. Run post-processors in order

Also defines named pipeline configurations (DEFAULT_CONFIG, FAST_CONFIG, etc.).
"""

from __future__ import annotations

import json
import logging
import time
import traceback
from pathlib import Path
from typing import TYPE_CHECKING

from .captions import DetectedCaption, find_all_captions
from .combination import combine_hypotheses
from .methods.camelot_extraction import CamelotHybrid, CamelotLattice
from .methods.cell_pdfminer import PdfMinerExtraction
from .methods.cell_rawdict import RawdictExtraction
from .methods.cell_words import WordAssignment
from .methods.cliff import GlobalCliff, PerRowCliff
from .methods.figure_detection import detect_figures, render_figure
from .methods.header_anchor import HeaderAnchor
from .methods.hotspot import GapSpanHotspot, SinglePointHotspot
from .methods.pdfplumber_structure import PdfplumberLines, PdfplumberText
from .methods.pymupdf_tables import PyMuPDFLines, PyMuPDFLinesStrict, PyMuPDFText
from .methods.ruled_lines import RuledLineDetection
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
from .scoring import rank_and_select
from .table_features import has_ruled_lines

if TYPE_CHECKING:
    import pymupdf

logger = logging.getLogger(__name__)

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
    SinglePointHotspot(),
    GapSpanHotspot(),
    GlobalCliff(),
    PerRowCliff(),
    HeaderAnchor(),
    RuledLineDetection(),
    PyMuPDFLines(),
    PyMuPDFLinesStrict(),
    PyMuPDFText(),
    CamelotLattice(),
    CamelotHybrid(),
    PdfplumberLines(),
    PdfplumberText(),
)

# ---------------------------------------------------------------------------
# All cell extraction methods
# ---------------------------------------------------------------------------

_ALL_CELL_METHODS = (
    RawdictExtraction(),
    WordAssignment(),
    PdfMinerExtraction(),
)

# ---------------------------------------------------------------------------
# Named pipeline configurations
# ---------------------------------------------------------------------------

DEFAULT_CONFIG: PipelineConfig = PipelineConfig(
    structure_methods=_ALL_STRUCTURE_METHODS,
    cell_methods=_ALL_CELL_METHODS,
    postprocessors=_ALL_POSTPROCESSORS,
    activation_rules={
        "camelot_lattice": has_ruled_lines,
        "camelot_hybrid": has_ruled_lines,
        "global_cliff": lambda ctx: not has_ruled_lines(ctx),
        "per_row_cliff": lambda ctx: not has_ruled_lines(ctx),
    },
    combination_strategy="expand_overlap",
    selection_strategy="rank_based",
)

FAST_CONFIG: PipelineConfig = PipelineConfig(
    structure_methods=(
        PyMuPDFLines(),
        GapSpanHotspot(),
    ),
    cell_methods=(
        RawdictExtraction(),
        WordAssignment(),
    ),
    postprocessors=_ALL_POSTPROCESSORS,
    activation_rules={},
    combination_strategy="expand_overlap",
    selection_strategy="rank_based",
)

RULED_CONFIG: PipelineConfig = PipelineConfig(
    structure_methods=_ALL_STRUCTURE_METHODS,
    cell_methods=_ALL_CELL_METHODS,
    postprocessors=_ALL_POSTPROCESSORS,
    activation_rules={
        "camelot_lattice": has_ruled_lines,
        "camelot_hybrid": has_ruled_lines,
        "global_cliff": lambda ctx: not has_ruled_lines(ctx),
        "per_row_cliff": lambda ctx: not has_ruled_lines(ctx),
    },
    combination_strategy="expand_overlap",
    selection_strategy="rank_based",
    confidence_multipliers={"ruled_lines": 3.0},
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
    combination_strategy="expand_overlap",
    selection_strategy="rank_based",
)


class Pipeline:
    """Orchestrates multi-method table extraction for a single table region.

    Parameters
    ----------
    config:
        Immutable pipeline configuration specifying which methods to run,
        activation predicates, and strategy names.
    """

    # Default location for the tuned weights JSON file.
    # Set by tests or via Pipeline(config, weights_path=...) for custom locations.
    _DEFAULT_WEIGHTS_PATH: Path = Path(__file__).resolve().parents[3] / "tests" / "pipeline_weights.json"

    def __init__(
        self,
        config: PipelineConfig,
        weights_path: Path | None = None,
    ) -> None:
        # Check for pipeline_weights.json and merge confidence multipliers
        wp = weights_path if weights_path is not None else self._DEFAULT_WEIGHTS_PATH
        if wp.exists():
            try:
                data = json.loads(wp.read_text(encoding="utf-8"))
                file_multipliers = data.get("confidence_multipliers", {})
                if file_multipliers:
                    # Merge: file values override config defaults
                    merged = dict(config.confidence_multipliers)
                    merged.update(file_multipliers)
                    config = config.with_overrides(confidence_multipliers=merged)
                    logger.info(
                        "Loaded %d confidence multipliers from %s",
                        len(file_multipliers), wp,
                    )
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to read weights from %s: %s", wp, exc)

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
            # Activation check
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
        # Step 3: Per-method cell extraction
        # ------------------------------------------------------------------
        if not result.boundary_hypotheses:
            result.consensus_boundaries = None
            return result

        for hypothesis in result.boundary_hypotheses:
            self._extract_cells_for_hypothesis(
                hypothesis, hypothesis.method, ctx, result,
            )

        # ------------------------------------------------------------------
        # Step 4: Consensus combination + cell extraction
        # ------------------------------------------------------------------
        result.consensus_boundaries = combine_hypotheses(
            result.boundary_hypotheses, ctx,
            confidence_multipliers=self._config.confidence_multipliers,
        )

        if result.consensus_boundaries is not None:
            self._extract_cells_for_hypothesis(
                result.consensus_boundaries, "consensus", ctx, result,
            )

        # ------------------------------------------------------------------
        # Step 6: Scoring and selection
        # ------------------------------------------------------------------
        if not result.cell_grids:
            return result

        winning_grid, scores_dict = rank_and_select(result.cell_grids, ctx)
        result.grid_scores = scores_dict
        result.winning_grid = winning_grid

        if result.winning_grid is None:
            return result

        # ------------------------------------------------------------------
        # Step 7: Post-processing
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
                    # Deduplicate: skip if we already have a table with >50% overlap
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
    """Extract footnote text by diffing pre- and post-FootnoteStrip snapshots.

    The FootnoteStrip post-processor removes footnote rows from the grid.
    By comparing the grid before and after FootnoteStrip, we can recover
    the removed rows and concatenate their text as the footnote string.

    Returns empty string if no FootnoteStrip snapshot exists or no rows
    were removed.
    """
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
    """Compute the fraction of bbox_a that overlaps with bbox_b.

    Returns a value between 0.0 and 1.0. Uses the area of intersection
    divided by the area of bbox_a.
    """
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
