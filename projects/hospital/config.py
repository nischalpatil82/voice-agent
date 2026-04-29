"""
projects/hospital/config.py — Hospital management system configuration
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

PROJECT_NAME  = "Hospital Management"
LANGUAGE      = os.getenv("HOSPITAL_LANGUAGE", "en-IN")
API_BASE_URL  = os.getenv("HOSPITAL_API_BASE_URL", "http://localhost:8082")
RELOAD_EVERY  = _env_int("HOSPITAL_RELOAD_EVERY", 600)
CONFIDENCE_WARN = _env_float("HOSPITAL_CONFIDENCE_WARN", 0.4)
CONFIDENCE_REJECT = _env_float("HOSPITAL_CONFIDENCE_REJECT", 0.35)

DB_CONFIG = {
    "host":     os.getenv("HOSPITAL_DB_HOST", "localhost"),
    "port":     _env_int("HOSPITAL_DB_PORT", 3306),
    "user":     os.getenv("HOSPITAL_DB_USER", ""),
    "password": os.getenv("HOSPITAL_DB_PASSWORD", ""),
    "database": os.getenv("HOSPITAL_DB_NAME", "hospital_db"),
}

TABLE_CONFIG = {
    "table":      os.getenv("HOSPITAL_TABLE_NAME", "doctors"),
    "id_col":     os.getenv("HOSPITAL_TABLE_ID_COL", "id"),
    "name_col":   os.getenv("HOSPITAL_TABLE_NAME_COL", "name"),
    "price_col":  os.getenv("HOSPITAL_TABLE_PRICE_COL", "consultation_fee"),
    "active_col": os.getenv("HOSPITAL_TABLE_ACTIVE_COL", "is_available"),
}

FALLBACK_ITEMS = [
    {"id": 1, "name": "Dr. Sharma - Cardiologist",       "price": 800,  "keywords": ["sharma","cardiologist","heart","cardiac"]},
    {"id": 2, "name": "Dr. Patel - General Physician",   "price": 500,  "keywords": ["patel","general","physician","gp"]},
    {"id": 3, "name": "Dr. Reddy - Orthopedic",          "price": 700,  "keywords": ["reddy","orthopedic","bone","joint"]},
    {"id": 4, "name": "Dr. Singh - Dermatologist",       "price": 600,  "keywords": ["singh","dermatologist","skin"]},
    {"id": 5, "name": "Dr. Kumar - Neurologist",         "price": 900,  "keywords": ["kumar","neurologist","neuro","brain"]},
    {"id": 6, "name": "Dr. Verma - Pediatrician",        "price": 500,  "keywords": ["verma","pediatrician","child","kids"]},
    {"id": 7, "name": "Dr. Gupta - Gynecologist",        "price": 750,  "keywords": ["gupta","gynecologist","gyno"]},
    {"id": 8, "name": "Dr. Mehta - ENT Specialist",      "price": 600,  "keywords": ["mehta","ent","ear","nose","throat"]},
]
