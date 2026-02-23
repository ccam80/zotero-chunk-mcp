"""Tests for HeaderDetection post-processor."""
from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock

import pytest

from zotero_chunk_rag.feature_extraction.models import CellGrid, TableContext
from zotero_chunk_rag.feature_extraction.postprocessors.header_detection import (
    HeaderDetection,
    _row_font_properties,
)
from zotero_chunk_rag.feature_extraction.protocols import PostProcessor


def _make_dict_blocks(
    rows_spec: list[dict],
) -> list[dict]:
    """Build dict_blocks from a spec: list of {y_center, size, bold, text}.

    Each entry generates one block with one line and one span.
    """
    blocks = []
    for spec in rows_spec:
        y = spec["y_center"]
        blocks.append({
            "type": 0,
            "lines": [{
                "spans": [{
                    "bbox": (10.0, y - 5.0, 200.0, y + 5.0),
                    "size": spec["size"],
                    "flags": 16 if spec.get("bold", False) else 0,
                    "font": "Arial-Bold" if spec.get("bold", False) else "Arial",
                    "text": spec.get("text", "sample text"),
                }],
            }],
        })
    return blocks


def _make_ctx(dict_blocks: list[dict], bbox: tuple = (0.0, 0.0, 300.0, 200.0)) -> MagicMock:
    ctx = MagicMock(spec=TableContext)
    ctx.dict_blocks = dict_blocks
    ctx.bbox = bbox
    return ctx


def _make_grid(
    rows: tuple[tuple[str, ...], ...],
    headers: tuple[str, ...] = (),
    row_boundaries: tuple[float, ...] = (),
) -> CellGrid:
    return CellGrid(
        headers=headers,
        rows=rows,
        col_boundaries=(0.0, 150.0, 300.0),
        row_boundaries=row_boundaries,
        method="test",
    )


class TestHeaderDetection:
    def test_bold_header(self) -> None:
        """Bold row 0, regular rows 1+. Assert row 0 moved to headers."""
        dict_blocks = _make_dict_blocks([
            {"y_center": 25.0, "size": 9.0, "bold": True, "text": "Header A"},
            {"y_center": 75.0, "size": 9.0, "bold": False, "text": "data1"},
            {"y_center": 125.0, "size": 9.0, "bold": False, "text": "data2"},
        ])
        grid = _make_grid(
            rows=(
                ("Header A", "Header B", "Header C"),
                ("data1", "data2", "data3"),
                ("data4", "data5", "data6"),
            ),
            row_boundaries=(50.0, 100.0),
        )
        ctx = _make_ctx(dict_blocks)

        pp = HeaderDetection()
        result = pp.process(grid, ctx)

        assert result.headers == ("Header A", "Header B", "Header C")
        assert len(result.rows) == 2
        assert result.rows[0] == ("data1", "data2", "data3")

    def test_larger_font_header(self) -> None:
        """Row 0 at 10pt, data at 8pt. Assert detected as header."""
        dict_blocks = _make_dict_blocks([
            {"y_center": 25.0, "size": 10.0, "bold": False, "text": "Head"},
            {"y_center": 75.0, "size": 8.0, "bold": False, "text": "val1"},
            {"y_center": 125.0, "size": 8.0, "bold": False, "text": "val2"},
        ])
        grid = _make_grid(
            rows=(
                ("Head1", "Head2", "Head3"),
                ("val1", "val2", "val3"),
                ("val4", "val5", "val6"),
            ),
            row_boundaries=(50.0, 100.0),
        )
        ctx = _make_ctx(dict_blocks)

        pp = HeaderDetection()
        result = pp.process(grid, ctx)

        assert result.headers == ("Head1", "Head2", "Head3")
        assert len(result.rows) == 2

    def test_multi_row_header(self) -> None:
        """Rows 0-1 bold, rows 2+ regular. Both should become headers."""
        dict_blocks = _make_dict_blocks([
            {"y_center": 15.0, "size": 9.0, "bold": True, "text": "H1"},
            {"y_center": 40.0, "size": 9.0, "bold": True, "text": "H2"},
            {"y_center": 70.0, "size": 9.0, "bold": False, "text": "d1"},
            {"y_center": 100.0, "size": 9.0, "bold": False, "text": "d2"},
        ])
        grid = _make_grid(
            rows=(
                ("Category", "", ""),
                ("A", "B", "C"),
                ("d1", "d2", "d3"),
                ("d4", "d5", "d6"),
            ),
            row_boundaries=(30.0, 55.0, 85.0),
        )
        ctx = _make_ctx(dict_blocks)

        pp = HeaderDetection()
        result = pp.process(grid, ctx)

        # Multi-row headers merged
        assert result.headers is not None
        assert len(result.rows) == 2
        assert result.rows[0] == ("d1", "d2", "d3")

    def test_no_font_difference(self) -> None:
        """All same font. Grid unchanged."""
        dict_blocks = _make_dict_blocks([
            {"y_center": 25.0, "size": 9.0, "bold": False, "text": "row0"},
            {"y_center": 75.0, "size": 9.0, "bold": False, "text": "row1"},
            {"y_center": 125.0, "size": 9.0, "bold": False, "text": "row2"},
        ])
        grid = _make_grid(
            rows=(
                ("a", "b", "c"),
                ("d", "e", "f"),
                ("g", "h", "i"),
            ),
            row_boundaries=(50.0, 100.0),
        )
        ctx = _make_ctx(dict_blocks)

        pp = HeaderDetection()
        result = pp.process(grid, ctx)

        assert result is grid  # Unchanged

    def test_protocol_conformance(self) -> None:
        """HeaderDetection satisfies PostProcessor protocol."""
        pp = HeaderDetection()
        assert isinstance(pp, PostProcessor)
        assert pp.name == "header_detection"
