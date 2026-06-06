"""Job functions executed by the RQ workers.

Each function must be top-level and importable so RQ can resolve it from
the worker process. Heavy imports happen lazily inside the functions to
keep the enqueue path fast.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


def process_whatsapp_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Parse one WhatsApp webhook payload and run the orchestrator per message.

    Returns a small dict the RQ result store can keep for one hour (useful for
    debugging from the dashboard's worker page).
    """
    from ..deps import get_orchestrator, get_whatsapp_adapter
    adapter = get_whatsapp_adapter()
    orch    = get_orchestrator()

    handled = 0
    failed  = 0
    skipped_duplicates = 0

    try:
        messages = adapter.parse_inbound(payload)
    except Exception:
        log.exception("could not parse whatsapp payload")
        return {"handled": 0, "failed": 1, "reason": "parse_failed"}

    # Idempotency at the worker level (after the webhook has already ACKed Meta).
    try:
        from core.conversation_store import IdempotencyStore
        from ..db import pool
        idem = IdempotencyStore(pool())
    except Exception:
        idem = None

    for msg in messages:
        if idem is not None and not idem.claim(msg.tenant_id, msg.channel, msg.channel_msg_id):
            skipped_duplicates += 1
            continue
        try:
            result = orch.handle(msg)
        except Exception:
            log.exception("orchestrator failed for tenant=%s", msg.tenant_id)
            failed += 1
            continue
        try:
            adapter.send_reply(msg, result.reply_text)
            handled += 1
        except Exception:
            log.exception("send_reply failed for tenant=%s", msg.tenant_id)
            failed += 1

    return {
        "handled": handled,
        "failed":  failed,
        "skipped_duplicates": skipped_duplicates,
    }


def ingest_uploaded_document(
    *,
    document_id: str,
    tenant_id: str,
    document_type: str,
    source_path: str,
) -> dict[str, Any]:
    """Run heavy document ingestion in a background process."""
    from core.ingestion import ingest
    from ..deps import get_retrieval_service
    from ..routers.documents import _mark_document  # reuse the row-state helper

    path = Path(source_path)
    try:
        _mark_document(document_id, status="processing")
        result = ingest(
            retrieval_service=get_retrieval_service(),
            tenant_id=tenant_id,
            document_id=document_id,
            document_type=document_type,
            source_path=path,
        )
        if result.errors:
            _mark_document(document_id, status="failed",
                            chunk_count=result.chunks_created,
                            error_message="; ".join(result.errors)[:500])
        else:
            _mark_document(document_id, status="ready",
                            chunk_count=result.chunks_created)
        return {
            "document_id": document_id,
            "chunks_created": result.chunks_created,
            "duration_s": round(result.duration_s, 2),
            "errors": result.errors,
        }
    finally:
        try:
            path.unlink()
        except Exception:
            pass
