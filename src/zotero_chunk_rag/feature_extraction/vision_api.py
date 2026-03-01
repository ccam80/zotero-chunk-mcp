"""Vision API: API access layer for vision table extraction.

Provides TableVisionSpec, cost logging, and generic batch infrastructure.
Single-agent extraction logic is built on top of this layer.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

try:
    import anthropic
except ImportError:
    anthropic = None  # type: ignore[assignment]

from .vision_extract import (
    AgentResponse,
    build_common_ctx,
    parse_agent_response,
    render_table_png,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class TableVisionSpec:
    """Input spec for one table to extract via vision."""

    table_id: str
    pdf_path: Path
    page_num: int
    bbox: tuple[float, float, float, float]
    raw_text: str
    caption: str | None = None
    garbled: bool = False


@dataclass
class CostEntry:
    """One API call's cost record."""

    timestamp: str
    session_id: str
    table_id: str
    agent_role: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_write_tokens: int
    cache_read_tokens: int
    cost_usd: float


# ---------------------------------------------------------------------------
# Pricing (dollars per million tokens)
# ---------------------------------------------------------------------------

_PRICING: dict[str, dict[str, float]] = {
    "claude-haiku-4-5-20251001": {
        "input": 1.00,
        "output": 5.00,
        "cache_write": 1.25,
        "cache_read": 0.10,
    },
}


def _compute_cost(usage: object, model: str) -> float:
    """Compute USD cost from an API response's usage object."""
    prices = _PRICING.get(model, _PRICING["claude-haiku-4-5-20251001"])
    input_t = getattr(usage, "input_tokens", 0) or 0
    output_t = getattr(usage, "output_tokens", 0) or 0
    cache_w = getattr(usage, "cache_creation_input_tokens", 0) or 0
    cache_r = getattr(usage, "cache_read_input_tokens", 0) or 0
    return (
        input_t * prices["input"]
        + output_t * prices["output"]
        + cache_w * prices["cache_write"]
        + cache_r * prices["cache_read"]
    ) / 1_000_000


# ---------------------------------------------------------------------------
# Cost logging
# ---------------------------------------------------------------------------

_LOG_LOCK = asyncio.Lock()


async def _append_cost_entry(path: Path, entry: CostEntry) -> None:
    """Append a cost entry to the JSON log file (async-safe)."""
    async with _LOG_LOCK:
        entries: list[dict] = []
        if path.exists():
            try:
                entries = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                entries = []
        entries.append(asdict(entry))
        path.write_text(
            json.dumps(entries, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


# ---------------------------------------------------------------------------
# VisionAPI
# ---------------------------------------------------------------------------


class VisionAPI:
    """API access layer for vision table extraction with cost logging.

    Parameters
    ----------
    api_key:
        Anthropic API key.
    model:
        Model ID (default: claude-haiku-4-5-20251001).
    cost_log_path:
        Path to persistent JSON cost log file.
    cache:
        Enable prompt caching (system prompts cached across requests).
    dpi:
        PNG render resolution.
    padding_px:
        Padding around table bbox in pixels.
    concurrency:
        Max concurrent API calls for async mode.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-haiku-4-5-20251001",
        cost_log_path: Path | str = Path("vision_api_costs.json"),
        cache: bool = True,
        dpi: int = 300,
        padding_px: int = 20,
        concurrency: int = 50,
    ) -> None:
        if anthropic is None:
            raise ImportError("anthropic package required: pip install anthropic")

        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._sync_client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._cost_log_path = Path(cost_log_path)
        self._cache = cache
        self._dpi = dpi
        self._padding_px = padding_px
        self._concurrency = concurrency
        self._session_id = datetime.now(timezone.utc).isoformat()
        self._session_cost = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def session_cost(self) -> float:
        """Total USD cost accumulated this session."""
        return self._session_cost

    # ------------------------------------------------------------------
    # Generic batch infrastructure
    # ------------------------------------------------------------------

    def _create_batch(self, requests: list[dict]) -> str:
        """Submit a batch and return the batch ID (synchronous API call)."""
        batch = self._sync_client.messages.batches.create(requests=requests)
        logger.info("Submitted batch %s (%d requests)", batch.id, len(requests))
        return batch.id

    async def _poll_batch(
        self,
        batch_id: str,
        expected_count: int,
        poll_interval: float = 5.0,
    ) -> dict[str, str]:
        """Poll a batch until done, return {custom_id: response_text}."""
        while True:
            await asyncio.sleep(poll_interval)
            status = self._sync_client.messages.batches.retrieve(batch_id)
            if status.processing_status == "ended":
                break
            logger.debug("Batch %s status: %s", batch_id, status.processing_status)
            poll_interval = min(poll_interval * 1.5, 30.0)

        results: dict[str, str] = {}
        for result in self._sync_client.messages.batches.results(batch_id):
            cid = result.custom_id
            rtype = getattr(result.result, "type", "unknown")
            if rtype != "succeeded":
                logger.error(
                    "Batch result %s: type=%s (not succeeded) — "
                    "this table will have no data for this stage",
                    cid, rtype,
                )
                continue
            try:
                text = result.result.message.content[0].text
                results[cid] = text

                # Log cost for batch results
                usage = result.result.message.usage
                parts = cid.split("__")
                table_id = parts[0] if parts else cid
                role = parts[1] if len(parts) > 1 else "unknown"
                cost = _compute_cost(usage, self._model)
                self._session_cost += cost
                entry = CostEntry(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    session_id=self._session_id,
                    table_id=table_id,
                    agent_role=role,
                    model=self._model,
                    input_tokens=getattr(usage, "input_tokens", 0) or 0,
                    output_tokens=getattr(usage, "output_tokens", 0) or 0,
                    cache_write_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
                    cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
                    cost_usd=cost,
                )
                await _append_cost_entry(self._cost_log_path, entry)
            except (AttributeError, IndexError) as exc:
                logger.warning("Could not parse batch result %s: %s", cid, exc)

        if len(results) < expected_count:
            logger.error(
                "Batch %s: received %d/%d results — %d missing. "
                "Missing tables will have no data for this stage.",
                batch_id, len(results), expected_count,
                expected_count - len(results),
            )

        return results

    async def _submit_and_poll(
        self,
        requests: list[dict],
        poll_interval: float = 5.0,
    ) -> dict[str, str]:
        """Submit a batch, poll until done, return {custom_id: response_text}."""
        if not requests:
            return {}
        batch_id = self._create_batch(requests)
        return await self._poll_batch(batch_id, len(requests), poll_interval)

    # ------------------------------------------------------------------
    # Prompt text builders
    # ------------------------------------------------------------------

    def _prepare_table(
        self, spec: TableVisionSpec,
    ) -> tuple[str, str, tuple]:
        """Render PNG for a table spec. Returns (image_b64, media_type, bbox)."""
        png_bytes, media_type = render_table_png(
            spec.pdf_path, spec.page_num, spec.bbox,
            dpi=self._dpi, padding_px=self._padding_px,
        )
        image_b64 = base64.b64encode(png_bytes).decode("ascii")
        return image_b64, media_type, spec.bbox
