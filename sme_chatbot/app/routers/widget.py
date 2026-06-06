"""Web widget endpoints.

POST /widget/v1/session     Open a session, return greeting + session_token
POST /widget/v1/message     Send a customer message, receive bot reply
POST /widget/v1/feedback    Thumbs up / down on a turn
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from ..deps import get_orchestrator, get_tenant_service, get_widget_adapter

log = logging.getLogger(__name__)
router = APIRouter(prefix="/widget/v1", tags=["widget"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class OpenSessionRequest(BaseModel):
    widget_key: str = Field(min_length=8)


class OpenSessionResponse(BaseModel):
    session_token: str
    expires_at: str
    greeting: str


class WidgetMessageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class WidgetMessageResponse(BaseModel):
    reply: str
    escalated: bool
    turn_id: str
    detected_language: str


class FeedbackRequest(BaseModel):
    turn_id: str
    rating: str   # "up" | "down"
    note: str | None = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/session", response_model=OpenSessionResponse)
def open_session(
    body: OpenSessionRequest,
    origin: str | None = Header(default=None),
    adapter=Depends(get_widget_adapter),
    tenants=Depends(get_tenant_service),
):
    try:
        session = adapter.open_session(body.widget_key, origin or "")
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    try:
        cfg = tenants.get(session.tenant_id)
        greeting = cfg.greeting or "Hi! How can I help?"
    except Exception:  # noqa: BLE001
        greeting = "Hi! How can I help?"

    return OpenSessionResponse(
        session_token=session.session_id,
        expires_at=session.expires_at.isoformat(),
        greeting=greeting,
    )


@router.post("/message", response_model=WidgetMessageResponse)
def post_message(
    body: WidgetMessageRequest,
    authorization: str = Header(...),
    adapter=Depends(get_widget_adapter),
    orchestrator=Depends(get_orchestrator),
):
    token = authorization.removeprefix("Bearer ").strip()
    try:
        session = adapter.resolve_session(token)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    msg = adapter.to_canonical(session, body.text)
    result = orchestrator.handle(msg)
    return WidgetMessageResponse(
        reply=result.reply_text,
        escalated=result.escalated,
        turn_id=result.turn_id,
        detected_language=result.detected_language,
    )


@router.post("/feedback")
def post_feedback(
    body: FeedbackRequest,
    authorization: str = Header(...),
):
    # TODO: persist into feedback table; for now just acknowledge.
    log.info("feedback received: turn=%s rating=%s", body.turn_id, body.rating)
    return {"ok": True}
