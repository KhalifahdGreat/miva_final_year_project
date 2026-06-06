# SME Chatbot — Multilingual Customer-Service Assistant for Nigerian SMEs

> **Master's final-year project (research + product).**
> A multi-tenant chatbot that serves Nigerian SMEs over **WhatsApp Cloud API** and an **embeddable web widget**, with a Nigeria-specific language pipeline (curated 2 M-vector corpus + Pidgin-aware language detection + persona-weighted RAG + grammar-aware prompts) running on top of **Llama 3.3 70B Versatile via Groq**.

This folder contains **all final-year-project code**. It is self-contained and does **not modify** any of the existing `ofofo_engine/` or `milestone_*/` code in the parent project — it only imports `ofofo_engine` as a library to reuse the proven `RetrievalService` and `LLMClient`, and reads the pre-built Milvus vector DB at `../../milestone_two/db/ofofo_vectors.db`.

---

## What this is (in one paragraph)

A Python (FastAPI) backend, a TypeScript embeddable widget, and a Next.js admin dashboard. Each Nigerian SME signs up, connects WhatsApp, uploads their catalogue / FAQs / pricing, configures a tone (formal / casual / pidgin-friendly), and immediately has a bot that replies to their customers in English, Pidgin, and (best-effort) Yoruba — grounded in their own knowledge plus a 2 million-vector Nigerian linguistic corpus.

---

## Repository layout

```
sme_chatbot/
├── README.md                 ← you are here
├── pyproject.toml            ← Python deps
├── docker-compose.yml        ← local Postgres + Redis
├── Makefile                  ← common commands (make dev, make smoke, ...)
├── .env.example              ← copy to .env and fill in
│
├── app/                      ← FastAPI service (the HTTP edge)
│   ├── main.py               ← entry point
│   ├── config.py             ← typed settings from env
│   ├── deps.py               ← FastAPI dependencies (auth, tenant context)
│   ├── db.py                 ← Postgres connection pool
│   └── routers/
│       ├── webhooks.py       ← /webhooks/whatsapp
│       ├── widget.py         ← /widget/v1/*
│       ├── tenants.py        ← admin: tenant CRUD + config
│       ├── documents.py      ← admin: knowledge upload
│       ├── conversations.py  ← admin: review + feedback
│       └── analytics.py      ← admin: dashboard metrics
│
├── core/                     ← Pure-Python engine, no FastAPI imports
│   ├── types.py              ← TenantConfig, CanonicalMessage, Turn, Hit
│   ├── language_detector.py  ← Pidgin-aware langid (thesis sub-contribution)
│   ├── nigerian_prompt_block.py  ← static Pidgin grammar block
│   ├── prompt_builder.py     ← composes system + user prompts
│   ├── guards.py             ← price-hallucination, PII, escalation rules
│   ├── tenant_service.py     ← load/save tenant configs from Postgres
│   ├── ingestion.py          ← file → chunk → embed → upsert
│   └── orchestrator.py       ← single-turn handler (wires it all together)
│
├── adapters/
│   ├── whatsapp.py           ← Meta WhatsApp Cloud API
│   └── widget.py             ← Web widget message handler
│
├── migrations/               ← Alembic migrations
│   └── versions/
│
├── widget/                   ← Vanilla TS embeddable widget (Vite build)
│   ├── package.json
│   ├── vite.config.ts
│   ├── index.html            ← demo host page
│   └── src/
│       ├── main.ts           ← entry point installed by <script> tag
│       └── widget.ts         ← chat UI
│
├── dashboard/                ← Next.js admin dashboard
│   ├── package.json
│   ├── next.config.mjs
│   ├── app/                  ← App-Router pages
│   ├── components/
│   └── lib/
│
├── scripts/                  ← One-off ops scripts
│   └── smoke_test.py         ← end-to-end Pidgin Q&A smoke test
│
└── tests/
    ├── unit/
    └── integration/
```

