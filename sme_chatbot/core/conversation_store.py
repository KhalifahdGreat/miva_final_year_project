"""Postgres-backed conversation persistence and audit logging.

Three responsibilities live in this module:

    * `PostgresHistoryStore`   — implements the `HistoryStore` protocol
                                  used by the orchestrator; reads and
                                  writes `conversations` and `turns`.
    * `AuditStore`             — writes `audit_records` for every
                                  orchestrator turn so that the
                                  evaluation in Chapter 5 has data.
    * `IdempotencyStore`       — guards against WhatsApp's at-least-once
                                  webhook deliveries via the
                                  `processed_messages` table.

All three accept a psycopg `ConnectionPool` so they remain pure-Python
and unit-testable without FastAPI in the dependency tree.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from .orchestrator import HistoryStore
from .types import OrchestrationResult, Turn

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _json_safe(d: Any) -> str:
    try:
        return json.dumps(d, default=str)
    except Exception:
        return "{}"


# ---------------------------------------------------------------------------
# PostgresHistoryStore
# ---------------------------------------------------------------------------


class PostgresHistoryStore(HistoryStore):
    """Persistent (conversation, turns) backing store."""

    def __init__(self, pool) -> None:
        self._pool = pool

    # --- conversation lookup / creation --------------------------------

    def _conversation_id(self, tenant_id: str, channel: str, sender_id: str) -> str:
        """Return the canonical conversation_id for this (tenant, channel, sender).

        Conversations are eternal — a single sender on a single channel for a
        single tenant always maps to the same conversation_id, so review and
        evaluation see the full history rather than a fresh row per session.
        """
        with self._pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO conversations (conversation_id, tenant_id, channel, sender_id,
                                            started_at, last_turn_at, turn_count)
                VALUES (gen_random_uuid(), %s, %s, %s, NOW(), NOW(), 0)
                ON CONFLICT (tenant_id, channel, sender_id) DO UPDATE
                    SET last_turn_at = EXCLUDED.last_turn_at
                RETURNING conversation_id
                """,
                (tenant_id, channel, sender_id),
            )
            return str(cur.fetchone()[0])

    # --- HistoryStore protocol -----------------------------------------

    def append(self, tenant_id: str, sender_id: str, turn: Turn) -> None:
        """Default appender — used when channel is unknown (in-memory path).

        In the orchestrator path we prefer the richer `append_with_meta`
        below, which carries channel + detected language + escalation
        signals onto the turn row.
        """
        self.append_with_meta(
            tenant_id=tenant_id,
            channel="widget",
            sender_id=sender_id,
            turn=turn,
        )

    def append_with_meta(
        self,
        *,
        tenant_id: str,
        channel: str,
        sender_id: str,
        turn: Turn,
        detected_language: str | None = None,
        is_mixed_language: bool | None = None,
        escalated: bool = False,
        escalation_reason: str | None = None,
        channel_msg_id: str | None = None,
    ) -> str:
        """Write a turn and return its turn_id."""
        conv_id = self._conversation_id(tenant_id, channel, sender_id)
        with self._pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO turns (turn_id, conversation_id, tenant_id, role, text,
                                    received_at, detected_language, is_mixed_language,
                                    escalated, escalation_reason, channel_msg_id)
                VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING turn_id
                """,
                (
                    conv_id, tenant_id, turn.role, turn.text, turn.ts,
                    detected_language, is_mixed_language,
                    escalated, escalation_reason, channel_msg_id,
                ),
            )
            turn_id = str(cur.fetchone()[0])
            cur.execute(
                """
                UPDATE conversations
                    SET last_turn_at = %s,
                        turn_count   = turn_count + 1,
                        languages_seen = (
                            SELECT ARRAY(
                                SELECT DISTINCT UNNEST(languages_seen || %s::text[])
                            )
                        )
                    WHERE conversation_id = %s
                """,
                (turn.ts, [detected_language] if detected_language else [], conv_id),
            )
        return turn_id

    def last_n(self, tenant_id: str, sender_id: str, n: int = 6) -> list[Turn]:
        with self._pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT t.role, t.text, t.received_at
                    FROM turns t
                    JOIN conversations c ON c.conversation_id = t.conversation_id
                    WHERE c.tenant_id = %s AND c.sender_id = %s
                    ORDER BY t.received_at DESC
                    LIMIT %s
                """,
                (tenant_id, sender_id, n),
            )
            rows = cur.fetchall()
        rows.reverse()
        return [Turn(role=r[0], text=r[1], ts=r[2]) for r in rows]


# ---------------------------------------------------------------------------
# AuditStore
# ---------------------------------------------------------------------------


@dataclass
class AuditPayload:
    """Everything we need to capture about one orchestrator turn for offline evaluation."""

    tenant_id: str
    conversation_id: str
    turn_id: str
    user_text: str
    retrieved_chunk_ids: list[int]
    retrieved_chunk_blob: str
    system_prompt: str
    user_prompt: str
    response_text: str
    result: OrchestrationResult
    guard_mutations: list[str]
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class AuditStore:
    def __init__(self, pool) -> None:
        self._pool = pool

    def write(self, payload: AuditPayload) -> str:
        with self._pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO audit_records (
                    audit_id, tenant_id, conversation_id, turn_id, user_text,
                    detected_language, is_mixed_language, retrieved_chunk_ids,
                    retrieved_chunk_blob, system_prompt, user_prompt, response_text,
                    model, provider, prompt_tokens, completion_tokens,
                    latency_breakdown_ms, escalated, escalation_reason, guard_mutations
                ) VALUES (
                    gen_random_uuid(), %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s::jsonb, %s, %s, %s
                )
                RETURNING audit_id
                """,
                (
                    payload.tenant_id,
                    payload.conversation_id,
                    payload.turn_id,
                    payload.user_text,
                    payload.result.detected_language,
                    payload.result.is_mixed_language,
                    payload.retrieved_chunk_ids,
                    payload.retrieved_chunk_blob[:4000],
                    payload.system_prompt,
                    payload.user_prompt,
                    payload.response_text,
                    payload.result.model,
                    payload.result.provider,
                    payload.prompt_tokens,
                    payload.completion_tokens,
                    _json_safe(payload.result.latency_breakdown_ms),
                    payload.result.escalated,
                    payload.result.escalation_reason,
                    payload.guard_mutations or [],
                ),
            )
            return str(cur.fetchone()[0])


# ---------------------------------------------------------------------------
# IdempotencyStore
# ---------------------------------------------------------------------------


class IdempotencyStore:
    """Guards against duplicate WhatsApp deliveries.

    Meta's Cloud API can deliver the same webhook event more than once.  The
    `processed_messages` table records the (tenant_id, channel, channel_msg_id)
    triple and lets us short-circuit duplicates without any race conditions
    using INSERT ... ON CONFLICT.
    """

    def __init__(self, pool) -> None:
        self._pool = pool

    def claim(self, tenant_id: str, channel: str, channel_msg_id: str) -> bool:
        """Try to claim a message id. Returns True on first sight, False on duplicate."""
        if not channel_msg_id:
            return True
        try:
            with self._pool.connection() as conn, conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO processed_messages (tenant_id, channel, channel_msg_id, processed_at)
                    VALUES (%s, %s, %s, NOW())
                    ON CONFLICT DO NOTHING
                    RETURNING channel_msg_id
                    """,
                    (tenant_id, channel, channel_msg_id),
                )
                row = cur.fetchone()
            return row is not None
        except Exception:
            log.exception("idempotency claim failed; allowing message through")
            return True
