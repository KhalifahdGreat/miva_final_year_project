from core.language_detector import detect, expand_query_for_retrieval


def test_english_short_message():
    r = detect("Hello, do you ship to Abuja?")
    assert r.dominant == "en"
    assert r.mixed is False


def test_pidgin_high_signal():
    # Multiple Pidgin tokens + a Pidgin discourse pattern.
    r = detect("Abeg, una dey open today and how much be one plate of jollof rice?")
    assert r.dominant == "pid"


def test_pidgin_discourse_marker_alone():
    r = detect("Wetin dey happen?")
    assert r.dominant == "pid"


def test_yoruba_greeting():
    r = detect("Ekaaro, mo fẹ ra jollof")
    # Pidgin should NOT win this one
    assert r.dominant == "yo"


def test_empty_string():
    r = detect("")
    assert r.dominant == "unknown"


def test_mixed_english_pidgin_flag():
    r = detect("The food is great, abi you no try am?")
    assert r.dominant in ("pid", "en")
    # at least one Pidgin signal recorded
    assert r.scores["pid"] > 0


def test_yoruba_buy_intent_not_english():
    r = detect("mo fe ra ewedu ati amala")
    assert r.dominant == "yo"


def test_yoruba_when_ready_not_english():
    r = detect("Nigba wo ni o ma pari")
    assert r.dominant == "yo"


def test_hausa_price_question():
    r = detect("Nawa ne jollof rice da kaza?")
    assert r.dominant == "ha"


def test_hausa_not_yoruba_when_dishes_are_named():
    # Live playground miss: Hausa sentence naming amala/ewedu was labelled Yoruba.
    r = detect(
        "Akwai Amala da Ewedu; farashin ya kai Naira 3,000. "
        "Sai dai, ban san nawa za a biya don kawo shi Tashar Motar Mushin ba tukuna."
    )
    assert r.dominant == "ha"


def test_igbo_price_question_not_pidgin():
    r = detect("Ego ole ka jollof rice na okuko bu?")
    assert r.dominant == "ig"


def test_igbo_where_are_you():
    r = detect("Ebee ka unu di?")
    assert r.dominant == "ig"


def test_tone_marked_yoruba_order():
    r = detect("Mo fẹ́ paṣẹ àmàlà àti ewédú; mélòó ni iye owó?")
    assert r.dominant == "yo"


def test_english_naming_dishes_stays_english():
    r = detect("How much is amala and ewedu with goat meat delivery to Mushin?")
    assert r.dominant == "en"


def test_igbo_hyphen_verbs_not_pidgin():
    r = detect("Kedu oge unu na-emeghe na nke unu na-emechi?")
    assert r.dominant == "ig"


def test_pidgin_how_much_be():
    r = detect("How much be jollof rice with chicken?")
    assert r.dominant == "pid"


def test_pidgin_how_i_go_take():
    r = detect("How I go take order food?")
    assert r.dominant == "pid"


def test_english_i_go_to_place_stays_english():
    r = detect("I go to the shop on Sunday for delivery.")
    assert r.dominant == "en"


def test_english_take_order_stays_english():
    r = detect("Can I take this order for delivery to the island?")
    assert r.dominant == "en"


def test_single_word_greetings():
    assert detect("Bawo").dominant == "yo"
    assert detect("Kedu?").dominant == "ig"
    assert detect("Sannu").dominant == "ha"
    assert detect("Abeg").dominant == "pid"


def test_all_caps_pidgin():
    r = detect("ABEG UNA DEY OPEN TODAY?")
    assert r.dominant == "pid"


def test_code_switch_yoruba_then_pidgin_stays_yoruba():
    r = detect("Mo fe ra amala abeg")
    assert r.dominant == "yo"


def test_igbo_query_expands_for_english_kb():
    q = expand_query_for_retrieval(
        "Ogologo oge ole ka o ga-ewe tupu i kwadebe ofe ose na ofe afang? "
        "Ego ole ka a ga-akwu maka ibute ha?"
    )
    assert detect(
        "Ogologo oge ole ka o ga-ewe tupu i kwadebe ofe ose (pepper soup) "
        "na ofe afang?"
    ).dominant == "ig"
    low = q.lower()
    assert "price" in low
    assert "soup" in low
    assert "delivery" in low
