# Final-Year Project — Technical Documentation Set

**Working title:** Development of an AI-Powered Multilingual Customer Service Chatbot for Nigerian SMEs Using a Nigeria-Specific Language Model

**Owner:** _you_
**Type:** Master's final-year project — combined product + research artefact
**Status:** Source-of-truth specification for build, evaluation, and thesis defence

---

## Documents in this set

Read in order for engineering. For thesis writing, jump from `00 → 05` then back to `02` and `03`.

| # | File | Scope |
|---|---|---|
| 0 | [`PROJECT_SCOPE.md`](./PROJECT_SCOPE.md) | The original scope brief (already in this folder) |
| 1 | [`00_TECHNICAL_PRD.md`](./00_TECHNICAL_PRD.md) | Master product + research PRD: problem, goals, FRs/NFRs, stack, multi-tenancy, security, performance budget, costs, risks, open questions |
| 2 | [`01_ARCHITECTURE.md`](./01_ARCHITECTURE.md) | Component diagrams, module contracts, sequence diagrams, deployment topology, scaling plan, failure modes |
| 3 | [`02_CORE_ENGINE.md`](./02_CORE_ENGINE.md) | The NLU + RAG + LM core: `LMClient`, `RetrievalService`, `PersonaService`, `LanguageDetector`, `PromptBuilder`, `Guardrails`, `ConversationOrchestrator`, fine-tuning recipe — with annotated code |
| 4 | [`03_CHANNELS_AND_API.md`](./03_CHANNELS_AND_API.md) | WhatsApp Business Cloud API, embeddable web widget, public REST API, auth, idempotency, rate-limiting |
| 5 | [`04_DATA_MODEL.md`](./04_DATA_MODEL.md) | PostgreSQL schemas (with row-level security), vector DB schema, object-storage layout, Redis cache, migrations, retention/erasure |
| 6 | [`05_IMPLEMENTATION_AND_EVAL.md`](./05_IMPLEMENTATION_AND_EVAL.md) | Six-month sprint plan, repo layout, definition-of-done per phase, then the full thesis-grade evaluation methodology (research questions, datasets, metrics, baselines, annotation protocol, statistical treatment) |

---

## Reading paths

### "I'm building this — where do I start?"

`00 → 01 → 02 → 04 → 03 → 05`

### "I'm writing the thesis — where do I look?"

- Chapters 1–3 (Intro, Background, Methodology): `00`, then `05 §7–§13`
- Chapter 4 (System): `01`, `02`, `03`, `04`
- Chapter 5 (Implementation): `05 §1–§6`
- Chapter 6 (Evaluation): `05 §9–§13` filled with results
- Chapter 7 (Future Work): `00 §4.2`, `00 §17`

### "I have 10 minutes — what do I read?"

`00_TECHNICAL_PRD.md` §1, §3, §8, §9, §11. Then skim `01 §2`.

---

## What's deliberately NOT in scope (recap)

These are mentioned as **future work** in the thesis — not built:

- Voice channel (IVR, voice-note transcription / synthesis)
- Native mobile apps
- Subscription billing / payments
- Granular RBAC beyond owner + staff
- Outbound campaigns / broadcast
- Marketplace plugins (Selar / Bumpa / Paystack Storefront)
- Auto-fine-tuning per tenant from feedback logs
- Cohort / funnel / retention analytics

See `00 §4.2` for full justification.

---

## Single-sentence summary

> A multi-tenant FastAPI service that exposes a Nigerian-fluent chatbot over WhatsApp Business API and a web widget, where each Nigerian SME tenant customises behaviour via uploaded knowledge (RAG over a per-tenant vector namespace) and a declarative persona config — with a Llama-3.1-based LoRA fine-tune trained on a curated Nigerian corpus (NaijaSenti, MasakhaNEWS, Nairaland, Pidgin pairs) serving as the platform-shared linguistic core, evaluated against GPT-4o / Claude / Gemini and ablations on a 600-turn annotated pilot dataset plus a hand-curated 500-example NigerianBench.
