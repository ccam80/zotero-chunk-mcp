"""Consolidated unit tests for paddle extraction: parsers, models, factory, and caption matching.

Test classes:
  TestImports            (3)  -- B1 Task 1.1: PaddleOCR import smoke tests
  TestRawPaddleTable     (1)  -- B1 Task 1.2: dataclass field presence and typing
  TestEngineFactory      (3)  -- B1 Task 1.2: factory dispatch and protocol conformance
  TestHTMLParser         (8)  -- B1 Task 2.1: _parse_html_table behaviour
  TestMarkdownParser     (7)  -- B1 Task 2.2: _parse_markdown_table behaviour
  TestMatchedPaddleTable (2)  -- B3 Task 1.1: MatchedPaddleTable dataclass
  TestCaptionMatching    (6)  -- B3 Task 1.2: match_tables_to_captions algorithm
  TestDebugDB            (2)  -- B4 Task 2.1: write_paddle_result and write_paddle_gt_diff
"""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

from zotero_chunk_rag.feature_extraction.captions import DetectedCaption
from zotero_chunk_rag.feature_extraction.debug_db import (
    write_paddle_gt_diff,
    write_paddle_result,
)
from zotero_chunk_rag.feature_extraction.paddle_extract import (
    MatchedPaddleTable,
    PaddleEngine,
    RawPaddleTable,
    get_engine,
    match_tables_to_captions,
)
from zotero_chunk_rag.feature_extraction.paddle_engines.pp_structure import (
    _parse_html_table,
)
from zotero_chunk_rag.feature_extraction.paddle_engines.paddleocr_vl import (
    _parse_markdown_table,
)


# ---------------------------------------------------------------------------
# Shared test helpers
# ---------------------------------------------------------------------------


def _raw(
    page_num: int,
    bbox: tuple[float, float, float, float],
    page_size: tuple[int, int] = (1000, 1000),
) -> RawPaddleTable:
    return RawPaddleTable(
        page_num=page_num,
        bbox=bbox,
        page_size=page_size,
        headers=["Col A", "Col B"],
        rows=[["1", "2"]],
        footnotes="",
        engine_name="test_engine",
        raw_output="<table/>",
    )


def _caption(
    y_center: float,
    text: str = "Table 1. Example caption.",
    number: str | None = "1",
    bbox: tuple[float, float, float, float] | None = None,
) -> DetectedCaption:
    if bbox is None:
        bbox = (0.0, y_center - 5.0, 100.0, y_center + 5.0)
    return DetectedCaption(
        text=text,
        bbox=bbox,
        y_center=y_center,
        caption_type="table",
        number=number,
    )


# ---------------------------------------------------------------------------
# TestImports — B1 Task 1.1
# ---------------------------------------------------------------------------


class TestImports:
    def test_paddleocr_importable(self) -> None:
        """import paddleocr must succeed without error."""
        import paddleocr  # noqa: F401

    def test_ppstructurev3_importable(self) -> None:
        """from paddleocr import PPStructureV3 must succeed."""
        from paddleocr import PPStructureV3  # noqa: F401

    def test_paddleocrvl_importable(self) -> None:
        """from paddleocr import PaddleOCRVL must succeed."""
        from paddleocr import PaddleOCRVL  # noqa: F401


# ---------------------------------------------------------------------------
# TestRawPaddleTable — B1 Task 1.2
# ---------------------------------------------------------------------------


class TestRawPaddleTable:
    def test_fields_present(self) -> None:
        """Construct RawPaddleTable with all fields; assert each accessible and correctly typed."""
        t = RawPaddleTable(
            page_num=3,
            bbox=(10.0, 20.0, 200.0, 300.0),
            page_size=(1240, 1754),
            headers=["Name", "Value"],
            rows=[["alpha", "1"], ["beta", "2"]],
            footnotes="Note: values are approximate.",
            engine_name="pp_structure_v3",
            raw_output="<table><tr><td>Name</td></tr></table>",
        )
        assert isinstance(t.page_num, int)
        assert t.page_num == 3
        assert isinstance(t.bbox, tuple)
        assert len(t.bbox) == 4
        assert t.bbox == (10.0, 20.0, 200.0, 300.0)
        assert isinstance(t.page_size, tuple)
        assert len(t.page_size) == 2
        assert t.page_size == (1240, 1754)
        assert isinstance(t.headers, list)
        assert t.headers == ["Name", "Value"]
        assert isinstance(t.rows, list)
        assert t.rows == [["alpha", "1"], ["beta", "2"]]
        assert isinstance(t.footnotes, str)
        assert t.footnotes == "Note: values are approximate."
        assert isinstance(t.engine_name, str)
        assert t.engine_name == "pp_structure_v3"
        assert isinstance(t.raw_output, str)
        assert "<table>" in t.raw_output


