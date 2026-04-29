"""
projects/hotel/config.py — Hotel booking system configuration
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

PROJECT_NAME  = "Hotel Booking"
LANGUAGE      = os.getenv("HOTEL_LANGUAGE", "en-US")
API_BASE_URL  = os.getenv("HOTEL_API_BASE_URL", "http://localhost:8083")
RELOAD_EVERY  = _env_int("HOTEL_RELOAD_EVERY", 300)
CONFIDENCE_WARN = _env_float("HOTEL_CONFIDENCE_WARN", 0.4)
CONFIDENCE_REJECT = _env_float("HOTEL_CONFIDENCE_REJECT", 0.35)

DB_CONFIG = {
    "host":     os.getenv("HOTEL_DB_HOST", "localhost"),
    "port":     _env_int("HOTEL_DB_PORT", 3306),
    "user":     os.getenv("HOTEL_DB_USER", ""),
    "password": os.getenv("HOTEL_DB_PASSWORD", ""),
    "database": os.getenv("HOTEL_DB_NAME", "hotel_db"),
}

TABLE_CONFIG = {
    "table":      os.getenv("HOTEL_TABLE_NAME", "rooms"),
    "id_col":     os.getenv("HOTEL_TABLE_ID_COL", "id"),
    "name_col":   os.getenv("HOTEL_TABLE_NAME_COL", "room_type"),
    "price_col":  os.getenv("HOTEL_TABLE_PRICE_COL", "price_per_night"),
    "active_col": os.getenv("HOTEL_TABLE_ACTIVE_COL", "is_available"),
}

FALLBACK_ITEMS = [
    {"id": 1, "name": "Standard Room",    "price": 2500, "keywords": ["standard","basic","room"]},
    {"id": 2, "name": "Deluxe Room",      "price": 4000, "keywords": ["deluxe","room"]},
    {"id": 3, "name": "Suite",            "price": 8000, "keywords": ["suite","luxury"]},
    {"id": 4, "name": "Family Room",      "price": 5500, "keywords": ["family","large"]},
    {"id": 5, "name": "Executive Room",   "price": 6000, "keywords": ["executive","business"]},
    {"id": 6, "name": "Presidential Suite","price":20000, "keywords": ["presidential","vip","penthouse"]},
    {"id": 7, "name": "Pool View Room",   "price": 4500, "keywords": ["pool","view","poolside"]},
    {"id": 8, "name": "Garden Room",      "price": 3000, "keywords": ["garden","nature","ground"]},
]
