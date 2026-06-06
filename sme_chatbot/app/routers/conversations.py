"""Conversation review endpoints for the admin dashboard.

GET   /v1/tenants/{tenant_id}/conversations
GET   /v1/tenants/{tenant_id}/conversations/{conversation_id}/turns
POST  /v1/tenants/{tenant_id}/conversations/{conversation_id}/feedback
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..db import pool as get_pool

log = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/tenants", tags=["conversations"])


class FeedbackBody(BaseModel):
    turn_id: str
    rating: str             # "up" | "down"
    note: str | None = None
    corrected_answer: str | None = None


@router.get("/{tenant_id}/conversations")
def list_conversations(
    tenant_id: str,
    language: str | None = Query(default=None, description="Filter by detected language"),
    escalated: bool | None = Query(default=None, description="Show only escalated conversations"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """Return the most recently active conversations for a tenant."""
    where = ["c.tenant_id = %s"]
    params: list[Any] = [tenant_id]

    if language:
        where.append("%s = ANY(c.languages_seen)")
        params.append(language)
    if escalated is True:
        where.append("EXISTS (SELECT 1 FROM turns t WHERE t.conversation_id = c.conversation_id AND t.escalated = TRUE)")

    sql = f"""
        SELECT c.conversation_id, c.channel, c.sender_id,
                c.started_at, c.last_turn_at, c.turn_count, c.languages_seen,
                EXISTS (SELECT 1 FROM turns t WHERE t.conversation_id = c.conversation_id AND t.escalated = TRUE) AS has_escalation
            FROM conversations c
            WHERE {" AND ".join(where)}
            ORDER BY c.last_turn_at DESC
            LIMIT %s OFFSET %s
    """
    params.extend([limit, offset])

    try:
        with get_pool().connection() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    except Exception as exc:                              # pragma: no cover
        log.exception("list_conversations failed: %s", exc)
        return {"items": [], "tenant_id": tenant_id, "error": str(exc)}

    items = [
        {
            "conversation_id": str(r[0]),
            "channel": r[1],
            "sender_id": r[2],
            "started_at": r[3].isoformat() if r[3] else None,
            "last_turn_at": r[4].isoformat() if r[4] else None,
            "turn_count": r[5],
            "languages_seen": r[6] or [],
            "has_escalation": bool(r[7]),
        }
        for r in rows
    ]
    return {"items": items, "tenant_id": tenant_id, "limit": limit, "offset": offset}


@router.get("/{tenant_id}/conversations/{conversation_id}/turns")
def get_turns(tenant_id: str, conversation_id: str):
    sql = """
        SELECT t.turn_id, t.role, t.text, t.received_at,
                t.detected_language, t.is_mixed_language,
                t.escalated, t.escalation_reason
            FROM turns t
            JOIN conversations c ON c.conversation_id = t.conversation_id
            WHERE c.tenant_id = %s AND c.conversation_id = %s
            ORDER BY t.received_at ASC
    """
    try:
        with get_pool().connection() as conn, conn.cursor() as cur:
            cur.execute(sql, (tenant_id, conversation_id))
            rows = cur.fetchall()
    except Exception as exc:                              # pragma: no cover
        log.exception("get_turns failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    items = [
        {
            "turn_id": str(r[0]),
            "role": r[1],
            "text": r[2],
            "received_at": r[3].isoformat() if r[3] else None,
            "detected_language": r[4],
            "is_mixed_language": r[5],
            "escalated": r[6],
            "escalation_reason": r[7],
        }
        for r in rows
    ]
    return {"items": items, "conversation_id": conversation_id}


@router.post("/{tenant_id}/conversations/{conversation_id}/feedback")
def submit_feedback(tenant_id: str, conversation_id: str, body: FeedbackBody):
    if body.rating not in ("up", "down"):
        raise HTTPException(status_code=400, detail="rating must be 'up' or 'down'")
    sql = """
        INSERT INTO feedback (feedback_id, tenant_id, turn_id, rating, note, corrected_answer)
            VALUES (gen_random_uuid(), %s, %s, %s, %s, %s)
            RETURNING feedback_id
    """
    try:
        with get_pool().connection() as conn, conn.cursor() as cur:
            cur.execute(sql, (tenant_id, body.turn_id, body.rating, body.note, body.corrected_answer))
            row = cur.fetchone()
    except Exception as exc:                              # pragma: no cover
        log.exception("submit_feedback failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"ok": True, "feedback_id": str(row[0])}