---

## Reuse from the existing engine

This project **imports** two modules from the parent `ofofo_engine/` package:

| Imported | What it gives us |
|---|---|
| `ofofo_engine.retrieval.RetrievalService` | Milvus Lite client + MiniLM embedder + persona-weighted search |
| `ofofo_engine.llm.LLMClient` | Groq + Llama 3.3 70B client with retries |
| `../../milestone_two/db/ofofo_vectors.db` (file) | 2 M-vector Nigerian corpus (Nairaland, NaijaSenti, slang, news) |

Everything else — multi-tenant config, tenant knowledge collections, language detector, prompt builder, guards, channel adapters, dashboard — is **new code in this folder** and does **not** touch the parent project.

---

## Quick start

### Prerequisites

- Python 3.11+
- Docker + Docker Compose (for local Postgres + Redis)
- A Groq API key (free tier: <https://console.groq.com>)

### Setup

```bash
cd final_year_project/sme_chatbot

cp .env.example .env
# edit .env — at minimum set GROQ_API_KEY

make install         # creates .venv and installs deps
make db-up           # starts Postgres + Redis in Docker
make migrate         # runs Alembic migrations
make smoke           # end-to-end Pidgin Q&A — proves the engine reuse works
make dev             # starts FastAPI on http://localhost:8000
```

The smoke test asks a Pidgin question (`"Bros abeg how much be the gold watch?"`) through the orchestrator, fetches chunks from the existing Nigerian corpus, calls Groq, and prints the reply. If that prints sensible Pidgin output, the entire reuse pattern is working.

### Running the widget (separately)

```bash
cd widget
npm install
npm run dev          # http://localhost:5173 — Vite demo page
```

### Running the dashboard (separately)

```bash
cd dashboard
npm install
npm run dev          # http://localhost:3000
```

---

## Deployment (Render, ≈ $15/month)

A single Render container runs the FastAPI app. The Milvus DB file lives on a persistent disk mounted at `/data/ofofo_vectors.db`. The dashboard deploys to Vercel; the widget bundle is a static asset on Cloudflare Pages or Vercel.

A `render.yaml` and a production `Dockerfile` will be added in Sprint 3 (Phase B).

---

## Six-month roadmap (recap)

See `final_year_project/05_IMPLEMENTATION_AND_EVAL.md` §3 for the full sprint plan. Headline:

| Month | Focus |
|---|---|
| 1 | Productise engine (this scaffold) — multi-tenant Postgres, knowledge upload, orchestrator, smoke test |
| 2 | Channels — WhatsApp Cloud API + embeddable web widget |
| 3 | Dashboard — onboarding, knowledge manager, conversation review, analytics |
| 4 | Pilot recruitment + soft launch (3–4 Nigerian SMEs) |
| 5 | Pilots run; **three ablation studies** executed |
| 6 | Analysis + thesis writing |

---

## Companion docs (in the parent folder)

- [`PROJECT_SCOPE.md`](../PROJECT_SCOPE.md) — the locked thesis scope
- [`00_TECHNICAL_PRD.md`](../00_TECHNICAL_PRD.md) — full product/research PRD
- [`01_ARCHITECTURE.md`](../01_ARCHITECTURE.md) — component diagrams + module contracts
- [`02_CORE_ENGINE.md`](../02_CORE_ENGINE.md) — NLU + RAG + LM deep dive
- [`03_CHANNELS_AND_API.md`](../03_CHANNELS_AND_API.md) — WhatsApp + widget + REST API spec
- [`04_DATA_MODEL.md`](../04_DATA_MODEL.md) — Postgres / vector / storage schemas
- [`05_IMPLEMENTATION_AND_EVAL.md`](../05_IMPLEMENTATION_AND_EVAL.md) — sprint plan + evaluation methodology
- [`Tech_Stack_Decisions.pdf`](../Tech_Stack_Decisions.pdf) — locked tech-stack decisions
