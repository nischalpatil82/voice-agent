"""
projects/cravehub/config.py — CraveHub food delivery configuration
"""

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

PROJECT_NAME  = "CraveHub"
LANGUAGE      = os.getenv("CRAVEHUB_LANGUAGE", "en-IN")
API_BASE_URL  = os.getenv("CRAVEHUB_API_BASE_URL", "http://localhost:8080")
RELOAD_EVERY  = _env_int("CRAVEHUB_RELOAD_EVERY", 300)
CONFIDENCE_WARN = _env_float("CRAVEHUB_CONFIDENCE_WARN", 0.4)
CONFIDENCE_REJECT = _env_float("CRAVEHUB_CONFIDENCE_REJECT", 0.35)

DB_CONFIG = {
    "host":     os.getenv("CRAVEHUB_DB_HOST", "127.0.0.1"),
    "port":     _env_int("CRAVEHUB_DB_PORT", 3306),
    "user":     os.getenv("CRAVEHUB_DB_USER", ""),
    "password": os.getenv("CRAVEHUB_DB_PASSWORD", ""),
    "database": os.getenv("CRAVEHUB_DB_NAME", "cravehub"),
}

TABLE_CONFIG = {
    "table":      os.getenv("CRAVEHUB_TABLE_NAME", "menu"),
    "id_col":     os.getenv("CRAVEHUB_TABLE_ID_COL", "menu_id"),
    "name_col":   os.getenv("CRAVEHUB_TABLE_NAME_COL", "menu_name"),
    "price_col":  os.getenv("CRAVEHUB_TABLE_PRICE_COL", "price"),
}

FALLBACK_ITEMS = [
    {"id": 1, "name": "American Pizza",    "price": 350, "keywords": ["american","pizza"]},
    {"id": 2, "name": "Veg Pizza",         "price": 250, "keywords": ["veg","pizza"]},
    {"id": 3, "name": "Chicken Burger",    "price": 80,  "keywords": ["chicken","burger"]},
    {"id": 4, "name": "Chocolate Mousse",  "price": 250, "keywords": ["chocolate","mousse"]},
    {"id": 5, "name": "Veg Burger",        "price": 50,  "keywords": ["veg","burger"]},
]
