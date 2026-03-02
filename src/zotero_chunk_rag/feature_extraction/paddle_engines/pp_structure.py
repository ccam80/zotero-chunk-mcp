"""PP-StructureV3 engine: initialises PaddleOCR's PP-StructureV3 pipeline and
extracts tables from PDFs by parsing the HTML output produced by the table
recognition stage.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")


from ..paddle_extract import RawPaddleTable


def _parse_html_table(html: str) -> tuple[list[str], list[list[str]], str]:
    """Parse an HTML table string into headers, data rows, and footnotes.

    Args:
        html: Raw HTML containing a ``<table>`` element, optionally followed
              by footnote text after the closing ``</table>`` tag.

    Returns:
        A 3-tuple ``(headers, rows, footnotes)`` where:
        - ``headers`` is a list of column header strings.
        - ``rows`` is a list of data rows, each a list of cell strings.
        - ``footnotes`` is any plain text that appears after ``</table>``.
    """
    # Extract footnotes: text after </table>
    table_end_match = re.search(r"</table\s*>", html, re.IGNORECASE)
    if table_end_match:
        after = html[table_end_match.end():]
        footnotes = re.sub(r"<[^>]+>", " ", after)
        footnotes = " ".join(footnotes.split())
        table_html = html[: table_end_match.end()]
    else:
        footnotes = ""
        table_html = html

    # Extract all <tr> blocks
    tr_pattern = re.compile(r"<tr[^>]*>(.*?)</tr\s*>", re.IGNORECASE | re.DOTALL)
    tr_blocks = tr_pattern.findall(table_html)

    if not tr_blocks:
        return [], [], footnotes

    def _parse_cells(
        tr_html: str, tag: str
    ) -> list[tuple[str, int, int]]:
        """Return list of (text, colspan, rowspan) for each cell in a row."""
        cell_pattern = re.compile(
            rf"<{tag}([^>]*)>(.*?)</{tag}\s*>",
            re.IGNORECASE | re.DOTALL,
        )
        cells = []
        for attrs_str, content in cell_pattern.findall(tr_html):
            colspan_m = re.search(r'colspan\s*=\s*["\']?(\d+)["\']?', attrs_str, re.IGNORECASE)
            rowspan_m = re.search(r'rowspan\s*=\s*["\']?(\d+)["\']?', attrs_str, re.IGNORECASE)
            colspan = int(colspan_m.group(1)) if colspan_m else 1
            rowspan = int(rowspan_m.group(1)) if rowspan_m else 1
            text = re.sub(r"<[^>]+>", " ", content)
            text = " ".join(text.split())
            cells.append((text, colspan, rowspan))
        return cells

    # Determine whether any row uses <th> tags
    has_th = bool(re.search(r"<th[\s>]", table_html, re.IGNORECASE))

    # Build a grid that handles colspan and rowspan.
    # pending_rowspans[col] = (remaining_rows, value) for active rowspans.
    pending_rowspans: dict[int, tuple[int, str]] = {}

    def _expand_row(
        raw_cells: list[tuple[str, int, int]],
        row_index: int,
    ) -> tuple[list[str], dict[int, tuple[int, str]]]:
        """Expand a list of raw cells into a full row, respecting rowspans."""
        result: list[str] = []
        new_pending: dict[int, tuple[int, str]] = {}

        # Determine which column slots are already occupied by rowspans
        col = 0
        raw_iter = iter(raw_cells)
        consumed = False

        def next_free_col() -> int:
            nonlocal col
            while col in pending_rowspans:
                remaining, val = pending_rowspans[col]
                result.append(val)
                if remaining - 1 > 0:
                    new_pending[col] = (remaining - 1, val)
                col += 1
            return col

        for text, colspan, rowspan in raw_cells:
            col = next_free_col()
            for _ in range(colspan):
                result.append(text)
                if rowspan > 1:
                    new_pending[col] = (rowspan - 1, text)
                col += 1

        # Flush any trailing rowspan columns
        while col in pending_rowspans:
            remaining, val = pending_rowspans[col]
            result.append(val)
            if remaining - 1 > 0:
                new_pending[col] = (remaining - 1, val)
            col += 1

        return result, new_pending

    header_rows: list[list[str]] = []
    data_rows: list[list[str]] = []

    for i, tr_html in enumerate(tr_blocks):
        if has_th:
            th_cells = _parse_cells(tr_html, "th")
            td_cells = _parse_cells(tr_html, "td")
            if th_cells:
                expanded, new_pending = _expand_row(th_cells, i)
                pending_rowspans.update(new_pending)
                header_rows.append(expanded)
                continue
            else:
                raw_cells = td_cells
        else:
            raw_cells = _parse_cells(tr_html, "td")

        expanded, new_pending = _expand_row(raw_cells, i)
        pending_rowspans.update(new_pending)

        if not has_th and not header_rows:
            header_rows.append(expanded)
        else:
            data_rows.append(expanded)

    headers = header_rows[0] if header_rows else []
    return headers, data_rows, footnotes


class PPStructureEngine:
    """PaddleOCR PP-StructureV3 table extraction engine.

    Initialises the PP-StructureV3 pipeline at construction time and processes
    full PDF files, extracting table regions from the layout detection output
    and parsing their HTML representations into structured ``RawPaddleTable``
    objects.
    """
    from paddleocr import PPStructureV3  # noqa: E402

    def __init__(self) -> None:
        self._pipeline = PPStructureV3(device="gpu", lang="en")

    def extract_tables(self, pdf_path: Path) -> list[RawPaddleTable]:
        """Extract all tables from a PDF file.

        Args:
            pdf_path: Absolute path to the PDF file.

        Returns:
            One ``RawPaddleTable`` per detected table region, in page order.
        """
        results = self._pipeline.predict(str(pdf_path))

        tables: list[RawPaddleTable] = []

        for page_result in results:
            page_num: int = page_result.get("page_num", 0)
            page_width: int = page_result.get("page_width", 0)
            page_height: int = page_result.get("page_height", 0)
            page_size: tuple[int, int] = (page_width, page_height)

            layout_regions = page_result.get("layout_result", {}).get("boxes", [])

            for region in layout_regions:
                label: str = region.get("label", "").lower()
                if label != "table":
                    continue

                bbox_raw = region.get("bbox", [0.0, 0.0, 0.0, 0.0])
                bbox: tuple[float, float, float, float] = (
                    float(bbox_raw[0]),
                    float(bbox_raw[1]),
                    float(bbox_raw[2]),
                    float(bbox_raw[3]),
                )

                html: str = region.get("table_result", {}).get("html", "")

                headers, rows, footnotes = _parse_html_table(html)

                tables.append(
                    RawPaddleTable(
                        page_num=page_num,
                        bbox=bbox,
                        page_size=page_size,
                        headers=headers,
                        rows=rows,
                        footnotes=footnotes,
                        engine_name="pp_structure_v3",
                        raw_output=html,
                    )
                )

        return tables
