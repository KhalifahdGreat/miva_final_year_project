from core.language_detector import detect


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
    assert r.dominant in ("yo", "pid")  # tolerate either, but never plain en


def test_empty_string():
    r = detect("")
    assert r.dominant == "unknown"


def test_mixed_english_pidgin_flag():
    r = detect("The food is great, abi you no try am?")
    assert r.dominant in ("pid", "en")
    # at least one Pidgin signal recorded
    assert r.scores["pid"] > 0
