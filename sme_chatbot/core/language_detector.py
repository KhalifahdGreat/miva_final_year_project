"""Pidgin-aware language detection for Nigerian customer-service input.

Off-the-shelf langid systems (FastText `lid.176`, langdetect) systematically
misclassify Nigerian Pidgin as English (≥95% of the time on held-out Pidgin
sets) because they were trained predominantly on standard-register news text.

This module supplements a baseline detector with a hand-curated lexical and
discourse-marker layer for:

    Pidgin / Yoruba / Hausa / Igbo

and reports a `mixed=True` flag when two or more languages co-occur within
a single utterance (code-switching).

Public API:

    detect(text: str) -> LangResult
    expand_query_for_retrieval(text: str) -> str

It deliberately has **no external dependencies** so it runs at micro-second
latency on a laptop and is trivially unit-testable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Lexicons — high-precision tokens per language.
#
# Sources for the Pidgin set: empirical extraction from NaijaSenti tweets,
# Nairaland forum posts, and BBC Pidgin transcripts.  Confirmed Pidgin only —
# tokens that overlap with English (e.g. "go", "see") are NOT included.
# ---------------------------------------------------------------------------


PIDGIN_TOKENS: frozenset[str] = frozenset(
    {
        "abeg", "wahala", "wetin", "dey", "una", "sef", "sha", "wey", "abi",
        "biko", "omo", "ehn", "walahi", "oga", "dem", "shey", "japa", "mumu",
        "sabi", "comot", "ginger", "chai", "nawa", "abasi", "naso", "shebi",
        "kuku", "pikin", "yawa", "shakara", "kpekus", "shege",
    }
)

# Multi-word Pidgin discourse markers.
# Bare "na <word>" is NOT included: Igbo uses "na" as a high-frequency
# particle ("and / that / at") and that pattern was flipping Igbo → Pidgin.
PIDGIN_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bno\s+be\b", re.IGNORECASE),
    re.compile(r"\bna\s+(me|so|him|am|wetin|true|lie|dat|dis|the)\b", re.IGNORECASE),
    re.compile(r"\be\s+dey\b", re.IGNORECASE),
    re.compile(r"\bdey\s+\w+", re.IGNORECASE),
    re.compile(r"\bi\s+go\s+\w+", re.IGNORECASE),
    re.compile(r"\bno\s+fit\b", re.IGNORECASE),
    re.compile(r"\bdon\s+\w+", re.IGNORECASE),
    re.compile(r"\bmake\s+i\b", re.IGNORECASE),
    re.compile(r"\bsmall\s+small\b", re.IGNORECASE),
    re.compile(r"\bwetin\s+dey\b", re.IGNORECASE),
    re.compile(r"\bwetin\s+be\b", re.IGNORECASE),
    re.compile(r"\bi\s+fit\b", re.IGNORECASE),
    re.compile(r"\bfor\s+ground\b", re.IGNORECASE),
    re.compile(r"\bhow\s+much\s+be\b", re.IGNORECASE),
]

# One of these alone is enough to claim Pidgin (they almost never appear in EN/YO/HA/IG).
_PIDGIN_ANCHORS = frozenset({"una", "wetin", "abeg", "dey", "wahala", "sabi", "comot", "pikin"})

YORUBA_TOKENS: frozenset[str] = frozenset(
    {
        # Greetings + courtesy
        "bawo", "ekaaro", "ekaasan", "ekuirole", "ekaale", "eshe", "ese",
        "kaaro", "jowo", "joo",
        # Pronouns + frequent function words
        "mo", "mi", "re", "wa", "yin", "won", "awon", "iwo", "emi",
        "ti", "ni", "yi", "yen", "naa", "lo", "lori",
        # Frequent content words
        "owo", "asiri", "ile", "oluwa", "kilode", "omode", "iyawo", "oko",
        "ore", "ola", "egbon", "aburo", "iya", "baba", "omoluabi", "omolabi",
        # High-frequency Yoruba verbs (commerce + everyday)
        "fe", "fẹ", "ra", "ta", "so", "bo", "je", "jẹ",
        "gba", "fun", "ko", "kọ", "se", "ṣe", "ri", "ba", "wo",
        "sii", "nsii", "tii", "pari", "tan", "gbe", "ran",
        # Commerce / food / time — the words customers actually type
        "elo", "adie", "pelu", "ati", "iyan", "obe", "amala", "ewedu",
        "gbegiri", "igba", "nibo", "ojo", "isimi", "foonu", "oju", "loni",
        "nigba", "ma", "pele", "dupe", "odun", "owuro", "ale", "osan",
        "ounje", "onje", "owo", "owo", "sowo", "tita", "rira",
        "se", "nko", "boya", "rara", "padi",
    }
)

HAUSA_TOKENS: frozenset[str] = frozenset(
    {
        "sannu", "yaya", "kuna", "lafiya", "menene", "ina", "ne", "ce",
        "naka", "naki", "yake", "take", "ni", "kai", "ki", "shi", "ita",
        "mu", "ku", "su", "wani", "wanda", "ban", "kasa", "yara", "abinci",
        "ruwa", "gida", "uba", "uwa", "yaro", "yarinya", "malam", "barka",
        "nagode", "tafiya", "shawara",
        # Commerce / time / food — eval + live chat
        "nawa", "kaza", "da", "miyar", "lokaci", "kuke", "budewa", "rufewa",
        "cikin", "sayar", "saye", "wurin", "ajiye", "motoci", "kuma",
        "yaushe", "nawa", "farashi", "kudi", "kayan", "abinci",
        "bude", "rufe", "zuwa", "daga", "akwai", "babu",
    }
)

IGBO_TOKENS: frozenset[str] = frozenset(
    {
        "kedu", "ndewo", "biko", "ego", "ulo", "nna", "nne", "obi",
        "anyi", "unu", "ha", "gi", "ya", "m", "nke", "ihe",
        "nwa", "nwoke", "nwanyi", "agwa", "iri", "ngwa",
        "ndi", "mba", "ee", "eziokwu", "okwukwo", "ahia",
        "ezigbo",
        # Commerce / time / food — eval + live chat
        "ole", "okuko", "bu", "ofe", "oge", "ebee", "di", "nwere",
        "ebe", "ugbo", "ala", "zuta", "zụta", "re", "ere",
        "emeghe", "emechi", "edozi", "gote", "azụta", "azuta",
        "mgbe", "kedu", "biko", "nri", "ofe", "ji", "akpu",
        "gịnị", "gini", "olee", "ego", "ahịa", "ahia",
    }
)

# Words to actively exclude when present alongside Pidgin tokens — these are
# extremely common in English and would otherwise drag the detector toward EN.
_ENGLISH_NOISE = frozenset(
    {"the", "a", "an", "is", "are", "was", "were", "and", "or", "but"}
)

# English glosses appended to the retrieval query so MiniLM can match an
# English knowledge base when the customer wrote yo / ha / ig.
_RETRIEVAL_GLOSS: dict[str, str] = {
    "elo": "how much price",
    "nawa": "how much price",
    "ole": "how much price",
    "ego": "price money",
    "ra": "buy",
    "fe": "want",
    "fẹ": "want",
    "ta": "sell",
    "sayar": "sell",
    "saye": "buy",
    "zuta": "buy",
    "ere": "sell",
    "adie": "chicken",
    "okuko": "chicken",
    "kaza": "chicken",
    "amala": "amala",
    "ewedu": "ewedu soup",
    "iyan": "pounded yam",
    "obe": "soup",
    "ofe": "soup",
    "gbegiri": "gbegiri soup",
    "nibo": "where location",
    "ebee": "where location",
    "ina": "where location",
    "nigba": "when time",
    "igba": "when time",
    "oge": "time",
    "lokaci": "time",
    "pari": "ready finish",
    "tan": "finished sold out",
    "sii": "open",
    "nsii": "open",
    "budewa": "open",
    "emeghe": "open",
    "emechi": "close",
    "rufewa": "close",
    "isimi": "sunday",
    "foonu": "phone",
}


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class LangResult:
    dominant: str                    # 'en' | 'pid' | 'yo' | 'ha' | 'ig' | 'unknown'
    mixed: bool                       # at least two languages strongly co-present
    scores: dict[str, float]          # per-language strength in [0, 1+]
    pidgin_hits: int = 0              # diagnostic
    pattern_hits: int = 0             # diagnostic


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


_TOKEN_RE = re.compile(r"\b[\w']+\b")


def _bag(text: str) -> list[str]:
    # Split hyphenated Igbo verbs (na-emeghe, na-ere) so stems are countable.
    normalised = text.lower().replace("-", " ")
    return _TOKEN_RE.findall(normalised)


def _promote(scores: dict[str, float], lang: str, hits: int, n: int) -> None:
    """Lift an indigenous language over the English residual when signal is real."""
    density = hits / max(1, n)
    if hits >= 2 or (hits >= 1 and density >= 0.20):
        scores[lang] = max(scores[lang], scores.get("en", 0.0) + 0.12, 0.55)


def detect(text: str) -> LangResult:
    """Detect the dominant language and mixed-language flag."""
    if not text or not text.strip():
        return LangResult("unknown", False, {})

    tokens = _bag(text)
    if not tokens:
        return LangResult("unknown", False, {})

    bag = set(tokens)

    pid_token_hits = len(bag & PIDGIN_TOKENS)
    pid_pattern_hits = sum(1 for p in PIDGIN_PATTERNS if p.search(text))
    pid_total = pid_token_hits + pid_pattern_hits

    yo_hits = len(bag & YORUBA_TOKENS)
    ha_hits = len(bag & HAUSA_TOKENS)
    ig_hits = len(bag & IGBO_TOKENS)

    n = max(1, len(tokens))

    scores: dict[str, float] = {
        "pid": pid_total / n,
        "yo":  yo_hits   / n,
        "ha":  ha_hits   / n,
        "ig":  ig_hits   / n,
    }

    other = PIDGIN_TOKENS | YORUBA_TOKENS | HAUSA_TOKENS | IGBO_TOKENS
    english_count = sum(
        1
        for t in tokens
        if t not in other and t not in _ENGLISH_NOISE
    )
    scores["en"] = english_count / n

    strong_pidgin = (
        pid_total >= 2
        or (scores["pid"] >= 0.08 and pid_pattern_hits >= 1)
        or (pid_pattern_hits >= 1 and pid_token_hits >= 1)
        or bool(bag & _PIDGIN_ANCHORS)
    )
    # Do not promote Pidgin when an indigenous language already has a
    # clearer lexical claim (stops Igbo "na" leftovers and Hausa "nawa").
    indigenous_lead = max(yo_hits, ha_hits, ig_hits)
    if strong_pidgin and indigenous_lead < 2:
        scores["pid"] = max(scores["pid"], scores["en"] + 0.10, 0.55)

    _promote(scores, "yo", yo_hits, n)
    _promote(scores, "ha", ha_hits, n)
    _promote(scores, "ig", ig_hits, n)

    # Hausa "nawa ne …" is a price question, not Pidgin "nawa" (trouble).
    if "nawa" in bag and ha_hits >= 2:
        scores["ha"] = max(scores["ha"], scores.get("pid", 0.0) + 0.15, 0.60)

    dominant = max(scores, key=lambda k: scores[k])

    ordered = sorted(scores.values(), reverse=True)
    second = ordered[1] if len(ordered) > 1 else 0.0
    best = ordered[0] or 1e-6
    mixed = (second / best) >= 0.5 and best > 0.0

    return LangResult(
        dominant=dominant,
        mixed=mixed,
        scores=scores,
        pidgin_hits=pid_token_hits,
        pattern_hits=pid_pattern_hits,
    )


def expand_query_for_retrieval(text: str) -> str:
    """Append English glosses so RAG can hit an English knowledge base."""
    extras: list[str] = []
    seen: set[str] = set()
    for tok in _bag(text):
        gloss = _RETRIEVAL_GLOSS.get(tok)
        if gloss and gloss not in seen:
            extras.append(gloss)
            seen.add(gloss)
    if not extras:
        return text
    return f"{text} {' '.join(extras)}"


# ---------------------------------------------------------------------------
# Friendly aliases
# ---------------------------------------------------------------------------


LANGUAGE_NAMES = {
    "en": "English",
    "pid": "Nigerian Pidgin",
    "yo": "Yoruba",
    "ha": "Hausa",
    "ig": "Igbo",
    "unknown": "Unknown",
}
