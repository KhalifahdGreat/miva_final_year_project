"""Pidgin-aware language detection for Nigerian customer-service input.

Off-the-shelf langid systems misclassify Nigerian Pidgin as English. This
module combines four cheap signals, with no extra dependencies:

    1. Orthography  — Yoruba/Igbo/Hausa special letters and tone marks
    2. Function words — high-precision closed-class lexicons (folded ASCII)
    3. Discourse patterns — multi-word regexes per language
    4. Loanword ignore  — menu/place/English words never pick a language

Public API:

    detect(text: str) -> LangResult
    expand_query_for_retrieval(text: str) -> str
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Loanwords / named entities — never count toward yo/ha/ig/pid
# ---------------------------------------------------------------------------

_LOANWORDS = frozenset(
    {
        "amala", "ewedu", "gbegiri", "iyan", "jollof", "moimoi", "moi",
        "egusi", "ogbono", "efo", "edikaikong", "suya", "kilishi", "zobo",
        "rice", "fried", "chicken", "goat", "beef", "fish", "catfish",
        "pepper", "soup", "plate", "wrap", "naira", "nairas",
        "lagos", "ikeja", "mushin", "abuja", "kano", "ibadan", "ph",
        "mainland", "island", "allen", "sunday", "monday", "saturday",
        "whatsapp", "transfer", "card", "cash", "delivery", "order",
        "iphone", "sku", "menu", "kitchen",
        "okuko", "kaza", "adie", "ofe", "obe", "akpu", "ji",
    }
)

_ENGLISH_NOISE = frozenset(
    {"the", "a", "an", "is", "are", "was", "were", "and", "or", "but",
     "to", "for", "of", "in", "on", "at", "with", "you", "your", "do"}
)


# ---------------------------------------------------------------------------
# Orthography
# ---------------------------------------------------------------------------

_YO_LETTERS = set("ẹọṣń")
_HA_LETTERS = set("ƙɗɓ")
_IG_LETTERS = set("ịụṅ")
_TONE_MARKS = set("́̀̂̄")  # combining acute/grave/circumflex/macron


# ---------------------------------------------------------------------------
# Lexicons (ASCII-folded). Function words outweigh content words.
# ---------------------------------------------------------------------------

PIDGIN_TOKENS: frozenset[str] = frozenset(
    {
        "abeg", "wahala", "wetin", "dey", "una", "sef", "sha", "wey", "abi",
        "biko", "omo", "ehn", "walahi", "oga", "dem", "shey", "japa", "mumu",
        "sabi", "comot", "ginger", "chai", "nawa", "abasi", "naso", "shebi",
        "kuku", "pikin", "yawa", "shakara", "shege", "fit", "don",
    }
)
_PIDGIN_ANCHORS = frozenset(
    {"una", "wetin", "abeg", "dey", "wahala", "sabi", "comot", "pikin"}
)

YORUBA_TOKENS: frozenset[str] = frozenset(
    {
        "bawo", "ekaaro", "ekaasan", "ekuirole", "ekaale", "eshe", "ese",
        "kaaro", "jowo", "joo", "pele", "dupe", "epele",
        "mo", "mi", "re", "wa", "yin", "won", "awon", "iwo", "emi",
        "ti", "ni", "yi", "yen", "naa", "lo", "lori", "ati",
        "elo", "pelu", "nibo", "nigba", "igba", "kilode", "nko",
        "fe", "ra", "ta", "se", "je", "gba", "fun", "ko", "ri", "wo",
        "sii", "nsii", "tii", "pari", "tan", "gbe", "ran", "pase",
        "meloo", "iye", "owo", "apo", "merin", "eran", "ewure",
        "bakan", "gbe", "sile", "loni", "ojo", "isimi", "foonu",
        "oju", "ounje", "onje", "sowo", "rira", "boya", "rara",
        "padi", "omode", "iyawo", "egbon", "aburo", "omoluabi",
        "asiri", "ile", "oluwa",
    }
)
_YO_FUNCTION = frozenset(
    {
        "mo", "mi", "wa", "yin", "won", "emi", "iwo", "ati", "ni", "ti",
        "elo", "nibo", "nigba", "kilode", "jowo", "bawo", "fe", "se",
        "meloo", "iye", "bakan",
    }
)

HAUSA_TOKENS: frozenset[str] = frozenset(
    {
        "sannu", "yaya", "kuna", "lafiya", "menene", "ina", "ne", "ce",
        "naka", "naki", "yake", "kai", "shi", "ita",
        "mu", "ku", "su", "wani", "wanda", "ban", "kasa",
        "nawa", "da", "lokaci", "kuke", "budewa", "rufewa", "cikin",
        "sayar", "saye", "wurin", "kuma", "yaushe", "farashi", "farashin",
        "kudi", "bude", "rufe", "zuwa", "daga", "akwai", "babu",
        "zan", "yau", "sai", "dai", "tukuna", "sannan", "tabbatar",
        "hakan", "kawo", "biya", "tasha", "tashar", "mota", "motar",
        "baya", "sanar", "maka", "nagode", "barka", "malam",
        "abinci", "gida", "ruwa", "yaro", "yarinya", "miyar",
        "kawo", "za",
    }
)
_HA_FUNCTION = frozenset(
    {
        "akwai", "nawa", "ne", "ce", "da", "ban", "zan", "sai", "kuna",
        "kuke", "ina", "menene", "yaya", "sannu", "farashi", "farashin",
        "tukuna", "sannan", "daga", "babu", "yaushe",
    }
)

IGBO_TOKENS: frozenset[str] = frozenset(
    {
        "kedu", "ndewo", "biko", "ego", "ulo", "nna", "nne",
        "anyi", "unu", "gi", "nke", "ihe", "nwoke", "nwanyi",
        "ndi", "mba", "ee", "eziokwu", "ahia", "ezigbo",
        "ole", "olee", "bu", "oge", "ebee", "nwere", "ebe",
        "zuta", "ere", "emeghe", "emechi", "edozi", "gote",
        "azuta", "mgbe", "nri", "gini", "biko",
        "ka", "di", "ga",
    }
)
_IG_FUNCTION = frozenset(
    {
        "kedu", "ndewo", "biko", "unu", "anyi", "ebee", "ole", "olee",
        "ego", "nke", "nwere", "gini", "mgbe", "bu",
    }
)

PIDGIN_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bno\s+be\b", re.IGNORECASE),
    re.compile(r"\bna\s+(me|so|him|am|wetin|true|lie|dat|dis|the)\b", re.IGNORECASE),
    re.compile(r"\be\s+dey\b", re.IGNORECASE),
    re.compile(r"\bdey\s+\w+", re.IGNORECASE),
    re.compile(
        r"\bi\s+go\s+(take|pay|come|send|chop|buy|call|see|try|use|give|"
        r"collect|enter|order|check|run|do|fit|go)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bhow\s+i\s+go\b", re.IGNORECASE),
    re.compile(r"\bi\s+wan\b", re.IGNORECASE),
    re.compile(r"\bno\s+wahala\b", re.IGNORECASE),
    re.compile(r"\bmake\s+una\b", re.IGNORECASE),
    re.compile(r"\bno\s+fit\b", re.IGNORECASE),
    re.compile(r"\bdon\s+\w+", re.IGNORECASE),
    re.compile(r"\bmake\s+i\b", re.IGNORECASE),
    re.compile(r"\bsmall\s+small\b", re.IGNORECASE),
    re.compile(r"\bwetin\s+(dey|be)\b", re.IGNORECASE),
    re.compile(r"\bi\s+fit\b", re.IGNORECASE),
    re.compile(r"\bhow\s+much\s+be\b", re.IGNORECASE),
]

_YO_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bmo\s+fe\b", re.IGNORECASE),
    re.compile(r"\belo\s+ni\b", re.IGNORECASE),
    re.compile(r"\bnibo\s+ni\b", re.IGNORECASE),
    re.compile(r"\bnigba\s+wo\b", re.IGNORECASE),
    re.compile(r"\bmeloo\s+ni\b", re.IGNORECASE),
    re.compile(r"\bse\s+e\b", re.IGNORECASE),
]

_HA_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bnawa\s+ne\b", re.IGNORECASE),
    re.compile(r"\bakwai\b", re.IGNORECASE),
    re.compile(r"\bban\s+\w+\b", re.IGNORECASE),
    re.compile(r"\bza\s+a\b", re.IGNORECASE),
    re.compile(r"\bkuna\s+\w+\b", re.IGNORECASE),
    re.compile(r"\bina\s+\w+\b", re.IGNORECASE),
]

_IG_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bego\s+ole\b", re.IGNORECASE),
    re.compile(r"\bebee\s+ka\b", re.IGNORECASE),
    re.compile(r"\bkedu\b", re.IGNORECASE),
    re.compile(r"\bunu\s+na\b", re.IGNORECASE),
    re.compile(r"\bna-e\w+", re.IGNORECASE),
]


_RETRIEVAL_GLOSS: dict[str, str] = {
    "elo": "how much price", "meloo": "how much price",
    "nawa": "how much price", "ole": "how much price", "ego": "price money",
    "ra": "buy", "fe": "want", "ta": "sell", "pase": "order",
    "sayar": "sell", "saye": "buy", "zuta": "buy", "ere": "sell",
    "amala": "amala", "ewedu": "ewedu soup", "iyan": "pounded yam",
    "nibo": "where location", "ebee": "where location", "ina": "where location",
    "nigba": "when time", "oge": "time how long", "lokaci": "time",
    "pari": "ready finish", "tan": "finished sold out",
    "sii": "open", "budewa": "open", "emeghe": "open",
    "emechi": "close", "rufewa": "close", "isimi": "sunday",
    "gbe": "deliver bring", "kawo": "deliver bring",
    "ofe": "soup", "ose": "pepper soup", "afang": "afang soup",
    "kwadebe": "prepare ready time", "ibute": "delivery deliver",
    "ogologo": "how long duration", "tupu": "before until",
    "azu": "fish", "anu": "meat", "ugwu": "ugu pumpkin leaf",
    "karama": "bottle drink", "itinye": "add extra",
    "akwukwo": "vegetable leaf",
}


@dataclass
class LangResult:
    dominant: str
    mixed: bool
    scores: dict[str, float]
    pidgin_hits: int = 0
    pattern_hits: int = 0


_TOKEN_RE = re.compile(r"\b[\w']+\b", re.UNICODE)
_FOLD_MAP = str.maketrans(
    {
        "ẹ": "e", "ọ": "o", "ṣ": "s", "ń": "n",
        "ị": "i", "ụ": "u", "ṅ": "n",
        "ƙ": "k", "ɗ": "d", "ɓ": "b",
    }
)


def _fold(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text.lower())
    stripped = "".join(ch for ch in nfkd if unicodedata.category(ch) != "Mn")
    return stripped.translate(_FOLD_MAP)


def _bag(text: str) -> list[str]:
    return _TOKEN_RE.findall(_fold(text).replace("-", " "))


def _script_bonus(text: str) -> dict[str, float]:
    yo = sum(1 for ch in text.lower() if ch in _YO_LETTERS)
    ha = sum(1 for ch in text.lower() if ch in _HA_LETTERS)
    ig = sum(1 for ch in text.lower() if ch in _IG_LETTERS)
    tones = sum(1 for ch in unicodedata.normalize("NFKD", text) if ch in _TONE_MARKS)
    # Tone marks are used in Yoruba and Igbo; boost both lightly, Yoruba more
    # because SME customers mark Yoruba more often.
    return {
        "yo": 0.18 * yo + 0.06 * tones,
        "ha": 0.22 * ha,
        "ig": 0.18 * ig + 0.03 * tones,
        "pid": 0.0,
        "en": 0.0,
    }


def _count(bag: set[str], lexicon: frozenset[str]) -> int:
    return len((bag - _LOANWORDS) & lexicon)


def detect(text: str) -> LangResult:
    if not text or not text.strip():
        return LangResult("unknown", False, {})

    tokens = _bag(text)
    if not tokens:
        return LangResult("unknown", False, {})

    bag = set(tokens) - _LOANWORDS
    n = max(1, len(tokens))

    pid_tok = _count(bag, PIDGIN_TOKENS)
    yo_tok = _count(bag, YORUBA_TOKENS)
    ha_tok = _count(bag, HAUSA_TOKENS)
    ig_tok = _count(bag, IGBO_TOKENS)

    yo_fn = len(bag & _YO_FUNCTION)
    ha_fn = len(bag & _HA_FUNCTION)
    ig_fn = len(bag & _IG_FUNCTION)

    pid_pat = sum(1 for p in PIDGIN_PATTERNS if p.search(text))
    yo_pat = sum(1 for p in _YO_PATTERNS if p.search(_fold(text)))
    ha_pat = sum(1 for p in _HA_PATTERNS if p.search(_fold(text)))
    ig_pat = sum(1 for p in _IG_PATTERNS if p.search(text) or p.search(_fold(text)))

    # Weighted evidence: function words and patterns beat raw token density.
    scores: dict[str, float] = {
        "pid": (pid_tok + 1.4 * pid_pat) / n,
        "yo":  (yo_tok + 1.2 * yo_fn + 1.4 * yo_pat) / n,
        "ha":  (ha_tok + 1.2 * ha_fn + 1.4 * ha_pat) / n,
        "ig":  (ig_tok + 1.2 * ig_fn + 1.4 * ig_pat) / n,
    }
    bonus = _script_bonus(text)
    for lang, extra in bonus.items():
        scores[lang] = scores.get(lang, 0.0) + extra

    other = PIDGIN_TOKENS | YORUBA_TOKENS | HAUSA_TOKENS | IGBO_TOKENS | _LOANWORDS
    english_count = sum(1 for t in tokens if t not in other and t not in _ENGLISH_NOISE)
    scores["en"] = english_count / n

    indigenous = {"yo": yo_tok + yo_fn + yo_pat, "ha": ha_tok + ha_fn + ha_pat, "ig": ig_tok + ig_fn + ig_pat}
    lead = max(indigenous.values())

    strong_pidgin = (
        pid_tok + pid_pat >= 2
        or bool(bag & _PIDGIN_ANCHORS)
        or (pid_pat >= 1 and pid_tok >= 1)
        or (pid_pat >= 1 and lead < 2)
    )
    if strong_pidgin and lead < 3:
        scores["pid"] = max(scores["pid"], scores["en"] + 0.10, 0.55)

    def _promote(lang: str, evidence: int) -> None:
        if evidence >= 2 or (evidence >= 1 and evidence / n >= 0.18):
            scores[lang] = max(scores[lang], scores.get("en", 0.0) + 0.12, 0.55)

    _promote("yo", indigenous["yo"])
    _promote("ha", indigenous["ha"])
    _promote("ig", indigenous["ig"])

    if "nawa" in bag and indigenous["ha"] >= 2:
        scores["ha"] = max(scores["ha"], scores.get("pid", 0.0) + 0.15, 0.62)

    raw = {
        "yo": indigenous["yo"],
        "ha": indigenous["ha"],
        "ig": indigenous["ig"],
        "pid": pid_tok + pid_pat,
        "en": english_count,
    }
    dominant = max(scores, key=lambda k: (scores[k], raw.get(k, 0)))

    ordered = sorted(scores.values(), reverse=True)
    second = ordered[1] if len(ordered) > 1 else 0.0
    best = ordered[0] or 1e-6
    mixed = (second / best) >= 0.5 and best > 0.0

    return LangResult(
        dominant=dominant,
        mixed=mixed,
        scores=scores,
        pidgin_hits=pid_tok,
        pattern_hits=pid_pat + yo_pat + ha_pat + ig_pat,
    )


def expand_query_for_retrieval(text: str) -> str:
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


LANGUAGE_NAMES = {
    "en": "English",
    "pid": "Nigerian Pidgin",
    "yo": "Yoruba",
    "ha": "Hausa",
    "ig": "Igbo",
    "unknown": "Unknown",
}
