"""Vision-primary, traditional-fallback orchestrator.

Wraps the existing Pipeline class. Uses Pipeline.extract_page() for bbox
discovery and figure detection, then replaces the per-table cell extraction
with vision agents where vision extraction succeeds with sufficient consensus.

Typical usage::

    client = anthropic.AsyncAnthropic()
    pipeline = Pipeline(DEFAULT_CONFIG)
    page_features = await extract_page_with_vision(
        page, page_num, pdf_path, pipeline, client=client
    )
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

from .models import CellGrid, ExtractionResult, PageFeatures, TableContext
from .pipeline import Pipeline
from .postprocessors.absorbed_caption import AbsorbedCaptionStrip
from .postprocessors.cell_cleaning import CellCleaning
from .postprocessors.continuation_merge import ContinuationMerge

if TYPE_CHECKING:
    import pymupdf

try:
    import anthropic
except ImportError:
    anthropic = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Reduced post-processor chain for vision results.
# The LLM already handles header detection, header/data split, inline headers,
# and footnote extraction, so only these three remain.
# ---------------------------------------------------------------------------

VISION_POSTPROCESSORS = (
    AbsorbedCaptionStrip(),
    ContinuationMerge(),
    CellCleaning(),
)


# ---------------------------------------------------------------------------
# Public async API
# ---------------------------------------------------------------------------


async def extract_page_with_vision(
    page: pymupdf.Page,
    page_num: int,
    pdf_path: Path,
    traditional_pipeline: Pipeline,
    *,
    client: anthropic.AsyncAnthropic | None = None,
    use_vision: bool = True,
    consensus_threshold: float = 0.6,
    vision_model: str = "claude-haiku-4-5-20251001",
    vision_num_agents: int = 3,
    vision_dpi: int = 300,
    vision_padding_px: int = 20,
    page_chunk: dict | None = None,
    write_images: bool = False,
    images_dir: str | None = None,
    doc: pymupdf.Document | None = None,
) -> PageFeatures:
    """Detect page features using the traditional pipeline, then optionally
    replace per-table cell extraction with vision agents.

    The traditional pipeline is ALWAYS run first for bbox and figure
    discovery. Vision only replaces the cell extraction step for tables
    where the vision consensus meets *consensus_threshold*.

    Parameters
    ----------
    page:
        A pymupdf Page object.
    page_num:
        1-indexed page number.
    pdf_path:
        Path to the PDF file.
    traditional_pipeline:
        Fully-initialised Pipeline instance used for bbox discovery and
        as the fallback extractor.
    client:
        Async Anthropic client. If None, vision is skipped even when
        *use_vision* is True.
    use_vision:
        Set to False to disable vision extraction entirely (traditional
        result returned as-is).
    consensus_threshold:
        Minimum ``agent_agreement_rate`` required to accept a vision result.
        Tables below this threshold fall back to the traditional result.
    vision_model:
        Anthropic model identifier passed to ``extract_table_vision()``.
    vision_num_agents:
        Number of independent vision agents to run per table.
    vision_dpi:
        Resolution for rendering table region PNG crops.
    vision_padding_px:
        Padding (pixels) added around each table bbox before rendering.
    page_chunk:
        Page chunk dict from pymupdf4llm (used by figure detection).
    write_images:
        Passed through to ``Pipeline.extract_page()`` for figure rendering.
    images_dir:
        Passed through to ``Pipeline.extract_page()`` for figure rendering.
    doc:
        Open pymupdf.Document for figure rendering.

    Returns
    -------
    PageFeatures
        Tables and figures detected on the page. Table ExtractionResults may
        be a mix of vision-extracted and traditionally-extracted depending on
        per-table consensus scores.
    """
    # Step 1: Always run the traditional pipeline for bbox / figure discovery.
    page_features: PageFeatures = traditional_pipeline.extract_page(
        page,
        page_num,
        str(pdf_path),
        page_chunk,
        write_images=write_images,
        images_dir=images_dir,
        doc=doc,
    )

    # Step 2: Early exit if vision is disabled or unavailable.
    if not use_vision or client is None:
        return page_features

    # Step 3: Replace per-table cell extraction with vision where possible.
    from .vision_extract import (  # local import — optional dependency
        VisionExtractionResult,
        extract_table_vision,
        vision_result_to_cell_grid,
    )

    upgraded_tables: list[ExtractionResult] = []

    for traditional_table in page_features.tables:
        table_id = traditional_table.table_id
        bbox = traditional_table.bbox
        caption_text = traditional_table.caption or ""
        raw_text = page.get_text("text", clip=bbox)

        try:
            vision_result: VisionExtractionResult = await extract_table_vision(
                page=page,
                bbox=bbox,
                raw_text=raw_text,
                caption=caption_text,
                client=client,
                model=vision_model,
                num_agents=vision_num_agents,
                dpi=vision_dpi,
                padding_px=vision_padding_px,
            )
        except Exception as exc:
            logger.info(
                "Table %s: vision fallback — extract_table_vision raised %s",
                table_id,
                exc,
            )
            upgraded_tables.append(traditional_table)
            continue

        # Decide whether to accept the vision result.
        consensus = vision_result.consensus if vision_result is not None else None

        if consensus is None:
            logger.info(
                "Table %s: vision fallback — no consensus produced",
                table_id,
            )
            upgraded_tables.append(traditional_table)
            continue

        agreement = getattr(consensus, "agent_agreement_rate", 0.0)
        if agreement < consensus_threshold:
            logger.info(
                "Table %s: vision fallback — agreement %.2f below threshold %.2f",
                table_id,
                agreement,
                consensus_threshold,
            )
            upgraded_tables.append(traditional_table)
            continue

        # Convert and post-process the vision grid.
        vision_grid: CellGrid | None = vision_result_to_cell_grid(vision_result)
        if vision_grid is None:
            logger.info(
                "Table %s: vision fallback — vision_result_to_cell_grid returned None",
                table_id,
            )
            upgraded_tables.append(traditional_table)
            continue

        ctx = TableContext(
            page=page,
            page_num=page_num,
            bbox=bbox,
            pdf_path=pdf_path,
        )
        current = vision_grid
        for pp in VISION_POSTPROCESSORS:
            current = pp.process(current, ctx)

        vision_result_obj = ExtractionResult(
            table_id=table_id,
            bbox=bbox,
        )
        vision_result_obj.winning_grid = vision_grid
        vision_result_obj.post_processed = current
        vision_result_obj.caption = traditional_table.caption
        vision_result_obj.footnotes = (
            consensus.footnotes if hasattr(consensus, "footnotes") else ""
        )
        # Record the strategy so callers can identify vision-sourced results.
        vision_result_obj.timing["extraction_strategy"] = 0.0  # marker entry
        vision_result_obj.method_errors = []  # explicit empty

        logger.info(
            "Table %s: vision extraction accepted (agreement=%.2f)",
            table_id,
            agreement,
        )
        upgraded_tables.append(vision_result_obj)

    return PageFeatures(tables=upgraded_tables, figures=page_features.figures)


async def extract_prose_table_with_vision(
    pdf_path: Path,
    page: pymupdf.Page,
    page_num: int,
    caption_text: str,
    caption_bbox: tuple[float, float, float, float],
    *,
    client: anthropic.AsyncAnthropic | None = None,
    model: str = "claude-haiku-4-5-20251001",
    num_agents: int = 3,
    dpi: int = 300,
) -> VisionExtractionResult | None:
    """Run vision extraction on a prose table that find_tables() missed.

    The caller provides a caption bbox; this function estimates a table bbox
    covering the lower half of the remaining page below the caption, then
    calls ``extract_table_vision()``.

    Parameters
    ----------
    pdf_path:
        Path to the PDF file (currently unused but included for future
        rendering paths that may need it).
    page:
        A pymupdf Page object.
    page_num:
        1-indexed page number.
    caption_text:
        Caption text associated with this prose table.
    caption_bbox:
        Bounding box of the caption: (x0, y0, x1, y1).
    client:
        Async Anthropic client. Returns None immediately if None.
    model:
        Anthropic model identifier.
    num_agents:
        Number of independent vision agents.
    dpi:
        Resolution for rendering the table region crop.

    Returns
    -------
    VisionExtractionResult | None
        Vision result, or None if extraction failed or client is unavailable.
    """
    if client is None:
        return None

    from .vision_extract import VisionExtractionResult, extract_table_vision

    page_rect = page.rect
    # Estimate table bbox: full page width, from caption bottom to next 50% of
    # remaining page height.
    bbox: tuple[float, float, float, float] = (
        page_rect.x0,
        caption_bbox[3],
        page_rect.x1,
        min(page_rect.y1, caption_bbox[3] + page_rect.height * 0.5),
    )
    raw_text = page.get_text("text", clip=bbox)

    try:
        result: VisionExtractionResult = await extract_table_vision(
            page=page,
            bbox=bbox,
            raw_text=raw_text,
            caption=caption_text,
            client=client,
            model=model,
            num_agents=num_agents,
            dpi=dpi,
        )
    except Exception as exc:
        logger.info(
            "Prose table p%d '%s': vision extraction failed — %s",
            page_num,
            caption_text[:60],
            exc,
        )
        return None

    return result


# ---------------------------------------------------------------------------
# Availability helper
# ---------------------------------------------------------------------------


def vision_available(client: anthropic.AsyncAnthropic | None = None) -> bool:
    """Return True if vision extraction is available.

    Requires the ``anthropic`` package to be installed and a client to be
    provided.
    """
    return anthropic is not None and client is not None
