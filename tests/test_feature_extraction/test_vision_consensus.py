"""Unit tests for the consensus algorithm in vision_extract.py.

All tests use synthetic AgentResponse objects only — no API calls, no PDFs,
no external dependencies.
"""

from __future__ import annotations

import pytest

from zotero_chunk_rag.feature_extraction.vision_extract import (
    AgentResponse,
    ConsensusResult,
    VisionExtractionResult,
    _parse_agent_json,
    build_consensus,
    vision_result_to_cell_grid,
)


# ---------------------------------------------------------------------------
# Helper factory
# ---------------------------------------------------------------------------


def _make_response(
    headers: list[str],
    rows: list[list[str]],
    *,
    footnotes: str = "",
    table_label: str | None = None,
    is_incomplete: bool = False,
    incomplete_reason: str = "",
    parse_success: bool = True,
) -> AgentResponse:
    """Build an AgentResponse with sensible defaults."""
    return AgentResponse(
        headers=headers,
        rows=rows,
        footnotes=footnotes,
        table_label=table_label,
        is_incomplete=is_incomplete,
        incomplete_reason=incomplete_reason,
        raw_shape=(len(rows), len(headers)),
        parse_success=parse_success,
        raw_response="",
    )


# ---------------------------------------------------------------------------
# Shape / structural consensus
# ---------------------------------------------------------------------------


class TestShapeConsensus:
    def test_3_agents_agree(self) -> None:
        """All 3 produce identical output — expect 100% agreement."""
        responses = [
            _make_response(["A", "B"], [["1", "2"], ["3", "4"]]),
            _make_response(["A", "B"], [["1", "2"], ["3", "4"]]),
            _make_response(["A", "B"], [["1", "2"], ["3", "4"]]),
        ]
        result = build_consensus(responses)

        assert result is not None
        assert result.agent_agreement_rate == pytest.approx(1.0)
        assert result.disputed_cells == []
        assert result.shape_agreement is True
        assert result.winning_shape == (2, 2)
        assert result.headers == ("A", "B")
        assert result.rows == (("1", "2"), ("3", "4"))

    def test_shape_majority(self) -> None:
        """2-of-3 agents agree on shape (3,2); minority agent has (4,2)."""
        responses = [
            _make_response(["X", "Y"], [["a", "b"], ["c", "d"], ["e", "f"]]),
            _make_response(["X", "Y"], [["a", "b"], ["c", "d"], ["e", "f"]]),
            _make_response(["X", "Y"], [["a", "b"], ["c", "d"], ["e", "f"], ["g", "h"]]),
        ]
        result = build_consensus(responses)

        assert result is not None
        assert result.winning_shape == (3, 2)
        assert result.shape_agreement is True

    def test_shape_all_differ(self) -> None:
        """All 3 agents disagree on shape — fallback to median, shape_agreement=False."""
        responses = [
            _make_response(["A", "B"], [["1", "2"], ["3", "4"], ["5", "6"]]),
            _make_response(["A", "B", "C"], [["1", "2", "3"], ["4", "5", "6"],
                                             ["7", "8", "9"], ["10", "11", "12"]]),
            _make_response(["A", "B"], [["1", "2"], ["3", "4"], ["5", "6"],
                                        ["7", "8"], ["9", "10"]]),
        ]
        result = build_consensus(responses)

        # Must return something (median fallback) but shape_agreement=False
        assert result is not None
        assert result.shape_agreement is False

    def test_shape_insufficient(self) -> None:
        """Only 1 agent parsed successfully — build_consensus returns None."""
        responses = [
            _make_response(["A", "B"], [["1", "2"]], parse_success=True),
            _make_response([], [], parse_success=False),
            _make_response([], [], parse_success=False),
        ]
        result = build_consensus(responses)

        assert result is None


# ---------------------------------------------------------------------------
# Cell-level voting
# ---------------------------------------------------------------------------


