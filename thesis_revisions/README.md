# Thesis revisions package

This folder contains everything needed to bring the draft thesis into
agreement with the implemented codebase in `final_year_project/sme_chatbot/`.

## Contents

| File / folder | What it is |
|---|---|
| `THESIS_REVISIONS.md` | Verbatim replacements for the inaccurate paragraphs in Chapters One and Two, plus a full Chapter Three. Paste sections directly into the thesis. |
| `THESIS_REVISIONS.pdf` | A typeset PDF copy of the above, with the five figures embedded. |
| `figures/` | Five technical diagrams (PNG, 200 DPI). Drop these into the thesis at the marked positions. |
| `generate_figures.py` | The Python script that produces every figure. Re-run with `python3 generate_figures.py` if you want to tweak labels, colours, or layout. |

## The five figures

| # | File | Caption (matches the markdown) |
|---|---|---|
| 3.1 | `figures/fig_3_1_system_architecture.png` | Overall System Architecture — four-tier diagram |
| 3.2 | `figures/fig_3_2_message_lifecycle.png` | Single-Turn Message Lifecycle (Pidgin example) — sequence diagram |
| 3.3 | `figures/fig_3_3_rag_pipeline.png` | Retrieval-Augmented Generation Pipeline — indexing + query paths |
| 3.4 | `figures/fig_3_4_multitenant_isolation.png` | Multi-Tenant Data Isolation across three concurrent tenants |
| 3.5 | `figures/fig_3_5_data_model_erd.png` | Relational Data Model — 13 tables in four functional groups |

## What was changed and why

Five technical claims in the draft did not match what was implemented in
`final_year_project/sme_chatbot/`. The corrections preserve the academic
register of the surrounding text and replace only the inaccurate technical
details:

| In the draft | What was actually built |
|---|---|
| "Nigeria-specific fine-tuned language model" | A Nigerian-language *pipeline* — curated corpus + Pidgin-aware detector + Nigerian prompt block — running over Llama 3.3 70B via Groq. **No fine-tuning.** |
| LangGraph orchestrator | A custom single-turn finite-state machine in `core/orchestrator.py`. |
| BAAI/BGE-M3 embeddings | `sentence-transformers/all-MiniLM-L6-v2` (384-d). The shared 2 M-vector corpus is already encoded with this model. |
| Qdrant primary, pgvector fallback | Milvus Lite (embedded, file-backed) for both the shared corpus and per-tenant collections. |
| Celery task queue | RQ (Redis Queue). |

These corrections are reflected throughout `THESIS_REVISIONS.md` (§A.1 – §A.9).
Chapter Three (Part B) is written from scratch and refers only to the
implemented system.

## Regenerating

```bash
cd final_year_project/thesis_revisions
python3 generate_figures.py     # re-renders all five PNGs into figures/
```

To rebuild the PDF (requires pandoc + a LaTeX engine like xelatex):

```bash
pandoc THESIS_REVISIONS.md \
    -o THESIS_REVISIONS.pdf \
    --pdf-engine=xelatex \
    -V geometry:margin=2cm \
    -V mainfont="DejaVu Sans" \
    -V linkcolor=blue
```