# ---------------------------------------------------------------------------
# TestEngineFactory — B1 Task 1.2
# ---------------------------------------------------------------------------


class TestEngineFactory:
    def test_pp_structure_v3(self) -> None:
        """get_engine('pp_structure_v3') returns an instance satisfying PaddleEngine protocol."""
        engine = get_engine("pp_structure_v3")
        assert isinstance(engine, PaddleEngine)
        assert hasattr(engine, "extract_tables")
        assert callable(engine.extract_tables)

    def test_paddleocr_vl(self) -> None:
        """get_engine('paddleocr_vl_1.5') returns an instance satisfying PaddleEngine protocol."""
        engine = get_engine("paddleocr_vl_1.5")
        assert isinstance(engine, PaddleEngine)
        assert hasattr(engine, "extract_tables")
        assert callable(engine.extract_tables)

    def test_unknown_raises(self) -> None:
        """get_engine('nonexistent') raises ValueError containing the invalid name."""
        with pytest.raises(ValueError, match="nonexistent"):
            get_engine("nonexistent")


# ---------------------------------------------------------------------------
# TestHTMLParser — B1 Task 2.1
# ---------------------------------------------------------------------------


class TestHTMLParser:
    def test_simple_table(self) -> None:
        """All-<td> table: first row becomes headers, second row becomes data."""
        html = (
            "<table>"
            "<tr><td>Name</td><td>Age</td></tr>"
            "<tr><td>Alice</td><td>30</td></tr>"
            "</table>"
        )
        headers, rows, footnotes = _parse_html_table(html)
        assert headers == ["Name", "Age"]
        assert rows == [["Alice", "30"]]

    def test_th_headers(self) -> None:
        """<th> tags mark header row; <td> rows are data."""
        html = (
            "<table>"
            "<tr><th>A</th><th>B</th></tr>"
            "<tr><td>1</td><td>2</td></tr>"
            "</table>"
        )
        headers, rows, _ = _parse_html_table(html)
        assert headers == ["A", "B"]
        assert rows == [["1", "2"]]

    def test_no_th_first_row_fallback(self) -> None:
        """When no <th> tags exist, first row is promoted to headers."""
        html = (
            "<table>"
            "<tr><td>Header1</td><td>Header2</td></tr>"
            "<tr><td>val1</td><td>val2</td></tr>"
            "<tr><td>val3</td><td>val4</td></tr>"
            "</table>"
        )
        headers, rows, _ = _parse_html_table(html)
        assert headers == ["Header1", "Header2"]
        assert rows == [["val1", "val2"], ["val3", "val4"]]

    def test_colspan(self) -> None:
        """colspan='3' repeats the cell value 3 times in that row."""
        html = (
            "<table>"
            "<tr><td colspan='3'>Merged</td></tr>"
            "</table>"
        )
        headers, rows, _ = _parse_html_table(html)
        assert headers == ["Merged", "Merged", "Merged"]

    def test_rowspan(self) -> None:
        """rowspan='2' copies the value into the next row at the same column."""
        html = (
            "<table>"
            "<tr><td rowspan='2'>Span</td><td>R1C2</td></tr>"
            "<tr><td>R2C2</td></tr>"
            "</table>"
        )
        headers, rows, _ = _parse_html_table(html)
        # First row promoted to headers: ["Span", "R1C2"]
        # Second row: the rowspan value "Span" fills col 0, "R2C2" fills col 1
        assert rows[0][0] == "Span"
        assert rows[0][1] == "R2C2"

    def test_nested_tags_stripped(self) -> None:
        """HTML tags inside cells are stripped; whitespace is normalized."""
        html = "<table><tr><td><b>Bold</b> text</td></tr></table>"
        headers, rows, _ = _parse_html_table(html)
        assert headers == ["Bold text"]

    def test_empty_table(self) -> None:
        """<table></table> returns ([], [], '')."""
        headers, rows, footnotes = _parse_html_table("<table></table>")
        assert headers == []
        assert rows == []
        assert footnotes == ""

    def test_whitespace_normalization(self) -> None:
        """Multiple internal spaces collapse to a single space."""
        html = "<table><tr><td>  multiple   spaces  </td></tr></table>"
        headers, rows, _ = _parse_html_table(html)
        assert headers == ["multiple spaces"]


