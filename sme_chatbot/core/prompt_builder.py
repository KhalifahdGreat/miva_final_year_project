"""Composes the system + user prompts for one orchestrator turn.

This is the single place where:
  * the tenant persona is rendered,
  * the Nigerian fluency block is injected,
  * the Pidgin grammar block is conditionally included,
  * retrieved chunks become the KNOWLEDGE block,
  * the conversation history is folded into the user prompt.

The output is a `(system, user)` pair ready to feed into `LMClient.complete`.
"""

from __future__ import annotations

from .nigerian_prompt_block import (
    HARD_RULES,
    NIGERIAN_FLUENCY_BLOCK,
    PIDGIN_GRAMMAR_BLOCK,
    TONE_INSTRUCTIONS,
    language_directive,
)
from .types import Hit, TenantConfig, Turn


def _format_knowledge(hits: list[Hit], max_items: int = 6) -> str:
    """Convert retrieved chunks into a readable KNOWLEDGE block."""
    if not hits:
        return "(no specific knowledge retrieved for this query)"
    lines: list[str] = []
    for h in hits[:max_items]:
        label = f"{h.document_type}/{h.section or '-'}" if h.document_type else (h.section or "ref")
        snippet = h.text[:500].replace("\n", " ").strip()
        lines.append(f"- [{label}] {snippet}")
    return "\n".join(lines)


def _format_brand_voice(examples: list[str]) -> str:
    if not examples:
        return ""
    joined = "\n".join(f'- "{ex}"' for ex in examples[:3])
    return f"\nBRAND VOICE (echo this energy; do not copy verbatim):\n{joined}\n"


def _format_history(history: list[Turn], max_turns: int = 6) -> str:
    if not history:
        return ""
    lines: list[str] = []
    for t in history[-max_turns:]:
        who = "Customer" if t.role == "user" else "Assistant"
        lines.append(f"{who}: {t.text}")
    return "Conversation so far:\n" + "\n".join(lines) + "\n\n"


def build(
    *,
    tenant_config: TenantConfig,
    retrieved_chunks: list[Hit],
    history: list[Turn],
    user_message: str,
    detected_language: str,
    is_mixed_language: bool = False,
    escalation_hint: str = "",
) -> tuple[str, str]:
    """Build a (system, user) prompt pair.

    Parameters
    ----------
    tenant_config
        The SME's locked configuration.
    retrieved_chunks
        Chunks from the tenant's own knowledge plus the shared Nigerian corpus.
    history
        Last N turns of the conversation (most recent last).
    user_message
        The customer's current message (raw).
    detected_language
        One of ``en | pid | yo | ha | ig | unknown``.
    is_mixed_language
        True when the detector found strong evidence of two languages.
    escalation_hint
        Optional note added to the user prompt when an escalation rule has
        already fired upstream — instructs the model to acknowledge and stay calm.
    """

    tone_block = TONE_INSTRUCTIONS.get(tenant_config.tone, TONE_INSTRUCTIONS["casual"])
    lang_directive = language_directive(detected_language, tenant_config.languages)
    if is_mixed_language:
        lang_directive += (
            " Note: the customer used more than one language in this message; "
            "reply in the dominant one and don't translate yourself."
        )

    knowledge = _format_knowledge(retrieved_chunks)
    brand_voice = _format_brand_voice(tenant_config.brand_voice_examples)
    pidgin_block = PIDGIN_GRAMMAR_BLOCK if detected_language == "pid" else ""

    biz_name = tenant_config.business_name
    tagline = tenant_config.tagline.strip()

    system_parts = [
        f"You are {biz_name}'s customer-service assistant on WhatsApp."
        + (f" {tagline}" if tagline else ""),
        "",
        tone_block,
        "",
        lang_directive,
        "",
        NIGERIAN_FLUENCY_BLOCK,
        "",
        "USE THIS KNOWLEDGE ONLY (do not invent facts beyond it):",
        knowledge,
        brand_voice,
        pidgin_block,
        HARD_RULES,
    ]

    system = "\n".join(p for p in system_parts if p is not None).strip()

    user_parts = []
    history_block = _format_history(history)
    if history_block:
        user_parts.append(history_block)
    user_parts.append(f'New customer message:\n"{user_message}"')
    if escalation_hint:
        user_parts.append(f"\n[Internal note: {escalation_hint}]")
    user_parts.append("\nReply:")
    user = "\n".join(user_parts)

    return system, user
