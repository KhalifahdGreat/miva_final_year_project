"""WhatsApp Business Cloud API adapter (Meta).

Implements the three things every channel adapter must do:

    parse_inbound(payload)  → CanonicalMessage(s)
    send_reply(msg, text)   → POST to Meta Graph API
    verify_webhook(...)     → checks the HMAC signature

Reference:
    https://developers.facebook.com/docs/whatsapp/cloud-api
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from core.types import CanonicalMessage

log = logging.getLogger(__name__)


class WhatsAppCloudAdapter:
    name: str = "whatsapp"

    def __init__(
        self,
        *,
        app_secret: str,
        verify_token: str,
        graph_api_base: str = "https://graph.facebook.com/v20.0",
        # tenant_resolver: maps a Meta phone_number_id → tenant_id
        tenant_resolver,
        # creds_provider: returns (phone_number_id, access_token) for a tenant
        creds_provider,
        http_timeout_s: float = 8.0,
    ) -> None:
        self._app_secret = app_secret
        self._verify_token = verify_token
        self._graph_api_base = graph_api_base.rstrip("/")
        self._tenant_resolver = tenant_resolver
        self._creds_provider = creds_provider
        self._timeout = http_timeout_s

    # -------------------------------------------------------------------
    # Webhook verification
    # -------------------------------------------------------------------

    def verify_challenge(self, mode: str, token: str, challenge: str) -> str | None:
        """Handle Meta's GET subscribe challenge."""
        if mode == "subscribe" and token == self._verify_token:
            return challenge
        return None

    def verify_signature(self, raw_body: bytes, header_sig: str | None) -> bool:
        if not header_sig or not self._app_secret:
            return False
        # Meta sends "sha256=<hex>"
        if header_sig.startswith("sha256="):
            header_sig = header_sig[len("sha256="):]
        expected = hmac.new(
            self._app_secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, header_sig)

    # -------------------------------------------------------------------
    # Inbound
    # -------------------------------------------------------------------

    def parse_inbound(self, raw: dict[str, Any]) -> list[CanonicalMessage]:
        """Turn one Meta webhook POST into 0..N CanonicalMessages.

        Meta batches multiple messages in a single POST, hence the list.
        Non-text message types (image, audio, location, etc.) are logged
        and skipped in v1 — they become Future Work entries.
        """
        out: list[CanonicalMessage] = []
        for entry in raw.get("entry", []) or []:
            for change in entry.get("changes", []) or []:
                value = change.get("value") or {}
                metadata = value.get("metadata") or {}
                phone_number_id = metadata.get("phone_number_id")
                if not phone_number_id:
                    continue
                tenant_id = self._tenant_resolver(phone_number_id)
                if not tenant_id:
                    log.warning("no tenant for phone_number_id=%s", phone_number_id)
                    continue
                for m in value.get("messages") or []:
                    mtype = m.get("type")
                    if mtype != "text":
                        log.info("ignoring non-text message type=%s", mtype)
                        continue
                    text_body = (m.get("text") or {}).get("body") or ""
                    ts = m.get("timestamp")
                    try:
                        received = datetime.fromtimestamp(int(ts), tz=timezone.utc)
                    except (TypeError, ValueError):
                        received = datetime.now(timezone.utc)
                    out.append(CanonicalMessage(
                        tenant_id=tenant_id,
                        channel="whatsapp",
                        sender_id=m.get("from", ""),
                        text=text_body,
                        received_at=received,
                        channel_msg_id=m.get("id", ""),
                    ))
        return out

    # -------------------------------------------------------------------
    # Outbound
    # -------------------------------------------------------------------

    def send_reply(self, msg: CanonicalMessage, reply_text: str) -> dict[str, Any]:
        phone_number_id, access_token = self._creds_provider(msg.tenant_id)
        url = f"{self._graph_api_base}/{phone_number_id}/messages"
        body = {
            "messaging_product": "whatsapp",
            "to": msg.sender_id,
            "type": "text",
            "text": {"body": reply_text[:4096]},
        }
        headers = {"Authorization": f"Bearer {access_token}"}
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(url, json=body, headers=headers)
            resp.raise_for_status()
            return resp.json()

    def send_typing_indicator(self, msg: CanonicalMessage) -> None:
        # Meta's Cloud API doesn't expose typing indicators in the same way
        # the on-device app does. This is a no-op in v1.
        return None
