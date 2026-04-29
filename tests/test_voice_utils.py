from core.tts import normalize_tts_text
from core.voice import _normalize_language, build_voice_guidance


class DummyConfig:
    VOICE_HINT_TERMS = ["JustBill", "cart", "cart", "wishlist"]
    VOICE_HINT_PRODUCT_LIMIT = 2
    VOICE_HOTWORD_LIMIT = 4
    VOICE_PROMPT_TERM_LIMIT = 2
    VOICE_INITIAL_PROMPT = "Prefer shopping terms."


def test_normalize_tts_text_expands_currency():
    text = normalize_tts_text("Your total is Rs. 1,499 and cart is ready")
    assert "rupees" in text
    assert "1499" in text


def test_normalize_language_codes():
    assert _normalize_language("en-IN") == "en"
    assert _normalize_language("en-US") == "en"
    assert _normalize_language("") == "en"


def test_build_voice_guidance_dedupes_terms_and_prompt():
    hotwords, prompt = build_voice_guidance(
        DummyConfig,
        [
            {"name": "Diamond Ring", "keywords": ["diamond", "ring"]},
            {"name": "Gold Chain", "keywords": ["gold", "chain"]},
        ],
    )

    assert hotwords == ["JustBill", "cart", "wishlist", "Diamond Ring"]
    assert prompt == "Prefer shopping terms. Key terms: JustBill, cart."
