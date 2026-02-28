"""
Vision pipeline stage viewer.

Displays per-table outputs from each vision agent (transcriber, y_verifier,
x_verifier, synthesizer) side-by-side with ground truth and a rendered PDF
snippet.  Character-level diffs highlight exactly where agent output diverges
from ground truth.

Usage:
    python tools/vision_viewer.py [vision_db] [debug_db] [gt_db]

Defaults (relative to project root):
    vision_db  = _vision_stage_eval.db
    debug_db   = _stress_test_debug.db
    gt_db      = tests/ground_truth.db
"""

from __future__ import annotations

import difflib
import json
import re
import sqlite3
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import (
    QColor,
    QFont,
    QImage,
    QPixmap,
    QTextCharFormat,
    QTextCursor,
)
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

VISION_DB_DEFAULT = PROJECT_ROOT / "_vision_stage_eval.db"
DEBUG_DB_DEFAULT = PROJECT_ROOT / "_stress_test_debug.db"
GT_DB_DEFAULT = PROJECT_ROOT / "tests" / "ground_truth.db"

# Accuracy colour thresholds
_GREEN = QColor("#4caf50")
_YELLOW = QColor("#ffc107")
_ORANGE = QColor("#ff9800")
_RED = QColor("#f44336")

_AGENT_ROLES = ["transcriber", "y_verifier", "x_verifier", "synthesizer"]
_SELECTABLE_ROLES = ["y_verifier", "x_verifier", "synthesizer"]
_ROLE_SHORT = {"transcriber": "T", "y_verifier": "Y", "x_verifier": "X", "synthesizer": "S"}

# ── helpers ──────────────────────────────────────────────────────────────────


def _conn(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _accuracy_color(pct: float | None) -> QColor:
    if pct is None:
        return QColor("#888888")
    if pct >= 95:
        return _GREEN
    if pct >= 80:
        return _YELLOW
    if pct >= 50:
        return _ORANGE
    return _RED


def _safe_json(text: str | None) -> list:
    if not text:
        return []
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return []


def _render_table_png(pdf_path: str, page_num: int, bbox_json: str | list,
                      dpi: int = 200, padding_px: int = 20) -> bytes | None:
    """Render a table region from a PDF page as PNG bytes."""
    try:
        import pymupdf
    except ImportError:
        return None
    bbox = json.loads(bbox_json) if isinstance(bbox_json, str) else bbox_json
    if not bbox or len(bbox) < 4:
        return None
    try:
        doc = pymupdf.open(str(pdf_path))
        page = doc[page_num - 1]  # page_num is 1-indexed
        page_rect = page.rect
        pts_per_px = 72.0 / dpi
        pad = padding_px * pts_per_px
        x0, y0, x1, y1 = bbox
        clip = pymupdf.Rect(
            max(page_rect.x0, x0 - pad), max(page_rect.y0, y0 - pad),
            min(page_rect.x1, x1 + pad), min(page_rect.y1, y1 + pad),
        )
        mat = pymupdf.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat, clip=clip)
        png_bytes = pix.tobytes("png")
        doc.close()
        return png_bytes
    except Exception:
        return None


def _build_norm_index_map(original: str, normalized: str) -> list[int]:
    """Build a mapping from each normalized-string index to the corresponding
    position in the original string.  When normalization collapses characters
    (e.g. ``^{a}`` → ``a``), the mapping assigns the original position of the
    *last* contributing character so that slicing ``original[map[i]:map[j]]``
    covers the full original span.

    Returns a list of length ``len(normalized) + 1`` (the extra entry is the
    sentinel for end-of-string slicing).
    """
    n_map: list[int] = []
    oi = 0
    for ni in range(len(normalized)):
        nc = normalized[ni]
        # Advance through original until we find a character that could produce nc
        while oi < len(original) and _normalize_cell(original[oi]) == "" and original[oi].strip() == "":
            oi += 1
        n_map.append(oi)
        # Skip past the original character(s) that produced this normalized char
        # Simple heuristic: advance at least 1 char in original
        if oi < len(original):
            oi += 1
    n_map.append(len(original))  # sentinel
    return n_map


def _char_diff_html(agent_text: str, gt_text: str) -> str:
    """Return HTML with character-level diff highlighting.

    Normalizes both sides before computing the diff (dash unification,
    ligatures, super/subscripts) so that equivalent representations
    (e.g. U+2212 minus vs ASCII hyphen) don't show as false diffs.

    The diff is computed on normalized text.  For ``equal`` and ``insert``
    opcodes, original agent characters are displayed (so the user sees
    what the agent actually output).  For ``delete`` and ``replace``,
    the missing GT text is shown with strikethrough.

    - Characters matching GT (after normalization): plain black
    - Characters only in agent (insertions): green background
    - Characters missing from agent (deletions): red strikethrough
    """
    norm_agent = _normalize_cell(agent_text)
    norm_gt = _normalize_cell(gt_text)
    if norm_agent == norm_gt:
        return _escape_html(agent_text)

    # Build index maps: normalized index → original string index
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


