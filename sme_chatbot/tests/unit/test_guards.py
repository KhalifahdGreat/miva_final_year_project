from core.guards import apply_guards
from core.tenant_service import default_config


def _cfg():
    return default_config("tid-test", "Acme")


def test_price_in_knowledge_passes_through():
    cfg = _cfg()
    out = apply_guards(
        "Our gold watch is ₦150,000.",
        retrieved_text_blob="Gold watch — price ₦150,000. Delivery 2 days.",
        tenant_config=cfg,
        user_message="how much is the gold watch?",
    )
    assert out.escalated is False
    assert "150,000" in out.final_text


def test_invented_price_is_blocked():
    cfg = _cfg()
    out = apply_guards(
        "Our gold watch is ₦250,000.",
        retrieved_text_blob="Silver watch is ₦80,000.",
        tenant_config=cfg,
        user_message="how much is the gold watch?",
    )
    assert out.escalated is True
    assert "hallucinated_price" in (out.reason or "")


def test_phone_redacted():
    cfg = _cfg()
    out = apply_guards(
        "Call me on 08031234567 please.",
        retrieved_text_blob="",
        tenant_config=cfg,
        user_message="hi",
    )
    assert "[REDACTED-PHONE]" in out.final_text
    assert "redacted_phone" in out.mutations


def test_length_cap():
    cfg = _cfg()
    long_reply = "a " * 600
    out = apply_guards(
        long_reply,
        retrieved_text_blob="",
        tenant_config=cfg,
        user_message="hi",
    )
    assert len(out.final_text) <= 800
    assert "truncated" in out.mutations
