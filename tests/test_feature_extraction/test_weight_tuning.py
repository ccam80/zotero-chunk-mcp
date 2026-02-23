"""Tests for data-driven weight tuning (tune_weights.py) and Pipeline weight loading."""
from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from zotero_chunk_rag.feature_extraction.debug_db import EXTENDED_SCHEMA
from zotero_chunk_rag.feature_extraction.models import PipelineConfig, TableContext
from zotero_chunk_rag.feature_extraction.pipeline import Pipeline

# Import the functions under test
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from tune_weights import compute_multipliers, compute_win_rates, write_config


def _create_mock_debug_db(db_path: Path) -> None:
    """Create a mock debug DB with method_results for 3 tables, 2 methods.

    Method A wins 2 tables (higher quality_score), Method B wins 1.
    """
    con = sqlite3.connect(str(db_path))
    con.executescript(EXTENDED_SCHEMA)

    # Table 1: method_a+rawdict wins (score 85), method_b+rawdict loses (score 60)
    con.execute(
        "INSERT INTO method_results (table_id, method_name, quality_score) VALUES (?, ?, ?)",
        ("t1", "method_a+rawdict", 85.0),
    )
    con.execute(
        "INSERT INTO method_results (table_id, method_name, quality_score) VALUES (?, ?, ?)",
        ("t1", "method_b+rawdict", 60.0),
    )

    # Table 2: method_a+rawdict wins (score 90), method_b+rawdict loses (score 75)
    con.execute(
        "INSERT INTO method_results (table_id, method_name, quality_score) VALUES (?, ?, ?)",
        ("t2", "method_a+rawdict", 90.0),
    )
    con.execute(
        "INSERT INTO method_results (table_id, method_name, quality_score) VALUES (?, ?, ?)",
        ("t2", "method_b+rawdict", 75.0),
    )

    # Table 3: method_b+rawdict wins (score 95), method_a+rawdict loses (score 70)
    con.execute(
        "INSERT INTO method_results (table_id, method_name, quality_score) VALUES (?, ?, ?)",
        ("t3", "method_a+rawdict", 70.0),
    )
    con.execute(
        "INSERT INTO method_results (table_id, method_name, quality_score) VALUES (?, ?, ?)",
        ("t3", "method_b+rawdict", 95.0),
    )

    con.commit()
    con.close()


class TestWinRates:
    """Tests for compute_win_rates()."""

    def test_computes_from_db(self):
        """Method A wins 2/3 tables, Method B wins 1/3."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "debug.db"
            _create_mock_debug_db(db_path)

            win_rates = compute_win_rates(db_path)

            assert "method_a" in win_rates
            assert "method_b" in win_rates

            # method_a wins 2 out of 3 tables (participated in all 3)
            assert abs(win_rates["method_a"] - 2 / 3) < 0.01

            # method_b wins 1 out of 3 tables (participated in all 3)
            assert abs(win_rates["method_b"] - 1 / 3) < 0.01


class TestMultipliers:
    """Tests for compute_multipliers()."""

    def test_normalization(self):
        """Best method gets 1.0, others proportional."""
        win_rates = {"A": 0.8, "B": 0.2}
        multipliers = compute_multipliers(win_rates)

        assert abs(multipliers["A"] - 1.0) < 0.001
        assert abs(multipliers["B"] - 0.25) < 0.001

    def test_zero_win_floor(self):
        """Method with 0 wins gets multiplier 0.1 floor."""
        win_rates = {"A": 0.5, "B": 0.0}
        multipliers = compute_multipliers(win_rates)

        assert abs(multipliers["A"] - 1.0) < 0.001
        assert abs(multipliers["B"] - 0.1) < 0.001


class TestConfig:
    """Tests for write_config() and Pipeline weight reading."""

    def test_writes_json(self):
        """Output file is valid JSON with confidence_multipliers key."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "weights.json"
            multipliers = {"method_a": 1.0, "method_b": 0.5}
            write_config(multipliers, output_path)

            assert output_path.exists()
            data = json.loads(output_path.read_text(encoding="utf-8"))
            assert "confidence_multipliers" in data
            assert data["confidence_multipliers"]["method_a"] == 1.0
            assert data["confidence_multipliers"]["method_b"] == 0.5

    def test_pipeline_reads_weights(self):
        """Pipeline reads multipliers from weights JSON and merges into config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            weights_path = Path(tmpdir) / "pipeline_weights.json"
            weights_data = {
                "confidence_multipliers": {
                    "ruled_lines": 2.5,
                    "hotspot": 0.8,
                },
            }
            weights_path.write_text(json.dumps(weights_data), encoding="utf-8")

            # Create a minimal config with some existing multipliers
            mock_struct = MagicMock()
            mock_struct.name = "test"
            mock_struct.detect = MagicMock(return_value=None)

            mock_cell = MagicMock()
            mock_cell.name = "test_cell"
            mock_cell.extract = MagicMock(return_value=None)

            config = PipelineConfig(
                structure_methods=(mock_struct,),
                cell_methods=(mock_cell,),
                postprocessors=(),
                activation_rules={},
                combination_strategy="expand_overlap",
                selection_strategy="rank_based",
                confidence_multipliers={"existing": 1.0},
            )

            pipeline = Pipeline(config, weights_path=weights_path)

            # Check merged multipliers
            assert pipeline._config.confidence_multipliers["ruled_lines"] == 2.5
            assert pipeline._config.confidence_multipliers["hotspot"] == 0.8
            assert pipeline._config.confidence_multipliers["existing"] == 1.0

    def test_pipeline_no_weights_file(self):
        """Pipeline works fine when no weights JSON exists."""
        mock_struct = MagicMock()
        mock_struct.name = "test"
        mock_struct.detect = MagicMock(return_value=None)

        mock_cell = MagicMock()
        mock_cell.name = "test_cell"
        mock_cell.extract = MagicMock(return_value=None)

        config = PipelineConfig(
            structure_methods=(mock_struct,),
            cell_methods=(mock_cell,),
            postprocessors=(),
            activation_rules={},
            combination_strategy="expand_overlap",
            selection_strategy="rank_based",
            confidence_multipliers={"existing": 1.0},
        )

        # Use a non-existent path
        pipeline = Pipeline(config, weights_path=Path("__nonexistent__.json"))
        assert pipeline._config.confidence_multipliers == {"existing": 1.0}
