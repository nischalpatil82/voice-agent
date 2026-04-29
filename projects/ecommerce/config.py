import os


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


PROJECT_NAME  = "Ecommerce Store"
LANGUAGE      = os.getenv("ECOMMERCE_LANGUAGE", "en-US")
API_BASE_URL  = os.getenv("ECOMMERCE_API_BASE_URL", "http://localhost:8081")
RELOAD_EVERY  = _env_int("ECOMMERCE_RELOAD_EVERY", 300)
CONFIDENCE_WARN = _env_float("ECOMMERCE_CONFIDENCE_WARN", 0.4)
CONFIDENCE_REJECT = _env_float("ECOMMERCE_CONFIDENCE_REJECT", 0.35)

# Voice transcription tuning for /voice-command
VOICE_MODEL  = "small"
VOICE_COMPUTE_TYPE = "int8"
VOICE_LANGUAGE = "en"
VOICE_BEAM_SIZE = 2
VOICE_BEST_OF = 2
VOICE_PATIENCE = 1.0
VOICE_TEMPERATURE = 0.0
VOICE_NO_SPEECH_THRESHOLD = 0.4
VOICE_LOG_PROB_THRESHOLD = -1.2
VOICE_HALLUCINATION_SILENCE_THRESHOLD = 1.5
VOICE_VAD_MIN_SILENCE_MS = 180
VOICE_VAD_SPEECH_PAD_MS = 180
VOICE_HINT_PRODUCT_LIMIT = 8
VOICE_HOTWORD_LIMIT = 24
VOICE_PROMPT_TERM_LIMIT = 10
VOICE_HINT_TERMS = [
    "cart", "checkout", "wishlist", "speaker", "headphones",
    "laptop bag", "smart watch", "usb cable", "search", "products",
]
VOICE_INITIAL_PROMPT = (
    "This is an English ecommerce voice command. "
    "Prefer product, cart, checkout, wishlist, and search terms."
)

DB_CONFIG = {
    "host":     os.getenv("ECOMMERCE_DB_HOST", "127.0.0.1"),
    "port":     _env_int("ECOMMERCE_DB_PORT", 3306),
    "user":     os.getenv("ECOMMERCE_DB_USER", ""),
    "password": os.getenv("ECOMMERCE_DB_PASSWORD", ""),
    "database": os.getenv("ECOMMERCE_DB_NAME", "ecommerce_db"),
}

TABLE_CONFIG = {
    "table":      os.getenv("ECOMMERCE_TABLE_NAME", "products"),
    "id_col":     os.getenv("ECOMMERCE_TABLE_ID_COL", "id"),
    "name_col":   os.getenv("ECOMMERCE_TABLE_NAME_COL", "name"),
    "price_col":  os.getenv("ECOMMERCE_TABLE_PRICE_COL", "price"),
    "active_col": os.getenv("ECOMMERCE_TABLE_ACTIVE_COL", "is_active"),
}

FALLBACK_ITEMS = [
    {"id": 1, "name": "Wireless Headphones", "price": 2999, "keywords": ["wireless","headphones"]},
    {"id": 2, "name": "Bluetooth Speaker",   "price": 1999, "keywords": ["bluetooth","speaker"]},
    {"id": 3, "name": "Running Shoes",       "price": 3499, "keywords": ["running","shoes"]},
    {"id": 4, "name": "Laptop Bag",          "price": 1499, "keywords": ["laptop","bag"]},
    {"id": 5, "name": "Smart Watch",         "price": 8999, "keywords": ["smart","watch"]},
    {"id": 6, "name": "Phone Case",          "price":  499, "keywords": ["phone","case"]},
    {"id": 7, "name": "USB-C Cable",         "price":  299, "keywords": ["usb","cable"]},
    {"id": 8, "name": "Desk Lamp",           "price":  899, "keywords": ["desk","lamp"]},
]
