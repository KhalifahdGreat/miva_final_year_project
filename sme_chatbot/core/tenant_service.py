"""Per-tenant configuration persistence.

Backed by Postgres (table `tenant_configs`, JSONB column `data`) with an
in-memory LRU + Redis cache for hot reads.  In the dev / smoke-test path
we expose `InMemoryTenantService` so the engine can be exercised without
spinning up Postgres.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Protocol

from .types import EscalationRule, TenantConfig


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------


class TenantService(Protocol):
    def get(self, tenant_id: str) -> TenantConfig: ...
    def save(self, cfg: TenantConfig) -> int: ...
    def list_all(self) -> list[TenantConfig]: ...


# ---------------------------------------------------------------------------
# In-memory implementation (dev / smoke-test)
# ---------------------------------------------------------------------------


class InMemoryTenantService:
    """Tenant configs held in-process.  No persistence between runs."""

    def __init__(self) -> None:
        self._data: dict[str, TenantConfig] = {}

    def get(self, tenant_id: str) -> TenantConfig:
        cfg = self._data.get(tenant_id)
        if cfg is None:
            raise LookupError(f"no tenant config for {tenant_id}")
        return cfg

    def save(self, cfg: TenantConfig) -> int:
        existing = self._data.get(cfg.tenant_id)
        cfg.version = (existing.version + 1) if existing else 1
        self._data[cfg.tenant_id] = cfg
        return cfg.version

    def list_all(self) -> list[TenantConfig]:
        return list(self._data.values())


# ---------------------------------------------------------------------------
# Postgres-backed implementation
# ---------------------------------------------------------------------------


def _serialise(cfg: TenantConfig) -> str:
    d = asdict(cfg)
    d["escalation_rules"] = [asdict(r) for r in cfg.escalation_rules]
    return json.dumps(d, default=str)


def _deserialise(blob: str | dict) -> TenantConfig:
    # psycopg 3 transparently decodes JSONB columns into Python dicts, but
    # older drivers (and any caller that hands us a JSON string) pass us raw
    # text — handle both gracefully.
    d = blob if isinstance(blob, dict) else json.loads(blob)
    d["escalation_rules"] = [EscalationRule(**r) for r in d.get("escalation_rules", [])]
    return TenantConfig(**d)


class PostgresTenantService:
    """Postgres + JSONB storage, with versioned rows per tenant."""

    def __init__(self, db_pool) -> None:
        # `db_pool` is expected to be a psycopg ConnectionPool. We accept
        # `Any` here to avoid importing psycopg in core/ (keeps core pure).
        self._pool = db_pool

    def get(self, tenant_id: str) -> TenantConfig:
        with self._pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT data FROM tenant_configs WHERE tenant_id = %s "
                "ORDER BY version DESC LIMIT 1",
                (tenant_id,),
            )
            row = cur.fetchone()
        if not row:
            raise LookupError(f"no tenant config for {tenant_id}")
        return _deserialise(row[0])

    def save(self, cfg: TenantConfig) -> int:
        with self._pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT COALESCE(MAX(version), 0) FROM tenant_configs WHERE tenant_id = %s",
                (cfg.tenant_id,),
            )
            current = cur.fetchone()[0]
            new_version = int(current) + 1
            cfg.version = new_version
            cur.execute(
                "INSERT INTO tenant_configs (tenant_id, version, data) "
                "VALUES (%s, %s, %s::jsonb)",
                (cfg.tenant_id, new_version, _serialise(cfg)),
            )
        return new_version

    def list_all(self) -> list[TenantConfig]:
        with self._pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT ON (tenant_id) data FROM tenant_configs "
                "ORDER BY tenant_id, version DESC"
            )
            rows = cur.fetchall()
        return [_deserialise(r[0]) for r in rows]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def default_config(tenant_id: str, business_name: str) -> TenantConfig:
    """Sensible starter config for a newly-onboarded SME."""
    return TenantConfig(
        tenant_id=tenant_id,
        business_name=business_name,
        tagline="",
        tone="casual",
        languages=["en", "pid", "yo", "ha", "ig"],
        timezone="Africa/Lagos",
        operating_hours={
            "mon_fri": "09:00-19:00",
            "sat": "10:00-17:00",
            "sun": "closed",
        },
        greeting=f"Hi! Welcome to {business_name}. How can I help you today?",
        out_of_hours=(
            "Thanks for reaching out — we're closed for now. "
            "We'll reply when we're back."
        ),
        fallback="I'm not sure about that one — let me get a human colleague to help.",
        escalation_rules=[],
        brand_voice_examples=[],
        retrieval_weights={
            "manual_faq": 4,
            "faq": 3,
            "pricing": 2,
            "catalogue": 2,
            "policy": 1,
        },
        version=1,
    )