def _escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace(" ", "&nbsp;")


# ── cell normalization (mirrors ground_truth._normalize_cell) ─────────────

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


# ── main window ──────────────────────────────────────────────────────────────


class VisionViewer(QMainWindow):
    def __init__(
        self,
        vision_db: str | Path,
        debug_db: str | Path,
        gt_db: str | Path,
    ):
        super().__init__()
        self.vision_db = Path(vision_db)
        self.debug_db = Path(debug_db)
        self.gt_db = Path(gt_db)

        # Open connections
        self.v_conn = _conn(self.vision_db) if self.vision_db.exists() else None
        self.d_conn = _conn(self.debug_db) if self.debug_db.exists() else None
        self.gt_conn = _conn(self.gt_db) if self.gt_db.exists() else None

        # Load available runs (most recent first)
        self._runs: list[dict] = []
        self.run_id: str | None = None
        if self.v_conn:
            rows = self.v_conn.execute(
                "SELECT run_id, timestamp, num_papers, num_tables FROM runs "
                "ORDER BY timestamp DESC"
            ).fetchall()
            self._runs = [dict(r) for r in rows]
            if self._runs:
                self.run_id = self._runs[0]["run_id"]

        self.setWindowTitle(
            f"Vision Pipeline Viewer — run {self.run_id or '(none)'}"
        )
        self.resize(1700, 1000)

        # Caches
        self._accuracy_cache: dict[str, dict[str, float | None]] = {}
        self._gt_cache: dict[str, dict] = {}
        self._agent_data_cache: dict[tuple[str, str], dict] = {}

        # Currently selected
        self._current_table_id: str | None = None
        self._current_selected_role: str = "y_verifier"

        self._build_ui()
        self._load_tree()

    # ── UI construction ──────────────────────────────────────────────────

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(4, 4, 4, 4)
        root_layout.setSpacing(4)

        # Info bar at top (two lines: paper info + table details)
        self.info_bar = QLabel("")
        self.info_bar.setFont(QFont("Consolas", 9))
        self.info_bar.setWordWrap(True)
        self.info_bar.setStyleSheet(
            "background: #263238; color: #eceff1; padding: 6px; border-radius: 3px;"
        )
        root_layout.addWidget(self.info_bar)

        # Main splitter: left tree | right content
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        root_layout.addWidget(main_splitter, stretch=1)

        # ── Left panel: tree ────────────────────────────────────────────
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(2)

        # Run selector
        run_row = QHBoxLayout()
        run_row.addWidget(QLabel("Run:"))
        self.run_combo = QComboBox()
        for r in self._runs:
            ts = r["timestamp"][:16].replace("T", " ")
            label = f"{r['run_id']}  ({r['num_papers']}p / {r['num_tables']}t)  {ts}"
            self.run_combo.addItem(label, r["run_id"])
        self.run_combo.currentIndexChanged.connect(self._on_run_changed)
        run_row.addWidget(self.run_combo, stretch=1)
        left_layout.addLayout(run_row)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Table", "T acc", "T→S"])
        self.tree.setColumnWidth(0, 220)
        self.tree.setColumnWidth(1, 55)
        self.tree.setColumnWidth(2, 55)
        self.tree.setMinimumWidth(360)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.itemClicked.connect(self._on_tree_click)
        left_layout.addWidget(self.tree)
        main_splitter.addWidget(left_panel)

        # ── Right panel ─────────────────────────────────────────────────
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)

        # 2x2 grid
        grid_widget = QWidget()
        grid_layout = QGridLayout(grid_widget)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setSpacing(4)

        # (0,0) Top-left: Selected agent
        self.tl_group = QGroupBox("Agent Output")
        tl_inner = QVBoxLayout(self.tl_group)
        tl_inner.setContentsMargins(4, 4, 4, 4)
        tl_inner.setSpacing(2)

        tl_header = QHBoxLayout()
        self.agent_combo = QComboBox()
        for role in _SELECTABLE_ROLES:
            self.agent_combo.addItem(role)
        self.agent_combo.currentTextChanged.connect(self._on_agent_changed)
        tl_header.addWidget(QLabel("Agent:"))
        tl_header.addWidget(self.agent_combo)
        self.tl_header_warn = QLabel("")
        self.tl_header_warn.setStyleSheet("color: #c62828; font-weight: bold;")
        tl_header.addWidget(self.tl_header_warn)
        tl_header.addStretch()
        tl_inner.addLayout(tl_header)

        self.tl_table = QTableWidget()
        self.tl_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tl_table.setAlternatingRowColors(True)
        tl_inner.addWidget(self.tl_table)
        grid_layout.addWidget(self.tl_group, 0, 0)

        # (0,1) Top-right: Transcriber
        self.tr_group = QGroupBox("Transcriber")
        tr_inner = QVBoxLayout(self.tr_group)
        tr_inner.setContentsMargins(4, 4, 4, 4)
        tr_inner.setSpacing(2)
        self.tr_header_warn = QLabel("")
        self.tr_header_warn.setStyleSheet("color: #c62828; font-weight: bold;")
        tr_inner.addWidget(self.tr_header_warn)
        self.tr_table = QTableWidget()
        self.tr_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tr_table.setAlternatingRowColors(True)
        tr_inner.addWidget(self.tr_table)
        grid_layout.addWidget(self.tr_group, 0, 1)

        # (1,0) Bottom-left: Ground Truth
        self.bl_group = QGroupBox("Ground Truth")
        bl_inner = QVBoxLayout(self.bl_group)
        bl_inner.setContentsMargins(4, 4, 4, 4)
        bl_inner.setSpacing(2)
        self.bl_table = QTableWidget()
        self.bl_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.bl_table.setAlternatingRowColors(True)
        bl_inner.addWidget(self.bl_table)
        grid_layout.addWidget(self.bl_group, 1, 0)

        # (1,1) Bottom-right: PNG
        self.br_group = QGroupBox("PDF Table Region")
        br_inner = QVBoxLayout(self.br_group)
        br_inner.setContentsMargins(4, 4, 4, 4)
        br_inner.setSpacing(2)
        self.png_scroll = QScrollArea()
        self.png_scroll.setWidgetResizable(True)
        self.png_label = QLabel("(select a table)")
        self.png_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.png_scroll.setWidget(self.png_label)
        br_inner.addWidget(self.png_scroll)
        grid_layout.addWidget(self.br_group, 1, 1)

        right_layout.addWidget(grid_widget, stretch=1)

        # ── Bottom panels: corrections + footnotes side by side ─────────
        bottom_splitter = QSplitter(Qt.Orientation.Horizontal)

        self.corrections_group = QGroupBox("Corrections Log")
        corr_inner = QVBoxLayout(self.corrections_group)
        corr_inner.setContentsMargins(4, 4, 4, 4)
        self.corrections_text = QTextEdit()
        self.corrections_text.setReadOnly(True)
        self.corrections_text.setFont(QFont("Consolas", 9))
        self.corrections_text.setMaximumHeight(160)
        corr_inner.addWidget(self.corrections_text)
        bottom_splitter.addWidget(self.corrections_group)

        self.footnotes_group = QGroupBox("Footnotes")
        fn_inner = QVBoxLayout(self.footnotes_group)
        fn_inner.setContentsMargins(4, 4, 4, 4)
        fn_header = QHBoxLayout()
        fn_header.addWidget(QLabel("Agent:"))
        self.fn_agent_combo = QComboBox()
        for role in _AGENT_ROLES:
            self.fn_agent_combo.addItem(role)
        self.fn_agent_combo.currentTextChanged.connect(self._on_fn_agent_changed)
        fn_header.addWidget(self.fn_agent_combo, stretch=1)
        fn_inner.addLayout(fn_header)
        self.footnotes_text = QTextEdit()
        self.footnotes_text.setReadOnly(True)
        self.footnotes_text.setFont(QFont("Consolas", 9))
        self.footnotes_text.setMaximumHeight(160)
        fn_inner.addWidget(self.footnotes_text)
        bottom_splitter.addWidget(self.footnotes_group)

        bottom_splitter.setSizes([600, 600])
        right_layout.addWidget(bottom_splitter, stretch=0)

        main_splitter.addWidget(right_panel)
        main_splitter.setSizes([320, 1380])

    # ── data loading ─────────────────────────────────────────────────────

    def _get_accuracy(self, table_id: str) -> dict[str, float | None]:
        """Return {role: cell_accuracy_pct} for a table."""
        if table_id in self._accuracy_cache:
            return self._accuracy_cache[table_id]
        result: dict[str, float | None] = {r: None for r in _AGENT_ROLES}
        if self.v_conn and self.run_id:
            rows = self.v_conn.execute(
                "SELECT agent_role, cell_accuracy_pct FROM gt_comparisons "
                "WHERE run_id = ? AND table_id = ?",
                (self.run_id, table_id),
            ).fetchall()
            for r in rows:
                result[r["agent_role"]] = r["cell_accuracy_pct"]
        self._accuracy_cache[table_id] = result
        return result

    def _get_agent_data(self, table_id: str, role: str) -> dict:
        """Return agent output for a table + role."""
        key = (table_id, role)
        if key in self._agent_data_cache:
            return self._agent_data_cache[key]
        result = {"headers": [], "rows": [], "footnotes": "", "shape": "", "parse_success": 1}
        if self.v_conn and self.run_id:
            row = self.v_conn.execute(
                "SELECT headers_json, rows_json, footnotes, shape, parse_success "
                "FROM agent_outputs WHERE run_id = ? AND table_id = ? AND agent_role = ?",
                (self.run_id, table_id, role),
            ).fetchone()
            if row:
                result["headers"] = _safe_json(row["headers_json"])
                result["rows"] = _safe_json(row["rows_json"])
                result["footnotes"] = row["footnotes"] or ""
                result["shape"] = row["shape"] or ""
                result["parse_success"] = row["parse_success"]
        self._agent_data_cache[key] = result
        return result

    def _get_ts_similarity(self, table_id: str) -> float | None:
        """Compute cell-level similarity between transcriber and synthesizer.

        Returns percentage of matching cells (0-100), or None if data missing.
        Works regardless of whether GT exists.
        """
        t = self._get_agent_data(table_id, "transcriber")
        s = self._get_agent_data(table_id, "synthesizer")
        if not t["rows"] and not s["rows"]:
            return None
        # Compare headers + rows cell-by-cell
        t_cells = [c for c in t["headers"]] + [c for row in t["rows"] for c in row]
        s_cells = [c for c in s["headers"]] + [c for row in s["rows"] for c in row]
        if not t_cells and not s_cells:
            return None
        total = max(len(t_cells), len(s_cells))
        if total == 0:
            return None
        matches = sum(
            1 for a, b in zip(t_cells, s_cells)
            if str(a).strip() == str(b).strip()
        )
        return 100.0 * matches / total

    def _get_gt(self, table_id: str) -> dict | None:
        """Return ground truth data for a table, or None."""
        if table_id in self._gt_cache:
            return self._gt_cache[table_id]
        result = None
        if self.gt_conn:
            row = self.gt_conn.execute(
                "SELECT headers_json, rows_json, footnotes, num_rows, num_cols "
                "FROM ground_truth_tables WHERE table_id = ?",
                (table_id,),
            ).fetchone()
            if row:
                result = {
                    "headers": _safe_json(row["headers_json"]),
                    "rows": _safe_json(row["rows_json"]),
                    "footnotes": row["footnotes"] or "",
                    "shape": f"{row['num_rows']}x{row['num_cols']}",
                }
        self._gt_cache[table_id] = result
        return result

    def _get_gt_comparison(self, table_id: str, role: str) -> dict | None:
        """Return gt_comparisons row for table+role."""
        if not self.v_conn or not self.run_id:
            return None
        row = self.v_conn.execute(
            "SELECT * FROM gt_comparisons WHERE run_id = ? AND table_id = ? AND agent_role = ?",
            (self.run_id, table_id, role),
        ).fetchone()
        if row:
            return dict(row)
        return None

    def _get_pdf_info(self, table_id: str) -> tuple[str | None, int | None, str | None]:
        """Return (pdf_path, page_num, bbox_json) from debug DB or vision DB."""
        paper_key = table_id.split("_")[0] if table_id else None
        if not paper_key:
            return None, None, None

        pdf_path = None
        page_num = None
        bbox = None

        # Try debug DB first
        if self.d_conn:
            paper = self.d_conn.execute(
                "SELECT pdf_path FROM papers WHERE item_key = ?", (paper_key,)
            ).fetchone()
            if paper:
                pdf_path = paper["pdf_path"]
            et = self.d_conn.execute(
                "SELECT page_num, bbox FROM extracted_tables WHERE table_id = ?",
                (table_id,),
            ).fetchone()
            if et:
                page_num, bbox = et["page_num"], et["bbox"]

        # Fall back to vision DB (papers/extracted_tables written by eval script)
        if self.v_conn and (pdf_path is None or page_num is None):
            if pdf_path is None:
                paper = self.v_conn.execute(
                    "SELECT pdf_path FROM papers WHERE item_key = ?", (paper_key,)
                ).fetchone()
                if paper:
                    pdf_path = paper["pdf_path"]
            if page_num is None:
                et = self.v_conn.execute(
                    "SELECT page_num, bbox FROM extracted_tables WHERE table_id = ?",
                    (table_id,),
                ).fetchone()
                if et:
                    page_num, bbox = et["page_num"], et["bbox"]

        return pdf_path, page_num, bbox

    def _get_corrections(self, table_id: str) -> list[dict]:
        """Return correction_log entries for a table."""
        if not self.v_conn or not self.run_id:
            return []
        rows = self.v_conn.execute(
            "SELECT agent_role, correction_index, correction_text "
            "FROM correction_log WHERE run_id = ? AND table_id = ? "
            "ORDER BY agent_role, correction_index",
            (self.run_id, table_id),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── tree ─────────────────────────────────────────────────────────────

    def _load_tree(self) -> None:
        self.tree.clear()
        if not self.v_conn or not self.run_id:
            return

        # Get all table_ids for this run, grouped by paper_key
        rows = self.v_conn.execute(
            "SELECT DISTINCT table_id FROM agent_outputs WHERE run_id = ? ORDER BY table_id",
            (self.run_id,),
        ).fetchall()

        # Group by paper_key (first segment before _)
        papers: dict[str, list[str]] = {}
        for r in rows:
            tid = r["table_id"]
            pkey = tid.split("_")[0]
            papers.setdefault(pkey, []).append(tid)

        # Resolve paper short_name from debug DB, falling back to vision DB
        paper_names: dict[str, str] = {}
        for pkey in papers:
            found = False
            if self.d_conn:
                p = self.d_conn.execute(
                    "SELECT short_name FROM papers WHERE item_key = ?", (pkey,)
                ).fetchone()
                if p:
                    paper_names[pkey] = p["short_name"]
                    found = True
            if not found and self.v_conn:
                p = self.v_conn.execute(
                    "SELECT short_name FROM papers WHERE item_key = ?", (pkey,)
                ).fetchone()
                if p:
                    paper_names[pkey] = p["short_name"]

        for pkey in sorted(papers.keys()):
            name = paper_names.get(pkey, pkey)
            parent = QTreeWidgetItem(self.tree, [name, "", ""])
            parent.setData(0, Qt.ItemDataRole.UserRole, None)  # Not a table
            parent.setExpanded(True)

            for tid in papers[pkey]:
                acc = self._get_accuracy(tid)
                t_acc = acc.get("transcriber")
                has_gt = self._get_gt(tid) is not None

                if t_acc is not None:
                    acc_str = f"{t_acc:.1f}%"
                else:
                    acc_str = "no GT" if not has_gt else "N/A"

                # T→S column: cell-level similarity (100% = no edits)
                ts_sim = self._get_ts_similarity(tid)
                if ts_sim is not None:
                    delta_str = f"{ts_sim:.0f}%"
                else:
                    delta_str = ""

                label = tid.replace(f"{pkey}_", "")  # Shorten display
                child = QTreeWidgetItem(parent, [label, acc_str, delta_str])
                child.setData(0, Qt.ItemDataRole.UserRole, tid)

                # Color-code by transcriber accuracy (grey for no-GT tables)
                color = _accuracy_color(t_acc)
                child.setForeground(0, color)
                child.setForeground(1, color)

                # Color-code T→S: green if identical, red if heavily edited
                if ts_sim is not None:
                    if ts_sim >= 99.5:
                        child.setForeground(2, _GREEN)  # no edits
                    elif ts_sim >= 90:
                        child.setForeground(2, _YELLOW)  # minor edits
                    elif ts_sim >= 70:
                        child.setForeground(2, _ORANGE)  # moderate edits
                    else:
                        child.setForeground(2, _RED)  # heavy edits

    # ── event handlers ───────────────────────────────────────────────────

    def _on_run_changed(self, index: int) -> None:
        if index < 0 or index >= len(self._runs):
            return
        self.run_id = self._runs[index]["run_id"]
        self.setWindowTitle(
            f"Vision Pipeline Viewer — run {self.run_id}"
        )
        # Clear caches and reload
        self._accuracy_cache.clear()
        self._gt_cache.clear()
        self._agent_data_cache.clear()
        self._current_table_id = None
        self._load_tree()

    def _on_tree_click(self, item: QTreeWidgetItem, column: int) -> None:
        table_id = item.data(0, Qt.ItemDataRole.UserRole)
        if not table_id:
            return
        self._current_table_id = table_id
        self._refresh_all()

    def _on_agent_changed(self, role: str) -> None:
        self._current_selected_role = role
        if self._current_table_id:
            self._refresh_tl()
            self._refresh_info_bar()

    def _on_fn_agent_changed(self, role: str) -> None:
        if self._current_table_id:
            self._refresh_footnotes()

    # ── refresh methods ──────────────────────────────────────────────────

    def _refresh_all(self) -> None:
        tid = self._current_table_id
        if not tid:
            return
        self._refresh_info_bar()
        self._refresh_tl()
        self._refresh_tr()
        self._refresh_bl()
        self._refresh_png()
        self._refresh_corrections()
        self._refresh_footnotes()

    def _get_paper_meta(self, paper_key: str) -> dict:
        """Return paper metadata (title, year, authors) from vision or debug DB."""
        meta = {"title": "", "year": None, "authors": ""}
        row = None
        # Try vision DB first (has title, year)
        if self.v_conn:
            row = self.v_conn.execute(
                "SELECT title, year, pdf_path FROM papers WHERE item_key = ?",
                (paper_key,),
            ).fetchone()
        if not row and self.d_conn:
            row = self.d_conn.execute(
                "SELECT short_name as title, '' as pdf_path FROM papers WHERE item_key = ?",
                (paper_key,),
            ).fetchone()
        if row:
            meta["title"] = row["title"] or ""
            meta["year"] = row["year"] if "year" in row.keys() else None
            # Parse author from PDF filename: "Smith et al. - 2022 - Title.pdf"
            pdf_path = row["pdf_path"] if "pdf_path" in row.keys() else ""
            if pdf_path:
                fname = Path(pdf_path).stem
                dash_split = fname.split(" - ")
                if len(dash_split) >= 2:
                    meta["authors"] = dash_split[0].strip()
        return meta

    def _refresh_info_bar(self) -> None:
        tid = self._current_table_id
        if not tid:
            self.info_bar.setText("")
            return

        pkey = tid.split("_")[0]
        paper = self._get_paper_meta(pkey)
        acc = self._get_accuracy(tid)
        gt = self._get_gt(tid)
        gt_cmp = self._get_gt_comparison(tid, "transcriber")

        # Line 1: paper info
        paper_parts = []
        if paper["authors"]:
            paper_parts.append(paper["authors"])
        if paper["year"]:
            paper_parts.append(f"({paper['year']})")
        if paper["title"]:
            # Truncate long titles
            t = paper["title"]
            paper_parts.append(t[:90] + "..." if len(t) > 90 else t)
        paper_line = " ".join(paper_parts) if paper_parts else pkey

        # Line 2: table details
        detail_parts = [f"Table: {tid}"]
        if gt:
            detail_parts.append(f"GT shape: {gt['shape']}")
        else:
            detail_parts.append("NO GT — diffs vs Transcriber")
        if gt_cmp:
            detail_parts.append(f"Ext shape: {gt_cmp.get('ext_shape', '?')}")
            scov = gt_cmp.get("structural_coverage_pct")
            if scov is not None:
                detail_parts.append(f"Coverage: {scov:.1f}%")

        # Accuracy row
        acc_parts = []
        for role in _AGENT_ROLES:
            short = _ROLE_SHORT[role]
            val = acc.get(role)
            acc_parts.append(f"{short}: {val:.1f}%" if val is not None else f"{short}: N/A")
        detail_parts.append(" | ".join(acc_parts))

        self.info_bar.setText(f"{paper_line}\n{'    '.join(detail_parts)}")

    def _refresh_tl(self) -> None:
        """Refresh top-left: selected agent output with diff highlighting.

        When ground truth exists, diffs are against GT.  When GT is absent,
        diffs are against the transcriber output so the user can see what the
        later stages changed.
        """
        tid = self._current_table_id
        role = self._current_selected_role
        if not tid:
            return

        data = self._get_agent_data(tid, role)
        gt = self._get_gt(tid)
        acc = self._get_accuracy(tid)
        role_acc = acc.get(role)

        title = f"{role}"
        if role_acc is not None:
            title += f" ({role_acc:.1f}%)"

        if gt is not None:
            self.tl_group.setTitle(title)
            self._populate_diff_table(self.tl_table, data, gt, self.tl_header_warn)
        else:
            # No GT — diff against transcriber instead
            transcriber = self._get_agent_data(tid, "transcriber")
            ref = {
                "headers": transcriber["headers"],
                "rows": transcriber["rows"],
                "footnotes": transcriber["footnotes"],
            }
            self.tl_group.setTitle(f"{title}  [diff vs Transcriber]")
            self._populate_diff_table(
                self.tl_table, data, ref, self.tl_header_warn,
                reference_label="Transcriber",
            )

    def _refresh_tr(self) -> None:
        """Refresh top-right: transcriber output.

        When GT exists, diffs are shown against GT.  When GT is absent the
        transcriber IS the reference, so it is displayed plain.
        """
        tid = self._current_table_id
        if not tid:
            return

        data = self._get_agent_data(tid, "transcriber")
        gt = self._get_gt(tid)
        acc = self._get_accuracy(tid)
        t_acc = acc.get("transcriber")

        title = "Transcriber"
        if t_acc is not None:
            title += f" ({t_acc:.1f}%)"
        if gt is None:
            title += "  [REFERENCE]"
        self.tr_group.setTitle(title)

        # When no GT, show plain (transcriber is the reference — nothing to diff against)
        self._populate_diff_table(self.tr_table, data, gt, self.tr_header_warn)

    def _refresh_bl(self) -> None:
        """Refresh bottom-left: ground truth (plain, no diff)."""
        tid = self._current_table_id
        if not tid:
            return

        gt = self._get_gt(tid)
        if not gt:
            self.bl_group.setTitle("Ground Truth (not available)")
            self.bl_table.clear()
            self.bl_table.setRowCount(2)
            self.bl_table.setColumnCount(1)
            msg = QTableWidgetItem("No ground truth for this table")
            msg.setForeground(QColor("#888888"))
            self.bl_table.setItem(0, 0, msg)
            hint = QTableWidgetItem(
                "Left pane diffs are against Transcriber output"
            )
            hint.setForeground(QColor("#64b5f6"))
            self.bl_table.setItem(1, 0, hint)
            self.bl_table.setHorizontalHeaderLabels([""])
            self.bl_table.resizeColumnsToContents()
            return

        self.bl_group.setTitle(f"Ground Truth ({gt['shape']})")
        headers = gt["headers"]
        rows = gt["rows"]
        n_cols = len(headers) if headers else (len(rows[0]) if rows else 0)
        total_rows = 1 + len(rows)  # header row + data rows

        self.bl_table.clear()
        self.bl_table.setColumnCount(n_cols)
        self.bl_table.setRowCount(total_rows)
        self.bl_table.setHorizontalHeaderLabels([str(i) for i in range(n_cols)])

        # Row 0: headers (bold, light grey bg)
        for c, h in enumerate(headers):
            item = QTableWidgetItem(str(h))
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            item.setBackground(QColor("#e0e0e0"))
            self.bl_table.setItem(0, c, item)

        # Data rows
        for r_idx, row in enumerate(rows):
            for c_idx, cell in enumerate(row):
                if c_idx < n_cols:
                    self.bl_table.setItem(r_idx + 1, c_idx, QTableWidgetItem(str(cell)))

        self.bl_table.resizeColumnsToContents()

    def _refresh_png(self) -> None:
        """Refresh bottom-right: rendered PDF table region."""
        tid = self._current_table_id
        if not tid:
            return

        pdf_path, page_num, bbox = self._get_pdf_info(tid)
        if not pdf_path or not page_num or not bbox:
            self.br_group.setTitle("PDF Table Region (not available)")
            self.png_label.setText("PNG not available — missing PDF path or bbox")
            self.png_label.setPixmap(QPixmap())
            return

        png_bytes = _render_table_png(pdf_path, page_num, bbox)
        if not png_bytes:
            self.br_group.setTitle("PDF Table Region (render failed)")
            self.png_label.setText("PNG rendering failed")
            self.png_label.setPixmap(QPixmap())
            return

        self.br_group.setTitle(f"PDF Table Region (page {page_num})")
        img = QImage()
        img.loadFromData(png_bytes)
        pixmap = QPixmap.fromImage(img)

        # Scale to fit the scroll area while preserving aspect ratio
        available = self.png_scroll.size()
        scaled = pixmap.scaled(
            available, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.png_label.setPixmap(scaled)

    def _refresh_corrections(self) -> None:
        """Refresh corrections panel."""
        tid = self._current_table_id
        if not tid:
            self.corrections_text.clear()
            return

        corrections = self._get_corrections(tid)
        if not corrections:
            self.corrections_text.setPlainText("(no corrections for this table)")
            return

        lines = []
        current_role = None
        for c in corrections:
            role = c["agent_role"]
            if role != current_role:
                if current_role is not None:
                    lines.append("")
                lines.append(f"=== {role} ===")
                current_role = role
            lines.append(f"  [{c['correction_index']}] {c['correction_text']}")

        self.corrections_text.setPlainText("\n".join(lines))

    def _refresh_footnotes(self) -> None:
        """Refresh footnotes panel for the selected agent."""
        tid = self._current_table_id
        if not tid:
            self.footnotes_text.clear()
            return

        role = self.fn_agent_combo.currentText()
        data = self._get_agent_data(tid, role)
        fn = data.get("footnotes", "")

        # Also show GT footnotes for comparison if available
        gt = self._get_gt(tid)
        gt_fn = gt.get("footnotes", "") if gt else ""

        parts = []
        if fn:
            parts.append(f"[{role}]\n{fn}")
        else:
            parts.append(f"[{role}]\n(none)")

        if gt_fn:
            parts.append(f"\n[Ground Truth]\n{gt_fn}")

        self.footnotes_text.setPlainText("\n".join(parts))

    # ── diff table population ────────────────────────────────────────────

    def _populate_diff_table(
        self,
        widget: QTableWidget,
        agent_data: dict,
        gt: dict | None,
        header_warn_label: QLabel,
        reference_label: str = "GT",
    ) -> None:
        """Populate a QTableWidget with agent data, applying character-level
        diff highlighting against a reference (ground truth or transcriber)."""
        widget.clear()
        headers = agent_data["headers"]
        rows = agent_data["rows"]
        n_cols = len(headers) if headers else (len(rows[0]) if rows else 0)
        total_rows = 1 + len(rows)  # header row + data rows

        if n_cols == 0 and len(rows) == 0:
            widget.setRowCount(1)
            widget.setColumnCount(1)
            widget.setHorizontalHeaderLabels([""])
            item = QTableWidgetItem("No data")
            item.setForeground(QColor("#888888"))
            widget.setItem(0, 0, item)
            header_warn_label.setText("")
            return

        widget.setColumnCount(n_cols)
        widget.setRowCount(total_rows)
        widget.setHorizontalHeaderLabels([str(i) for i in range(n_cols)])

        gt_headers = gt["headers"] if gt else []
        gt_rows = gt["rows"] if gt else []
        has_gt = gt is not None

        # Check for header mismatches (using normalization)
        header_mismatch = False
        if has_gt:
            for c in range(min(len(headers), len(gt_headers))):
                if _normalize_cell(str(headers[c])) != _normalize_cell(str(gt_headers[c])):
                    header_mismatch = True
                    break
            if len(headers) != len(gt_headers):
                header_mismatch = True

        if header_mismatch:
            header_warn_label.setText(f"!! Headers differ from {reference_label}")
        else:
            header_warn_label.setText("")

        # Row 0: headers
        for c, h in enumerate(headers):
            h_str = str(h)
            gt_h_str = str(gt_headers[c]).strip() if has_gt and c < len(gt_headers) else None

            item = QTableWidgetItem()
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            item.setBackground(QColor("#e0e0e0"))

            if has_gt and gt_h_str is not None and _normalize_cell(h_str) != _normalize_cell(gt_h_str):
                # Header mismatch: red border tint
                item.setBackground(QColor("#ffcdd2"))
                item.setText(h_str)
            else:
                item.setText(h_str)

            widget.setItem(0, c, item)

        # Data rows with diff highlighting
        for r_idx, row in enumerate(rows):
            gt_row = gt_rows[r_idx] if has_gt and r_idx < len(gt_rows) else None
            for c_idx, cell in enumerate(row):
                if c_idx >= n_cols:
                    continue
                cell_str = str(cell)
                gt_cell_str = (
                    str(gt_row[c_idx]).strip()
                    if gt_row is not None and c_idx < len(gt_row)
                    else None
                )

                if has_gt and gt_cell_str is not None and _normalize_cell(cell_str) != _normalize_cell(gt_cell_str):
                    # Cells differ after normalization -- use rich text via QTextEdit
                    diff_html = _char_diff_html(cell_str.strip(), gt_cell_str)
                    te = QTextEdit()
                    te.setReadOnly(True)
                    te.setFrameStyle(0)
                    te.setHtml(
                        f'<span style="font-family:Consolas;font-size:9pt;">{diff_html}</span>'
                    )
                    te.setVerticalScrollBarPolicy(
                        Qt.ScrollBarPolicy.ScrollBarAlwaysOff
                    )
                    te.setHorizontalScrollBarPolicy(
                        Qt.ScrollBarPolicy.ScrollBarAlwaysOff
                    )
                    widget.setCellWidget(r_idx + 1, c_idx, te)
                else:
                    item = QTableWidgetItem(cell_str)
                    widget.setItem(r_idx + 1, c_idx, item)

        widget.resizeColumnsToContents()
        widget.resizeRowsToContents()


# ── entry point ──────────────────────────────────────────────────────────────


def main() -> None:
    args = sys.argv[1:]
    vision_db = Path(args[0]) if len(args) > 0 else VISION_DB_DEFAULT
    debug_db = Path(args[1]) if len(args) > 1 else DEBUG_DB_DEFAULT
    gt_db = Path(args[2]) if len(args) > 2 else GT_DB_DEFAULT

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Dark-ish palette to match debug_viewer feel
    font = QFont("Segoe UI", 9)
    app.setFont(font)

    window = VisionViewer(vision_db, debug_db, gt_db)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
