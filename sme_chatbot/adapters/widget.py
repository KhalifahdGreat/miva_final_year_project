"""Embeddable web widget adapter.

The widget loads a 1-line `<script>` from the SME's site, opens a session
against this backend, and exchanges messages via HTTP.  Session tokens
are short-lived JWTs scoped to a (tenant_id, session_id) pair.

Unlike the WhatsApp adapter, the widget adapter does not call out to any
third party — the FastAPI router handles request/response directly.  This
class exists for symmetry with `WhatsAppCloudAdapter` and to host the
session creation / origin-pinning logic.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from core.types import CanonicalMessage


@dataclass
class WidgetSession:
    session_id: str
    tenant_id: str
    issued_at: datetime
    expires_at: datetime
    origin: str


class WidgetAdapter:
    name: str = "widget"

    def __init__(self, *, tenant_resolver, session_ttl_hours: int = 24) -> None:
        # tenant_resolver: maps a widget_key → (tenant_id, allowed_origins[])
        self._tenant_resolver = tenant_resolver
        self._ttl = timedelta(hours=session_ttl_hours)
        # In-memory session store. Swap for Redis in production.
        self._sessions: dict[str, WidgetSession] = {}

    # -------------------------------------------------------------------
    # Session lifecycle
    # -------------------------------------------------------------------

    def open_session(self, widget_key: str, origin: str) -> WidgetSession:
        resolved = self._tenant_resolver(widget_key)
        if not resolved:
            raise PermissionError("invalid widget key")
        tenant_id, allowed_origins = resolved
        if allowed_origins and origin not in allowed_origins:
            raise PermissionError(f"origin not allowed: {origin}")

        now = datetime.now(timezone.utc)
        session = WidgetSession(
            session_id=secrets.token_urlsafe(24),
            tenant_id=tenant_id,
            issued_at=now,
            expires_at=now + self._ttl,
            origin=origin,
        )
        self._sessions[session.session_id] = session
        return session

    def resolve_session(self, session_id: str) -> WidgetSession:
        sess = self._sessions.get(session_id)
        if sess is None:
            raise PermissionError("unknown session")
        if sess.expires_at < datetime.now(timezone.utc):
            self._sessions.pop(session_id, None)
            raise PermissionError("session expired")
        return sess

    # -------------------------------------------------------------------
    # Inbound
    # -------------------------------------------------------------------

    def to_canonical(self, session: WidgetSession, text: str) -> CanonicalMessage:
        return CanonicalMessage(
            tenant_id=session.tenant_id,
            channel="widget",
            sender_id=session.session_id,
            text=text,
            received_at=datetime.now(timezone.utc),
            channel_msg_id=secrets.token_urlsafe(12),
        )

    # -------------------------------------------------------------------
    # Outbound (no-op — FastAPI returns the reply in the HTTP response)
    # -------------------------------------------------------------------

    def send_reply(self, msg: CanonicalMessage, reply_text: str) -> dict[str, Any]:
        return {"ok": True, "reply": reply_text}
