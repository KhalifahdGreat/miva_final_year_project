"""Knowledge upload endpoints.

POST   /v1/tenants/{tenant_id}/documents     Upload one document
GET    /v1/tenants/{tenant_id}/documents     List documents
DELETE /v1/tenants/{tenant_id}/documents/{document_id}
"""

from __future__ import annotations

import logging
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile

from core.ingestion import ingest

from .. import storage
from ..db import pool as get_pool
from ..deps import get_retrieval_service

log = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/tenants", tags=["documents"])

ALLOWED_TYPES = {"catalogue", "faq", "policy", "manual_faq", "pricing"}


def _insert_document(tenant_id: str, document_id: str, title: str, document_type: str,
                      mime_type: str, byte_size: int, object_key: str | None = None) -> None:
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO documents (document_id, tenant_id, title, document_type,
                                    mime_type, byte_size, status, object_key)
            VALUES (%s, %s, %s, %s, %s, %s, 'queued', %s)
            """,
            (document_id, tenant_id, title, document_type, mime_type, byte_size, object_key),
        )


def _mark_document(document_id: str, *, status: str, chunk_count: int = 0,
                    error_message: str | None = None) -> None:
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE documents
                SET status = %s, chunk_count = %s, error_message = %s, updated_at = NOW()
                WHERE document_id = %s
            """,
            (status, chunk_count, error_message, document_id),
        )


def _ingest_in_background(document_id: str, tenant_id: str, document_type: str,
                          source_path: Path, retrieval) -> None:
    """Wrap `core.ingest` with DB status updates so the dashboard can poll."""
    try:
        _mark_document(document_id, status="processing")
        result = ingest(
            retrieval_service=retrieval,
            tenant_id=tenant_id,
            document_id=document_id,
            document_type=document_type,
            source_path=source_path,
        )
        if result.errors:
            _mark_document(document_id, status="failed",
                            chunk_count=result.chunks_created,
                            error_message="; ".join(result.errors)[:500])
        else:
            _mark_document(document_id, status="ready",
                            chunk_count=result.chunks_created)
    except Exception as exc:                              # pragma: no cover
        log.exception("ingestion failed for document=%s", document_id)
        _mark_document(document_id, status="failed", error_message=str(exc)[:500])
    finally:
        try:
            source_path.unlink()
        except Exception:
            pass


@router.post("/{tenant_id}/documents")
async def upload_document(
    tenant_id: str,
    background_tasks: BackgroundTasks,
    document_type: str = Form(...),
    file: UploadFile = File(...),
    retrieval=Depends(get_retrieval_service),
):
    if document_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"document_type must be one of {ALLOWED_TYPES}")

    document_id = str(uuid.uuid4())
    suffix = Path(file.filename or "upload").suffix
    raw = await file.read()

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(raw)
        tmp_path = Path(tmp.name)

    # Persist the original file to object storage (R2) when configured, so it
    # can be re-downloaded / re-ingested later. No-op if R2 isn't set up.
    obj_key: str | None = None
    if storage.is_enabled():
        candidate = storage.object_key(tenant_id, document_id, file.filename or "upload")
        if storage.upload_bytes(candidate, raw, file.content_type):
            obj_key = candidate

    try:
        _insert_document(
            tenant_id=tenant_id,
            document_id=document_id,
            title=file.filename or "upload",
            document_type=document_type,
            mime_type=file.content_type or "application/octet-stream",
            byte_size=len(raw),
            object_key=obj_key,
        )
    except Exception as exc:                              # pragma: no cover
        log.exception("could not record document row: %s", exc)
        raise HTTPException(status_code=500, detail=f"db insert failed: {exc}") from exc

    background_tasks.add_task(
        _ingest_in_background, document_id, tenant_id, document_type, tmp_path, retrieval,
    )

    return {
        "document_id": document_id,
        "status": "queued",
        "title": file.filename,
        "document_type": document_type,
        "byte_size": len(raw),
    }


@router.get("/{tenant_id}/documents")
def list_documents(tenant_id: str):
    sql = """
        SELECT document_id, title, document_type, mime_type, byte_size,
                chunk_count, status, error_message, created_at, updated_at,
                object_key
            FROM documents
            WHERE tenant_id = %s AND archived_at IS NULL
            ORDER BY created_at DESC
            LIMIT 200
    """
    try:
        with get_pool().connection() as conn, conn.cursor() as cur:
            cur.execute(sql, (tenant_id,))
            rows = cur.fetchall()
    except Exception as exc:                              # pragma: no cover
        log.exception("list_documents failed: %s", exc)
        return {"items": [], "tenant_id": tenant_id, "error": str(exc)}

    items = [
        {
            "document_id": str(r[0]),
            "title": r[1],
            "document_type": r[2],
            "mime_type": r[3],
            "byte_size": r[4],
            "chunk_count": r[5],
            "status": r[6],
            "error_message": r[7],
            "created_at": r[8].isoformat() if r[8] else None,
            "updated_at": r[9].isoformat() if r[9] else None,
            "has_file": bool(r[10]),
        }
        for r in rows
    ]
    return {"items": items, "tenant_id": tenant_id}


@router.get("/{tenant_id}/documents/{document_id}/download")
def download_document(tenant_id: str, document_id: str):
    """Return a short-lived presigned URL for the original uploaded file."""
    try:
        with get_pool().connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT object_key FROM documents WHERE tenant_id = %s AND document_id = %s",
                (tenant_id, document_id),
            )
            row = cur.fetchone()
    except Exception as exc:                              # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not row:
        raise HTTPException(status_code=404, detail="document not found")
    if not row[0]:
        raise HTTPException(status_code=404, detail="no stored file for this document")
    url = storage.presigned_get_url(row[0])
    if not url:
        raise HTTPException(status_code=503, detail="object storage not configured")
    return {"url": url}


@router.delete("/{tenant_id}/documents/{document_id}")
def delete_document(tenant_id: str, document_id: str):
    """Soft-delete a document by archiving the row.

    The vector chunks remain in Milvus for one Sprint cycle so an accidental
    delete can be reverted; a separate housekeeping job (Sprint 3) hard-purges
    them when archived_at > NOW() - 7 days.
    """
    sql = """
        UPDATE documents
            SET archived_at = NOW(), updated_at = NOW()
            WHERE tenant_id = %s AND document_id = %s AND archived_at IS NULL
            RETURNING document_id
    """
    try:
        with get_pool().connection() as conn, conn.cursor() as cur:
            cur.execute(sql, (tenant_id, document_id))
            row = cur.fetchone()
    except Exception as exc:                              # pragma: no cover
        log.exception("delete_document failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if row is None:
        raise HTTPException(status_code=404, detail="document not found")
    return {"ok": True, "document_id": document_id}
