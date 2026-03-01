"""Engine protocol, data models, and factory for PaddleOCR-based table extraction."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class PaddleEngine(Protocol):
    """Protocol that all PaddleOCR engine implementations must satisfy."""

    def extract_tables(self, pdf_path: Path) -> list[RawPaddleTable]:
        """Extract all tables from a PDF file.

        Args:
            pdf_path: Absolute path to the PDF file.

        Returns:
            List of raw table extractions in engine-native pixel coordinates.
        """
        ...


@dataclass
class RawPaddleTable:
    """Intermediate representation of a table as returned by a PaddleOCR engine.

    Bounding box coordinates are in engine-native pixel space and must be
    normalised to PDF points by the caller using page_size.
    """

    page_num: int
    bbox: tuple[float, float, float, float]
    page_size: tuple[int, int]
    headers: list[str]
    rows: list[list[str]]
    footnotes: str
    engine_name: str
    raw_output: str


def get_engine(name: str) -> PaddleEngine:
    """Return an initialised engine instance for the given engine name.

    Model loading occurs inside each engine's ``__init__``, so the returned
    instance is ready to call ``extract_tables`` immediately.

    Args:
        name: Engine identifier. Supported values:
            ``"pp_structure_v3"`` — PP-StructureV3 (HTML output)
            ``"paddleocr_vl_1.5"`` — PaddleOCR-VL-1.5 (markdown output)

    Raises:
        ValueError: If *name* does not match any known engine.
    """
    if name == "pp_structure_v3":
        from .paddle_engines import PPStructureEngine
        return PPStructureEngine()
    if name == "paddleocr_vl_1.5":
        from .paddle_engines import PaddleOCRVLEngine
        return PaddleOCRVLEngine()
    raise ValueError(f"Unknown engine name: {name!r}")
