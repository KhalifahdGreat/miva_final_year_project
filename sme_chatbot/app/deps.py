"""FastAPI dependencies.

These factories build the orchestrator (and its dependencies) once per
application lifetime via lru_cache, then inject them into route handlers.

Reuses `ofofo_engine.retrieval.RetrievalService` and
`ofofo_engine.llm.LLMClient` directly — the heart of the "library import"
pattern.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from .config import get_settings


# ---------------------------------------------------------------------------
# Shared engine reuse
# ---------------------------------------------------------------------------


def _build_engine_config():
    """Build an `ofofo_engine.config.EngineConfig` from our app settings.

    We import inside the function so a missing parent package fails clearly
    only when a route that actually needs it is hit.
    """
    from ofofo_engine.config import EngineConfig

    s = get_settings()
    return EngineConfig(
        groq_api_key=s.groq_api_key,
        llm_model=s.llm_model,
        vector_db_path=Path(s.ofofo_vector_db_path).resolve(),
        embedding_model=s.ofofo_embedding_model,
    )


@lru_cache(maxsize=1)
def get_retrieval_service():
    from ofofo_engine.retrieval import RetrievalService

    return RetrievalService(_build_engine_config())


@lru_cache(maxsize=1)
def get_llm_client():
    from ofofo_engine.llm import LLMClient

    return LLMClient(_build_engine_config())


# ---------------------------------------------------------------------------
# Orchestrator (singleton)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_tenant_service():
    """Return the active TenantService.

    Postgres-backed in production; falls back to in-memory for dev / tests
    if Postgres is unreachable at boot.
    """
    from core.tenant_service import InMemoryTenantService, PostgresTenantService

    try:
        from .db import init_pool
        pool = init_pool()
        return PostgresTenantService(pool)
    except Exception:  # noqa: BLE001
        return InMemoryTenantService()


@lru_cache(maxsize=1)
def get_history_store():
    """Postgres-backed history when available, otherwise in-memory.

    The in-memory fallback exists so the smoke test and local unit tests run
    without Postgres on the box. Production always uses Postgres.
    """
    from core.orchestrator import InMemoryHistoryStore
    try:
        from core.conversation_store import PostgresHistoryStore
        from .db import init_pool
        return PostgresHistoryStore(init_pool())
    except Exception:                                     # pragma: no cover
        return InMemoryHistoryStore()


@lru_cache(maxsize=1)
def get_audit_store():
    """Postgres-backed audit store, or None when DB is unavailable."""
    try:
        from core.conversation_store import AuditStore
        from .db import init_pool
        return AuditStore(init_pool())
    except Exception:                                     # pragma: no cover
        return None


@lru_cache(maxsize=1)
def get_orchestrator():
    from core.orchestrator import SMEOrchestrator

    return SMEOrchestrator(
        retrieval=get_retrieval_service(),
        llm=get_llm_client(),
        tenant_service=get_tenant_service(),
        history=get_history_store(),
        audit_store=get_audit_store(),
    )


# ---------------------------------------------------------------------------
# Adapters
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_whatsapp_adapter():
    from adapters.whatsapp import WhatsAppCloudAdapter

    s = get_settings()

    # In a real deployment, these resolvers consult the DB.
    # For Sprint 1 the smoke test uses a single hard-coded tenant.
    def tenant_resolver(phone_number_id: str) -> str | None:
        return None  # TODO: lookup tenant_whatsapp_credentials table

    def creds_provider(tenant_id: str) -> tuple[str, str]:
        raise NotImplementedError("tenant_whatsapp_credentials not implemented yet")

    return WhatsAppCloudAdapter(
        app_secret=s.whatsapp_app_secret,
        verify_token=s.whatsapp_verify_token,
        graph_api_base=s.meta_graph_api_base,
        tenant_resolver=tenant_resolver,
        creds_provider=creds_provider,
    )


@lru_cache(maxsize=1)
def get_widget_adapter():
    from adapters.widget import WidgetAdapter

    s = get_settings()

    def tenant_resolver(widget_key: str):
        # TODO: lookup tenant_widget_keys table
        return None

    return WidgetAdapter(tenant_resolver=tenant_resolver)
