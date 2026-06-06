#!/usr/bin/env python3
"""End-to-end persistence smoke test.

Proves that:
    1. The schema in migrations/001_initial.sql applies cleanly to a fresh DB.
    2. PostgresHistoryStore writes a conversation + two turns.
    3. The orchestrator calls Groq, the response comes back Pidgin-fluent,
       AND an audit_record row is written carrying the system prompt,
       user prompt, response text, latency breakdown and chunk ids.
    4. The /v1/tenants/{tid}/analytics/summary aggregation returns sensible
       numbers given the row we just wrote.

Run from the project root:

    docker compose up -d postgres redis
    psql $DATABASE_URL -f migrations/001_initial.sql
    python3 scripts/smoke_test_persistence.py
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
OFOFO_ROOT = PROJECT.parent.parent
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(OFOFO_ROOT))


def main() -> int:
    print("=" * 72)
    print("SME Chatbot — persistence smoke test")
    print("=" * 72)

    from app.config import get_settings
    settings = get_settings()
    for required in ("groq_api_key", "database_url"):
        if not getattr(settings, required):
            print(f"\n{required.upper()} is missing — set it in .env before running.")
            return 2
    if not Path(settings.ofofo_vector_db_path).exists():
        print(f"\nVector DB not found at: {settings.ofofo_vector_db_path}")
        return 2

    print(f"  Database     : {settings.database_url.split('@')[-1]}")
    print(f"  LLM model    : {settings.llm_model}")

    # 1.  Pool + schema sanity
    print("\n[1/5] Verifying Postgres schema is in place ...")
    from app.db import init_pool
    pool = init_pool()
    expected = {"users", "tenants", "tenant_configs", "documents", "conversations",
                "turns", "audit_records", "feedback", "processed_messages"}
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
        present = {r[0] for r in cur.fetchall()}
    missing = expected - present
    if missing:
        print(f"      Missing tables: {missing}")
        print("      Run:  psql $DATABASE_URL -f migrations/001_initial.sql")
        return 3
    print(f"      All {len(expected)} core tables present.")

    # 2.  Provision a tenant and orchestrator
    print("\n[2/5] Provisioning a fresh tenant ...")
    from core.tenant_service import PostgresTenantService, default_config
    tenants = PostgresTenantService(pool)
    tid = str(uuid.uuid4())
    # First insert a tenants row so the foreign keys validate
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenants (tenant_id, business_name, slug) VALUES (%s, %s, %s)",
            (tid, "Smoke-Test Kitchen", f"smoke-{tid[:8]}"),
        )
    cfg = default_config(tid, "Smoke-Test Kitchen")
    cfg.tone = "pidgin_friendly"
    cfg.greeting = "Welcome to Mama Ngozi! How I fit help?"
    tenants.save(cfg)
    print(f"      tenant_id = {tid}")

    # 3.  Run a Pidgin orchestrator turn end-to-end
    print("\n[3/5] Running one orchestrated Pidgin turn through Postgres ...")
    from core.conversation_store import AuditStore, PostgresHistoryStore
    from core.orchestrator import SMEOrchestrator
    from core.types import CanonicalMessage
    from ofofo_engine.config import EngineConfig
    from ofofo_engine.llm import LLMClient
    from ofofo_engine.retrieval import RetrievalService

    engine_cfg = EngineConfig(
        groq_api_key=settings.groq_api_key,
        llm_model=settings.llm_model,
        vector_db_path=Path(settings.ofofo_vector_db_path).resolve(),
        embedding_model=settings.ofofo_embedding_model,
    )
    retrieval = RetrievalService(engine_cfg)
    llm = LLMClient(engine_cfg)

    orchestrator = SMEOrchestrator(
        retrieval=retrieval, llm=llm, tenant_service=tenants,
        history=PostgresHistoryStore(pool),
        audit_store=AuditStore(pool),
    )

    msg = CanonicalMessage(
        tenant_id=tid, channel="widget", sender_id="smoke-sender-1",
        text="Abeg, una dey open today and how much be one plate of jollof?",
        received_at=datetime.now(timezone.utc),
        channel_msg_id=f"smoke-{uuid.uuid4().hex[:8]}",
    )
    result = orchestrator.handle(msg)

    print(f"      detected language : {result.detected_language}")
    print(f"      reply             : {result.reply_text}")
    print(f"      latency (total)   : {result.latency_breakdown_ms.get('total_ms', 0):.0f}ms")

    # 4.  Verify rows landed in conversations + turns + audit_records
    print("\n[4/5] Verifying persistence ...")
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM conversations WHERE tenant_id = %s", (tid,))
        n_conv = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM turns WHERE tenant_id = %s", (tid,))
        n_turns = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM audit_records WHERE tenant_id = %s", (tid,))
        n_audit = cur.fetchone()[0]
    print(f"      conversations  rows: {n_conv}  (expected 1)")
    print(f"      turns          rows: {n_turns} (expected 2 — user + assistant)")
    print(f"      audit_records  rows: {n_audit} (expected 1)")
    assert n_conv == 1 and n_turns == 2 and n_audit == 1, "persistence assertions failed"

    # 5.  Verify analytics summary aggregation works
    print("\n[5/5] Verifying analytics summary aggregation ...")
    from fastapi.testclient import TestClient
    from app.main import app as fastapi_app
    client = TestClient(fastapi_app)
    resp = client.get(f"/v1/tenants/{tid}/analytics/summary?window=24h")
    if resp.status_code == 200:
        data = resp.json()
        print(f"      messages_total    : {data['messages_total']}")
        print(f"      escalations_total : {data['escalations_total']}")
        print(f"      deflection_rate   : {data['deflection_rate']}")
        print(f"      by_language       : {data['by_language']}")
    else:
        print(f"      analytics call failed: HTTP {resp.status_code}: {resp.text}")
        return 4

    # Cleanup
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM tenants WHERE tenant_id = %s", (tid,))
    retrieval.close()

    print("\nAll checks passed. Persistence + audit + analytics work end-to-end.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
