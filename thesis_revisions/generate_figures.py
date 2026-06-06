"""Generate technical figures for the thesis.

Run from this folder:
    python3 generate_figures.py

Produces five PNGs into ./figures/, each sized for an A4 thesis page.

Figures:
    fig_3_1_system_architecture.png    — high-level system architecture
    fig_3_2_message_lifecycle.png      — end-to-end inbound message sequence
    fig_3_3_rag_pipeline.png           — RAG indexing + retrieval pipeline
    fig_3_4_multitenant_isolation.png  — per-tenant isolation across stores
    fig_3_5_data_model_erd.png         — relational entity diagram
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from pathlib import Path

OUT = Path(__file__).resolve().parent / "figures"
OUT.mkdir(exist_ok=True)

# Palette — deliberately monochrome+blue, prints well in greyscale.
NAVY = "#1f3a5f"
BLUE = "#4f7cac"
TEAL = "#2e8b8b"
ORANGE = "#d97706"
GREEN = "#16a34a"
LIGHT = "#eef2f7"
GREY = "#6b7280"
DARK = "#0f172a"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 9,
    "axes.titleweight": "bold",
})


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------


def box(ax, x, y, w, h, label, sub="", *, fill=LIGHT, edge=NAVY, fontsize=9, textcolor=DARK):
    """Rounded rectangle with a title and optional subtitle."""
    patch = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.02,rounding_size=0.08",
        linewidth=1.4,
        edgecolor=edge,
        facecolor=fill,
    )
    ax.add_patch(patch)
    if sub:
        ax.text(x + w / 2, y + h * 0.62, label,
                ha="center", va="center", fontsize=fontsize, weight="bold", color=textcolor)
        ax.text(x + w / 2, y + h * 0.28, sub,
                ha="center", va="center", fontsize=fontsize - 1.5, color=GREY)
    else:
        ax.text(x + w / 2, y + h / 2, label,
                ha="center", va="center", fontsize=fontsize, weight="bold", color=textcolor)


def arrow(ax, x1, y1, x2, y2, *, label="", color=NAVY, style="-|>", curve=0.0, label_offset=(0, 0.1)):
    """Curved arrow with optional inline label."""
    arr = FancyArrowPatch(
        (x1, y1), (x2, y2),
        arrowstyle=style,
        mutation_scale=12,
        linewidth=1.2,
        color=color,
        connectionstyle=f"arc3,rad={curve}",
    )
    ax.add_patch(arr)
    if label:
        midx = (x1 + x2) / 2 + label_offset[0]
        midy = (y1 + y2) / 2 + label_offset[1]
        ax.text(midx, midy, label, ha="center", va="center",
                fontsize=7.5, color=color,
                bbox=dict(boxstyle="round,pad=0.18", facecolor="white", edgecolor="none"))


def container(ax, x, y, w, h, title, *, color=BLUE, alpha=0.10):
    """Dashed container box with a title in the top-left."""
    patch = mpatches.FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.02,rounding_size=0.08",
        linewidth=1.0,
        linestyle="--",
        edgecolor=color,
        facecolor=color,
        alpha=alpha,
    )
    ax.add_patch(patch)
    ax.text(x + 0.15, y + h - 0.22, title, fontsize=8.5, weight="bold", color=color)


def save(name: str, fig):
    fig.tight_layout()
    path = OUT / name
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  wrote {path.relative_to(OUT.parent)}")


# ---------------------------------------------------------------------------
# Figure 3.1  System Architecture
# ---------------------------------------------------------------------------


def fig_system_architecture():
    fig, ax = plt.subplots(figsize=(11, 7.5))
    ax.set_xlim(0, 20)
    ax.set_ylim(0, 13)
    ax.axis("off")
    ax.set_title("Figure 3.1  Overall System Architecture", loc="left", fontsize=11)

    # Tier 1 — Channels (top)
    container(ax, 0.5, 10.5, 19, 1.8, "Channels (end-user surfaces)", color=ORANGE)
    box(ax, 1.5, 10.9, 4.0, 1.1, "WhatsApp customer", "Meta Cloud API",      fill="#fff3e0", edge=ORANGE)
    box(ax, 7.5, 10.9, 4.0, 1.1, "Website visitor",    "Embeddable widget",  fill="#fff3e0", edge=ORANGE)
    box(ax, 13.5, 10.9, 5.5, 1.1, "SME owner (admin)",  "Next.js dashboard", fill="#fff3e0", edge=ORANGE)

    # Tier 2 — API + adapters
    container(ax, 0.5, 7.7, 19, 2.4, "Application tier (FastAPI on Render)", color=BLUE)
    box(ax, 1.5, 8.7, 4.0, 1.0, "Webhooks router",     "/webhooks/whatsapp",     fill=LIGHT, edge=BLUE)
    box(ax, 7.5, 8.7, 4.0, 1.0, "Widget router",        "/widget/v1/*",          fill=LIGHT, edge=BLUE)
    box(ax, 13.5, 8.7, 5.5, 1.0, "Admin routers",        "/v1/tenants/*",         fill=LIGHT, edge=BLUE)
    box(ax, 1.5, 7.85, 4.0, 0.7, "WhatsApp adapter",    "HMAC verify · send",   fill="white", edge=BLUE, fontsize=8)
    box(ax, 7.5, 7.85, 4.0, 0.7, "Widget adapter",       "session · JWT",         fill="white", edge=BLUE, fontsize=8)
    box(ax, 13.5, 7.85, 5.5, 0.7, "Auth (Clerk) + RLS", "tenant context",        fill="white", edge=BLUE, fontsize=8)

    # Tier 3 — Core engine
    container(ax, 0.5, 4.0, 19, 3.3, "Core engine (pure Python, library-imported into FastAPI + workers)", color=NAVY)
    box(ax, 1.0, 5.8, 3.4, 1.2, "Language\ndetector", "Pidgin-aware\nlexicon + patterns", fill=LIGHT, edge=NAVY)
    box(ax, 4.8, 5.8, 3.4, 1.2, "Persona /\ntenant config", "Postgres JSONB,\nversioned",   fill=LIGHT, edge=NAVY)
    box(ax, 8.6, 5.8, 3.4, 1.2, "Retrieval\nservice", "Milvus Lite\nover 2 M vectors",      fill=LIGHT, edge=NAVY)
    box(ax, 12.4, 5.8, 3.4, 1.2, "Prompt builder", "Nigerian fluency\n+ Pidgin grammar",    fill=LIGHT, edge=NAVY)
    box(ax, 16.2, 5.8, 3.0, 1.2, "Guardrails", "Price · PII ·\nescalation",                fill=LIGHT, edge=NAVY)
    box(ax, 5.5, 4.2, 9.0, 1.2,
        "Conversation orchestrator (single-turn FSM)",
        "detect-lang  ->  retrieve  ->  build-prompt  ->  LM call  ->  guards  ->  persist",
        fill="#dde7f3", edge=NAVY, fontsize=10)

    # Tier 4 — Data + external
    container(ax, 0.5, 0.5, 19, 3.2, "Data tier + external services", color=TEAL)
    box(ax, 1.0, 2.0, 3.8, 1.4, "PostgreSQL",
        "tenants · configs ·\nturns · audit · feedback", fill="#e0f2f1", edge=TEAL)
    box(ax, 5.2, 2.0, 3.8, 1.4, "Milvus Lite",
        "shared corpus +\nper-tenant kb_<tid>",          fill="#e0f2f1", edge=TEAL)
    box(ax, 9.4, 2.0, 3.4, 1.4, "Redis + RQ",
        "webhook fan-out\nsession cache",                 fill="#e0f2f1", edge=TEAL)
    box(ax, 13.2, 2.0, 3.0, 1.4, "Cloudflare R2",
        "uploaded\ndocuments",                           fill="#e0f2f1", edge=TEAL)
    box(ax, 16.6, 2.0, 2.6, 1.4, "Groq API",
        "Llama 3.3 70B\nVersatile",                       fill="#fff7e6", edge=ORANGE)

    box(ax, 1.0, 0.7, 5.0, 0.9, "Embedder",  "sentence-transformers/all-MiniLM-L6-v2 (384-d)",
        fill="white", edge=TEAL, fontsize=8)
    box(ax, 6.5, 0.7, 5.0, 0.9, "Observability", "Langfuse + structlog + Sentry",
        fill="white", edge=TEAL, fontsize=8)
    box(ax, 12.0, 0.7, 7.0, 0.9, "Deployment",
        "Render (backend) · Vercel (dashboard/widget CDN)",
        fill="white", edge=TEAL, fontsize=8)

    # Arrows between tiers
    arrow(ax, 3.5, 10.85, 3.5, 9.75)      # whatsapp → webhooks
    arrow(ax, 9.5, 10.85, 9.5, 9.75)      # widget user → widget router
    arrow(ax, 16.3, 10.85, 16.3, 9.75)    # admin → admin routers
    arrow(ax, 3.5, 7.8, 5.5, 5.4, curve=0.2)
    arrow(ax, 9.5, 7.8, 8.5, 5.4, curve=-0.2)
    arrow(ax, 16.3, 7.8, 14.5, 5.4, curve=-0.2)
    arrow(ax, 6.5, 4.2, 3.0, 3.4, curve=-0.2)
    arrow(ax, 10.0, 4.2, 7.0, 3.4, curve=-0.2)
    arrow(ax, 13.5, 4.2, 17.6, 3.4, curve=0.2, label="LLM")

    return fig


# ---------------------------------------------------------------------------
# Figure 3.2  Message Lifecycle (sequence-like horizontal flow)
# ---------------------------------------------------------------------------


def fig_message_lifecycle():
    fig, ax = plt.subplots(figsize=(11, 7.5))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 12)
    ax.axis("off")
    ax.set_title("Figure 3.2  Single-Turn Message Lifecycle (Pidgin example)",
                 loc="left", fontsize=11)

    # Actors (lanes)
    actors = [
        ("Customer",        0.9,  ORANGE),
        ("WhatsApp Cloud",  2.6,  ORANGE),
        ("FastAPI webhook", 4.3,  BLUE),
        ("Orchestrator",    6.0,  NAVY),
        ("RAG (Milvus)",    7.7,  TEAL),
        ("LLM (Groq)",      9.4,  ORANGE),
        ("Guards + DB",    11.1,  TEAL),
    ]
    for name, x, color in actors:
        ax.add_patch(plt.Rectangle((x - 0.55, 11.0), 1.1, 0.5,
                                   facecolor=color, alpha=0.15,
                                   edgecolor=color, linewidth=1.0))
        ax.text(x, 11.25, name, ha="center", va="center", fontsize=8,
                weight="bold", color=color)
        ax.plot([x, x], [0.5, 11.0], color=color, linewidth=0.8, linestyle="--", alpha=0.5)

    # Sequence steps (top → bottom). (from_x, to_x, y, label, color)
    steps = [
        (0.9,  2.6, 10.4, '1.  "Abeg, una dey open today?" (Pidgin)',     ORANGE),
        (2.6,  4.3, 9.9,  '2.  Webhook POST (with X-Hub-Signature-256)',   ORANGE),
        (4.3,  4.3, 9.4,  '3.  Verify HMAC, parse to CanonicalMessage',    BLUE),
        (4.3,  6.0, 8.9,  '4.  Hand off CanonicalMessage',                  BLUE),
        (6.0,  6.0, 8.4,  '5.  Pidgin-aware language detect -> pid',       NAVY),
        (6.0,  6.0, 7.9,  '6.  Load tenant config + last 6 turns',          NAVY),
        (6.0,  7.7, 7.4,  '7.  Search kb_<tid> + Nigerian corpus (k=7)',    NAVY),
        (7.7,  6.0, 6.9,  '8.  Return top hits (chunks + scores)',          TEAL),
        (6.0,  6.0, 6.4,  '9.  Build prompt: persona + grammar + KB',       NAVY),
        (6.0,  9.4, 5.9,  '10. Chat completion (Llama 3.3 70B, T=0.4)',     NAVY),
        (9.4,  6.0, 5.4,  '11. Return Pidgin reply text',                    ORANGE),
        (6.0, 11.1, 4.9,  '12. Guards: price-check, PII redact, length',    NAVY),
        (11.1, 11.1, 4.4, '13. Write turn + audit_record',                  TEAL),
        (11.1, 6.0, 3.9,  '14. final_text + escalated flag',                 TEAL),
        (6.0,  4.3, 3.4,  '15. OrchestrationResult',                         NAVY),
        (4.3,  2.6, 2.9,  '16. POST /messages (text reply) ',                BLUE),
        (2.6,  0.9, 2.4,  '17. WhatsApp delivers Pidgin reply',              ORANGE),
        (4.3,  2.6, 1.9,  '18. ACK 200 OK to Meta',                          BLUE),
    ]
    for fx, tx, y, label, color in steps:
        if fx == tx:
            # Self-call: draw a small loop
            ax.add_patch(FancyArrowPatch(
                (fx, y), (fx + 0.0, y),
                arrowstyle="-|>",
                connectionstyle="arc3,rad=2.0",
                mutation_scale=10, color=color,
            ))
            ax.text(fx + 0.55, y, label, ha="left", va="center", fontsize=7.5, color=DARK)
        else:
            arr = FancyArrowPatch(
                (fx, y), (tx, y),
                arrowstyle="-|>", mutation_scale=10,
                linewidth=1.2, color=color,
            )
            ax.add_patch(arr)
            mid = (fx + tx) / 2
            ax.text(mid, y + 0.15, label, ha="center", va="bottom",
                    fontsize=7.5, color=DARK,
                    bbox=dict(boxstyle="round,pad=0.18",
                              facecolor="white", edgecolor="none"))

    # Latency budget block
    ax.text(0.4, 0.9,
            "Typical end-to-end latency budget (p95): detect 5 ms · retrieve 700 ms · "
            "LLM 1500 ms · guards 5 ms · DB writes 20 ms → ≈ 2.3 s",
            fontsize=8, color=GREY,
            bbox=dict(boxstyle="round,pad=0.4",
                      facecolor=LIGHT, edgecolor=GREY))

    return fig


# ---------------------------------------------------------------------------
# Figure 3.3  RAG indexing + retrieval pipeline
# ---------------------------------------------------------------------------


def fig_rag_pipeline():
    fig, ax = plt.subplots(figsize=(11, 6.5))
    ax.set_xlim(0, 20)
    ax.set_ylim(0, 10)
    ax.axis("off")
    ax.set_title("Figure 3.3  Retrieval-Augmented Generation Pipeline",
                 loc="left", fontsize=11)

    # Indexing path (top row)
    container(ax, 0.5, 5.6, 19, 4.0, "Indexing path (per uploaded SME document, offline)", color=TEAL)
    nodes_top = [
        (1.0, 7.0, 2.6, 1.4, "Upload",       ".pdf .docx\n.txt .csv .xlsx"),
        (4.4, 7.0, 2.6, 1.4, "Extract",      "pypdf · docx ·\npandas readers"),
        (7.8, 7.0, 2.6, 1.4, "Chunk",        "≈ 512-token\nsemantic chunks"),
        (11.2, 7.0, 2.6, 1.4, "Embed",       "MiniLM-L6-v2\n384-d, cosine"),
        (14.6, 7.0, 2.6, 1.4, "Tag",         "document_type,\nboost, tenant_id"),
        (18.0, 7.0, 1.5, 1.4, "Upsert",      "kb_<tid>"),
    ]
    for x, y, w, h, lbl, sub in nodes_top:
        box(ax, x, y, w, h, lbl, sub, fill=LIGHT, edge=TEAL)
    for i in range(len(nodes_top) - 1):
        x1 = nodes_top[i][0] + nodes_top[i][2]
        x2 = nodes_top[i + 1][0]
        y = nodes_top[i][1] + nodes_top[i][3] / 2
        arrow(ax, x1, y, x2, y, color=TEAL)

    # Query path (bottom row)
    container(ax, 0.5, 0.4, 19, 4.7, "Query path (per inbound message, online)", color=BLUE)
    nodes_bot = [
        (1.0, 2.6, 2.6, 1.4, "Inbound\nmessage", "from WhatsApp\nor widget"),
        (4.4, 2.6, 2.6, 1.4, "Language\ndetect",  "Pidgin-aware"),
        (7.8, 2.6, 2.6, 1.4, "Embed\nquery",     "same MiniLM"),
        (11.2, 2.6, 2.6, 1.4, "Search",          "kb_<tid> +\nshared corpus"),
        (14.6, 2.6, 2.6, 1.4, "Merge +\nre-rank", "score · boost"),
        (18.0, 2.6, 1.5, 1.4, "Top-k\nhits",     "k = 7"),
    ]
    for x, y, w, h, lbl, sub in nodes_bot:
        box(ax, x, y, w, h, lbl, sub, fill=LIGHT, edge=BLUE)
    for i in range(len(nodes_bot) - 1):
        x1 = nodes_bot[i][0] + nodes_bot[i][2]
        x2 = nodes_bot[i + 1][0]
        y = nodes_bot[i][1] + nodes_bot[i][3] / 2
        arrow(ax, x1, y, x2, y, color=BLUE)

    # Down arrow showing Milvus Lite is the shared store
    arrow(ax, 18.7, 7.0, 18.7, 4.0, color=NAVY, label="Milvus Lite\n(file-backed,\nCOSINE index)", label_offset=(1.0, 0))
    return fig


# ---------------------------------------------------------------------------
# Figure 3.4  Multi-tenant isolation
# ---------------------------------------------------------------------------


def fig_multitenant_isolation():
    fig, ax = plt.subplots(figsize=(11, 6.5))
    ax.set_xlim(0, 18)
    ax.set_ylim(0, 11)
    ax.axis("off")
    ax.set_title("Figure 3.4  Multi-Tenant Data Isolation",
                 loc="left", fontsize=11)

    # Three tenant lanes
    for i, (name, color) in enumerate([
        ("Tenant A — Mama Ngozi's Kitchen", GREEN),
        ("Tenant B — Lagos Tech Hub",       ORANGE),
        ("Tenant C — Abuja Boutique",       BLUE),
    ]):
        x = 0.5 + i * 6.0
        container(ax, x, 0.5, 5.6, 10.0, name, color=color, alpha=0.06)
        box(ax, x + 0.4, 8.8, 4.8, 1.2,  "Postgres rows",
            "RLS: WHERE tenant_id = current_tenant",
            fill=LIGHT, edge=color)
        box(ax, x + 0.4, 6.8, 4.8, 1.2,  "Tenant config (JSONB)",
            f"tenant_configs / version N",
            fill=LIGHT, edge=color)
        box(ax, x + 0.4, 4.8, 4.8, 1.2,  "Milvus collection",
            f"kb_{name.split()[1].lower()[:6]}<hash>",
            fill=LIGHT, edge=color)
        box(ax, x + 0.4, 2.8, 4.8, 1.2,  "R2 prefix",
            f"r2://sme-uploads/tenant_{name.split()[1].lower()[:3]}/",
            fill=LIGHT, edge=color)
        box(ax, x + 0.4, 0.8, 4.8, 1.2,  "Audit + turns",
            "tenant_id-stamped rows",
            fill=LIGHT, edge=color)

    ax.text(9.0, 10.7,
            "Same database, same vector store, same object bucket — separation enforced at the row / collection / prefix level.",
            ha="center", fontsize=9, color=GREY, style="italic")
    return fig


# ---------------------------------------------------------------------------
# Figure 3.5  Data Model ERD
# ---------------------------------------------------------------------------


def fig_data_model():
    fig, ax = plt.subplots(figsize=(11, 7.5))
    ax.set_xlim(0, 20)
    ax.set_ylim(0, 13)
    ax.axis("off")
    ax.set_title("Figure 3.5  Relational Data Model (Postgres)",
                 loc="left", fontsize=11)

    tables = [
        # x, y, w, h, name, fields
        (0.5, 10.0, 3.8, 2.2, "users",
         "user_id (PK)\nemail\nauth_provider · subject\ndisplay_name"),
        (5.0, 10.0, 3.8, 2.2, "tenants",
         "tenant_id (PK)\nbusiness_name\nslug · plan · status"),
        (9.5, 10.0, 4.2, 2.2, "tenant_memberships",
         "(tenant_id, user_id) PK\nrole\nFK -> users · tenants"),
        (14.5, 10.0, 5.0, 2.2, "tenant_configs",
         "(tenant_id, version) PK\ndata JSONB\nedited_by"),

        (0.5, 6.4, 4.4, 2.4, "documents",
         "document_id (PK)\ntenant_id (FK)\ntitle · document_type\ns3_key · chunk_count\nstatus"),
        (5.4, 6.4, 4.4, 2.4, "manual_faqs",
         "faq_id (PK)\ntenant_id (FK)\nquestion · answer\nlanguage_hint · boost"),
        (10.3, 6.4, 4.4, 2.4, "tenant_whatsapp_credentials",
         "tenant_id (PK)\nwaba_id · phone_number_id (uq)\naccess_token_enc"),
        (15.2, 6.4, 4.4, 2.4, "tenant_widget_keys",
         "widget_key (PK)\ntenant_id (FK)\nallowed_origins[]"),

        (0.5, 2.5, 4.6, 3.2, "conversations",
         "conversation_id (PK)\ntenant_id (FK)\nchannel · sender_id (uq)\nstarted_at · last_turn_at\nturn_count · languages_seen"),
        (5.6, 2.5, 4.6, 3.2, "turns",
         "turn_id (PK)\nconversation_id (FK)\nrole · text · received_at\ndetected_language\nis_mixed_language · escalated"),
        (10.7, 2.5, 4.6, 3.2, "audit_records",
         "audit_id (PK)\nconversation_id · turn_id\nretrieved_chunk_ids[]\nsystem_prompt · user_prompt\nresponse_text · model\nlatency_breakdown_ms JSONB"),
        (15.8, 2.5, 3.8, 3.2, "feedback",
         "feedback_id (PK)\nturn_id (FK)\nrating · note\ncorrected_answer"),

        (0.5, 0.2, 6.0, 1.7, "processed_messages",
         "(tenant_id, channel, channel_msg_id) PK\nprocessed_at  — idempotency"),
    ]
    for x, y, w, h, name, fields in tables:
        # Header band
        ax.add_patch(FancyBboxPatch(
            (x, y + h - 0.55), w, 0.55,
            boxstyle="round,pad=0.02,rounding_size=0.04",
            facecolor=NAVY, edgecolor=NAVY,
        ))
        ax.text(x + w / 2, y + h - 0.28, name,
                ha="center", va="center", fontsize=8.5, weight="bold", color="white")
        ax.add_patch(FancyBboxPatch(
            (x, y), w, h - 0.55,
            boxstyle="round,pad=0.02,rounding_size=0.04",
            facecolor=LIGHT, edgecolor=NAVY, linewidth=1.0,
        ))
        ax.text(x + 0.15, y + (h - 0.55) - 0.3, fields,
                ha="left", va="top", fontsize=7.5, color=DARK)

    return fig


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------


def main() -> None:
    print("Generating figures...")
    save("fig_3_1_system_architecture.png",  fig_system_architecture())
    save("fig_3_2_message_lifecycle.png",    fig_message_lifecycle())
    save("fig_3_3_rag_pipeline.png",         fig_rag_pipeline())
    save("fig_3_4_multitenant_isolation.png", fig_multitenant_isolation())
    save("fig_3_5_data_model_erd.png",       fig_data_model())
    print("Done.")


if __name__ == "__main__":
    main()
