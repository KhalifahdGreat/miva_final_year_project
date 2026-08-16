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


# Used when the price guard fires so the customer still hears their language.
_PRICE_FALLBACK = {
    "en": (
        "I'm not sure about that one — let me get a human colleague to help. "
        "I'd rather double-check the exact figure with my colleague."
    ),
    "pid": "I no too sure of that figure — make I confirm with my colleague first.",
    "yo": "Mi o daadaa mo iye owo yen. Jowo, je ki n beere lowo alabojuto mi ki n da yin lohun.",
    "ha": "Ban tabbata wannan farashi ba. Bari in tambayi abokina na aiki in dawo da amsa.",
    "ig": "Biko chere ntakịrị — ka m jụọ onye nọ n'usekwu ego ole ka ọ dị, ka m ghara ịgwa gị ọnụahịa na-ezighị ezi.",
}


# ---------------------------------------------------------------------------
# Pattern library
# ---------------------------------------------------------------------------


# Digit groups: 4,500 | 4 500 | 4500 | 4500.00  (grouped form must include a separator)
_DIGITS = (
    r"(\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?"
    r"|\d{1,3}(?: \d{3})+(?:\.\d{1,2})?"
    r"|\d+(?:\.\d{1,2})?)"
)
_NGN_PRICE = re.compile(
    rf"(?:₦|#)\s*{_DIGITS}\s*(k\b)?"
    rf"|\bNGN\s*{_DIGITS}\s*(k\b)?"
    rf"|\bnaira\s*{_DIGITS}"
    rf"|{_DIGITS}\s*(k\s*)?(?:naira|ngn)\b"
    rf"|\bN(?=[\s.]?\d){_DIGITS}\s*(k\b)?",
    re.IGNORECASE,
)
_BVN_NIN = re.compile(r"\b\d{11}\b")
_CARD = re.compile(r"\b(?:\d{4}[\s-]?){3}\d{4}\b")
_PHONE = re.compile(r"(?:\+234|0)[789][01]\d{8}")
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_MIN_NAIRA = 20.0  # ignore stray N9 / 9am false hits


def _match_amount(m: re.Match[str]) -> float | None:
    raw = next((g for g in m.groups() if g and re.search(r"\d", g)), None)
    if not raw:
        return None
    whole = m.group(0).lower()
    cleaned = re.sub(r"[,\s]", "", raw)
    try:
        value = float(cleaned)
    except ValueError:
        return None
    if re.search(r"\dk", whole.lower().replace(" ", "")):
        value *= 1000
    if value < _MIN_NAIRA:
        return None
    return value


def _phone_spans(text: str) -> list[tuple[int, int]]:
    return [m.span() for m in _PHONE.finditer(text)]


def _overlaps_phone(span: tuple[int, int], phones: list[tuple[int, int]]) -> bool:
    a, b = span
    return any(a < pe and b > ps for ps, pe in phones)


def _amounts(text: str) -> set[float]:
    """Extract naira amounts, normalised (4,500 == 4500 == 4.5k)."""
    if not text:
        return set()
    phones = _phone_spans(text)
    out: set[float] = set()
    for m in _NGN_PRICE.finditer(text):
        if _overlaps_phone(m.span(), phones):
            continue
        value = _match_amount(m)
        if value is not None:
            out.add(value)
    return out


def extract_naira_amounts(text: str) -> set[float]:
    """Public wrapper used by tests."""
    return _amounts(text)


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


def _price_fallback(lang: str, tenant_fallback: str) -> str:
    if lang != "en":
        return _PRICE_FALLBACK.get(lang) or tenant_fallback or _PRICE_FALLBACK["en"]
    base = tenant_fallback or (
        "I'm not sure about that one — let me get a human colleague to help."
    )
    extra = "I'd rather double-check the exact figure with my colleague."
    if extra.lower() in base.lower():
        return base
    return f"{base.rstrip()} {extra}"


def _drop_invented_price_sentences(text: str, invented: set[float]) -> str:
    """Remove invented price spans; keep grounded clauses in any language."""

    def repl(m: re.Match[str]) -> str:
        value = _match_amount(m)
        if value is not None and value in invented:
            return ""
        return m.group(0)

    cleaned = _NGN_PRICE.sub(repl, text)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([,.;!?])", r"\1", cleaned)
    cleaned = re.sub(
        r"\b(?:bụ|bu|is|be|na|for|at|of|bụrụ)\s*[.,;]",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    parts = re.split(r"(?<=[.!?;])\s+|\n+", cleaned.strip())
    kept = [p.strip() for p in parts if len(p.strip()) >= 8]
    return " ".join(kept).strip(" ,;.-")


def apply_guards(
    response_text: str,
    *,
    retrieved_text_blob: str,
    tenant_config: TenantConfig,
    user_message: str,
    detected_language: str = "en",
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
            kept = _drop_invented_price_sentences(text, invented)
            confirm = _price_fallback(detected_language, tenant_config.fallback)
            final = f"{kept} {confirm}".strip() if len(kept) >= 20 else confirm
            return GuardResult(
                final_text=final,
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
