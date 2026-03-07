"""
ChromaDB index browser for DeepZotero.

Usage:
    python tools/debug_viewer.py [chroma_db_path] [--zotero-dir PATH]

If no chroma path given, defaults to ~/.local/share/deep-zotero/chroma.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap, QFont, QColor, QImage
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
)

CHROMA_DEFAULT = Path("~/.local/share/deep-zotero/chroma").expanduser()
ZOTERO_DEFAULT = Path("~/Zotero").expanduser()

GRADE_COLOURS = {
    "A": "#4caf50",
    "B": "#8bc34a",
    "C": "#ffc107",
    "D": "#ff9800",
    "F": "#f44336",
}


# -- helpers ------------------------------------------------------------------


def _truncate(text: str, length: int = 80) -> str:
    if not text:
        return ""
    text = text.replace("\n", " ").strip()
    return text[:length] + "..." if len(text) > length else text


def _populate_meta_table(
    widget: QTableWidget,
    rows: list[tuple[str, str]],
) -> None:
    """Fill a two-column key/value metadata table."""
    widget.clear()
    widget.setColumnCount(2)
    widget.setRowCount(len(rows))
    widget.setHorizontalHeaderLabels(["Field", "Value"])
    for r_idx, (key, val) in enumerate(rows):
        k_item = QTableWidgetItem(key)
        k_item.setFont(_bold_font())
        widget.setItem(r_idx, 0, k_item)
        widget.setItem(r_idx, 1, QTableWidgetItem(str(val)))
    widget.resizeColumnsToContents()
    header = widget.horizontalHeader()
    if header:
        header.setStretchLastSection(True)


def _bold_font() -> QFont:
    f = QFont()
    f.setBold(True)
    return f


# -- data loading -------------------------------------------------------------


def _load_chroma_data(chroma_path: Path) -> dict:
    """Load all items from the ChromaDB chunks collection.

    Returns a dict keyed by doc_id, each value being:
        {
            "title": str,
            "authors": str,
            "year": str,
            "collections": str,
            "quality_grade": str,
            "tables": [{"id": str, "meta": dict, "document": str}, ...],
            "figures": [{"id": str, "meta": dict, "document": str}, ...],
            "chunks": [{"id": str, "meta": dict, "document": str}, ...],
        }
    """
    import chromadb
    from chromadb.config import Settings

    client = chromadb.PersistentClient(
        path=str(chroma_path),
        settings=Settings(anonymized_telemetry=False),
    )
    collection = client.get_collection("chunks")
    result = collection.get(include=["documents", "metadatas"])

    papers: dict[str, dict] = {}

    ids = result["ids"] or []
    documents = result["documents"] or []
    metadatas = result["metadatas"] or []

    for item_id, doc, meta in zip(ids, documents, metadatas):
        if not meta:
            continue
        doc_id = meta.get("doc_id", "unknown")
        if doc_id not in papers:
            papers[doc_id] = {
                "title": meta.get("doc_title", ""),
                "authors": meta.get("authors", ""),
                "year": str(meta.get("year", "")),
                "collections": meta.get("collections", ""),
                "quality_grade": meta.get("quality_grade", ""),
                "tables": [],
                "figures": [],
                "chunks": [],
            }
        paper = papers[doc_id]
        chunk_type = meta.get("chunk_type", "text")
        entry = {"id": item_id, "meta": meta, "document": doc or ""}

        if chunk_type == "table":
            paper["tables"].append(entry)
        elif chunk_type == "figure":
            paper["figures"].append(entry)
        else:
            paper["chunks"].append(entry)

    # Sort artifacts within each paper
    for paper in papers.values():
        paper["tables"].sort(key=lambda x: (
            x["meta"].get("page_num", 0),
            x["meta"].get("table_index", 0),
        ))
        paper["figures"].sort(key=lambda x: (
            x["meta"].get("page_num", 0),
            x["meta"].get("figure_index", 0),
        ))
        paper["chunks"].sort(key=lambda x: (
            x["meta"].get("page_num", 0),
            x["meta"].get("chunk_index", 0),
        ))

    return papers


# -- main window --------------------------------------------------------------


class IndexViewer(QMainWindow):
    def __init__(self, chroma_path: Path, zotero_dir: Path):
        super().__init__()
        self.chroma_path = chroma_path
        self.zotero_dir = zotero_dir
        self.setWindowTitle("DeepZotero Index Viewer")
        self.resize(1600, 950)

        # Lazy-loaded resources
        self._pymupdf = None
        self._zotero_client = None
        self._pdf_cache: dict[str, Path | None] = {}  # doc_id -> pdf_path

        # Load data
        self.papers = _load_chroma_data(chroma_path)

        # -- layout -----------------------------------------------------------
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(4, 4, 4, 4)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        # Left: tree
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Index Contents")
        self.tree.setMinimumWidth(380)
        self.tree.itemClicked.connect(self._on_tree_click)
        splitter.addWidget(self.tree)

        # Right: detail panel
        self.right_panel = QWidget()
        self.right_layout = QVBoxLayout(self.right_panel)
        self.right_layout.setContentsMargins(4, 4, 4, 4)

        # Metadata table (always visible at top)
        self.meta_table = QTableWidget()
        self.meta_table.setMaximumHeight(200)
        self.meta_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.meta_table.verticalHeader().setVisible(False)
        self.right_layout.addWidget(self.meta_table)

        # Content area (stacked: text, table-splitter, or figure display)
        self.content_area = QWidget()
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.right_layout.addWidget(self.content_area, stretch=1)

        splitter.addWidget(self.right_panel)
        splitter.setSizes([380, 1220])

        # Build tree
        self._build_tree()

        # Status bar
        total_items = sum(
            len(p["tables"]) + len(p["figures"]) + len(p["chunks"])
            for p in self.papers.values()
        )
        self.statusBar().showMessage(
            f"Loaded {len(self.papers)} papers, {total_items} total items from {chroma_path}"
        )

    # -- tree building --------------------------------------------------------

    def _build_tree(self) -> None:
        self.tree.clear()

        # Sort papers by title
        sorted_papers = sorted(
            self.papers.items(),
            key=lambda kv: kv[1]["title"].lower(),
        )

        for doc_id, paper in sorted_papers:
            grade = paper["quality_grade"] or "?"
            title_short = _truncate(paper["title"], 50)
            paper_node = QTreeWidgetItem(self.tree)
            paper_node.setText(0, f'{title_short} ({doc_id}) [Grade: {grade}]')
            paper_node.setData(0, Qt.ItemDataRole.UserRole, ("paper", doc_id))

            # Colour grade
            colour = GRADE_COLOURS.get(grade, "#999999")
            paper_node.setForeground(0, QColor(colour))

            # Tables
            if paper["tables"]:
                tables_node = QTreeWidgetItem(paper_node)
                tables_node.setText(0, f'Tables ({len(paper["tables"])})')
                tables_node.setData(0, Qt.ItemDataRole.UserRole, None)
                for i, tbl in enumerate(paper["tables"]):
                    m = tbl["meta"]
                    caption = _truncate(m.get("table_caption", ""), 50)
                    page = m.get("page_num", "?")
                    node = QTreeWidgetItem(tables_node)
                    node.setText(0, f'Table {i + 1}: "{caption}" (p.{page})')
                    node.setData(0, Qt.ItemDataRole.UserRole, ("table", doc_id, i))

            # Figures
            if paper["figures"]:
                figs_node = QTreeWidgetItem(paper_node)
                figs_node.setText(0, f'Figures ({len(paper["figures"])})')
                figs_node.setData(0, Qt.ItemDataRole.UserRole, None)
                for i, fig in enumerate(paper["figures"]):
                    m = fig["meta"]
                    caption = _truncate(m.get("caption", ""), 50)
                    page = m.get("page_num", "?")
                    node = QTreeWidgetItem(figs_node)
                    node.setText(0, f'Figure {i + 1}: "{caption}" (p.{page})')
                    node.setData(0, Qt.ItemDataRole.UserRole, ("figure", doc_id, i))

            # Chunks
            if paper["chunks"]:
                chunks_node = QTreeWidgetItem(paper_node)
                chunks_node.setText(0, f'Chunks ({len(paper["chunks"])})')
                chunks_node.setData(0, Qt.ItemDataRole.UserRole, None)
                for i, chunk in enumerate(paper["chunks"]):
                    m = chunk["meta"]
                    section = m.get("section", "")
                    page = m.get("page_num", "?")
                    node = QTreeWidgetItem(chunks_node)
                    node.setText(0, f'Chunk {i}: {section} (p.{page})')
                    node.setData(0, Qt.ItemDataRole.UserRole, ("chunk", doc_id, i))

    # -- event handling -------------------------------------------------------

    def _on_tree_click(self, item: QTreeWidgetItem, column: int) -> None:
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data is None:
            return

        kind = data[0]
        if kind == "paper":
            self._show_paper(data[1])
        elif kind == "table":
            self._show_table(data[1], data[2])
        elif kind == "figure":
            self._show_figure(data[1], data[2])
        elif kind == "chunk":
            self._show_chunk(data[1], data[2])

    # -- clear content area ---------------------------------------------------

    def _clear_content(self) -> None:
        while self.content_layout.count():
            child = self.content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    # -- display: paper -------------------------------------------------------

    def _show_paper(self, doc_id: str) -> None:
        paper = self.papers[doc_id]
        meta = [
            ("Document ID", doc_id),
            ("Title", paper["title"]),
            ("Authors", paper["authors"]),
            ("Year", paper["year"]),
            ("Collections", paper["collections"]),
            ("Quality Grade", paper["quality_grade"] or "?"),
            ("Text Chunks", str(len(paper["chunks"]))),
            ("Tables", str(len(paper["tables"]))),
            ("Figures", str(len(paper["figures"]))),
        ]
        _populate_meta_table(self.meta_table, meta)

        self._clear_content()
        label = QLabel(
            f"Select a table, figure, or chunk from the tree to view details.\n\n"
            f"This paper has {len(paper['chunks'])} text chunks, "
            f"{len(paper['tables'])} tables, and {len(paper['figures'])} figures."
        )
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("color: #666; font-size: 14px; padding: 40px;")
        self.content_layout.addWidget(label)

    # -- display: table -------------------------------------------------------

    def _show_table(self, doc_id: str, index: int) -> None:
        paper = self.papers[doc_id]
        tbl = paper["tables"][index]
        m = tbl["meta"]

        meta = [
            ("Document ID", doc_id),
            ("Paper", _truncate(paper["title"], 80)),
            ("Caption", m.get("table_caption", "")),
            ("Page", str(m.get("page_num", "?"))),
            ("Rows", str(m.get("table_num_rows", "?"))),
            ("Columns", str(m.get("table_num_cols", "?"))),
            ("Table Index", str(m.get("table_index", "?"))),
            ("Chunk ID", tbl["id"]),
        ]
        _populate_meta_table(self.meta_table, meta)

        self._clear_content()

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: markdown content
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setFont(QFont("Consolas", 10))
        text_edit.setPlainText(tbl["document"])
        splitter.addWidget(text_edit)

        # Right: PDF page render
        page_label = self._render_pdf_page(doc_id, m.get("page_num"))
        scroll = QScrollArea()
        scroll.setWidget(page_label)
        scroll.setWidgetResizable(True)
        splitter.addWidget(scroll)

        splitter.setSizes([600, 600])
        self.content_layout.addWidget(splitter)

    # -- display: figure ------------------------------------------------------

    def _show_figure(self, doc_id: str, index: int) -> None:
        paper = self.papers[doc_id]
        fig = paper["figures"][index]
        m = fig["meta"]

        meta = [
            ("Document ID", doc_id),
            ("Paper", _truncate(paper["title"], 80)),
            ("Caption", m.get("caption", "")),
            ("Page", str(m.get("page_num", "?"))),
            ("Figure Index", str(m.get("figure_index", "?"))),
            ("Image Path", m.get("image_path", "")),
            ("Chunk ID", fig["id"]),
        ]
        _populate_meta_table(self.meta_table, meta)

        self._clear_content()

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: caption text
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setFont(QFont("Consolas", 10))
        text_edit.setPlainText(fig["document"])
        splitter.addWidget(text_edit)

        # Right: figure image
        image_path = m.get("image_path", "")
        img_label = QLabel()
        img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if image_path and os.path.isfile(image_path):
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                img_label.setPixmap(
                    pixmap.scaled(
                        QSize(800, 800),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
            else:
                img_label.setText("(failed to load image)")
                img_label.setStyleSheet("color: #999; font-size: 13px;")
        else:
            img_label.setText("(image not available)")
            img_label.setStyleSheet("color: #999; font-size: 13px;")

        scroll = QScrollArea()
        scroll.setWidget(img_label)
        scroll.setWidgetResizable(True)
        splitter.addWidget(scroll)

        splitter.setSizes([500, 700])
        self.content_layout.addWidget(splitter)

    # -- display: chunk -------------------------------------------------------

    def _show_chunk(self, doc_id: str, index: int) -> None:
        paper = self.papers[doc_id]
        chunk = paper["chunks"][index]
        m = chunk["meta"]

        meta = [
            ("Document ID", doc_id),
            ("Paper", _truncate(paper["title"], 80)),
            ("Section", m.get("section", "")),
            ("Page", str(m.get("page_num", "?"))),
            ("Chunk Index", str(m.get("chunk_index", "?"))),
            ("Quality Grade", m.get("quality_grade", "?")),
            ("Chunk ID", chunk["id"]),
        ]
        _populate_meta_table(self.meta_table, meta)

        self._clear_content()

        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setFont(QFont("Consolas", 10))
        text_edit.setPlainText(chunk["document"])
        self.content_layout.addWidget(text_edit)

    # -- PDF rendering --------------------------------------------------------

    def _get_pymupdf(self):
        if self._pymupdf is None:
            try:
                import pymupdf
                self._pymupdf = pymupdf
            except ImportError:
                try:
                    import fitz as pymupdf
                    self._pymupdf = pymupdf
                except ImportError:
                    self._pymupdf = False
        return self._pymupdf if self._pymupdf is not False else None

    def _get_zotero_client(self):
        if self._zotero_client is None:
            try:
                from deep_zotero.zotero_client import ZoteroClient
                self._zotero_client = ZoteroClient(self.zotero_dir)
            except Exception:
                self._zotero_client = False
        return self._zotero_client if self._zotero_client is not False else None

    def _resolve_pdf(self, doc_id: str) -> Path | None:
        """Resolve a doc_id (Zotero item key) to a PDF path. Cached."""
        if doc_id in self._pdf_cache:
            return self._pdf_cache[doc_id]

        pdf_path = None
        client = self._get_zotero_client()
        if client:
            try:
                item = client.get_item(doc_id)
                if item and item.pdf_path and item.pdf_path.exists():
                    pdf_path = item.pdf_path
            except Exception:
                pass

        self._pdf_cache[doc_id] = pdf_path
        return pdf_path

    def _render_pdf_page(self, doc_id: str, page_num: int | None) -> QLabel:
        """Render a PDF page as a QLabel with a QPixmap."""
        label = QLabel()
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if page_num is None:
            label.setText("(no page number)")
            label.setStyleSheet("color: #999; font-size: 13px;")
            return label

        fitz = self._get_pymupdf()
        if fitz is None:
            label.setText("(pymupdf not available -- install pymupdf to view PDF pages)")
            label.setStyleSheet("color: #999; font-size: 13px;")
            return label

        pdf_path = self._resolve_pdf(doc_id)
        if pdf_path is None:
            label.setText(f"(PDF not found for {doc_id})")
            label.setStyleSheet("color: #999; font-size: 13px;")
            return label

        try:
            doc = fitz.open(str(pdf_path))
            # page_num in metadata is 1-based, pymupdf is 0-based
            page_idx = int(page_num) - 1
            if page_idx < 0 or page_idx >= len(doc):
                label.setText(f"(page {page_num} out of range, PDF has {len(doc)} pages)")
                label.setStyleSheet("color: #999; font-size: 13px;")
                doc.close()
                return label

            page = doc[page_idx]
            mat = fitz.Matrix(150 / 72, 150 / 72)  # 150 DPI
            pix = page.get_pixmap(matrix=mat)
            doc.close()

            qimg = QImage(
                pix.samples,
                pix.width,
                pix.height,
                pix.stride,
                QImage.Format.Format_RGB888,
            )
            pixmap = QPixmap.fromImage(qimg)
            label.setPixmap(pixmap)
        except Exception as exc:
            label.setText(f"(error rendering PDF: {exc})")
            label.setStyleSheet("color: #c62828; font-size: 13px;")

        return label


# -- entry point --------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="DeepZotero ChromaDB Index Browser",
    )
    parser.add_argument(
        "chroma_path",
        nargs="?",
        default=str(CHROMA_DEFAULT),
        help=f"Path to ChromaDB directory (default: {CHROMA_DEFAULT})",
    )
    parser.add_argument(
        "--zotero-dir",
        default=str(ZOTERO_DEFAULT),
        help=f"Path to Zotero data directory (default: {ZOTERO_DEFAULT})",
    )
    args = parser.parse_args()

    chroma_path = Path(args.chroma_path).expanduser()
    zotero_dir = Path(args.zotero_dir).expanduser()

    if not chroma_path.exists():
        print(f"ChromaDB directory not found: {chroma_path}", file=sys.stderr)
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    viewer = IndexViewer(chroma_path, zotero_dir)
    viewer.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
