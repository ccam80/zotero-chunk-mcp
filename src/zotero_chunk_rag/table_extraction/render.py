"""Rendering utilities -- render table regions from PDFs as PNG images."""
from __future__ import annotations

from pathlib import Path

import pymupdf

from zotero_chunk_rag.models import ExtractedTable


def render_table_image(
    pdf_path: Path | str,
    page_num: int,
    bbox: tuple[float, float, float, float],
    output_path: Path,
    *,
    dpi: int = 300,
    padding: int = 20,
) -> Path:
    """Render a table region from a PDF page as a PNG image.

    Parameters
    ----------
    pdf_path:
        Path to the source PDF.
    page_num:
        1-indexed page number (consistent with the rest of the codebase).
    bbox:
        ``(x0, y0, x1, y1)`` bounding box in PDF points.
    output_path:
        Destination path for the PNG file.
    dpi:
        Resolution for rendering (default 300).
    padding:
        PDF-point padding added around the bbox before rendering.
        The padded region is clipped to page bounds.

    Returns
    -------
    Path
        The *output_path* (for convenience in chaining).
    """
    pdf_path = Path(pdf_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = pymupdf.open(str(pdf_path))
    try:
        page = doc[page_num - 1]  # convert 1-indexed to 0-indexed
        page_rect = page.rect

        x0, y0, x1, y1 = bbox
        clip = pymupdf.Rect(
            max(x0 - padding, page_rect.x0),
            max(y0 - padding, page_rect.y0),
            min(x1 + padding, page_rect.x1),
            min(y1 + padding, page_rect.y1),
        )

        pix = page.get_pixmap(clip=clip, dpi=dpi)
        pix.save(str(output_path))
    finally:
        doc.close()

    return output_path


def render_all_tables(
    pdf_path: Path | str,
    tables: list[ExtractedTable],
    output_dir: Path,
    *,
    dpi: int = 300,
) -> dict[str, Path]:
    """Render all non-artifact tables as PNG images.

    Parameters
    ----------
    pdf_path:
        Path to the source PDF.
    tables:
        List of ``ExtractedTable`` objects (typically from extraction).
    output_dir:
        Directory where PNG files will be written.
    dpi:
        Resolution for rendering (default 300).

    Returns
    -------
    dict[str, Path]
        Mapping of ``{caption_or_id: output_path}`` for each rendered table.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    result: dict[str, Path] = {}

    for idx, t in enumerate(tables):
        if t.artifact_type is not None:
            continue

        if t.caption:
            key = t.caption
        else:
            key = f"table_p{t.page_num}_i{t.table_index}"

        safe_name = f"table_{idx:03d}.png"
        out = output_dir / safe_name

        render_table_image(
            pdf_path,
            t.page_num,
            t.bbox,
            out,
            dpi=dpi,
        )
        result[key] = out

    return result
