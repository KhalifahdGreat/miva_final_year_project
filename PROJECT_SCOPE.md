# AI-Powered Multilingual Customer Service Chatbot for Nigerian SMEs

**Project type:** Master's final-year project (product + research)
**Working title:** Development of an AI-Powered Multilingual Customer Service Chatbot for Nigerian SMEs Using a Nigeria-Specific Language Model

---

## 1. Current State (Already Built)

The two **core engine components** are already implemented in the existing project:

1. **Per-tenant Vector DB / Knowledge Base** — SMEs upload their own data (catalog, FAQs, policies) and it is chunked, embedded, and stored for retrieval.
2. **Fine-tuned Nigeria-Specific Language Model** — handles English, Pidgin, Yoruba, Hausa, Igbo, and code-switching between them. This is the research artifact.

Everything below is designed to **build on top of these two components**, not replace them.

---

## 2. Scope Philosophy: Research vs. Product

A Master's thesis on this topic should deliver three layers:

| Layer | Purpose | Status |
|---|---|---|
| **Layer 1 — Core engine** | NLU, multilingual handling, retrieval, generation | Done (Vector DB + Fine-tuned NG LM) |
| **Layer 2 — Integration surface** | How real SMEs actually use it (channels, widgets, plugins) | To build |
| **Layer 3 — Validation** | Pilots with real SMEs, measurable metrics, qualitative feedback | To plan + execute |

**Explicitly out of scope** (mention as Future Work): billing/subscription system, multi-tenant RBAC dashboards, mobile apps, full analytics suites, voice channel.

---

## 3. Question 1 — How far should the "product" side go?

You don't need a commercial SaaS used by hundreds of SMEs. You need a **defensible, working MVP** with evidence it solves a real problem.

### Recommended integration channels (pick 1 primary + 1 secondary)

| Channel | Why it matters for Nigerian SMEs | Recommendation |
|---|---|---|
| **WhatsApp Business API** (via Meta Cloud API, Twilio, or 360dialog) | ~90%+ of Nigerian SMEs already do customer service on WhatsApp. Non-negotiable for real adoption. | **Primary** |
| **Embeddable web widget** (JS snippet) | For SMEs with websites/landing pages. Easy to demo to your panel. | **Secondary** |
| Instagram DMs / Facebook Messenger | Same Meta API stack as WhatsApp — small extra effort if WhatsApp is built. | Optional |
| Telegram | Easy to build, lower SME usage in Nigeria. | Skip |
| Plugins for local platforms (Selar, Bumpa, Paystack checkout, Flutterwave Store) | Nice-to-have. One plugin = one strong thesis chapter. | Optional stretch |

**Final recommendation:** Build **WhatsApp + a web widget**. That alone is a serious product and gives panel-worthy demos.

---

## 4. Question 2 — How would a company "make it theirs"?

This is the **tenant adaptation problem**. Four mechanisms, in order of increasing complexity. SMEs are non-technical, so design around #1 and #2.

### Mechanism 1 — Knowledge-base ingestion via RAG (primary mechanism)
The SME uploads:
- Product catalog (CSV, Excel, scraped from website/Instagram)
- FAQs / policies (PDF, Word, plain text)
- Pricing sheets, delivery zones, return policy
- Past customer-service chat logs (optional, very powerful)

The system chunks → embeds → stores in the **per-tenant Vector DB** (already built) → retrieves at inference.

> This is how 95% of real-world business chatbots are "trained" today. Cheap, fast, updates instantly when the SME edits their catalog. **No ML expertise required from the SME.**

### Mechanism 2 — Configuration / persona layer (no ML required)
A simple admin UI where the owner sets:
- Business name, tagline, tone (formal / casual / Pidgin-friendly)
- Supported languages
- Operating hours, escalation rules (e.g., "if customer asks about refund > ₦50k, hand off to human")
- Greeting and fallback messages
- Brand voice examples

These get injected into the system prompt at runtime.

