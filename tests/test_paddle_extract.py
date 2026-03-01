"""Tests for paddle_extract.py: MatchedPaddleTable dataclass and match_tables_to_captions()."""

from __future__ import annotations

import pytest

from src.zotero_chunk_rag.feature_extraction.captions import DetectedCaption
from src.zotero_chunk_rag.feature_extraction.paddle_extract import (
    MatchedPaddleTable,
    RawPaddleTable,
    match_tables_to_captions,
)


# ---------------------------------------------------------------------------
# Helpers
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
# TestMatchedPaddleTable
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
# TestCaptionMatching
# ---------------------------------------------------------------------------


class TestCaptionMatching:
    def test_single_match(self) -> None:
        """One table at pixel y=400 on 1000px page; caption at PDF y=28.8 on 72pt page.

        Both normalize to ~0.4, caption is above table → matched.
        """
        # Page size: 1000 x 1000 pixels. Table top edge at pixel y=400 → y_norm = 0.4.
        table = _raw(page_num=1, bbox=(0.0, 400.0, 500.0, 700.0), page_size=(1000, 1000))

        # PDF page rect: y0=0, y1=72pt. Caption y_center=28.8pt → y_norm = 28.8/72 = 0.4.
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

        # PDF page rect: y0=0, y1=100pt. Caption y_center values in points.
        # y_norm = y_center / 100. We want each caption just above its table.
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

        # Caption at PDF y_center=90.0 on 100pt page → norm 0.9 > 0.1 (below table)
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
        # Table 1 at y=400, Table 2 at y=500
        table1 = _raw(1, (0.0, 400.0, 500.0, 450.0), page_size)  # y0_norm = 0.4
        table2 = _raw(1, (0.0, 500.0, 500.0, 550.0), page_size)  # y0_norm = 0.5

        # Single caption at PDF y_center=35.0 on 100pt page → norm 0.35 < 0.4 (above both)
        cap = _caption(y_center=35.0, text="Table 1. Only caption.", number="1")
        captions_by_page = {1: [cap]}
        page_rects = {1: (0.0, 0.0, 500.0, 100.0)}

        result = match_tables_to_captions([table1, table2], captions_by_page, page_rects)

        assert len(result) == 2
        # First table (lower y_norm) gets the caption
        assert result[0].is_orphan is False
        assert result[0].caption_number == "1"
        # Second table is orphaned
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
        # Table from page 1 gets page-1 caption
        p1_result = next(r for r in result if r.page_num == 1)
        assert p1_result.caption_number == "1"
        assert p1_result.is_orphan is False
        # Table from page 3 gets page-3 caption
        p3_result = next(r for r in result if r.page_num == 3)
        assert p3_result.caption_number == "2"
        assert p3_result.is_orphan is False

    def test_empty_inputs(self) -> None:
        """Empty raw_tables → empty result. Tables with no captions → all orphans."""
        # Empty input
        result = match_tables_to_captions([], {}, {})
        assert result == []

        # Tables on page 2 but no captions defined for page 2
        page_size = (1000, 1000)
        table = _raw(2, (0.0, 400.0, 500.0, 600.0), page_size)
        cap_p1 = _caption(y_center=30.0, text="Table 1. Wrong page.", number="1")

        result = match_tables_to_captions(
            [table],
            {1: [cap_p1]},  # caption on page 1, not page 2
            {1: (0.0, 0.0, 500.0, 100.0), 2: (0.0, 0.0, 500.0, 100.0)},
        )
        assert len(result) == 1
        assert result[0].is_orphan is True
        assert result[0].caption is None