# ---------------------------------------------------------------------------
# TestMarkdownParser — B1 Task 2.2
# ---------------------------------------------------------------------------


class TestMarkdownParser:
    def test_simple_table(self) -> None:
        """Standard markdown table: header row, separator, one data row."""
        md = "| A | B |\n|---|---|\n| 1 | 2 |"
        headers, rows, _ = _parse_markdown_table(md)
        assert headers == ["A", "B"]
        assert rows == [["1", "2"]]

    def test_alignment_stripped(self) -> None:
        """Alignment separator row (|:---|---:|) is not treated as data."""
        md = "| A | B |\n|:---|---:|\n| 1 | 2 |"
        headers, rows, _ = _parse_markdown_table(md)
        assert headers == ["A", "B"]
        assert rows == [["1", "2"]]

    def test_escaped_pipes(self) -> None:
        r"""Escaped pipes (\|) inside cells produce a literal pipe character."""
        md = "| A |\n|---|\n| val\\|ue |"
        headers, rows, _ = _parse_markdown_table(md)
        assert rows == [["val|ue"]]

    def test_whitespace_trimmed(self) -> None:
        """Leading and trailing whitespace is stripped per cell."""
        md = "|  A  |  B  |\n|---|---|\n|  1  |  2  |"
        headers, rows, _ = _parse_markdown_table(md)
        assert headers == ["A", "B"]
        assert rows == [["1", "2"]]

    def test_empty_string(self) -> None:
        """Empty string input returns ([], [], '')."""
        headers, rows, footnotes = _parse_markdown_table("")
        assert headers == []
        assert rows == []
        assert footnotes == ""

    def test_no_separator_row(self) -> None:
        """Table without a |---| separator: first row still treated as headers."""
        md = "| Col1 | Col2 |\n| data1 | data2 |"
        headers, rows, _ = _parse_markdown_table(md)
        assert headers == ["Col1", "Col2"]
        assert rows == [["data1", "data2"]]

    def test_multirow(self) -> None:
        """3 data rows → rows has length 3, each with correct cell count."""
        md = (
            "| X | Y | Z |\n"
            "|---|---|---|\n"
            "| a | b | c |\n"
            "| d | e | f |\n"
            "| g | h | i |"
        )
        headers, rows, _ = _parse_markdown_table(md)
        assert headers == ["X", "Y", "Z"]
        assert len(rows) == 3
        assert rows[0] == ["a", "b", "c"]
        assert rows[1] == ["d", "e", "f"]
        assert rows[2] == ["g", "h", "i"]


# ---------------------------------------------------------------------------
# TestMatchedPaddleTable — B3 Task 1.1
# ---------------------------------------------------------------------------


class TestMatchedPaddleTable:
    def test_fields(self) -> None:
        """Construct with all fields; assert caption and is_orphan are accessible."""
        t = MatchedPaddleTable(
            page_num=1,
            bbox=(10.0, 20.0, 200.0, 300.0),
            page_size=(1000, 1400),
            headers=["A", "B"],
            rows=[["x", "y"]],
            footnotes="note",
            engine_name="pp_structure_v3",
            raw_output="<html/>",
            caption="Table 1. Results.",
            caption_number="1",
            is_orphan=False,
        )
        assert t.page_num == 1
        assert t.bbox == (10.0, 20.0, 200.0, 300.0)
        assert t.page_size == (1000, 1400)
        assert t.headers == ["A", "B"]
        assert t.rows == [["x", "y"]]
        assert t.footnotes == "note"
        assert t.engine_name == "pp_structure_v3"
        assert t.raw_output == "<html/>"
        assert t.caption == "Table 1. Results."
        assert t.caption_number == "1"
        assert t.is_orphan is False

    def test_orphan_defaults(self) -> None:
        """Orphan table has caption=None, caption_number=None, is_orphan=True."""
        t = MatchedPaddleTable(
            page_num=2,
            bbox=(0.0, 0.0, 100.0, 100.0),
            page_size=(800, 1100),
            headers=[],
            rows=[],
            footnotes="",
            engine_name="engine",
            raw_output="",
            caption=None,
            caption_number=None,
            is_orphan=True,
        )
        assert t.caption is None
        assert t.caption_number is None
        assert t.is_orphan is True


