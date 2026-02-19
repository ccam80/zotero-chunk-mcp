"""Tests for the ground truth workspace creation script and batch loader."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from zotero_chunk_rag.table_extraction.ground_truth import (
    create_ground_truth_db,
    get_table_ids,
    make_table_id,
)


# ---------------------------------------------------------------------------
# Helpers — mock debug DB creation
# ---------------------------------------------------------------------------

_DEBUG_SCHEMA = """\
CREATE TABLE papers (
    item_key TEXT PRIMARY KEY,
    short_name TEXT,
    title TEXT,
    num_pages INTEGER,
    num_chunks INTEGER,
    quality_grade TEXT,
    figures_found INTEGER,
    figures_with_captions INTEGER,
    figures_missing INTEGER,
    figure_captions_found INTEGER,
    tables_found INTEGER,
    tables_with_captions INTEGER,
    tables_missing INTEGER,
    table_captions_found INTEGER,
    tables_1x1 INTEGER,
    encoding_artifact_captions INTEGER,
    duplicate_captions INTEGER,
    figure_number_gaps TEXT,
    table_number_gaps TEXT,
    unmatched_figure_captions TEXT,
    unmatched_table_captions TEXT,
    completeness_grade TEXT,
    full_markdown TEXT
);

CREATE TABLE extracted_tables (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_key TEXT,
    table_index INTEGER,
    page_num INTEGER,
    caption TEXT,
    caption_position TEXT,
    num_rows INTEGER,
    num_cols INTEGER,
    non_empty_cells INTEGER,
    total_cells INTEGER,
    fill_rate REAL,
    headers_json TEXT,
    rows_json TEXT,
    markdown TEXT,
    reference_context TEXT,
    bbox TEXT,
    artifact_type TEXT,
    extraction_strategy TEXT
);
"""


def _create_mock_db(
    db_path: Path,
    papers: list[dict],
    tables: list[dict],
) -> None:
    """Create a mock debug database with the given papers and tables."""
    conn = sqlite3.connect(str(db_path))
    conn.executescript(_DEBUG_SCHEMA)
    for p in papers:
        conn.execute(
            """INSERT INTO papers (item_key, short_name, title, num_pages,
               num_chunks, quality_grade, figures_found, figures_with_captions,
               figures_missing, figure_captions_found, tables_found,
               tables_with_captions, tables_missing, table_captions_found,
               tables_1x1, encoding_artifact_captions, duplicate_captions,
               figure_number_gaps, table_number_gaps,
               unmatched_figure_captions, unmatched_table_captions,
               completeness_grade, full_markdown)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                p["item_key"], p["short_name"], p.get("title", "Test Paper"),
                p.get("num_pages", 10), 0, "A", 0, 0, 0, 0,
                0, 0, 0, 0, 0, 0, 0, "[]", "[]", "[]", "[]", "A", "",
            ),
        )
    for t in tables:
        conn.execute(
            """INSERT INTO extracted_tables
               (item_key, table_index, page_num, caption, caption_position,
                num_rows, num_cols, non_empty_cells, total_cells, fill_rate,
                headers_json, rows_json, markdown, reference_context, bbox,
                artifact_type, extraction_strategy)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                t["item_key"], t["table_index"], t["page_num"],
                t.get("caption", "Table 1"),
                t.get("caption_position", "above"),
                t.get("num_rows", 2), t.get("num_cols", 3),
                t.get("non_empty_cells", 6), t.get("total_cells", 6),
                t.get("fill_rate", 1.0),
                json.dumps(t.get("headers", ["A", "B", "C"])),
                json.dumps(t.get("rows", [["1", "2", "3"], ["4", "5", "6"]])),
                t.get("markdown", "| A | B | C |"),
                t.get("reference_context", ""),
                json.dumps(t.get("bbox", [72.0, 200.0, 540.0, 400.0])),
                t.get("artifact_type", None),
                t.get("extraction_strategy", "rawdict"),
            ),
        )
    conn.commit()
    conn.close()


@pytest.fixture()
def mock_db(tmp_path: Path) -> Path:
    """Create a mock debug DB with 2 papers, 1 table each (paper2 has an artifact)."""
    db_path = tmp_path / "debug.db"
    papers = [
        {"item_key": "KEY1", "short_name": "paper-alpha"},
        {"item_key": "KEY2", "short_name": "paper-beta"},
    ]
    tables = [
        {
            "item_key": "KEY1",
            "table_index": 0,
            "page_num": 3,
            "caption": "Table 1. Demographics",
            "headers": ["Variable", "Value"],
            "rows": [["Age", "55"]],
            "bbox": [72.0, 200.0, 540.0, 400.0],
        },
        {
            "item_key": "KEY2",
            "table_index": 0,
            "page_num": 5,
            "caption": "Table 1. Results",
            "headers": ["Metric", "Score", "p"],
            "rows": [["Test", "0.95", "0.01"]],
            "bbox": [50.0, 100.0, 500.0, 300.0],
        },
    ]
    _create_mock_db(db_path, papers, tables)
    return db_path


@pytest.fixture()
def mock_db_with_artifact(tmp_path: Path) -> Path:
    """Create a mock debug DB where paper has 1 regular table + 1 artifact table."""
    db_path = tmp_path / "debug_artifact.db"
    papers = [
        {"item_key": "KEY1", "short_name": "paper-alpha"},
    ]
    tables = [
        {
            "item_key": "KEY1",
            "table_index": 0,
            "page_num": 3,
            "caption": "Table 1. Demographics",
            "headers": ["Variable", "Value"],
            "rows": [["Age", "55"]],
            "bbox": [72.0, 200.0, 540.0, 400.0],
        },
        {
            "item_key": "KEY1",
            "table_index": 1,
            "page_num": 4,
            "caption": "Figure 2 data",
            "headers": ["X", "Y"],
            "rows": [["1", "2"]],
            "bbox": [72.0, 200.0, 540.0, 350.0],
            "artifact_type": "figure_data_table",
        },
    ]
    _create_mock_db(db_path, papers, tables)
    return db_path


@pytest.fixture()
def fixture_pdf() -> Path:
    """Return the path to a real fixture PDF for rendering tests."""
    pdf = Path(__file__).resolve().parent.parent / "fixtures" / "papers" / "noname1.pdf"
    assert pdf.exists(), f"Fixture PDF not found: {pdf}"
    return pdf


def _mock_render(pdf_path, page_num, bbox, output_path, **kwargs):
    """Write a minimal valid PNG file instead of rendering from a PDF."""
    # Minimal 1x1 white PNG (67 bytes)
    import struct
    import zlib

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # PNG signature
    sig = b"\x89PNG\r\n\x1a\n"
    # IHDR chunk: 1x1, 8-bit grayscale
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0)
    ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF
    ihdr = struct.pack(">I", 13) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)
    # IDAT chunk: single white pixel (filter byte 0 + pixel value 255)
    raw = zlib.compress(b"\x00\xff")
    idat_crc = zlib.crc32(b"IDAT" + raw) & 0xFFFFFFFF
    idat = struct.pack(">I", len(raw)) + b"IDAT" + raw + struct.pack(">I", idat_crc)
    # IEND chunk
    iend_crc = zlib.crc32(b"IEND") & 0xFFFFFFFF
    iend = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", iend_crc)

    output_path.write_bytes(sig + ihdr + idat + iend)
    return output_path


# ---------------------------------------------------------------------------
# TestWorkspace
# ---------------------------------------------------------------------------


class TestWorkspace:
    """Tests for create_workspace()."""

    def _run_workspace(self, mock_db_path: Path, output_dir: Path) -> None:
        """Run create_workspace with mocked rendering."""
        # Import here to avoid top-level import issues with sys.path manipulation
        # in the script.
        from tests.create_ground_truth import create_workspace

        # Provide fake pdf_paths so the script doesn't try to connect to Zotero
        fake_pdf_paths = {
            "KEY1": Path(__file__).resolve().parent.parent / "fixtures" / "papers" / "noname1.pdf",
            "KEY2": Path(__file__).resolve().parent.parent / "fixtures" / "papers" / "noname1.pdf",
        }

        with patch(
            "tests.create_ground_truth.render_table_image",
            side_effect=_mock_render,
        ):
            create_workspace(
                mock_db_path,
                output_dir,
                pdf_paths=fake_pdf_paths,
            )

    def test_creates_paper_directories(self, mock_db: Path, tmp_path: Path) -> None:
        output_dir = tmp_path / "workspace"
        self._run_workspace(mock_db, output_dir)
        assert (output_dir / "paper-alpha").is_dir()
        assert (output_dir / "paper-beta").is_dir()

    def test_renders_table_images(self, mock_db: Path, tmp_path: Path) -> None:
        output_dir = tmp_path / "workspace"
        self._run_workspace(mock_db, output_dir)
        png_alpha = output_dir / "paper-alpha" / "table_0.png"
        png_beta = output_dir / "paper-beta" / "table_0.png"
        assert png_alpha.exists()
        assert png_beta.exists()
        # Check PNG magic bytes
        assert png_alpha.read_bytes()[:4] == b"\x89PNG"
        assert png_beta.read_bytes()[:4] == b"\x89PNG"

    def test_writes_extraction_json(self, mock_db: Path, tmp_path: Path) -> None:
        output_dir = tmp_path / "workspace"
        self._run_workspace(mock_db, output_dir)
        ext_path = output_dir / "paper-alpha" / "table_0_extraction.json"
        assert ext_path.exists()
        data = json.loads(ext_path.read_text(encoding="utf-8"))
        required_fields = {"headers", "rows", "bbox", "fill_rate", "artifact_type", "markdown"}
        assert required_fields.issubset(data.keys())
        assert data["headers"] == ["Variable", "Value"]
        assert data["rows"] == [["Age", "55"]]
        assert data["fill_rate"] == 1.0

    def test_writes_gt_template(self, mock_db: Path, tmp_path: Path) -> None:
        output_dir = tmp_path / "workspace"
        self._run_workspace(mock_db, output_dir)
        gt_path = output_dir / "paper-alpha" / "table_0_gt.json"
        assert gt_path.exists()
        data = json.loads(gt_path.read_text(encoding="utf-8"))
        assert data["verified"] is False
        assert data["headers"] == []
        assert data["rows"] == []
        expected_id = make_table_id("KEY1", "Table 1. Demographics", 3, 0)
        assert data["table_id"] == expected_id

    def test_writes_manifest(self, mock_db: Path, tmp_path: Path) -> None:
        output_dir = tmp_path / "workspace"
        self._run_workspace(mock_db, output_dir)
        manifest_path = output_dir / "paper-alpha" / "manifest.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["num_tables"] == 1
        entry = manifest["tables"][0]
        required_fields = {
            "table_index", "table_id", "page_num", "caption",
            "artifact_type", "image_path", "extraction_path", "gt_path",
        }
        assert required_fields.issubset(entry.keys())

    def test_includes_artifact_tables(self, mock_db_with_artifact: Path, tmp_path: Path) -> None:
        output_dir = tmp_path / "workspace"
        fake_pdf_paths = {
            "KEY1": Path(__file__).resolve().parent.parent / "fixtures" / "papers" / "noname1.pdf",
        }
        from tests.create_ground_truth import create_workspace

        with patch(
            "tests.create_ground_truth.render_table_image",
            side_effect=_mock_render,
        ):
            create_workspace(
                mock_db_with_artifact,
                output_dir,
                pdf_paths=fake_pdf_paths,
            )

        manifest = json.loads(
            (output_dir / "paper-alpha" / "manifest.json").read_text(encoding="utf-8")
        )
        assert manifest["num_tables"] == 2

        # Find the artifact table entry
        artifact_entries = [t for t in manifest["tables"] if t["artifact_type"] is not None]
        assert len(artifact_entries) == 1
        assert artifact_entries[0]["artifact_type"] == "figure_data_table"

        # Verify artifact table files exist
        assert (output_dir / "paper-alpha" / "table_1.png").exists()
        assert (output_dir / "paper-alpha" / "table_1_extraction.json").exists()
        assert (output_dir / "paper-alpha" / "table_1_gt.json").exists()

    def test_requires_debug_db(self, tmp_path: Path) -> None:
        from tests.create_ground_truth import create_workspace

        nonexistent = tmp_path / "does_not_exist.db"
        with pytest.raises(FileNotFoundError):
            create_workspace(nonexistent, tmp_path / "output")


# ---------------------------------------------------------------------------
# Helpers — GT workspace for loader tests
# ---------------------------------------------------------------------------


def _write_gt_file(
    paper_dir: Path,
    table_index: int,
    *,
    table_id: str,
    paper: str,
    item_key: str,
    page_num: int,
    caption: str,
    headers: list[str],
    rows: list[list[str]],
    notes: str = "",
    verified: bool = False,
) -> Path:
    """Write a GT JSON file into a paper directory."""
    paper_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "table_id": table_id,
        "paper": paper,
        "item_key": item_key,
        "page_num": page_num,
        "table_index": table_index,
        "caption": caption,
        "headers": headers,
        "rows": rows,
        "notes": notes,
        "verified": verified,
    }
    gt_path = paper_dir / f"table_{table_index}_gt.json"
    gt_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return gt_path


# ---------------------------------------------------------------------------
# TestLoader
# ---------------------------------------------------------------------------


class TestLoader:
    """Tests for load_verified_ground_truth()."""

    def test_loads_verified(self, tmp_path: Path) -> None:
        from tests.load_ground_truth import load_verified_ground_truth

        workspace = tmp_path / "workspace"
        paper_dir = workspace / "test-paper"

        _write_gt_file(
            paper_dir, 0,
            table_id="KEY1_table_1",
            paper="test-paper",
            item_key="KEY1",
            page_num=3,
            caption="Table 1. Results",
            headers=["A", "B"],
            rows=[["1", "2"]],
            verified=True,
        )
        _write_gt_file(
            paper_dir, 1,
            table_id="KEY1_table_2",
            paper="test-paper",
            item_key="KEY1",
            page_num=5,
            caption="Table 2. Summary",
            headers=["X"],
            rows=[["y"]],
            verified=False,
        )

        db_path = tmp_path / "gt.db"
        result = load_verified_ground_truth(workspace, db_path)

        assert result["loaded"] == 1
        assert result["skipped_unverified"] == 1
        assert result["errors"] == []

        ids = get_table_ids(db_path)
        assert "KEY1_table_1" in ids
        assert "KEY1_table_2" not in ids

    def test_skips_unverified(self, tmp_path: Path) -> None:
        from tests.load_ground_truth import load_verified_ground_truth

        workspace = tmp_path / "workspace"
        paper_dir = workspace / "test-paper"

        _write_gt_file(
            paper_dir, 0,
            table_id="KEY1_table_1",
            paper="test-paper",
            item_key="KEY1",
            page_num=3,
            caption="Table 1",
            headers=["A"],
            rows=[["1"]],
            verified=False,
        )

        db_path = tmp_path / "gt.db"
        result = load_verified_ground_truth(workspace, db_path)

        assert result["loaded"] == 0
        assert result["skipped_unverified"] == 1
        ids = get_table_ids(db_path)
        assert ids == []

    def test_data_fidelity(self, tmp_path: Path) -> None:
        from tests.load_ground_truth import load_verified_ground_truth

        workspace = tmp_path / "workspace"
        paper_dir = workspace / "fidelity-paper"

        headers = ["Name", "Age (SD)", "p-value"]
        rows = [
            ["Group A", "55.2 (12.1)", "0.047"],
            ["Group B", "54.8 (11.9)", "<0.001"],
        ]

        _write_gt_file(
            paper_dir, 0,
            table_id="FID_table_1",
            paper="fidelity-paper",
            item_key="FID",
            page_num=7,
            caption="Table 1. Fidelity Check",
            headers=headers,
            rows=rows,
            notes="Footnote: SD = standard deviation",
            verified=True,
        )

        db_path = tmp_path / "gt.db"
        load_verified_ground_truth(workspace, db_path)

        conn = sqlite3.connect(str(db_path))
        try:
            row = conn.execute(
                "SELECT headers_json, rows_json, notes FROM ground_truth_tables WHERE table_id = ?",
                ("FID_table_1",),
            ).fetchone()
            assert row is not None
            assert json.loads(row[0]) == headers
            assert json.loads(row[1]) == rows
            assert row[2] == "Footnote: SD = standard deviation"
        finally:
            conn.close()

    def test_creates_db_if_missing(self, tmp_path: Path) -> None:
        from tests.load_ground_truth import load_verified_ground_truth

        workspace = tmp_path / "workspace"
        paper_dir = workspace / "test-paper"

        _write_gt_file(
            paper_dir, 0,
            table_id="KEY1_table_1",
            paper="test-paper",
            item_key="KEY1",
            page_num=3,
            caption="Table 1",
            headers=["A"],
            rows=[["1"]],
            verified=True,
        )

        db_path = tmp_path / "new_dir" / "gt.db"
        assert not db_path.exists()

        result = load_verified_ground_truth(workspace, db_path)

        assert db_path.exists()
        assert result["loaded"] == 1
        ids = get_table_ids(db_path)
        assert "KEY1_table_1" in ids

    def test_idempotent_reload(self, tmp_path: Path) -> None:
        from tests.load_ground_truth import load_verified_ground_truth

        workspace = tmp_path / "workspace"
        paper_dir = workspace / "test-paper"

        _write_gt_file(
            paper_dir, 0,
            table_id="KEY1_table_1",
            paper="test-paper",
            item_key="KEY1",
            page_num=3,
            caption="Table 1",
            headers=["A", "B"],
            rows=[["1", "2"]],
            verified=True,
        )

        db_path = tmp_path / "gt.db"

        result1 = load_verified_ground_truth(workspace, db_path)
        assert result1["loaded"] == 1
        assert result1["errors"] == []

        result2 = load_verified_ground_truth(workspace, db_path)
        assert result2["loaded"] == 1
        assert result2["errors"] == []

        ids = get_table_ids(db_path)
        assert ids == ["KEY1_table_1"]

        conn = sqlite3.connect(str(db_path))
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM ground_truth_tables WHERE table_id = ?",
                ("KEY1_table_1",),
            ).fetchone()[0]
            assert count == 1
        finally:
            conn.close()
