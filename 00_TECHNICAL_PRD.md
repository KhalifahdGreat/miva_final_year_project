# Technical Product Requirements Document (PRD)

**Project:** AI-Powered Multilingual Customer Service Chatbot for Nigerian SMEs Using a Nigeria-Specific Language Model

**Document type:** Master's final-year project — combined product + research artefact

**Working name:** *Naija SME Assistant* (placeholder — replace with final brand)

**Version:** 1.0

**Status:** Source-of-truth specification for build, evaluation, and thesis defence

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Research Contribution](#3-research-contribution)
4. [Goals and Non-Goals](#4-goals-and-non-goals)
5. [Personas and Use Cases](#5-personas-and-use-cases)
6. [Functional Requirements](#6-functional-requirements)
7. [Non-Functional Requirements](#7-non-functional-requirements)
8. [System Architecture (high level)](#8-system-architecture-high-level)
9. [Tech Stack](#9-tech-stack)
10. [Multi-tenancy Strategy](#10-multi-tenancy-strategy)
11. [Tenant Customisation Mechanisms](#11-tenant-customisation-mechanisms)
12. [Conversation Lifecycle](#12-conversation-lifecycle)
13. [Security, Privacy, and Compliance](#13-security-privacy-and-compliance)
14. [Performance Budget](#14-performance-budget)
15. [Observability and Operations](#15-observability-and-operations)
16. [Cost Model](#16-cost-model)
17. [Risks and Mitigations](#17-risks-and-mitigations)
18. [Assumptions and Open Questions](#18-assumptions-and-open-questions)
19. [Companion Documents](#19-companion-documents)

---

## 1. Executive Summary

The platform is a **multi-tenant, multilingual conversational AI service** designed specifically for Nigerian small and medium-sized enterprises (SMEs). It allows a non-technical business owner to:

1. Sign up, connect their WhatsApp Business number (or drop a one-line `<script>` tag on their website), and
2. Upload their product catalogue, FAQs, policies, and price lists, and
3. Configure a brand voice (formal, casual, Pidgin-friendly, etc.), and
4. Start serving customer queries automatically — in **English, Nigerian Pidgin, Yoruba, Hausa, and Igbo**, including code-switched utterances.

Under the hood, the platform combines two research-grade components:

- A **per-tenant retrieval-augmented generation (RAG) layer** built on a vector database with semantic embeddings and weighted multi-collection search.
- A **fine-tuned Nigeria-specific language model** that handles Pidgin and the major Nigerian languages, including code-switching (e.g. *"Abeg, how much be the latest iPhone wey una get?"*).

These two components are fronted by a thin **conversation orchestrator**, exposed through a **WhatsApp Business API adapter** and an **embeddable web widget**, and managed via an **admin dashboard** for SME owners.

The work is positioned as a Master's research artefact with three deliverables:

| Deliverable | Form |
|---|---|
| **Engineering MVP** | Hosted product running across 3–4 SME pilots in Nigeria |
| **Research evaluation** | Quantitative + qualitative results comparing the platform against generic foundation models on Nigerian-language and code-switching tasks |
| **Thesis manuscript** | Full write-up with methodology, results, ablations, and future work |

---

## 2. Problem Statement

### 2.1 Market context

Nigerian SMEs run customer service almost entirely on WhatsApp and Instagram DMs. Estimates from MSME surveys consistently put WhatsApp adoption among Nigerian small businesses above 85%. The vendor typically:

- Replies on a personal phone, often after-hours.
- Repeats the same answers ("Are you still selling the size-42 boots?", "What's your delivery to Surulere?", "Do you accept transfer?") thousands of times per month.
- Loses customers when reply latency exceeds ~10–15 minutes.

### 2.2 Why generic chatbots don't fit

Existing chatbot platforms (Intercom, Zendesk, generic GPT-4 wrappers) assume:

- Customers will write in standard English.
- The business owner is technical enough to author flow trees, intents, and entities.
- The customer journey will happen on a website, not on WhatsApp.

All three assumptions break in the Nigerian SME context:

- A large fraction of SME customers write in **Pidgin** ("Bros abeg na how much for the cream") or **code-switch** ("How far, you still get the red one?").
- The vendor is rarely technical; they will not author dialogue trees.
- The vendor lives on WhatsApp; a website widget is secondary.

### 2.3 Gap

There is no commercially available chatbot service that simultaneously:

1. Understands and responds correctly in Nigerian Pidgin and the three major Nigerian languages (Yoruba, Hausa, Igbo) at production quality,
2. Handles code-switching gracefully,
3. Is configurable by a non-technical Nigerian SME owner via simple uploads + form fields,
4. Is delivered natively on WhatsApp Business API.

This project closes that gap and quantitatively measures the language-handling improvement that comes from a **Nigeria-specific fine-tune** over generic foundation models.

---

## 3. Research Contribution

The thesis-defensible contributions are:

1. **Nigeria-Specific Fine-Tuned Language Model.** A LoRA / QLoRA fine-tune over an open-weights base (Llama 3.1 / Mistral / InkubaLM family) on a curated Nigerian corpus covering English, Pidgin, Yoruba, Hausa, Igbo, and code-switched utterances. Evaluated against GPT-4o, Claude 3.5, Gemini 1.5, and the un-fine-tuned base on the same prompts.

2. **Per-Tenant RAG over SME Knowledge.** A documented and reproducible architecture for chunking, embedding, and querying SME knowledge with strict tenant isolation, persona-weighted retrieval, and slang/dialect-aware reranking.

3. **End-to-End SME-Facing System.** Validated through real pilots: 3–4 Nigerian SMEs, 4–6 weeks live, with metrics collected on response accuracy, language detection F1, code-switch handling, deflection rate, customer satisfaction, and latency.

4. **Reusable Engineering Patterns.** A modular conversation engine separating language detection, retrieval, generation, escalation, and channel adaptation — published as a thesis appendix and (optionally) as an open-source reference implementation.

The thesis defence story is: *"Generic LLMs miss substantial Nigerian linguistic nuance; a Nigeria-specific fine-tune combined with per-tenant RAG closes that gap by **X%** in measured accuracy and **Y%** in customer-rated naturalness, while remaining commercially viable for SMEs."*

---

## 4. Goals and Non-Goals

### 4.1 Goals (in scope)

- **G1.** Multi-tenant chatbot service with strict per-tenant data isolation.
- **G2.** Knowledge ingestion via file upload (PDF, DOCX, TXT, CSV/Excel) and manual FAQ entry.
- **G3.** WhatsApp Business API channel (primary).
- **G4.** Embeddable web widget channel (secondary).
- **G5.** Admin dashboard for onboarding, knowledge management, persona configuration, conversation review, and basic analytics.
- **G6.** Multilingual support: English, Pidgin, plus **at least one** of Yoruba/Hausa/Igbo at MVP, with the other two at *"early support"* level.
- **G7.** Code-switching handling within a single utterance.
- **G8.** Human handoff on configurable triggers (low confidence, refund > threshold, explicit user request).
- **G9.** Conversation logging, feedback (thumbs up/down), and a feedback loop that improves the knowledge base.
- **G10.** Quantitative + qualitative evaluation suitable for a Master's thesis.

### 4.2 Non-Goals (explicitly out of scope, mention as Future Work)

- Voice channel (IVR, voice-note transcription, voice-note replies).
- Native mobile apps (iOS, Android) — web is sufficient.
- Subscription billing / payments integration (Paystack, Flutterwave, Stripe).
- Role-based access control beyond owner + 1 admin per tenant.
- Outbound marketing / broadcast features (WhatsApp campaign sender).
- Marketplace plugins (Selar, Bumpa, Paystack Storefront, etc.).
- Auto-fine-tuning per tenant from feedback logs.
- Cohort analytics, funnel analysis, retention dashboards.
- Multi-region or HA deployment topology — single-region is acceptable for a thesis MVP.

---

## 5. Personas and Use Cases

### 5.1 Personas

| Persona | Goal | Pain | Tech literacy |
|---|---|---|---|
| **Mama Adaeze** — fashion vendor on Lekki, sells via WhatsApp + Instagram | Reply to "is this still available?", "how much?", "do you deliver to Yaba?" without having to be online 24/7 | She personally answers all messages on her phone; loses sales after 9pm | Low — uses WhatsApp, Instagram, can fill simple forms |
| **Tunde** — owns a small fintech fielding compliance and KYC questions | Deflect repetitive KYC questions to a bot, escalate complex ones to staff | Three-person support team is overwhelmed, high attrition | Medium — uses Notion, Slack, basic Google Sheets |
| **Dr. Bola** — runs a private clinic | Patients ask in Yoruba and English about appointments, hours, prices | Receptionist takes calls she doesn't have time for | Low |
| **Chidi** — restaurant manager | Orders, hours, menu questions in Pidgin and English | Same questions on repeat | Low |
| **Customer (end user)** | Get a fast, correct, Nigerian-sounding answer | Generic chatbots feel American/robotic and don't understand Pidgin | Varies; expects WhatsApp-grade UX |

### 5.2 Use cases

1. **Onboarding.** SME owner signs up, follows a 5-step wizard: business profile → connect WhatsApp → upload knowledge → configure persona → test conversation → go live.
2. **Knowledge upload.** SME drops a 40-page PDF policy doc and a CSV catalogue into the dashboard. The system chunks, embeds, and indexes it within ~2 minutes.
3. **Customer chat (WhatsApp).** Customer sends "Bros abeg the gold-color watch wey I see on your status, e still dey?" The bot replies in matching tone within ~3 seconds, citing a real SKU from the catalogue.
4. **Code-switch handling.** Customer mixes English and Yoruba in one message. The bot detects mixed-language and replies in the dominant language with appropriate code-switch markers.
5. **Escalation.** Customer says "I want refund of ₦80,000". The threshold rule fires; the bot says *"I'm transferring this to my human colleague — please hold on small."* and DMs the SME owner.
6. **Conversation review.** SME owner opens the dashboard, sees flagged conversations, marks 3 answers as wrong, edits the canonical answer. The correction is added to the knowledge base on save.
7. **Analytics.** Owner sees: 142 conversations this week, 81% deflected without human help, top 5 intents, language distribution.

---

## 6. Functional Requirements

### 6.1 Tenant management

- **F1.1** A tenant has: ID, business name, WhatsApp phone number ID, owner email, plan (free / paid — free only for thesis MVP), created_at, status.
- **F1.2** A tenant's data (knowledge chunks, conversations, configs) is isolated. Cross-tenant queries MUST be impossible by construction (per-tenant collection or hard tenant_id filter on every query).
- **F1.3** Sign-up via email + magic link or OAuth (Google).

### 6.2 Knowledge base

- **F2.1** Accept uploads: PDF, DOCX, TXT, CSV, XLSX (≤ 25 MB each, ≤ 200 MB total per tenant for MVP).
- **F2.2** Chunk by semantic boundaries (paragraphs, sections, table rows), target chunk size ~512 tokens with ~50-token overlap.
- **F2.3** Embed each chunk using the configured multilingual embedder; store in tenant's namespace.
- **F2.4** Allow manual FAQ entry: question + canonical answer pair, stored as a special chunk type with higher retrieval weight.
- **F2.5** Allow edit / delete of any chunk.
- **F2.6** Re-embedding triggered automatically on edit; soft-delete supported (mark deleted, exclude from search).

### 6.3 Persona / configuration

- **F3.1** Per-tenant configuration:
  - Display name and tagline
  - Tone preset: `formal`, `casual`, `pidgin_friendly`, `youthful`
  - Supported languages (subset of {EN, PID, YO, HA, IG})
  - Operating hours and timezone (default WAT)
  - Greeting message
  - Out-of-hours message
  - Fallback message ("Sorry, I'm not sure — let me transfer you to a person.")
  - Escalation rules (list of patterns / thresholds)
  - Brand voice examples (3–5 sample utterances)
- **F3.2** Configuration is injected into the system prompt at runtime (no retraining).
- **F3.3** Versioned: every save creates a new revision; rollback supported.

### 6.4 Conversation engine

- **F4.1** Detect input language(s). Support EN, PID, YO, HA, IG, and `mixed`.
- **F4.2** Retrieve top-k relevant knowledge chunks for the query (default k=5, configurable per tenant).
- **F4.3** Call the language model with: tenant config + retrieved chunks + last 5–8 turns of conversation history + the user message.
- **F4.4** Apply post-generation guardrails: profanity filter (mild — Nigerian context is less strict), PII redaction, and a "do not invent prices" rule.
- **F4.5** If retrieval confidence < threshold OR escalation rule fires, return the fallback message and dispatch a human handoff event.
- **F4.6** Persist every turn (input, retrieved chunks, prompt, response, latency, language detected, escalation flag).

### 6.5 Channels

- **F5.1 WhatsApp.** Webhook receiver, message sender, support for: text, images (echo back what was uploaded), location (acknowledge), buttons (for canned escalations), templates (for proactive greetings, optional).
- **F5.2 Web widget.** A single `<script>` tag installs an iframe-based chat widget that is themable to brand colour. Widget supports text, typing indicator, message read receipts.
- **F5.3** Both channels share the same conversation engine — only the adapter differs.

### 6.6 Admin dashboard

- **F6.1** Sign-up + login.
- **F6.2** Five-step onboarding wizard.
- **F6.3** Knowledge manager (upload, list, edit, delete chunks; manual FAQ CRUD).
- **F6.4** Persona configurator.
- **F6.5** Conversation review (list with filters: language, escalated, flagged; per-conversation thread view; mark good/bad; edit canonical answer).
- **F6.6** Analytics (volume per day, deflection rate, top intents, language distribution, P50/P95 latency).
- **F6.7** Settings (WhatsApp connection, web widget snippet, escalation phone/email).

### 6.7 Feedback loop

- **F7.1** Thumbs up/down on every bot reply (visible to staff, optionally to end users).
- **F7.2** Owner-edited canonical answers flow back into the knowledge base as boosted chunks.
- **F7.3** Aggregate feedback exported as a JSONL dataset for offline use (potential future-work fine-tuning).

---

## 7. Non-Functional Requirements

| ID | Requirement | Target |
|---|---|---|
| **NFR-1** | End-to-end latency (text in → text out) | P50 ≤ 3.0s, P95 ≤ 6.0s |
| **NFR-2** | Knowledge ingestion | ≤ 2 min for a 40-page PDF |
| **NFR-3** | Concurrent active conversations per tenant | 50 (MVP), gracefully queue beyond |
| **NFR-4** | Tenant isolation | Hard — cross-tenant data exposure is a P0 bug |
| **NFR-5** | Uptime (MVP target) | 99.0% over the pilot window (≈4 hours downtime per month allowed) |
| **NFR-6** | Data residency | Storage in any region with stable connectivity to Nigeria; document choice in thesis |
| **NFR-7** | Privacy | NDPR-aligned; PII masked in logs; raw uploads encrypted at rest |
| **NFR-8** | Auditability | Every conversation turn traceable with retrieved chunks and the exact prompt sent to the LLM |
| **NFR-9** | Cost ceiling per tenant during pilots | ≤ ₦15,000 / USD 10 per month at expected pilot volumes |

---

## 8. System Architecture (high level)

```
                         ┌─────────────────────────────┐
                         │ End-user channels           │
                         │  • WhatsApp (Business API)  │  ← primary
                         │  • Web widget (JS snippet)  │  ← secondary
                         │  • (future) IG / Messenger  │
                         └──────────────┬──────────────┘
                                        │ webhooks / HTTP
                                        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  Channel Adapter Layer (FastAPI)                    │
│  Normalises every inbound event into a CanonicalMessage             │
│  (tenant_id, channel, sender_id, text, attachments, ts, msg_id)     │
└──────────────────────────────────┬──────────────────────────────────┘
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Conversation Orchestrator                      │
│   1. resolve tenant + load config                                   │
│   2. detect language (EN/PID/YO/HA/IG/mixed)                        │
│   3. fetch conversation history (last N turns)                      │
│   4. RAG: persona-weighted retrieval over tenant's vector namespace │
│   5. build prompt (tenant persona + retrieved chunks + history)     │
│   6. call fine-tuned NG LM                                          │
│   7. apply guardrails (PII / pricing / profanity / escalation)      │
│   8. persist turn, dispatch reply, optionally fire handoff          │
└──┬──────────────────┬──────────────────────────┬───────────────────┘
   │                  │                          │
   ▼                  ▼                          ▼
┌────────────┐ ┌──────────────┐ ┌──────────────────────────────────┐
│ Postgres   │ │ Vector DB    │ │ Fine-tuned NG LM                 │
│ (tenants,  │ │ (per-tenant  │ │ (Llama 3.1 / Mistral / Inkuba    │
│  configs,  │ │  namespace,  │ │  base + LoRA, served via         │
│  history,  │ │  multi-      │ │  vLLM / TGI / HF Endpoint)       │
│  feedback) │ │  collection) │ │                                  │
└────────────┘ └──────────────┘ └──────────────────────────────────┘
                                   │
                                   ▼
                       ┌──────────────────────┐
                       │ Object storage (S3)  │
                       │ raw uploads, audit   │
                       └──────────────────────┘
```

A more detailed component-level architecture, with contracts for each module, is in `01_ARCHITECTURE.md`.

---

## 9. Tech Stack

### 9.1 Backend services

| Layer | Choice | Justification |
|---|---|---|
| Language | **Python 3.11** | Native fit for the LM and ML ecosystem; the team and supervisor are Python-fluent. |
| API framework | **FastAPI** | Async, fast, type-safe via Pydantic, automatic OpenAPI for the dashboard and pilot integrations. |
| LLM client wrapper | Custom thin layer | Centralises retries, backoff, timeouts, model swap. Pattern below in §9.6. |
| Orchestration | **Custom finite-state machine** (not LangGraph for MVP) | Avoids heavy framework lock-in; the orchestration is small enough (~6 steps) to own. LangGraph optional in v2. |
| Background jobs | **Redis + RQ** (or Celery if needed) | Webhook fan-out, ingestion pipelines, daily aggregations. |
| Relational DB | **PostgreSQL 16** | Tenants, configs, conversations, feedback, audit logs. Mature, NDPR-friendly. |
| Vector DB | **Milvus Lite** (file-backed) for MVP, **pgvector** or **Qdrant Cloud** as a production swap | Milvus Lite proves the design in a single binary; pgvector unifies storage + tenancy if Postgres is the base. Decision recorded in §10. |
| Embeddings | **`intfloat/multilingual-e5-large`** (default), **`BAAI/bge-m3`** as a stronger alternative | Both are top-tier multilingual embedders; bge-m3 has dense + sparse + multi-vector modes useful for code-switch. |
| Object storage | **Cloudflare R2** (S3-compatible, cheap, no egress fees) | For raw uploads and audit archives. |
| Cache | **Redis** | Conversation history (24h TTL), retrieval cache (1h TTL), rate-limit counters. |

### 9.2 Language model layer

| Layer | Choice |
|---|---|
| Base model candidates | **Llama 3.1 8B / 70B Instruct**, **Mistral 7B / Mixtral 8×7B**, **Lelapa AI InkubaLM**, **Awarri's Eko / EkoLM**, Masakhane community models |
| Fine-tuning method | **LoRA / QLoRA** on the curated Nigerian corpus |
| Fine-tuning library | **`peft` + `trl`** (HuggingFace) or **`unsloth`** for 2–4× faster iteration on a single GPU |
| Inference serving (production) | **vLLM** on a single A100 / L40S, OR **HuggingFace Inference Endpoints** if budget allows |
| Inference serving (dev / fallback) | Groq (`llama-3.3-70b-versatile`) as a high-throughput hosted fallback for prompt-engineering experiments and the comparative-baseline arm |
| Quantisation | **AWQ** or **GPTQ-int4** on the fine-tuned weights for production GPU memory savings |

A pragmatic two-track strategy: while the fine-tune is being prepared, the orchestrator runs against a hosted general-purpose LLM (Groq + Llama 3.3 70B) so that the rest of the stack can be built and pilot-tested in parallel. The thesis evaluation then swaps in the fine-tune and reports the delta.

### 9.3 Frontend (admin dashboard)

| Layer | Choice |
|---|---|
| Framework | **Next.js 14 (App Router) + TypeScript** |
| UI kit | **Tailwind CSS + shadcn/ui** |
| Auth | **Clerk** or **Auth.js** (DB sessions on Postgres) |
| Charts | **Tremor** (or Recharts) for dashboards |
| State | TanStack Query for server state; minimal local state |
| Web widget | Vanilla TypeScript built with **Vite**, packaged as a single ES module + a 1-line installer script |

### 9.4 Channel integrations

| Channel | Provider |
|---|---|
| **WhatsApp Business API** | **Meta Cloud API** (free, official) for MVP; **360dialog** as a paid option if Meta onboarding stalls |
| Web widget | First-party — no third party |
| Instagram DM / Messenger | (Optional) Meta Graph API — same credentials |

### 9.5 Infrastructure / DevOps

| Concern | Choice |
|---|---|
| Backend hosting | **Render** or **Fly.io** (containerised FastAPI) |
| Frontend hosting | **Vercel** |
| LM hosting | Single GPU VM (RunPod / Lambda Labs / Paperspace) running vLLM, behind a small auth proxy |
| Postgres | **Render Postgres** or **Neon** |
| Vector DB | Milvus Lite (volume-mounted) or **Qdrant Cloud** free tier |
| Object storage | **Cloudflare R2** |
| CI/CD | **GitHub Actions** — test, lint, build, deploy on push to `main` |
| Containerisation | **Docker** with multi-stage builds; one image per service |

### 9.6 Observability

| Concern | Tool |
|---|---|
| LLM tracing | **Langfuse** (self-hosted or cloud free tier) |
| Application errors | **Sentry** |
| Logs | Structured JSON to stdout; aggregated by Render / Fly's built-in log tail or Logfire |
| Metrics | Prometheus exporter on FastAPI; basic Grafana for thesis screenshots |
| Uptime | **UptimeRobot** (free) on the public webhook + dashboard URLs |

A complete component-by-component breakdown lives in `01_ARCHITECTURE.md`. Code-level patterns (LLM client, retrieval service, prompt builder, conversation orchestrator) live in `02_CORE_ENGINE.md`.

---

## 10. Multi-tenancy Strategy

Tenant isolation is a **P0** correctness concern. Three layers enforce it:

### 10.1 Database layer (Postgres)

- Every tenant-owned row has a `tenant_id UUID NOT NULL` column.
- A **row-level security (RLS)** policy is enabled on all tenant tables. The application sets `SET LOCAL app.current_tenant = '<id>'` at the start of every request; RLS enforces `tenant_id = current_setting('app.current_tenant')`.
- Even if application code forgets a `WHERE tenant_id = ?`, RLS makes cross-tenant reads impossible.

### 10.2 Vector DB layer

Two options — pick one in §18:

- **Option A (recommended for MVP):** one collection per tenant, named `kb_<tenant_id>`. Cleanest isolation; trivially correct; minimal extra code.
- **Option B (recommended for scale):** a single shared collection with a `tenant_id` payload field; every query attaches a strict filter. Easier to operate at 1000+ tenants but makes mistakes catastrophic.

**Recommendation for thesis MVP:** Option A. With ≤ 50 tenants in the pilot, the operational cost is negligible and the correctness guarantee is structural rather than procedural.

### 10.3 Object storage layer

- Bucket: `<env>-tenant-uploads` (single bucket).
- Object key: `tenants/<tenant_id>/<file_id>/<original_filename>`.
- Pre-signed URLs are scoped per-key, not per-bucket.
- IAM policy: the application service has read/write only to the `tenants/` prefix; tenants never get raw S3 credentials.

### 10.4 Application layer

- Every request is authenticated; the resolved `tenant_id` is attached to a request-scoped context.
- A FastAPI dependency `get_tenant_context(request)` is the only legitimate way to obtain a tenant ID; direct query-string `tenant_id` parameters are forbidden by lint rule.
- The conversation orchestrator takes `tenant_id` as the first argument of every internal call; functions that do not need it explicitly do not see it.

---

## 11. Tenant Customisation Mechanisms

Customisation works **without retraining the model per tenant**. There are four mechanisms, in order of complexity. SMEs interact only with the first two.

### 11.1 Mechanism 1 — Knowledge ingestion (RAG)

This is how SMEs make the bot *theirs*. They upload:

- Product / service catalogue (CSV or Excel)
- FAQ document (PDF, DOCX, plain text)
- Pricing sheets
- Delivery policies, return policies
- Optional: past customer-service WhatsApp chat logs

The pipeline:

1. Parse and clean (`pypdf`, `python-docx`, `openpyxl`, custom CSV reader).
2. Chunk semantically (~512 tokens, 50 overlap, never split rows).
3. Embed with the multilingual embedder.
4. Insert into the tenant's vector namespace with metadata: `chunk_id`, `document_id`, `document_type`, `section`, `original_text`, `language_hint`, `boost` (default 1.0; manual FAQs get 1.5).
5. Show ingestion status in the dashboard with a per-document progress bar.

### 11.2 Mechanism 2 — Persona / configuration layer

Stored in `tenant_configs` (JSONB column). Injected into the system prompt builder at runtime. **This is purely declarative — no code or ML knowledge required from the SME.** Schema:

```jsonc
{
  "business_name": "Mama Adaeze Boutique",
  "tagline": "Lekki's premium wrappers and gele",
  "tone": "pidgin_friendly",        // formal | casual | pidgin_friendly | youthful
  "languages": ["en", "pid", "yo"],
  "timezone": "Africa/Lagos",
  "operating_hours": { "mon_fri": "09:00-19:00", "sat": "10:00-17:00", "sun": "closed" },
  "greeting": "Hi! Welcome to Mama Adaeze Boutique. How fit help you today?",
  "out_of_hours": "Thanks for reaching out — we're closed for now. We'll reply by 9am.",
  "fallback": "I'm not sure about that one — let me get a human colleague to help.",
  "escalation_rules": [
    { "type": "amount_over", "field": "money", "threshold": 50000, "action": "handoff" },
    { "type": "intent", "intent": "complaint", "action": "handoff" },
    { "type": "phrase", "patterns": ["speak to manager", "human please"], "action": "handoff" }
  ],
  "brand_voice_examples": [
    "Sis, that one don finish for now but I get something even finer in stock",
    "We deliver Lekki same-day, mainland next-day, no wahala"
  ],
  "version": 7
}
```

### 11.3 Mechanism 3 — Feedback loop (semi-automated)

- Owner reviews flagged conversations in the dashboard.
- Marks a reply as good / bad / "not the way I'd say it" and provides an optional correction.
- Corrections become **boosted manual-FAQ chunks** in the tenant's vector namespace and immediately influence subsequent retrievals.
- Aggregated feedback (JSONL) is the dataset for any future per-tenant or platform-level fine-tune (Mechanism 4).

### 11.4 Mechanism 4 — Platform-level fine-tuning (one model, all tenants)

The Nigeria-specific fine-tune is **shared across all tenants**. Per-tenant fine-tuning is intentionally out of scope: it is overkill for SMEs, makes hosting expensive, and breaks RAG-based isolation.

> Position in the thesis: *"We fine-tune **once** on Nigerian languages and discourse patterns; each SME customises via RAG + configuration. This decouples linguistic competence from business knowledge and gives both better economics and clearer evaluation."*

---

## 12. Conversation Lifecycle

A single user turn, end-to-end:

```
1.  Channel adapter receives webhook
        │
        ▼
2.  Resolve tenant from phone-number-id / widget origin
        │
        ▼
3.  Authenticate + dedupe (Meta retries webhooks!)
        │
        ▼
4.  CanonicalMessage emitted
        │
        ▼
5.  Orchestrator picks up:
        │
        ├── 5a. Load tenant config from cache (else Postgres)
        │
        ├── 5b. Load last N turns (Redis, fall through to Postgres)
        │
        ├── 5c. Language detect (FastText langid + heuristics for Pidgin)
        │
        ├── 5d. Persona-weighted RAG over tenant namespace
        │
        ├── 5e. Build prompt (system + retrieved + history + user)
        │
        ├── 5f. Call LM (with retries + 8s timeout)
        │
        ├── 5g. Apply post-generation guardrails
        │
        ├── 5h. Decide: send_reply | escalate | both
        │
        └── 5i. Persist turn + retrieved chunk IDs + latencies
        │
        ▼
6.  Channel adapter sends reply (with typing indicator if supported)
        │
        ▼
7.  Async: Langfuse trace, metrics emit, feedback hook
```

A complete sequence diagram and the corresponding code skeleton are in `02_CORE_ENGINE.md` §3.

---

## 13. Security, Privacy, and Compliance

### 13.1 NDPR alignment (Nigeria Data Protection Regulation)

- **Lawful basis:** legitimate interest of the SME for service delivery + customer consent on first interaction.
- **Data minimisation:** store only message text, sender ID (phone number for WhatsApp), language, and timestamps. No biometric data, no government IDs.
- **Retention:** raw conversation transcripts retained for 90 days by default; tenant can configure a shorter window.
- **Right to erasure:** customer-side request via `/forget me` keyword triggers a hard-delete job for that customer's records across DB and vector store.
- **Data Protection Officer:** the SME is the data controller; the platform is the processor. A standard Data Processing Agreement (DPA) is auto-generated at signup.

### 13.2 PII handling

- A pre-storage redactor masks: BVN, NIN, account numbers, card numbers (Luhn-validated), email addresses (configurable), phone numbers (kept hashed).
- Redaction happens **before** Langfuse tracing, before logs, and before vector storage.
- Raw-text exports are gated behind a separate, audit-logged endpoint.

### 13.3 Authentication

- Dashboard: Clerk-managed OAuth (Google) + email magic link.
- API: JWT Bearer tokens, per-tenant scoped, rotatable.
- Webhooks: Meta WhatsApp signature verification; widget endpoints use a per-tenant `widget_key` plus origin pinning.

### 13.4 Threat model (top items)

| Threat | Mitigation |
|---|---|
| Cross-tenant data exposure | RLS + per-tenant vector collections + dependency-injected `tenant_id` |
| LLM prompt injection from user input | System prompt placed last; user input wrapped in a tagged block; output validated against a small guard model (or regex) for `<system>` echo |
| Webhook replay | Idempotency on `message_id`; signature verification |
| Knowledge-base poisoning by a tenant's own staff | Per-document audit log; rollback supported |
| Cost runaway from a single noisy tenant | Per-tenant rate limits; daily token budget circuit-breaker |

---

## 14. Performance Budget

End-to-end target: **P50 ≤ 3.0 s, P95 ≤ 6.0 s** for a typical text-only query.

| Stage | P50 | P95 |
|---|---|---|
| Inbound webhook → orchestrator dequeue | 50 ms | 200 ms |
| Tenant config + history load | 30 ms | 120 ms |
| Language detect | 5 ms | 20 ms |
| Embedding (query) | 80 ms | 200 ms |
| Vector search (top-7) | 60 ms | 200 ms |
| Prompt build | 5 ms | 20 ms |
| LLM call | 1.8 s | 4.5 s |
| Guardrails | 30 ms | 100 ms |
| Persist + send reply | 200 ms | 700 ms |
| **Total** | **2.3 s** | **6.0 s** |

If the production fine-tune is hosted on vLLM with a quantised 7B/13B variant, the LLM stage usually fits comfortably under 1.5 s on a single A100, and the budget tightens nicely.

---

## 15. Observability and Operations

### 15.1 Logging

- Structured JSON logs, one event per significant step.
- Required fields: `ts`, `tenant_id`, `conversation_id`, `turn_id`, `event`, `latency_ms`, `language_detected`, `retrieval_count`, `model`, `tokens_in`, `tokens_out`, `escalated`.

### 15.2 Tracing

- Langfuse for every LLM call: full prompt, retrieved chunks, response, score (if scored), tags `tenant_id`, `language`, `intent`.

### 15.3 Metrics

- Counters: `messages_total{channel}`, `escalations_total{reason}`, `errors_total{stage}`.
- Histograms: `latency_seconds{stage}`.
- Gauges: `active_tenants`, `tokens_per_min`.

### 15.4 Alerts

- LLM error rate > 2% over 5 min → alert.
- WhatsApp webhook 5xx > 1% over 5 min → alert.
- Daily token spend > configured cap → alert.

### 15.5 Runbooks

A small `/docs/runbooks/` directory with: ingestion failure, LLM downtime, WhatsApp number ban risk, tenant offboarding, knowledge rollback. (Build during pilot phase; it's also a good thesis appendix.)

---

## 16. Cost Model

Rough monthly cost at pilot scale (4 tenants × ~3,000 messages each = 12,000 messages):

| Item | Estimate (USD/mo) |
|---|---|
| Backend hosting (Render / Fly small) | 7 |
| Postgres (Render / Neon free → small) | 0–7 |
| Frontend (Vercel Hobby) | 0 |
| Object storage (R2) | < 1 |
| Vector DB (Milvus Lite on disk → free) | 0 |
| LM hosting — GPU VM 24/7 (RunPod L40S) | 280 |
| LM hosting — alternative: Groq fallback only | < 30 |
| Langfuse cloud / Sentry / UptimeRobot | 0 (free tiers) |
| Domain | 1 |
| **Total (GPU 24/7 baseline)** | **≈ 295** |
| **Total (Groq fallback only baseline)** | **≈ 45** |

A pragmatic two-mode strategy for the pilots:

- **Mode A (cheap):** run the orchestrator against Groq + the un-fine-tuned base for the first half of pilots (gather workload, debug the product), record baseline metrics.
- **Mode B (research):** spin up the GPU VM for the evaluation window — 2–3 weeks — to serve the fine-tuned model and collect the contrastive metrics.

This lets the thesis report both *real-world platform metrics* and *clean head-to-head LM comparisons* without bleeding cash.

---

## 17. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Meta WhatsApp Business API onboarding takes weeks | High | High | Start on day 1; have 360dialog as a paid fallback; build the web widget in parallel so demos are not blocked. |
| Fine-tuning data quality is uneven (especially YO/HA/IG) | Medium | High | Stage the corpus: ship with **EN + Pidgin + 1 other** at MVP; report HA/YO/IG honestly in evaluation. |
| GPU access goes down during pilot | Medium | Medium | Hot-fallback to Groq's hosted model with a feature flag; document the swap in the thesis. |
| SME pilot drop-out (small businesses are busy) | High | Medium | Recruit 6–8 SMEs to keep 3–4 active; run weekly check-ins; offer something tangible (e.g. account credits, a custom onboarding session). |
| Prompt injection or hallucinated prices damage SME reputation | Medium | High | Strict "do not invent prices" rule: prices must come from the knowledge base or the bot must say *"let me confirm"* and escalate. |
| Pidgin is hard to evaluate objectively | High | Medium | Three independent Nigerian-fluent annotators per held-out test set; report inter-annotator agreement (Cohen's κ). |
| Model output sounds like an American doing Pidgin | High | High | Mitigated by the fine-tuning corpus (Nairaland-style discourse, NaijaSenti tweets, real conversational Pidgin pairs); evaluated explicitly in §6 of `05_IMPLEMENTATION_AND_EVAL.md`. |

---

## 18. Assumptions and Open Questions

These should be locked down before sprint 1:

1. **Base LM choice for fine-tuning.** Default: **Llama 3.1 8B Instruct** (open weights, proven LoRA tooling, modest GPU needs). Alternative: **InkubaLM** if its African-language coverage proves stronger on a held-out probe set.
2. **Embedding model.** Default: **`intfloat/multilingual-e5-large`** (1024-dim). Alternative: **`BAAI/bge-m3`**.
3. **Vector DB choice for production.** **Milvus Lite** for MVP / pilots; if going beyond ~10 tenants in production, switch to **pgvector** (unified with Postgres) or **Qdrant Cloud**.
4. **WhatsApp provider.** **Meta Cloud API** primary (free); **360dialog** standby.
5. **Languages at MVP.** **EN + Pidgin + Yoruba** as the GA set; HA + IG as "best-effort" with explicit evaluation caveats.
6. **Hosting region.** Closest stable region to Nigeria with the chosen providers — typically Frankfurt (`eu-central-1`) for Render / Fly.
7. **Pilot recruitment criteria.** Variety: 1 fashion vendor, 1 food/restaurant, 1 fintech / digital service, 1 clinic. Each must do at least 200 customer messages per week pre-pilot.

---

## 19. Companion Documents

This PRD is the master. The deep-dive companions are:

| File | Scope |
|---|---|
| `01_ARCHITECTURE.md` | Component diagrams, module contracts, sequence diagrams, deployment topology |
| `02_CORE_ENGINE.md` | Conversation orchestrator design, RAG service, persona/config loader, prompt builder, language detection — with annotated code patterns |
| `03_CHANNELS_AND_API.md` | WhatsApp adapter, web widget, public REST API specification |
| `04_DATA_MODEL.md` | Postgres schemas, vector collection schemas, file storage layout, cache layout |
| `05_IMPLEMENTATION_AND_EVAL.md` | Six-month sprint plan, evaluation methodology, metrics, baselines, qualitative protocol |

Read in that order for engineering; read `00 → 05 → 02 → 03` for the thesis-writing path.
