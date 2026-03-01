"""Post-processor: clean cell text across the entire grid.

Applies ligature normalization, leading-zero recovery, negative-sign
reassembly, whitespace normalization, and font-aware control-character
mapping to every cell.
"""
from __future__ import annotations

import re

from ..models import CellGrid

# ---------------------------------------------------------------------------
# Ligature map
# ---------------------------------------------------------------------------

_LIGATURE_MAP = {
    "\ufb00": "ff",
    "\ufb01": "fi",
    "\ufb02": "fl",
    "\ufb03": "ffi",
    "\ufb04": "ffl",
}

# ---------------------------------------------------------------------------
# Numeric helpers
# ---------------------------------------------------------------------------

_STAT_MARKERS = re.compile(r"[*\u2020\u2021\u00a7\u2016]+")
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_WHITESPACE_RE = re.compile(r"  +")

# Leading-dot numeric: ".digits" possibly repeated
_LEADING_ZERO_RE = re.compile(r"(?:^|(?<=\s))\.(\d)")

# Negative sign reassembly
_NEG_DOT_RE = re.compile(r"(\d+)\s*[\u2212\-]\s*\.\s*(\d*)")
_NEG_DIGITS_RE = re.compile(r"[\u2212\-]\s*(\d[\d.]*)")

# Greek/Math/Symbol font detection
_SYMBOL_FONT_RE = re.compile(
    r"symbol|greek|math|cmsy|cmex|cmmi|msam|msbm",
    re.IGNORECASE,
)


def _looks_numeric(text: str) -> bool:
    """Check if *text* is purely numeric (statistical markers stripped)."""
    stripped = _STAT_MARKERS.sub("", text).strip()
    if not stripped:
        return False
    return all(c in "0123456789.\u2212-+, " for c in stripped)


def _normalize_ligatures(text: str) -> str:
    """Replace common ligature codepoints with their ASCII equivalents."""
    for lig, replacement in _LIGATURE_MAP.items():
        text = text.replace(lig, replacement)
    return text


def _recover_leading_zeros(text: str) -> str:
    """Recover leading zeros: ``.047`` becomes ``0.047``.

    Only applies when the text looks numeric (guarded).
    """
    if _looks_numeric(text):
        text = _LEADING_ZERO_RE.sub(r"0.\1", text)
    return text


def _reassemble_negative_signs(text: str) -> str:
    """Reassemble split negative signs.

    Handles ``"digits - ."`` and ``"- digits"`` patterns.
    """
    text_stripped = text.strip()

    # Pattern 1: "18278 - ." -> negative decimal
    m_neg_dot = _NEG_DOT_RE.match(text_stripped)
    if m_neg_dot and _looks_numeric(text):
        digits = m_neg_dot.group(1)
        frac = m_neg_dot.group(2) or ""
        if frac:
            return f"-{digits}.{frac}"
        return f"-{digits}."

    # Pattern 2: "- 18278" -> negative number
    if text_stripped.startswith(("\u2212", "-")) and _looks_numeric(text):
        m_neg = _NEG_DIGITS_RE.match(text_stripped)
        if m_neg:
            return f"-{m_neg.group(1)}"

    return text


def _map_control_chars(
    text: str,
    cell_bbox: tuple[float, float, float, float] | None,
    dict_blocks: list[dict],
) -> str:
    """Map control characters based on font context.

    For Symbol/Greek/Math fonts, attempt to preserve the character
    (the font encodes legitimate symbols). For text fonts, strip
    the control character.

    When *cell_bbox* is provided, the nearest span determines the font.
    When *cell_bbox* is ``None``, all spans are checked and if ANY span
    uses a symbol font, control characters are preserved.
    """
    if not _CONTROL_CHAR_RE.search(text):
        return text

    font_name = ""
    if dict_blocks:
        if cell_bbox:
            # Find nearest span to the cell center
            cx = (cell_bbox[0] + cell_bbox[2]) / 2
            cy = (cell_bbox[1] + cell_bbox[3]) / 2
            best_dist = float("inf")
            for block in dict_blocks:
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        sb = span.get("bbox", (0, 0, 0, 0))
                        sx = (sb[0] + sb[2]) / 2
                        sy = (sb[1] + sb[3]) / 2
                        dist = abs(sx - cx) + abs(sy - cy)
                        if dist < best_dist:
                            best_dist = dist
                            font_name = span.get("font", "")
        else:
            # No cell bbox — check all spans for symbol fonts
            for block in dict_blocks:
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        fn = span.get("font", "")
                        if _SYMBOL_FONT_RE.search(fn):
                            font_name = fn
                            break
                    if font_name:
                        break
                if font_name:
                    break

    if _SYMBOL_FONT_RE.search(font_name):
        # Symbol/Greek font — keep control chars (they map to symbols)
        return text

    # Text font — strip control chars
    return _CONTROL_CHAR_RE.sub("", text)


class CellCleaning:
    """Clean cell text across the entire grid."""

    @property
    def name(self) -> str:
        return "cell_cleaning"

    def process(self, grid: CellGrid, dict_blocks: list[dict] | None = None) -> CellGrid:
        try:
            return self._process(grid, dict_blocks or [])
        except Exception:
            return grid

    def _process(self, grid: CellGrid, dict_blocks: list[dict]) -> CellGrid:

        def clean(text: str, bbox: tuple[float, float, float, float] | None = None) -> str:
            if not text:
                return text
            # 1. Ligature normalization
            text = _normalize_ligatures(text)
            # 2. Control character mapping (font-aware)
            text = _map_control_chars(text, bbox, dict_blocks)
            # 3. Negative sign reassembly (before whitespace collapse)
            text = _reassemble_negative_signs(text)
            # 4. Leading zero recovery
            text = _recover_leading_zeros(text)
            # 5. Whitespace normalization
            text = text.replace("\n", " ")
            text = _WHITESPACE_RE.sub(" ", text).strip()
            # 6. Normalize Unicode minus to ASCII hyphen-minus
            text = text.replace("\u2212", "-")
            return text

        new_headers = tuple(clean(h) for h in grid.headers)
        new_rows = tuple(
            tuple(clean(c) for c in row) for row in grid.rows
        )

        if new_headers == grid.headers and new_rows == grid.rows:
            return grid

        return CellGrid(
            headers=new_headers,
            rows=new_rows,
            col_boundaries=grid.col_boundaries,
            row_boundaries=grid.row_boundaries,
            method=grid.method,
        )
