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
    _compute_agreement_rate,
    _compute_x_boundaries,
    _detect_inline_headers,
    _extract_word_positions,
    _format_x_evidence,
    _format_y_evidence,
    _parse_agent_json,
    _render_table_png,
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
# Response parsing (reused from vision_extract)
# ---------------------------------------------------------------------------


def _parse_response(raw_text: str, agent_label: str) -> AgentResponse:
    """Parse raw API response text into AgentResponse."""
    _failure = AgentResponse(
        headers=[], rows=[], footnotes="",
        table_label=None, is_incomplete=False,
        incomplete_reason="", raw_shape=(0, 0),
        parse_success=False, raw_response=raw_text,
    )

    parsed = _parse_agent_json(raw_text)
    if parsed is None:
        logger.warning("%s failed to parse JSON", agent_label)
        return _failure

    try:
        headers = parsed["headers"]
        rows = parsed["rows"]
        if not isinstance(headers, list):
            raise ValueError("headers must be a list")
        if not isinstance(rows, list):
            raise ValueError("rows must be a list")
        for r in rows:
            if not isinstance(r, list):
                raise ValueError("each row must be a list")

        corrections = parsed.get("corrections", [])
        if corrections:
            logger.info(
                "%s made %d corrections: %s",
                agent_label, len(corrections), corrections,
            )

        table_label = parsed.get("table_label")
        return AgentResponse(
            headers=[str(h) for h in headers],
            rows=[[str(c) for c in row] for row in rows],
            footnotes=str(parsed.get("footnotes", "")),
            table_label=table_label if isinstance(table_label, str) else None,
            is_incomplete=bool(parsed.get("is_incomplete", False)),
            incomplete_reason=str(parsed.get("incomplete_reason", "")),
            raw_shape=(len(rows), len(headers)),
            parse_success=True,
            raw_response=raw_text,
        )

    except (KeyError, ValueError, TypeError) as exc:
        logger.warning("%s response validation failed: %s", agent_label, exc)
        return _failure


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
        for spec, (image_b64, media_type, bbox), t_resp in zip(
            specs, prep, transcriber_results
        ):
            verifier_inputs.append(
                self._build_verifier_inputs(spec, image_b64, media_type, bbox, t_resp)
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
            agreement = _compute_agreement_rate(authority, all_responses)
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
                png, mt = _render_table_png(
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
                raw_text=spec.raw_text, caption=spec.caption,
            ))

        # All requests in a single batch — the Batch API provides cache
        # hits on a best-effort basis within the same batch.  Splitting
        # into warm-up + remainder would be worse (separate batches).
        raw_results = await self._submit_and_poll(requests)

        results = []
        for spec in specs:
            key = f"{spec.table_id}__{role}"
            text = raw_results.get(key, "")
            results.append(_parse_response(text, f"{role}[{spec.table_id}]"))
        return results

    async def _submit_verifier_batch(
        self,
        specs: list[TableVisionSpec],
        prep: list[tuple[str, str, tuple]],
        verifier_inputs: list[tuple[str, str, str]],
    ) -> tuple[list[AgentResponse], list[AgentResponse]]:
        """Submit Y+X verifier requests as a single batch."""
        requests = []
        for spec, (image_b64, media_type, _bbox), (y_text, x_text, _ih) in zip(
            specs, prep, verifier_inputs,
        ):
            requests.append(self._build_batch_request(
                f"{spec.table_id}__y_verifier",
                "y_verifier", image_b64, media_type, y_text,
                raw_text=spec.raw_text, caption=spec.caption,
            ))
            requests.append(self._build_batch_request(
                f"{spec.table_id}__x_verifier",
                "x_verifier", image_b64, media_type, x_text,
                raw_text=spec.raw_text, caption=spec.caption,
            ))

        raw_results = await self._submit_and_poll(requests)

        y_results, x_results = [], []
        for spec in specs:
            y_key = f"{spec.table_id}__y_verifier"
            x_key = f"{spec.table_id}__x_verifier"
            y_results.append(_parse_response(
                raw_results.get(y_key, ""), f"y_verifier[{spec.table_id}]",
            ))
            x_results.append(_parse_response(
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
        verifier_inputs: list[tuple[str, str, str]],
    ) -> list[AgentResponse]:
        """Submit synthesizer requests as a batch."""
        requests = []
        for spec, (image_b64, media_type, _bbox), t, y, x, (_, _, ih) in zip(
            specs, prep, t_results, y_results, x_results, verifier_inputs,
        ):
            synth_text = self._build_synthesizer_user_text(spec, t, y, x, ih)
            requests.append(self._build_batch_request(
                f"{spec.table_id}__synthesizer",
                "synthesizer", image_b64, media_type, synth_text,
                raw_text=spec.raw_text, caption=spec.caption,
            ))

        raw_results = await self._submit_and_poll(requests)

        results = []
        for spec in specs:
            key = f"{spec.table_id}__synthesizer"
            results.append(_parse_response(
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
    ) -> dict:
        """Build one Anthropic batch request dict with dual cache breakpoints."""
        system_blocks = [{"type": "text", "text": SHARED_SYSTEM}]
        if self._cache:
            system_blocks[0]["cache_control"] = {"type": "ephemeral"}

        common_ctx = f"## Raw extracted text\n\n{raw_text}"
        if caption:
            common_ctx += f"\n\n## Caption\n\n{caption}"

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
            png_bytes, media_type = _render_table_png(
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
            "", raw_text=spec.raw_text, caption=spec.caption,
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
                    png2, mt2 = _render_table_png(
                        spec.pdf_path, spec.page_num, full,
                        dpi=self._dpi, padding_px=self._padding_px,
                    )
                    b64_2 = base64.b64encode(png2).decode("ascii")
                    t2 = await self._call_agent(
                        "transcriber", spec.table_id, b64_2, mt2,
                        "", raw_text=spec.raw_text, caption=spec.caption,
                    )
                    if t2.parse_success:
                        transcriber = t2
                        image_b64, media_type = b64_2, mt2
                        current_bbox, render_attempts = full, 2
                except Exception:
                    pass

        # Phase 2: Y-Verifier + X-Verifier (parallel)
        word_positions = _extract_word_positions(
            spec.pdf_path, spec.page_num, current_bbox,
        )
        y_evidence = _format_y_evidence(word_positions, headers=transcriber.headers)
        x_evidence = _format_x_evidence(word_positions)

        col_boundaries = _compute_x_boundaries(word_positions)
        inline_headers = _detect_inline_headers(
            word_positions, col_boundaries, transcriber.rows,
        )

        transcriber_json = json.dumps(
            {"table_label": transcriber.table_label,
             "headers": transcriber.headers,
             "rows": transcriber.rows,
             "footnotes": transcriber.footnotes},
            indent=2, ensure_ascii=False,
        )

        # -- inline header detection --
        if inline_headers:
            ih_section = inline_headers
            ih_instruction = (
                "INLINE SECTION HEADERS: The programmatic detection above found "
                "rows that have words ONLY in the leftmost column with NO data at "
                "column boundary positions. These are VERIFIED inline headers \u2014 "
                "each MUST be split into its own row with empty strings (\"\") in "
                "all data columns. Also check the IMAGE for any additional inline "
                "headers the detection may have missed."
            )
        else:
            ih_section = ""
            ih_instruction = (
                "CRITICAL \u2014 INLINE SECTION HEADERS: Look at the table IMAGE "
                "carefully. Many tables have inline section headers \u2014 bold or "
                "italic labels like \"Baseline\", \"Conversation\", \"Panel A\", "
                "\"Males\", \"Females\" that span the full table width with NO "
                "data values. These MUST be their own row with empty strings "
                "(\"\") in all data columns. The transcriber almost always merges "
                "these into the data row below. If you see ANY such labels in the "
                "image, add them as separate rows. USE THE IMAGE for this check."
            )

        # -- Y-Verifier role text (no raw_text/caption — those are in common context) --
        y_user_text = (
            f"## Transcriber's extraction\n\n{transcriber_json}\n\n"
            f"## Row gap analysis\n\n{y_evidence}\n\n"
        )
        if ih_section:
            y_user_text += f"{ih_section}\n\n"
        y_user_text += (
            f"## Verification\n\n{ih_instruction}\n\n"
            f"Additional checks:\n"
            f"1. COMPARE the transcriber's row count ({transcriber.raw_shape[0]} "
            f"data rows + 1 header row = {transcriber.raw_shape[0] + 1} total rows) "
            f"against what you see in the image.\n"
            f"2. SUBSCRIPTS: Very small gaps between adjacent rows indicate "
            f"sub/superscripts \u2014 these belong to the row above, NOT separate rows.\n"
            f"3. MERGED ROWS: Two visually distinct rows the transcriber combined.\n"
            f"4. MISSING ROWS: Rows visible in the image with no match.\n"
        )

        # -- X-Verifier role text --
        x_user_text = (
            f"## Transcriber's extraction\n\n{transcriber_json}\n\n"
            f"## Column gap analysis (cliff method)\n\n"
            f"Inter-word gaps from all rows are pooled and sorted. The \"cliff\" "
            f"is the largest ratio jump, separating small within-cell word spacing "
            f"from larger column-boundary gaps.\n\n{x_evidence}\n\n"
            f"## Verification\n\n"
            f"Compare the suggested column count against the transcriber "
            f"({transcriber.raw_shape[1]} columns).\n"
        )

        y_verifier, x_verifier = await asyncio.gather(
            self._call_agent(
                "y_verifier", spec.table_id, image_b64, media_type,
                y_user_text, raw_text=spec.raw_text, caption=spec.caption,
            ),
            self._call_agent(
                "x_verifier", spec.table_id, image_b64, media_type,
                x_user_text, raw_text=spec.raw_text, caption=spec.caption,
            ),
        )

        # Phase 3: Synthesizer
        def _agent_json(resp: AgentResponse) -> str:
            if not resp.parse_success:
                return "(agent failed to produce valid output)"
            return json.dumps(
                {"table_label": resp.table_label, "headers": resp.headers,
                 "rows": resp.rows, "footnotes": resp.footnotes},
                indent=2, ensure_ascii=False,
            )

        def _corrections(resp: AgentResponse) -> str:
            if not resp.parse_success:
                return "N/A (agent failed)"
            parsed = _parse_agent_json(resp.raw_response)
            if parsed and parsed.get("corrections"):
                return json.dumps(parsed["corrections"], ensure_ascii=False)
            return "None"

        def _shape(resp: AgentResponse) -> str:
            if not resp.parse_success:
                return "failed"
            return f"{resp.raw_shape[0]} rows x {resp.raw_shape[1]} cols"

        # -- Synthesizer role text (no raw_text/caption — in common context) --
        synth_user_text = (
            f"## Transcriber output ({_shape(transcriber)})\n\n"
            f"{_agent_json(transcriber)}\n\n"
            f"## Row verifier output ({_shape(y_verifier)})\n\n"
            f"{_agent_json(y_verifier)}\n\n"
            f"Row corrections: {_corrections(y_verifier)}\n\n"
            f"## Column verifier output ({_shape(x_verifier)})\n\n"
            f"{_agent_json(x_verifier)}\n\n"
            f"Column corrections: {_corrections(x_verifier)}\n"
        )
        if ih_section:
            synth_user_text += f"\n{ih_section}\n"

        synthesizer = await self._call_agent(
            "synthesizer", spec.table_id, image_b64, media_type,
            synth_user_text, raw_text=spec.raw_text, caption=spec.caption,
        )

        # Build result
        all_responses = [transcriber, y_verifier, x_verifier, synthesizer]
        authority = synthesizer if synthesizer.parse_success else transcriber
        agreement = _compute_agreement_rate(authority, all_responses)
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
        common_ctx = f"## Raw extracted text\n\n{raw_text}"
        if caption:
            common_ctx += f"\n\n## Caption\n\n{caption}"

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

        return _parse_response(raw_text, f"{role}[{table_id}]")

    # ------------------------------------------------------------------
    # Prompt text builders
    # ------------------------------------------------------------------

    def _prepare_table(
        self, spec: TableVisionSpec,
    ) -> tuple[str, str, tuple]:
        """Render PNG for a table spec. Returns (image_b64, media_type, bbox)."""
        png_bytes, media_type = _render_table_png(
            spec.pdf_path, spec.page_num, spec.bbox,
            dpi=self._dpi, padding_px=self._padding_px,
        )
        image_b64 = base64.b64encode(png_bytes).decode("ascii")
        return image_b64, media_type, spec.bbox

    def _build_verifier_inputs(
        self,
        spec: TableVisionSpec,
        image_b64: str,
        media_type: str,
        bbox: tuple,
        transcriber: AgentResponse,
    ) -> tuple[str, str, str]:
        """Build Y-verifier, X-verifier user texts and inline header evidence.

        Returns (y_user_text, x_user_text, inline_header_section).
        """
        word_positions = _extract_word_positions(
            spec.pdf_path, spec.page_num, bbox,
        )
        y_evidence = _format_y_evidence(word_positions, headers=transcriber.headers)
        x_evidence = _format_x_evidence(word_positions)

        col_boundaries = _compute_x_boundaries(word_positions)
        ih_section = _detect_inline_headers(
            word_positions, col_boundaries, transcriber.rows,
        )

        transcriber_json = json.dumps(
            {"table_label": transcriber.table_label,
             "headers": transcriber.headers,
             "rows": transcriber.rows,
             "footnotes": transcriber.footnotes},
            indent=2, ensure_ascii=False,
        )

        # raw_text and caption are in common context — NOT included here
        y_user_text = (
            f"## Transcriber's extraction\n\n{transcriber_json}\n\n"
            f"## Row gap analysis\n\n{y_evidence}\n\n"
            f"{ih_section + chr(10) + chr(10) if ih_section else ''}"
            f"Row count: {transcriber.raw_shape[0]} data rows + 1 header = "
            f"{transcriber.raw_shape[0] + 1} total\n"
        )

        x_user_text = (
            f"## Transcriber's extraction\n\n{transcriber_json}\n\n"
            f"## Column gap analysis\n\n{x_evidence}\n\n"
            f"Transcriber column count: {transcriber.raw_shape[1]}\n"
        )

        return y_user_text, x_user_text, ih_section

    def _build_synthesizer_user_text(
        self,
        spec: TableVisionSpec,
        transcriber: AgentResponse,
        y_verifier: AgentResponse,
        x_verifier: AgentResponse,
        inline_headers: str,
    ) -> str:
        """Build Synthesizer role-specific text (raw_text/caption in common context)."""
        def _aj(resp: AgentResponse) -> str:
            if not resp.parse_success:
                return "(agent failed)"
            return json.dumps(
                {"table_label": resp.table_label, "headers": resp.headers,
                 "rows": resp.rows, "footnotes": resp.footnotes},
                indent=2, ensure_ascii=False,
            )

        def _corr(resp: AgentResponse) -> str:
            if not resp.parse_success:
                return "N/A"
            parsed = _parse_agent_json(resp.raw_response)
            if parsed and parsed.get("corrections"):
                return json.dumps(parsed["corrections"], ensure_ascii=False)
            return "None"

        def _sh(resp: AgentResponse) -> str:
            if not resp.parse_success:
                return "failed"
            return f"{resp.raw_shape[0]}r x {resp.raw_shape[1]}c"

        text = (
            f"## Transcriber ({_sh(transcriber)})\n\n{_aj(transcriber)}\n\n"
            f"## Row verifier ({_sh(y_verifier)})\n\n{_aj(y_verifier)}\n\n"
            f"Row corrections: {_corr(y_verifier)}\n\n"
            f"## Column verifier ({_sh(x_verifier)})\n\n{_aj(x_verifier)}\n\n"
            f"Column corrections: {_corr(x_verifier)}\n"
        )
        if inline_headers:
            text += f"\n{inline_headers}\n"
        return text
