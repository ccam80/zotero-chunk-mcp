"""
Stress-test debug database viewer.

Usage:
    python tools/debug_viewer.py [path_to_db]

If no path given, defaults to _stress_test_debug.db in the project root.
"""

from __future__ import annotations

import difflib
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap, QFont, QColor, QIcon, QPainter, QPen, QImage
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QScrollArea,
    QStatusBar,
    QComboBox,
)

DB_DEFAULT = Path(__file__).resolve().parent.parent / "_stress_test_debug.db"
PROJECT_ROOT = Path(__file__).resolve().parent.parent

GRADE_COLOURS = {
    "A": "#4caf50",
    "B": "#8bc34a",
    "C": "#ffc107",
    "D": "#ff9800",
    "F": "#f44336",
}


# ── helpers ──────────────────────────────────────────────────────────────────


def _conn(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _truncate(text: str, length: int = 80) -> str:
    if not text:
        return ""
    text = text.replace("\n", " ").strip()
    return text[:length] + "..." if len(text) > length else text


def _table_has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    """Check whether *column* exists in *table* via PRAGMA."""
    cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    return column in cols


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    """Check whether *table* exists in the database."""
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def _populate_table_widget(
    widget: QTableWidget,
    headers: list[str],
    rows: list[list[str]],
    cell_marks: dict[tuple[int, int], bool] | None = None,
) -> None:
    """Fill a QTableWidget from headers + rows.

    *cell_marks* maps ``(row, col)`` to ``True`` (match) or ``False``
    (mismatch).  Matched cells get a green tick prefix, mismatched cells
    get a red cross prefix with red text.  Unmarked cells are left plain.
    """
    widget.clear()
    n_cols = len(headers) if headers else (len(rows[0]) if rows else 0)
    widget.setColumnCount(n_cols)
    widget.setRowCount(len(rows))
    if headers:
        widget.setHorizontalHeaderLabels(headers)
    for r_idx, row in enumerate(rows):
        for c_idx, cell in enumerate(row):
            text = str(cell)
            if cell_marks and (r_idx, c_idx) in cell_marks:
                if cell_marks[(r_idx, c_idx)]:
                    text = "\u2713 " + text  # tick
                else:
                    text = "\u2717 " + text  # cross
            item = QTableWidgetItem(text)
            if cell_marks and (r_idx, c_idx) in cell_marks:
                if not cell_marks[(r_idx, c_idx)]:
                    item.setForeground(QColor("#c62828"))  # dark red text
            widget.setItem(r_idx, c_idx, item)
    widget.resizeColumnsToContents()


# ── char-level diff helpers (ported from vision_viewer) ──────────────────────

_DASH_CHARS = "\u2212\u2013\u2014\u2010\u2011\ufe63\uff0d"

_LIGATURE_MAP = {
    "\ufb00": "ff", "\ufb01": "fi", "\ufb02": "fl",
    "\ufb03": "ffi", "\ufb04": "ffl",
}

_SUPER_SUB_MAP = str.maketrans({
    "\u00b2": "2", "\u00b3": "3", "\u00b9": "1",
    "\u2070": "0", "\u2074": "4", "\u2075": "5", "\u2076": "6",
    "\u2077": "7", "\u2078": "8", "\u2079": "9",
    "\u207a": "+", "\u207b": "-", "\u207c": "=", "\u207d": "(", "\u207e": ")",
    "\u207f": "n", "\u1d40": "T", "\u1d48": "d", "\u1d49": "e", "\u2071": "i",
    "\u2080": "0", "\u2081": "1", "\u2082": "2", "\u2083": "3", "\u2084": "4",
    "\u2085": "5", "\u2086": "6", "\u2087": "7", "\u2088": "8", "\u2089": "9",
    "\u208a": "+", "\u208b": "-", "\u208c": "=", "\u208d": "(", "\u208e": ")",
    "\u2090": "a", "\u2091": "e", "\u2092": "o", "\u2093": "x",
    "\u2095": "h", "\u2096": "k", "\u2097": "l", "\u2098": "m",
    "\u2099": "n", "\u209a": "p", "\u209b": "s", "\u209c": "t", "\u1d0b": "K",
})

_LATEX_SUPER_RE = re.compile(r"\^{([^}]*)}")
_LATEX_SUB_RE = re.compile(r"_{([^}]*)}")


def _normalize_cell(text: str) -> str:
    """Normalize a cell for comparison (mirrors ground_truth._normalize_cell)."""
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    for ch in _DASH_CHARS:
        text = text.replace(ch, "-")
    for lig, repl in _LIGATURE_MAP.items():
        text = text.replace(lig, repl)
    text = _LATEX_SUPER_RE.sub(r"\1", text)
    text = _LATEX_SUB_RE.sub(r"\1", text)
    text = text.translate(_SUPER_SUB_MAP)
    return text


def _escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace(" ", "&nbsp;")


def _build_norm_index_map(original: str, normalized: str) -> list[int]:
    """Map normalized string indices back to original string positions."""
    n_map: list[int] = []
    oi = 0
    for ni in range(len(normalized)):
        while oi < len(original) and _normalize_cell(original[oi]) == "" and original[oi].strip() == "":
            oi += 1
        n_map.append(oi)
        if oi < len(original):
            oi += 1
    n_map.append(len(original))
    return n_map


def _char_diff_html(agent_text: str, gt_text: str) -> str:
    """Return HTML with character-level diff highlighting.

    - Equal text: plain black
    - Insertions (only in agent): green background
    - Deletions (only in GT): red strikethrough
    - Replacements: red strikethrough + green insertion
    """
    norm_agent = _normalize_cell(agent_text)
    norm_gt = _normalize_cell(gt_text)
    if norm_agent == norm_gt:
        return _escape_html(agent_text)

    a_map = _build_norm_index_map(agent_text, norm_agent)
    g_map = _build_norm_index_map(gt_text, norm_gt)

    sm = difflib.SequenceMatcher(None, norm_gt, norm_agent)
    parts: list[str] = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            orig_slice = agent_text[a_map[j1]:a_map[j2]]
            parts.append(_escape_html(orig_slice))
        elif op == "insert":
            orig_slice = agent_text[a_map[j1]:a_map[j2]]
            parts.append(
                f'<span style="background:#a5d6a7;">{_escape_html(orig_slice)}</span>'
            )
        elif op == "delete":
            orig_slice = gt_text[g_map[i1]:g_map[i2]]
            parts.append(
                f'<span style="background:#ef9a9a;text-decoration:line-through;">'
                f'{_escape_html(orig_slice)}</span>'
            )
        elif op == "replace":
            gt_slice = gt_text[g_map[i1]:g_map[i2]]
            ag_slice = agent_text[a_map[j1]:a_map[j2]]
            parts.append(
                f'<span style="background:#ef9a9a;text-decoration:line-through;">'
                f'{_escape_html(gt_slice)}</span>'
            )
            parts.append(
                f'<span style="background:#a5d6a7;">{_escape_html(ag_slice)}</span>'
            )
    return "".join(parts)


def _populate_diff_table(
    widget: QTableWidget,
    headers: list[str],
    rows: list[list[str]],
    ref_headers: list[str] | None = None,
    ref_rows: list[list[str]] | None = None,
) -> None:
    """Fill a QTableWidget with char-level diff highlighting against a reference.

    When ref_headers/ref_rows are None, falls back to plain display (no diff).
    """
    widget.clear()
    n_cols = len(headers) if headers else (len(rows[0]) if rows else 0)
    total_rows = 1 + len(rows)

    if n_cols == 0 and len(rows) == 0:
        widget.setRowCount(1)
        widget.setColumnCount(1)
        widget.setHorizontalHeaderLabels([""])
        item = QTableWidgetItem("No data")
        item.setForeground(QColor("#888888"))
        widget.setItem(0, 0, item)
        return

    widget.setColumnCount(n_cols)
    widget.setRowCount(total_rows)
    widget.setHorizontalHeaderLabels([str(i) for i in range(n_cols)])

    has_ref = ref_headers is not None and ref_rows is not None

    # Row 0: headers
    for c, h in enumerate(headers):
        h_str = str(h)
        ref_h = str(ref_headers[c]).strip() if has_ref and c < len(ref_headers) else None
        item = QTableWidgetItem()
        font = item.font()
        font.setBold(True)
        item.setFont(font)
        item.setBackground(QColor("#e0e0e0"))
        if has_ref and ref_h is not None and _normalize_cell(h_str) != _normalize_cell(ref_h):
            item.setBackground(QColor("#ffcdd2"))
        item.setText(h_str)
        widget.setItem(0, c, item)

    # Data rows
    for r_idx, row in enumerate(rows):
        ref_row = ref_rows[r_idx] if has_ref and r_idx < len(ref_rows) else None
        for c_idx, cell in enumerate(row):
            if c_idx >= n_cols:
                continue
            cell_str = str(cell)
            ref_cell = (
                str(ref_row[c_idx]).strip()
                if ref_row is not None and c_idx < len(ref_row)
                else None
            )
            if has_ref and ref_cell is not None and _normalize_cell(cell_str) != _normalize_cell(ref_cell):
                diff_html = _char_diff_html(cell_str.strip(), ref_cell)
                te = QTextEdit()
                te.setReadOnly(True)
                te.setFrameStyle(0)
                te.setHtml(
                    f'<span style="font-family:Consolas;font-size:9pt;">{diff_html}</span>'
                )
                te.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                te.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                widget.setCellWidget(r_idx + 1, c_idx, te)
            else:
                item = QTableWidgetItem(cell_str)
                widget.setItem(r_idx + 1, c_idx, item)

    widget.resizeColumnsToContents()
    widget.resizeRowsToContents()


# ── main window ──────────────────────────────────────────────────────────────


class DebugViewer(QMainWindow):
    def __init__(self, db_path: str | Path):
        super().__init__()
        self.db_path = Path(db_path)
        self.conn = _conn(self.db_path)
        self.setWindowTitle(f"Extraction Debug Viewer — {self.db_path.name}")
        self.resize(1600, 950)

        # ── capability flags (backward compat) ────────────────────────────
        self._has_method_results = _table_exists(self.conn, "method_results")
        self._has_pipeline_runs = _table_exists(self.conn, "pipeline_runs")
        self._has_gt_diffs = _table_exists(self.conn, "ground_truth_diffs")
        self._has_table_id_col = _table_has_column(
            self.conn, "extracted_tables", "table_id"
        ) if _table_exists(self.conn, "extracted_tables") else False
        self._has_pdf_path_col = _table_has_column(
            self.conn, "papers", "pdf_path"
        ) if _table_exists(self.conn, "papers") else False
        self._has_vision_results = _table_exists(self.conn, "vision_agent_results")
        self._has_vision_role_col = (
            _table_has_column(self.conn, "vision_agent_results", "agent_role")
            if self._has_vision_results else False
        )
        self._has_paddle_results = _table_exists(self.conn, "paddle_results")
        self._has_paddle_gt_diffs = _table_exists(self.conn, "paddle_gt_diffs")

        # ── load manifest (for PDF paths / bboxes) ────────────────────────
        self._manifest: dict[str, dict] = {}
        manifest_path = PROJECT_ROOT / "tests" / "llm_structure" / "manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    for entry in json.load(f):
                        self._manifest[entry["table_id"]] = entry
            except (json.JSONDecodeError, KeyError):
                pass

        # ── open ground truth DB ──────────────────────────────────────────
        self.gt_conn: sqlite3.Connection | None = None
        gt_path = PROJECT_ROOT / "tests" / "ground_truth.db"
        if gt_path.exists():
            self.gt_conn = sqlite3.connect(str(gt_path))
            self.gt_conn.row_factory = sqlite3.Row

        # ── pymupdf lazy import flag ──────────────────────────────────────
        self._pymupdf = None  # lazy

        # ── build layout ─────────────────────────────────────────────────
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(4, 4, 4, 4)

        # Main horizontal splitter: tree | right panels
        hsplitter = QSplitter(Qt.Orientation.Horizontal)
        root_layout.addWidget(hsplitter)

        # Left: tree + filter
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(2)

        self.grade_filter = QComboBox()
        self.grade_filter.addItem("All grades")
        for g in ("A", "B", "C", "D", "F"):
            self.grade_filter.addItem(f"Grade {g}")
        self.grade_filter.currentIndexChanged.connect(self._apply_grade_filter)
        left_layout.addWidget(self.grade_filter)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Item", "Details"])
        self.tree.setColumnWidth(0, 280)
        self.tree.setMinimumWidth(350)
        self.tree.itemClicked.connect(self._on_tree_click)
        left_layout.addWidget(self.tree)

        hsplitter.addWidget(left_panel)

        # Right: vertical splitter  (top = metadata,  bottom = content)
        vsplitter = QSplitter(Qt.Orientation.Vertical)
        hsplitter.addWidget(vsplitter)

        # Top-right: metadata table
        self.meta_table = QTableWidget()
        self.meta_table.setColumnCount(2)
        self.meta_table.setHorizontalHeaderLabels(["Field", "Value"])
        self.meta_table.horizontalHeader().setStretchLastSection(True)
        self.meta_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.meta_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.meta_table.setAlternatingRowColors(True)
        self.meta_table.setWordWrap(True)
        self.meta_table.verticalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        vsplitter.addWidget(self.meta_table)

        # Bottom-right: content area (stacked via showing/hiding)
        self.content_stack = QWidget()
        content_layout = QVBoxLayout(self.content_stack)
        content_layout.setContentsMargins(0, 0, 0, 0)

        # text display
        self.text_display = QTextEdit()
        self.text_display.setReadOnly(True)
        self.text_display.setFont(QFont("Consolas", 10))
        content_layout.addWidget(self.text_display)

        # image display (inside scroll area)
        self.image_scroll = QScrollArea()
        self.image_scroll.setWidgetResizable(True)
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_scroll.setWidget(self.image_label)
        content_layout.addWidget(self.image_scroll)

        # rendered table
        self.rendered_table = QTableWidget()
        self.rendered_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.rendered_table.setAlternatingRowColors(True)
        content_layout.addWidget(self.rendered_table)

        # ── 2x2 comparison widget ────────────────────────────────────────
        self.comparison_widget = QWidget()
        cmp_layout = QGridLayout(self.comparison_widget)
        cmp_layout.setContentsMargins(0, 0, 0, 0)
        cmp_layout.setSpacing(4)

        # (0,0) Extracted table
        self.cmp_ext_group = QGroupBox("Extracted Table")
        ext_layout = QVBoxLayout(self.cmp_ext_group)
        self.cmp_ext_table = QTableWidget()
        self.cmp_ext_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.cmp_ext_table.setAlternatingRowColors(True)
        ext_layout.addWidget(self.cmp_ext_table)
        cmp_layout.addWidget(self.cmp_ext_group, 0, 0)

        # (0,1) PDF region
        self.cmp_pdf_group = QGroupBox("PDF Region")
        pdf_layout = QVBoxLayout(self.cmp_pdf_group)
        self.cmp_pdf_scroll = QScrollArea()
        self.cmp_pdf_scroll.setWidgetResizable(True)
        self.cmp_pdf_label = QLabel("(no PDF available)")
        self.cmp_pdf_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cmp_pdf_scroll.setWidget(self.cmp_pdf_label)
        pdf_layout.addWidget(self.cmp_pdf_scroll)
        cmp_layout.addWidget(self.cmp_pdf_group, 0, 1)

        # (1,0) Ground truth
        self.cmp_gt_group = QGroupBox("Ground Truth")
        gt_layout = QVBoxLayout(self.cmp_gt_group)
        self.cmp_gt_table = QTableWidget()
        self.cmp_gt_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.cmp_gt_table.setAlternatingRowColors(True)
        gt_layout.addWidget(self.cmp_gt_table)
        cmp_layout.addWidget(self.cmp_gt_group, 1, 0)

        # (1,1) Grid overlay
        self.cmp_overlay_group = QGroupBox("Grid Overlay")
        overlay_layout = QVBoxLayout(self.cmp_overlay_group)
        self.cmp_overlay_scroll = QScrollArea()
        self.cmp_overlay_scroll.setWidgetResizable(True)
        self.cmp_overlay_label = QLabel("(no overlay available)")
        self.cmp_overlay_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cmp_overlay_scroll.setWidget(self.cmp_overlay_label)
        overlay_layout.addWidget(self.cmp_overlay_scroll)
        cmp_layout.addWidget(self.cmp_overlay_group, 1, 1)

        content_layout.addWidget(self.comparison_widget)

        # ── vision comparison widget (vertical 3-panel) ────────────────
        self.vision_widget = QWidget()
        vision_layout = QVBoxLayout(self.vision_widget)
        vision_layout.setContentsMargins(0, 0, 0, 0)
        vision_layout.setSpacing(4)

        vision_splitter = QSplitter(Qt.Orientation.Vertical)

        # Top: PDF region
        self.vis_pdf_group = QGroupBox("PDF Region")
        vis_pdf_layout = QVBoxLayout(self.vis_pdf_group)
        self.vis_pdf_scroll = QScrollArea()
        self.vis_pdf_scroll.setWidgetResizable(True)
        self.vis_pdf_label = QLabel("(no PDF available)")
        self.vis_pdf_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.vis_pdf_label.setWordWrap(True)
        self.vis_pdf_scroll.setWidget(self.vis_pdf_label)
        vis_pdf_layout.addWidget(self.vis_pdf_scroll)
        vision_splitter.addWidget(self.vis_pdf_group)

        # Middle: Extracted table with char-level diff highlighting
        self.vis_ext_group = QGroupBox("Extracted Table")
        vis_ext_layout = QVBoxLayout(self.vis_ext_group)
        self.vis_ext_table = QTableWidget()
        self.vis_ext_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.vis_ext_table.setAlternatingRowColors(True)
        self.vis_ext_table.setWordWrap(True)
        self.vis_ext_table.setVerticalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self.vis_ext_table.setHorizontalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        vis_ext_layout.addWidget(self.vis_ext_table)
        vision_splitter.addWidget(self.vis_ext_group)

        # Bottom: Reference panel (selectable via dropdown)
        self.vis_ref_group = QGroupBox("Reference")
        vis_ref_layout = QVBoxLayout(self.vis_ref_group)
        self.vis_ref_combo = QComboBox()
        self.vis_ref_combo.currentIndexChanged.connect(self._on_ref_dropdown_changed)
        vis_ref_layout.addWidget(self.vis_ref_combo)
        self.vis_ref_table = QTableWidget()
        self.vis_ref_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.vis_ref_table.setAlternatingRowColors(True)
        self.vis_ref_table.setWordWrap(True)
        self.vis_ref_table.setVerticalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self.vis_ref_table.setHorizontalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        vis_ref_layout.addWidget(self.vis_ref_table)
        vision_splitter.addWidget(self.vis_ref_group)

        # Default proportions: PDF 25%, extracted 40%, reference 35%
        vision_splitter.setSizes([220, 350, 300])

        vision_layout.addWidget(vision_splitter)
        content_layout.addWidget(self.vision_widget)

        # ── state for vision view refresh ────────────────────────────
        # Stored when a vision/paddle/method node is clicked so the
        # dropdown change handler can recalculate diffs without
        # re-querying the extraction data.
        self._vis_current_table_id: str | None = None
        self._vis_current_ext_headers: list[str] = []
        self._vis_current_ext_rows: list[list[str]] = []
        self._vis_ref_sources: list[dict] = []  # [{label, headers, rows}]

        vsplitter.addWidget(self.content_stack)

        # initial visibility
        self._show_content("text")

        # splitter proportions
        hsplitter.setSizes([380, 1200])
        vsplitter.setSizes([300, 650])

        # status bar
        self.status = QStatusBar()
        self.setStatusBar(self.status)

        # ── populate tree ────────────────────────────────────────────────
        self._populate_tree()
        self._show_run_metadata()

    # ── pymupdf lazy loader ───────────────────────────────────────────────

    def _get_pymupdf(self):
        if self._pymupdf is None:
            import pymupdf
            self._pymupdf = pymupdf
        return self._pymupdf

    # ── tree population ──────────────────────────────────────────────────

    def _populate_tree(self):
        self.tree.clear()
        papers = self.conn.execute(
            "SELECT * FROM papers ORDER BY short_name"
        ).fetchall()

        for paper in papers:
            key = paper["item_key"]
            grade = paper["quality_grade"] or "?"
            colour = GRADE_COLOURS.get(grade, "#888")

            # paper node
            paper_item = QTreeWidgetItem(
                [paper["short_name"] or key, f"[{grade}] {paper['num_pages']}pp"]
            )
            paper_item.setData(0, Qt.ItemDataRole.UserRole, ("paper", key))
            paper_item.setForeground(1, QColor(colour))
            font = paper_item.font(1)
            font.setBold(True)
            paper_item.setFont(1, font)
            self.tree.addTopLevelItem(paper_item)

            # ── Sections ─────────────────────────────────────────────
            sections = self.conn.execute(
                "SELECT * FROM sections WHERE item_key=? ORDER BY char_start", (key,)
            ).fetchall()
            if sections:
                sec_parent = QTreeWidgetItem(["Sections", str(len(sections))])
                sec_parent.setData(0, Qt.ItemDataRole.UserRole, ("sections_parent", key))
                paper_item.addChild(sec_parent)
                for sec in sections:
                    label = sec["label"]
                    heading = _truncate(sec["heading_text"], 50) or "(no heading)"
                    si = QTreeWidgetItem([f"{label}", heading])
                    si.setData(
                        0, Qt.ItemDataRole.UserRole, ("section", key, sec["id"])
                    )
                    sec_parent.addChild(si)

            # ── Chunks ───────────────────────────────────────────────
            chunks = self.conn.execute(
                "SELECT id, chunk_index, page_num, section, "
                "substr(text, 1, 80) AS preview FROM chunks "
                "WHERE item_key=? ORDER BY chunk_index",
                (key,),
            ).fetchall()
            if chunks:
                chunk_parent = QTreeWidgetItem(["Chunks", str(len(chunks))])
                chunk_parent.setData(
                    0, Qt.ItemDataRole.UserRole, ("chunks_parent", key)
                )
                paper_item.addChild(chunk_parent)
                for ch in chunks:
                    preview = _truncate(ch["preview"], 60)
                    ci = QTreeWidgetItem(
                        [f"#{ch['chunk_index']}  p{ch['page_num']}", preview]
                    )
                    ci.setData(
                        0, Qt.ItemDataRole.UserRole, ("chunk", key, ch["id"])
                    )
                    chunk_parent.addChild(ci)

            # ── Tables ───────────────────────────────────────────────
            tables = self.conn.execute(
                "SELECT * FROM extracted_tables WHERE item_key=? ORDER BY table_index",
                (key,),
            ).fetchall()
            if tables:
                table_parent = QTreeWidgetItem(["Tables", str(len(tables))])
                table_parent.setData(
                    0, Qt.ItemDataRole.UserRole, ("tables_parent", key)
                )
                paper_item.addChild(table_parent)
                for tbl in tables:
                    cap = _truncate(tbl["caption"], 60) or "(no caption)"
                    tag = ""
                    if tbl["artifact_type"]:
                        tag = f" [{tbl['artifact_type']}]"
                    ti = QTreeWidgetItem(
                        [f"Table {tbl['table_index']}  p{tbl['page_num']}", cap + tag]
                    )
                    ti.setData(
                        0, Qt.ItemDataRole.UserRole, ("table", key, tbl["id"])
                    )
                    table_parent.addChild(ti)

                    # ── Method children ───────────────────────────────
                    self._add_method_children(ti, key, tbl)

                    # ── Vision agent children ─────────────────────────
                    self._add_vision_children(ti, key, tbl)

                    # ── Paddle engine children ────────────────────────
                    self._add_paddle_children(ti, key, tbl)

            # ── Figures ──────────────────────────────────────────────
            figures = self.conn.execute(
                "SELECT * FROM extracted_figures WHERE item_key=? ORDER BY figure_index",
                (key,),
            ).fetchall()
            if figures:
                fig_parent = QTreeWidgetItem(["Figures", str(len(figures))])
                fig_parent.setData(
                    0, Qt.ItemDataRole.UserRole, ("figures_parent", key)
                )
                paper_item.addChild(fig_parent)
                for fig in figures:
                    cap = _truncate(fig["caption"], 60) or "(no caption)"
                    has = "img" if fig["has_image"] else "no-img"
                    fi = QTreeWidgetItem(
                        [f"Fig {fig['figure_index']}  p{fig['page_num']}  [{has}]", cap]
                    )
                    fi.setData(
                        0, Qt.ItemDataRole.UserRole, ("figure", key, fig["id"])
                    )
                    fig_parent.addChild(fi)

            # ── Test results ─────────────────────────────────────────
            tests = self.conn.execute(
                "SELECT * FROM test_results WHERE paper=? ORDER BY id", (paper["short_name"],)
            ).fetchall()
            if tests:
                n_pass = sum(1 for t in tests if t["passed"])
                n_fail = len(tests) - n_pass
                test_parent = QTreeWidgetItem(
                    ["Tests", f"{n_pass} pass / {n_fail} fail"]
                )
                test_parent.setData(
                    0, Qt.ItemDataRole.UserRole, ("tests_parent", key)
                )
                if n_fail:
                    test_parent.setForeground(1, QColor("#f44336"))
                else:
                    test_parent.setForeground(1, QColor("#4caf50"))
                paper_item.addChild(test_parent)
                for t in tests:
                    status = "PASS" if t["passed"] else "FAIL"
                    sev = f" ({t['severity']})" if t["severity"] else ""
                    ti = QTreeWidgetItem(
                        [f"{status}{sev}", _truncate(t["test_name"], 50)]
                    )
                    ti.setData(
                        0, Qt.ItemDataRole.UserRole, ("test", key, t["id"])
                    )
                    if not t["passed"]:
                        ti.setForeground(0, QColor("#f44336"))
                    test_parent.addChild(ti)

        # global test results
        global_tests = self.conn.execute(
            "SELECT * FROM test_results WHERE paper='all' ORDER BY id"
        ).fetchall()
        if global_tests:
            n_pass = sum(1 for t in global_tests if t["passed"])
            n_fail = len(global_tests) - n_pass
            gt = QTreeWidgetItem(
                ["Global Tests", f"{n_pass} pass / {n_fail} fail"]
            )
            gt.setData(0, Qt.ItemDataRole.UserRole, ("global_tests",))
            if n_fail:
                gt.setForeground(1, QColor("#f44336"))
            self.tree.addTopLevelItem(gt)
            for t in global_tests:
                status = "PASS" if t["passed"] else "FAIL"
                ti = QTreeWidgetItem([f"{status}", _truncate(t["test_name"], 50)])
                ti.setData(0, Qt.ItemDataRole.UserRole, ("test", "all", t["id"]))
                if not t["passed"]:
                    ti.setForeground(0, QColor("#f44336"))
                gt.addChild(ti)

        self.status.showMessage(
            f"Loaded {len(papers)} papers from {self.db_path.name}"
        )

    # ── method child nodes ────────────────────────────────────────────────

    def _add_method_children(
        self, table_item: QTreeWidgetItem, item_key: str, tbl: sqlite3.Row
    ) -> None:
        """Add per-method child nodes under a table tree item."""
        if not self._has_method_results:
            return

        # Resolve table_id: prefer DB column, else compute from caption
        table_id = None
        if self._has_table_id_col:
            table_id = tbl["table_id"]
        if not table_id:
            # Compute from caption (backward compat with old DB)
            from zotero_chunk_rag.feature_extraction.ground_truth import make_table_id
            table_id = make_table_id(
                item_key, tbl["caption"], tbl["page_num"], tbl["table_index"]
            )

        methods = self.conn.execute(
            "SELECT id, method_name, quality_score FROM method_results "
            "WHERE table_id=? ORDER BY quality_score DESC",
            (table_id,),
        ).fetchall()
        if not methods:
            return

        # Find winning method
        winning_method = None
        if self._has_pipeline_runs:
            pr = self.conn.execute(
                "SELECT winning_method FROM pipeline_runs WHERE table_id=?",
                (table_id,),
            ).fetchone()
            if pr:
                winning_method = pr["winning_method"]

        for m in methods:
            score = m["quality_score"]
            score_str = f"{score:.1f}%" if score is not None else "?"
            name = m["method_name"]

            # Check if this is the winner
            # winning_method uses "structure:cell" format, method_name uses "structure+cell"
            is_winner = False
            if winning_method:
                # Normalize: winning_method may be "struct:cell", method_name "struct+cell"
                norm_winner = winning_method.replace(":", "+")
                is_winner = (name == norm_winner)

            prefix = "\u2605 " if is_winner else ""  # star
            mi = QTreeWidgetItem(
                [f"{prefix}{name}", f"[{score_str}]"]
            )
            mi.setData(
                0, Qt.ItemDataRole.UserRole,
                ("method", item_key, tbl["id"], table_id, m["id"]),
            )
            if is_winner:
                bold_font = mi.font(0)
                bold_font.setBold(True)
                mi.setFont(0, bold_font)
                mi.setForeground(1, QColor("#4caf50"))
            table_item.addChild(mi)

    # ── vision agent child nodes ──────────────────────────────────────────

    _VISION_ROLE_LABELS = {
        "transcriber": "Transcriber",
        "y_verifier": "Y-Verifier",
        "x_verifier": "X-Verifier",
        "synthesizer": "Synthesizer",
    }

    def _add_vision_children(
        self, table_item: QTreeWidgetItem, item_key: str, tbl: sqlite3.Row
    ) -> None:
        """Add per-agent vision child nodes under a table tree item."""
        if not self._has_vision_results:
            return

        # Resolve table_id
        table_id = None
        if self._has_table_id_col:
            table_id = tbl["table_id"]
        if not table_id:
            from zotero_chunk_rag.feature_extraction.ground_truth import make_table_id
            table_id = make_table_id(
                item_key, tbl["caption"], tbl["page_num"], tbl["table_index"]
            )

        agents = self.conn.execute(
            "SELECT id, agent_idx, agent_role, cell_accuracy_pct, num_corrections "
            "FROM vision_agent_results WHERE table_id=? ORDER BY agent_idx",
            (table_id,),
        ).fetchall()
        if not agents:
            return

        vision_parent = QTreeWidgetItem(["Vision Agents", f"{len(agents)} stages"])
        vision_parent.setData(
            0, Qt.ItemDataRole.UserRole, ("vision_parent", item_key, table_id)
        )
        vision_parent.setForeground(0, QColor("#7e57c2"))  # purple
        table_item.addChild(vision_parent)

        for ag in agents:
            role = ag["agent_role"] or f"agent_{ag['agent_idx']}"
            label = self._VISION_ROLE_LABELS.get(role, role)
            acc = ag["cell_accuracy_pct"]
            n_corr = ag["num_corrections"] or 0

            acc_str = f"{acc:.1f}%" if acc is not None else "no GT"
            corr_str = f"  {n_corr} corr" if n_corr > 0 else ""

            vi = QTreeWidgetItem([f"{label}", f"[{acc_str}]{corr_str}"])
            vi.setData(
                0, Qt.ItemDataRole.UserRole,
                ("vision_agent", item_key, tbl["id"], table_id, ag["id"]),
            )

            # Color-code accuracy
            if acc is not None:
                if acc >= 95:
                    vi.setForeground(1, QColor("#4caf50"))  # green
                elif acc >= 80:
                    vi.setForeground(1, QColor("#ffc107"))  # amber
                else:
                    vi.setForeground(1, QColor("#f44336"))  # red

            if n_corr > 0:
                bold_font = vi.font(0)
                bold_font.setBold(True)
                vi.setFont(0, bold_font)

            vision_parent.addChild(vi)

    # ── paddle engine child nodes ─────────────────────────────────────────

    def _add_paddle_children(
        self, table_item: QTreeWidgetItem, item_key: str, tbl: sqlite3.Row
    ) -> None:
        """Add per-engine paddle child nodes under a table tree item."""
        if not self._has_paddle_results:
            return

        # Resolve table_id
        table_id = None
        if self._has_table_id_col:
            table_id = tbl["table_id"]
        if not table_id:
            from zotero_chunk_rag.feature_extraction.ground_truth import make_table_id
            table_id = make_table_id(
                item_key, tbl["caption"], tbl["page_num"], tbl["table_index"]
            )

        engines = self.conn.execute(
            "SELECT id, engine_name, caption, is_orphan "
            "FROM paddle_results WHERE table_id=? ORDER BY engine_name",
            (table_id,),
        ).fetchall()
        if not engines:
            return

        paddle_parent = QTreeWidgetItem(["Paddle Engines", f"{len(engines)} results"])
        paddle_parent.setData(
            0, Qt.ItemDataRole.UserRole, ("paddle_parent", item_key, table_id)
        )
        paddle_parent.setForeground(0, QColor("#00897b"))  # teal
        table_item.addChild(paddle_parent)

        for eng in engines:
            engine_name = eng["engine_name"]
            # Look up accuracy from paddle_gt_diffs
            acc_str = "no GT"
            if self._has_paddle_gt_diffs:
                gtd = self.conn.execute(
                    "SELECT cell_accuracy_pct FROM paddle_gt_diffs "
                    "WHERE table_id=? AND engine_name=?",
                    (table_id, engine_name),
                ).fetchone()
                if gtd and gtd["cell_accuracy_pct"] is not None:
                    acc_str = f"{gtd['cell_accuracy_pct']:.1f}%"

            short_label = engine_name.replace("paddleocr_", "").replace("pp_structure_", "ppv")
            ei = QTreeWidgetItem([short_label, f"[{acc_str}]"])
            ei.setData(
                0, Qt.ItemDataRole.UserRole,
                ("paddle_result", item_key, tbl["id"], table_id, eng["id"]),
            )

            # Color-code accuracy
            if acc_str != "no GT":
                acc_val = float(acc_str.rstrip("%"))
                if acc_val >= 95:
                    ei.setForeground(1, QColor("#4caf50"))
                elif acc_val >= 80:
                    ei.setForeground(1, QColor("#ffc107"))
                else:
                    ei.setForeground(1, QColor("#f44336"))

            paddle_parent.addChild(ei)

    # ── grade filter ─────────────────────────────────────────────────────

    def _apply_grade_filter(self):
        sel = self.grade_filter.currentText()
        grade = None if sel == "All grades" else sel.split()[-1]
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data and data[0] == "paper":
                detail = item.text(1)
                item_grade = detail.split("]")[0].replace("[", "").strip()
                item.setHidden(grade is not None and item_grade != grade)

    # ── content display helpers ──────────────────────────────────────────

    def _show_content(self, mode: str):
        """Show one of: 'text', 'image', 'table', 'comparison', 'vision'."""
        self.text_display.setVisible(mode == "text")
        self.image_scroll.setVisible(mode == "image")
        self.rendered_table.setVisible(mode == "table")
        self.comparison_widget.setVisible(mode == "comparison")
        self.vision_widget.setVisible(mode == "vision")

    def _set_meta(self, rows: list[tuple[str, str]]):
        self.meta_table.setRowCount(len(rows))
        for i, (field, value) in enumerate(rows):
            fi = QTableWidgetItem(field)
            fi.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            self.meta_table.setItem(i, 0, fi)
            vi = QTableWidgetItem(str(value))
            vi.setFont(QFont("Consolas", 9))
            self.meta_table.setItem(i, 1, vi)

    # ── run metadata (shown on startup) ──────────────────────────────────

    def _show_run_metadata(self):
        rows = self.conn.execute("SELECT * FROM run_metadata").fetchall()
        meta = [(r["key"], r["value"]) for r in rows]
        self._set_meta(meta)
        self._show_content("text")
        self.text_display.setPlainText(
            "Select an item in the tree to view its content.\n\n"
            "Run metadata is shown in the metadata panel above."
        )

    # ── tree click handler ───────────────────────────────────────────────

    def _on_tree_click(self, item: QTreeWidgetItem, column: int):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        kind = data[0]

        if kind == "paper":
            self._show_paper(data[1])
        elif kind == "section":
            self._show_section(data[1], data[2])
        elif kind == "chunk":
            self._show_chunk(data[1], data[2])
        elif kind == "table":
            self._show_table(data[1], data[2])
        elif kind == "figure":
            self._show_figure(data[1], data[2])
        elif kind == "test":
            self._show_test(data[2])
        elif kind == "method":
            self._show_method_comparison(data[1], data[2], data[3], data[4])
        elif kind == "vision_agent":
            self._show_vision_agent(data[1], data[2], data[3], data[4])
        elif kind == "paddle_result":
            self._show_paddle_result(data[1], data[2], data[3], data[4])
        elif kind == "vision_parent":
            self._show_vision_summary(data[1], data[2])
        elif kind == "paddle_parent":
            self._show_paddle_summary(data[1], data[2])
        elif kind == "chunks_parent":
            self._show_chunks_summary(data[1])
        elif kind == "tables_parent":
            self._show_tables_summary(data[1])
        elif kind == "figures_parent":
            self._show_figures_summary(data[1])
        elif kind == "tests_parent":
            self._show_tests_summary(data[1])
        elif kind == "sections_parent":
            self._show_sections_summary(data[1])

    # ── display: paper ───────────────────────────────────────────────────

    def _show_paper(self, item_key: str):
        row = self.conn.execute(
            "SELECT * FROM papers WHERE item_key=?", (item_key,)
        ).fetchone()
        if not row:
            return

        meta = [
            ("Title", row["title"] or ""),
            ("Item Key", row["item_key"]),
            ("Short Name", row["short_name"] or ""),
            ("Pages", row["num_pages"]),
            ("Chunks", row["num_chunks"]),
            ("Quality Grade", row["quality_grade"] or ""),
            ("", ""),
            ("Figures Found", row["figures_found"]),
            ("Figures w/ Captions", row["figures_with_captions"]),
            ("Figures Missing", row["figures_missing"]),
            ("Figure Captions Found", row["figure_captions_found"]),
            ("Figure Number Gaps", row["figure_number_gaps"] or "[]"),
            ("Unmatched Fig Captions", row["unmatched_figure_captions"] or "[]"),
            ("", ""),
            ("Tables Found", row["tables_found"]),
            ("Tables w/ Captions", row["tables_with_captions"]),
            ("Tables Missing", row["tables_missing"]),
            ("Table Captions Found", row["table_captions_found"]),
            ("Tables 1x1", row["tables_1x1"]),
            ("Table Number Gaps", row["table_number_gaps"] or "[]"),
            ("Unmatched Tbl Captions", row["unmatched_table_captions"] or "[]"),
            ("", ""),
            ("Encoding Artifact Captions", row["encoding_artifact_captions"]),
            ("Duplicate Captions", row["duplicate_captions"]),
        ]
        self._set_meta(meta)

        # Show full markdown in content area
        md = row["full_markdown"] or "(no markdown)"
        self._show_content("text")
        self.text_display.setPlainText(md)
        self.status.showMessage(f"Paper: {row['short_name']} [{row['quality_grade']}]")

    # ── display: section ─────────────────────────────────────────────────

    def _show_section(self, item_key: str, section_id: int):
        sec = self.conn.execute(
            "SELECT * FROM sections WHERE id=?", (section_id,)
        ).fetchone()
        if not sec:
            return

        meta = [
            ("Label", sec["label"]),
            ("Heading", sec["heading_text"] or "(none)"),
            ("Confidence", f"{sec['confidence']:.2f}"),
            ("Char Range", f"{sec['char_start']} – {sec['char_end']}"),
            ("Length (chars)", sec["char_end"] - sec["char_start"]),
        ]
        self._set_meta(meta)

        # Extract the section text from full_markdown
        paper = self.conn.execute(
            "SELECT full_markdown FROM papers WHERE item_key=?", (item_key,)
        ).fetchone()
        if paper and paper["full_markdown"]:
            text = paper["full_markdown"][sec["char_start"]:sec["char_end"]]
        else:
            text = "(full markdown not available)"

        self._show_content("text")
        self.text_display.setPlainText(text)
        self.status.showMessage(
            f"Section: {sec['label']} (confidence {sec['confidence']:.2f})"
        )

    # ── display: chunk ───────────────────────────────────────────────────

    def _show_chunk(self, item_key: str, chunk_id: int):
        row = self.conn.execute(
            "SELECT * FROM chunks WHERE id=?", (chunk_id,)
        ).fetchone()
        if not row:
            return

        meta = [
            ("Chunk Index", row["chunk_index"]),
            ("Page", row["page_num"]),
            ("Section", row["section"]),
            ("Section Confidence", f"{row['section_confidence']:.2f}"),
            ("Char Range", f"{row['char_start']} – {row['char_end']}"),
            ("Length (chars)", row["char_end"] - row["char_start"]),
        ]
        self._set_meta(meta)
        self._show_content("text")
        self.text_display.setPlainText(row["text"] or "")
        self.status.showMessage(
            f"Chunk #{row['chunk_index']}  page {row['page_num']}  "
            f"section={row['section']}"
        )

    # ── display: table ───────────────────────────────────────────────────

    def _show_table(self, item_key: str, table_id: int):
        row = self.conn.execute(
            "SELECT * FROM extracted_tables WHERE id=?", (table_id,)
        ).fetchone()
        if not row:
            return

        meta = [
            ("Table Index", row["table_index"]),
            ("Page", row["page_num"]),
            ("Caption", row["caption"] or "(none)"),
            ("Caption Position", row["caption_position"] or ""),
            ("Rows x Cols", f"{row['num_rows']} x {row['num_cols']}"),
            ("Fill Rate", f"{row['fill_rate']:.1%}"),
            ("Non-empty Cells", f"{row['non_empty_cells']} / {row['total_cells']}"),
            ("Artifact Type", row["artifact_type"] or "(none)"),
            ("BBox", row["bbox"] or ""),
        ]
        if row["reference_context"]:
            meta.append(("Reference Context", row["reference_context"]))
        self._set_meta(meta)

        # Render the table
        headers = json.loads(row["headers_json"]) if row["headers_json"] else []
        data_rows = json.loads(row["rows_json"]) if row["rows_json"] else []

        self.rendered_table.clear()
        n_cols = len(headers) if headers else (len(data_rows[0]) if data_rows else 0)
        self.rendered_table.setColumnCount(n_cols)
        self.rendered_table.setRowCount(len(data_rows))
        if headers:
            self.rendered_table.setHorizontalHeaderLabels(headers)
        for r_idx, data_row in enumerate(data_rows):
            for c_idx, cell in enumerate(data_row):
                self.rendered_table.setItem(
                    r_idx, c_idx, QTableWidgetItem(str(cell))
                )
        self.rendered_table.resizeColumnsToContents()

        self._show_content("table")
        self.status.showMessage(
            f"Table {row['table_index']}  page {row['page_num']}  "
            f"{row['num_rows']}x{row['num_cols']}  fill={row['fill_rate']:.0%}"
        )

    # ── display: figure ──────────────────────────────────────────────────

    def _show_figure(self, item_key: str, figure_id: int):
        row = self.conn.execute(
            "SELECT * FROM extracted_figures WHERE id=?", (figure_id,)
        ).fetchone()
        if not row:
            return

        meta = [
            ("Figure Index", row["figure_index"]),
            ("Page", row["page_num"]),
            ("Caption", row["caption"] or "(none)"),
            ("Has Image", "Yes" if row["has_image"] else "No"),
            ("Image Path", row["image_path"] or ""),
            ("BBox", row["bbox"] or ""),
        ]
        if row["reference_context"]:
            meta.append(("Reference Context", row["reference_context"]))
        self._set_meta(meta)

        # Show image if available
        img_path = row["image_path"]
        if img_path and os.path.isfile(img_path):
            pixmap = QPixmap(img_path)
            if not pixmap.isNull():
                # Scale to fit, max 800px wide
                if pixmap.width() > 800:
                    pixmap = pixmap.scaledToWidth(
                        800, Qt.TransformationMode.SmoothTransformation
                    )
                self.image_label.setPixmap(pixmap)
                self._show_content("image")
                self.status.showMessage(
                    f"Figure {row['figure_index']}  page {row['page_num']}  "
                    f"{pixmap.width()}x{pixmap.height()}px"
                )
                return

        # No image — show caption as text
        self._show_content("text")
        self.text_display.setPlainText(
            f"No image file available.\n\n"
            f"Path: {img_path or '(none)'}\n\n"
            f"Caption:\n{row['caption'] or '(none)'}"
        )
        self.status.showMessage(
            f"Figure {row['figure_index']}  page {row['page_num']}  (no image)"
        )

    # ── display: test result ─────────────────────────────────────────────

    def _show_test(self, test_id: int):
        row = self.conn.execute(
            "SELECT * FROM test_results WHERE id=?", (test_id,)
        ).fetchone()
        if not row:
            return

        meta = [
            ("Test Name", row["test_name"]),
            ("Paper", row["paper"]),
            ("Passed", "Yes" if row["passed"] else "No"),
            ("Severity", row["severity"] or ""),
        ]
        self._set_meta(meta)
        self._show_content("text")
        self.text_display.setPlainText(row["detail"] or "(no detail)")
        status = "PASS" if row["passed"] else "FAIL"
        self.status.showMessage(f"Test: {row['test_name']} — {status}")

    # ── display: method comparison (2x2 view) ────────────────────────────

    def _resolve_pdf_info(self, table_id: str, item_key: str) -> dict | None:
        """Resolve PDF path, page number, and bbox for a table.

        Checks manifest first, then papers.pdf_path column.
        Returns {pdf_path, page_num, bbox} or None.
        """
        # 1. Check manifest
        if table_id in self._manifest:
            entry = self._manifest[table_id]
            pdf_path = entry.get("pdf_path")
            if pdf_path and os.path.isfile(pdf_path):
                return {
                    "pdf_path": pdf_path,
                    "page_num": entry.get("page_num"),
                    "bbox": entry.get("bbox"),
                }

        # 2. Fallback: papers.pdf_path + extracted_tables.bbox
        if self._has_pdf_path_col:
            paper = self.conn.execute(
                "SELECT pdf_path FROM papers WHERE item_key=?", (item_key,)
            ).fetchone()
            if paper and paper["pdf_path"] and os.path.isfile(paper["pdf_path"]):
                # Get bbox and page_num from extracted_tables via table_id
                if self._has_table_id_col:
                    tbl = self.conn.execute(
                        "SELECT page_num, bbox FROM extracted_tables "
                        "WHERE table_id=? AND item_key=?",
                        (table_id, item_key),
                    ).fetchone()
                else:
                    tbl = None
                if tbl and tbl["bbox"]:
                    return {
                        "pdf_path": paper["pdf_path"],
                        "page_num": tbl["page_num"],
                        "bbox": json.loads(tbl["bbox"]),
                    }

        return None

    def _load_ground_truth(self, table_id: str) -> tuple[list[str], list[list[str]]] | None:
        """Load ground truth headers and rows for a table_id."""
        if not self.gt_conn:
            return None
        row = self.gt_conn.execute(
            "SELECT headers_json, rows_json FROM ground_truth_tables WHERE table_id=?",
            (table_id,),
        ).fetchone()
        if not row:
            return None
        return json.loads(row["headers_json"]), json.loads(row["rows_json"])

    def _render_table_pixmap(
        self,
        pdf_path: str,
        page_num: int,
        bbox: list[float],
        padding: int = 20,
        dpi: int = 300,
    ) -> tuple[QPixmap, tuple[float, float]] | None:
        """Render a table region from a PDF as a QPixmap.

        Returns (pixmap, (clip_x0, clip_y0)) or None on failure.
        """
        try:
            fitz = self._get_pymupdf()
            doc = fitz.open(str(pdf_path))
            try:
                page = doc[page_num - 1]  # 1-indexed -> 0-indexed
                page_rect = page.rect
                x0, y0, x1, y1 = bbox
                clip = fitz.Rect(
                    max(x0 - padding, page_rect.x0),
                    max(y0 - padding, page_rect.y0),
                    min(x1 + padding, page_rect.x1),
                    min(y1 + padding, page_rect.y1),
                )
                pix = page.get_pixmap(clip=clip, dpi=dpi)
                # Convert to QImage -> QPixmap
                img = QImage(
                    pix.samples,
                    pix.width,
                    pix.height,
                    pix.stride,
                    QImage.Format.Format_RGB888,
                )
                qpixmap = QPixmap.fromImage(img.copy())  # .copy() to detach from samples buffer
                return qpixmap, (clip.x0, clip.y0)
            finally:
                doc.close()
        except Exception:
            return None

    def _draw_grid_overlay(
        self,
        base_pixmap: QPixmap,
        clip_origin: tuple[float, float],
        col_boundaries: list[float],
        row_boundaries: list[float],
        bbox: list[float],
        dpi: int = 300,
    ) -> QPixmap:
        """Draw column/row boundary lines and bbox outline on a pixmap copy."""
        result = base_pixmap.copy()
        painter = QPainter(result)
        scale = dpi / 72.0
        clip_x0, clip_y0 = clip_origin

        # Red pen for column boundaries (vertical lines)
        col_pen = QPen(QColor("#e53935"), 2)
        painter.setPen(col_pen)
        for x in col_boundaries:
            px = (x - clip_x0) * scale
            painter.drawLine(int(px), 0, int(px), result.height())

        # Blue pen for row boundaries (horizontal lines)
        row_pen = QPen(QColor("#1e88e5"), 2)
        painter.setPen(row_pen)
        for y in row_boundaries:
            py = (y - clip_y0) * scale
            painter.drawLine(0, int(py), result.width(), int(py))

        # Green dashed pen for bbox outline
        bbox_pen = QPen(QColor("#43a047"), 1, Qt.PenStyle.DashLine)
        painter.setPen(bbox_pen)
        bx0 = int((bbox[0] - clip_x0) * scale)
        by0 = int((bbox[1] - clip_y0) * scale)
        bx1 = int((bbox[2] - clip_x0) * scale)
        by1 = int((bbox[3] - clip_y0) * scale)
        painter.drawRect(bx0, by0, bx1 - bx0, by1 - by0)

        painter.end()
        return result

    def _show_method_comparison(
        self,
        item_key: str,
        table_db_id: int,
        table_id: str,
        method_row_id: int,
    ) -> None:
        """Show 2x2 comparison view for a specific method result."""
        # Load method result
        mr = self.conn.execute(
            "SELECT * FROM method_results WHERE id=?", (method_row_id,)
        ).fetchone()
        if not mr:
            return

        method_name = mr["method_name"]
        quality_score = mr["quality_score"]

        # Parse cell grid
        ext_headers: list[str] = []
        ext_rows: list[list[str]] = []
        col_boundaries: list[float] = []
        row_boundaries: list[float] = []
        structure_method = ""
        cell_method = ""

        if mr["cell_grid_json"]:
            try:
                grid = json.loads(mr["cell_grid_json"])
                ext_headers = grid.get("headers", [])
                ext_rows = grid.get("rows", [])
                col_boundaries = grid.get("col_boundaries", [])
                row_boundaries = grid.get("row_boundaries", [])
                structure_method = grid.get("structure_method", "")
                cell_method = grid.get("method", "")
            except (json.JSONDecodeError, TypeError):
                pass

        # Parse boundary hypotheses for additional info
        boundary_info = {}
        if mr["boundary_hypotheses_json"]:
            try:
                boundary_info = json.loads(mr["boundary_hypotheses_json"])
            except (json.JSONDecodeError, TypeError):
                pass

        # Load ground truth
        gt_data = self._load_ground_truth(table_id)
        gt_headers: list[str] = gt_data[0] if gt_data else []
        gt_rows: list[list[str]] = gt_data[1] if gt_data else []

        # Per-cell GT match/mismatch marks
        cell_marks: dict[tuple[int, int], bool] = {}
        gt_diff_info = {}
        if gt_data and ext_headers and ext_rows:
            try:
                from zotero_chunk_rag.feature_extraction.ground_truth import (
                    compare_extraction,
                    GROUND_TRUTH_DB_PATH,
                    _normalize_cell,
                )
                cmp = compare_extraction(
                    GROUND_TRUTH_DB_PATH, table_id, ext_headers, ext_rows,
                )
                gt_diff_info = {
                    "cell_accuracy": cmp.cell_accuracy_pct,
                    "fuzzy_accuracy": cmp.fuzzy_accuracy_pct,
                    "fuzzy_precision": cmp.fuzzy_precision_pct,
                    "fuzzy_recall": cmp.fuzzy_recall_pct,
                    "splits": len(cmp.column_splits) + len(cmp.row_splits),
                    "merges": len(cmp.column_merges) + len(cmp.row_merges),
                    "cell_diffs": len(cmp.cell_diffs),
                    "coverage": cmp.structural_coverage_pct,
                }
                # Build col map for GT->ext index translation.
                # Start with header-aligned matches from the comparison,
                # then add positional fallbacks for unmatched columns so
                # that a header transcription error (e.g. subscript)
                # doesn't exclude the entire column from cell marking.
                col_map = {g: e for g, e in cmp.matched_columns}
                used_gt = {g for g, _ in cmp.matched_columns}
                used_ext = {e for _, e in cmp.matched_columns}
                for g_ci in cmp.missing_columns:
                    if g_ci not in used_gt and g_ci not in used_ext:
                        # Same-index ext column available?
                        if g_ci < len(ext_headers) and g_ci not in used_ext:
                            col_map[g_ci] = g_ci
                            used_gt.add(g_ci)
                            used_ext.add(g_ci)

                # Same for rows: add positional fallbacks
                row_map: list[tuple[int, int]] = list(cmp.matched_rows)
                used_gt_r = {g for g, _ in cmp.matched_rows}
                used_ext_r = {e for _, e in cmp.matched_rows}
                for g_ri in cmp.missing_rows:
                    if g_ri not in used_gt_r and g_ri not in used_ext_r:
                        if g_ri < len(ext_rows) and g_ri not in used_ext_r:
                            row_map.append((g_ri, g_ri))
                            used_gt_r.add(g_ri)
                            used_ext_r.add(g_ri)

                # Compare each ext cell against its GT counterpart directly
                for g_ri, e_ri in row_map:
                    for g_ci, e_ci in col_map.items():
                        gt_val = _normalize_cell(
                            gt_rows[g_ri][g_ci]
                        ) if g_ci < len(gt_rows[g_ri]) else ""
                        ext_val = _normalize_cell(
                            ext_rows[e_ri][e_ci]
                        ) if e_ci < len(ext_rows[e_ri]) else ""
                        cell_marks[(e_ri, e_ci)] = (gt_val == ext_val)
            except (KeyError, ImportError):
                pass

        # ── Populate extracted table (0,0) ────────────────────────────
        _populate_table_widget(self.cmp_ext_table, ext_headers, ext_rows, cell_marks)

        # ── Populate ground truth table (1,0) ─────────────────────────
        if gt_data:
            _populate_table_widget(self.cmp_gt_table, gt_headers, gt_rows)
            self.cmp_gt_group.setTitle(
                f"Ground Truth ({len(gt_rows)}x{len(gt_headers)})"
            )
        else:
            self.cmp_gt_table.clear()
            self.cmp_gt_table.setRowCount(0)
            self.cmp_gt_table.setColumnCount(0)
            self.cmp_gt_group.setTitle("Ground Truth (not available)")

        # ── Render PDF images (0,1) and (1,1) ────────────────────────
        # Always use extracted_tables bbox (precise) — manifest bbox is
        # full-page-width and would show the entire page.
        tbl_row = self.conn.execute(
            "SELECT bbox, page_num FROM extracted_tables WHERE id=?", (table_db_id,)
        ).fetchone()
        bbox = json.loads(tbl_row["bbox"]) if tbl_row and tbl_row["bbox"] else None

        pdf_info = self._resolve_pdf_info(table_id, item_key)

        if pdf_info and bbox:
            render_result = self._render_table_pixmap(
                pdf_info["pdf_path"],
                pdf_info["page_num"] or tbl_row["page_num"],
                bbox,
            )
            if render_result:
                clean_pixmap, clip_origin = render_result
                # Scale for display
                display_pixmap = clean_pixmap
                if display_pixmap.width() > 600:
                    display_pixmap = display_pixmap.scaledToWidth(
                        600, Qt.TransformationMode.SmoothTransformation
                    )
                self.cmp_pdf_label.setPixmap(display_pixmap)
                self.cmp_pdf_group.setTitle("PDF Region")

                # Grid overlay
                overlay_pixmap = self._draw_grid_overlay(
                    clean_pixmap, clip_origin,
                    col_boundaries, row_boundaries, bbox,
                )
                if overlay_pixmap.width() > 600:
                    overlay_pixmap = overlay_pixmap.scaledToWidth(
                        600, Qt.TransformationMode.SmoothTransformation
                    )
                self.cmp_overlay_label.setPixmap(overlay_pixmap)
                self.cmp_overlay_group.setTitle(
                    f"Grid Overlay ({len(col_boundaries)} cols, "
                    f"{len(row_boundaries)} rows)"
                )
            else:
                self.cmp_pdf_label.setText("(PDF render failed)")
                self.cmp_pdf_label.setPixmap(QPixmap())
                self.cmp_overlay_label.setText("(no overlay)")
                self.cmp_overlay_label.setPixmap(QPixmap())
        else:
            self.cmp_pdf_label.setText("(no PDF available)")
            self.cmp_pdf_label.setPixmap(QPixmap())
            self.cmp_overlay_label.setText("(no overlay available)")
            self.cmp_overlay_label.setPixmap(QPixmap())

        # ── Build metadata ────────────────────────────────────────────
        # Check if this is the pipeline winner
        is_winner = False
        if self._has_pipeline_runs:
            pr = self.conn.execute(
                "SELECT winning_method FROM pipeline_runs WHERE table_id=?",
                (table_id,),
            ).fetchone()
            if pr and pr["winning_method"]:
                norm_winner = pr["winning_method"].replace(":", "+")
                is_winner = (method_name == norm_winner)

        n_ext_rows = len(ext_rows)
        n_ext_cols = len(ext_headers) if ext_headers else (
            len(ext_rows[0]) if ext_rows else 0
        )
        # Compute fill rate
        non_empty = sum(
            1 for row in ext_rows for cell in row if str(cell).strip()
        )
        total = sum(len(row) for row in ext_rows)
        fill_rate = non_empty / total if total else 0.0

        meta: list[tuple[str, str]] = [
            ("Method", method_name),
            ("Structure Method", structure_method or boundary_info.get("structure_method", "")),
            ("Cell Method", cell_method or boundary_info.get("cell_method", "")),
            ("Pipeline Winner", "Yes" if is_winner else "No"),
            ("Quality Score", f"{quality_score:.1f}%" if quality_score is not None else "N/A"),
            ("Grid Shape", f"{n_ext_rows} x {n_ext_cols}"),
            ("Fill Rate", f"{fill_rate:.1%}"),
            ("Col Boundaries", f"{len(col_boundaries)}  {col_boundaries}"),
            ("Row Boundaries", f"{len(row_boundaries)}  {row_boundaries}"),
        ]

        # GT comparison metrics
        if gt_diff_info:
            meta.extend([
                ("", ""),
                ("GT Cell Accuracy", f"{gt_diff_info['cell_accuracy']:.1f}%"),
                ("GT Fuzzy Accuracy", f"{gt_diff_info['fuzzy_accuracy']:.1f}%"),
                ("GT Fuzzy Precision", f"{gt_diff_info['fuzzy_precision']:.1f}%"),
                ("GT Fuzzy Recall", f"{gt_diff_info['fuzzy_recall']:.1f}%"),
                ("Splits", str(gt_diff_info["splits"])),
                ("Merges", str(gt_diff_info["merges"])),
                ("Cell Diffs", str(gt_diff_info["cell_diffs"])),
                ("Coverage", f"{gt_diff_info['coverage']:.1f}%"),
            ])
        elif gt_data:
            meta.append(("GT Comparison", "comparison failed"))
        else:
            meta.append(("GT Comparison", "no ground truth"))

        # Also show GT diffs from the debug DB if available
        if self._has_gt_diffs:
            gtd = self.conn.execute(
                "SELECT cell_accuracy_pct, fuzzy_accuracy_pct, num_splits, "
                "num_merges, num_cell_diffs FROM ground_truth_diffs "
                "WHERE table_id=? LIMIT 1",
                (table_id,),
            ).fetchone()
            if gtd:
                meta.extend([
                    ("", ""),
                    ("DB GT Accuracy", f"{gtd['cell_accuracy_pct']:.1f}%"
                     if gtd["cell_accuracy_pct"] is not None else "N/A"),
                    ("DB Fuzzy Accuracy", f"{gtd['fuzzy_accuracy_pct']:.1f}%"
                     if gtd["fuzzy_accuracy_pct"] is not None else "N/A"),
                ])

        self._set_meta(meta)

        # Switch to comparison mode
        self._show_content("comparison")
        self.status.showMessage(
            f"Method: {method_name}  "
            f"score={quality_score:.1f}%  "
            f"{n_ext_rows}x{n_ext_cols}  "
            f"{'WINNER' if is_winner else ''}"
            if quality_score is not None
            else f"Method: {method_name}  {n_ext_rows}x{n_ext_cols}"
        )

    # ── display: vision agent (2x2 view) ────────────────────────────────

    def _show_vision_agent(
        self,
        item_key: str,
        table_db_id: int,
        table_id: str,
        vision_row_id: int,
    ) -> None:
        """Show vertical 3-panel view: PDF, extracted table with char-level
        diff, and selectable reference panel."""
        vr = self.conn.execute(
            "SELECT * FROM vision_agent_results WHERE id=?", (vision_row_id,)
        ).fetchone()
        if not vr:
            return

        role = vr["agent_role"] if self._has_vision_role_col else f"agent_{vr['agent_idx']}"
        label = self._VISION_ROLE_LABELS.get(role, role)

        # Parse headers/rows
        ext_headers: list[str] = []
        ext_rows: list[list[str]] = []
        if vr["headers_json"]:
            try:
                ext_headers = json.loads(vr["headers_json"])
            except (json.JSONDecodeError, TypeError):
                pass
        if vr["rows_json"]:
            try:
                ext_rows = json.loads(vr["rows_json"])
            except (json.JSONDecodeError, TypeError):
                pass

        # ── Top: PDF region ───────────────────────────────────────────
        tbl_row = self.conn.execute(
            "SELECT bbox, page_num FROM extracted_tables WHERE id=?", (table_db_id,)
        ).fetchone()
        bbox = json.loads(tbl_row["bbox"]) if tbl_row and tbl_row["bbox"] else None
        pdf_info = self._resolve_pdf_info(table_id, item_key)

        if pdf_info and bbox:
            render_result = self._render_table_pixmap(
                pdf_info["pdf_path"],
                pdf_info["page_num"] or tbl_row["page_num"],
                bbox,
            )
            if render_result:
                clean_pixmap, _ = render_result
                display_pixmap = clean_pixmap
                if display_pixmap.width() > 900:
                    display_pixmap = display_pixmap.scaledToWidth(
                        900, Qt.TransformationMode.SmoothTransformation
                    )
                self.vis_pdf_label.setPixmap(display_pixmap)
                self.vis_pdf_group.setTitle("PDF Region")
            else:
                self.vis_pdf_label.setText("(PDF render failed)")
                self.vis_pdf_label.setPixmap(QPixmap())
        else:
            self.vis_pdf_label.setText("(no PDF available)")
            self.vis_pdf_label.setPixmap(QPixmap())

        # ── Middle + Bottom: extraction with diff + dropdown reference ─
        n_corr = vr["num_corrections"] or 0
        corr_suffix = f" — {n_corr} corrections" if n_corr else ""
        self.vis_ext_group.setTitle(f"{label} Output{corr_suffix}")
        self._setup_vision_view(table_id, ext_headers, ext_rows)

        # ── Build metadata ────────────────────────────────────────────
        n_ext_rows = len(ext_rows)
        n_ext_cols = len(ext_headers) if ext_headers else (
            len(ext_rows[0]) if ext_rows else 0
        )
        non_empty = sum(
            1 for row in ext_rows for cell in row if str(cell).strip()
        )
        total = sum(len(row) for row in ext_rows)
        fill_rate = non_empty / total if total else 0.0

        meta: list[tuple[str, str]] = [
            ("Agent", label),
            ("Role", role),
            ("Grid Shape", f"{n_ext_rows} x {n_ext_cols}"),
            ("Fill Rate", f"{fill_rate:.1%}"),
            ("Parse Success", "Yes" if vr["parse_success"] else "No"),
            ("Corrections", str(n_corr)),
        ]

        if vr["footnotes"]:
            meta.append(("Footnotes", vr["footnotes"]))

        # Show corrections text in metadata
        corrections: list[str] = []
        if vr["corrections_json"]:
            try:
                corrections = json.loads(vr["corrections_json"])
            except (json.JSONDecodeError, TypeError):
                pass
        if corrections:
            meta.append(("", ""))
            for i, c in enumerate(corrections, 1):
                meta.append((f"Correction {i}", c))

        # GT accuracy from stored data
        stored_acc = vr["cell_accuracy_pct"]
        if stored_acc is not None:
            meta.append(("", ""))
            meta.append(("Stored GT Accuracy", f"{stored_acc:.1f}%"))

        self._set_meta(meta)

        self._show_content("vision")
        acc_str = f"{stored_acc:.1f}%" if stored_acc is not None else "no GT"
        self.status.showMessage(
            f"Vision: {label}  {n_ext_rows}x{n_ext_cols}  "
            f"acc={acc_str}  corrections={n_corr}"
        )

    def _show_vision_summary(self, item_key: str, table_id: str) -> None:
        """Show accuracy summary across all vision agents for a table."""
        agents = self.conn.execute(
            "SELECT agent_role, cell_accuracy_pct, num_corrections, parse_success "
            "FROM vision_agent_results WHERE table_id=? ORDER BY agent_idx",
            (table_id,),
        ).fetchall()
        if not agents:
            return

        meta = [("Table ID", table_id)]
        for ag in agents:
            role = ag["agent_role"] or "?"
            label = self._VISION_ROLE_LABELS.get(role, role)
            acc = ag["cell_accuracy_pct"]
            acc_str = f"{acc:.1f}%" if acc is not None else "no GT"
            n_corr = ag["num_corrections"] or 0
            corr_str = f", {n_corr} corrections" if n_corr > 0 else ""
            meta.append((label, f"acc={acc_str}{corr_str}"))

        # Accuracy progression
        accs = [
            ag["cell_accuracy_pct"]
            for ag in agents
            if ag["cell_accuracy_pct"] is not None
        ]
        if len(accs) >= 2:
            delta = accs[-1] - accs[0]
            meta.append(("", ""))
            meta.append(("Net Accuracy Change", f"{delta:+.1f}% (transcriber -> synthesizer)"))

        self._set_meta(meta)
        self._show_content("text")
        self.text_display.setPlainText(
            "Click an individual agent to see its output vs ground truth."
        )
        self.status.showMessage(f"Vision agents for {table_id}")

    # ── paddle result display ────────────────────────────────────────────

    def _show_paddle_result(
        self,
        item_key: str,
        table_db_id: int,
        table_id: str,
        paddle_row_id: int,
    ) -> None:
        """Show a paddle engine result in the vision view with diff highlighting."""
        pr = self.conn.execute(
            "SELECT * FROM paddle_results WHERE id=?", (paddle_row_id,)
        ).fetchone()
        if not pr:
            return

        engine_name = pr["engine_name"]

        # Parse headers/rows
        ext_headers: list[str] = []
        ext_rows: list[list[str]] = []
        if pr["headers_json"]:
            try:
                ext_headers = json.loads(pr["headers_json"])
            except (json.JSONDecodeError, TypeError):
                pass
        if pr["rows_json"]:
            try:
                ext_rows = json.loads(pr["rows_json"])
            except (json.JSONDecodeError, TypeError):
                pass

        # Render PDF
        tbl_row = self.conn.execute(
            "SELECT bbox, page_num FROM extracted_tables WHERE id=?", (table_db_id,)
        ).fetchone()
        bbox = json.loads(tbl_row["bbox"]) if tbl_row and tbl_row["bbox"] else None
        pdf_info = self._resolve_pdf_info(table_id, item_key)

        if pdf_info and bbox:
            render_result = self._render_table_pixmap(
                pdf_info["pdf_path"],
                pdf_info["page_num"] or tbl_row["page_num"],
                bbox,
            )
            if render_result:
                clean_pixmap, _ = render_result
                display_pixmap = clean_pixmap
                if display_pixmap.width() > 900:
                    display_pixmap = display_pixmap.scaledToWidth(
                        900, Qt.TransformationMode.SmoothTransformation
                    )
                self.vis_pdf_label.setPixmap(display_pixmap)
                self.vis_pdf_group.setTitle("PDF Region")
            else:
                self.vis_pdf_label.setText("(PDF render failed)")
                self.vis_pdf_label.setPixmap(QPixmap())
        else:
            self.vis_pdf_label.setText("(no PDF available)")
            self.vis_pdf_label.setPixmap(QPixmap())

        # Build metadata
        n_ext_rows = len(ext_rows)
        n_ext_cols = len(ext_headers) if ext_headers else (
            len(ext_rows[0]) if ext_rows else 0
        )
        non_empty = sum(
            1 for row in ext_rows for cell in row if str(cell).strip()
        )
        total = sum(len(row) for row in ext_rows)
        fill_rate = non_empty / total if total else 0.0

        meta: list[tuple[str, str]] = [
            ("Engine", engine_name),
            ("Caption", pr["caption"] or "(none)"),
            ("Orphan", "Yes" if pr["is_orphan"] else "No"),
            ("Page", str(pr["page_num"])),
            ("Grid Shape", f"{n_ext_rows} x {n_ext_cols}"),
            ("Fill Rate", f"{fill_rate:.1%}"),
        ]

        # GT comparison from paddle_gt_diffs
        if self._has_paddle_gt_diffs:
            gtd = self.conn.execute(
                "SELECT * FROM paddle_gt_diffs "
                "WHERE table_id=? AND engine_name=?",
                (table_id, engine_name),
            ).fetchone()
            if gtd:
                meta.extend([
                    ("", ""),
                    ("GT Cell Accuracy", f"{gtd['cell_accuracy_pct']:.1f}%"
                     if gtd["cell_accuracy_pct"] is not None else "N/A"),
                    ("GT Fuzzy Accuracy", f"{gtd['fuzzy_accuracy_pct']:.1f}%"
                     if gtd["fuzzy_accuracy_pct"] is not None else "N/A"),
                    ("Splits", str(gtd["num_splits"])),
                    ("Merges", str(gtd["num_merges"])),
                    ("Cell Diffs", str(gtd["num_cell_diffs"])),
                ])

        self._set_meta(meta)

        # Show in vision view with diff
        short_label = engine_name.replace("paddleocr_", "").replace("pp_structure_", "ppv")
        self.vis_ext_group.setTitle(f"{short_label} Output")
        self._setup_vision_view(table_id, ext_headers, ext_rows)

        self._show_content("vision")
        self.status.showMessage(
            f"Paddle: {engine_name}  {n_ext_rows}x{n_ext_cols}  fill={fill_rate:.0%}"
        )

    def _show_paddle_summary(self, item_key: str, table_id: str) -> None:
        """Show accuracy summary across all paddle engines for a table."""
        if not self._has_paddle_results:
            return

        engines = self.conn.execute(
            "SELECT engine_name FROM paddle_results WHERE table_id=? ORDER BY engine_name",
            (table_id,),
        ).fetchall()

        meta = [("Table ID", table_id)]
        for eng in engines:
            engine_name = eng["engine_name"]
            acc_str = "no GT"
            if self._has_paddle_gt_diffs:
                gtd = self.conn.execute(
                    "SELECT cell_accuracy_pct FROM paddle_gt_diffs "
                    "WHERE table_id=? AND engine_name=?",
                    (table_id, engine_name),
                ).fetchone()
                if gtd and gtd["cell_accuracy_pct"] is not None:
                    acc_str = f"{gtd['cell_accuracy_pct']:.1f}%"
            meta.append((engine_name, f"acc={acc_str}"))

        self._set_meta(meta)
        self._show_content("text")
        self.text_display.setPlainText(
            "Click an individual engine to see its output vs reference."
        )
        self.status.showMessage(f"Paddle engines for {table_id}")

    # ── reference dropdown and vision view helpers ────────────────────────

    def _gather_ref_sources(self, table_id: str) -> list[dict]:
        """Gather all available reference sources for a table_id.

        Returns a list of {label, headers, rows} dicts for populating the
        reference dropdown.
        """
        sources: list[dict] = []

        # 1. Ground Truth
        gt_data = self._load_ground_truth(table_id)
        if gt_data:
            sources.append({
                "label": "Ground Truth",
                "headers": gt_data[0],
                "rows": gt_data[1],
            })

        # 2. Vision transcriber
        if self._has_vision_results:
            vr = self.conn.execute(
                "SELECT headers_json, rows_json FROM vision_agent_results "
                "WHERE table_id=? AND agent_role='transcriber'",
                (table_id,),
            ).fetchone()
            if vr and vr["headers_json"]:
                try:
                    sources.append({
                        "label": "Vision (transcriber)",
                        "headers": json.loads(vr["headers_json"]),
                        "rows": json.loads(vr["rows_json"] or "[]"),
                    })
                except (json.JSONDecodeError, TypeError):
                    pass

        # 3. Paddle engines
        if self._has_paddle_results:
            paddles = self.conn.execute(
                "SELECT engine_name, headers_json, rows_json "
                "FROM paddle_results WHERE table_id=? ORDER BY engine_name",
                (table_id,),
            ).fetchall()
            for pr in paddles:
                if pr["headers_json"]:
                    try:
                        label = pr["engine_name"].replace(
                            "paddleocr_", "PaddleOCR-"
                        ).replace("pp_structure_", "PP-Structure-")
                        sources.append({
                            "label": label,
                            "headers": json.loads(pr["headers_json"]),
                            "rows": json.loads(pr["rows_json"] or "[]"),
                        })
                    except (json.JSONDecodeError, TypeError):
                        pass

        # 4. Pipeline methods (from extracted_tables — the pipeline winner)
        if self._has_table_id_col:
            et = self.conn.execute(
                "SELECT headers_json, rows_json, extraction_strategy "
                "FROM extracted_tables WHERE table_id=?",
                (table_id,),
            ).fetchone()
            if et and et["headers_json"]:
                try:
                    strat = et["extraction_strategy"] or "pipeline"
                    sources.append({
                        "label": f"Pipeline ({strat})",
                        "headers": json.loads(et["headers_json"]),
                        "rows": json.loads(et["rows_json"] or "[]"),
                    })
                except (json.JSONDecodeError, TypeError):
                    pass

        # 5. Individual pipeline methods
        if self._has_method_results:
            methods = self.conn.execute(
                "SELECT method_name, cell_grid_json FROM method_results "
                "WHERE table_id=? AND cell_grid_json IS NOT NULL "
                "ORDER BY quality_score DESC",
                (table_id,),
            ).fetchall()
            for m in methods:
                try:
                    grid = json.loads(m["cell_grid_json"])
                    if grid.get("headers") or grid.get("rows"):
                        sources.append({
                            "label": f"Method: {m['method_name']}",
                            "headers": grid.get("headers", []),
                            "rows": grid.get("rows", []),
                        })
                except (json.JSONDecodeError, TypeError):
                    pass

        return sources

    def _setup_vision_view(
        self,
        table_id: str,
        ext_headers: list[str],
        ext_rows: list[list[str]],
    ) -> None:
        """Set up the vision view with extraction data and populate the
        reference dropdown.  Called by _show_vision_agent and _show_paddle_result."""
        # Store current extraction for dropdown refresh
        self._vis_current_table_id = table_id
        self._vis_current_ext_headers = ext_headers
        self._vis_current_ext_rows = ext_rows

        # Gather reference sources
        self._vis_ref_sources = self._gather_ref_sources(table_id)

        # Populate dropdown (block signals to avoid triggering refresh mid-setup)
        self.vis_ref_combo.blockSignals(True)
        self.vis_ref_combo.clear()
        for src in self._vis_ref_sources:
            self.vis_ref_combo.addItem(src["label"])
        if not self._vis_ref_sources:
            self.vis_ref_combo.addItem("(no references available)")
        self.vis_ref_combo.blockSignals(False)

        # Trigger initial refresh with first reference
        self._refresh_vision_diff()

    def _on_ref_dropdown_changed(self, index: int) -> None:
        """Handle reference dropdown selection change — recalculate diff."""
        self._refresh_vision_diff()

    def _refresh_vision_diff(self) -> None:
        """Recalculate char-level diff between current extraction and selected reference."""
        ext_headers = self._vis_current_ext_headers
        ext_rows = self._vis_current_ext_rows

        # Get selected reference
        ref_idx = self.vis_ref_combo.currentIndex()
        ref_headers: list[str] | None = None
        ref_rows: list[list[str]] | None = None
        ref_label = "(none)"

        if 0 <= ref_idx < len(self._vis_ref_sources):
            src = self._vis_ref_sources[ref_idx]
            ref_headers = src["headers"]
            ref_rows = src["rows"]
            ref_label = src["label"]

        # Populate extracted table with char-level diff
        _populate_diff_table(
            self.vis_ext_table, ext_headers, ext_rows,
            ref_headers, ref_rows,
        )
        self.vis_ext_table.verticalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )

        # Populate reference table (plain, no diff)
        if ref_headers is not None and ref_rows is not None:
            n_ref_cols = len(ref_headers) if ref_headers else (
                len(ref_rows[0]) if ref_rows else 0
            )
            self.vis_ref_group.setTitle(
                f"Reference: {ref_label} ({len(ref_rows)}x{n_ref_cols})"
            )
            _populate_table_widget(
                self.vis_ref_table, ref_headers, ref_rows,
            )
            self.vis_ref_table.verticalHeader().setSectionResizeMode(
                QHeaderView.ResizeMode.ResizeToContents
            )
        else:
            self.vis_ref_table.clear()
            self.vis_ref_table.setRowCount(0)
            self.vis_ref_table.setColumnCount(0)
            self.vis_ref_group.setTitle("Reference (not available)")

    # ── summary views for category nodes ─────────────────────────────────

    def _show_chunks_summary(self, item_key: str):
        rows = self.conn.execute(
            "SELECT section, COUNT(*) as cnt, "
            "MIN(page_num) as first_page, MAX(page_num) as last_page "
            "FROM chunks WHERE item_key=? GROUP BY section ORDER BY MIN(chunk_index)",
            (item_key,),
        ).fetchall()
        meta = [(r["section"], f"{r['cnt']} chunks  (pp {r['first_page']}-{r['last_page']})") for r in rows]
        total = sum(r["cnt"] for r in rows)
        meta.insert(0, ("Total Chunks", str(total)))
        self._set_meta(meta)
        self._show_content("text")
        self.text_display.setPlainText(
            "Click an individual chunk to view its text."
        )

    def _show_tables_summary(self, item_key: str):
        rows = self.conn.execute(
            "SELECT table_index, page_num, caption, num_rows, num_cols, "
            "fill_rate, artifact_type FROM extracted_tables "
            "WHERE item_key=? ORDER BY table_index",
            (item_key,),
        ).fetchall()
        meta = [("Total Tables", str(len(rows)))]
        for r in rows:
            cap = _truncate(r["caption"], 40) or "(no caption)"
            tag = f" [{r['artifact_type']}]" if r["artifact_type"] else ""
            meta.append((
                f"Table {r['table_index']} p{r['page_num']}",
                f"{r['num_rows']}x{r['num_cols']}  fill={r['fill_rate']:.0%}{tag}  {cap}",
            ))
        self._set_meta(meta)
        self._show_content("text")
        self.text_display.setPlainText("Click an individual table to view its data.")

    def _show_figures_summary(self, item_key: str):
        rows = self.conn.execute(
            "SELECT figure_index, page_num, caption, has_image "
            "FROM extracted_figures WHERE item_key=? ORDER BY figure_index",
            (item_key,),
        ).fetchall()
        meta = [("Total Figures", str(len(rows)))]
        with_img = sum(1 for r in rows if r["has_image"])
        meta.append(("With Images", str(with_img)))
        for r in rows:
            cap = _truncate(r["caption"], 50) or "(no caption)"
            img = "img" if r["has_image"] else "no-img"
            meta.append((
                f"Fig {r['figure_index']} p{r['page_num']} [{img}]",
                cap,
            ))
        self._set_meta(meta)
        self._show_content("text")
        self.text_display.setPlainText("Click an individual figure to view it.")

    def _show_tests_summary(self, item_key: str):
        paper = self.conn.execute(
            "SELECT short_name FROM papers WHERE item_key=?", (item_key,)
        ).fetchone()
        if not paper:
            return
        rows = self.conn.execute(
            "SELECT test_name, passed, severity, detail FROM test_results "
            "WHERE paper=? ORDER BY passed, severity DESC",
            (paper["short_name"],),
        ).fetchall()
        failures = [r for r in rows if not r["passed"]]
        meta = [
            ("Total Tests", str(len(rows))),
            ("Passed", str(len(rows) - len(failures))),
            ("Failed", str(len(failures))),
        ]
        self._set_meta(meta)
        self._show_content("text")
        if failures:
            lines = ["FAILURES:\n"]
            for f in failures:
                sev = f"[{f['severity']}] " if f["severity"] else ""
                lines.append(f"  {sev}{f['test_name']}")
                if f["detail"]:
                    lines.append(f"    {f['detail']}\n")
            self.text_display.setPlainText("\n".join(lines))
        else:
            self.text_display.setPlainText("All tests passed.")

    def _show_sections_summary(self, item_key: str):
        rows = self.conn.execute(
            "SELECT label, heading_text, confidence, char_start, char_end "
            "FROM sections WHERE item_key=? ORDER BY char_start",
            (item_key,),
        ).fetchall()
        meta = [("Total Sections", str(len(rows)))]
        for r in rows:
            length = r["char_end"] - r["char_start"]
            heading = _truncate(r["heading_text"], 40) or "(no heading)"
            meta.append((
                f"{r['label']} ({r['confidence']:.0%})",
                f"{heading}  [{length} chars]",
            ))
        self._set_meta(meta)
        self._show_content("text")
        self.text_display.setPlainText(
            "Click an individual section to view its text."
        )


# ── entry point ──────────────────────────────────────────────────────────────


def main():
    db_path = sys.argv[1] if len(sys.argv) > 1 else str(DB_DEFAULT)
    if not os.path.isfile(db_path):
        print(f"Database not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    viewer = DebugViewer(db_path)
    viewer.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
