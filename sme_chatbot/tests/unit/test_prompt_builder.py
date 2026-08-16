from core.prompt_builder import build
from core.tenant_service import default_config
from core.types import Hit, Turn


def test_pidgin_path_includes_grammar_block():
    cfg = default_config("tid", "Mama Ngozi's")
    cfg.tone = "pidgin_friendly"
    hits = [Hit(chunk_id=1, text="Jollof — ₦2,500 per plate", document_type="pricing", section="menu", score=0.9)]
    sys_prompt, user_prompt = build(
        tenant_config=cfg,
        retrieved_chunks=hits,
        history=[],
        user_message="abeg how much be jollof",
        detected_language="pid",
    )
    assert "PIDGIN GRAMMAR" in sys_prompt
    assert "Mama Ngozi" in sys_prompt
    assert "Jollof" in sys_prompt
    assert "abeg how much" in user_prompt


def test_yoruba_path_includes_reply_block_and_hard_rule():
    cfg = default_config("tid", "Mama Put Kitchen")
    cfg.languages = ["en", "pid", "yo", "ha", "ig"]
    sys_prompt, _ = build(
        tenant_config=cfg,
        retrieved_chunks=[],
        history=[],
        user_message="mo fe ra ewedu ati amala",
        detected_language="yo",
    )
    assert "YORUBA REPLY" in sys_prompt
    assert "HARD LANGUAGE RULE" in sys_prompt
    assert "Yoruba" in sys_prompt
    assert "PIDGIN GRAMMAR" not in sys_prompt


def test_hausa_and_igbo_paths_include_reply_blocks():
    cfg = default_config("tid", "Mama Put Kitchen")
    cfg.languages = ["en", "pid", "yo", "ha", "ig"]
    ha, _ = build(
        tenant_config=cfg, retrieved_chunks=[], history=[],
        user_message="Nawa ne jollof?", detected_language="ha",
    )
    ig, _ = build(
        tenant_config=cfg, retrieved_chunks=[], history=[],
        user_message="Ego ole ka jollof bu?", detected_language="ig",
    )
    assert "HAUSA REPLY" in ha
    assert "IGBO REPLY" in ig


def test_english_path_omits_pidgin_block():
    cfg = default_config("tid", "Acme")
    hits = []
    sys_prompt, _ = build(
        tenant_config=cfg,
        retrieved_chunks=hits,
        history=[],
        user_message="What time do you open?",
        detected_language="en",
    )
    assert "PIDGIN GRAMMAR" not in sys_prompt


def test_history_is_included():
    cfg = default_config("tid", "Acme")
    history = [Turn(role="user", text="hi"), Turn(role="assistant", text="hello")]
    _, user_prompt = build(
        tenant_config=cfg,
        retrieved_chunks=[],
        history=history,
        user_message="thanks",
        detected_language="en",
    )
    assert "Conversation so far" in user_prompt
    assert "hello" in user_prompt
