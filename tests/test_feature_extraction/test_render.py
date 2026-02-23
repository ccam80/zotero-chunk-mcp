"""Tests for table image rendering."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from zotero_chunk_rag.feature_extraction.render import render_table_image

FIXTURE_PDF = Path(__file__).resolve().parents[1] / "fixtures" / "papers" / "noname1.pdf"

# A reasonable bbox covering the upper portion of page 7 (which contains Table 1)
_SAMPLE_BBOX = (50.0, 50.0, 550.0, 400.0)


class TestRender:
    def test_renders_png(self, tmp_path: Path) -> None:
        out = tmp_path / "table.png"
        result = render_table_image(FIXTURE_PDF, 7, _SAMPLE_BBOX, out)
        assert result == out
        assert out.exists()
        with open(out, "rb") as f:
            header = f.read(4)
        assert header == b"\x89PNG"

    def test_output_dimensions(self, tmp_path: Path) -> None:
        out = tmp_path / "table.png"
        render_table_image(FIXTURE_PDF, 7, _SAMPLE_BBOX, out)
        assert out.stat().st_size > 0

    def test_padding_expands_region(self, tmp_path: Path) -> None:
        out_no_pad = tmp_path / "no_pad.png"
        out_padded = tmp_path / "padded.png"
        render_table_image(FIXTURE_PDF, 7, _SAMPLE_BBOX, out_no_pad, padding=0)
        render_table_image(FIXTURE_PDF, 7, _SAMPLE_BBOX, out_padded, padding=40)
        assert out_padded.stat().st_size > out_no_pad.stat().st_size

    def test_clips_to_page(self, tmp_path: Path) -> None:
        out = tmp_path / "clipped.png"
        bbox_beyond = (-50.0, -50.0, 550.0, 400.0)
        render_table_image(FIXTURE_PDF, 7, bbox_beyond, out)
        assert out.exists()
        with open(out, "rb") as f:
            header = f.read(4)
        assert header == b"\x89PNG"

    def test_page_num_one_indexed(self, tmp_path: Path) -> None:
        out = tmp_path / "page1.png"
        render_table_image(FIXTURE_PDF, 1, (0.0, 0.0, 200.0, 200.0), out)
        assert out.exists()
        with open(out, "rb") as f:
            header = f.read(4)
        assert header == b"\x89PNG"