class TestCellVoting:
    def test_2_of_3_agree_cells(self) -> None:
        """Agents 0 and 1 agree on cell (0,1); agent 2 differs — majority wins."""
        responses = [
            _make_response(["A", "B"], [["1", "0.047"]]),
            _make_response(["A", "B"], [["1", "0.047"]]),
            _make_response(["A", "B"], [["1", "0.048"]]),
        ]
        result = build_consensus(responses)

        assert result is not None
        assert result.rows[0][1] == "0.047"
        assert result.agent_agreement_rate > 0.0

    def test_all_3_disagree_cells(self) -> None:
        """All 3 give different values for cell (0,0) — flagged as disputed, first used."""
        responses = [
            _make_response(["H"], [["a"]]),
            _make_response(["H"], [["b"]]),
            _make_response(["H"], [["c"]]),
        ]
        result = build_consensus(responses)

        assert result is not None
        # Cell (0,0) is disputed
        disputed_positions = [(r, c) for r, c, _ in result.disputed_cells]
        assert (0, 0) in disputed_positions

        # First agent's value used
        assert result.rows[0][0] == "a"

        # The disputed entry should list all three values
        for r, c, vals in result.disputed_cells:
            if (r, c) == (0, 0):
                assert set(vals) == {"a", "b", "c"}
                break


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------


class TestCellNormalization:
    def test_cell_normalization_whitespace(self) -> None:
        """Trailing/leading whitespace differences must not create a dispute."""
        responses = [
            _make_response(["H"], [["0.047"]]),
            _make_response(["H"], [["0.047 "]]),
            _make_response(["H"], [[" 0.047"]]),
        ]
        result = build_consensus(responses)

        assert result is not None
        # No dispute — all normalize to the same value
        assert result.disputed_cells == []
        assert result.rows[0][0].strip() == "0.047"

    def test_cell_normalization_dashes(self) -> None:
        """Unicode minus (U+2212) and ASCII hyphen must be treated identically."""
        unicode_minus = "\u2212"
        responses = [
            _make_response(["H"], [[f"{unicode_minus}0.5"]]),
            _make_response(["H"], [["-0.5"]]),
            _make_response(["H"], [["-0.5"]]),
        ]
        result = build_consensus(responses)

        assert result is not None
        # No dispute after dash normalization
        assert result.disputed_cells == []


# ---------------------------------------------------------------------------
# Incomplete voting
# ---------------------------------------------------------------------------


class TestIncompleteVoting:
    def test_incomplete_vote_2_of_3(self) -> None:
        """2-of-3 agents say incomplete — consensus is_incomplete=True."""
        responses = [
            _make_response(["A"], [["1"]], is_incomplete=True),
            _make_response(["A"], [["1"]], is_incomplete=True),
            _make_response(["A"], [["1"]], is_incomplete=False),
        ]
        result = build_consensus(responses)

        assert result is not None
        assert result.is_incomplete is True

    def test_incomplete_vote_1_of_3(self) -> None:
        """Only 1-of-3 agents says incomplete — consensus is_incomplete=False."""
        responses = [
            _make_response(["A"], [["1"]], is_incomplete=True),
            _make_response(["A"], [["1"]], is_incomplete=False),
            _make_response(["A"], [["1"]], is_incomplete=False),
        ]
        result = build_consensus(responses)

        assert result is not None
        assert result.is_incomplete is False


# ---------------------------------------------------------------------------
# Footnote merging
# ---------------------------------------------------------------------------


class TestFootnotesMerging:
    def test_footnote_union_merge(self) -> None:
        """Different footnotes from different agents are union-merged."""
        responses = [
            _make_response(["A"], [["1"]], footnotes="* p < 0.05"),
            _make_response(["A"], [["1"]], footnotes="† Adjusted for age"),
            _make_response(["A"], [["1"]], footnotes="* p < 0.05"),
        ]
        result = build_consensus(responses)

        assert result is not None
        merged = result.footnotes
        assert "* p < 0.05" in merged
        assert "† Adjusted for age" in merged

    def test_footnote_dedup(self) -> None:
        """Identical footnote from all 3 agents appears exactly once."""
        fn = "* p < 0.05"
        responses = [
            _make_response(["A"], [["1"]], footnotes=fn),
            _make_response(["A"], [["1"]], footnotes=fn),
            _make_response(["A"], [["1"]], footnotes=fn),
        ]
        result = build_consensus(responses)

        assert result is not None
        # Count occurrences of the footnote text in the merged string
        assert result.footnotes.count(fn) == 1


