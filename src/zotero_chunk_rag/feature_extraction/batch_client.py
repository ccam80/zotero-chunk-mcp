"""Two-stage Anthropic Batch API client for bulk vision extraction.

Stage 1 — Submit: Render PNGs, build requests, submit batch, persist batch_id to SQLite.
Stage 2 — Collect: On next invocation, check status. If ended, retrieve and parse results.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

try:
    import anthropic
except ImportError:
    anthropic = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

VISION_BATCH_SCHEMA = """\
CREATE TABLE IF NOT EXISTS vision_batches (
    batch_id        TEXT PRIMARY KEY,
    submitted_at    TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    collected_at    TEXT,
    num_requests    INTEGER,
    num_tables      INTEGER,
    paper_keys_json TEXT,
    table_ids_json  TEXT
);
"""


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class BatchTableRequest:
    """One table extraction request for the batch."""

    paper_key: str
    table_id: str
    agent_idx: int  # 0, 1, 2 (for 3 agents per table)
    image_b64: str
    media_type: str
    raw_text: str
    caption: str | None


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class VisionBatchClient:
    """Persist-and-resume client for the Anthropic Message Batches API."""

    def __init__(
        self,
        db_path: Path,
        api_key: str | None = None,
        model: str = "claude-haiku-4-5-20251001",
    ) -> None:
        if anthropic is None:
            raise ImportError(
                "anthropic package is not installed. "
                "Install it with: pip install anthropic"
            )
        self._client = anthropic.Anthropic(api_key=api_key)
        self._db_path = db_path
        self._model = model
        self._ensure_schema()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_schema(self) -> None:
        """Create vision_batches table if not exists."""
        conn = sqlite3.connect(str(self._db_path))
        try:
            conn.executescript(VISION_BATCH_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def _build_prompt_text(self, raw_text: str, caption: str | None) -> str:
        """Build the prompt text with raw_text and caption interpolated."""
        from .vision_extract import CAPTION_SECTION_TEMPLATE, VISION_PROMPT_TEMPLATE

        caption_section = (
            CAPTION_SECTION_TEMPLATE.format(caption=caption)
            if caption
            else ""
        )
        return VISION_PROMPT_TEMPLATE.format(
            raw_text=raw_text,
            caption_section=caption_section,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def prepare_requests(
        self,
        tables: list[tuple[str, str, str, str, str | None]],
        num_agents: int = 3,
    ) -> list[dict]:
        """Build batch API request dicts.

        Parameters
        ----------
        tables:
            List of ``(paper_key, table_id, image_b64, raw_text, caption)`` tuples.
        num_agents:
            Number of parallel agent requests to create per table (default 3).

        Returns
        -------
        list[dict]
            Request dicts in the Anthropic batch format, ready for submission.
        """
        requests: list[dict] = []
        for paper_key, table_id, image_b64, raw_text, caption in tables:
            prompt_text = self._build_prompt_text(raw_text, caption)
            # Detect media type from base64 header if possible; default to png.
            media_type = "image/png"
            for agent_idx in range(num_agents):
                custom_id = f"{paper_key}__{table_id}__{agent_idx}"
                requests.append(
                    {
                        "custom_id": custom_id,
                        "params": {
                            "model": self._model,
                            "max_tokens": 4096,
                            "messages": [
                                {
                                    "role": "user",
                                    "content": [
                                        {
                                            "type": "image",
                                            "source": {
                                                "type": "base64",
                                                "media_type": media_type,
                                                "data": image_b64,
                                            },
                                        },
                                        {
                                            "type": "text",
                                            "text": prompt_text,
                                        },
                                    ],
                                }
                            ],
                        },
                    }
                )
        logger.debug(
            "Prepared %d batch requests for %d tables (%d agents each).",
            len(requests),
            len(tables),
            num_agents,
        )
        return requests

    def submit_batch(
        self,
        requests: list[dict],
        paper_keys: list[str],
        table_ids: list[str],
    ) -> str:
        """Submit requests to the Anthropic Batch API and persist metadata.

        Parameters
        ----------
        requests:
            Request dicts produced by :meth:`prepare_requests`.
        paper_keys:
            Unique paper keys included in this batch (for bookkeeping).
        table_ids:
            Unique table IDs included in this batch (for bookkeeping).

        Returns
        -------
        str
            The batch_id assigned by Anthropic.

        Raises
        ------
        anthropic.APIError
            On API-level failures during submission.
        """
        batch = self._client.messages.batches.create(requests=requests)
        batch_id: str = batch.id
        now = datetime.now(timezone.utc).isoformat()

        conn = sqlite3.connect(str(self._db_path))
        try:
            conn.execute(
                """
                INSERT INTO vision_batches
                    (batch_id, submitted_at, status, num_requests, num_tables,
                     paper_keys_json, table_ids_json)
                VALUES (?, ?, 'pending', ?, ?, ?, ?)
                """,
                (
                    batch_id,
                    now,
                    len(requests),
                    len(table_ids),
                    json.dumps(paper_keys),
                    json.dumps(table_ids),
                ),
            )
            conn.commit()
        finally:
            conn.close()

        logger.info(
            "Submitted batch %s: %d requests, %d tables.",
            batch_id,
            len(requests),
            len(table_ids),
        )
        return batch_id

    def check_batch_status(self, batch_id: str) -> str:
        """Return the current processing status for a batch.

        Parameters
        ----------
        batch_id:
            Batch ID returned by :meth:`submit_batch`.

        Returns
        -------
        str
            One of ``'in_progress'``, ``'ended'``, ``'canceling'``,
            ``'canceled'``, or ``'expired'``.
        """
        batch = self._client.messages.batches.retrieve(batch_id)
        status: str = batch.processing_status
        logger.debug("Batch %s status: %s", batch_id, status)
        return status

    def collect_batch(self, batch_id: str) -> dict[str, list[dict]]:
        """Retrieve and parse results for a completed batch.

        Only call when :meth:`check_batch_status` returns ``'ended'``.

        Parameters
        ----------
        batch_id:
            Batch ID to collect.

        Returns
        -------
        dict[str, list[dict]]
            Mapping of ``table_id`` -> list of parsed response dicts
            (one per agent).
        """
        from .vision_extract import _parse_agent_json

        grouped: dict[str, list[dict]] = {}

        for result in self._client.messages.batches.results(batch_id):
            custom_id: str = result.custom_id
            parts = custom_id.split("__")
            if len(parts) != 3:
                logger.warning("Unexpected custom_id format: %r — skipping.", custom_id)
                continue

            _paper_key, table_id, _agent_idx = parts

            try:
                text = result.result.message.content[0].text
            except (AttributeError, IndexError) as exc:
                logger.warning(
                    "Could not extract text from result %r: %s", custom_id, exc
                )
                continue

            parsed = _parse_agent_json(text)
            grouped.setdefault(table_id, []).append(parsed)

        now = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(str(self._db_path))
        try:
            conn.execute(
                "UPDATE vision_batches SET status='collected', collected_at=? WHERE batch_id=?",
                (now, batch_id),
            )
            conn.commit()
        finally:
            conn.close()

        logger.info(
            "Collected batch %s: results for %d tables.", batch_id, len(grouped)
        )
        return grouped

    def get_pending_batches(self) -> list[dict]:
        """Return all batches with status ``'pending'`` or ``'in_progress'``.

        Returns
        -------
        list[dict]
            Each dict contains ``batch_id``, ``submitted_at``, and ``num_tables``.
        """
        conn = sqlite3.connect(str(self._db_path))
        try:
            cursor = conn.execute(
                """
                SELECT batch_id, submitted_at, num_tables
                FROM vision_batches
                WHERE status IN ('pending', 'in_progress')
                ORDER BY submitted_at ASC
                """
            )
            rows = cursor.fetchall()
        finally:
            conn.close()

        return [
            {"batch_id": row[0], "submitted_at": row[1], "num_tables": row[2]}
            for row in rows
        ]

    def cancel_batch(self, batch_id: str) -> None:
        """Cancel a running batch.

        Parameters
        ----------
        batch_id:
            Batch ID to cancel.
        """
        self._client.messages.batches.cancel(batch_id)

        conn = sqlite3.connect(str(self._db_path))
        try:
            conn.execute(
                "UPDATE vision_batches SET status='cancelled' WHERE batch_id=?",
                (batch_id,),
            )
            conn.commit()
        finally:
            conn.close()

        logger.info("Cancelled batch %s.", batch_id)
