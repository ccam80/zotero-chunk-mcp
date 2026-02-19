"""Tests for table extraction package dependencies and structure."""

import pytest
import os


class TestDependencies:
    """Verify that camelot and pdfplumber are installed and functional."""

    def test_camelot_imports(self):
        import camelot
        assert isinstance(camelot.__version__, str)
        assert len(camelot.__version__) > 0

    def test_pdfplumber_imports(self):
        import pdfplumber
        assert isinstance(pdfplumber.__version__, str)
        assert len(pdfplumber.__version__) > 0

    def test_camelot_ghostscript(self):
        import camelot
        fixture_pdf = os.path.join(
            os.path.dirname(__file__),
            "..",
            "fixtures",
            "papers",
            "noname1.pdf",
        )
        fixture_pdf = os.path.abspath(fixture_pdf)
        # Use lattice flavor — requires Ghostscript. Must not raise a
        # Ghostscript-related exception (or any exception).
        try:
            tables = camelot.read_pdf(fixture_pdf, pages="1", flavor="lattice")
            # Result may be 0 tables — lattice finds grid-rule tables only.
            assert isinstance(tables, camelot.core.TableList)
        except Exception as exc:
            # Fail clearly if a Ghostscript error surfaces.
            assert False, f"camelot.read_pdf raised an exception: {exc}"


class TestPackageStructure:
    """Verify that the table_extraction package skeleton is importable."""

    def test_package_importable(self):
        import zotero_chunk_rag.table_extraction  # noqa: F401

    def test_subpackages_importable(self):
        import zotero_chunk_rag.table_extraction.methods  # noqa: F401
        import zotero_chunk_rag.table_extraction.postprocessors  # noqa: F401