### Mechanism 3 — Feedback loop / continual improvement (semi-automated)
- SME or staff reviews flagged conversations in a dashboard
- Marks answers as good/bad, provides corrections
- Corrections feed back into the knowledge base or a "preferred answers" cache
- Accumulated feedback can periodically be used for fine-tuning (see #4)

### Mechanism 4 — Fine-tuning the underlying LM (advanced, mostly out of scope per-tenant)
Per-tenant fine-tuning is overkill for SMEs. The fine-tuning you've already done lives at the **platform level** (one Nigerian model serves all tenants). Each company customizes via **RAG + config**, not by retraining.

> Position it as: *"We fine-tune once on Nigerian languages/contexts; each company customizes via RAG + config."*

---

## 5. Target Architecture (build on top of what exists)

```
                    ┌───────────────────────────┐
                    │  WhatsApp Business API    │  ◄── primary channel
                    │  Web Widget (JS snippet)  │  ◄── secondary
                    │  (later: IG / Messenger)  │
                    └─────────────┬─────────────┘
                                  │
                                  ▼
                    ┌───────────────────────────┐
                    │   Channel Adapter Layer   │  (normalizes events)
                    └─────────────┬─────────────┘
                                  ▼
                    ┌───────────────────────────┐
                    │   Language Detector       │  (NG-specific: EN/PID/YO/HA/IG)
                    └─────────────┬─────────────┘
                                  ▼
                    ┌───────────────────────────┐
                    │      Orchestrator         │
                    │  (LangGraph / custom FSM) │
                    └──┬───────────────┬────────┘
                       │               │
                       ▼               ▼
        ┌──────────────────────┐   ┌─────────────────────────┐
        │ Tenant Config +      │   │ Per-tenant Vector DB    │  ✅ DONE
        │ Persona Store        │   │ (knowledge base / RAG)  │
        └──────────────────────┘   └────────────┬────────────┘
                                                ▼
                                   ┌─────────────────────────┐
                                   │ Fine-tuned NG LM         │  ✅ DONE
                                   │ (EN/PID/YO/HA/IG)        │
                                   └────────────┬────────────┘
                                                ▼
                                   ┌─────────────────────────┐
                                   │ Response + Escalation   │
                                   │ (human handoff rules)   │
                                   └────────────┬────────────┘
                                                ▼
                                   ┌─────────────────────────┐
                                   │ Conversation Logs +     │
                                   │ Feedback Dashboard      │
                                   └─────────────────────────┘
```

---

## 6. Suggested Tech Stack

This is a starting point — adjust to match what's already in the existing project.

### Backend
- **Language / framework:** Python (FastAPI) — natural fit since the LM is Python-based
- **Orchestration:** LangGraph or LangChain (or a small custom state machine if you want to avoid heavy deps)
- **Async / queue:** Redis + Celery or RQ (for WhatsApp webhook fan-out)
- **Database:** PostgreSQL (tenants, configs, conversations, feedback)
- **Vector DB:** whatever is already in use (Qdrant / Weaviate / pgvector / Chroma)
- **Embeddings:** multilingual model — `intfloat/multilingual-e5-large`, `BAAI/bge-m3`, or an African-language-tuned embedder if available

### Channel integrations
- **WhatsApp:** Meta Cloud API directly (free, official) or via 360dialog / Twilio (easier onboarding, paid)
- **Web widget:** vanilla JS + a small React build, served as a single `<script>` snippet
- **Instagram / Messenger:** Meta Graph API (same credentials as WhatsApp Cloud API)

### Frontend (admin dashboard for SMEs)
- **Framework:** Next.js (React) + TypeScript
- **UI:** Tailwind + shadcn/ui (clean, fast to build)
- **Auth:** Clerk / Auth.js / Supabase Auth — pick one, don't roll your own
- **Charts:** Recharts or Tremor

### Infra / DevOps
- **Hosting:** Render / Railway / Fly.io for backend; Vercel for frontend (cheap, fast for a thesis)
- **LM hosting:** Hugging Face Inference Endpoints, RunPod, or a single GPU VM (Lambda Labs / Paperspace)
- **Storage:** S3-compatible (Cloudflare R2 is cheapest) for SME-uploaded documents
- **Observability:** Logfire / Langfuse for LLM traces; Sentry for app errors

### Data / fine-tuning (already largely done)
- **Base model candidates** (for reference / discussion in thesis): Llama 3.1, Mistral, Gemma, **Lelapa AI's InkubaLM**, **Awarri's LatAm/EkoLM**, **Masakhane** community models
- **Method:** LoRA / QLoRA fine-tuning
- **Eval:** benchmark against GPT-4o / Claude / Gemini on Nigerian-language and code-switching tasks

---

## 7. What's Left to Build (Roadmap on Top of Existing Engine)

Ordered by priority. Each item is roughly 1–3 weeks of work.

### Phase A — Productize the engine
1. **Tenant model** — multi-tenant data isolation in DB and Vector DB (namespaces / collections per tenant)
2. **Tenant config + persona store** — system prompt builder driven by tenant settings
3. **Knowledge upload pipeline** — file upload → chunk → embed → store in tenant's Vector DB namespace
4. **Conversation orchestrator** — language detect → retrieve → generate → escalate
5. **Conversation logging** — every turn stored for review and metrics

### Phase B — Channel integrations
6. **WhatsApp Business API integration** — webhook receiver, message sender, media handling
7. **Embeddable web widget** — JS snippet, conversation UI, session handling
8. *(Optional)* **Instagram DM / Messenger** — reuse Meta stack

### Phase C — Admin dashboard for SMEs
9. **Onboarding flow** — sign up, connect WhatsApp, upload knowledge base, configure persona
10. **Conversation review UI** — list conversations, mark good/bad, edit responses
11. **Basic analytics** — message volume, deflection rate, top intents, languages used
12. **Knowledge base manager** — CRUD on uploaded documents and FAQ entries

### Phase D — Validation
13. **Recruit 3–4 SME pilots** — variety: fashion vendor, food vendor, fintech startup, clinic
14. **Run pilots for 4–6 weeks**
15. **Collect metrics:**
    - Response accuracy (human-evaluated sample)
    - Language detection accuracy
    - Code-switching handling quality
    - Customer-satisfaction proxy (thumbs up/down, CSAT survey)
    - Deflection rate (% of queries resolved without human)
    - Latency (P50, P95)
16. **Qualitative interviews** with SME owners
17. **Write up results** in thesis

---

## 8. Validation & Evaluation Plan

### Quantitative metrics
- **Language detection F1** across EN / Pidgin / YO / HA / IG
- **Code-switching handling** — accuracy on a held-out test set with mixed-language utterances
- **Retrieval quality** — top-k recall on a labeled SME-FAQ test set
- **End-to-end answer quality** — human eval on a Likert scale (helpfulness, correctness, tone)
- **Deflection rate** — fraction of conversations resolved without human handoff
- **Latency** — P50 and P95 response time per channel

### Comparative baselines
- GPT-4o / Claude 3.5 / Gemini 1.5 (closed-source generalists)
- Base Llama 3.1 / Mistral without your fine-tuning (to show the fine-tune adds value)
- A non-RAG version of your system (to show RAG adds value)

### Qualitative
- SME owner interviews (ease of setup, trust, willingness to pay, perceived accuracy)
- Customer interviews (did the bot feel "Nigerian"? Did it understand Pidgin?)

---

## 9. Realistic 6-Month Timeline

| Month | Focus | Deliverables |
|---|---|---|
| 1 | Productize engine (Phase A) | Multi-tenant DB, tenant config, knowledge upload pipeline, orchestrator |
| 2 | WhatsApp + web widget (Phase B) | Working bot on WhatsApp + a demo site with the widget |
| 3 | Admin dashboard (Phase C) | SME can self-onboard, upload knowledge, configure persona, view conversations |
| 4 | Pilot recruitment + soft launch | 3–4 SMEs onboarded, bot live in their channels |
| 5 | Pilots running + metrics collection | 4–6 weeks of real conversations logged |
| 6 | Analysis + thesis writing | Final eval, comparative baselines, write-up, defense prep |

---

## 10. Open Questions to Resolve Next

Before deeper tech-stack decisions, lock these down:

1. Which **fine-tuning base model** is currently used? (Affects hosting cost and licensing.)
2. Which **Vector DB** is currently in use? (Affects multi-tenancy strategy.)
3. Which **embedding model** is currently used? (Must be the same at ingest and query time.)
4. Is there an existing **API surface** around the engine, or is it called directly in code today?
5. **Hosting budget / GPU access** — self-hosted GPU, HF Inference Endpoint, or RunPod?
6. Which **WhatsApp provider** — Meta Cloud API (free, more setup) or 360dialog/Twilio (paid, easier)?
7. How many **languages to support at MVP** — recommend EN + Pidgin + 1 of (YO/HA/IG) for v1.

---

## 11. Cut From Scope (Future Work in Thesis)

Mention these explicitly in your thesis to show you understand the broader product space without being expected to build them:

- Subscription billing and payments (Paystack / Flutterwave integration)
- Role-based access control for SME teams
- Native mobile apps (iOS/Android) — web is enough
- Voice channel (IVR, voice notes transcription) — large undertaking
- Outbound marketing / broadcast features
- Advanced analytics (cohort analysis, funnel, retention)
- Auto-fine-tuning per tenant from feedback logs
- Marketplace plugins for Selar / Bumpa / Paystack / Flutterwave Store

---

## 12. Summary

- **Engine (Vector DB + Fine-tuned NG LM) is done** — that's your research core.
- **Build on top:** multi-tenant productization → WhatsApp + web widget → admin dashboard → pilots.
- **Customers customize via RAG + config**, not retraining.
- **Validate with 3–4 real Nigerian SME pilots** and quantitative + qualitative metrics.
- **Cut aggressively** — billing, mobile apps, voice, plugins all go in Future Work.
