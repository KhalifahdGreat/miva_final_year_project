#!/usr/bin/env python3
"""End-to-end smoke test.

Proves the FYP scaffold can:

    1. import the parent ``ofofo_engine`` package as a library,
    2. open the existing Milvus DB at ``../../milestone_two/db/ofofo_vectors.db``,
    3. run the new core engine (language detector + RAG + prompt builder +
       guards + orchestrator), and
    4. produce a sensible Nigerian-fluent reply from Groq + Llama 3.3 70B.

Run from the project root:

    make smoke

Or directly:

    PYTHONPATH=$(pwd)/../..:$PYTHONPATH \\
        python scripts/smoke_test.py

It does NOT touch any tenant Postgres data — it uses the in-memory
TenantService and an in-memory history store.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Make both `core/`, `adapters/`, `app/` and the parent project root importable.
HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent                            # final_year_project/sme_chatbot/
OFOFO_ROOT = PROJECT.parent.parent               # repo root that contains ofofo_engine/
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(OFOFO_ROOT))


def main() -> int:
    print("=" * 72)
    print("SME Chatbot — end-to-end smoke test")
    print("=" * 72)

    # Lazy imports so failure messages are localised and readable.
    from app.config import get_settings

    settings = get_settings()
    if not settings.groq_api_key:
        print("\nGROQ_API_KEY is empty. Set it in .env before running the smoke test.")
        return 2

    db_path = Path(settings.ofofo_vector_db_path).resolve()
    if not db_path.exists():
        print(f"\nVector DB not found at: {db_path}")
        print("Edit OFOFO_VECTOR_DB_PATH in .env to point at ofofo_vectors.db.")
        return 2

    print(f"  GROQ key            : {'set' if settings.groq_api_key else 'MISSING'}")
    print(f"  LLM model           : {settings.llm_model}")
    print(f"  Vector DB           : {db_path}")
    print(f"  Embedding model     : {settings.ofofo_embedding_model}")

    # ---------------- Build the engine wiring ----------------
    print("\n[1/6] Building EngineConfig + RetrievalService + LLMClient ...")
    from ofofo_engine.config import EngineConfig
    from ofofo_engine.llm import LLMClient
    from ofofo_engine.retrieval import RetrievalService

    engine_cfg = EngineConfig(
        groq_api_key=settings.groq_api_key,
        llm_model=settings.llm_model,
        vector_db_path=db_path,
        embedding_model=settings.ofofo_embedding_model,
    )
    retrieval = RetrievalService(engine_cfg)
    llm = LLMClient(engine_cfg)
    print("      shared engine ready.")

    # ---------------- Build the FYP orchestrator ----------------
    print("\n[2/6] Building SMEOrchestrator + in-memory tenant config ...")
    from core.orchestrator import SMEOrchestrator
    from core.tenant_service import InMemoryTenantService, default_config

    tenants = InMemoryTenantService()
    tenant_id = "11111111-1111-1111-1111-111111111111"
    cfg = default_config(tenant_id, business_name="Mama Ngozi's Kitchen")
    cfg.tone = "pidgin_friendly"
    cfg.tagline = "We dey serve the best jollof for Yaba."
    cfg.greeting = "Welcome to Mama Ngozi's! How I fit help you today?"
    tenants.save(cfg)

    orchestrator = SMEOrchestrator(
        retrieval=retrieval,
        llm=llm,
        tenant_service=tenants,
    )
    print(f"      tenant '{cfg.business_name}' loaded.")

    # ---------------- Language detector check ----------------
    print("\n[3/6] Quick language-detector sanity check ...")
    from core import language_detector

    samples = [
        ("Bros abeg how much be the gold watch?", "pid"),
        ("Hello, do you ship to Abuja?", "en"),
        ("Una dey open today abi?", "pid"),
        ("Wetin dey, I wan buy your jollof", "pid"),
    ]
    for text, expected in samples:
        result = language_detector.detect(text)
        flag = "OK" if result.dominant == expected else "DIFFERS"
        print(f"      [{flag}] '{text[:40]}' → {result.dominant} "
              f"(scores={ {k: round(v, 2) for k, v in result.scores.items()} })")

    # ---------------- One real orchestrated turn ----------------
    print("\n[4/6] Running one orchestrated Pidgin turn ...")
    from core.types import CanonicalMessage

    msg = CanonicalMessage(
        tenant_id=tenant_id,
        channel="widget",
        sender_id="smoke-test-1",
        text="Abeg, una dey open today and how much be one plate of jollof rice?",
        received_at=datetime.now(timezone.utc),
        channel_msg_id="smoke-msg-1",
    )

    result = orchestrator.handle(msg)

    print("\n[5/6] Result")
    print(f"      Detected language : {result.detected_language}")
    print(f"      Mixed languages   : {result.is_mixed_language}")
    print(f"      Retrieved chunks  : {result.retrieval_count}")
    print(f"      Escalated         : {result.escalated}")
    print(f"      Latency breakdown : "
          f"lang={result.latency_breakdown_ms.get('lang_ms', 0):.0f}ms, "
          f"retrieval={result.latency_breakdown_ms.get('retrieval_ms', 0):.0f}ms, "
          f"lm={result.latency_breakdown_ms.get('lm_ms', 0):.0f}ms, "
          f"total={result.latency_breakdown_ms.get('total_ms', 0):.0f}ms")

    print("\n[6/6] Reply")
    print("      " + "-" * 60)
    for line in (result.reply_text or "").splitlines() or [result.reply_text or "(empty)"]:
        print(f"      {line}")
    print("      " + "-" * 60)

    # Cleanup
    retrieval.close()
    print("\nDone. If the reply above sounds like a real Nigerian shop owner, the wiring works.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
