"""Domain types shared across the core engine.

All types are plain dataclasses and `from __future__ import annotations` is
used everywhere so callers can construct them without runtime overhead.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Tenant configuration
# ---------------------------------------------------------------------------


Tone = Literal["formal", "casual", "pidgin_friendly", "youthful"]
Language = Literal["en", "pid", "yo", "ha", "ig"]


@dataclass
class EscalationRule:
    """A single rule that, when matched, hands the conversation to a human."""

    type: Literal["amount_over", "intent", "phrase"]
    target_field: str | None = None
    threshold: float | None = None
    intent: str | None = None
    patterns: list[str] = field(default_factory=list)
    action: Literal["handoff"] = "handoff"


@dataclass
class TenantConfig:
    """A single SME tenant's settings.

    Stored in Postgres as a JSONB blob keyed by ``(tenant_id, version)``.
    Loaded by `TenantService` and injected at orchestrator entry.
    """

    tenant_id: str
    business_name: str
    tagline: str = ""
    tone: Tone = "casual"
    languages: list[Language] = field(default_factory=lambda: ["en", "pid"])
    timezone: str = "Africa/Lagos"
    operating_hours: dict[str, str] = field(default_factory=dict)
    greeting: str = ""
    out_of_hours: str = ""
    fallback: str = (
        "I'm not sure about that one — let me get a human colleague to help."
    )
    escalation_rules: list[EscalationRule] = field(default_factory=list)
    brand_voice_examples: list[str] = field(default_factory=list)
    retrieval_weights: dict[str, int] = field(
        default_factory=lambda: {
            "manual_faq": 4,
            "faq": 3,
            "pricing": 2,
            "catalogue": 2,
            "policy": 1,
        }
    )
    version: int = 1


# ---------------------------------------------------------------------------
# Conversation primitives
# ---------------------------------------------------------------------------


@dataclass
class Turn:
    """A single message in the conversation history."""

    role: Literal["user", "assistant"]
    text: str
    ts: datetime = field(default_factory=_now)


@dataclass
class CanonicalMessage:
    """Channel-agnostic inbound message.

    Every channel adapter normalises its wire format into this.
    """

    tenant_id: str
    channel: Literal["whatsapp", "widget"]
    sender_id: str
    text: str
    received_at: datetime
    channel_msg_id: str
    attachments: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------


@dataclass
class Hit:
    """A retrieved chunk with score and metadata."""

    chunk_id: int
    text: str
    document_type: str
    section: str
    score: float
    boost: float = 1.0
    document_id: str = ""
    collection: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Orchestrator output
# ---------------------------------------------------------------------------


@dataclass
class OrchestrationResult:
    """What the orchestrator returns for a single turn."""

    reply_text: str
    detected_language: str
    is_mixed_language: bool
    retrieval_count: int
    escalated: bool
    escalation_reason: str | None
    latency_breakdown_ms: dict[str, float]
    turn_id: str = field(default_factory=_uuid)
    model: str = ""
    provider: str = ""
