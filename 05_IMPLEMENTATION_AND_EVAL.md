# Implementation Plan and Evaluation Methodology

This is the operational document — the *"what to do every week, and how to prove it works"* companion to the product and architecture specs. Two halves:

1. **Implementation Plan.** A six-month sprint plan covering Phases A–D from the project scope.
2. **Evaluation Methodology.** The thesis-grade evaluation: metrics, baselines, datasets, annotation protocol, statistical treatment.

---

## Table of Contents

### Implementation Plan

1. [Project Layout](#1-project-layout)
2. [Tooling and Local Setup](#2-tooling-and-local-setup)
3. [Six-Month Roadmap](#3-six-month-roadmap)
4. [Definition of Done — per Phase](#4-definition-of-done--per-phase)
5. [Engineering Practices](#5-engineering-practices)
6. [Risk-Adjusted Scope Cuts](#6-risk-adjusted-scope-cuts)

### Evaluation Methodology

7. [Research Questions](#7-research-questions)
8. [Datasets](#8-datasets)
9. [Quantitative Metrics](#9-quantitative-metrics)
10. [Baselines](#10-baselines)
11. [Human Evaluation Protocol](#11-human-evaluation-protocol)
12. [Pilot Study Design](#12-pilot-study-design)
13. [Statistical Treatment](#13-statistical-treatment)
14. [Reporting in the Thesis](#14-reporting-in-the-thesis)

---

## 1. Project Layout

```
naija_sme_assistant/
├── README.md
├── pyproject.toml
├── docker-compose.yml
├── docker-compose.gpu.yml
├── .env.example
├── apps/
│   ├── api/                       # FastAPI service
│   │   ├── main.py
│   │   ├── deps.py                # FastAPI dependencies (auth, tenant context)
│   │   ├── routers/
│   │   │   ├── auth.py
│   │   │   ├── tenants.py
│   │   │   ├── documents.py
│   │   │   ├── conversations.py
│   │   │   ├── analytics.py
│   │   │   ├── channels.py
│   │   │   ├── widget.py          # /widget/v1/*
│   │   │   └── webhooks.py        # /webhooks/whatsapp
│   │   └── schemas/                # Pydantic models for I/O
│   ├── worker/
│   │   ├── main.py                 # RQ worker bootstrap
│   │   └── jobs/
│   │       ├── ingest.py
│   │       ├── reembed.py
│   │       ├── promote_feedback.py
│   │       └── aggregate_analytics.py
│   ├── widget/                     # Vite + TS web widget
│   │   ├── src/
│   │   ├── public/
│   │   └── vite.config.ts
│   └── dashboard/                  # Next.js admin app
│       ├── app/
│       ├── components/
│       └── lib/
├── core/                           # The engine — pure Python, no FastAPI imports
│   ├── lm_client.py
│   ├── retrieval.py
│   ├── persona.py
│   ├── language.py
│   ├── prompt_builder.py
│   ├── guards.py
│   ├── orchestrator.py
│   ├── history.py
│   ├── audit.py
│   ├── ingestion.py
│   └── adapters/
│       ├── whatsapp.py
│       └── widget.py
├── infra/
│   ├── postgres/
│   │   └── init.sql
│   ├── milvus/
│   ├── nginx/
│   └── runpod/
│       └── start_vllm.sh
├── migrations/                     # Alembic
│   └── postgres/
├── ml/
│   ├── data/                       # cleaned corpora (DO NOT COMMIT raw)
│   ├── recipes/
│   │   ├── train_lora.py
│   │   ├── eval_bench.py
│   │   └── make_dataset.py
│   └── README.md
├── eval/
│   ├── benchmarks/
│   │   ├── nigerianbench.jsonl    # see §8.2
│   │   ├── codeswitch.jsonl
│   │   └── faq_test_set.jsonl
│   ├── runners/
│   │   ├── run_baselines.py
│   │   └── run_pilot_replay.py
│   └── results/
└── tests/
    ├── unit/
    ├── integration/
    └── load/
```

The `core/` package is **pure Python with no FastAPI imports**. This makes it easy to call from a Jupyter notebook for evaluation, from a CLI, or from the worker — and it makes unit testing trivial.

---

## 2. Tooling and Local Setup

### 2.1 Required tools

| Tool | Version |
|---|---|
| Python | 3.11+ |
| Node | 20+ |
| Docker + Docker Compose | – |
| `uv` (or `pip-tools`) | latest |
| `make` | – |

### 2.2 `pyproject.toml` (excerpt)

```toml
[project]
name = "naija-sme-assistant"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi==0.115.*",
    "uvicorn[standard]==0.30.*",
    "gunicorn==23.*",
    "pydantic==2.*",
    "psycopg[binary,pool]==3.2.*",
    "alembic==1.13.*",
    "redis==5.*",
    "rq==1.16.*",
    "pymilvus==2.4.*",
    "sentence-transformers==3.*",
    "openai==1.*",
    "groq==0.11.*",
    "huggingface-hub>=0.24",
    "langfuse==2.*",
    "sentry-sdk[fastapi]==2.*",
    "boto3==1.34.*",                    # for R2 (S3-compatible)
    "pypdf==4.*",
    "python-docx==1.*",
    "openpyxl==3.*",
    "pandas==2.*",
    "fasttext-langdetect==1.*",
    "python-dotenv==1.*",
    "tenacity==8.*",
    "structlog==24.*",
]

[project.optional-dependencies]
dev = [
    "ruff==0.6.*",
    "pytest==8.*",
    "pytest-asyncio==0.23.*",
    "pytest-cov==5.*",
    "mypy==1.*",
    "freezegun==1.*",
]
ml = [
    "transformers==4.*",
    "datasets==3.*",
    "accelerate==1.*",
    "peft==0.13.*",
    "trl==0.11.*",
    "unsloth==2024.*",
    "wandb==0.18.*",
]
```

### 2.3 `Makefile`

```makefile
.PHONY: dev migrate test fmt lint typecheck eval

dev:
	docker compose up -d postgres redis milvus
	uv run uvicorn apps.api.main:app --reload --port 8000

migrate:
	uv run alembic upgrade head

test:
	uv run pytest tests/ -q

fmt:
	uv run ruff format .

lint:
	uv run ruff check .

typecheck:
	uv run mypy core apps

eval:
	uv run python eval/runners/run_baselines.py --suite nigerianbench
```

---

## 3. Six-Month Roadmap

The roadmap is structured around the four phases from `00_TECHNICAL_PRD.md`. Each sprint is two weeks; total of 13 sprints in six months.

### Month 1 — Phase A: Productize the engine

#### Sprint 1 (weeks 1–2)

- Repo scaffolding, Docker Compose for Postgres + Redis + Milvus.
- Postgres schema (§04 — tenants, users, configs, documents, turns).
- Alembic migration `001_initial`.
- `core/lm_client.py` with all three providers; integration test against Groq.
- `core/retrieval.py` against Milvus Lite; unit tests with synthetic data.
- `LanguageDetector` with Pidgin overrides; unit-test on a 200-utterance fixture.

#### Sprint 2 (weeks 3–4)

- `PersonaService` with versioning + cache.
- `PromptBuilder` with all four tone presets and the Pidgin grammar block.
- `Guardrails` with price-hallucination and PII checks.
- `ConversationOrchestrator` end-to-end against a stub channel.
- Audit table + `AuditWriter`.
- Worker scaffolding (RQ + Redis).
- Ingestion pipeline for PDF / DOCX / CSV / XLSX / TXT (no manual FAQ yet).

### Month 2 — Phase B: Channel integrations

#### Sprint 3 (weeks 5–6)

- WhatsApp Cloud API integration end-to-end (Tech Provider account, Embedded Signup).
- Inbound webhook with idempotency.
- Outbound `send_reply`.
- Status callbacks → `turns.outbound_status`.
- Manual smoke test: send a Pidgin message, get a Pidgin reply.

#### Sprint 4 (weeks 7–8)

- Web widget (Vite + TS), single-script installer.
- `/widget/v1/*` endpoints.
- Origin pinning, session tokens.
- Demo-site harness for the panel.

### Month 3 — Phase C: Admin dashboard

#### Sprint 5 (weeks 9–10)

- Next.js scaffolding, Clerk auth, tenant context.
- Onboarding wizard (5 steps).
- Tenant profile + persona configurator UI.
- Knowledge upload UI with progress bars.

#### Sprint 6 (weeks 11–12)

- Manual FAQ CRUD.
- Conversation review (list + detail, filters, mark good/bad, edit canonical answer).
- Basic analytics (volume, deflection, language distribution, latency).
- Settings (WhatsApp connect status, widget snippet, escalation contact).
- End-to-end smoke: a fresh tenant onboards, uploads, configures, and chats — all from the UI.

### Month 4 — Phase D entry: pilots and fine-tune

#### Sprint 7 (weeks 13–14)

- Recruit 6–8 Nigerian SMEs (target 4 active pilots).
- Pre-pilot interviews to capture: existing FAQ docs, common queries, languages used, SLAs.
- Build the **fine-tuning corpus** in parallel:
  - Curate NaijaSenti, MasakhaNEWS, Nairaland, Pidgin pairs.
  - Generate synthetic SME Q/A from sample catalogues, filter with Nigerian annotators.
  - Format as chat-style instruction JSONL.
- Provision the GPU VM (RunPod L40S or A100); set up vLLM and the training environment.

#### Sprint 8 (weeks 15–16)

- Run **LoRA fine-tune** on Llama 3.1 8B (and optionally InkubaLM as a comparator).
- Internal eval on the held-out 5% + the curated NigerianBench (§8.2).
- Decide which fine-tune ships to pilots.
- Deploy fine-tune to vLLM; switch the orchestrator's `LMClient` provider to `vllm-local` via a feature flag.
- Onboard the first 2 pilots in Mode A (Groq baseline) for the first 2 weeks.

### Month 5 — Pilots running

#### Sprint 9 (weeks 17–18)

- Onboard remaining pilots.
- Switch all pilots to Mode B (fine-tuned model).
- Daily monitoring: dashboards, Langfuse traces, error rates.
- Weekly check-ins with each SME owner.
- Collect WhatsApp-only data for at least 2 weeks per pilot.

#### Sprint 10 (weeks 19–20)

- Continue pilots.
- Address any production issues (rate-limit, latency spikes, auth refresh).
- Begin **annotated grading** of randomly sampled turns (§11).
- Halfway pulse: SME owner satisfaction survey 1 of 2.

### Month 6 — Analysis and write-up

#### Sprint 11 (weeks 21–22)

- Close pilots; second SME satisfaction survey.
- Final annotation pass on sampled turns (target ≥ 600 turns scored).
- Run the **comparative evaluation** suite: same prompts through GPT-4o, Claude 3.5 Sonnet, Gemini 1.5 Pro, base Llama 3.1 (no fine-tune), and the fine-tuned model.
- Compute all metrics in §9.

#### Sprint 12 (weeks 23–24)

- Draft thesis chapters 1–3 (Introduction, Background, Methodology) — earlier than this if feasible.
- Draft chapter 4 (System) using `00`–`04`.
- Draft chapter 5 (Evaluation) using results from §9–§13.

#### Sprint 13 (weeks 25–26)

- Draft chapter 6 (Discussion), chapter 7 (Future Work), abstract.
- Internal review with supervisor.
- Defence prep: 30-minute talk, 2-minute demo, 4–6 representative pilot screenshots, 3 redacted conversation transcripts (with consent).

---

## 4. Definition of Done — per Phase

### Phase A (engine productised)

- [ ] All 11 module contracts (`01_ARCHITECTURE.md` §3) implemented.
- [ ] Multi-tenant DB with RLS verified by an integration test that **expects 403** on cross-tenant access.
- [ ] Vector DB collection-creation idempotent.
- [ ] One full conversation turn against a stub channel in < 3.5s P50 on a laptop.
- [ ] Audit record written for every turn.
- [ ] ≥ 70% line coverage on `core/`.

### Phase B (channels)

- [ ] WhatsApp inbound + outbound on at least one test number.
- [ ] Widget installs from a one-line snippet on a static demo site.
- [ ] Origin pinning rejects a wrong origin in an integration test.
- [ ] Idempotent on Meta retries.

### Phase C (dashboard)

- [ ] An owner can: sign up → connect WhatsApp → upload a 40-page PDF → configure persona → see ≥ 3 conversations come through → review and mark them.
- [ ] Knowledge re-embedding triggered on edit and visible in search within 60s.
- [ ] Analytics page shows non-zero numbers after the smoke test.

### Phase D (pilots & evaluation)

- [ ] ≥ 3 SMEs ran the bot in production for ≥ 4 weeks.
- [ ] ≥ 600 annotated turns across pilots.
- [ ] Comparative metrics computed against ≥ 3 baselines.
- [ ] All §9 metrics tabulated with confidence intervals.

---

## 5. Engineering Practices

- **Trunk-based development** with short-lived branches; PR review required.
- **CI** runs lint (`ruff`), type-check (`mypy`), unit + integration tests, and a smoke run of the orchestrator on a tiny test corpus.
- **Pre-commit hooks** for `ruff format`, `ruff check`, `mypy --strict` on `core/`.
- **Observability from day 1.** Langfuse traces every LLM call from sprint 1.
- **Feature flags** for model swaps (`provider=vllm-local | groq`), guardrail toggles (`enforce_price_check`), and Pidgin-block injection. Implemented as simple env vars (or LaunchDarkly / Unleash if budget allows).
- **Migrations are forward-compatible.** Never break the API of `core/` mid-pilot — add new fields as optional, deprecate slowly.

---

## 6. Risk-Adjusted Scope Cuts

If anything slips, the cut order is:

1. **Drop Yoruba / Hausa / Igbo from MVP languages.** Keep EN + Pidgin only. Document in evaluation; report YO/HA/IG as future work.
2. **Drop the Next.js dashboard's analytics page.** Replace with a Streamlit / Retool internal-only view for the thesis demo.
3. **Drop manual-FAQ editing.** Keep only file uploads.
4. **Drop the dual-base-model fine-tune (InkubaLM).** Keep Llama 3.1 only.
5. **Drop the web widget.** Demo only on WhatsApp.
6. **Drop one pilot.** Run with 3 instead of 4.

The Pidgin grammar layer, the per-tenant RAG, the WhatsApp adapter, and the evaluation framework are **never cut** — they are the thesis.

---

# Evaluation Methodology

## 7. Research Questions

The evaluation answers four research questions:

- **RQ1.** Does a Nigeria-specific fine-tune produce statistically significantly higher human-rated answer quality than a generic foundation model on Nigerian SME customer-service queries?
- **RQ2.** What is the language-detection F1 for Nigerian Pidgin (and the three major Nigerian languages) achieved by the system, compared to off-the-shelf langid?
- **RQ3.** Does code-switching within a single utterance degrade answer quality, and by how much?
- **RQ4.** Does per-tenant RAG meaningfully improve grounded-correctness over a no-RAG baseline using the same model?

Each RQ corresponds to a metric and a comparative baseline below.

---

## 8. Datasets

### 8.1 Pilot dataset (real)

- **Source:** all conversation turns logged from the 3–4 SME pilots over 4–6 weeks.
- **Volume target:** ≥ 4,000 turns aggregated.
- **Sampling for annotation:** stratified random sample of 600 turns, balanced by language (EN / PID / mixed) and by tenant.

### 8.2 NigerianBench (held-out test set)

A hand-curated 500-example evaluation set authored by the project lead with three Nigerian-fluent annotators. Each example is a tuple:

```jsonc
{
  "id": "nb_0001",
  "tenant_profile": "fashion_vendor_lekki",
  "knowledge_excerpt": "<a small relevant excerpt from a synthetic SME catalogue>",
  "language": "pid",                  // 'en' | 'pid' | 'yo' | 'ha' | 'ig' | 'mixed'
  "user_message": "Bros, the gold-color watch wey I see for your status, e still dey?",
  "reference_answer": "<an ideal reply, agreed by all three annotators>",
  "must_contain": ["gold", "yes" | "available" | "still get"],
  "must_not_contain": ["price"],      // because no price was given in the excerpt
  "register": "casual_pidgin"
}
```

Distribution:

| Slice | Count |
|---|---|
| English | 150 |
| Pidgin | 150 |
| Code-switched (EN+PID) | 100 |
| Yoruba | 40 |
| Hausa | 30 |
| Igbo | 30 |

### 8.3 Code-switch test set

A 200-example subset of NigerianBench specifically containing within-utterance language switches, with ground-truth language labels at the token level for the language-detector evaluation.

### 8.4 FAQ retrieval test set

For each pilot: 50 queries with the ground-truth canonical chunk identified. Used for top-k recall evaluation of the retrieval service.

---

## 9. Quantitative Metrics

| ID | Metric | Definition | Target |
|---|---|---|---|
| **M1** | End-to-end answer quality | Mean Likert (1–5) over 3 Nigerian annotators on the 600-turn sample, dimensions: helpfulness, correctness, naturalness | ≥ 4.0 mean overall, ≥ 3.5 on each dimension |
| **M2** | Pairwise win rate vs GPT-4o | Annotators choose better-of-two; bot vs GPT-4o on same prompts | ≥ 0.45 (within range, not strictly winning) |
| **M3** | Pairwise win rate vs base Llama 3.1 (un-fine-tuned) | – | ≥ 0.65 |
| **M4** | Pairwise win rate vs no-RAG version | – | ≥ 0.65 |
| **M5** | Language detection F1 | macro-F1 over {en, pid, yo, ha, ig, mixed} on the code-switch set | ≥ 0.85 |
| **M6** | Pidgin-detection F1 specifically | precision + recall on Pidgin utterances | ≥ 0.90 |
| **M7** | Code-switch handling accuracy | Fraction of code-switched messages where the reply is in the dominant language and naturally handles the secondary | ≥ 0.75 |
| **M8** | Retrieval top-5 recall | On the FAQ retrieval test set | ≥ 0.85 |
| **M9** | Deflection rate | Fraction of conversations that end without escalation in pilot data | ≥ 0.65 |
| **M10** | Hallucination rate | Fraction of replies containing claims not supported by retrieved chunks (annotator-judged) | ≤ 0.05 |
| **M11** | Price-hallucination incidents | Count of prices invented (caught by guardrail or annotator) | 0 (after guardrail) |
| **M12** | End-to-end latency P50 | – | ≤ 3.0s |
| **M13** | End-to-end latency P95 | – | ≤ 6.0s |
| **M14** | Customer-rated NPS proxy | thumbs-up rate among labelled feedback | ≥ 0.7 |

Each is reported with a 95% bootstrap confidence interval.

---

## 10. Baselines

For every applicable metric, run the same prompt through every baseline:

1. **B1.** Fine-tuned Nigeria-specific model (the system).
2. **B2.** Same fine-tune, **no RAG** — RAG ablation.
3. **B3.** Base Llama 3.1 8B Instruct, no fine-tune, with same RAG — fine-tune ablation.
4. **B4.** GPT-4o (commercial generalist) with same RAG.
5. **B5.** Claude 3.5 Sonnet with same RAG.
6. **B6.** Gemini 1.5 Pro with same RAG.

(B5 and B6 may be dropped if API budget is tight; report only those run, transparently.)

A single script in `eval/runners/run_baselines.py` iterates over each test item and emits a JSONL with one row per (item, baseline). Annotators grade in a tool that randomises baseline order to prevent ordering bias.

---

## 11. Human Evaluation Protocol

### 11.1 Annotators

- Three independent Nigerian-fluent annotators per item.
- Recruited via university channels or a paid platform; balanced by language fluency: at least one fluent in YO, one in HA, one in IG.
- Each annotator completes a short calibration set (15 examples) with discussion before the main pass to align on rubric.

### 11.2 Rubric

Each reply is graded on three dimensions:

| Dimension | Anchor 1 | Anchor 5 |
|---|---|---|
| **Helpfulness** | Doesn't answer the question | Fully addresses the question with the right info |
| **Correctness** | Contains factually wrong / invented info | All claims supported by the knowledge excerpt |
| **Naturalness** | Sounds like a textbook / American doing Pidgin | Sounds like a Nigerian shopkeeper or agent |

Plus three binary flags: `pidgin_grammatical_yes_no`, `code_switch_handled_yes_no`, `escalation_correct_yes_no` (only when applicable).

### 11.3 Tool

A small annotation app (Streamlit / Label Studio / Argilla) that:

- Shows the user message + knowledge excerpt + the reply (baseline name hidden).
- Captures Likert scores and the binary flags.
- Captures freeform notes for borderline cases.
- Exports JSONL.

### 11.4 Inter-annotator agreement

Reported per dimension:

- Cohen's κ (pairwise) for binary flags.
- Krippendorff's α for ordinal Likert.
- Discrepancies > 2 Likert points are arbitrated by the project lead.

---

## 12. Pilot Study Design

### 12.1 Recruitment

Target 6–8 Nigerian SMEs to keep 3–4 active. Variety:

- 1 fashion vendor (high volume, casual register, Pidgin common).
- 1 food / restaurant.
- 1 fintech / digital service (more formal English).
- 1 clinic (mixed register, polite tone, sensitive content).

Selection criteria:

- ≥ 200 customer messages per week pre-pilot.
- Willing to grant a Data Processing Agreement.
- WhatsApp Business is their primary channel.

Compensation: free service during the pilot + a small token (e.g. ₦25,000 / USD 15 voucher) on completion.

### 12.2 Onboarding

A short structured intake captures: business name, top 20 customer questions, current FAQ docs, supported languages, hours, escalation contact.

### 12.3 Pre-/post-pilot interviews

Semi-structured, 30 minutes each, with the SME owner:

- Pre-pilot: pain points, expectations, any prior chatbot exposure.
- Post-pilot: trust, perceived quality, what they'd pay, what they'd change, top 3 wins, top 3 frustrations.

Recordings transcribed and thematic-coded for the qualitative chapter.

### 12.4 Customer survey

A short in-bot survey at the end of selected conversations: *"How was that interaction? 👍 / 😐 / 👎"*. Samples taken across the pilot window.

### 12.5 Rollback plan

If a pilot tenant's bot misbehaves badly (> 2% hallucination rate observed), pull the bot from production, share findings with the SME, and re-run after fixes. This is recorded in the thesis's risk-management appendix.

---

## 13. Statistical Treatment

- Each metric reported with **95% bootstrap CI** (1000 resamples).
- Pairwise comparisons (M2, M3, M4) reported as win/tie/loss with **McNemar's test** p-values.
- Mean Likert differences across baselines tested with **Wilcoxon signed-rank** (non-parametric, paired).
- Multiple-comparison correction: **Benjamini–Hochberg** at FDR 0.05 across all reported tests.
- Effect sizes reported alongside p-values (Cliff's δ for ordinal, Cohen's d for parametric where applicable).
- Pre-register the analysis plan before opening the annotation results to avoid post-hoc cherry-picking.

---

## 14. Reporting in the Thesis

The thesis chapter structure aligns with these documents:

| Thesis chapter | Source documents |
|---|---|
| 1. Introduction | `00 §1, §2, §3` |
| 2. Background and Related Work | new content; Nigerian NLP landscape, multilingual LMs, RAG, SME chatbot deployments |
| 3. Methodology | `02 §10` (fine-tuning), `04` (data model), `05 §7–§13` (evaluation) |
| 4. System Design | `00 §5–§13`, `01`, `02`, `03`, `04` |
| 5. Implementation | `05 §1–§6` |
| 6. Evaluation Results | `05 §9–§13` filled with actual numbers |
| 7. Discussion and Future Work | `00 §17`, `00 §4.2`, lessons from pilots |
| Appendix A | NigerianBench examples |
| Appendix B | Annotator rubric and calibration set |
| Appendix C | Module contracts and code listings |
| Appendix D | Pilot DPA, ethics approval |

A clean, defensible Master's dissertation falls naturally out of executing this plan honestly.