# ---------------------------------------------------------------------------
# TestCaptionMatching — B3 Task 1.2
# ---------------------------------------------------------------------------


class TestCaptionMatching:
    def test_single_match(self) -> None:
        """One table at pixel y=400 on 1000px page; caption at PDF y=28.8 on 72pt page.

        Both normalize to ~0.4, caption is above table → matched.
        """
        table = _raw(page_num=1, bbox=(0.0, 400.0, 500.0, 700.0), page_size=(1000, 1000))

        cap = _caption(y_center=28.8)
        captions_by_page = {1: [cap]}
        page_rects = {1: (0.0, 0.0, 500.0, 72.0)}

        result = match_tables_to_captions([table], captions_by_page, page_rects)

        assert len(result) == 1
        assert result[0].is_orphan is False
        assert result[0].caption == cap.text
        assert result[0].caption_number == cap.number

    def test_multiple_tables(self) -> None:
        """3 tables at pixel y=200, 500, 800; 3 captions at proportional PDF positions.

        Correct 1:1 assignment: each table gets nearest-above caption.
        """
        page_size = (1000, 1000)
        tables = [
            _raw(1, (0.0, 200.0, 500.0, 350.0), page_size),  # y0_norm = 0.2
            _raw(1, (0.0, 500.0, 500.0, 650.0), page_size),  # y0_norm = 0.5
            _raw(1, (0.0, 800.0, 500.0, 950.0), page_size),  # y0_norm = 0.8
        ]

        cap1 = _caption(y_center=15.0, text="Table 1. First.", number="1")   # norm 0.15 < 0.2
        cap2 = _caption(y_center=45.0, text="Table 2. Second.", number="2")  # norm 0.45 < 0.5
        cap3 = _caption(y_center=75.0, text="Table 3. Third.", number="3")   # norm 0.75 < 0.8

        captions_by_page = {1: [cap1, cap2, cap3]}
        page_rects = {1: (0.0, 0.0, 500.0, 100.0)}

        result = match_tables_to_captions(tables, captions_by_page, page_rects)

        assert len(result) == 3
        assert result[0].caption_number == "1"
        assert result[1].caption_number == "2"
        assert result[2].caption_number == "3"
        assert all(not r.is_orphan for r in result)

    def test_orphan(self) -> None:
        """Table at pixel y=100 with caption below at y=900 → is_orphan=True."""
        page_size = (1000, 1000)
        table = _raw(1, (0.0, 100.0, 500.0, 300.0), page_size)  # y0_norm = 0.1

        cap = _caption(y_center=90.0, text="Table 1. Below.", number="1")
        captions_by_page = {1: [cap]}
        page_rects = {1: (0.0, 0.0, 500.0, 100.0)}

        result = match_tables_to_captions([table], captions_by_page, page_rects)

        assert len(result) == 1
        assert result[0].is_orphan is True
        assert result[0].caption is None
        assert result[0].caption_number is None

    def test_no_double_match(self) -> None:
        """2 tables close together, 1 caption → first table gets caption, second is orphan."""
        page_size = (1000, 1000)
        table1 = _raw(1, (0.0, 400.0, 500.0, 450.0), page_size)  # y0_norm = 0.4
        table2 = _raw(1, (0.0, 500.0, 500.0, 550.0), page_size)  # y0_norm = 0.5

        cap = _caption(y_center=35.0, text="Table 1. Only caption.", number="1")
        captions_by_page = {1: [cap]}
        page_rects = {1: (0.0, 0.0, 500.0, 100.0)}

        result = match_tables_to_captions([table1, table2], captions_by_page, page_rects)

        assert len(result) == 2
        assert result[0].is_orphan is False
        assert result[0].caption_number == "1"
        assert result[1].is_orphan is True
        assert result[1].caption is None

    def test_multi_page(self) -> None:
        """Tables on pages 1 and 3; captions on pages 1 and 3 → per-page, no cross-page matching."""
        page_size = (1000, 1000)
        table_p1 = _raw(1, (0.0, 400.0, 500.0, 600.0), page_size)
        table_p3 = _raw(3, (0.0, 400.0, 500.0, 600.0), page_size)

        cap_p1 = _caption(y_center=30.0, text="Table 1. Page one.", number="1")
        cap_p3 = _caption(y_center=30.0, text="Table 2. Page three.", number="2")

        captions_by_page = {1: [cap_p1], 3: [cap_p3]}
        page_rects = {
            1: (0.0, 0.0, 500.0, 100.0),
            3: (0.0, 0.0, 500.0, 100.0),
        }

        result = match_tables_to_captions([table_p1, table_p3], captions_by_page, page_rects)

        assert len(result) == 2
        p1_result = next(r for r in result if r.page_num == 1)
        assert p1_result.caption_number == "1"
        assert p1_result.is_orphan is False
        p3_result = next(r for r in result if r.page_num == 3)
        assert p3_result.caption_number == "2"
        assert p3_result.is_orphan is False

    def test_empty_inputs(self) -> None:
        """Empty raw_tables → empty result. Tables with no captions on their page → all orphans."""
        result = match_tables_to_captions([], {}, {})
        assert result == []

        page_size = (1000, 1000)
        table = _raw(2, (0.0, 400.0, 500.0, 600.0), page_size)
        cap_p1 = _caption(y_center=30.0, text="Table 1. Wrong page.", number="1")

        result = match_tables_to_captions(
            [table],
            {1: [cap_p1]},
            {1: (0.0, 0.0, 500.0, 100.0), 2: (0.0, 0.0, 500.0, 100.0)},
        )
        assert len(result) == 1
        assert result[0].is_orphan is True
        assert result[0].caption is None


