"""Single-turn conversation orchestrator.

The only place where business logic for one customer-service turn lives:

    inbound CanonicalMessage
        │
        ▼
    1. resolve tenant config
    2. fetch conversation history
    3. detect language (Pidgin-aware)
    4. RAG retrieval:
         - tenant's own knowledge collection
         - shared Nigerian corpus (Nairaland, slang, replies)
    5. build prompt (persona + Nigerian fluency + Pidgin block + KB)
    6. call LM (Groq + Llama 3.3 70B, via ofofo_engine.LLMClient)
    7. apply guards (price hallucination, PII, escalation rules)
    8. persist turn + audit trail
        │
        ▼
    OrchestrationResult (reply text + diagnostics)

This module imports `ofofo_engine.retrieval.RetrievalService` and
`ofofo_engine.llm.LLMClient` so we reuse the existing 2 M-vector Nigerian
corpus and the proven Groq client wrapper.  Nothing in `ofofo_engine/`
is modified.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from . import language_detector, prompt_builder
from .guards import apply_guards
from .types import CanonicalMessage, Hit, OrchestrationResult, TenantConfig, Turn

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared-corpus collections (already populated, ~2 M vectors)
# ---------------------------------------------------------------------------

SHARED_NIGERIAN_COLLECTIONS = (
    "nigerian_slang",
    "nigerian_replies",
    "nairaland_discourse",
)


# ---------------------------------------------------------------------------
# Helpers — adapt ofofo_engine.SearchHit → core.Hit
# ---------------------------------------------------------------------------


def _adapt_hit(raw: Any) -> Hit:
    """Convert an ofofo_engine SearchHit dataclass into our core.Hit."""
    return Hit(
        chunk_id=getattr(raw, "chunk_id", 0) or 0,
        text=raw.text,
        document_type=raw.section or "",
        section=raw.section,
        score=raw.score,
        boost=1.0,
        document_id=getattr(raw, "source", ""),
        collection=getattr(raw, "collection", ""),
        metadata=getattr(raw, "metadata", {}) or {},
    )


# ---------------------------------------------------------------------------
# Conversation history protocol (kept minimal so any backend can plug in)
# ---------------------------------------------------------------------------


class HistoryStore:
    """Minimal interface for the conversation memory layer."""

    def append(self, tenant_id: str, sender_id: str, turn: Turn) -> None:  # pragma: no cover
        raise NotImplementedError

    def last_n(self, tenant_id: str, sender_id: str, n: int = 6) -> list[Turn]:  # pragma: no cover
        raise NotImplementedError


class InMemoryHistoryStore(HistoryStore):
    """For dev / smoke testing.  Holds the last 50 turns per (tenant, sender)."""

    def __init__(self) -> None:
        self._store: dict[tuple[str, str], list[Turn]] = {}

    def append(self, tenant_id: str, sender_id: str, turn: Turn) -> None:
        key = (tenant_id, sender_id)
        self._store.setdefault(key, []).append(turn)
        if len(self._store[key]) > 50:
            self._store[key] = self._store[key][-50:]

    def last_n(self, tenant_id: str, sender_id: str, n: int = 6) -> list[Turn]:
        return self._store.get((tenant_id, sender_id), [])[-n:]


# ---------------------------------------------------------------------------
# The orchestrator
# ---------------------------------------------------------------------------


class SMEOrchestrator:
    """Handles one customer-service turn end-to-end."""

    def __init__(
        self,
        *,
        retrieval,                       # ofofo_engine.retrieval.RetrievalService
        llm,                             # ofofo_engine.llm.LLMClient
        tenant_service,                  # core.tenant_service.TenantService
        history: HistoryStore | None = None,
        audit_store=None,                # core.conversation_store.AuditStore | None
        shared_collections: tuple[str, ...] = SHARED_NIGERIAN_COLLECTIONS,
        tenant_kb_prefix: str = "kb_",
        temperature: float = 0.4,
        max_tokens: int = 400,
    ) -> None:
        self._retrieval = retrieval
        self._llm = llm
        self._tenants = tenant_service
        self._history = history or InMemoryHistoryStore()
        self._audit = audit_store
        self._shared_collections = shared_collections
        self._tenant_kb_prefix = tenant_kb_prefix
        self._temperature = temperature
        self._max_tokens = max_tokens

    # -------------------------------------------------------------------
    # Retrieval
    # -------------------------------------------------------------------

    def _tenant_collection(self, tenant_id: str) -> str:
        return f"{self._tenant_kb_prefix}{tenant_id.replace('-', '')[:12]}"

    def _retrieve(self, tenant_id: str, query: str, cfg: TenantConfig) -> list[Hit]:
        """Pull chunks from the tenant's KB + the shared Nigerian corpus.

        The tenant's own knowledge always takes precedence; the shared
        Nigerian corpus contributes linguistic and contextual chunks (slang,
        Pidgin discourse patterns) that help the LM stay Nigerian-fluent.
        """
        tenant_coll = self._tenant_collection(tenant_id)

        tenant_hits: list[Any] = []
        try:
            tenant_hits = self._retrieval.search(
                query,
                collections=[tenant_coll],
                top_k=4,
            )
        except Exception as exc:
            log.info("tenant collection %s not yet populated: %s", tenant_coll, exc)

        try:
            shared_hits = self._retrieval.search(
                query,
                collections=list(self._shared_collections),
                top_k=3,
            )
        except Exception as exc:
            log.warning("shared corpus search failed: %s", exc)
            shared_hits = []

        merged = list(tenant_hits) + list(shared_hits)
        adapted = [_adapt_hit(h) for h in merged]
        adapted.sort(key=lambda h: h.score, reverse=True)
        return adapted[:7]

    # -------------------------------------------------------------------
    # Single turn
    # -------------------------------------------------------------------

    def handle(self, msg: CanonicalMessage) -> OrchestrationResult:
        latencies: dict[str, float] = {}
        t_start = time.perf_counter()

        # 1. tenant config
        t = time.perf_counter()
        cfg = self._tenants.get(msg.tenant_id)
        latencies["config_ms"] = (time.perf_counter() - t) * 1000

        # 2. history
        t = time.perf_counter()
        history = self._history.last_n(msg.tenant_id, msg.sender_id, n=6)
        latencies["history_ms"] = (time.perf_counter() - t) * 1000

        # 3. language detect
        t = time.perf_counter()
        lang_result = language_detector.detect(msg.text)
        latencies["lang_ms"] = (time.perf_counter() - t) * 1000

        # 4. RAG — expand yo/ha/ig queries so MiniLM can hit an English KB
        t = time.perf_counter()
        retrieval_query = language_detector.expand_query_for_retrieval(msg.text)
        hits = self._retrieve(msg.tenant_id, retrieval_query, cfg)
        latencies["retrieval_ms"] = (time.perf_counter() - t) * 1000

        # 5. prompt build
        t = time.perf_counter()
        system, user = prompt_builder.build(
            tenant_config=cfg,
            retrieved_chunks=hits,
            history=history,
            user_message=msg.text,
            detected_language=lang_result.dominant,
            is_mixed_language=lang_result.mixed,
        )
        latencies["prompt_ms"] = (time.perf_counter() - t) * 1000

        # 6. LM call
        t = time.perf_counter()
        lm_text, model_name = self._call_llm(system, user)
        latencies["lm_ms"] = (time.perf_counter() - t) * 1000

        # 7. guards
        t = time.perf_counter()
        retrieved_blob = " ".join(h.text for h in hits)
        guarded = apply_guards(
            lm_text,
            retrieved_text_blob=retrieved_blob,
            tenant_config=cfg,
            user_message=msg.text,
            detected_language=lang_result.dominant,
        )
        latencies["guards_ms"] = (time.perf_counter() - t) * 1000

        # 8. persist history (with channel/lang metadata when the store supports it)
        t = time.perf_counter()
        user_turn = Turn(role="user", text=msg.text, ts=msg.received_at)
        assistant_turn = Turn(role="assistant", text=guarded.final_text)
        user_turn_id: str | None = None
        assistant_turn_id: str | None = None
        if hasattr(self._history, "append_with_meta"):
            user_turn_id = self._history.append_with_meta(
                tenant_id=msg.tenant_id, channel=msg.channel,
                sender_id=msg.sender_id, turn=user_turn,
                detected_language=lang_result.dominant,
                is_mixed_language=lang_result.mixed,
                escalated=False, channel_msg_id=msg.channel_msg_id,
            )
            assistant_turn_id = self._history.append_with_meta(
                tenant_id=msg.tenant_id, channel=msg.channel,
                sender_id=msg.sender_id, turn=assistant_turn,
                detected_language=lang_result.dominant,
                is_mixed_language=lang_result.mixed,
                escalated=guarded.escalated,
                escalation_reason=guarded.reason or None,
            )
        else:
            self._history.append(msg.tenant_id, msg.sender_id, user_turn)
            self._history.append(msg.tenant_id, msg.sender_id, assistant_turn)
        latencies["persist_ms"] = (time.perf_counter() - t) * 1000

        latencies["total_ms"] = (time.perf_counter() - t_start) * 1000

        result = OrchestrationResult(
            reply_text=guarded.final_text,
            detected_language=lang_result.dominant,
            is_mixed_language=lang_result.mixed,
            retrieval_count=len(hits),
            escalated=guarded.escalated,
            escalation_reason=guarded.reason or None,
            latency_breakdown_ms=latencies,
            model=model_name,
            provider="groq",
        )

        # 9. write audit record (best-effort — failures here never break the reply)
        if self._audit is not None and assistant_turn_id is not None:
            try:
                from .conversation_store import AuditPayload  # local to avoid cycle
                # conversation_id is what we just stamped onto turns; fetch via store helper
                conv_id = getattr(self._history, "_conversation_id", lambda *_: "")(
                    msg.tenant_id, msg.channel, msg.sender_id,
                )
                self._audit.write(AuditPayload(
                    tenant_id=msg.tenant_id,
                    conversation_id=conv_id,
                    turn_id=assistant_turn_id,
                    user_text=msg.text,
                    retrieved_chunk_ids=[h.chunk_id for h in hits if h.chunk_id],
                    retrieved_chunk_blob=retrieved_blob[:4000],
                    system_prompt=system,
                    user_prompt=user,
                    response_text=guarded.final_text,
                    result=result,
                    guard_mutations=list(guarded.mutations or []),
                ))
            except Exception:
                log.exception("audit write failed (non-fatal)")

        return result

    # -------------------------------------------------------------------
    # LM invocation (isolated so tests can mock easily)
    # -------------------------------------------------------------------

    def _call_llm(self, system: str, user: str) -> tuple[str, str]:
        """Call ofofo_engine.LLMClient.complete and return (text, model_name)."""
        try:
            text = self._llm.complete(
                system=system,
                user=user,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
            )
            model_name = getattr(self._llm, "_model", "llama-3.3-70b-versatile")
            return text or "", model_name
        except Exception as exc:
            log.exception("LM call failed: %s", exc)
            raise
