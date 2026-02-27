"""Vision API: unified interface for vision table extraction.

Abstracts prompt construction with caching, parallel/batch execution,
and cost logging.

Usage::

    api = VisionAPI(api_key="...", model="claude-haiku-4-5-20251001")
    results = asyncio.run(api.extract_tables(specs, batch=False))

    # Or from sync context (e.g. indexer):
    results = api.extract_tables_sync(specs, batch=False)
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
    SHARED_SYSTEM,
    AgentResponse,
    ConsensusResult,
    VisionExtractionResult,
    _MAX_TOKENS,
    _ROLE_PREAMBLES,
    build_common_ctx,
    build_verifier_inputs,
    build_synthesizer_user_text,
    compute_agreement_rate,
    detect_garbled_encoding,
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
    """Unified interface for vision table extraction with caching and cost logging.

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

    async def extract_tables(
        self,
        specs: list[TableVisionSpec],
        batch: bool = False,
    ) -> list[tuple[TableVisionSpec, VisionExtractionResult]]:
        """Extract all tables via the 4-agent adversarial pipeline.

        Parameters
        ----------
        specs:
            List of table specifications to extract.
        batch:
            If True, use the Anthropic Batch API (3-stage pipeline).
            If False, use asyncio.gather with semaphore.

        Returns
        -------
        list[tuple[TableVisionSpec, VisionExtractionResult]]
            Paired (spec, result) for each input spec.
        """
        if not specs:
            return []

        # Pre-flight: detect garbled font encoding on each spec's raw text
        for spec in specs:
            if not spec.garbled and detect_garbled_encoding(spec.raw_text):
                spec.garbled = True
                logger.info(
                    "Garbled encoding detected for %s — agents will trust image for symbols",
                    spec.table_id,
                )

        if batch:
            return await self._batch_extract(specs)
        return await self._async_extract(specs)

    def extract_tables_sync(
        self,
        specs: list[TableVisionSpec],
        batch: bool = False,
    ) -> list[tuple[TableVisionSpec, VisionExtractionResult]]:
        """Synchronous wrapper around extract_tables."""
        return asyncio.run(self.extract_tables(specs, batch=batch))

    @property
    def session_cost(self) -> float:
        """Total USD cost accumulated this session."""
        return self._session_cost

    # ------------------------------------------------------------------
    # Async extraction (asyncio.gather with semaphore)
    # ------------------------------------------------------------------

    async def _async_extract(
        self,
        specs: list[TableVisionSpec],
    ) -> list[tuple[TableVisionSpec, VisionExtractionResult]]:
        sem = asyncio.Semaphore(self._concurrency)

        async def _run_one(spec: TableVisionSpec) -> tuple[TableVisionSpec, VisionExtractionResult]:
            async with sem:
                result = await self._run_pipeline(spec)
                return (spec, result)

        # Warm-up: run the first table sequentially to write the system
        # prompt cache (breakpoint 1).  All subsequent parallel calls
        # then get cache reads on the ~5k-token system prefix.
        # Within each table, the sequential 4-agent pipeline handles
        # breakpoint 2 (image cache) automatically.
        if self._cache and len(specs) > 1:
            first_result = await _run_one(specs[0])
            rest_results = await asyncio.gather(
                *(_run_one(s) for s in specs[1:]),
                return_exceptions=True,
            )
            all_results = [first_result, *rest_results]
        else:
            all_results = await asyncio.gather(
                *(_run_one(s) for s in specs),
                return_exceptions=True,
            )

        # Filter out exceptions
        results: list[tuple[TableVisionSpec, VisionExtractionResult]] = []
        for i, r in enumerate(all_results):
            if isinstance(r, Exception):
                logger.error("Table %s failed: %s", specs[i].table_id, r)
                results.append((
                    specs[i],
                    VisionExtractionResult(
                        consensus=None, agent_responses=[],
                        error=str(r), timing_ms=0.0,
                    ),
                ))
            else:
                results.append(r)

        return results

    # ------------------------------------------------------------------
    # Batch extraction (3-stage Batch API pipeline)
    # ------------------------------------------------------------------

    async def _batch_extract(
        self,
        specs: list[TableVisionSpec],
    ) -> list[tuple[TableVisionSpec, VisionExtractionResult]]:
        """3-stage batch pipeline: Transcriber -> Verifiers -> Synthesizer.

        Each stage submits all requests in a single batch.  The Batch API
        provides prompt cache hits on a best-effort basis within a batch.
        """
        # Stage 1: Transcriber
        logger.info("Batch Stage 1: Transcribers (%d tables)", len(specs))
        prep = [self._prepare_table(s) for s in specs]
        transcriber_results = await self._submit_batch_stage(
            "transcriber", specs, prep,
        )

        # Stage 1b: Retry incomplete/empty transcriptions with expanded bbox
        prep, transcriber_results = await self._retry_incomplete_transcriptions(
            specs, prep, transcriber_results,
        )

        # Stage 2: Verifiers (Y + X for each table)
        logger.info("Batch Stage 2: Verifiers (%d tables)", len(specs))
        verifier_inputs = []
        for spec, (_image_b64, _media_type, bbox), t_resp in zip(
            specs, prep, transcriber_results
        ):
            verifier_inputs.append(
                build_verifier_inputs(spec.pdf_path, spec.page_num, bbox, t_resp)
            )
        y_results, x_results = await self._submit_verifier_batch(
            specs, prep, verifier_inputs,
        )

        # Stage 3: Synthesizer
        logger.info("Batch Stage 3: Synthesizers (%d tables)", len(specs))
        results: list[tuple[TableVisionSpec, VisionExtractionResult]] = []
        synth_results = await self._submit_synthesizer_batch(
            specs, prep, transcriber_results, y_results, x_results,
            verifier_inputs,
        )

        for spec, t_resp, y_resp, x_resp, s_resp in zip(
            specs, transcriber_results, y_results, x_results, synth_results,
        ):
            all_responses = [t_resp, y_resp, x_resp, s_resp]
            authority = s_resp if s_resp.parse_success else t_resp
            agreement = compute_agreement_rate(authority, all_responses)
            successful = [r for r in all_responses if r.parse_success]
            shape_agreeing = sum(
                1 for r in successful if r.raw_shape == authority.raw_shape
            )

            consensus = ConsensusResult(
                headers=tuple(authority.headers),
                rows=tuple(tuple(r) for r in authority.rows),
                footnotes=authority.footnotes,
                table_label=authority.table_label,
                is_incomplete=authority.is_incomplete,
                disputed_cells=[],
                agent_agreement_rate=agreement,
                shape_agreement=shape_agreeing >= 2,
                winning_shape=authority.raw_shape,
                num_agents_succeeded=len(successful),
            )

            results.append((
                spec,
                VisionExtractionResult(
                    consensus=consensus,
                    agent_responses=all_responses,
                    render_attempts=1,
                    timing_ms=0.0,
                ),
            ))

        return results

    @staticmethod
    def _needs_retry(resp: AgentResponse) -> bool:
        """Check if a transcriber result needs bbox expansion retry."""
        if not resp.parse_success:
            return False
        if resp.is_incomplete:
            return True
        # Empty output (parsed OK but nothing found) — likely clipped bbox
        if not resp.headers and not resp.rows:
            return True
        return False

    async def _retry_incomplete_transcriptions(
        self,
        specs: list[TableVisionSpec],
        prep: list[tuple[str, str, tuple]],
        transcriber_results: list[AgentResponse],
    ) -> tuple[list[tuple[str, str, tuple]], list[AgentResponse]]:
        """Re-render incomplete/empty tables at full-page and re-transcribe.

        After the transcriber batch, any table whose result is incomplete or
        empty is re-rendered at full page resolution and re-submitted as a
        batch.  Returns the (possibly updated) prep and results lists.
        """
        import pymupdf

        retry_indices = [
            i for i, resp in enumerate(transcriber_results)
            if self._needs_retry(resp)
        ]
        if not retry_indices:
            return prep, transcriber_results

        logger.info(
            "Batch Stage 1b: Retrying %d incomplete/empty transcriptions "
            "(full page)",
            len(retry_indices),
        )

        # Make mutable copies
        prep = list(prep)
        transcriber_results = list(transcriber_results)

        # Re-render at full page and build retry batch inputs
        retry_specs: list[TableVisionSpec] = []
        retry_prep: list[tuple[str, str, tuple]] = []
        retry_map: list[int] = []  # maps retry index -> original index

        for idx in retry_indices:
            spec = specs[idx]
            try:
                doc = pymupdf.open(str(spec.pdf_path))
                page_rect = doc[spec.page_num - 1].rect
                page_w, page_h = page_rect.width, page_rect.height
                doc.close()
            except Exception:
                continue

            if page_w <= 0:
                continue

            full_bbox = (0.0, 0.0, page_w, page_h)
            try:
                png, mt = render_table_png(
                    spec.pdf_path, spec.page_num, full_bbox,
                    dpi=self._dpi, padding_px=self._padding_px,
                )
                b64 = base64.b64encode(png).decode("ascii")
                retry_specs.append(spec)
                retry_prep.append((b64, mt, full_bbox))
                retry_map.append(idx)
            except Exception:
                logger.warning(
                    "Full-page render failed for %s", spec.table_id,
                )

        if not retry_specs:
            return prep, transcriber_results

        # Submit retries as a batch
        retry_results = await self._submit_batch_stage(
            "transcriber", retry_specs, retry_prep,
        )

        # Merge successful retries back
        for ri, (idx, result) in enumerate(zip(retry_map, retry_results)):
            if result.parse_success:
                transcriber_results[idx] = result
                prep[idx] = retry_prep[ri]
                logger.info(
                    "Retry succeeded (full page) for %s",
                    specs[idx].table_id,
                )
            else:
                logger.warning(
                    "Retry failed for %s — still incomplete/empty",
                    specs[idx].table_id,
                )

        return prep, transcriber_results

    async def _submit_batch_stage(
        self,
        role: str,
        specs: list[TableVisionSpec],
        prep: list[tuple[str, str, tuple]],
    ) -> list[AgentResponse]:
        """Submit a batch of requests for a single role, poll, collect."""
        requests = []
        for i, (spec, (image_b64, media_type, _bbox)) in enumerate(zip(specs, prep)):
            requests.append(self._build_batch_request(
                f"{spec.table_id}__{role}",
                role, image_b64, media_type, "",
                raw_text=spec.raw_text, caption=spec.caption, garbled=spec.garbled,
            ))

        # All requests in a single batch — the Batch API provides cache
        # hits on a best-effort basis within the same batch.  Splitting
        # into warm-up + remainder would be worse (separate batches).
        raw_results = await self._submit_and_poll(requests)

        results = []
        for spec in specs:
            key = f"{spec.table_id}__{role}"
            text = raw_results.get(key, "")
            results.append(parse_agent_response(text, f"{role}[{spec.table_id}]"))
        return results

    async def _submit_verifier_batch(
        self,
        specs: list[TableVisionSpec],
        prep: list[tuple[str, str, tuple]],
        verifier_inputs: list[tuple[str, str, str, str]],
    ) -> tuple[list[AgentResponse], list[AgentResponse]]:
        """Submit Y+X verifier requests as a single batch."""
        requests = []
        for spec, (image_b64, media_type, _bbox), (y_text, x_text, _ih, _ih_instr) in zip(
            specs, prep, verifier_inputs,
        ):
            requests.append(self._build_batch_request(
                f"{spec.table_id}__y_verifier",
                "y_verifier", image_b64, media_type, y_text,
                raw_text=spec.raw_text, caption=spec.caption, garbled=spec.garbled,
            ))
            requests.append(self._build_batch_request(
                f"{spec.table_id}__x_verifier",
                "x_verifier", image_b64, media_type, x_text,
                raw_text=spec.raw_text, caption=spec.caption, garbled=spec.garbled,
            ))

        raw_results = await self._submit_and_poll(requests)

        y_results, x_results = [], []
        for spec in specs:
            y_key = f"{spec.table_id}__y_verifier"
            x_key = f"{spec.table_id}__x_verifier"
            y_results.append(parse_agent_response(
                raw_results.get(y_key, ""), f"y_verifier[{spec.table_id}]",
            ))
            x_results.append(parse_agent_response(
                raw_results.get(x_key, ""), f"x_verifier[{spec.table_id}]",
            ))
        return y_results, x_results

    async def _submit_synthesizer_batch(
        self,
        specs: list[TableVisionSpec],
        prep: list[tuple[str, str, tuple]],
        t_results: list[AgentResponse],
        y_results: list[AgentResponse],
        x_results: list[AgentResponse],
        verifier_inputs: list[tuple[str, str, str, str]],
    ) -> list[AgentResponse]:
        """Submit synthesizer requests as a batch."""
        requests = []
        for spec, (image_b64, media_type, _bbox), t, y, x, (_, _, ih, _ih_instr) in zip(
            specs, prep, t_results, y_results, x_results, verifier_inputs,
        ):
            synth_text = build_synthesizer_user_text(t, y, x, ih)
            requests.append(self._build_batch_request(
                f"{spec.table_id}__synthesizer",
                "synthesizer", image_b64, media_type, synth_text,
                raw_text=spec.raw_text, caption=spec.caption, garbled=spec.garbled,
            ))

        raw_results = await self._submit_and_poll(requests)

        results = []
        for spec in specs:
            key = f"{spec.table_id}__synthesizer"
            results.append(parse_agent_response(
                raw_results.get(key, ""), f"synthesizer[{spec.table_id}]",
            ))
        return results

    def _build_batch_request(
        self,
        custom_id: str,
        role: str,
        image_b64: str,
        media_type: str,
        role_text: str,
        raw_text: str = "",
        caption: str | None = None,
        garbled: bool = False,
    ) -> dict:
        """Build one Anthropic batch request dict with dual cache breakpoints."""
        system_blocks = [{"type": "text", "text": SHARED_SYSTEM}]
        if self._cache:
            system_blocks[0]["cache_control"] = {"type": "ephemeral"}

        common_ctx = build_common_ctx(raw_text, caption, garbled=garbled)

        image_block: dict = {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": image_b64,
            },
        }
        if self._cache:
            image_block["cache_control"] = {"type": "ephemeral"}

        full_role_text = _ROLE_PREAMBLES[role] + "\n" + role_text

        return {
            "custom_id": custom_id,
            "params": {
                "model": self._model,
                "max_tokens": _MAX_TOKENS[role],
                "system": system_blocks,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": common_ctx},
                        image_block,
                        {"type": "text", "text": full_role_text},
                    ],
                }],
            },
        }

    async def _submit_and_poll(
        self,
        requests: list[dict],
        poll_interval: float = 5.0,
    ) -> dict[str, str]:
        """Submit a batch, poll until done, return {custom_id: response_text}."""
        if not requests:
            return {}

        batch = self._sync_client.messages.batches.create(requests=requests)
        batch_id = batch.id
        logger.info("Submitted batch %s (%d requests)", batch_id, len(requests))

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

        return results

    # ------------------------------------------------------------------
    # Per-table pipeline (async mode)
    # ------------------------------------------------------------------

    async def _run_pipeline(
        self,
        spec: TableVisionSpec,
    ) -> VisionExtractionResult:
        """Run the full 4-agent adversarial pipeline for one table."""
        t0 = time.monotonic()

        # Render PNG
        try:
            png_bytes, media_type = render_table_png(
                spec.pdf_path, spec.page_num, spec.bbox,
                dpi=self._dpi, padding_px=self._padding_px,
            )
        except Exception as exc:
            return VisionExtractionResult(
                consensus=None, agent_responses=[],
                error=f"Render failed: {exc}",
                timing_ms=(time.monotonic() - t0) * 1000.0,
            )
        image_b64 = base64.b64encode(png_bytes).decode("ascii")
        current_bbox = spec.bbox

        # Phase 1: Transcriber
        # Role-specific text is empty — Transcriber uses the common context
        # (raw_text + caption) and the image, both provided via _call_agent.
        transcriber = await self._call_agent(
            "transcriber", spec.table_id, image_b64, media_type,
            "", raw_text=spec.raw_text, caption=spec.caption, garbled=spec.garbled,
        )

        if not transcriber.parse_success:
            elapsed = (time.monotonic() - t0) * 1000.0
            return VisionExtractionResult(
                consensus=None, agent_responses=[transcriber],
                render_attempts=1, error="Transcriber failed to parse",
                timing_ms=elapsed,
            )

        # Handle incomplete or empty: retry with full page render
        import pymupdf
        render_attempts = 1
        if self._needs_retry(transcriber):
            try:
                doc = pymupdf.open(str(spec.pdf_path))
                page_rect = doc[spec.page_num - 1].rect
                page_w, page_h = page_rect.width, page_rect.height
                doc.close()
            except Exception:
                page_w = page_h = 0.0

            if page_w > 0:
                full = (0.0, 0.0, page_w, page_h)
                try:
                    png2, mt2 = render_table_png(
                        spec.pdf_path, spec.page_num, full,
                        dpi=self._dpi, padding_px=self._padding_px,
                    )
                    b64_2 = base64.b64encode(png2).decode("ascii")
                    t2 = await self._call_agent(
                        "transcriber", spec.table_id, b64_2, mt2,
                        "", raw_text=spec.raw_text, caption=spec.caption, garbled=spec.garbled,
                    )
                    if t2.parse_success:
                        transcriber = t2
                        image_b64, media_type = b64_2, mt2
                        current_bbox, render_attempts = full, 2
                except Exception:
                    pass

        # Phase 2: Y-Verifier + X-Verifier (parallel)
        y_role_text, x_role_text, inline_header_section, _inline_header_instruction = (
            build_verifier_inputs(spec.pdf_path, spec.page_num, current_bbox, transcriber)
        )

        y_verifier, x_verifier = await asyncio.gather(
            self._call_agent(
                "y_verifier", spec.table_id, image_b64, media_type,
                y_role_text, raw_text=spec.raw_text, caption=spec.caption, garbled=spec.garbled,
            ),
            self._call_agent(
                "x_verifier", spec.table_id, image_b64, media_type,
                x_role_text, raw_text=spec.raw_text, caption=spec.caption, garbled=spec.garbled,
            ),
        )

        # Phase 3: Synthesizer
        synth_user_text = build_synthesizer_user_text(
            transcriber, y_verifier, x_verifier, inline_header_section,
        )

        synthesizer = await self._call_agent(
            "synthesizer", spec.table_id, image_b64, media_type,
            synth_user_text, raw_text=spec.raw_text, caption=spec.caption, garbled=spec.garbled,
        )

        # Build result
        all_responses = [transcriber, y_verifier, x_verifier, synthesizer]
        authority = synthesizer if synthesizer.parse_success else transcriber
        agreement = compute_agreement_rate(authority, all_responses)
        successful = [r for r in all_responses if r.parse_success]
        shape_agreeing = sum(
            1 for r in successful if r.raw_shape == authority.raw_shape
        )

        consensus = ConsensusResult(
            headers=tuple(authority.headers),
            rows=tuple(tuple(r) for r in authority.rows),
            footnotes=authority.footnotes,
            table_label=authority.table_label,
            is_incomplete=authority.is_incomplete,
            disputed_cells=[],
            agent_agreement_rate=agreement,
            shape_agreement=shape_agreeing >= 2,
            winning_shape=authority.raw_shape,
            num_agents_succeeded=len(successful),
        )

        elapsed_ms = (time.monotonic() - t0) * 1000.0
        logger.info(
            "Pipeline complete [%s]: shape=%s, agreement=%.0f%%, "
            "T=%s Y=%s X=%s S=%s, %.0fms",
            spec.table_id, authority.raw_shape, agreement * 100,
            "ok" if transcriber.parse_success else "FAIL",
            "ok" if y_verifier.parse_success else "FAIL",
            "ok" if x_verifier.parse_success else "FAIL",
            "ok" if synthesizer.parse_success else "FAIL",
            elapsed_ms,
        )

        return VisionExtractionResult(
            consensus=consensus,
            agent_responses=all_responses,
            render_attempts=render_attempts,
            timing_ms=elapsed_ms,
        )

    # ------------------------------------------------------------------
    # API call with caching + cost logging
    # ------------------------------------------------------------------

    async def _call_agent(
        self,
        role: str,
        table_id: str,
        image_b64: str,
        media_type: str,
        role_text: str,
        raw_text: str = "",
        caption: str | None = None,
        garbled: bool = False,
    ) -> AgentResponse:
        """Call one agent with shared system prompt + dual cache breakpoints.

        Cache strategy:
          Breakpoint 1 (system): SHARED_SYSTEM cached across ALL calls.
          Breakpoint 2 (image):  system + common_context + image cached
                                 within one table's 4-agent pipeline.
        """
        # Breakpoint 1: shared system prompt (cached across all calls)
        system_blocks: list[dict] = [
            {"type": "text", "text": SHARED_SYSTEM},
        ]
        if self._cache:
            system_blocks[0]["cache_control"] = {"type": "ephemeral"}

        # Common context (identical for all 4 roles on the same table)
        common_ctx = build_common_ctx(raw_text, caption, garbled=garbled)

        # Breakpoint 2: image block (cached within one table's pipeline)
        image_block: dict = {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": image_b64,
            },
        }
        if self._cache:
            image_block["cache_control"] = {"type": "ephemeral"}

        # Role-specific text (varies per agent — NOT cached)
        full_role_text = _ROLE_PREAMBLES[role] + "\n" + role_text

        _failure = AgentResponse(
            headers=[], rows=[], footnotes="",
            table_label=None, is_incomplete=False,
            incomplete_reason="", raw_shape=(0, 0),
            parse_success=False, raw_response="",
        )

        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=_MAX_TOKENS[role],
                system=system_blocks,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": common_ctx},
                        image_block,
                        {"type": "text", "text": full_role_text},
                    ],
                }],
            )
        except Exception as exc:
            logger.warning("%s[%s] API error: %s", role, table_id, exc)
            _failure.raw_response = str(exc)
            return _failure

        # Log cost
        usage = response.usage
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

        cache_info = (
            f"cache_write={entry.cache_write_tokens}, "
            f"cache_read={entry.cache_read_tokens}"
        )
        logger.debug(
            "%s[%s] %d in + %d out, %s, $%.6f",
            role, table_id, entry.input_tokens, entry.output_tokens,
            cache_info, cost,
        )

        # Parse response
        raw_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                raw_text += block.text

        return parse_agent_response(raw_text, f"{role}[{table_id}]")

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

