"""WhatsApp webhook endpoints.

GET  /webhooks/whatsapp     Meta verification handshake
POST /webhooks/whatsapp     Inbound message delivery (enqueues for the worker)

The POST handler does the minimum amount of work possible — verify the
HMAC, claim idempotency, enqueue the payload, ACK 200 OK. Heavy
orchestration runs in the RQ worker (`app/workers/worker.py`) so we
always answer Meta within their 5-second SLA.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from ..config import get_settings
from ..deps import get_orchestrator, get_whatsapp_adapter

log = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.get("/whatsapp")
async def whatsapp_verify(
    request: Request,
    adapter=Depends(get_whatsapp_adapter),
) -> Response:
    params = request.query_params
    challenge = adapter.verify_challenge(
        mode=params.get("hub.mode", ""),
        token=params.get("hub.verify_token", ""),
        challenge=params.get("hub.challenge", ""),
    )
    if challenge is None:
        raise HTTPException(status_code=403, detail="bad verify token")
    return Response(content=challenge, media_type="text/plain")


@router.post("/whatsapp")
async def whatsapp_inbound(
    request: Request,
    adapter=Depends(get_whatsapp_adapter),
    orchestrator=Depends(get_orchestrator),
) -> Response:
    """Process inbound WhatsApp messages.

    We ALWAYS return 200 OK to Meta, even if signature verification fails (we
    just log it). The actual work is enqueued to RQ where retries and dead-letter
    handling apply. When the queue is unavailable we fall back to inline
    processing so a misconfigured worker dyno doesn't drop customer messages.
    """
    raw_body = await request.body()
    sig = request.headers.get("x-hub-signature-256")
    settings = get_settings()
    if settings.whatsapp_app_secret and not adapter.verify_signature(raw_body, sig):
        log.warning("invalid whatsapp signature; ignoring payload")
        return Response(status_code=200)

    try:
        payload = await request.json()
    except Exception:
        log.warning("whatsapp payload was not valid JSON; ignoring")
        return Response(status_code=200)

    # Try to enqueue. If Redis is unreachable, fall back to inline processing
    # so we never drop a customer message during a transient outage.
    enqueued = False
    try:
        from ..workers.jobs import process_whatsapp_payload
        from ..workers.queues import whatsapp_queue
        whatsapp_queue().enqueue(
            process_whatsapp_payload, payload,
            job_timeout=120, result_ttl=3600, failure_ttl=86400,
        )
        enqueued = True
    except Exception as exc:                              # pragma: no cover
        log.warning("could not enqueue whatsapp payload (%s); processing inline", exc)

    if not enqueued:
        try:
            for msg in adapter.parse_inbound(payload):
                try:
                    result = orchestrator.handle(msg)
                    adapter.send_reply(msg, result.reply_text)
                except Exception:
                    log.exception("inline orchestration failed for tenant=%s", msg.tenant_id)
        except Exception:
            log.exception("inline whatsapp processing failed completely")

    return Response(status_code=200)
