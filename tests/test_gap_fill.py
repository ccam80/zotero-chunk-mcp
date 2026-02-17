"""Unit tests for the _gap_fill recovery module.

WARNING: These are mock-based plumbing tests only. They verify that the
recovery logic correctly processes synthetic inputs (matching, distance
rejection, greedy assignment). They do NOT verify that the module actually
recovers captions from real PDFs. As of 2026-02-11, the gap-fill module
recovered zero captions in the 10-paper stress test. Real-paper validation
must come from the stress test, not from these mocks.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from zotero_chunk_rag.models import ExtractedFigure, ExtractedTable


def _make_figure(page_num, fig_idx, caption=None, y0=100, y1=300):
    return ExtractedFigure(
        page_num=page_num,
        figure_index=fig_idx,
        bbox=(50, y0, 500, y1),
        caption=caption,
    )


def _make_table(page_num, tab_idx, caption=None, y0=100, y1=300):
    return ExtractedTable(
        page_num=page_num,
        table_index=tab_idx,
        bbox=(50, y0, 500, y1),
        headers=["A", "B"],
        rows=[["1", "2"]],
        caption=caption,
    )


class TestRunRecoveryNoop:
    """Recovery should be a no-op when there are no orphans."""

    def test_no_orphans_no_change(self):
        """All figures have captions → nothing recovered."""
        from zotero_chunk_rag._gap_fill import run_recovery

        figures = [
            _make_figure(1, 0, caption="Figure 1. First"),
            _make_figure(2, 1, caption="Figure 2. Second"),
        ]
        tables = [
            _make_table(1, 0, caption="Table 1. Data"),
        ]

        mock_page = MagicMock()
        mock_page.rect.height = 792.0
        doc = MagicMock()
        doc.__len__ = MagicMock(return_value=3)
        doc.__getitem__ = MagicMock(return_value=mock_page)
        doc.__iter__ = MagicMock(return_value=iter([mock_page, mock_page, mock_page]))

        with patch("zotero_chunk_rag._gap_fill.run_recovery", wraps=run_recovery):
            result_figs, result_tabs = run_recovery(
                doc, figures, tables, [],
            )

        assert result_figs[0].caption == "Figure 1. First"
        assert result_figs[1].caption == "Figure 2. Second"
        assert result_tabs[0].caption == "Table 1. Data"

    def test_empty_lists(self):
        """Empty inputs → empty outputs, no crash."""
        from zotero_chunk_rag._gap_fill import run_recovery

        mock_page = MagicMock()
        mock_page.rect.height = 792.0
        doc = MagicMock()
        doc.__len__ = MagicMock(return_value=1)
        doc.__getitem__ = MagicMock(return_value=mock_page)
        doc.__iter__ = MagicMock(return_value=iter([mock_page]))

        result_figs, result_tabs = run_recovery(doc, [], [], [])
        assert result_figs == []
        assert result_tabs == []


class TestYProximityMatching:
    """Test orphan ↔ floating caption matching by y-distance."""

    def test_orphan_matched_to_floating_caption(self):
        """Orphan figure on same page as floating caption → matched."""
        from zotero_chunk_rag._gap_fill import _recover_captions

        figures = [
            _make_figure(1, 0, caption="Figure 1. First"),
            _make_figure(1, 1, caption=None, y0=400, y1=600),  # orphan
        ]

        # Mock caption finder: returns Fig 1 (assigned) and Fig 2 (floating)
        def mock_finder(page, strict_re, *, relaxed_re=None, label_only_re=None):
            return [
                (200.0, "Figure 1. First", (50, 180, 500, 220)),
                (620.0, "Figure 2. Second figure", (50, 610, 500, 630)),
            ]

        import re
        strict_re = re.compile(r"^(?:Figure|Fig\.?)\s+(\d+)\s*[.:()\u2014\u2013-]", re.IGNORECASE)
        relaxed_re = re.compile(r"^(?:Figure|Fig\.?)\s+(\d+)\s+\S", re.IGNORECASE)
        label_only_re = re.compile(r"^(?:Figure|Fig\.?)\s+(\d+)\s*$", re.IGNORECASE)
        ref_re = re.compile(r"(?:Figure|Fig\.?)\s+(\d+)\s*[.:()\u2014\u2013-]", re.IGNORECASE)

        doc = MagicMock()
        doc.__len__ = MagicMock(return_value=1)
        mock_page = MagicMock()
        doc.__iter__ = MagicMock(return_value=iter([mock_page]))
        doc.__getitem__ = MagicMock(return_value=mock_page)

        count = _recover_captions(
            doc, figures, mock_finder,
            strict_re, relaxed_re, label_only_re, ref_re,
            kind="figure",
            max_y_distance=120.0,
        )

        assert count == 1
        assert figures[1].caption == "Figure 2. Second figure"

    def test_orphan_too_far_not_matched(self):
        """Floating caption > 120pts away → not matched."""
        from zotero_chunk_rag._gap_fill import _recover_captions

        figures = [
            _make_figure(1, 0, caption=None, y0=50, y1=100),  # orphan at top
        ]

        # Caption is far below the orphan (y_center=500, orphan_bottom=100 → dist=400)
        def mock_finder(page, strict_re, *, relaxed_re=None, label_only_re=None):
            return [
                (500.0, "Figure 1. Far away", (50, 490, 500, 510)),
            ]

        import re
        strict_re = re.compile(r"^(?:Figure|Fig\.?)\s+(\d+)\s*[.:()\u2014\u2013-]", re.IGNORECASE)
        relaxed_re = re.compile(r"^(?:Figure|Fig\.?)\s+(\d+)\s+\S", re.IGNORECASE)
        label_only_re = re.compile(r"^(?:Figure|Fig\.?)\s+(\d+)\s*$", re.IGNORECASE)
        ref_re = re.compile(r"(?:Figure|Fig\.?)\s+(\d+)\s*[.:()\u2014\u2013-]", re.IGNORECASE)

        doc = MagicMock()
        doc.__len__ = MagicMock(return_value=1)
        mock_page = MagicMock()
        doc.__iter__ = MagicMock(return_value=iter([mock_page]))

        count = _recover_captions(
            doc, figures, mock_finder,
            strict_re, relaxed_re, label_only_re, ref_re,
            kind="figure",
            max_y_distance=120.0,
        )

        assert count == 0
        assert figures[0].caption is None

    def test_different_page_not_matched(self):
        """Floating caption on different page → not matched."""
        from zotero_chunk_rag._gap_fill import _recover_captions

        figures = [
            _make_figure(1, 0, caption=None, y0=400, y1=600),  # orphan on p1
        ]

        # Caption on page 2 only
        def mock_finder(page, strict_re, *, relaxed_re=None, label_only_re=None):
            # page_num_0 is tracked via the iter; we return different results per page
            if not hasattr(mock_finder, '_call_count'):
                mock_finder._call_count = 0
            mock_finder._call_count += 1
            if mock_finder._call_count == 2:  # page 2
                return [(620.0, "Figure 1. On page 2", (50, 610, 500, 630))]
            return []

        import re
        strict_re = re.compile(r"^(?:Figure|Fig\.?)\s+(\d+)\s*[.:()\u2014\u2013-]", re.IGNORECASE)
        relaxed_re = re.compile(r"^(?:Figure|Fig\.?)\s+(\d+)\s+\S", re.IGNORECASE)
        label_only_re = re.compile(r"^(?:Figure|Fig\.?)\s+(\d+)\s*$", re.IGNORECASE)
        ref_re = re.compile(r"(?:Figure|Fig\.?)\s+(\d+)\s*[.:()\u2014\u2013-]", re.IGNORECASE)

        doc = MagicMock()
        doc.__len__ = MagicMock(return_value=2)
        pages = [MagicMock(), MagicMock()]
        doc.__iter__ = MagicMock(return_value=iter(pages))

        mock_finder._call_count = 0  # reset
        count = _recover_captions(
            doc, figures, mock_finder,
            strict_re, relaxed_re, label_only_re, ref_re,
            kind="figure",
            max_y_distance=120.0,
        )

        assert count == 0
        assert figures[0].caption is None


class TestMultiOrphanGreedyAssignment:
    """Test that multiple orphans on the same page get greedy top-to-bottom assignment."""

    def test_two_orphans_two_floating(self):
        """Two orphans and two floating captions → both matched correctly."""
        from zotero_chunk_rag._gap_fill import _recover_captions

        figures = [
            _make_figure(1, 0, caption=None, y0=50, y1=200),   # orphan top
            _make_figure(1, 1, caption=None, y0=400, y1=550),   # orphan bottom
        ]

        def mock_finder(page, strict_re, *, relaxed_re=None, label_only_re=None):
            return [
                (220.0, "Figure 1. Top fig", (50, 210, 500, 230)),
                (570.0, "Figure 2. Bottom fig", (50, 560, 500, 580)),
            ]

        import re
        strict_re = re.compile(r"^(?:Figure|Fig\.?)\s+(\d+)\s*[.:()\u2014\u2013-]", re.IGNORECASE)
        relaxed_re = re.compile(r"^(?:Figure|Fig\.?)\s+(\d+)\s+\S", re.IGNORECASE)
        label_only_re = re.compile(r"^(?:Figure|Fig\.?)\s+(\d+)\s*$", re.IGNORECASE)
        ref_re = re.compile(r"(?:Figure|Fig\.?)\s+(\d+)\s*[.:()\u2014\u2013-]", re.IGNORECASE)

        doc = MagicMock()
        doc.__len__ = MagicMock(return_value=1)
        mock_page = MagicMock()
        doc.__iter__ = MagicMock(return_value=iter([mock_page]))

        count = _recover_captions(
            doc, figures, mock_finder,
            strict_re, relaxed_re, label_only_re, ref_re,
            kind="figure",
            max_y_distance=120.0,
        )

        assert count == 2
        assert figures[0].caption == "Figure 1. Top fig"
        assert figures[1].caption == "Figure 2. Bottom fig"


class TestTableRecovery:
    """Test that recovery works for tables too."""

    def test_orphan_table_matched(self):
        """Orphan table matched to floating table caption."""
        from zotero_chunk_rag._gap_fill import _recover_captions

        tables = [
            _make_table(1, 0, caption="Table 1. First"),
            _make_table(1, 1, caption=None, y0=400, y1=600),  # orphan
        ]

        def mock_finder(page, strict_re, *, relaxed_re=None, label_only_re=None):
            return [
                (200.0, "Table 1. First", (50, 180, 500, 220)),
                (620.0, "Table 2. Second table", (50, 610, 500, 630)),
            ]

        import re
        strict_re = re.compile(r"^(?:Table|Tab\.)\s+(\d+)\s*[.:()\u2014\u2013-]", re.IGNORECASE)
        relaxed_re = re.compile(r"^(?:Table|Tab\.)\s+(\d+)\s+\S", re.IGNORECASE)
        label_only_re = re.compile(r"^(?:Table|Tab\.?)\s+(\d+)\s*$", re.IGNORECASE)
        ref_re = re.compile(r"(?:Table|Tab\.)\s+(\d+)\s*[.:()\u2014\u2013-]", re.IGNORECASE)

        doc = MagicMock()
        doc.__len__ = MagicMock(return_value=1)
        mock_page = MagicMock()
        doc.__iter__ = MagicMock(return_value=iter([mock_page]))

        count = _recover_captions(
            doc, tables, mock_finder,
            strict_re, relaxed_re, label_only_re, ref_re,
            kind="table",
            max_y_distance=120.0,
        )

        assert count == 1
        assert tables[1].caption == "Table 2. Second table"



class TestNoFalsePositives:
    """Verify recovery doesn't match already-assigned captions or body references."""

    def test_assigned_caption_not_rematched(self):
        """A caption already assigned to a figure should not be matched again."""
        from zotero_chunk_rag._gap_fill import _recover_captions

        figures = [
            _make_figure(1, 0, caption="Figure 1. Already assigned"),
            _make_figure(1, 1, caption=None, y0=400, y1=600),  # orphan
        ]

        # Only Fig 1 caption on page — already assigned, nothing floating
        def mock_finder(page, strict_re, *, relaxed_re=None, label_only_re=None):
            return [
                (200.0, "Figure 1. Already assigned", (50, 180, 500, 220)),
            ]

        import re
        strict_re = re.compile(r"^(?:Figure|Fig\.?)\s+(\d+)\s*[.:()\u2014\u2013-]", re.IGNORECASE)
        relaxed_re = re.compile(r"^(?:Figure|Fig\.?)\s+(\d+)\s+\S", re.IGNORECASE)
        label_only_re = re.compile(r"^(?:Figure|Fig\.?)\s+(\d+)\s*$", re.IGNORECASE)
        ref_re = re.compile(r"(?:Figure|Fig\.?)\s+(\d+)\s*[.:()\u2014\u2013-]", re.IGNORECASE)

        doc = MagicMock()
        doc.__len__ = MagicMock(return_value=1)
        mock_page = MagicMock()
        doc.__iter__ = MagicMock(return_value=iter([mock_page]))

        count = _recover_captions(
            doc, figures, mock_finder,
            strict_re, relaxed_re, label_only_re, ref_re,
            kind="figure",
            max_y_distance=120.0,
        )

        assert count == 0
        assert figures[1].caption is None  # still orphan — no floating caption to match
