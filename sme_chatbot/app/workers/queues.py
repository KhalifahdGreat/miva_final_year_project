"""RQ queue helpers."""

from __future__ import annotations

from functools import lru_cache

from redis import Redis
from rq import Queue

from ..config import get_settings


@lru_cache(maxsize=1)
def redis_conn() -> Redis:
    return Redis.from_url(get_settings().redis_url)


@lru_cache(maxsize=1)
def whatsapp_queue() -> Queue:
    return Queue("whatsapp", connection=redis_conn(), default_timeout=120)


@lru_cache(maxsize=1)
def ingestion_queue() -> Queue:
    return Queue("ingestion", connection=redis_conn(), default_timeout=900)
