"""Object storage for uploaded documents (Cloudflare R2, S3-compatible).

R2 is reached through the standard boto3 S3 client by pointing ``endpoint_url``
at the R2 gateway. Everything here is **optional**: if the R2 settings are not
configured the helpers degrade gracefully (``is_enabled()`` is False and the
upload path simply keeps using the container's temp disk), so the service runs
fine before credentials are supplied.

Object key layout:
    tenants/<tenant_id>/documents/<document_id>/<filename>
"""

from __future__ import annotations

import logging
from functools import lru_cache

from .config import get_settings

log = logging.getLogger(__name__)


def is_enabled() -> bool:
    s = get_settings()
    return bool(s.r2_endpoint_url and s.r2_access_key_id and s.r2_secret_access_key and s.r2_bucket)


@lru_cache(maxsize=1)
def _client():
    import boto3
    from botocore.config import Config

    s = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=s.r2_endpoint_url,
        aws_access_key_id=s.r2_access_key_id,
        aws_secret_access_key=s.r2_secret_access_key,
        region_name="auto",
        config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
    )


def object_key(tenant_id: str, document_id: str, filename: str) -> str:
    safe = (filename or "upload").replace("/", "_").strip()
    return f"tenants/{tenant_id}/documents/{document_id}/{safe}"


def upload_bytes(key: str, data: bytes, content_type: str | None = None) -> bool:
    """Store bytes at ``key``. Returns True on success, False otherwise."""
    if not is_enabled():
        return False
    try:
        s = get_settings()
        _client().put_object(
            Bucket=s.r2_bucket,
            Key=key,
            Body=data,
            ContentType=content_type or "application/octet-stream",
        )
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("R2 upload failed for key=%s: %s", key, exc)
        return False


def presigned_get_url(key: str, expires_s: int = 900) -> str | None:
    """Return a time-limited download URL for ``key`` (or None)."""
    if not is_enabled():
        return None
    try:
        s = get_settings()
        return _client().generate_presigned_url(
            "get_object",
            Params={"Bucket": s.r2_bucket, "Key": key},
            ExpiresIn=expires_s,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("R2 presign failed for key=%s: %s", key, exc)
        return None


def delete(key: str) -> bool:
    if not is_enabled() or not key:
        return False
    try:
        s = get_settings()
        _client().delete_object(Bucket=s.r2_bucket, Key=key)
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("R2 delete failed for key=%s: %s", key, exc)
        return False
