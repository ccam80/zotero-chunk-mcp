"""Tests for vision_api.py — sync conversion, _prepare_table, _build_request, extract_tables_batch."""

from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zotero_chunk_rag.feature_extraction.vision_api import (
    VisionAPI,
    TableVisionSpec,
    _append_cost_entry,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_api(cache: bool = True) -> VisionAPI:
    """Construct a VisionAPI without a real Anthropic client."""
    with patch("zotero_chunk_rag.feature_extraction.vision_api.anthropic") as mock_anthropic:
        mock_anthropic.Anthropic.return_value = MagicMock()
        api = VisionAPI(api_key="test-key", cache=cache)
    return api


def _make_spec(table_id: str = "5SIZVS65_table_1") -> TableVisionSpec:
    return TableVisionSpec(
        table_id=table_id,
        pdf_path=Path("/fake/paper.pdf"),
        page_num=1,
        bbox=(10.0, 20.0, 200.0, 400.0),
        raw_text="Col1 Col2\nval1 val2",
        caption="Table 1. Results",
        garbled=False,
    )


def _valid_json_response() -> str:
    return json.dumps({
        "table_label": "Table 1",
        "caption": "Table 1. Results",
        "is_incomplete": False,
        "incomplete_reason": "",
        "headers": ["Col1", "Col2"],
        "rows": [["val1", "val2"]],
        "footnotes": "",
        "recrop": {"needed": False, "bbox_pct": [0, 0, 100, 100]},
    })


# ---------------------------------------------------------------------------
# TestSyncConversion
# ---------------------------------------------------------------------------

class TestSyncConversion:

    def test_no_asyncio_import(self):
        """asyncio must not appear as an import in vision_api.py."""
        import zotero_chunk_rag.feature_extraction.vision_api as mod
        source_path = Path(mod.__file__)
        source = source_path.read_text(encoding="utf-8")
        # Check that 'import asyncio' is not present as a top-level import
        assert "import asyncio" not in source, (
            "vision_api.py must not import asyncio"
        )

    def test_poll_batch_is_not_coroutine(self):
        """_poll_batch must be a regular function, not a coroutine."""
        assert not asyncio.iscoroutinefunction(VisionAPI._poll_batch), (
            "VisionAPI._poll_batch must not be an async def"
        )

    def test_append_cost_entry_is_not_coroutine(self):
        """_append_cost_entry must be a regular function, not a coroutine."""
        assert not asyncio.iscoroutinefunction(_append_cost_entry), (
            "_append_cost_entry must not be an async def"
        )

    def test_init_no_concurrency_param(self):
        """VisionAPI.__init__ must not accept a 'concurrency' parameter."""
        with patch("zotero_chunk_rag.feature_extraction.vision_api.anthropic") as mock_anthropic:
            mock_anthropic.Anthropic.return_value = MagicMock()
            with pytest.raises(TypeError):
                VisionAPI(api_key="test-key", concurrency=10)

    def test_init_no_dpi_param(self):
        """VisionAPI.__init__ must not accept a 'dpi' parameter."""
        with patch("zotero_chunk_rag.feature_extraction.vision_api.anthropic") as mock_anthropic:
            mock_anthropic.Anthropic.return_value = MagicMock()
            with pytest.raises(TypeError):
                VisionAPI(api_key="test-key", dpi=300)


# ---------------------------------------------------------------------------
# TestPrepareTable
# ---------------------------------------------------------------------------

class TestPrepareTable:

    def test_returns_list_of_pairs(self):
        """_prepare_table returns a list with one tuple; second element is 'image/png'."""
        api = _make_api()
        spec = _make_spec()

        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_doc.__getitem__ = MagicMock(return_value=mock_page)

        with patch("zotero_chunk_rag.feature_extraction.vision_api.pymupdf") as mock_pymupdf, \
             patch("zotero_chunk_rag.feature_extraction.vision_api.render_table_region") as mock_render:
            mock_pymupdf.open.return_value = mock_doc
            mock_render.return_value = [(b"fake_png", "image/png")]

            result = api._prepare_table(spec)

        assert len(result) == 1
        assert result[0][1] == "image/png"

    def test_base64_encoded(self):
        """First element of each tuple must be valid base64."""
        api = _make_api()
        spec = _make_spec()

        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_doc.__getitem__ = MagicMock(return_value=mock_page)

        with patch("zotero_chunk_rag.feature_extraction.vision_api.pymupdf") as mock_pymupdf, \
             patch("zotero_chunk_rag.feature_extraction.vision_api.render_table_region") as mock_render:
            mock_pymupdf.open.return_value = mock_doc
            mock_render.return_value = [(b"fake_png_bytes", "image/png")]

            result = api._prepare_table(spec)

        # Must not raise
        decoded = base64.b64decode(result[0][0])
        assert decoded == b"fake_png_bytes"

    def test_multi_strip(self):
        """When render_table_region returns 2 strips, _prepare_table returns 2 tuples."""
        api = _make_api()
        spec = _make_spec()

        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_doc.__getitem__ = MagicMock(return_value=mock_page)

        with patch("zotero_chunk_rag.feature_extraction.vision_api.pymupdf") as mock_pymupdf, \
             patch("zotero_chunk_rag.feature_extraction.vision_api.render_table_region") as mock_render:
            mock_pymupdf.open.return_value = mock_doc
            mock_render.return_value = [
                (b"strip1", "image/png"),
                (b"strip2", "image/png"),
            ]

            result = api._prepare_table(spec)

        assert len(result) == 2
        assert result[0][1] == "image/png"
        assert result[1][1] == "image/png"
        # Both must be valid base64
        assert base64.b64decode(result[0][0]) == b"strip1"
        assert base64.b64decode(result[1][0]) == b"strip2"

    def test_document_closed(self):
        """PDF document's .close() must be called exactly once, even if rendering raises."""
        api = _make_api()
        spec = _make_spec()

        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_doc.__getitem__ = MagicMock(return_value=mock_page)

        with patch("zotero_chunk_rag.feature_extraction.vision_api.pymupdf") as mock_pymupdf, \
             patch("zotero_chunk_rag.feature_extraction.vision_api.render_table_region") as mock_render:
            mock_pymupdf.open.return_value = mock_doc
            mock_render.return_value = [(b"data", "image/png")]

            api._prepare_table(spec)

        mock_doc.close.assert_called_once()

    def test_document_closed_on_render_error(self):
        """PDF document's .close() must be called even when render_table_region raises."""
        api = _make_api()
        spec = _make_spec()

        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_doc.__getitem__ = MagicMock(return_value=mock_page)

        with patch("zotero_chunk_rag.feature_extraction.vision_api.pymupdf") as mock_pymupdf, \
             patch("zotero_chunk_rag.feature_extraction.vision_api.render_table_region") as mock_render:
            mock_pymupdf.open.return_value = mock_doc
            mock_render.side_effect = RuntimeError("render failed")

            with pytest.raises(RuntimeError):
                api._prepare_table(spec)

        mock_doc.close.assert_called_once()


# ---------------------------------------------------------------------------
# TestBuildRequest
# ---------------------------------------------------------------------------

class TestBuildRequest:

    def _build(self, spec: TableVisionSpec | None = None,
               images: list | None = None,
               cache: bool = True) -> dict:
        api = _make_api(cache=cache)
        if spec is None:
            spec = _make_spec()
        if images is None:
            images = [(base64.b64encode(b"img").decode("ascii"), "image/png")]
        return api._build_request(spec, images)

    def test_custom_id_format(self):
        """custom_id must be '{table_id}__transcriber'."""
        spec = _make_spec("5SIZVS65_table_1")
        request = self._build(spec=spec)
        assert request["custom_id"] == "5SIZVS65_table_1__transcriber"

    def test_system_prompt_cache_control(self):
        """With cache=True, system block must have cache_control == {'type': 'ephemeral'}."""
        request = self._build(cache=True)
        system = request["params"]["system"]
        assert len(system) == 1
        assert system[0]["cache_control"] == {"type": "ephemeral"}

    def test_no_cache_control_when_disabled(self):
        """With cache=False, system block must not have 'cache_control'."""
        request = self._build(cache=False)
        system = request["params"]["system"]
        assert len(system) == 1
        assert "cache_control" not in system[0]

    def test_user_content_structure(self):
        """1 image: user_content has 2 blocks — text first, then image; image has source.type='base64'."""
        b64 = base64.b64encode(b"img_data").decode("ascii")
        request = self._build(images=[(b64, "image/png")])
        user_content = request["params"]["messages"][0]["content"]

        assert len(user_content) == 2
        assert user_content[0]["type"] == "text"
        assert user_content[1]["type"] == "image"
        assert user_content[1]["source"]["type"] == "base64"

    def test_user_content_text_contains_raw_text(self):
        """The text block must contain the raw_text from the spec."""
        spec = _make_spec()
        request = self._build(spec=spec)
        user_content = request["params"]["messages"][0]["content"]
        assert spec.raw_text in user_content[0]["text"]

    def test_multi_image_content(self):
        """2 images: user_content has 3 blocks — 1 text + 2 images in order."""
        b64a = base64.b64encode(b"img_a").decode("ascii")
        b64b = base64.b64encode(b"img_b").decode("ascii")
        request = self._build(images=[(b64a, "image/png"), (b64b, "image/png")])
        user_content = request["params"]["messages"][0]["content"]

        assert len(user_content) == 3
        assert user_content[0]["type"] == "text"
        assert user_content[1]["type"] == "image"
        assert user_content[1]["source"]["data"] == b64a
        assert user_content[2]["type"] == "image"
        assert user_content[2]["source"]["data"] == b64b

    def test_model_matches_init(self):
        """params.model must match the model passed to __init__."""
        with patch("zotero_chunk_rag.feature_extraction.vision_api.anthropic") as mock_anthropic:
            mock_anthropic.Anthropic.return_value = MagicMock()
            api = VisionAPI(api_key="test-key", model="claude-haiku-4-5-20251001")
        images = [(base64.b64encode(b"img").decode("ascii"), "image/png")]
        request = api._build_request(_make_spec(), images)
        assert request["params"]["model"] == api._model

    def test_garbled_warning_in_context(self):
        """With garbled=True, user content text block must contain 'GARBLED SYMBOL ENCODING'."""
        spec = TableVisionSpec(
            table_id="tbl_garbled",
            pdf_path=Path("/fake/paper.pdf"),
            page_num=1,
            bbox=(0.0, 0.0, 100.0, 200.0),
            raw_text="some garbled text",
            caption=None,
            garbled=True,
        )
        request = self._build(spec=spec)
        user_content = request["params"]["messages"][0]["content"]
        assert "GARBLED SYMBOL ENCODING" in user_content[0]["text"]


# ---------------------------------------------------------------------------
# TestExtractTablesBatch
# ---------------------------------------------------------------------------

class TestExtractTablesBatch:

    def test_empty_specs(self):
        """extract_tables_batch([]) must return []."""
        api = _make_api()
        result = api.extract_tables_batch([])
        assert result == []

    def test_successful_extraction(self):
        """2 specs: returns 2 AgentResponse objects both with parse_success=True."""
        api = _make_api()
        spec1 = _make_spec("paper_table_1")
        spec2 = _make_spec("paper_table_2")

        valid_json = _valid_json_response()
        submit_results = {
            "paper_table_1__transcriber": valid_json,
            "paper_table_2__transcriber": valid_json,
        }

        with patch.object(api, "_prepare_table", return_value=[(base64.b64encode(b"img").decode("ascii"), "image/png")]), \
             patch.object(api, "_submit_and_poll", return_value=submit_results):
            responses = api.extract_tables_batch([spec1, spec2])

        assert len(responses) == 2
        assert responses[0].parse_success is True
        assert responses[1].parse_success is True
        assert responses[0].headers == ["Col1", "Col2"]
        assert responses[0].rows == [["val1", "val2"]]

    def test_missing_result(self):
        """When a spec's result is absent, that response has parse_success=False."""
        api = _make_api()
        spec1 = _make_spec("paper_table_1")
        spec2 = _make_spec("paper_table_2")

        submit_results = {
            "paper_table_1__transcriber": _valid_json_response(),
            # spec2 is missing
        }

        with patch.object(api, "_prepare_table", return_value=[(base64.b64encode(b"img").decode("ascii"), "image/png")]), \
             patch.object(api, "_submit_and_poll", return_value=submit_results):
            responses = api.extract_tables_batch([spec1, spec2])

        assert len(responses) == 2
        assert responses[0].parse_success is True
        assert responses[1].parse_success is False
        assert responses[1].headers == []
        assert responses[1].rows == []

    def test_result_order_matches_input(self):
        """Output order must match input order regardless of dict iteration order."""
        api = _make_api()
        spec_a = _make_spec("A")
        spec_b = _make_spec("B")
        spec_c = _make_spec("C")

        def make_json(label: str) -> str:
            return json.dumps({
                "table_label": label,
                "caption": f"Table {label}",
                "is_incomplete": False,
                "incomplete_reason": "",
                "headers": [label],
                "rows": [[label]],
                "footnotes": "",
                "recrop": {"needed": False, "bbox_pct": [0, 0, 100, 100]},
            })

        # Return results in reversed order (C, B, A) as dict
        submit_results = {
            "C__transcriber": make_json("C"),
            "B__transcriber": make_json("B"),
            "A__transcriber": make_json("A"),
        }

        with patch.object(api, "_prepare_table", return_value=[(base64.b64encode(b"img").decode("ascii"), "image/png")]), \
             patch.object(api, "_submit_and_poll", return_value=submit_results):
            responses = api.extract_tables_batch([spec_a, spec_b, spec_c])

        assert len(responses) == 3
        # Output must be A, B, C order (matching input)
        assert responses[0].headers == ["A"]
        assert responses[1].headers == ["B"]
        assert responses[2].headers == ["C"]

    def test_calls_prepare_and_build(self):
        """_prepare_table and _build_request must each be called once for a single spec."""
        api = _make_api()
        spec = _make_spec()

        fake_images = [(base64.b64encode(b"img").decode("ascii"), "image/png")]
        fake_request = {
            "custom_id": f"{spec.table_id}__transcriber",
            "params": {"model": "claude-haiku-4-5-20251001", "max_tokens": 4096,
                       "system": [], "messages": []},
        }

        with patch.object(api, "_prepare_table", return_value=fake_images) as mock_prepare, \
             patch.object(api, "_build_request", return_value=fake_request) as mock_build, \
             patch.object(api, "_submit_and_poll", return_value={
                 f"{spec.table_id}__transcriber": _valid_json_response()
             }):
            api.extract_tables_batch([spec])

        mock_prepare.assert_called_once_with(spec)
        mock_build.assert_called_once_with(spec, fake_images)
