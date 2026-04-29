"""
projects/justbill/config.py — JustBill Jewellery Store
Products loaded live from .NET API — database connection coming later
"""

import json
import os


def _env_bool(name, default=False):
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name, default):
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_float(name, default):
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _load_intent_warn_thresholds(defaults):
    raw = os.getenv("JUSTBILL_INTENT_WARN_THRESHOLDS", "").strip()
    if not raw:
        return dict(defaults)
    try:
        parsed = json.loads(raw)
    except Exception:
        return dict(defaults)
    if not isinstance(parsed, dict):
        return dict(defaults)

    merged = dict(defaults)
    for key, value in parsed.items():
        if not isinstance(key, str):
            continue
        try:
            merged[key] = float(value)
        except (TypeError, ValueError):
            continue
    return merged

PROJECT_NAME    = "Veloria Jewellery"
LANGUAGE        = os.getenv("JUSTBILL_LANGUAGE", "en-IN")
API_BASE_URL    = os.getenv("JUSTBILL_API_BASE_URL", "https://dev-api-justbill.itbycloud.com")
# Optional endpoint for async action callbacks. Keep empty to disable.
ACTION_API_BASE_URL = os.getenv("JUSTBILL_ACTION_API_URL", "").strip()
RELOAD_EVERY    = _env_int("JUSTBILL_RELOAD_EVERY", 300)
CONFIDENCE_WARN = _env_float("JUSTBILL_CONFIDENCE_WARN", 0.30)
CONFIDENCE_REJECT = _env_float("JUSTBILL_CONFIDENCE_REJECT", 0.30)
INTENT_WARN_THRESHOLDS = _load_intent_warn_thresholds(
    {
        "ADD_TO_CART": 0.35,
        "REMOVE_ITEM": 0.45,
        "UPDATE_CART": 0.45,
        "CHECKOUT": 0.40,
        "SHOW_CATEGORY": 0.32,
        "SEARCH": 0.32,
    }
)
ACTION_CONFIRM_THRESHOLD = _env_float("JUSTBILL_ACTION_CONFIRM_THRESHOLD", 0.48)

# Voice transcription tuning
# Profile presets:
# - fast: lowest latency
# - balanced: good latency + better accuracy (default)
# - accurate: highest accuracy among local defaults
VOICE_PROFILE = os.getenv("JUSTBILL_VOICE_PROFILE", "balanced").strip().lower()

# Backward compatibility: if legacy low-latency flag is enabled, force fast profile.
if _env_bool("JUSTBILL_VOICE_LOW_LATENCY", False):
    VOICE_PROFILE = "fast"

if VOICE_PROFILE not in {"fast", "balanced", "accurate"}:
    VOICE_PROFILE = "balanced"

_VOICE_DEFAULT_MODEL = {
    "fast": "tiny",
    "balanced": "small",
    "accurate": "medium",
}[VOICE_PROFILE]
_VOICE_DEFAULT_BEAM = {
    "fast": 1,
    "balanced": 2,
    "accurate": 5,
}[VOICE_PROFILE]
_VOICE_DEFAULT_BEST_OF = {
    "fast": 1,
    "balanced": 2,
    "accurate": 3,
}[VOICE_PROFILE]
_VOICE_DEFAULT_FALLBACK_PASS = {
    "fast": False,
    "balanced": True,
    "accurate": True,
}[VOICE_PROFILE]

