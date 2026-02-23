"""Tests for LLM-based table transcription evaluation workflow.

Covers:
- TestMarkdownParsing: pipe table parsing, footnotes, escaped pipes, empty cells,
  code fences, malformed input
- TestPromptGeneration: manifest has rawtext_path, rawtext.txt created
- TestEvaluation: evaluate module importable, synthetic response scored correctly
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from zotero_chunk_rag.feature_extraction.ground_truth import (
    create_ground_truth_db,
    insert_ground_truth,
)

TESTS_DIR = Path(__file__).resolve().parents[1]
LLM_STRUCTURE_DIR = TESTS_DIR / "llm_structure"
FIXTURES_DIR = TESTS_DIR / "fixtures" / "papers"


# ============================================================================
# Markdown parsing
# ============================================================================


class TestMarkdownParsing:
    """Tests for parse_markdown.py."""

    def test_basic_pipe_table(self):
        """A standard 3-column pipe table is parsed correctly."""
        from tests.llm_structure.parse_markdown import parse_markdown_table

        text = (
            "| A | B | C |\n"
            "| --- | --- | --- |\n"
            "| 1 | 2 | 3 |\n"
            "| 4 | 5 | 6 |\n"
        )
        headers, rows, footnotes = parse_markdown_table(text)
        assert headers == ["A", "B", "C"]
        assert len(rows) == 2
        assert rows[0] == ["1", "2", "3"]
        assert rows[1] == ["4", "5", "6"]
        assert footnotes == ""

    def test_footnotes_after_table(self):
        """Text after the last pipe line is captured as footnotes."""
        from tests.llm_structure.parse_markdown import parse_markdown_table

        text = (
            "| X | Y |\n"
            "| --- | --- |\n"
            "| a | b |\n"
            "\n"
            "* p < 0.05\n"
            "† Adjusted for age\n"
        )
        headers, rows, footnotes = parse_markdown_table(text)
        assert headers == ["X", "Y"]
        assert len(rows) == 1
        assert "p < 0.05" in footnotes
        assert "Adjusted for age" in footnotes

    def test_escaped_pipes(self):
        """Escaped pipes (\\|) inside cells are preserved."""
        from tests.llm_structure.parse_markdown import parse_markdown_table

        text = (
            "| Col1 | Col2 |\n"
            "| --- | --- |\n"
            "| a \\| b | c |\n"
        )
        headers, rows, footnotes = parse_markdown_table(text)
        assert headers == ["Col1", "Col2"]
        assert rows[0][0] == "a | b"
        assert rows[0][1] == "c"

    def test_empty_cells(self):
        """Empty cells are parsed as empty strings."""
        from tests.llm_structure.parse_markdown import parse_markdown_table

        text = (
            "| A | B | C |\n"
            "| --- | --- | --- |\n"
            "| 1 | | 3 |\n"
            "| | 5 | |\n"
        )
        headers, rows, footnotes = parse_markdown_table(text)
        assert rows[0] == ["1", "", "3"]
        assert rows[1] == ["", "5", ""]

    def test_code_fences_stripped(self):
        """Code fences around the table are removed before parsing."""
        from tests.llm_structure.parse_markdown import parse_markdown_table

        text = (
            "```markdown\n"
            "| A | B |\n"
            "| --- | --- |\n"
            "| 1 | 2 |\n"
            "```\n"
        )
        headers, rows, footnotes = parse_markdown_table(text)
        assert headers == ["A", "B"]
        assert len(rows) == 1
        assert rows[0] == ["1", "2"]

    def test_short_rows_padded(self):
        """Rows with fewer cells than headers are padded."""
        from tests.llm_structure.parse_markdown import parse_markdown_table

        text = (
            "| A | B | C |\n"
            "| --- | --- | --- |\n"
            "| 1 | 2 |\n"
        )
        headers, rows, footnotes = parse_markdown_table(text)
        assert len(rows[0]) == 3
        assert rows[0] == ["1", "2", ""]

    def test_no_table_returns_empty(self):
        """Input with no pipe characters returns empty headers/rows."""
        from tests.llm_structure.parse_markdown import parse_markdown_table

        text = "This is just plain text with no table."
        headers, rows, footnotes = parse_markdown_table(text)
        assert headers == []
        assert rows == []
        assert footnotes == text.strip()

    def test_load_response(self, tmp_path: Path):
        """load_response reads a file and parses the table."""
        from tests.llm_structure.parse_markdown import load_response

        md = (
            "| Name | Score |\n"
            "| --- | --- |\n"
            "| Alice | 92 |\n"
            "| Bob | 85 |\n"
        )
        response_path = tmp_path / "response_test.md"
        response_path.write_text(md, encoding="utf-8")

        headers, rows, footnotes = load_response(response_path)
        assert headers == ["Name", "Score"]
        assert len(rows) == 2

    def test_separator_without_colons(self):
        """Separator line with just dashes (no colons) is recognized."""
        from tests.llm_structure.parse_markdown import parse_markdown_table

        text = (
            "| A | B |\n"
            "|---|---|\n"
            "| 1 | 2 |\n"
        )
        headers, rows, footnotes = parse_markdown_table(text)
        assert headers == ["A", "B"]
        assert len(rows) == 1

    def test_separator_with_colons(self):
        """Separator line with alignment colons is recognized."""
        from tests.llm_structure.parse_markdown import parse_markdown_table

        text = (
            "| A | B | C |\n"
            "| :--- | :---: | ---: |\n"
            "| 1 | 2 | 3 |\n"
        )
        headers, rows, footnotes = parse_markdown_table(text)
        assert headers == ["A", "B", "C"]
        assert len(rows) == 1


# ============================================================================
# Prompt generation
# ============================================================================


class TestPromptGeneration:
    """Tests for generate_prompts.py."""

    def test_script_importable(self):
        """generate_prompts module imports without error."""
        from tests.llm_structure import generate_prompts

        assert hasattr(generate_prompts, "generate_all")
        assert hasattr(generate_prompts, "generate_for_table")
        assert hasattr(generate_prompts, "render_table_png")
        assert hasattr(generate_prompts, "extract_rawtext")

    def test_manifest_has_rawtext_path(self, tmp_path: Path):
        """Generation produces manifest entries with rawtext_path field."""
        fixture_pdf = FIXTURES_DIR / "noname1.pdf"
        if not fixture_pdf.exists():
            pytest.skip(f"Fixture PDF not found: {fixture_pdf}")

        db_path = tmp_path / "test_gt.db"
        create_ground_truth_db(db_path)
        insert_ground_truth(
            db_path=db_path,
            table_id="TEST_table_1",
            paper_key="TEST",
            page_num=1,
            caption="Table 1 Test table",
            headers=["A", "B"],
            rows=[["1", "2"], ["3", "4"]],
        )

        pdf_paths = {"TEST": fixture_pdf}

        from tests.llm_structure.generate_prompts import generate_all

        with (
            patch(
                "tests.llm_structure.generate_prompts.TABLES_DIR",
                tmp_path / "tables",
            ),
            patch(
                "tests.llm_structure.generate_prompts.MANIFEST_PATH",
                tmp_path / "manifest.json",
            ),
            patch(
                "tests.llm_structure.generate_prompts.LLM_STRUCTURE_DIR",
                tmp_path,
            ),
        ):
            entries = generate_all(pdf_paths, db_path=db_path)

        assert len(entries) >= 1
        entry = entries[0]
        assert "rawtext_path" in entry
        assert entry["rawtext_path"].endswith("rawtext.txt")

        # Verify rawtext.txt was actually created
        rawtext_path = tmp_path / "tables" / "TEST_table_1" / "rawtext.txt"
        assert rawtext_path.exists()
        rawtext_content = rawtext_path.read_text(encoding="utf-8")
        assert len(rawtext_content) > 0  # Should have some text

        # Verify PNG still created
        png_path = tmp_path / "tables" / "TEST_table_1" / "table.png"
        assert png_path.exists()
        assert png_path.stat().st_size > 100

    def test_no_prompt_md_generated(self, tmp_path: Path):
        """Generation no longer creates prompt.md files."""
        fixture_pdf = FIXTURES_DIR / "noname1.pdf"
        if not fixture_pdf.exists():
            pytest.skip(f"Fixture PDF not found: {fixture_pdf}")

        db_path = tmp_path / "test_gt.db"
        create_ground_truth_db(db_path)
        insert_ground_truth(
            db_path=db_path,
            table_id="TEST_table_1",
            paper_key="TEST",
            page_num=1,
            caption="Table 1 Test table",
            headers=["A", "B"],
            rows=[["1", "2"], ["3", "4"]],
        )

        pdf_paths = {"TEST": fixture_pdf}

        from tests.llm_structure.generate_prompts import generate_all

        with (
            patch(
                "tests.llm_structure.generate_prompts.TABLES_DIR",
                tmp_path / "tables",
            ),
            patch(
                "tests.llm_structure.generate_prompts.MANIFEST_PATH",
                tmp_path / "manifest.json",
            ),
            patch(
                "tests.llm_structure.generate_prompts.LLM_STRUCTURE_DIR",
                tmp_path,
            ),
        ):
            generate_all(pdf_paths, db_path=db_path)

        prompt_path = tmp_path / "tables" / "TEST_table_1" / "prompt.md"
        assert not prompt_path.exists()


# ============================================================================
# Evaluation
# ============================================================================


class TestEvaluation:
    """Tests for evaluate.py."""

    def test_module_importable(self):
        """evaluate module imports without error."""
        from tests.llm_structure import evaluate

        assert hasattr(evaluate, "evaluate_response")
        assert hasattr(evaluate, "evaluate_all")
        assert hasattr(evaluate, "find_responses")

    def test_synthetic_response_scored(self, tmp_path: Path):
        """A synthetic response that exactly matches GT scores 100%."""
        db_path = tmp_path / "test_gt.db"
        create_ground_truth_db(db_path)
        insert_ground_truth(
            db_path=db_path,
            table_id="TEST_table_1",
            paper_key="TEST",
            page_num=1,
            caption="Table 1 Test table",
            headers=["A", "B", "C"],
            rows=[["1", "2", "3"], ["4", "5", "6"]],
        )

        # Create a response that exactly matches
        response_text = (
            "| A | B | C |\n"
            "| --- | --- | --- |\n"
            "| 1 | 2 | 3 |\n"
            "| 4 | 5 | 6 |\n"
        )
        response_path = tmp_path / "response_test.md"
        response_path.write_text(response_text, encoding="utf-8")

        from tests.llm_structure.evaluate import evaluate_response

        result = evaluate_response(
            table_id="TEST_table_1",
            model="test",
            response_path=response_path,
            db_path=db_path,
        )
        assert result is not None
        assert result.cell_accuracy_pct == 100.0
        assert result.fuzzy_accuracy_pct == 100.0
        assert result.num_cell_diffs == 0
        assert result.num_header_diffs == 0

    def test_mismatched_response_scored(self, tmp_path: Path):
        """A response with wrong values scores below 100%."""
        db_path = tmp_path / "test_gt.db"
        create_ground_truth_db(db_path)
        insert_ground_truth(
            db_path=db_path,
            table_id="TEST_table_1",
            paper_key="TEST",
            page_num=1,
            caption="Table 1 Test table",
            headers=["A", "B"],
            rows=[["1", "2"], ["3", "4"]],
        )

        # Create a response with one wrong value
        response_text = (
            "| A | B |\n"
            "| --- | --- |\n"
            "| 1 | WRONG |\n"
            "| 3 | 4 |\n"
        )
        response_path = tmp_path / "response_test.md"
        response_path.write_text(response_text, encoding="utf-8")

        from tests.llm_structure.evaluate import evaluate_response

        result = evaluate_response(
            table_id="TEST_table_1",
            model="test",
            response_path=response_path,
            db_path=db_path,
        )
        assert result is not None
        assert result.cell_accuracy_pct < 100.0
        assert result.num_cell_diffs >= 1

    def test_find_responses(self, tmp_path: Path):
        """find_responses discovers response_*.md files."""
        table_dir = tmp_path / "tables" / "TEST_table_1"
        table_dir.mkdir(parents=True)
        (table_dir / "response_sonnet.md").write_text("| A |\n| --- |\n| 1 |\n")
        (table_dir / "response_haiku.md").write_text("| A |\n| --- |\n| 1 |\n")
        (table_dir / "table.png").write_bytes(b"fake png")

        from tests.llm_structure.evaluate import find_responses

        results = find_responses(tmp_path / "tables")
        assert len(results) == 2
        models = {r[1] for r in results}
        assert "sonnet" in models
        assert "haiku" in models


# ============================================================================
# Comparison
# ============================================================================


class TestComparison:
    """Tests for compare.py."""

    def test_module_importable(self):
        """compare module imports without error."""
        from tests.llm_structure import compare

        assert hasattr(compare, "generate_report")

    def test_report_generation(self, tmp_path: Path):
        """generate_report produces a markdown report."""
        from tests.llm_structure.compare import generate_report
        from tests.llm_structure.evaluate import EvaluationResult

        llm_results = [
            EvaluationResult(
                table_id="TEST_table_1",
                model="sonnet",
                fuzzy_accuracy_pct=85.0,
                fuzzy_precision_pct=90.0,
                fuzzy_recall_pct=80.0,
                cell_accuracy_pct=80.0,
                structural_coverage_pct=100.0,
                gt_shape=(3, 2),
                ext_shape=(3, 2),
                num_cell_diffs=1,
                num_header_diffs=0,
                num_extra_cols=0,
                num_missing_cols=0,
                num_extra_rows=0,
                num_missing_rows=0,
                footnote_match=None,
            ),
        ]
        pipeline_accs = {"TEST_table_1": 70.0}

        output_path = tmp_path / "report.md"
        report = generate_report(llm_results, pipeline_accs, output_path=output_path)

        assert output_path.exists()
        assert "LLM vs Pipeline" in report
        assert "TEST_table_1" in report
        assert "sonnet" in report


# ============================================================================
# Template
# ============================================================================


class TestPromptTemplate:
    """Tests for the prompt template file."""

    def test_template_exists(self):
        """Template file exists and is non-empty."""
        template_path = LLM_STRUCTURE_DIR / "prompt_template.md"
        assert template_path.exists(), f"Template not found at {template_path}"
        content = template_path.read_text(encoding="utf-8")
        assert len(content) > 100, "Template is too short"

    def test_template_describes_markdown_output(self):
        """Template instructs markdown pipe table output, not JSON coordinates."""
        template_path = LLM_STRUCTURE_DIR / "prompt_template.md"
        content = template_path.read_text(encoding="utf-8")
        # Should describe markdown output
        assert "pipe" in content.lower() or "GFM" in content
        assert "Phase 1" in content
        assert "Phase 2" in content
        # Should NOT describe the old coordinate-based approach
        assert '"position"' not in content
