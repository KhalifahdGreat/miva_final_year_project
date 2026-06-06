"""Post-generation guardrails.

These checks run AFTER the LLM produces a reply and BEFORE we send anything
to the customer. They can mutate or replace the reply and can raise an
escalation flag that the orchestrator forwards to the SME owner.

Built-in checks:
  1. Price hallucination — any naira amount in the reply that was not present
     in the retrieved chunks is treated as an invented price and triggers the
     fallback + escalation.
  2. PII redaction — BVN/NIN, card numbers, phone numbers, email addresses.
  3. Length cap — for WhatsApp, prefer < 800 chars.
  4. Tenant escalation rules — amount-over thresholds, phrase triggers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .types import TenantConfig


# ---------------------------------------------------------------------------
# Pattern library
# ---------------------------------------------------------------------------


# Money mentions: ₦, N, NGN, or "naira" followed by an amount.
_NGN_PRICE = re.compile(
    r"(?:₦|\bN(?:GN)?\s?|\bnaira\s+)\s?(\d{1,3}(?:[,.\s]\d{3})*(?:\.\d{1,2})?|\d{2,7}(?:\.\d{1,2})?)",
    re.IGNORECASE,
)
_BVN_NIN = re.compile(r"\b\d{11}\b")
_CARD = re.compile(r"\b(?:\d{4}[\s-]?){3}\d{4}\b")
_PHONE = re.compile(r"(?:\+234|0)[789][01]\d{8}")
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _amounts(text: str) -> set[float]:
    """Extract numeric amounts from naira mentions, normalised."""
    out: set[float] = set()
    for m in _NGN_PRICE.finditer(text):
        raw = m.group(1)
        cleaned = re.sub(r"[,\s]", "", raw)
        try:
            out.add(float(cleaned))
        except ValueError:
            continue
    return out


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class GuardResult:
    final_text: str
    mutated: bool
    escalated: bool
    reason: str = ""
    mutations: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.mutations is None:
            self.mutations = []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def apply_guards(
    response_text: str,
    *,
    retrieved_text_blob: str,
    tenant_config: TenantConfig,
    user_message: str,
) -> GuardResult:
    """Run all guardrails over a candidate reply.

    Parameters
    ----------
    response_text
        The raw LM output.
    retrieved_text_blob
        Concatenated text of every retrieved chunk — used to verify any prices
        the LM wrote actually came from the knowledge base.
    tenant_config
        The SME's locked configuration (escalation rules, fallback message).
    user_message
        The original customer message (used for escalation phrase matching).
    """

    text = (response_text or "").strip().strip('"').strip("'")
    mutations: list[str] = []
    escalated = False
    reason = ""

    # 1. Price hallucination
    reply_amounts = _amounts(text)
    if reply_amounts:
        known_amounts = _amounts(retrieved_text_blob)
        invented = {a for a in reply_amounts if a not in known_amounts}
        if invented:
            invented_str = ", ".join(f"₦{int(a):,}" for a in sorted(invented))
            return GuardResult(
                final_text=(
                    f"{tenant_config.fallback} "
                    "I'd rather double-check the exact figure with my colleague."
                ),
                mutated=True,
                escalated=True,
                reason=f"hallucinated_price:{invented_str}",
                mutations=["price_hallucination_blocked"],
            )

    # 2. PII redaction
    # Order matters: phone numbers (11 digits with 070/080/090 etc. prefix) must
    # be matched BEFORE the bare-11-digit BVN/NIN pattern, otherwise the latter
    # eats them as IDs.
    redacted = _PHONE.sub("[REDACTED-PHONE]", text)
    if redacted != text:
        mutations.append("redacted_phone")
        text = redacted
    redacted = _CARD.sub("[REDACTED-CARD]", text)
    if redacted != text:
        mutations.append("redacted_card")
        text = redacted
    redacted = _BVN_NIN.sub("[REDACTED-ID]", text)
    if redacted != text:
        mutations.append("redacted_id")
        text = redacted
    redacted = _EMAIL.sub("[REDACTED-EMAIL]", text)
    if redacted != text:
        mutations.append("redacted_email")
        text = redacted

    # 3. Tenant escalation rules
    for rule in tenant_config.escalation_rules:
        if rule.type == "phrase":
            lowered = user_message.lower()
            if any(p.lower() in lowered for p in rule.patterns):
                escalated = True
                reason = f"escalation_phrase:{rule.patterns[0]}"
                break
        elif rule.type == "amount_over" and rule.threshold is not None:
            for amount in _amounts(user_message):
                if amount >= rule.threshold:
                    escalated = True
                    reason = f"amount_over:{int(amount)}"
                    break

    # 4. Length cap (WhatsApp prefers <800 chars; truncate gracefully)
    if len(text) > 800:
        cut = text[:780].rsplit(" ", 1)[0]
        text = cut + "..."
        mutations.append("truncated")

    return GuardResult(
        final_text=text,
        mutated=bool(mutations),
        escalated=escalated,
        reason=reason,
        mutations=mutations,
    )
