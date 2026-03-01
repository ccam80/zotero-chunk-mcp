"""PaddleOCR-VL-1.5 engine: VLM-based PDF table extraction with markdown output."""

from __future__ import annotations

import os
import re
from pathlib import Path

os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

from paddleocr import PaddleOCRVL  # noqa: E402

from ..paddle_extract import RawPaddleTable  # noqa: E402

# Matches markdown table separator rows: cells containing only dashes, colons,
# and spaces (e.g. |---|, |:---|, |---:|, |:---:|).
_SEPARATOR_RE = re.compile(r"^\|(?:\s*:?-+:?\s*\|)+\s*$")


def _parse_markdown_table(md: str) -> tuple[list[str], list[list[str]], str]:
    """Parse a GitHub-flavour markdown table into headers, rows, and footnotes.

    Args:
        md: Raw markdown string containing a table.

    Returns:
        A three-tuple ``(headers, rows, footnotes)`` where *headers* is the
        first (header) row's cells, *rows* is every subsequent data row, and
        *footnotes* is any text found after the table body (currently always
        an empty string because the VL engine embeds footnotes in the block
        text rather than appending them to the markdown).
    """
    if not md or not md.strip():
        return [], [], ""

    raw_lines = md.splitlines()

    # Split on unescaped pipes only.  We temporarily replace ``\|`` with a
    # placeholder so a simple ``split("|")`` doesn't break on escaped pipes.
    _ESCAPED_PIPE_PLACEHOLDER = "\x00PIPE\x00"

    def _split_row(line: str) -> list[str]:
        """Split one markdown table row on unescaped ``|`` characters."""
        safe = line.replace(r"\|", _ESCAPED_PIPE_PLACEHOLDER)
        parts = safe.split("|")
        # Strip leading/trailing empty strings produced by outer ``|`` chars.
        if parts and parts[0].strip() == "":
            parts = parts[1:]
        if parts and parts[-1].strip() == "":
            parts = parts[:-1]
        return [p.replace(_ESCAPED_PIPE_PLACEHOLDER, "|").strip() for p in parts]

    # Collect only lines that look like table rows (contain at least one ``|``).
    table_lines = [ln for ln in raw_lines if "|" in ln]

    if not table_lines:
        return [], [], ""

    # Identify whether a separator row exists and where.
    separator_index: int | None = None
    for i, line in enumerate(table_lines):
        if _SEPARATOR_RE.match(line.strip()):
            separator_index = i
            break

    if separator_index is not None:
        # Standard layout: row 0 = headers, separator_index = alignment row,
        # rows after separator = data rows.
        headers = _split_row(table_lines[0])
        data_lines = table_lines[separator_index + 1 :]
    else:
        # Fallback: no separator found — treat first row as headers.
        headers = _split_row(table_lines[0])
        data_lines = table_lines[1:]

    rows = [_split_row(ln) for ln in data_lines if ln.strip()]

    return headers, rows, ""


class PaddleOCRVLEngine:
    """PaddleOCR-VL-1.5 engine for extracting tables from PDF files.

    Initialises the VLM pipeline once at construction time.  Each call to
    ``extract_tables`` runs a full-document predict pass and returns all
    detected table blocks as ``RawPaddleTable`` instances.
    """

    def __init__(self) -> None:
        self._pipeline = PaddleOCRVL(pipeline_version="v1.5", device="gpu:0")

    def extract_tables(self, pdf_path: Path) -> list[RawPaddleTable]:
        """Extract all tables from *pdf_path* using PaddleOCR-VL-1.5.

        The pipeline runs predict on the full PDF, then ``restructure_pages``
        merges cross-page tables before the results are iterated.

        Args:
            pdf_path: Absolute path to the PDF file.

        Returns:
            One ``RawPaddleTable`` per detected table block.
        """
        pages_res = self._pipeline.predict(str(pdf_path))
        restructured = self._pipeline.restructure_pages(pages_res, merge_tables=True)

        tables: list[RawPaddleTable] = []
        for page_result in restructured:
            page_num: int = page_result.get("page_num", 1)
            page_width: int = page_result.get("page_width", 0)
            page_height: int = page_result.get("page_height", 0)
            page_size: tuple[int, int] = (page_width, page_height)

            for block in page_result.get("parsing_res_list", []):
                block_label: str = block.get("block_label", "")
                if "table" not in block_label.lower():
                    continue

                markdown_str: str = block.get("block_content", "") or ""
                bbox_raw = block.get("block_bbox", [0.0, 0.0, 0.0, 0.0])
                bbox: tuple[float, float, float, float] = (
                    float(bbox_raw[0]),
                    float(bbox_raw[1]),
                    float(bbox_raw[2]),
                    float(bbox_raw[3]),
                )

                headers, rows, footnotes = _parse_markdown_table(markdown_str)

                tables.append(
                    RawPaddleTable(
                        page_num=page_num,
                        bbox=bbox,
                        page_size=page_size,
                        headers=headers,
                        rows=rows,
                        footnotes=footnotes,
                        engine_name="paddleocr_vl_1.5",
                        raw_output=markdown_str,
                    )
                )

        return tables
