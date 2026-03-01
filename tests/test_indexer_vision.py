"""Tests for VisionAPI construction in Indexer.__init__()."""
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zotero_chunk_rag.config import Config


def _make_config(tmp_path: Path) -> Config:
    chroma_dir = tmp_path / "chroma"
    chroma_dir.mkdir()
    return Config(
        zotero_data_dir=tmp_path,
        chroma_db_path=chroma_dir,
        embedding_model="gemini-embedding-001",
        embedding_dimensions=768,
        chunk_size=400,
        chunk_overlap=100,
        gemini_api_key=None,
        embedding_provider="local",
        embedding_timeout=120.0,
        embedding_max_retries=3,
        rerank_alpha=0.7,
        rerank_section_weights=None,
        rerank_journal_weights=None,
        rerank_enabled=True,
        oversample_multiplier=3,
        oversample_topic_factor=5,
        stats_sample_limit=10000,
        ocr_language="eng",
        openalex_email=None,
        vision_enabled=True,
        vision_model="claude-haiku-4-5-20251001",
        vision_num_agents=3,
        vision_dpi=300,
        vision_consensus_threshold=0.6,
        vision_padding_px=20,
        anthropic_api_key=None,
    )


class TestIndexerInit:
    def test_vision_api_created_with_key(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key-abc"}, clear=False):
            with patch("zotero_chunk_rag.indexer.ZoteroClient") as mock_zotero:
                with patch("zotero_chunk_rag.indexer.create_embedder") as mock_embedder:
                    with patch("zotero_chunk_rag.indexer.VectorStore") as mock_store:
                        with patch("zotero_chunk_rag.indexer.JournalRanker"):
                            with patch(
                                "zotero_chunk_rag.feature_extraction.vision_api.VisionAPI.__init__",
                                return_value=None,
                            ) as mock_vision_init:
                                mock_zotero.return_value = MagicMock()
                                mock_embedder.return_value = MagicMock()
                                mock_store.return_value = MagicMock()

                                from zotero_chunk_rag.indexer import Indexer
                                indexer = Indexer(config)

        assert indexer._vision_api is not None
        from zotero_chunk_rag.feature_extraction.vision_api import VisionAPI
        assert isinstance(indexer._vision_api, VisionAPI)

    def test_vision_api_none_without_key(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        env_without_key = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        with patch.dict(os.environ, env_without_key, clear=True):
            with patch("zotero_chunk_rag.indexer.ZoteroClient") as mock_zotero:
                with patch("zotero_chunk_rag.indexer.create_embedder") as mock_embedder:
                    with patch("zotero_chunk_rag.indexer.VectorStore") as mock_store:
                        with patch("zotero_chunk_rag.indexer.JournalRanker"):
                            mock_zotero.return_value = MagicMock()
                            mock_embedder.return_value = MagicMock()
                            mock_store.return_value = MagicMock()

                            from zotero_chunk_rag.indexer import Indexer
                            indexer = Indexer(config)

        assert indexer._vision_api is None
