"""Regenerate all REVIEW.md files from GT JSONs.

Uses HTML <table> for any table containing multi-line cells (equations,
structure descriptions, numbered lists). Markdown tables used for simple
single-line content. VS Code markdown preview renders HTML blocks correctly.

Usage::

    "./.venv/Scripts/python.exe" tests/regenerate_review_md.py
"""
from __future__ import annotations

import html
import json
from pathlib import Path


def _has_newlines(headers: list[str], rows: list[list[str]]) -> bool:
    """Check if any cell in the table contains newlines."""
    for h in headers:
        if "\n" in h:
            return True
    for row in rows:
        for cell in row:
            if "\n" in cell:
                return True
    return False


def _escape_pipe(s: str) -> str:
    """Escape literal pipe characters for markdown tables."""
    return s.replace("|", "\\|")


def _html_cell(s: str) -> str:
    """Convert cell content to HTML-safe text with <br> for newlines."""
    s = html.escape(s)
    s = s.replace("\n", "<br>")
    return s


def _render_html_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    """Render a table as an HTML <table> block."""
    ncols = len(headers)
    lines = []
    lines.append("<table>")
    lines.append("<thead><tr>")
    for h in headers:
        lines.append(f"<th>{_html_cell(h)}</th>")
    lines.append("</tr></thead>")
    lines.append("<tbody>")
    for row in rows:
        padded = list(row) + [""] * (ncols - len(row))
        lines.append("<tr>")
        for cell in padded[:ncols]:
            lines.append(f"<td>{_html_cell(cell)}</td>")
        lines.append("</tr>")
    lines.append("</tbody>")
    lines.append("</table>")
    return lines


def _render_md_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    """Render a table as a markdown table (no newlines in cells)."""
    ncols = len(headers)
    lines = []
    header_cells = [_escape_pipe(h) for h in headers]
    lines.append("| " + " | ".join(header_cells) + " |")
    lines.append("|" + "|".join(["---"] * ncols) + "|")
    for row in rows:
        padded = list(row) + [""] * (ncols - len(row))
        cells = [_escape_pipe(c) for c in padded[:ncols]]
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def render_paper(paper_dir: Path) -> str:
    """Render a complete REVIEW.md for one paper directory."""
    manifest = json.loads((paper_dir / "manifest.json").read_text(encoding="utf-8"))
    paper_name = manifest["paper"]
    item_key = manifest["item_key"]

    gt_files = sorted(paper_dir.glob("table_*_gt.json"))

    tables_info = []
    for gt_path in gt_files:
        data = json.loads(gt_path.read_text(encoding="utf-8"))
        tables_info.append(data)

    num_total = len(tables_info)
    num_artifacts = sum(
        1 for t in tables_info
        if not t.get("headers") and not t.get("rows")
    )
    num_data = num_total - num_artifacts

    lines = []
    lines.append(f"# {paper_name} — Ground Truth Review")
    lines.append("")
    lines.append(f"Paper: {paper_name}")
    lines.append(f"Item key: {item_key}")
    artifact_note = f" ({num_artifacts} artifact + {num_data} data)" if num_artifacts else ""
    lines.append(f"Total tables: {num_total}{artifact_note}")
    lines.append("")

    for i, data in enumerate(tables_info):
        idx = data.get("table_index", i)
        page = data.get("page_num", "?")
        caption = data.get("caption", "")
        headers = data.get("headers", [])
        rows = data.get("rows", [])
        notes = data.get("notes", "")
        verified = data.get("verified", False)
        artifact = data.get("artifact_type", "")

        ncols = len(headers)
        nrows = len(rows)

        lines.append("---")
        lines.append("")

        # Section heading
        if not headers and not rows:
            atype = artifact if artifact else "unknown"
            lines.append(f"## table_{idx} (p{page}) — ARTIFACT: {atype} [{ncols} cols × {nrows} rows]")
        else:
            short_caption = caption[:80] + ("..." if len(caption) > 80 else "")
            lines.append(f"## table_{idx} (p{page}) — {short_caption} [{ncols} cols × {nrows} rows]")

        lines.append("")

        # Metadata
        lines.append(f"- **Caption:** {caption}")
        if artifact:
            lines.append(f"- **Type:** {artifact}")
        if notes:
            lines.append(f"- **Notes:** {notes}")
        lines.append(f"- **Verified:** {str(verified).lower()}")
        lines.append("")

        if not headers and not rows:
            lines.append("(No table to render — headers and rows are empty.)")
            lines.append("")
            continue

        # Choose HTML or markdown based on whether cells have newlines
        if _has_newlines(headers, rows):
            lines.extend(_render_html_table(headers, rows))
        else:
            lines.extend(_render_md_table(headers, rows))

        lines.append("")

    # Review checklist
    lines.append("---")
    lines.append("")
    lines.append("## Review Checklist")
    lines.append("")
    for data in tables_info:
        idx = data.get("table_index", "?")
        headers = data.get("headers", [])
        rows = data.get("rows", [])
        ncols = len(headers)
        nrows = len(rows)
        if not headers and not rows:
            lines.append(f"- [ ] table_{idx} — artifact confirmed")
        else:
            lines.append(f"- [ ] table_{idx} — {nrows} rows, {ncols} cols verified")

    lines.append("")
    return "\n".join(lines)


def main():
    workspace = Path(__file__).resolve().parent.parent / "tests" / "ground_truth_workspace"

    paper_dirs = sorted(
        p for p in workspace.iterdir()
        if p.is_dir() and (p / "manifest.json").exists()
    )

    for paper_dir in paper_dirs:
        content = render_paper(paper_dir)
        review_path = paper_dir / "REVIEW.md"
        review_path.write_text(content, encoding="utf-8")
        print(f"  [{paper_dir.name}] REVIEW.md written")

    print(f"\nDone. {len(paper_dirs)} REVIEW.md files regenerated.")


if __name__ == "__main__":
    main()
