"""Broad edge cases for detection, retrieval gloss, and the price guard."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.guards import apply_guards, extract_naira_amounts
from core.language_detector import detect, expand_query_for_retrieval
from core.tenant_service import default_config

KB = (
    "Amala with ewedu and gbegiri soup costs 3000 naira. "
    "Catfish pepper soup costs 4500 naira. "
    "Delivery within Lagos mainland costs 1000 naira and takes about 45 minutes. "
    "Chilled zobo drink costs 500 naira per cup. "
    "We are closed on Sundays. Open 9am to 9pm. Call 08012345678."
)

PLAYGROUND_IGBO = (
    "Ogologo oge ole ka o ga-ewe tupu i kwadebe ofe ose (pepper soup) "
    "na ofe afang? Ego ole ka a ga-akwụ maka ibute ha? Ọzọkwa, ị nwere ike "
    "itinye azụ na anụ ọzọ, tinyere akwụkwọ ugwu? Achọkwara m karama Coke abụọ."
)

PLAYGROUND_HAUSA = (
    "Akwai Amala da Ewedu; farashin ya kai Naira 3,000. "
    "Sai dai, ban san nawa za a biya don kawo shi Tashar Motar Mushin ba tukuna."
)


def _cfg():
    return default_config("tid-edge", "Mama Put Kitchen")


def _guard(reply: str, lang: str, kb: str = KB):
    return apply_guards(
        reply,
        retrieved_text_blob=kb,
        tenant_config=_cfg(),
        user_message="price?",
        detected_language=lang,
    )


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,lang",
    [
        ("", "unknown"),
        ("   ", "unknown"),
        ("😂😂😂", "unknown"),
        ("???", "unknown"),
        ("Hello, do you ship to Abuja?", "en"),
        ("How much is amala and ewedu with goat meat delivery to Mushin?", "en"),
        ("I go to the shop on Sunday for delivery.", "en"),
        ("Can I take this order for delivery to the island?", "en"),
        ("What time do you open and close?", "en"),
        ("Are you open on Sundays?", "en"),
        ("How much be jollof rice with chicken?", "pid"),
        ("How I go take order food?", "pid"),
        ("Abeg una dey open today?", "pid"),
        ("Wetin be the price of pounded yam and egusi?", "pid"),
        ("I fit pay with card?", "pid"),
        ("You dey open for Sunday?", "pid"),
        ("ABEG UNA DEY OPEN TODAY?", "pid"),
        ("mo fe ra ewedu ati amala", "yo"),
        ("Elo ni amala ati ewedu ati gbegiri?", "yo"),
        ("Nigba wo ni o ma pari", "yo"),
        ("Mo fẹ́ paṣẹ àmàlà àti ewédú; mélòó ni iye owó?", "yo"),
        ("Nibo ni e wa?", "yo"),
        ("Bawo", "yo"),
        ("Nawa ne jollof rice da kaza?", "ha"),
        (PLAYGROUND_HAUSA, "ha"),
        ("Ina kuke?", "ha"),
        ("Sannu", "ha"),
        ("Ego ole ka jollof rice na okuko bu?", "ig"),
        ("Ebee ka unu di?", "ig"),
        ("Kedu oge unu na-emeghe na nke unu na-emechi?", "ig"),
        (PLAYGROUND_IGBO, "ig"),
        ("Kedu?", "ig"),
    ],
)
def test_detect_matrix(text, lang):
    assert detect(text).dominant == lang


def test_zero_width_and_smart_quotes_still_igbo():
    messy = "\u200bEgo ole ka jollof rice na okuko bu?\u200b"
    assert detect(messy).dominant == "ig"


def test_eval_dataset_stays_at_sixty():
    path = Path(__file__).resolve().parents[2] / "evaluation" / "dataset.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    misses = [
        (r["id"], r["lang"], detect(r["question"]).dominant, r["question"])
        for r in rows
        if detect(r["question"]).dominant != r["lang"]
    ]
    assert misses == []


def test_igbo_query_carries_english_kb_hints():
    q = expand_query_for_retrieval(PLAYGROUND_IGBO, "ig").lower()
    assert "price" in q
    assert "soup" in q
    assert "delivery" in q


# ---------------------------------------------------------------------------
# Price amounts
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("costs 4500 naira", {4500.0}),
        ("₦4,500", {4500.0}),
        ("N4,500", {4500.0}),
        ("NGN 4500", {4500.0}),
        ("naira 3,000", {3000.0}),
        ("Naira 3,000", {3000.0}),
        ("#1,000", {1000.0}),
        ("4.5k naira", {4500.0}),
        ("₦3k", {3000.0}),
        ("zobo is 500 naira", {500.0}),
        ("Open 9am to 9pm. 20 plates. 45 minutes.", set()),
        ("Call 08012345678", set()),
        ("We deliver in 45 minutes for 1000 naira", {1000.0}),
    ],
)
def test_amount_formats(text, expected):
    assert extract_naira_amounts(text) == expected


def test_equivalent_kb_and_reply_formats_do_not_escalate():
    out = _guard("Ofe ose dị ₦4,500. Mainland delivery bụ ₦1,000.", "ig")
    assert out.escalated is False
    assert "4,500" in out.final_text


@pytest.mark.parametrize("lang,needle", [("yo", "alabojuto"), ("ha", "abokina"), ("ig", "usekwu"), ("pid", "colleague")])
def test_invented_price_fallback_is_localized(lang, needle):
    out = _guard("Coke bụ ₦800.", lang)
    assert out.escalated is True
    assert "800" not in out.final_text
    assert needle in out.final_text
    assert "I'm not sure" not in out.final_text


def test_multi_item_keeps_grounded_igbo_drops_coke():
    out = _guard(
        "Ofe ose dị, ọ bụ ₦4,500; ofe afang ka m jụọ. Coke bụ ₦800.",
        "ig",
    )
    assert out.escalated is True
    assert "4,500" in out.final_text
    assert "800" not in out.final_text
    assert "I'm not sure" not in out.final_text


def test_hours_and_phone_in_kb_are_not_treated_as_prices():
    out = _guard("Anyị na-emeghe 9am ruo 9pm. Kpọọ 08012345678.", "ig")
    assert out.escalated is False
    assert "[REDACTED-PHONE]" in out.final_text