# ---------------------------------------------------------------------------
# TestDebugDB (2 tests) — B4 Task 2.1
# ---------------------------------------------------------------------------


class TestDebugDB:
    """Verify write_paddle_result and write_paddle_gt_diff round-trip correctly."""

    def test_write_paddle_result(self, tmp_path: Path) -> None:
        from zotero_chunk_rag.feature_extraction.debug_db import write_paddle_result

        db_path = str(tmp_path / "test.db")
        row = {
            "table_id": "ABC123_table_1",
            "page_num": 3,
            "engine_name": "pp_structure_v3",
            "caption": "Table 1. Results.",
            "is_orphan": False,
            "headers_json": json.dumps(["A", "B"]),
            "rows_json": json.dumps([["1", "2"]]),
            "bbox": json.dumps([10.0, 20.0, 300.0, 400.0]),
            "page_size": json.dumps([612, 792]),
            "raw_output": "<table><tr><td>1</td></tr></table>",
            "item_key": "ABC123",
        }
        write_paddle_result(db_path, row)

        with sqlite3.connect(db_path) as con:
            cur = con.execute(
                "SELECT * FROM paddle_results WHERE table_id = ?",
                (row["table_id"],),
            )
            cols = [d[0] for d in cur.description]
            result = dict(zip(cols, cur.fetchone()))

        assert result["table_id"] == "ABC123_table_1"
        assert result["page_num"] == 3
        assert result["engine_name"] == "pp_structure_v3"
        assert result["caption"] == "Table 1. Results."
        assert result["is_orphan"] == 0
        assert result["headers_json"] == json.dumps(["A", "B"])
        assert result["rows_json"] == json.dumps([["1", "2"]])
        assert result["item_key"] == "ABC123"

    def test_write_paddle_gt_diff(self, tmp_path: Path) -> None:
        from zotero_chunk_rag.feature_extraction.debug_db import write_paddle_gt_diff

        db_path = str(tmp_path / "test.db")
        row = {
            "table_id": "XYZ789_table_2",
            "engine_name": "paddleocr_vl_1.5",
            "cell_accuracy_pct": 87.5,
            "fuzzy_accuracy_pct": 92.0,
            "num_splits": 1,
            "num_merges": 0,
            "num_cell_diffs": 3,
            "gt_shape": "(5, 4)",
            "ext_shape": "(5, 4)",
            "diff_json": json.dumps({"cell_accuracy_pct": 87.5}),
        }
        write_paddle_gt_diff(db_path, row)

        with sqlite3.connect(db_path) as con:
            cur = con.execute(
                "SELECT * FROM paddle_gt_diffs WHERE table_id = ?",
                (row["table_id"],),
            )
            cols = [d[0] for d in cur.description]
            result = dict(zip(cols, cur.fetchone()))

        assert result["table_id"] == "XYZ789_table_2"
        assert result["engine_name"] == "paddleocr_vl_1.5"
        assert result["cell_accuracy_pct"] == 87.5
        assert result["num_splits"] == 1
        assert result["num_merges"] == 0
        assert result["num_cell_diffs"] == 3