VOICE_MODEL  = os.getenv("VOICE_WHISPER_MODEL", _VOICE_DEFAULT_MODEL)
VOICE_COMPUTE_TYPE = os.getenv("VOICE_WHISPER_COMPUTE", "int8")
VOICE_LANGUAGE = os.getenv("JUSTBILL_VOICE_LANGUAGE", "en")
VOICE_BEAM_SIZE = _env_int("JUSTBILL_VOICE_BEAM_SIZE", _VOICE_DEFAULT_BEAM)
VOICE_BEST_OF = _env_int("JUSTBILL_VOICE_BEST_OF", _VOICE_DEFAULT_BEST_OF)
VOICE_PATIENCE = _env_float("JUSTBILL_VOICE_PATIENCE", 1.0)
VOICE_TEMPERATURE = _env_float("JUSTBILL_VOICE_TEMPERATURE", 0.0)
VOICE_NO_SPEECH_THRESHOLD = _env_float("JUSTBILL_VOICE_NO_SPEECH_THRESHOLD", 0.45)
VOICE_LOG_PROB_THRESHOLD = _env_float("JUSTBILL_VOICE_LOG_PROB_THRESHOLD", -1.2)
VOICE_HALLUCINATION_SILENCE_THRESHOLD = _env_float("JUSTBILL_VOICE_HALLUCINATION_SILENCE_THRESHOLD", 1.5)
VOICE_VAD_MIN_SILENCE_MS = _env_int("JUSTBILL_VOICE_VAD_MIN_SILENCE_MS", 180)
VOICE_VAD_SPEECH_PAD_MS = _env_int("JUSTBILL_VOICE_VAD_SPEECH_PAD_MS", 180)
VOICE_ENABLE_FALLBACK_PASS = _env_bool("JUSTBILL_VOICE_ENABLE_FALLBACK_PASS", _VOICE_DEFAULT_FALLBACK_PASS)
VOICE_HINT_USE_FULL_CATALOG = _env_bool("JUSTBILL_VOICE_HINT_USE_FULL_CATALOG", True)
VOICE_HINT_PRODUCT_LIMIT = _env_int("JUSTBILL_VOICE_HINT_PRODUCT_LIMIT", 8)
VOICE_HOTWORD_LIMIT = _env_int("JUSTBILL_VOICE_HOTWORD_LIMIT", 120)
VOICE_PROMPT_TERM_LIMIT = _env_int("JUSTBILL_VOICE_PROMPT_TERM_LIMIT", 10)
VOICE_CONTEXT_PRODUCT_LIMIT = _env_int("JUSTBILL_VOICE_CONTEXT_PRODUCT_LIMIT", 12)
VOICE_CONTEXT_TERM_LIMIT = _env_int("JUSTBILL_VOICE_CONTEXT_TERM_LIMIT", 48)
VOICE_HINT_TERMS = [
    "JustBill", "jewellery", "jewelry", "diamond", "gold", "silver",
    "platinum", "pearl", "ruby", "emerald", "sapphire", "ring",
    "rings", "necklace", "necklaces", "earring", "earrings",
    "bracelet", "bracelets", "bangle", "bangles", "chain", "chains",
    "pendant", "pendants", "mangala sutra", "wishlist", "cart",
    "checkout", "compare", "offers",
]
VOICE_INITIAL_PROMPT = (
    "This is an English voice command for the JustBill jewellery shopping assistant. "
    "Prefer jewellery, product, cart, wishlist, checkout and offer terms over similar sounding words."
)

# ── Database config (fill in when ready) ──
DB_CONFIG = {
    "host":     os.getenv("JUSTBILL_DB_HOST", "localhost"),
    "port":     _env_int("JUSTBILL_DB_PORT", 3306),
    "user":     os.getenv("JUSTBILL_DB_USER", ""),
    "password": os.getenv("JUSTBILL_DB_PASSWORD", ""),
    "database": os.getenv("JUSTBILL_DB_NAME", ""),
}

TABLE_CONFIG = {
    "table":      os.getenv("JUSTBILL_TABLE_NAME", "ml_product"),
    "id_col":     os.getenv("JUSTBILL_TABLE_ID_COL", "productID"),
    "name_col":   os.getenv("JUSTBILL_TABLE_NAME_COL", "productName"),
    "price_col":  os.getenv("JUSTBILL_TABLE_PRICE_COL", "sellingPrice"),
    "active_col": os.getenv("JUSTBILL_TABLE_ACTIVE_COL", "isActive"),
}

# Demo-safe fallback catalog if live API is unavailable
FALLBACK_ITEMS = [
    {
        "id": 1001,
        "name": "Diamond Ring",
        "price": 149999,
        "keywords": ["diamond", "ring", "engagement"],
    },
    {
        "id": 1002,
        "name": "Gold Chain",
        "price": 89999,
        "keywords": ["gold", "chain", "daily wear"],
    },
    {
        "id": 1003,
        "name": "Pearl Necklace",
        "price": 79999,
        "keywords": ["pearl", "necklace", "classic"],
    },
    {
        "id": 1004,
        "name": "Emerald Earrings",
        "price": 55999,
        "keywords": ["emerald", "earrings", "party"],
    },
    {
        "id": 1005,
        "name": "Platinum Bracelet",
        "price": 129999,
        "keywords": ["platinum", "bracelet", "premium"],
    },
    {
        "id": 1006,
        "name": "Traditional Anklet",
        "price": 34999,
        "keywords": ["traditional", "anklet", "silver"],
    },
    {
        "id": 1007,
        "name": "Diamond Necklace",
        "price": 199999,
        "keywords": ["diamond", "necklace", "premium", "luxury"],
    },
]
