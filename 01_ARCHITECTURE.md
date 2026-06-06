# Architecture Reference

Companion to `00_TECHNICAL_PRD.md`. This document specifies the component-level architecture, module contracts, sequence diagrams, and deployment topology. It is the second document to read after the PRD and the primary reference during build.

---

## Table of Contents

1. [Architectural Style and Principles](#1-architectural-style-and-principles)
2. [Logical Component Diagram](#2-logical-component-diagram)
3. [Module Contracts](#3-module-contracts)
4. [Sequence Diagrams](#4-sequence-diagrams)
5. [Data Flow](#5-data-flow)
6. [Deployment Topology](#6-deployment-topology)
7. [Scaling Plan](#7-scaling-plan)
8. [Failure Modes and Recovery](#8-failure-modes-and-recovery)

---

## 1. Architectural Style and Principles

The platform follows a **modular monolith** for v1: a single FastAPI service exposing the public API and channel webhooks, plus a small worker process for background ingestion. The model is served as a separate process (vLLM) behind an internal HTTP boundary, so it can be swapped between providers (vLLM / HF Endpoint / Groq) without touching the orchestrator.

### Principles

1. **Single source of truth for tenant identity.** A `tenant_id` is resolved at the edge and threaded through every internal call. No function loads tenant data from a global request context.
2. **The LLM is a replaceable component.** All LLM calls go through one client wrapper (`LMClient`) with retries, timeouts, and a model-name parameter. Swapping providers is a config change, not a code change.
3. **Retrieval is per-tenant by construction.** The retrieval service takes `tenant_id` as a required parameter; it cannot be called without one.
4. **Channels are dumb adapters.** Adapters do not contain business logic; they only translate between the channel's wire format and the canonical `Message` type.
5. **Configuration is data, not code.** Tone, languages, escalation rules — all stored in a versioned JSONB column. Application code reads them; it never embeds them.
6. **Every important decision is auditable.** Every conversation turn stores its retrieved chunks, the exact prompt, the model name, the response, and the latency by stage.
7. **No hidden state.** Modules expose their dependencies through constructor injection (`__init__`); no module-level singletons except one optional in-process LRU cache for embedders and tokenisers.

---

## 2. Logical Component Diagram

```
                           ┌──────────────────────┐
                           │  Admin Dashboard     │
                           │  (Next.js, Vercel)   │
                           └─────────┬────────────┘
                                     │ REST + JWT
                                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│                         API Gateway (FastAPI)                          │
│  ┌──────────────────────┐  ┌────────────────┐  ┌────────────────────┐  │
│  │ Auth & tenant        │  │ Public REST    │  │ Channel webhooks   │  │
│  │ resolver middleware  │  │  (admin ops)   │  │  WhatsApp, widget  │  │
│  └──────────────────────┘  └───────┬────────┘  └─────────┬──────────┘  │
│                                    │                     │             │
│                                    └──────┬──────────────┘             │
│                                           ▼                            │
│             ┌─────────────────────────────────────────────┐            │
│             │       ConversationOrchestrator              │            │
│             │  (the only place business logic lives)      │            │
│             └─┬───────┬───────┬──────────┬─────────┬─────┘             │
│               │       │       │          │         │                   │
│         ┌─────▼──┐ ┌──▼───┐ ┌─▼─────┐ ┌──▼────┐ ┌──▼──────┐            │
│         │Persona │ │Lang  │ │Retri- │ │Prompt │ │Guards   │            │
│         │Service │ │Detect│ │eval   │ │Builder│ │+ Esc.   │            │
│         └────────┘ └──────┘ └───┬───┘ └───┬───┘ └─────────┘            │
│                                 │         │                            │
│                                 │         │                            │
│                                 ▼         ▼                            │
│                       ┌────────────────────┐                           │
│                       │      LMClient      │                           │
│                       │ (vLLM | HF | Groq) │                           │
│                       └────────────────────┘                           │
└────────────────────────────────────────────────────────────────────────┘
       │                │                │                 │
       ▼                ▼                ▼                 ▼
 ┌───────────┐    ┌──────────┐    ┌──────────────┐  ┌─────────────┐
 │ Postgres  │    │  Redis   │    │ Vector Store │  │ Object Store│
 │ (RLS)     │    │ (cache)  │    │ (per-tenant) │  │  (R2)       │
 └───────────┘    └──────────┘    └──────────────┘  └─────────────┘

         ┌──────────────────────────────────────┐
         │           Worker Process             │
         │  • ingestion pipeline                │
         │  • re-embedding on edit              │
         │  • daily aggregation jobs            │
         │  • feedback → boosted-FAQ promotion  │
         └──────────────────────────────────────┘
                        ▲
                        │  RQ jobs over Redis
                        │
                ┌───────┴────────┐
                │ API Gateway    │
                │ enqueues here  │
                └────────────────┘
```

---

## 3. Module Contracts

The following are **interface contracts**, not implementations. Each is a small, focused module with explicit inputs and outputs. Implementations are in `02_CORE_ENGINE.md`.

### 3.1 `LMClient`

```python
class LMClient:
    """Single point of contact with any language model.

    Provider is configurable: 'vllm-local', 'hf-endpoint', 'groq'.
    Adds retries with exponential backoff, timeouts, and per-tenant
    rate-limit hooks.
    """
    def __init__(self, provider: str, model: str, api_key: str | None,
                 timeout_s: float = 8.0, max_retries: int = 3) -> None: ...

    def complete(self, *,
                 system: str,
                 user: str,
                 history: list[dict] | None = None,
                 temperature: float = 0.4,
                 max_tokens: int = 400,
                 stop: list[str] | None = None) -> "LMResponse": ...
```

`LMResponse` carries `text`, `prompt_tokens`, `completion_tokens`, `model`, `latency_ms`, `provider`.

### 3.2 `RetrievalService`

```python
class RetrievalService:
    """Per-tenant semantic retrieval. Cannot be invoked without tenant_id."""

    def __init__(self, vector_client, embedder, *, default_top_k: int = 5,
                 min_score: float = 0.30) -> None: ...

    def search(self, tenant_id: UUID, query: str, *,
               top_k: int | None = None,
               min_score: float | None = None,
               document_types: list[str] | None = None) -> list[Hit]: ...

    def search_weighted(self, tenant_id: UUID, query: str, *,
                        weights: dict[str, int],   # by document_type
                        top_k: int = 7) -> list[Hit]: ...

    def upsert(self, tenant_id: UUID, chunks: list[Chunk]) -> int: ...
    def delete_document(self, tenant_id: UUID, document_id: UUID) -> int: ...
```

A `Hit` is `{chunk_id, document_id, document_type, text, section, score, metadata}`.

The two retrieval modes — `search` (uniform) and `search_weighted` (boosting certain document types) — mirror the proven pattern from the production engine: weighted retrieval lets manual FAQs and pricing sheets pull more attention than long policy PDFs.

### 3.3 `PersonaService`

```python
class PersonaService:
    """Loads and caches per-tenant configuration."""

    def get(self, tenant_id: UUID) -> "TenantConfig": ...
    def save(self, tenant_id: UUID, config: "TenantConfig",
             *, actor_user_id: UUID) -> int:    # returns new version
        ...
    def revisions(self, tenant_id: UUID) -> list["ConfigRevision"]: ...
    def rollback(self, tenant_id: UUID, version: int) -> None: ...
```

### 3.4 `LanguageDetector`

```python
class LanguageDetector:
    """Returns the dominant language and any secondary languages.

    Output values: 'en', 'pid', 'yo', 'ha', 'ig', 'mixed', 'unknown'.
    """

    def detect(self, text: str) -> "LangResult": ...
```

`LangResult` carries `dominant: str`, `mixed: bool`, `scores: dict[str, float]`.

Pidgin is detected via a hand-tuned heuristic layer on top of FastText langid (off-the-shelf detectors call Pidgin "English" almost always). The heuristic uses a corpus of high-precision Pidgin tokens (`abeg`, `wahala`, `wetin`, `dey`, `na`, `sef`, `sha`, `wey`, `e go`, `no be`, `omo`, `ehn`, `walahi`, etc.) plus discourse-marker patterns. This subsystem is itself a small thesis sub-contribution.

### 3.5 `PromptBuilder`

```python
class PromptBuilder:
    """Composes the system + user message sent to the LM."""

    def build(self, *,
              tenant_config: TenantConfig,
              retrieved_chunks: list[Hit],
              history: list[Turn],
              user_message: str,
              detected_language: str) -> tuple[str, str]:
        """Returns (system_prompt, user_prompt)."""
```

The builder is the single place language-specific instructions are added (e.g. *"Reply in Pidgin if the customer wrote Pidgin; never translate"*). All Pidgin grammar guidance lives here.

### 3.6 `Guardrails`

```python
class Guardrails:
    """Post-generation checks. Can mutate or reject the response."""

    def apply(self, response_text: str, *,
              tenant_config: TenantConfig,
              user_message: str,
              detected_language: str) -> "GuardResult":
        """GuardResult = {final_text, mutated: bool, escalated: bool, reason: str}"""
```

Built-in checks:

- **Price hallucination:** if the response contains a money pattern (`₦`, `N`, `naira`, `NGN`) and the matching chunks' retrieval did not contain the same number, replace with *"let me confirm and revert"* and escalate.
- **PII echo:** strip any phone number, BVN/NIN-shaped strings, account numbers from the response.
- **Profanity threshold:** flag (do not block) — Nigerian discourse is permissive; only block overt slurs.
- **Length:** truncate beyond 800 chars; for WhatsApp, prefer ≤ 600.
- **Escalation triggers:** match against tenant's escalation rules.

### 3.7 `ConversationOrchestrator`

```python
class ConversationOrchestrator:
    """The only place business logic for a single turn lives."""

    def __init__(self, *, persona: PersonaService, retrieval: RetrievalService,
                 lang: LanguageDetector, prompts: PromptBuilder,
                 lm: LMClient, guards: Guardrails,
                 history: HistoryService, audit: AuditWriter) -> None: ...

    def handle(self, msg: CanonicalMessage) -> "OrchestrationResult": ...
```

`CanonicalMessage`:

```python
@dataclass
class CanonicalMessage:
    tenant_id: UUID
    channel: Literal["whatsapp", "widget"]
    sender_id: str            # phone number for WhatsApp; widget session id for web
    text: str
    attachments: list[Attachment]
    received_at: datetime
    channel_msg_id: str       # for idempotency
```

`OrchestrationResult`:

```python
@dataclass
class OrchestrationResult:
    reply_text: str
    escalated: bool
    escalation_reason: str | None
    detected_language: str
    retrieval_count: int
    latency_breakdown: dict[str, float]   # ms per stage
    turn_id: UUID
```

### 3.8 `ChannelAdapter`

```python
class ChannelAdapter(Protocol):
    name: str

    def parse_inbound(self, raw_payload: dict) -> list[CanonicalMessage]: ...
    def send_reply(self, msg: CanonicalMessage, reply_text: str) -> None: ...
    def send_typing_indicator(self, msg: CanonicalMessage) -> None: ...
    def verify_webhook(self, headers: dict, raw_body: bytes) -> bool: ...
```

Concrete implementations: `WhatsAppCloudAdapter`, `WebWidgetAdapter`. (`InstagramAdapter` later.)

### 3.9 `IngestionPipeline`

```python
class IngestionPipeline:
    """Worker-side: file → chunks → embeddings → vector store."""

    def ingest_document(self, tenant_id: UUID, document_id: UUID,
                        s3_key: str, document_type: str) -> "IngestionResult": ...
```

`IngestionResult` carries: `chunks_created`, `chars_processed`, `duration_s`, `errors`.

### 3.10 `HistoryService`

```python
class HistoryService:
    """Conversation memory for a (tenant, sender) pair."""

    def append(self, tenant_id: UUID, sender_id: str, turn: Turn) -> None: ...
    def last_n(self, tenant_id: UUID, sender_id: str, n: int = 6) -> list[Turn]: ...
    def reset(self, tenant_id: UUID, sender_id: str) -> None: ...
```

Backed by Redis with 24h TTL; on miss, falls through to Postgres.

### 3.11 `AuditWriter`

```python
class AuditWriter:
    """Writes a single durable record per turn for audit + analytics."""

    def write(self, *, tenant_id: UUID, conversation_id: UUID, turn_id: UUID,
              user_text: str, retrieved_chunk_ids: list[UUID],
              system_prompt: str, user_prompt: str, response_text: str,
              model: str, latency_breakdown: dict, escalated: bool,
              language: str) -> None: ...
```

The audit record is the single source of truth for thesis-grade evaluation: it lets the same turn be re-graded later, and lets ablations be rerun (e.g. "what would the response have been with no RAG?").

---

## 4. Sequence Diagrams

### 4.1 Inbound text turn (WhatsApp)

```
Customer        Meta             API Gateway        Orchestrator         RetrievalSvc        LMClient        DB
   │              │                    │                  │                   │                │            │
   │── send msg ─▶│                    │                  │                   │                │            │
   │              │── webhook (POST) ─▶│                  │                   │                │            │
   │              │                    │── verify sig     │                   │                │            │
   │              │                    │── dedupe by msg_id                   │                │            │
   │              │                    │── parse_inbound ─▶ CanonicalMessage  │                │            │
   │              │                    │                  │                   │                │            │
   │              │                    │── handle(msg) ──▶│                   │                │            │
   │              │                    │                  │── load tenant config (cache → DB)  │            │
   │              │                    │                  │── load history (Redis → DB)        │            │
   │              │                    │                  │── detect language                  │            │
   │              │                    │                  │── search_weighted ─▶               │            │
   │              │                    │                  │                   │── embed query  │            │
   │              │                    │                  │                   │── vector search│            │
   │              │                    │                  │◀── chunks ────────│                │            │
   │              │                    │                  │── build prompt                     │            │
   │              │                    │                  │── complete ─────────────────────────▶          │
   │              │                    │                  │                                    │── HTTP    │
   │              │                    │                  │◀── response ────────────────────────│           │
   │              │                    │                  │── apply guards                     │            │
   │              │                    │                  │── persist turn ────────────────────────────────▶│
   │              │                    │◀── result ───────│                                    │            │
   │              │                    │── send_reply via WhatsApp Cloud API                   │            │
   │              │◀── HTTP send ──────│                                                       │            │
   │◀── reply ────│                    │                                                       │            │
```

### 4.2 Knowledge ingestion

```
Owner       Dashboard      API Gateway       Worker        ObjectStore     Embedder      VectorStore
  │            │                │              │                │             │              │
  │── upload PDF ──────────────▶│              │                │             │              │
  │            │                │── presign ──▶│ (or direct)   │             │              │
  │            │                │── store metadata row in DB   │             │              │
  │            │                │── enqueue job(document_id) ▶ │             │              │
  │            │                │              │── download s3 ─▶│             │              │
  │            │                │              │◀────────────────│             │              │
  │            │                │              │── parse + chunk │             │              │
  │            │                │              │── embed batch ─────────────▶│              │
  │            │                │              │◀─────────────────────────────│              │
  │            │                │              │── upsert to tenant namespace ─────────────▶│
  │            │                │              │── update document status "ready"           │
  │            │◀── poll status (via SWR / WS) │                                            │
  │◀── ready ──│                                                                           │
```

### 4.3 Escalation

```
Customer       Orchestrator         Guardrails        SME owner (out-of-band)
   │                │                    │                       │
   │── "I want refund N80k" ──▶          │                       │
   │                │── handle(msg)      │                       │
   │                │── ... build + LM   │                       │
   │                │── apply guards ───▶│                       │
   │                │◀── escalated=true  │                       │
   │                │── reply with fallback message              │
   │                │── enqueue handoff event                    │
   │◀── "let me get a human..." ────────                         │
   │                │                                            │
   │                │                    ── WhatsApp / email ──▶ │
                                                                 │
                                                                 ▼
                                                              owner takes over
```

---

## 5. Data Flow

### 5.1 At-rest data

| Store | What lives there |
|---|---|
| Postgres | tenants, users, configs, conversations, turns, documents (metadata only), feedback, audit records, escalation events |
| Vector DB | chunks (embedding + text + metadata), per-tenant namespace |
| Object store (R2) | raw uploaded files, optional audit-log archives |
| Redis | (a) conversation history with 24h TTL, (b) tenant config cache 5-min TTL, (c) embedder warm cache, (d) rate-limit counters, (e) RQ job queue |

### 5.2 In-flight data

A canonical message flows: **edge → orchestrator → retrieval → LLM → guardrails → channel adapter**. No raw user text is logged in plaintext beyond the audit table; logs use IDs and short hashes.

---

## 6. Deployment Topology

### 6.1 MVP topology (target during pilots)

```
┌────────────────── public internet ─────────────────────┐
│                                                        │
│  customers (WhatsApp / browser)         SME owners     │
│            │                                  │        │
└────────────│──────────────────────────────────│────────┘
             │                                  │
             ▼                                  ▼
   ┌──────────────────────┐         ┌────────────────────┐
   │ Cloudflare (TLS,    │          │ Vercel (frontend) │
   │ DNS, WAF basics)    │          └─────────┬──────────┘
   └──────────┬──────────┘                    │
              ▼                               │ REST
   ┌──────────────────────┐                   │
   │ Render / Fly         │◀──────────────────┘
   │  • api (FastAPI)     │
   │  • worker (RQ)       │
   └──┬───────────┬──────┘
      │           │
      │           │
      ▼           ▼
 ┌──────────┐ ┌─────────┐         ┌────────────────────┐
 │ Postgres │ │  Redis  │         │ GPU VM (RunPod)    │
 │ (Render) │ │(Render) │         │  • vLLM serving    │
 └──────────┘ └─────────┘         │    fine-tuned LM   │
                                  └─────────┬──────────┘
                                            │ (HTTP, internal token)
                                            │
                                  ┌─────────▼──────────┐
                                  │ Cloudflare R2      │
                                  │  + Milvus volume   │
                                  └────────────────────┘
```

### 6.2 Service boundaries

| Service | Port | Public? | Replicas |
|---|---|---|---|
| `api` (FastAPI, gunicorn + uvicorn workers) | 8000 | Yes | 2 (during pilots) |
| `worker` (RQ) | – | No | 1 |
| `lm` (vLLM) | 8001 | No (private) | 1 (single GPU) |
| `postgres` | 5432 | No | 1 |
| `redis` | 6379 | No | 1 |

### 6.3 Configuration

- All secrets via the platform's environment-variable manager (never committed).
- A single `app_config.yaml` for non-secret defaults, env-var-overridable.
- Per-tenant config lives in DB only.

### 6.4 Backups

- Postgres: daily pg_dump to R2, 14-day retention.
- Vector DB: weekly snapshot of the on-disk Milvus volume to R2.
- Object storage: R2's built-in versioning enabled.

---

## 7. Scaling Plan

The MVP is sized for the pilot. The thesis can credibly discuss scaling along the following axes:

| Axis | First bottleneck | Mitigation |
|---|---|---|
| Tenants | Vector DB collection-count limits (Milvus Lite caps low) | Move to pgvector or Qdrant Cloud at ~50 tenants |
| Concurrent conversations | LLM throughput (single GPU) | Add a second GPU; or batch with vLLM's continuous batching, already enabled |
| Knowledge size per tenant | Embedding compute on ingest | Async worker scales out horizontally; ingestion isn't latency-critical |
| Latency P95 | LLM inference | Quantise to int4, switch to a 7B fine-tune for smaller tenants, add response streaming |
| WhatsApp message rate | Meta rate limits per number | Multi-number per tenant; queue smoothing |

---

## 8. Failure Modes and Recovery

| Failure | Detection | Mitigation | Recovery |
|---|---|---|---|
| LLM down | health probe + 5xx on `complete()` | feature flag → Groq fallback → friendly fallback message | swap automatic, no data loss |
| Vector DB down | retrieval timeout > 1.5s | bypass RAG, send a "we're checking on that" reply, escalate | service auto-resumes; previously persisted chunks survive |
| Postgres down | DB driver errors | API returns 503; channel adapter buffers webhooks via Meta retries | restore from latest backup if catastrophic |
| Redis down | cache misses → DB fall-through still works | continue; latency rises | restart service |
| Webhook ingress failure | 5xx alerts | Meta retries automatically with backoff; ensure idempotency by `channel_msg_id` | Meta retries up to 7 times over 24h |
| Wrong tenant resolved | RLS makes data exposure impossible; 403 returned | unit tests + integration test that asserts cross-tenant access fails | log + alert |
| Hallucinated price | guardrail catches the pattern; escalate | reply with safe fallback; SME notified | feedback loop: owner edits canonical answer; chunk re-embedded |

A short runbook for each lives in `/docs/runbooks/` (build during pilots).
