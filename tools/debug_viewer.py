"""
Stress-test debug database viewer.

Usage:
    python tools/debug_viewer.py [path_to_db]

If no path given, defaults to _stress_test_debug.db in the project root.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap, QFont, QColor, QIcon
from PyQt6.QtWidgets import (
    QApplication,
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


# ── main window ──────────────────────────────────────────────────────────────


class DebugViewer(QMainWindow):
    def __init__(self, db_path: str | Path):
        super().__init__()
        self.db_path = Path(db_path)
        self.conn = _conn(self.db_path)
        self.setWindowTitle(f"Extraction Debug Viewer — {self.db_path.name}")
        self.resize(1600, 950)

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
        """Show one of: 'text', 'image', 'table'."""
        self.text_display.setVisible(mode == "text")
        self.image_scroll.setVisible(mode == "image")
        self.rendered_table.setVisible(mode == "table")

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