# ---------------------------------------------------------------------------
# Table label voting
# ---------------------------------------------------------------------------


class TestLabelVoting:
    def test_label_majority(self) -> None:
        """2-of-3 agents say 'Table 3' — consensus label is 'Table 3'."""
        responses = [
            _make_response(["A"], [["1"]], table_label="Table 3"),
            _make_response(["A"], [["1"]], table_label="Table 3"),
            _make_response(["A"], [["1"]], table_label="Table 2"),
        ]
        result = build_consensus(responses)

        assert result is not None
        assert result.table_label == "Table 3"

    def test_label_all_none(self) -> None:
        """All agents report no label — consensus label is None."""
        responses = [
            _make_response(["A"], [["1"]], table_label=None),
            _make_response(["A"], [["1"]], table_label=None),
            _make_response(["A"], [["1"]], table_label=None),
        ]
        result = build_consensus(responses)

        assert result is not None
        assert result.table_label is None


# ---------------------------------------------------------------------------
# CellGrid conversion
# ---------------------------------------------------------------------------


class TestVisionResultToCellGrid:
    def test_vision_result_to_cell_grid(self) -> None:
        """ConsensusResult wrapped in VisionExtractionResult converts to CellGrid."""
        consensus = ConsensusResult(
            headers=("Col1", "Col2"),
            rows=(("val1", "val2"),),
            footnotes="",
            table_label=None,
            is_incomplete=False,
            disputed_cells=[],
            agent_agreement_rate=1.0,
            shape_agreement=True,
            winning_shape=(1, 2),
            num_agents_succeeded=3,
        )
        result = VisionExtractionResult(
            consensus=consensus,
            agent_responses=[],
        )
        grid = vision_result_to_cell_grid(result)

        assert grid is not None
        assert grid.headers == ("Col1", "Col2")
        assert grid.rows == (("val1", "val2"),)
        assert grid.method == "vision_consensus"

    def test_vision_result_to_cell_grid_none(self) -> None:
        """VisionExtractionResult with consensus=None returns None."""
        result = VisionExtractionResult(
            consensus=None,
            agent_responses=[],
        )
        grid = vision_result_to_cell_grid(result)

        assert grid is None


# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------


class TestParseAgentJson:
    def test_parse_agent_json_valid(self) -> None:
        """Plain valid JSON string is parsed correctly."""
        raw = '{"headers": ["A", "B"], "rows": [], "footnotes": ""}'
        parsed = _parse_agent_json(raw)

        assert parsed is not None
        assert parsed["headers"] == ["A", "B"]

    def test_parse_agent_json_fenced(self) -> None:
        """JSON wrapped in ```json ... ``` code fence is parsed correctly."""
        raw = '```json\n{"headers": ["X"], "rows": [[\"v\"]], "footnotes": ""}\n```'
        parsed = _parse_agent_json(raw)

        assert parsed is not None
        assert parsed["headers"] == ["X"]

    def test_parse_agent_json_with_text(self) -> None:
        """JSON embedded in surrounding prose is extracted via fallback regex."""
        raw = 'Here is the result:\n{"headers": ["Z"], "rows": [], "footnotes": ""}\nDone.'
        parsed = _parse_agent_json(raw)

        assert parsed is not None
        assert parsed["headers"] == ["Z"]

    def test_parse_agent_json_invalid(self) -> None:
        """Completely invalid input returns None."""
        raw = "not json at all"
        parsed = _parse_agent_json(raw)

        assert parsed is None
