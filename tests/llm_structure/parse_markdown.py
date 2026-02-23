"""Parse GFM pipe tables from LLM response markdown files.

Core function: parse_markdown_table(text) -> (headers, rows, footnotes)
Convenience: load_response(path) -> (headers, rows, footnotes)
"""
from __future__ import annotations

import re
from pathlib import Path


def _strip_code_fences(text: str) -> str:
    """Remove surrounding code fences if present (defensive)."""
    lines = text.strip().splitlines()
    if len(lines) >= 2:
        first = lines[0].strip()
        last = lines[-1].strip()
        if first.startswith("```") and last == "```":
            lines = lines[1:-1]
    return "\n".join(lines)


def _is_separator_line(line: str) -> bool:
    """Return True if line is a GFM separator row (e.g., | --- | --- |)."""
    stripped = line.strip()
    if "|" not in stripped:
        return False
    cells = _split_pipe_cells(stripped)
    if not cells:
        return False
    return all(re.match(r"^[\s:\-]+$", cell) or cell.strip() == "" for cell in cells)


def _split_pipe_cells(line: str) -> list[str]:
    """Split a pipe-delimited line into cells, respecting escaped pipes.

    Handles \\| (escaped pipe) by temporarily replacing it, splitting on |,
    then restoring the escaped pipe in cell values.
    """
    placeholder = "\x00PIPE\x00"
    work = line.replace("\\|", placeholder)

    work = work.strip()
    if work.startswith("|"):
        work = work[1:]
    if work.endswith("|"):
        work = work[:-1]

    cells = work.split("|")
    return [cell.replace(placeholder, "|").strip() for cell in cells]


def parse_markdown_table(text: str) -> tuple[list[str], list[list[str]], str]:
    """Parse a GFM pipe table from text.

    Returns (headers, rows, footnotes) where:
    - headers: list of column header strings
    - rows: list of data rows (each a list of cell strings)
    - footnotes: text after the last pipe line (footnote block)

    Rows shorter than the header count are padded with empty strings.
    """
    text = _strip_code_fences(text)
    lines = text.splitlines()

    # Find all pipe-containing lines
    pipe_line_indices: list[int] = []
    for i, line in enumerate(lines):
        if "|" in line.strip():
            pipe_line_indices.append(i)

    if not pipe_line_indices:
        return ([], [], text.strip())

    # First pipe line = headers
    header_idx = pipe_line_indices[0]
    headers = _split_pipe_cells(lines[header_idx])

    # Find and skip separator line
    data_start = 1  # index into pipe_line_indices
    if len(pipe_line_indices) > 1:
        candidate = pipe_line_indices[1]
        if _is_separator_line(lines[candidate]):
            data_start = 2

    # Remaining pipe lines = data rows
    rows: list[list[str]] = []
    ncols = len(headers)
    last_pipe_idx = header_idx

    for pi in pipe_line_indices[data_start:]:
        line = lines[pi]
        if _is_separator_line(line):
            continue
        cells = _split_pipe_cells(line)
        while len(cells) < ncols:
            cells.append("")
        rows.append(cells)
        last_pipe_idx = pi

    # Everything after the last pipe line = footnotes
    footnote_lines = lines[last_pipe_idx + 1:]
    footnotes = "\n".join(footnote_lines).strip()

    return (headers, rows, footnotes)


def load_response(path: Path | str) -> tuple[list[str], list[list[str]], str]:
    """Load and parse a response markdown file.

    Convenience wrapper around parse_markdown_table.
    """
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    return parse_markdown_table(text)
