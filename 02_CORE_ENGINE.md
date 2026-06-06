# Core Engine — Deep Dive

This document specifies the **engine that handles a single conversation turn**: language detection, retrieval, prompt construction, model invocation, guardrails, persistence. Every code block is illustrative — production-grade enough to start from, but the canonical implementation will live in your repository.

The patterns here are **adapted from a battle-tested Nigerian-NLP system already in production** (the same author's prior work). Where a particular constant or weight has a justification, it's noted inline.

---

## Table of Contents

1. [Engine Anatomy](#1-engine-anatomy)
2. [LM Client](#2-lm-client)
3. [Retrieval Service](#3-retrieval-service)
4. [Persona / Tenant Configuration](#4-persona--tenant-configuration)
5. [Language Detection](#5-language-detection)
6. [Prompt Builder](#6-prompt-builder)
7. [Guardrails](#7-guardrails)
8. [Conversation Orchestrator](#8-conversation-orchestrator)
9. [Ingestion Pipeline](#9-ingestion-pipeline)
10. [Fine-tuning the Nigeria-Specific LM](#10-fine-tuning-the-nigeria-specific-lm)
11. [Why these design choices](#11-why-these-design-choices)

---

## 1. Engine Anatomy

```
                 ┌────────────────────────────┐
                 │  ConversationOrchestrator  │  ←── single entry point
                 └───────────┬────────────────┘
                             │
   ┌─────────────┬───────────┼───────────────┬──────────────┐
   ▼             ▼           ▼               ▼              ▼
PersonaSvc   LangDetect   Retrieval      PromptBuilder    LMClient
                                          │
                                          ▼
                                       Guardrails
                                          │
                                          ▼
                                    AuditWriter +
                                    HistoryService
```

Every component is replaceable behind its interface (see `01_ARCHITECTURE.md` §3). The orchestrator is the only module that knows the shape of the whole pipeline.

---

## 2. LM Client

A single class wraps every LLM provider. Every other module talks to it; nothing imports a vendor SDK directly.

### 2.1 Interface

```python
# core/lm_client.py
import time
import logging
from dataclasses import dataclass
from typing import Literal

log = logging.getLogger(__name__)


@dataclass
class LMResponse:
    text: str
    model: str
    provider: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int


_RETRYABLE_SUBSTRINGS = (
    "rate_limit", "429", "500", "502", "503", "504",
    "timeout", "connection", "econnreset",
)


class LMClient:
    """Single point of contact with any language model provider.

    Providers:
        - 'vllm-local'   internal vLLM server (production fine-tune)
        - 'hf-endpoint'  HuggingFace Inference Endpoint
        - 'groq'         Groq hosted (used for the comparative-baseline arm)
    """

    def __init__(self, provider: Literal["vllm-local", "hf-endpoint", "groq"],
                 model: str,
                 *,
                 base_url: str | None = None,
                 api_key: str | None = None,
                 timeout_s: float = 8.0,
                 max_retries: int = 3) -> None:
        self.provider = provider
        self.model = model
        self.base_url = base_url
        self.api_key = api_key
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self._client = None     # lazy

    def _ensure(self):
        if self._client is not None:
            return self._client
        if self.provider == "vllm-local":
            from openai import OpenAI       # vLLM exposes OpenAI-compatible API
            self._client = OpenAI(base_url=self.base_url, api_key=self.api_key or "internal")
        elif self.provider == "hf-endpoint":
            from huggingface_hub import InferenceClient
            self._client = InferenceClient(model=self.base_url, token=self.api_key)
        elif self.provider == "groq":
            from groq import Groq
            self._client = Groq(api_key=self.api_key)
        else:
            raise ValueError(f"unknown provider: {self.provider}")
        return self._client

    def complete(self, *,
                 system: str,
                 user: str,
                 history: list[dict] | None = None,
                 temperature: float = 0.4,
                 max_tokens: int = 400,
                 stop: list[str] | None = None) -> LMResponse:
        msgs: list[dict] = [{"role": "system", "content": system}]
        if history:
            msgs.extend(history)
        msgs.append({"role": "user", "content": user})

        start = time.perf_counter()
        last_exc: Exception | None = None
        backoff = (1.0, 3.0, 8.0)

        for attempt in range(self.max_retries):
            try:
                if self.provider in ("vllm-local", "groq"):
                    resp = self._ensure().chat.completions.create(
                        model=self.model, messages=msgs,
                        temperature=max(0.0, min(1.5, temperature)),
                        max_tokens=max_tokens, stop=stop,
                        timeout=self.timeout_s,
                    )
                    text = resp.choices[0].message.content or ""
                    pt = getattr(resp.usage, "prompt_tokens", 0) or 0
                    ct = getattr(resp.usage, "completion_tokens", 0) or 0
                else:  # hf-endpoint
                    out = self._ensure().chat_completion(
                        messages=msgs, max_tokens=max_tokens,
                        temperature=temperature, stop=stop,
                    )
                    text = out.choices[0].message.content
                    pt = ct = 0  # HF endpoint sometimes omits these

                return LMResponse(
                    text=text.strip(), model=self.model, provider=self.provider,
                    prompt_tokens=pt, completion_tokens=ct,
                    latency_ms=int((time.perf_counter() - start) * 1000),
                )
            except Exception as exc:
                last_exc = exc
                msg = str(exc).lower()
                if any(s in msg for s in _RETRYABLE_SUBSTRINGS) and attempt < self.max_retries - 1:
                    wait = backoff[min(attempt, len(backoff) - 1)]
                    log.warning("LM retry %d/%d in %.1fs: %s",
                                attempt + 1, self.max_retries, wait, exc)
                    time.sleep(wait)
                    continue
                raise
        raise last_exc  # type: ignore[misc]
```

### 2.2 Why this shape

- **One wrapper, three providers.** The fine-tuned model lives behind vLLM (which speaks the OpenAI Chat API). The Groq backend is for the contrastive baseline. HF Endpoints is a fallback if no GPU is available. Swapping is a config change.
- **Retry list is tight.** Only retry on transient (rate-limit / 5xx / network) errors. Application errors fail fast.
- **Response carries everything the audit table needs.** Including provider and model — important when ablations swap them.

---

## 3. Retrieval Service

### 3.1 Goals

1. Strict per-tenant isolation.
2. Two retrieval modes: uniform `search` and per-document-type weighted `search_weighted`.
3. Min-score filter to suppress junk hits.
4. A separate **specialised lookup** API for things the prompt builder needs frequently (e.g. *fetch the top FAQ answer for this query, exact-match-boosted*).

### 3.2 Vector schema

Each tenant gets a Milvus collection `kb_<tenant_id_short>`. Each chunk is a row:

```
id              INT64, primary
embedding       FLOAT_VECTOR, dim=1024 (e5-large) or 1024 (bge-m3)
text            VARCHAR(8192)
document_id     VARCHAR(36)        -- UUID
document_type   VARCHAR(32)        -- 'catalogue' | 'faq' | 'policy' | 'manual_faq' | 'pricing'
section         VARCHAR(128)
language_hint   VARCHAR(8)         -- 'en' | 'pid' | 'yo' | ...
boost           FLOAT              -- 1.0 default; manual_faq = 1.5
metadata_json   VARCHAR(4096)      -- e.g. SKU, price, URL
```

Index: `IVF_FLAT` or `HNSW`, metric `COSINE`. Embeddings are L2-normalised at insert (so cosine == dot product).

### 3.3 Implementation

```python
# core/retrieval.py
import json
import logging
from dataclasses import dataclass
from uuid import UUID

log = logging.getLogger(__name__)


@dataclass
class Hit:
    chunk_id: int
    document_id: str
    document_type: str
    text: str
    section: str
    score: float
    boost: float
    metadata: dict


class RetrievalService:
    DEFAULT_TOP_K = 5
    DEFAULT_MIN_SCORE = 0.30

    def __init__(self, vector_client, embedder) -> None:
        self._client = vector_client       # MilvusClient | QdrantClient
        self._embedder = embedder          # SentenceTransformer

    def _coll(self, tenant_id: UUID) -> str:
        return f"kb_{tenant_id.hex[:12]}"

    def _encode(self, text: str) -> list[float]:
        emb = self._embedder.encode([text], normalize_embeddings=True)[0]
        return emb.tolist()

    def search(self, tenant_id: UUID, query: str, *,
               top_k: int = DEFAULT_TOP_K,
               min_score: float = DEFAULT_MIN_SCORE,
               document_types: list[str] | None = None) -> list[Hit]:
        emb = self._encode(query)
        expr = None
        if document_types:
            joined = ", ".join(f'"{t}"' for t in document_types)
            expr = f"document_type in [{joined}]"

        results = self._client.search(
            collection_name=self._coll(tenant_id),
            data=[emb],
            limit=top_k * 2,
            output_fields=["text", "document_id", "document_type",
                           "section", "boost", "metadata_json"],
            search_params={"metric_type": "COSINE"},
            filter=expr,
        )

        hits: list[Hit] = []
        for hits_arr in results:
            for h in hits_arr:
                score = h.get("distance", 0.0)
                if score < min_score:
                    continue
                e = h.get("entity", {})
                boost = float(e.get("boost", 1.0))
                meta = {}
                try:
                    meta = json.loads(e.get("metadata_json", "{}"))
                except Exception:
                    pass
                hits.append(Hit(
                    chunk_id=h.get("id"),
                    document_id=e.get("document_id", ""),
                    document_type=e.get("document_type", ""),
                    text=e.get("text", ""),
                    section=e.get("section", ""),
                    score=score * boost,                    # boost-aware score
                    boost=boost,
                    metadata=meta,
                ))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:top_k]

    def search_weighted(self, tenant_id: UUID, query: str, *,
                        weights: dict[str, int],
                        top_k: int = 7,
                        min_score: float = DEFAULT_MIN_SCORE) -> list[Hit]:
        """Pull more from the document_types you care about most.

        weights is e.g. {"manual_faq": 4, "faq": 3, "catalogue": 2,
                         "policy": 1, "pricing": 2}.
        """
        if not weights:
            return self.search(tenant_id, query, top_k=top_k, min_score=min_score)

        total = sum(weights.values())
        emb = self._encode(query)
        all_hits: list[Hit] = []

        for doc_type, w in weights.items():
            k = max(1, int(top_k * w / total) + 1)
            results = self._client.search(
                collection_name=self._coll(tenant_id),
                data=[emb], limit=k,
                output_fields=["text", "document_id", "document_type",
                               "section", "boost", "metadata_json"],
                search_params={"metric_type": "COSINE"},
                filter=f'document_type == "{doc_type}"',
            )
            for hits_arr in results:
                for h in hits_arr:
                    score = h.get("distance", 0.0)
                    if score < min_score:
                        continue
                    e = h.get("entity", {})
                    boost = float(e.get("boost", 1.0))
                    all_hits.append(Hit(
                        chunk_id=h.get("id"),
                        document_id=e.get("document_id", ""),
                        document_type=e.get("document_type", ""),
                        text=e.get("text", ""),
                        section=e.get("section", ""),
                        score=score * boost,
                        boost=boost,
                        metadata=json.loads(e.get("metadata_json", "{}")) if e.get("metadata_json") else {},
                    ))

        all_hits.sort(key=lambda h: h.score, reverse=True)
        return all_hits[:top_k]

    @staticmethod
    def format_for_prompt(hits: list[Hit], max_items: int = 5) -> str:
        lines: list[str] = []
        for h in hits[:max_items]:
            label = f"{h.document_type}/{h.section}" if h.section else h.document_type
            preview = h.text[:500].replace("\n", " ")
            lines.append(f"- [{label}] {preview}")
        return "\n".join(lines)
```

### 3.4 Default per-tenant retrieval weights

Decided per tenant by document mix; sensible default:

```python
DEFAULT_WEIGHTS = {
    "manual_faq":  4,   # tenant-curated Q/A — strongest signal
    "faq":         3,   # FAQs from uploaded docs
    "pricing":     2,   # price sheets
    "catalogue":   2,   # SKU lists
    "policy":      1,   # long policy text — used sparingly
}
```

### 3.5 Specialised lookups

Two helpers worth exposing on the service:

```python
def fetch_canonical_answer(self, tenant_id, query) -> Hit | None:
    """Return a manual_faq hit only if its score is unusually high (>0.75)."""
    hits = self.search(tenant_id, query, top_k=3,
                       document_types=["manual_faq"])
    return hits[0] if hits and hits[0].score >= 0.75 else None

def fetch_pricing(self, tenant_id, query) -> list[Hit]:
    return self.search(tenant_id, query, top_k=3,
                       document_types=["pricing", "catalogue"])
```

The orchestrator uses `fetch_canonical_answer` to short-circuit: if a tenant has explicitly authored an answer for the query, prefer it directly (with the LM rephrasing for tone) instead of recomposing from raw chunks.

---

## 4. Persona / Tenant Configuration

### 4.1 The TenantConfig type

```python
# core/persona.py
from dataclasses import dataclass, field
from datetime import time
from uuid import UUID


@dataclass
class EscalationRule:
    type: str                    # "amount_over" | "intent" | "phrase"
    field: str | None = None
    threshold: float | None = None
    intent: str | None = None
    patterns: list[str] = field(default_factory=list)
    action: str = "handoff"


@dataclass
class TenantConfig:
    tenant_id: UUID
    business_name: str
    tagline: str
    tone: str                    # "formal" | "casual" | "pidgin_friendly" | "youthful"
    languages: list[str]         # subset of ["en","pid","yo","ha","ig"]
    timezone: str
    operating_hours: dict        # {"mon_fri": "09:00-19:00", ...}
    greeting: str
    out_of_hours: str
    fallback: str
    escalation_rules: list[EscalationRule]
    brand_voice_examples: list[str]
    retrieval_weights: dict[str, int]
    version: int
```

### 4.2 PersonaService

```python
class PersonaService:
    def __init__(self, db, cache):
        self._db = db                  # Postgres
        self._cache = cache            # Redis

    def get(self, tenant_id: UUID) -> TenantConfig:
        key = f"tcfg:{tenant_id}"
        cached = self._cache.get(key)
        if cached:
            return TenantConfig(**json.loads(cached))
        row = self._db.fetchone(
            "SELECT data FROM tenant_configs WHERE tenant_id = %s "
            "ORDER BY version DESC LIMIT 1", (str(tenant_id),))
        if not row:
            raise LookupError(f"no config for tenant {tenant_id}")
        cfg = TenantConfig(**json.loads(row["data"]))
        self._cache.setex(key, 300, json.dumps(asdict(cfg)))
        return cfg

    def save(self, cfg: TenantConfig, *, actor_user_id: UUID) -> int:
        new_version = cfg.version + 1
        self._db.execute(
            "INSERT INTO tenant_configs (tenant_id, version, data, edited_by) "
            "VALUES (%s, %s, %s, %s)",
            (str(cfg.tenant_id), new_version, json.dumps(asdict(cfg)), str(actor_user_id)),
        )
        self._cache.delete(f"tcfg:{cfg.tenant_id}")
        return new_version
```

### 4.3 Tone presets

Tone is *not* a freeform string — it is one of four presets, each with a baked-in instruction block in the prompt builder:

| Preset | Instruction (appended to system prompt) |
|---|---|
| `formal` | Reply in clear, polite English. No slang. Use full sentences. Address the customer as "sir/ma" only if they used a formal register first. |
| `casual` | Reply in friendly conversational English. Light contractions are fine. Avoid slang the customer didn't use first. |
| `pidgin_friendly` | If the customer wrote Pidgin, reply in Pidgin. If they wrote English, reply in English with a warm Nigerian register. **Never** translate yourself. |
| `youthful` | Match a Gen-Z Nigerian register. Light emoji ok if the customer used one first. Stay short and lively. |

These instructions live as static strings in code (not in the DB) so they can be updated centrally and audited.

---

## 5. Language Detection

### 5.1 Why it matters

Off-the-shelf langid systems (FastText `lid.176`, langdetect) are trained predominantly on news text and consistently misclassify Nigerian Pidgin as **English**. Empirically, on a 1k-utterance held-out Pidgin set, FastText returns "en" >95% of the time. The detection layer must therefore combine:

1. A baseline langid pass (FastText or `langid-lite`).
2. A **Pidgin lexical / discourse-marker layer** that overrides "en" → "pid" when Pidgin signals dominate.
3. A **mixed-language detector** that flags utterances combining two or more languages within one message.

### 5.2 Implementation sketch

```python
# core/language.py
import re
from dataclasses import dataclass


@dataclass
class LangResult:
    dominant: str           # 'en' | 'pid' | 'yo' | 'ha' | 'ig' | 'unknown'
    mixed: bool
    scores: dict[str, float]


# Hand-curated Pidgin signals (high precision).
# Source: derived from real Nairaland + Twitter Pidgin corpora.
PIDGIN_TOKENS = {
    "abeg", "wahala", "wetin", "dey", "no be", "na", "sef", "sha", "wey",
    "e go", "e dey", "na so", "no wahala", "omo", "ehn", "walahi",
    "oga", "una", "make", "dem", "biko", "abi", "shey", "small small",
    "gist", "mumu", "sabi", "sabi am", "no fit", "go fit", "fit",
    "as e be", "as in", "no concern", "wetin be", "comot", "find am",
    "join body", "carry go", "japa", "shey", "wahala dey",
}
PIDGIN_DISCOURSE = [
    r"\bna\s+\w+\s+\w+",          # "na me sabi"
    r"\bno\s+be\b",                # "no be lie"
    r"\bdey\s+\w+",                # "dey go", "dey sleep"
    r"\bgo\s+\w+\b",
    r"\bcomot\b",
]

YORUBA_TOKENS = {"bawo", "ekaaro", "eshe", "iro", "owo", "asiri", "ile", "oluwa", "se", "kilode"}
HAUSA_TOKENS  = {"sannu", "yaya", "kuna", "lafiya", "menene", "ina", "ne", "ce"}
IGBO_TOKENS   = {"kedu", "biko", "ndewo", "ego", "ulo", "nna", "nne", "obi", "kelechi"}


def _normalised(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _bag(text: str) -> set[str]:
    return set(re.findall(r"\b[\w']+\b", text.lower()))


def detect(text: str) -> LangResult:
    if not text or not text.strip():
        return LangResult("unknown", False, {})

    norm = _normalised(text)
    bag = _bag(norm)

    pid_hits = len(bag & PIDGIN_TOKENS) + sum(1 for p in PIDGIN_DISCOURSE if re.search(p, norm))
    yo_hits  = len(bag & YORUBA_TOKENS)
    ha_hits  = len(bag & HAUSA_TOKENS)
    ig_hits  = len(bag & IGBO_TOKENS)

    # Run a baseline langid in parallel (e.g. fasttext lid176)
    baseline = _fasttext_lang(norm)        # returns ('en', 0.92) etc.

    scores = {
        "pid": pid_hits / max(1, len(bag)),
        "yo":  yo_hits  / max(1, len(bag)),
        "ha":  ha_hits  / max(1, len(bag)),
        "ig":  ig_hits  / max(1, len(bag)),
    }
    if baseline:
        scores[baseline[0]] = max(scores.get(baseline[0], 0.0), baseline[1] * 0.5)

    # Pidgin override: if pidgin score is > 0.10 of tokens AND >= 2 hits,
    # promote it above any "en" baseline result.
    if pid_hits >= 2 and scores["pid"] >= 0.10:
        scores["pid"] = max(scores["pid"], 0.6)

    dominant = max(scores, key=scores.get)
    second   = sorted(scores.values(), reverse=True)[1] if len(scores) > 1 else 0.0
    mixed    = (second / max(scores[dominant], 1e-6)) > 0.5

    return LangResult(dominant=dominant, mixed=mixed, scores=scores)
```

### 5.3 Evaluation hook

Carry the `language_detected` and `mixed` flags on every conversation turn. They are essential for the thesis evaluation (language-detection F1, code-switch handling).

---

## 6. Prompt Builder

The prompt builder is **the only place** language behaviour is enforced. It is also the most product-defining component of the system.

### 6.1 Template structure

```
SYSTEM PROMPT
─────────────
1. Identity:   "You are <BUSINESS_NAME>'s WhatsApp assistant."
2. Mission:    "Help customers with questions about products, pricing,
                delivery, and policies. Be helpful, accurate, and brief."
3. Tone block: <preset instruction from §4.3>
4. Language directive: <built from detected_language + tenant.languages>
5. Knowledge block: "Use the following knowledge ONLY to answer.
                     If the answer isn't in here, say you'll check
                     and offer to involve a human."
6. Knowledge:  <retrieved chunks formatted by RetrievalService>
7. Brand voice: <up to 3 example utterances from tenant>
8. Hard rules: never invent prices, never invent policies,
               never reveal you're an AI unless asked,
               never insult or argue.
9. Pidgin grammar block (only when language is pid or mixed-pid).
10. Response format: "Reply in 1-3 short sentences. WhatsApp-style."

USER PROMPT
───────────
[Conversation so far]
<turn n-3 ... n-1>

[New customer message]
"<user_text>"

[If escalation rule fired] (orchestrator will set this)
"Note: this query may need human help. Acknowledge and reassure."
```

### 6.2 Pidgin grammar block

Lifted from real Pidgin discourse, this block is what stops the LM sounding like an American doing a Nigerian accent:

```
PIDGIN GRAMMAR (follow strictly when replying in Pidgin):
- 'am' = him/her/it (3rd-person object). Never 'I am'.
- 'e' or 'im' = he/she. 'no be say because im old, e no fit run' is correct.
- 'dey' = is/are (continuous). 'I dey here' = 'I am here'.
- 'wetin' = what; 'where' = where; 'who' = who.
- Don't translate to a textbook sentence. Match WhatsApp register: short, punchy.
- WRONG: "I will start to sweat" → RIGHT: "sweat dey kill me"
- WRONG: "make haste come" → RIGHT: "come quick"
- WRONG: "cool us down" → RIGHT: "make body cool"
- Don't mix up 'am', 'me', 'im', 'e'. If you mean yourself, say 'me'.
- Don't add filler words: no 'direct', no 'basically', no 'actually'.
- 1–3 sentences. No hashtags. No quotation marks around your reply.
```

### 6.3 Implementation

```python
# core/prompt_builder.py
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .persona import TenantConfig
    from .retrieval import Hit


_TONE_PRESETS = {
    "formal": (
        "Reply in clear, polite English. Use full sentences. "
        "Address the customer politely; only use 'sir/ma' if they used a formal register first."
    ),
    "casual": (
        "Reply in friendly conversational English. Light contractions are fine. "
        "Avoid slang the customer didn't use first."
    ),
    "pidgin_friendly": (
        "If the customer wrote Pidgin, reply in Pidgin. "
        "If they wrote English, reply in English with a warm Nigerian register. "
        "Never translate yourself."
    ),
    "youthful": (
        "Match a Gen-Z Nigerian register. Light emoji ok if the customer used one first. "
        "Stay short and lively."
    ),
}

_PIDGIN_GRAMMAR_BLOCK = """\
PIDGIN GRAMMAR (follow strictly when replying in Pidgin):
- 'am' = him/her/it (3rd-person object). Never 'I am'.
- 'e' or 'im' = he/she.
- 'dey' = is/are (continuous).
- 'wetin' = what; 'where' = where; 'who' = who.
- Match WhatsApp register: short, punchy. Don't translate to textbook English.
- WRONG: 'cool us down' / 'make haste come' / 'I go start to dey sweat'
- RIGHT: 'make body cool' / 'come quick' / 'sweat dey kill me'
- Don't mix up 'am', 'me', 'im', 'e'. If you mean yourself, say 'me'.
- 1–3 sentences. No hashtags. No quotation marks."""

_HARD_RULES = """\
HARD RULES (never break these):
- If the answer isn't in the knowledge above, say so. Do NOT invent prices, sizes, dates, or policies.
- Don't argue or insult the customer.
- If the customer asks something off-topic for this business, politely steer back.
- Reply in 1–3 short sentences. WhatsApp-style. No hashtags."""


def _language_directive(detected: str, supported: list[str]) -> str:
    if detected == "pid" and "pid" in supported:
        return "The customer wrote Pidgin. Reply in Pidgin."
    if detected in ("yo", "ha", "ig") and detected in supported:
        names = {"yo": "Yoruba", "ha": "Hausa", "ig": "Igbo"}
        return f"The customer wrote {names[detected]}. Reply briefly in {names[detected]}; use English for prices and SKUs."
    return "Reply in English."


def build_prompt(*,
                 tenant_config: "TenantConfig",
                 retrieved_chunks: list["Hit"],
                 history: list[dict],
                 user_message: str,
                 detected_language: str,
                 escalation_hint: str = "") -> tuple[str, str]:
    tone_block = _TONE_PRESETS.get(tenant_config.tone, _TONE_PRESETS["casual"])

    knowledge = "\n".join(
        f"- [{h.document_type}/{h.section or '-'}] {h.text[:500].strip()}"
        for h in retrieved_chunks[:5]
    ) or "(no specific knowledge retrieved for this query)"

    brand_voice = ""
    if tenant_config.brand_voice_examples:
        joined = "\n".join(f'- "{ex}"' for ex in tenant_config.brand_voice_examples[:3])
        brand_voice = f"\nBrand voice (echo this energy, don't copy):\n{joined}"

    pidgin_block = _PIDGIN_GRAMMAR_BLOCK if detected_language == "pid" else ""

    system = (
        f"You are {tenant_config.business_name}'s WhatsApp assistant. "
        f"{tenant_config.tagline}\n\n"
        f"{tone_block}\n\n"
        f"{_language_directive(detected_language, tenant_config.languages)}\n\n"
        f"USE THIS KNOWLEDGE ONLY:\n{knowledge}\n"
        f"{brand_voice}\n\n"
        f"{pidgin_block}\n\n"
        f"{_HARD_RULES}"
    ).strip()

    history_block = ""
    if history:
        formatted = []
        for t in history[-6:]:
            role = "Customer" if t["role"] == "user" else "Assistant"
            formatted.append(f"{role}: {t['text']}")
        history_block = "Conversation so far:\n" + "\n".join(formatted) + "\n\n"

    esc_block = f"\n\n[Internal note: {escalation_hint}]" if escalation_hint else ""

    user = f"{history_block}New customer message:\n\"{user_message}\"{esc_block}\n\nReply:"
    return system, user
```

---

## 7. Guardrails

### 7.1 Implementation

```python
# core/guards.py
import re
from dataclasses import dataclass

_NGN_PRICE = re.compile(r"(?:₦|N|NGN)\s?\d{2,7}(?:[.,]\d{1,3})?", re.IGNORECASE)
_BVN_NIN  = re.compile(r"\b\d{11}\b")
_CARD     = re.compile(r"\b(?:\d{4}[\s-]?){3}\d{4}\b")
_PHONE    = re.compile(r"(?:\+234|0)[789][01]\d{8}")


@dataclass
class GuardResult:
    final_text: str
    mutated: bool
    escalated: bool
    reason: str


def apply_guards(response_text: str, *,
                 retrieved_text_blob: str,
                 tenant_config,
                 user_message: str,
                 detected_language: str) -> GuardResult:
    text = response_text.strip().strip('"').strip("'")
    mutated, escalated, reason = False, False, ""

    # 1. price hallucination -- response contains a price not present in retrieved chunks
    response_prices = set(m.group(0) for m in _NGN_PRICE.finditer(text))
    if response_prices:
        retrieved_prices = set(m.group(0) for m in _NGN_PRICE.finditer(retrieved_text_blob))
        invented = response_prices - retrieved_prices
        if invented:
            text = (
                f"{tenant_config.fallback} "
                "(I'd rather confirm the exact price with my colleague than guess.)"
            )
            mutated = True
            escalated = True
            reason = f"hallucinated_price:{','.join(invented)}"
            return GuardResult(text, mutated, escalated, reason)

    # 2. PII redaction
    new_text = _BVN_NIN.sub("[REDACTED-ID]", text)
    new_text = _CARD.sub("[REDACTED-CARD]", new_text)
    new_text = _PHONE.sub("[REDACTED-PHONE]", new_text)
    if new_text != text:
        text, mutated = new_text, True

    # 3. tenant escalation rules
    for rule in tenant_config.escalation_rules:
        if rule.type == "phrase" and any(p.lower() in user_message.lower() for p in rule.patterns):
            escalated = True
            reason = f"escalation_phrase:{rule.patterns[0]}"
        elif rule.type == "amount_over":
            for m in _NGN_PRICE.finditer(user_message):
                amount = float(re.sub(r"[^\d.]", "", m.group(0)) or 0)
                if amount >= (rule.threshold or 0):
                    escalated = True
                    reason = f"amount_over:{int(amount)}"
                    break

    # 4. length guard
    if len(text) > 800:
        text = text[:780].rsplit(" ", 1)[0] + "..."
        mutated = True

    return GuardResult(text, mutated, escalated, reason)
```

---

## 8. Conversation Orchestrator

The orchestrator is the only place where the pipeline is composed. It takes a `CanonicalMessage` and returns an `OrchestrationResult` (and side-effects: persists turn, dispatches handoff event).

```python
# core/orchestrator.py
import time
from uuid import uuid4

class ConversationOrchestrator:
    def __init__(self, *, persona, retrieval, lang, prompts, lm,
                 guards, history, audit, dispatcher) -> None:
        self.persona = persona
        self.retrieval = retrieval
        self.lang = lang
        self.prompts = prompts
        self.lm = lm
        self.guards = guards
        self.history = history
        self.audit = audit
        self.dispatcher = dispatcher           # WhatsApp / widget sender

    def handle(self, msg) -> "OrchestrationResult":
        latencies: dict[str, float] = {}
        t0 = time.perf_counter()

        cfg = self.persona.get(msg.tenant_id)
        latencies["config_ms"] = (time.perf_counter() - t0) * 1000

        # 1. history
        t = time.perf_counter()
        history = self.history.last_n(msg.tenant_id, msg.sender_id, n=6)
        latencies["history_ms"] = (time.perf_counter() - t) * 1000

        # 2. language detect
        t = time.perf_counter()
        lang_res = self.lang.detect(msg.text)
        latencies["lang_ms"] = (time.perf_counter() - t) * 1000

        # 3. canonical-answer short-circuit
        canonical = self.retrieval.fetch_canonical_answer(msg.tenant_id, msg.text)

        # 4. weighted retrieval
        t = time.perf_counter()
        if canonical:
            hits = [canonical]
        else:
            hits = self.retrieval.search_weighted(
                msg.tenant_id, msg.text,
                weights=cfg.retrieval_weights,
                top_k=7,
            )
        latencies["retrieval_ms"] = (time.perf_counter() - t) * 1000

        # 5. build prompt
        t = time.perf_counter()
        history_msgs = [{"role": h.role, "text": h.text} for h in history]
        system, user = self.prompts.build(
            tenant_config=cfg,
            retrieved_chunks=hits,
            history=history_msgs,
            user_message=msg.text,
            detected_language=lang_res.dominant,
        )
        latencies["prompt_ms"] = (time.perf_counter() - t) * 1000

        # 6. call LM
        t = time.perf_counter()
        lm_resp = self.lm.complete(system=system, user=user,
                                   temperature=0.4, max_tokens=400)
        latencies["lm_ms"] = (time.perf_counter() - t) * 1000

        # 7. guardrails
        t = time.perf_counter()
        retrieved_blob = " ".join(h.text for h in hits)
        guarded = self.guards.apply(
            lm_resp.text,
            retrieved_text_blob=retrieved_blob,
            tenant_config=cfg,
            user_message=msg.text,
            detected_language=lang_res.dominant,
        )
        latencies["guards_ms"] = (time.perf_counter() - t) * 1000

        # 8. persist + dispatch
        turn_id = uuid4()
        self.history.append(msg.tenant_id, msg.sender_id, {
            "role": "user", "text": msg.text, "ts": msg.received_at.isoformat(),
        })
        self.history.append(msg.tenant_id, msg.sender_id, {
            "role": "assistant", "text": guarded.final_text,
            "ts": time.time(),
        })

        self.audit.write(
            tenant_id=msg.tenant_id,
            conversation_id=msg.sender_id,
            turn_id=turn_id,
            user_text=msg.text,
            retrieved_chunk_ids=[h.chunk_id for h in hits],
            system_prompt=system,
            user_prompt=user,
            response_text=guarded.final_text,
            model=lm_resp.model,
            latency_breakdown=latencies,
            escalated=guarded.escalated,
            language=lang_res.dominant,
        )

        if guarded.escalated:
            self.dispatcher.dispatch_handoff(msg.tenant_id, msg.sender_id, guarded.reason)

        return OrchestrationResult(
            reply_text=guarded.final_text,
            escalated=guarded.escalated,
            escalation_reason=guarded.reason or None,
            detected_language=lang_res.dominant,
            retrieval_count=len(hits),
            latency_breakdown=latencies,
            turn_id=turn_id,
        )
```

---

## 9. Ingestion Pipeline

Worker-side. A single function dispatched by RQ.

```python
# workers/ingestion.py
def ingest_document(tenant_id, document_id, s3_key, document_type):
    raw_path = download_from_r2(s3_key)
    text = extract_text(raw_path, document_type)        # pdf/docx/xlsx/csv/txt
    chunks = semantic_chunk(text, target=512, overlap=50)
    enriched = []
    for ch in chunks:
        enriched.append({
            "text": ch.text,
            "document_id": str(document_id),
            "document_type": document_type,
            "section": ch.section,
            "language_hint": detect_chunk_language(ch.text),
            "boost": 1.5 if document_type == "manual_faq" else 1.0,
            "metadata_json": json.dumps(ch.metadata),
        })

    embeddings = embedder.encode([c["text"] for c in enriched],
                                 batch_size=64, normalize_embeddings=True)
    rows = [{**c, "embedding": emb.tolist()} for c, emb in zip(enriched, embeddings)]

    coll = f"kb_{tenant_id.hex[:12]}"
    vector_client.insert(collection_name=coll, data=rows)
    update_document_status(document_id, "ready")
```

### 9.1 Chunking strategy

- **PDF / DOCX:** split by paragraphs first; merge until ~512 tokens; keep headings as `section` metadata.
- **CSV / XLSX (catalogue):** one row per chunk, with column names baked into the chunk text (`Product: <name> | Price: ₦<x> | Size: <y> | In stock: <z>`).
- **Manual FAQ:** the question becomes the chunk text; the answer goes into `metadata.canonical_answer` and the chunk gets `boost=1.5`.

### 9.2 Re-embedding

When an SME edits a chunk in the dashboard, the worker:

1. Marks the old chunk soft-deleted in the collection.
2. Re-embeds the new text.
3. Inserts a new row.

This keeps audit history (the old chunk_id remains referable from past audit records) and is operationally simpler than in-place update.

---

## 10. Fine-tuning the Nigeria-Specific LM

### 10.1 Strategy

Single-stage **SFT (supervised fine-tuning) with LoRA / QLoRA** on a curated Nigerian conversational corpus. No RLHF for v1 — costly to set up and not needed for the thesis story.

### 10.2 Base model

Default: **Llama 3.1 8B Instruct**. Tradeoffs:

| Candidate | Pros | Cons |
|---|---|---|
| Llama 3.1 8B | Excellent open weights, mature LoRA tooling, fits a single 24GB GPU at int8 | Limited African-language pretraining |
| Mistral 7B | Smaller, fast inference | Lower quality on instruction-following than Llama 3.1 |
| Mixtral 8×7B | High quality | Needs 80GB GPU at fp16, expensive |
| InkubaLM (Lelapa) | African-language pretraining baked in | Ecosystem younger, harder tooling |
| Awarri Eko / EkoLM | Nigeria-specific | Limited public tooling at writing time |

A defensible thesis move is to **fine-tune two bases (Llama 3.1 8B and InkubaLM)** and compare — this becomes a section in chapter 5.

### 10.3 Corpus

| Source | Approx. size after cleaning | Use |
|---|---|---|
| **NaijaSenti** tweets (English, Pidgin, YO, HA, IG sentiment-labelled) | ~30k | Pidgin + minority-language exposure |
| **MasakhaNEWS** (news in YO/HA/IG) | ~15k passages | Formal-register Nigerian-language exposure |
| **Nairaland forum** (filtered, scraped where ToS permits) | ~50k posts | Conversational discourse, Pidgin patterns |
| Curated **English ↔ Pidgin pairs** (from MakerOps / Lelapa / Masakhane resources) | ~20k pairs | Translation calibration |
| **Synthesised SME Q/A** pairs (generated by GPT-4 from sample SME catalogues, then filtered by Nigerian annotators) | ~10k | Domain shape: customer-service register |
| **Pidgin discourse corpora** (BBC Pidgin transcripts where licensing allows, real WhatsApp-style transcripts donated under consent) | ~5k | Authentic conversational rhythm |

Each example is formatted as a chat-style instruction:

```json
{"messages": [
  {"role": "system", "content": "<a generic SME assistant system prompt>"},
  {"role": "user", "content": "<utterance, often Pidgin or code-switched>"},
  {"role": "assistant", "content": "<a faithful Nigerian-register response>"}
]}
```

### 10.4 Training recipe

- Library: `unsloth` for speed, fall back to `peft + trl` for compatibility.
- Hyperparameters (starting point):
  - LoRA rank `r=16`, `alpha=32`, dropout `0.05`.
  - Target modules: `q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj`.
  - LR `2e-4`, cosine schedule, warmup ratio `0.03`.
  - 3 epochs, global batch size 32 (gradient accumulation 4 on a single A100).
  - Max sequence length 2048.
- Eval split: 5% held out, plus a hand-curated 500-example **NigerianBench** set (see `05_IMPLEMENTATION_AND_EVAL.md` §3).

### 10.5 Serving

- After training, merge LoRA into base weights for inference, then quantise to **AWQ int4** for the production serve.
- Run under **vLLM** with continuous batching on a single A100 / L40S.
- Expose an OpenAI-compatible chat-completions endpoint on an internal port; only the API service can reach it.

### 10.6 Evaluation in thesis

- BLEU / chrF for translation tasks.
- F1 for language detection (the Pidgin-aware detector built in §5 is itself evaluated).
- Likert-scaled human evaluation (helpfulness / correctness / naturalness) on 200 held-out customer queries by 3 Nigerian annotators per item.
- Pairwise win-rate against the un-fine-tuned base and against GPT-4o.
- Inter-annotator agreement (Cohen's κ) reported.

Full methodology in `05_IMPLEMENTATION_AND_EVAL.md`.

---

## 11. Why these design choices

A handful of the decisions above are non-obvious. Their justifications:

1. **The `LMClient` wraps OpenAI-compatible APIs only.** vLLM, Groq, and HF Endpoints all speak the OpenAI Chat schema. This means swapping providers is genuinely a config change. It also makes the audit table and Langfuse traces uniform.

2. **Per-tenant collections (Option A) over per-tenant filters (Option B).** At pilot scale, the operational overhead is trivial (a few hundred collections); the correctness guarantee is structural. As tenant count grows we can switch by introducing a `KBStore` interface that hides the choice.

3. **Boost-aware retrieval scoring.** Multiplying cosine similarity by `boost` is mathematically a hack but operationally clean: a `manual_faq` row with `boost=1.5` can outrank a generic-but-slightly-more-similar policy chunk, which is the desired editorial behaviour.

4. **Separate `PromptBuilder` from `LMClient`.** Prompt logic is extremely Nigeria-specific (Pidgin grammar block, tone presets); model invocation is generic. Keeping them apart means the Pidgin work is portable across model swaps.

5. **Pidgin-aware language detection lives in this codebase, not a third-party library.** No third-party langid currently handles Pidgin well, so it's a small but defensible thesis sub-contribution.

6. **No RLHF in v1.** SFT with high-quality data already handles register and code-switching well; RLHF requires a reward model and a couple of weeks of labelling that don't move the thesis story enough to justify.

7. **Hard rule: never invent prices.** This is the single most important guardrail. SMEs operate on tight margins — a hallucinated price is a real-money commitment they didn't authorise. The guard's behaviour: if a price appears in the response that wasn't in retrieved chunks, **rewrite the response and escalate**. This is more conservative than "warn the user" but it's the right tradeoff in this domain.

8. **Audit table is verbose by design.** Storing the exact prompt + retrieved chunk IDs + model name + latencies per stage is the only way to credibly defend evaluation in the thesis. It also enables ablations after the pilot ("what if we had used GPT-4 for these turns?") without re-running the pilot.
