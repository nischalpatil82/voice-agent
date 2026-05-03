"""
server.py — Enterprise Voice Agent Flask Server

Features:
  - Session-based user isolation (each browser = own cart/context)
  - Rate limiting & request size limits
  - CORS whitelist (configurable)
  - Optimized Whisper pipeline (VAD enabled, streaming-ready)
  - Structured logging & analytics
  - Combined /voice-command endpoint (transcribe + process)

Run:
  python server.py --project justbill    (port 5004)
  python server.py --all

Frontend sends:
  POST /command  { "text": "add 2 rings", "page": "menu" }
  POST /voice-command  FormData(audio, page)
  Headers: X-Session-ID: <uuid>
"""

import argparse
import importlib
import sys
import os
import json
import re
import secrets
import socket
import threading
import time
import logging
from collections import defaultdict
from io import BytesIO

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    # dotenv is optional in constrained environments.
    pass


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


def _env_list(name, default=None):
    raw = os.getenv(name)
    if not raw:
        return list(default or [])
    return [part.strip() for part in raw.split(",") if part.strip()]


def _port_is_available(port, host="0.0.0.0"):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, int(port)))
        except OSError:
            return False
    return True


def _resolve_project_port(project_name, requested_port, explicit_port=False):
    requested_port = int(requested_port)
    if _port_is_available(requested_port):
        return requested_port

    if explicit_port:
        raise ValueError(
            f"Port {requested_port} is already in use. Stop the other process or pass a different --port."
        )

    for candidate in range(requested_port + 1, 65536):
        if _port_is_available(candidate):
            log.warning(
                "[Startup] Port %s is busy; using %s instead for %s",
                requested_port,
                candidate,
                project_name,
            )
            return candidate

    raise ValueError(
        f"No free port found at or above {requested_port}. Stop the other process or pass --port <free port>."
    )

# ── Logging setup ──────────────────────────────────────────────────────────
_log_level_name = os.getenv("VOICE_AGENT_LOG_LEVEL", "INFO").upper()
_log_level = getattr(logging, _log_level_name, logging.INFO)
logging.basicConfig(
    level=_log_level,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("voice-agent")

# ── Try to import Flask ────────────────────────────────────────────────────
try:
    from flask import Flask, request, jsonify, g, send_file
    from flask_cors import CORS
    from flask_socketio import SocketIO, emit
    from werkzeug.exceptions import RequestEntityTooLarge
except ImportError:
    print("\n  [ERROR] Flask not installed.")
    print("  Run:  pip install flask flask-cors\n")
    sys.exit(1)

sys.path.insert(0, os.path.dirname(__file__))

# ── Auto-detect FFmpeg (needed by faster-whisper for voice transcription) ──
import shutil, glob
if not shutil.which("ffmpeg"):
    _ffmpeg_search = [
        os.path.expanduser("~\\AppData\\Local\\Microsoft\\WinGet\\Packages\\*FFmpeg*\\*\\bin"),
        "C:\\ffmpeg\\bin",
        "C:\\Program Files\\ffmpeg\\bin",
        "C:\\tools\\ffmpeg\\bin",
    ]
    for pattern in _ffmpeg_search:
        for match in glob.glob(pattern):
            if os.path.isfile(os.path.join(match, "ffmpeg.exe")):
                os.environ["PATH"] = match + ";" + os.environ.get("PATH", "")
                log.info(f"[FFmpeg] Auto-detected: {match}")
                break
        if shutil.which("ffmpeg"):
            break

from core.database   import ItemDB
from core.matcher    import ItemMatcher
from core.classifier import IntentClassifier
from core.context    import SessionManager
from core.actions    import ActionBuilder
from core.preprocessor import TextPreprocessor
from core.tts import synthesize_audio_bytes

class DummyFile:
    def __init__(self, data: bytes):
        self.data = data
    def save(self, path):
        with open(path, 'wb') as f:
            f.write(self.data)

def _socketio_cors_origins():
    raw = os.getenv("VOICE_AGENT_CORS_ORIGINS", "").strip()
    if not raw:
        return ["http://127.0.0.1:4200", "http://localhost:4200"]
    return [origin.strip() for origin in raw.split(",") if origin.strip()]

AVAILABLE_PROJECTS = ["cravehub", "ecommerce", "hospital", "hotel", "justbill"]

# Default ports per project
PROJECT_PORTS = {
    "cravehub":  5000,
    "ecommerce": 5001,
    "hospital":  5002,
    "hotel":     5003,
    "justbill":  5004,
}

VOICE_COMMAND_FIXES = (
    (re.compile(r"\bwish\s+list\b"), "wishlist"),
    (re.compile(r"\bcheck\s+out\b"), "checkout"),
    (re.compile(r"\blog\s+in\b"), "login"),
    (re.compile(r"\bsign\s+in\b"), "signin"),
    (re.compile(r"\bsign\s+up\b"), "signup"),
    (re.compile(r"\badd to card\b"), "add to cart"),
    (re.compile(r"\bto card\b"), "to cart"),
    (re.compile(r"\bmy card\b"), "my cart"),
    (re.compile(r"\bfrom card\b"), "from cart"),
    (re.compile(r"\bin card\b"), "in cart"),
    (re.compile(r"\bshow my card\b"), "show my cart"),
    (re.compile(r"\bopen my card\b"), "open my cart"),
    (re.compile(r"\bopen card\b"), "open cart"),
    (re.compile(r"\bview card\b"), "view cart"),
    (re.compile(r"\bclear card\b"), "clear cart"),
    (re.compile(r"\bremove from card\b"), "remove from cart"),
)
VOICE_PRODUCT_WORDS = {
    "ring", "rings", "necklace", "necklaces", "earring", "earrings",
    "bracelet", "bracelets", "bangle", "bangles", "chain", "chains",
    "pendant", "pendants", "anklet", "anklets", "choker", "chokers",
    "sutra", "mangala",
}
VOICE_DESCRIPTOR_WORDS = {
    "diamond", "gold", "silver", "platinum", "pearl",
    "ruby", "emerald", "sapphire", "kundan", "polki",
}

CATEGORY_BROWSE_TERM_MAP = {
    "ring": "rings",
    "rings": "rings",
    "necklace": "necklaces",
    "necklaces": "necklaces",
    "earring": "earrings",
    "earrings": "earrings",
    "bracelet": "bracelets",
    "bracelets": "bracelets",
    "bangle": "bangles",
    "bangles": "bangles",
    "chain": "chains",
    "chains": "chains",
    "pendant": "pendants",
    "pendants": "pendants",
    "anklet": "anklets",
    "anklets": "anklets",
}

CONFIRM_REPLY_TERMS = {
    "yes", "y", "yeah", "yep", "sure", "ok", "okay", "confirm", "no", "n", "nope", "nah", "cancel",
}


def _dedupe_terms(terms, limit=None):
    seen = set()
    unique = []
    for term in terms:
        cleaned = " ".join(str(term or "").split()).strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(cleaned)
        if limit and len(unique) >= limit:
            break
    return unique


def _safe_context_text(value, max_len=140):
    text = " ".join(str(value or "").split()).strip()
    if not text:
        return ""
    return text[:max_len]


def _normalize_frontend_context(raw_context):
    if not isinstance(raw_context, dict):
        return {}

    normalized = {
        "page_url": _safe_context_text(raw_context.get("page_url") or raw_context.get("page") or "", 180),
        "locale": _safe_context_text(raw_context.get("locale") or "", 20),
        "visible_products": [],
        "active_filters": {},
        "selected_product": {},
        "cart_snapshot": [],
    }

    selected = raw_context.get("selected_product")
    if isinstance(selected, dict):
        selected_id = selected.get("id") or selected.get("product_id")
        if selected_id is not None:
            normalized["selected_product"]["id"] = selected_id
        selected_name = _safe_context_text(selected.get("name"), 120)
        if selected_name:
            normalized["selected_product"]["name"] = selected_name

    visible_products = raw_context.get("visible_products")
    if isinstance(visible_products, list):
        for product in visible_products[:40]:
            if not isinstance(product, dict):
                continue
            normalized_product = {}
            product_id = product.get("id") or product.get("product_id")
            if product_id is not None:
                normalized_product["id"] = product_id
            product_name = _safe_context_text(product.get("name"), 120)
            if product_name:
                normalized_product["name"] = product_name
            category = _safe_context_text(product.get("category"), 80)
            if category:
                normalized_product["category"] = category
            keywords = product.get("keywords")
            if isinstance(keywords, list):
                cleaned_keywords = [_safe_context_text(word, 32) for word in keywords]
                cleaned_keywords = [word for word in cleaned_keywords if word]
                if cleaned_keywords:
                    normalized_product["keywords"] = cleaned_keywords[:8]
            if normalized_product:
                normalized["visible_products"].append(normalized_product)

    active_filters = raw_context.get("active_filters")
    if isinstance(active_filters, dict):
        for key, value in list(active_filters.items())[:20]:
            safe_key = _safe_context_text(key, 40)
            safe_value = _safe_context_text(value, 80)
            if safe_key and safe_value:
                normalized["active_filters"][safe_key] = safe_value

    cart_snapshot = raw_context.get("cart_snapshot")
    if isinstance(cart_snapshot, list):
        for item in cart_snapshot[:30]:
            if not isinstance(item, dict):
                continue
            normalized_item = {}
            product_id = item.get("product_id") or item.get("id")
            if product_id is not None:
                normalized_item["product_id"] = product_id
            item_name = _safe_context_text(item.get("name"), 120)
            if item_name:
                normalized_item["name"] = item_name
            quantity = item.get("quantity")
            if isinstance(quantity, (int, float)):
                normalized_item["quantity"] = max(1, int(quantity))
            if normalized_item:
                normalized["cart_snapshot"].append(normalized_item)

    return normalized


def _context_terms_from_frontend(frontend_context, product_limit=12, term_limit=48):
    if not isinstance(frontend_context, dict):
        return []

    terms = []
    selected = frontend_context.get("selected_product")
    if isinstance(selected, dict):
        selected_name = selected.get("name")
        if selected_name:
            terms.append(selected_name)

    visible_products = frontend_context.get("visible_products")
    if isinstance(visible_products, list):
        for product in visible_products[:product_limit]:
            if not isinstance(product, dict):
                continue
            if product.get("name"):
                terms.append(product["name"])
            if product.get("category"):
                terms.append(product["category"])
            if isinstance(product.get("keywords"), list):
                terms.extend(product["keywords"][:4])

    active_filters = frontend_context.get("active_filters")
    if isinstance(active_filters, dict):
        terms.extend(list(active_filters.values())[:10])

    cart_snapshot = frontend_context.get("cart_snapshot")
    if isinstance(cart_snapshot, list):
        for item in cart_snapshot[:10]:
            if isinstance(item, dict) and item.get("name"):
                terms.append(item["name"])

    return _dedupe_terms(terms, term_limit)


def _build_voice_terms(config, items, frontend_context=None):
    terms = list(getattr(config, "VOICE_HINT_TERMS", []))
    product_limit = getattr(config, "VOICE_HINT_PRODUCT_LIMIT", 8)
    use_full_catalog = bool(getattr(config, "VOICE_HINT_USE_FULL_CATALOG", False))

    source_items = items if use_full_catalog else items[:product_limit]

    for item in source_items:
        terms.append(item.get("name"))
        terms.extend(item.get("keywords", [])[:2])

    terms.extend(
        _context_terms_from_frontend(
            frontend_context,
            product_limit=getattr(config, "VOICE_CONTEXT_PRODUCT_LIMIT", 12),
            term_limit=getattr(config, "VOICE_CONTEXT_TERM_LIMIT", 48),
        )
    )

    hotword_limit = getattr(config, "VOICE_HOTWORD_LIMIT", 24)
    if use_full_catalog and hotword_limit < 64:
        hotword_limit = 64

    return _dedupe_terms(terms, hotword_limit)


def _token_edit_distance(source_tokens, target_tokens):
    rows = len(source_tokens) + 1
    cols = len(target_tokens) + 1
    dp = [[0] * cols for _ in range(rows)]

    for i in range(rows):
        dp[i][0] = i
    for j in range(cols):
        dp[0][j] = j

    for i in range(1, rows):
        for j in range(1, cols):
            cost = 0 if source_tokens[i - 1] == target_tokens[j - 1] else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,
                dp[i][j - 1] + 1,
                dp[i - 1][j - 1] + cost,
            )
    return dp[-1][-1]


def _wer_like_shift(raw_text, normalized_text):
    source_tokens = str(raw_text or "").lower().split()
    target_tokens = str(normalized_text or "").lower().split()
    if not source_tokens:
        return 0.0
    distance = _token_edit_distance(source_tokens, target_tokens)
    return round(distance / max(1, len(source_tokens)), 4)


def _build_initial_prompt(config, terms):
    prompt = getattr(config, "VOICE_INITIAL_PROMPT", "").strip()
    if not prompt:
        return None

    prompt_limit = getattr(config, "VOICE_PROMPT_TERM_LIMIT", 10)
    prompt_terms = ", ".join(terms[:prompt_limit])
    if prompt_terms:
        return f"{prompt} Key terms: {prompt_terms}."
    return prompt


def _normalize_transcript_text(text, preprocessor):
    normalized = preprocessor.preprocess(text)
    if not normalized:
        return ""

    for pattern, replacement in VOICE_COMMAND_FIXES:
        normalized = pattern.sub(replacement, normalized)

    words = set(normalized.split())
    if (
        normalized.startswith(("show ", "open ", "browse "))
        and words.intersection(VOICE_PRODUCT_WORDS)
        and words.intersection(VOICE_DESCRIPTOR_WORDS)
    ):
        normalized = re.sub(r"^(show|open|browse)\b", "search", normalized, count=1)

    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _normalize_category_browse_text(text):
    """Normalize category browse phrasing before intent classification."""
    normalized = re.sub(r"\s+", " ", str(text or "").strip().lower())
    if not normalized:
        return ""

    match = re.fullmatch(r"(show|open|browse)\s+(?:me\s+)?([a-z]+)", normalized)
    if not match:
        return normalized

    verb = match.group(1)
    noun = match.group(2)
    mapped_noun = CATEGORY_BROWSE_TERM_MAP.get(noun)
    if not mapped_noun:
        return normalized
    return f"{verb} {mapped_noun}"


def _is_confirmation_reply(text):
    normalized = " ".join(str(text or "").lower().split()).strip()
    return normalized in CONFIRM_REPLY_TERMS


def _intent_warn_threshold(config, intent):
    base_warn = float(getattr(config, "CONFIDENCE_WARN", 0.4))
    intent_map = getattr(config, "INTENT_WARN_THRESHOLDS", {})
    if not isinstance(intent_map, dict):
        return base_warn

    raw = intent_map.get(intent)
    if raw is None:
        return base_warn
    try:
        return float(raw)
    except (TypeError, ValueError):
        return base_warn


def _select_transcript_candidate(raw_text, normalized_text, classifier):
    raw_candidate = " ".join(str(raw_text or "").split()).strip()
    normalized_candidate = " ".join(str(normalized_text or "").split()).strip()

    candidates = []
    if normalized_candidate:
        candidates.append(("normalized", normalized_candidate))
    if raw_candidate and raw_candidate != normalized_candidate:
        candidates.append(("raw", raw_candidate))

    if not candidates:
        return "", {"selected": None, "confidence": 0.0, "intent": "OUT_OF_SCOPE"}

    best = None
    for source, candidate_text in candidates:
        intent, confidence = classifier.predict(candidate_text)
        row = {
            "source": source,
            "text": candidate_text,
            "intent": intent,
            "confidence": float(confidence),
        }
        if best is None or row["confidence"] > best["confidence"]:
            best = row

    if best and len(candidates) == 2:
        log.info(
            "[Audio] transcript_candidate selected=%s intent=%s confidence=%.3f",
            best["source"],
            best["intent"],
            best["confidence"],
        )

    return best["text"], {
        "selected": best["source"],
        "confidence": best["confidence"],
        "intent": best["intent"],
    }

# ── Rate Limiter ───────────────────────────────────────────────────────────
class RateLimiter:
    """Simple in-memory rate limiter per IP."""
    def __init__(self, max_requests=30, window_seconds=60):
        self.max_requests = max_requests
        self.window = window_seconds
        self.requests = defaultdict(list)
        self._lock = threading.Lock()

    def is_allowed(self, ip):
        now = time.time()
        with self._lock:
            # Clean old entries
            self.requests[ip] = [t for t in self.requests[ip] if now - t < self.window]
            if len(self.requests[ip]) >= self.max_requests:
                return False
            self.requests[ip].append(now)
            return True

# ── Analytics Logger ───────────────────────────────────────────────────────
class AnalyticsLogger:
    """Track command analytics for continuous improvement."""
    def __init__(self):
        self._lock = threading.Lock()
        self.total_commands = 0
        self.intent_counts = defaultdict(int)
        self.low_confidence = []  # Store for retraining
        self.errors = []
        self.avg_response_time = 0

    def log_command(self, text, intent, confidence, response_time):
        with self._lock:
            self.total_commands += 1
            self.intent_counts[intent] += 1
            # Track running average response time
            self.avg_response_time = (
                (self.avg_response_time * (self.total_commands - 1) + response_time)
                / self.total_commands
            )
            # Store low-confidence for retraining
            if confidence < 0.5:
                self.low_confidence.append({
                    "text": text, "intent": intent,
                    "confidence": confidence,
                    "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                })
                # Keep only last 100
                if len(self.low_confidence) > 100:
                    self.low_confidence = self.low_confidence[-100:]

    def log_error(self, text, error):
        with self._lock:
            self.errors.append({
                "text": text, "error": str(error),
                "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            })
            if len(self.errors) > 50:
                self.errors = self.errors[-50:]

    def get_stats(self):
        with self._lock:
            return {
                "total_commands": self.total_commands,
                "intent_distribution": dict(self.intent_counts),
                "avg_response_time_ms": round(self.avg_response_time * 1000, 1),
                "low_confidence_count": len(self.low_confidence),
                "error_count": len(self.errors),
                "recent_low_confidence": self.low_confidence[-5:],
            }


def create_agent(project_name):
    """Load and initialize a full agent for a given project."""
    config  = importlib.import_module(f"projects.{project_name}.config")
    intents = importlib.import_module(f"projects.{project_name}.intents")

    # Use project-specific database.py if it exists, else use core
    try:
        db_module = importlib.import_module(f"projects.{project_name}.database")
        db = db_module.ItemDB(config)
        log.info(f"[DB] Using custom database for {project_name}")
    except ModuleNotFoundError:
        db = ItemDB(config)

    db.load()

    fail_on_catalog_not_ready = _env_bool(
        "VOICE_AGENT_FAIL_STARTUP_ON_CATALOG_DEGRADED",
        _env_bool("VOICE_AGENT_PRODUCTION", False),
    )
    if fail_on_catalog_not_ready and hasattr(db, "get_health"):
        health = db.get_health()
        if not health.get("catalog_ready", True):
            reason = health.get("degraded_reason") or "catalog not ready"
            raise RuntimeError(f"Catalog readiness check failed: {reason}")

    matcher = ItemMatcher(db)
    reject_threshold = getattr(config, "CONFIDENCE_REJECT", 0.35)
    clf     = IntentClassifier(intents.TRAINING_DATA, confidence_threshold=reject_threshold)
    builder = ActionBuilder(config, intents)

    return {
        "config":  config,
        "intents": intents,
        "db":      db,
        "matcher": matcher,
        "clf":     clf,
        "builder": builder,
    }


def _validate_runtime_settings(project_name, port, production_mode):
    if not (1 <= int(port) <= 65535):
        raise ValueError(f"Invalid port: {port}")

    if _env_int("VOICE_AGENT_MAX_TEXT_LENGTH", 500) <= 0:
        raise ValueError("VOICE_AGENT_MAX_TEXT_LENGTH must be greater than 0")

    if _env_int("VOICE_AGENT_RATE_LIMIT_MAX", 60) <= 0:
        raise ValueError("VOICE_AGENT_RATE_LIMIT_MAX must be greater than 0")

    if _env_int("VOICE_AGENT_RATE_LIMIT_WINDOW_SECONDS", 60) <= 0:
        raise ValueError("VOICE_AGENT_RATE_LIMIT_WINDOW_SECONDS must be greater than 0")

    if not production_mode:
        return

    require_admin_token = _env_bool("VOICE_AGENT_REQUIRE_ADMIN_TOKEN", False)
    if require_admin_token and not os.getenv("VOICE_AGENT_ADMIN_TOKEN", "").strip():
        raise ValueError("VOICE_AGENT_ADMIN_TOKEN is required in production mode")

    require_public_token = _env_bool("VOICE_AGENT_REQUIRE_PUBLIC_TOKEN", False)
    if require_public_token and not os.getenv("VOICE_AGENT_PUBLIC_TOKEN", "").strip():
        raise ValueError(
            "VOICE_AGENT_PUBLIC_TOKEN is required in production mode when "
            "VOICE_AGENT_REQUIRE_PUBLIC_TOKEN=true"
        )

    cors_raw = os.getenv("VOICE_AGENT_CORS_ORIGINS", "").strip()
    if not cors_raw:
        raise ValueError("VOICE_AGENT_CORS_ORIGINS must be set in production mode")

    cors_origins = [part.strip().lower() for part in cors_raw.split(",") if part.strip()]
    has_localhost = any(("localhost" in origin) or ("127.0.0.1" in origin) for origin in cors_origins)
    if has_localhost and not _env_bool("VOICE_AGENT_ALLOW_LOCALHOST_ORIGINS", False):
        raise ValueError(
            "Localhost CORS origins are not allowed in production mode. "
            "Set VOICE_AGENT_ALLOW_LOCALHOST_ORIGINS=true to override."
        )

    if project_name == "justbill" and not _env_bool("JUSTBILL_VERIFY_TLS", True):
        raise ValueError("JUSTBILL_VERIFY_TLS must be true in production mode")


def create_app(project_name):
    """Create a Flask app for a single project."""
    agent = create_agent(project_name)
    app   = Flask(__name__)

    default_cors_origins = [
        r"http://localhost(:\d+)?",
        r"http://127\.0\.0\.1(:\d+)?",
    ]
    cors_origins = _env_list("VOICE_AGENT_CORS_ORIGINS", default_cors_origins)
    CORS(app, origins=cors_origins, supports_credentials=True)

    # ── Shared services ──
    app.session_manager = SessionManager(
        session_ttl=_env_int("VOICE_AGENT_SESSION_TTL_SECONDS", 1800),
        cleanup_interval=_env_int("VOICE_AGENT_SESSION_CLEANUP_SECONDS", 300),
    )
    app.rate_limiter    = RateLimiter(
        max_requests=_env_int("VOICE_AGENT_RATE_LIMIT_MAX", 60),
        window_seconds=_env_int("VOICE_AGENT_RATE_LIMIT_WINDOW_SECONDS", 60),
    )
    app.analytics       = AnalyticsLogger()
    app.admin_token = os.getenv("VOICE_AGENT_ADMIN_TOKEN", "").strip()
    app.public_token = os.getenv("VOICE_AGENT_PUBLIC_TOKEN", "").strip()
    app.require_admin_token = _env_bool("VOICE_AGENT_REQUIRE_ADMIN_TOKEN", False)
    app.require_public_token = _env_bool("VOICE_AGENT_REQUIRE_PUBLIC_TOKEN", False)
    app.public_auth_paths = {"/command", "/voice-command", "/transcribe", "/speak", "/items"}
    app.trust_proxy_headers = _env_bool("VOICE_AGENT_TRUST_PROXY_HEADERS", False)
    app.enable_analytics_endpoint = _env_bool("VOICE_AGENT_ENABLE_ANALYTICS", False)
    app.max_text_length = max(32, min(_env_int("VOICE_AGENT_MAX_TEXT_LENGTH", 500), 5000))
    app.max_content_length = _env_int("VOICE_AGENT_MAX_CONTENT_LENGTH_BYTES", 10 * 1024 * 1024)
    if app.max_content_length < 1024:
        app.max_content_length = 10 * 1024 * 1024
    app.access_log_enabled = _env_bool("VOICE_AGENT_ACCESS_LOG", True)
    app.preload_whisper = _env_bool("VOICE_AGENT_PRELOAD_WHISPER", True)
    app.transcript_preprocessor = TextPreprocessor()
    app.voice_guidance_cache = {
        "signature": None,
        "hotwords": None,
        "initial_prompt": None,
    }
    app.voice_verbose_segments = bool(getattr(agent["config"], "VOICE_VERBOSE_SEGMENTS", False))

    app.agent = agent

    if app.require_admin_token and not app.admin_token:
        raise RuntimeError("Admin endpoint token is required but VOICE_AGENT_ADMIN_TOKEN is empty")
    if not app.admin_token:
        log.warning("[Security] VOICE_AGENT_ADMIN_TOKEN is not set. Admin endpoints will be disabled.")
    if app.require_public_token and not app.public_token:
        raise RuntimeError("Public endpoint token is required but VOICE_AGENT_PUBLIC_TOKEN is empty")

    # ── Request size limit (default 10MB for audio) ──
    app.config['MAX_CONTENT_LENGTH'] = app.max_content_length

    # ── Pre-load Whisper model in background thread ──
    app.whisper_model = None
    app._whisper_lock = threading.Lock()

    def _preload_whisper():
        try:
            from faster_whisper import WhisperModel
            model_name = getattr(agent["config"], "VOICE_MODEL", "small")
            compute_type = getattr(agent["config"], "VOICE_COMPUTE_TYPE", "int8")
            log.info(f"[Whisper] Pre-loading model '{model_name}' in background...")
            app.whisper_model = WhisperModel(
                model_name,
                device="cpu",
                compute_type=compute_type,
            )
            log.info("[Whisper] Model ready! Voice is now available.")
        except Exception as e:
            log.warning(f"[Whisper] Pre-load failed: {e}")

    if app.preload_whisper:
        threading.Thread(target=_preload_whisper, daemon=True).start()

    def _get_client_ip():
        if app.trust_proxy_headers:
            forwarded_for = request.headers.get("X-Forwarded-For", "")
            if forwarded_for:
                return forwarded_for.split(",")[0].strip()
            real_ip = request.headers.get("X-Real-IP", "").strip()
            if real_ip:
                return real_ip
        return request.remote_addr or "unknown"

    def _is_admin_authorized(endpoint_name):
        if not app.admin_token:
            return False
        provided = request.headers.get("X-Admin-Token", "").strip()
        authorized = bool(provided) and secrets.compare_digest(provided, app.admin_token)
        if not authorized:
            log.warning(
                "[Security] Unauthorized admin access endpoint=%s ip=%s request_id=%s",
                endpoint_name,
                _get_client_ip(),
                getattr(g, "request_id", ""),
            )
        return authorized

    def _extract_public_token():
        direct = request.headers.get("X-Client-Token", "").strip()
        if direct:
            return direct
        auth_header = request.headers.get("Authorization", "").strip()
        if auth_header.lower().startswith("bearer "):
            return auth_header[7:].strip()
        return ""

    def _is_public_authorized(endpoint_name):
        if not app.require_public_token:
            return True
        provided = _extract_public_token()
        authorized = bool(provided) and secrets.compare_digest(provided, app.public_token)
        if not authorized:
            log.warning(
                "[Security] Unauthorized public access endpoint=%s ip=%s request_id=%s",
                endpoint_name,
                _get_client_ip(),
                getattr(g, "request_id", ""),
            )
        return authorized

    def _extract_actions(result_json):
        try:
            actions_obj = json.loads(result_json)
        except Exception:
            return []
        if not isinstance(actions_obj, dict):
            return []

        actions = actions_obj.get("actions", [])
        if not isinstance(actions, list):
            return []

        safe_actions = []
        for action in actions:
            if not isinstance(action, dict):
                continue
            action_type = action.get("type")
            if not isinstance(action_type, str) or not action_type.strip():
                continue
            params = action.get("params", {})
            if not isinstance(params, dict):
                params = {}
            safe_actions.append({"type": action_type.strip(), "params": params})
        return safe_actions

    def _clarification_response(text, intent, confidence, page):
        intent_name = (intent or "unknown").replace("_", " ").lower()
        message = (
            f"I heard '{text}', but confidence is low. "
            f"Say yes to confirm {intent_name} or no to cancel."
        )
        return {
            "intent": "CLARIFY",
            "confidence": confidence,
            "message": message,
            "actions": [
                {
                    "type": "clarify",
                    "params": {
                        "heard": text,
                        "suggested_intent": intent,
                        "confidence": confidence,
                    },
                }
            ],
            "page": page,
            "low_conf": True,
            "needs_confirmation": True,
            "session_id": g.session_id,
        }

    # ── Session middleware ──
    @app.before_request
    def _setup_session():
        """Extract or create session from request headers."""
        g.request_id = request.headers.get("X-Request-ID") or secrets.token_hex(8)
        g.request_started_at = time.time()

        if request.path in ("/health", "/ready", "/analytics", "/reload", "/items", "/transcribe", "/speak"):
            g.session_id = None
            g.ctx = None
            return None

        session_id = request.headers.get("X-Session-ID") or request.args.get("session_id")
        sid, ctx = app.session_manager.get_or_create(session_id)
        g.session_id = sid
        g.ctx = ctx

    # ── Rate limiting middleware ──
    @app.before_request
    def _check_rate_limit():
        if request.method == "OPTIONS":
            return None
        if request.path in ("/health", "/ready"):
            return None

        ip = _get_client_ip()
        if not app.rate_limiter.is_allowed(ip):
            return jsonify({"error": "Too many requests. Please slow down."}), 429

    @app.before_request
    def _check_public_auth():
        if request.method == "OPTIONS":
            return None
        if request.path not in app.public_auth_paths:
            return None
        if not _is_public_authorized(request.path):
            return jsonify({"error": "Unauthorized"}), 401

    @app.after_request
    def _add_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Request-ID"] = getattr(g, "request_id", "")

        if app.access_log_enabled:
            started_at = getattr(g, "request_started_at", time.time())
            duration_ms = int((time.time() - started_at) * 1000)
            log.info(
                "[Access] method=%s path=%s status=%s duration_ms=%s ip=%s request_id=%s",
                request.method,
                request.path,
                response.status_code,
                duration_ms,
                _get_client_ip(),
                getattr(g, "request_id", ""),
            )
        return response

    @app.errorhandler(RequestEntityTooLarge)
    def _request_too_large(_err):
        return jsonify({"error": "Request payload too large"}), 413

    @app.errorhandler(500)
    def _internal_error(_err):
        return jsonify({"error": "Internal server error"}), 500

    # ── Health check ──
    @app.route("/health", methods=["GET"])
    def health():
        item_count = len(agent["db"].items) if agent["db"].items else len(agent["db"].load())
        catalog = {}
        if hasattr(agent["db"], "get_health"):
            try:
                catalog = agent["db"].get_health()
            except Exception as exc:
                catalog = {"is_degraded": True, "degraded_reason": f"catalog health unavailable: {exc}"}

        status = "degraded" if catalog.get("is_degraded") else "ok"
        return jsonify({
            "status":  status,
            "project": project_name,
            "name":    agent["config"].PROJECT_NAME,
            "items":   item_count,
            "sessions": app.session_manager.active_count(),
            "whisper":  "ready" if app.whisper_model else "loading",
            "catalog": catalog,
        })

    @app.route("/ready", methods=["GET"])
    def ready():
        whisper_ready = (app.whisper_model is not None) or (not app.preload_whisper)
        catalog = {}
        catalog_ready = True
        if hasattr(agent["db"], "get_health"):
            try:
                catalog = agent["db"].get_health()
                catalog_ready = bool(catalog.get("catalog_ready", True))
            except Exception as exc:
                catalog_ready = False
                catalog = {"catalog_ready": False, "degraded_reason": str(exc)}

        is_ready = whisper_ready and catalog_ready
        return jsonify({
            "ready": is_ready,
            "project": project_name,
            "whisper_ready": whisper_ready,
            "catalog_ready": catalog_ready,
            "catalog": catalog,
        }), (200 if is_ready else 503)

    # ── Analytics endpoint ──
    @app.route("/analytics", methods=["GET"])
    def analytics():
        if not app.enable_analytics_endpoint:
            return jsonify({"error": "Not found"}), 404
        if not _is_admin_authorized("analytics"):
            return jsonify({"error": "Forbidden"}), 403
        return jsonify(app.analytics.get_stats())

    # ── Main command endpoint ──
    @app.route("/command", methods=["POST"])
    def command():
        """
        Text command → intent + actions.
        Body: { "text": "add 2 rings", "page": "menu" }
        Headers: X-Session-ID: <uuid>
        """
        start_time = time.time()
        data = request.get_json(silent=True)
        if data is None:
            data = {}
        if not isinstance(data, dict):
            return jsonify({"error": "Invalid JSON payload"}), 400
        text = (data.get("text") or "").strip()
        page = (data.get("page") or "unknown")
        frontend_context = _normalize_frontend_context(data.get("context"))

        if not text:
            return jsonify({"error": "No text provided"}), 400
        if len(text) > app.max_text_length:
            return jsonify({"error": f"Text too long (max {app.max_text_length} chars)"}), 400
        if len(page) > 80:
            page = page[:80]

        ctx = g.ctx
        if ctx is not None:
            if hasattr(ctx, "set_frontend_context"):
                ctx.set_frontend_context(frontend_context)
            else:
                ctx.last_frontend_context = frontend_context

        try:
            # Delegate to shared processor
            payload = _process_text_command(text, page, frontend_context, g.session_id, start_time)
            return jsonify(payload)

        except Exception as e:
            app.analytics.log_error(text, e)
            log.error(f"[Command] Error: {e}", exc_info=True)
            return jsonify({
                "error": "Internal server error",
                "intent": "ERROR",
                "message": "Something went wrong. Please try again.",
                "session_id": g.session_id,
            }), 500

    # ── Async command job support ──
    app._jobs = {}
    app._jobs_lock = threading.Lock()

    def _store_job_result(job_id, result_obj):
        with app._jobs_lock:
            app._jobs[job_id] = {
                "status": "done",
                "result": result_obj,
                "finished_at": time.time(),
            }

    def _process_text_command(text, page, frontend_context, session_id, start_time=None):
        """Shared processor for command logic. Returns result dict."""
        if start_time is None:
            start_time = time.time()

        ctx = None
        try:
            # Re-establish session context for background jobs if possible
            if session_id:
                sid, ctx = app.session_manager.get_or_create(session_id)

            classify_text = _normalize_category_browse_text(text)
            intent, confidence = agent["clf"].predict(classify_text)
            warn_threshold = _intent_warn_threshold(agent["config"], intent)

            if ctx is not None:
                try:
                    setattr(ctx, "last_intent_confidence", confidence)
                    setattr(ctx, "last_intent_warn_threshold", warn_threshold)
                    if hasattr(ctx, "set_frontend_context"):
                        ctx.set_frontend_context(frontend_context)
                    else:
                        ctx.last_frontend_context = frontend_context
                except Exception:
                    pass

            if confidence < warn_threshold and intent != "OUT_OF_SCOPE" and not _is_confirmation_reply(text):
                if ctx is not None:
                    try:
                        ctx.pending_action = {
                            "intent": intent,
                            "text": text,
                            "created_at": time.time(),
                        }
                    except Exception:
                        pass
                response_time = time.time() - start_time
                app.analytics.log_command(text, "CLARIFY", confidence, response_time)
                return _clarification_response(text, intent, confidence, page)

            result = agent["builder"].build(intent, text, agent["matcher"], ctx)
            actions = _extract_actions(result.get("json", ""))

            response_time = time.time() - start_time
            app.analytics.log_command(text, result["intent"], confidence, response_time)

            return {
                "intent":     result["intent"],
                "confidence": confidence,
                "message":    result.get("message"),
                "actions":    actions,
                "page":       page,
                "low_conf":   confidence < warn_threshold,
                "session_id": session_id,
            }
        except Exception as e:
            app.analytics.log_error(text, e)
            log.error(f"[Command] Background Error: {e}", exc_info=True)
            return {
                "error": "Internal server error",
                "intent": "ERROR",
                "message": "Something went wrong. Please try again.",
                "session_id": session_id,
            }

    @app.route("/command-async", methods=["POST"])
    def command_async():
        """Start processing command in background and return job id immediately."""
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({"error": "Invalid JSON payload"}), 400
        text = (data.get("text") or "").strip()
        page = (data.get("page") or "unknown")
        frontend_context = _normalize_frontend_context(data.get("context"))

        if not text:
            return jsonify({"error": "No text provided"}), 400
        if len(text) > app.max_text_length:
            return jsonify({"error": f"Text too long (max {app.max_text_length} chars)"}), 400

        session_id = g.session_id
        job_id = secrets.token_hex(12)
        with app._jobs_lock:
            app._jobs[job_id] = {"status": "pending", "created_at": time.time()}

        def _worker(jid, txt, pg, ctx_data, sid):
            res = _process_text_command(txt, pg, ctx_data, sid)
            _store_job_result(jid, res)

        thr = threading.Thread(target=_worker, args=(job_id, text, page, frontend_context, session_id), daemon=True)
        thr.start()
        return jsonify({"job_id": job_id, "status": "pending"}), 202

    @app.route("/command-result/<job_id>", methods=["GET"])
    def command_result(job_id):
        with app._jobs_lock:
            record = app._jobs.get(job_id)
        if not record:
            return jsonify({"error": "Job not found"}), 404
        if record.get("status") != "done":
            return jsonify({"job_id": job_id, "status": record.get("status")}), 202
        return jsonify({"job_id": job_id, "status": "done", "result": record.get("result")})

    @app.route("/reload", methods=["POST"])
    def reload_agent():
        """Reload items from DB and retrain classifier."""
        if not _is_admin_authorized("reload"):
            return jsonify({"error": "Forbidden"}), 403

        try:
            agent["db"].last_loaded = 0
            agent["db"].load()
            intents = importlib.import_module(f"projects.{project_name}.intents")
            importlib.reload(intents)
            agent["intents"] = intents
            reject_threshold = getattr(agent["config"], "CONFIDENCE_REJECT", 0.35)
            agent["clf"] = IntentClassifier(
                intents.TRAINING_DATA,
                confidence_threshold=reject_threshold,
            )
            return jsonify({"status": "reloaded", "items": len(agent["db"].load())})
        except Exception as e:
            log.error("[Reload] Error: %s", e, exc_info=True)
            return jsonify({"error": "Reload failed"}), 500

    @app.route("/items", methods=["GET"])
    def get_items():
        """Return all items — useful for frontend autocomplete."""
        items = agent["db"].load()
        return jsonify({"items": [
            {"id": i["id"], "name": i["name"], "price": i["price"]}
            for i in items
        ]})

    # ── Audio transcription helpers ──
    def _ensure_whisper():
        """Ensure Whisper model is loaded."""
        with app._whisper_lock:
            if app.whisper_model is None:
                from faster_whisper import WhisperModel
                model_name = getattr(agent["config"], "VOICE_MODEL", "small")
                compute_type = getattr(agent["config"], "VOICE_COMPUTE_TYPE", "int8")
                log.info(f"[Whisper] Loading model '{model_name}'...")
                app.whisper_model = WhisperModel(
                    model_name,
                    device="cpu",
                    compute_type=compute_type,
                )
                log.info("[Whisper] Model ready!")
        return app.whisper_model

    def _get_voice_guidance(frontend_context=None):
        """Cache hotwords/prompt until item data changes."""
        items = agent["db"].load()
        context_terms = _context_terms_from_frontend(
            frontend_context,
            product_limit=getattr(agent["config"], "VOICE_CONTEXT_PRODUCT_LIMIT", 12),
            term_limit=getattr(agent["config"], "VOICE_CONTEXT_TERM_LIMIT", 48),
        )
        signature = (len(items), agent["db"].last_loaded, tuple(context_terms[:12]))
        cache = app.voice_guidance_cache

        if cache["signature"] != signature:
            terms = _build_voice_terms(agent["config"], items, frontend_context=frontend_context)
            cache["signature"] = signature
            cache["hotwords"] = ", ".join(terms) if terms else None
            cache["initial_prompt"] = _build_initial_prompt(agent["config"], terms)

        return cache["hotwords"], cache["initial_prompt"]

    def _process_audio(audio_file, frontend_context=None):
        """Convert uploaded audio to text via Whisper. Returns (text, error)."""
        import tempfile, subprocess

        ffmpeg_path = shutil.which("ffmpeg")
        if not ffmpeg_path:
            return "", "ffmpeg is not installed"

        model = _ensure_whisper()
        hotwords, initial_prompt = _get_voice_guidance(frontend_context=frontend_context)
        allow_fallback_pass = bool(getattr(agent["config"], "VOICE_ENABLE_FALLBACK_PASS", True))

        tmp_webm = None
        tmp_wav  = None

        try:
            # Save uploaded audio
            tmp_fd, tmp_webm = tempfile.mkstemp(suffix=".webm")
            os.close(tmp_fd)
            audio_file.save(tmp_webm)
            webm_size = os.path.getsize(tmp_webm)
            log.info(f"[Audio] Received: {webm_size} bytes")

            if webm_size < 1000:
                return "", "Recording too short. Hold the mic button longer."

            # Convert webm → wav (voice-optimized)
            tmp_fd2, tmp_wav = tempfile.mkstemp(suffix=".wav")
            os.close(tmp_fd2)
            convert_cmd = [
                ffmpeg_path, "-y", "-nostdin", "-hide_banner", "-loglevel", "error", "-i", tmp_webm,
                "-af", "highpass=f=80,lowpass=f=4500,volume=1.8",
                "-ar", "16000", "-ac", "1", "-sample_fmt", "s16",
                tmp_wav
            ]
            result = subprocess.run(convert_cmd, capture_output=True, timeout=10)
            if result.returncode != 0:
                return "", "Failed to process audio"

            base_options = {
                "language": getattr(agent["config"], "VOICE_LANGUAGE", "en"),
                "task": "transcribe",
                "beam_size": getattr(agent["config"], "VOICE_BEAM_SIZE", 2),
                "best_of": getattr(agent["config"], "VOICE_BEST_OF", 2),
                "patience": getattr(agent["config"], "VOICE_PATIENCE", 1.0),
                "temperature": getattr(agent["config"], "VOICE_TEMPERATURE", 0.0),
                "repetition_penalty": 1.05,
                "no_repeat_ngram_size": 3,
                "condition_on_previous_text": False,
                "no_speech_threshold": getattr(agent["config"], "VOICE_NO_SPEECH_THRESHOLD", 0.4),
                "log_prob_threshold": getattr(agent["config"], "VOICE_LOG_PROB_THRESHOLD", -1.2),
                "hallucination_silence_threshold": getattr(
                    agent["config"], "VOICE_HALLUCINATION_SILENCE_THRESHOLD", 1.5
                ),
                "initial_prompt": initial_prompt,
                "hotwords": hotwords,
                "vad_filter": True,
                "vad_parameters": dict(
                    min_silence_duration_ms=getattr(agent["config"], "VOICE_VAD_MIN_SILENCE_MS", 180),
                    speech_pad_ms=getattr(agent["config"], "VOICE_VAD_SPEECH_PAD_MS", 180),
                ),
            }

            def _run_transcription(pass_name, options):
                segments, info = model.transcribe(tmp_wav, **options)
                lang = getattr(info, "language", "unknown")
                lang_prob = getattr(info, "language_probability", 0.0)
                log.info(f"[Audio] {pass_name} language={lang} prob={lang_prob:.2f}")

                segments_list = []
                for seg in segments:
                    if app.voice_verbose_segments:
                        log.info(
                            f"  [{pass_name}] segment [{seg.start:.1f}s-{seg.end:.1f}s] "
                            f"p={seg.no_speech_prob:.2f}: '{seg.text}'"
                        )
                    if seg.no_speech_prob < 0.75:
                        segments_list.append(seg.text)

                raw_text = " ".join(segments_list).strip()

                # Hallucination check
                words = raw_text.split()
                if len(words) > 6:
                    chunk = " ".join(words[:3])
                    if raw_text.count(chunk) >= 3:
                        log.warning(f"[Audio] Hallucination detected during {pass_name}: '{raw_text[:60]}...'")
                        raw_text = ""

                normalized_text = _normalize_transcript_text(raw_text, app.transcript_preprocessor)
                if raw_text:
                    shift = _wer_like_shift(raw_text, normalized_text)
                    log.info(
                        "[Audio] %s normalization_shift=%.3f raw_tokens=%s norm_tokens=%s",
                        pass_name,
                        shift,
                        len(raw_text.split()),
                        len(str(normalized_text or "").split()),
                    )
                if raw_text and normalized_text and normalized_text != raw_text.lower().strip():
                    log.info(f"[Audio] {pass_name} normalized: '{raw_text}' -> '{normalized_text}'")

                selected_text, selected_meta = _select_transcript_candidate(
                    raw_text,
                    normalized_text,
                    agent["clf"],
                )
                if selected_text and selected_text != normalized_text:
                    log.info(
                        "[Audio] %s selected raw transcript over normalized variant",
                        pass_name,
                    )
                if selected_meta.get("selected"):
                    log.info(
                        "[Audio] %s transcript_choice=%s conf=%.3f intent=%s",
                        pass_name,
                        selected_meta.get("selected"),
                        selected_meta.get("confidence", 0.0),
                        selected_meta.get("intent", "OUT_OF_SCOPE"),
                    )

                return selected_text

            text = _run_transcription("primary", base_options)

            if not text and allow_fallback_pass:
                retry_options = {
                    **base_options,
                    "vad_filter": False,
                    "no_speech_threshold": 0.25,
                    "log_prob_threshold": -1.5,
                    "hallucination_silence_threshold": None,
                    "temperature": [0.0, 0.2, 0.4, 0.6, 0.8],
                }
                text = _run_transcription("fallback", retry_options)

            if len(text) > app.max_text_length:
                text = text[:app.max_text_length]

            log.info(f"[Audio] Final transcript: '{text}'")
            return text, ""

        finally:
            for f in [tmp_webm, tmp_wav]:
                if f:
                    try: os.unlink(f)
                    except OSError: pass

    app._process_audio_func = _process_audio

    @app.route("/transcribe", methods=["POST"])
    def transcribe():
        """Transcribe audio to text only."""
        try:
            audio_file = request.files.get("audio")
            if not audio_file:
                return jsonify({"error": "No audio file"}), 400
            if not (audio_file.mimetype or "").startswith("audio/"):
                return jsonify({"error": "Invalid audio file type"}), 400

            frontend_context = {}
            context_raw = request.form.get("context_json") or request.form.get("context")
            if context_raw:
                try:
                    frontend_context = _normalize_frontend_context(json.loads(context_raw))
                except Exception:
                    frontend_context = {}

            text, error = _process_audio(audio_file, frontend_context=frontend_context)
            if error:
                return jsonify({"text": "", "error": error})
            return jsonify({"text": text, "auto_submit": True})

        except ImportError:
            return jsonify({"error": "faster-whisper not installed"}), 500
        except Exception as e:
            log.error(f"[Transcribe] {type(e).__name__}: {e}")
            return jsonify({"error": "Transcription failed"}), 500

    @app.route("/speak", methods=["POST"])
    def speak():
        """Synthesize text to speech and return WAV audio."""
        try:
            data = request.get_json(silent=True) or {}
            if not isinstance(data, dict):
                return jsonify({"error": "Invalid JSON payload"}), 400

            text = (data.get("text") or "").strip()
            if not text:
                return jsonify({"error": "No text provided"}), 400
            if len(text) > app.max_text_length:
                return jsonify({"error": f"Text too long (max {app.max_text_length} chars)"}), 400

            audio_bytes = synthesize_audio_bytes(text, voice_hint=getattr(agent["config"], "TTS_VOICE_HINT", ""))
            if not audio_bytes:
                return jsonify({"error": "Unable to synthesize speech"}), 500

            return send_file(
                BytesIO(audio_bytes),
                mimetype="audio/mpeg",
                as_attachment=False,
                download_name="speech.mp3",
                max_age=0,
            )
        except Exception as e:
            log.error(f"[Speak] {type(e).__name__}: {e}")
            return jsonify({"error": "Speech synthesis failed"}), 500

    @app.route("/voice-command", methods=["POST"])
    def voice_command():
        """
        Combined: transcribe audio → process command → return actions.
        Form data: audio (file), page (string)
        Headers: X-Session-ID
        """
        start_time = time.time()

        try:
            audio_file = request.files.get("audio")
            if not audio_file:
                return jsonify({"error": "No audio file"}), 400
            if not (audio_file.mimetype or "").startswith("audio/"):
                return jsonify({"error": "Invalid audio file type"}), 400

            page = request.form.get("page", "unknown")
            if len(page) > 80:
                page = page[:80]
            ctx  = g.ctx
            frontend_context = {}

            context_raw = request.form.get("context_json") or request.form.get("context")
            if context_raw:
                try:
                    frontend_context = _normalize_frontend_context(json.loads(context_raw))
                except Exception:
                    frontend_context = {}

            if ctx is not None:
                if hasattr(ctx, "set_frontend_context"):
                    ctx.set_frontend_context(frontend_context)
                else:
                    ctx.last_frontend_context = frontend_context

            # Step 1: Transcribe
            text, error = _process_audio(audio_file, frontend_context=frontend_context)
            if error:
                return jsonify({"text": "", "error": error})
            if not text:
                return jsonify({
                    "text": "",
                    "message": "Could not understand audio. Please try again.",
                })

            # Step 2: Process command
            try:
                classify_text = _normalize_category_browse_text(text)
                intent, confidence = agent["clf"].predict(classify_text)
                warn_threshold = _intent_warn_threshold(agent["config"], intent)

                if ctx is not None:
                    setattr(ctx, "last_intent_confidence", confidence)
                    setattr(ctx, "last_intent_warn_threshold", warn_threshold)

                if confidence < warn_threshold and intent != "OUT_OF_SCOPE" and not _is_confirmation_reply(text):
                    if ctx is not None:
                        ctx.pending_action = {
                            "intent": intent,
                            "text": text,
                            "created_at": time.time(),
                        }
                    response_time = time.time() - start_time
                    app.analytics.log_command(text, "CLARIFY", confidence, response_time)
                    return jsonify(_clarification_response(text, intent, confidence, page))

                cmd_result = agent["builder"].build(
                    intent, text, agent["matcher"], ctx
                )

                actions = _extract_actions(cmd_result.get("json", ""))

                response_time = time.time() - start_time
                app.analytics.log_command(text, cmd_result["intent"], confidence, response_time)

                log.info(f"[VoiceCmd] '{text}' → {cmd_result['intent']} "
                         f"({confidence:.2f}) [{response_time*1000:.0f}ms]")

                return jsonify({
                    "text":       text,
                    "intent":     cmd_result["intent"],
                    "confidence": confidence,
                    "message":    cmd_result["message"],
                    "actions":    actions,
                    "page":       page,
                    "low_conf":   confidence < warn_threshold,
                    "session_id": g.session_id,
                })

            except Exception as e:
                app.analytics.log_error(text, e)
                log.error(f"[VoiceCmd] Command error: {e}")
                return jsonify({
                    "text":    text,
                    "intent":  "ERROR",
                    "message": f"Heard: '{text}' but could not process. Please try again.",
                    "actions": [],
                    "error":   "Command processing failed",
                    "session_id": g.session_id,
                })

        except ImportError:
            return jsonify({"error": "faster-whisper not installed"}), 500
        except Exception as e:
            log.error(f"[VoiceCmd] {type(e).__name__}: {e}")
            return jsonify({"error": "Voice command failed"}), 500

    # ── WebSocket Handlers ──
    socketio = SocketIO(app, cors_allowed_origins=_socketio_cors_origins(), max_http_buffer_size=50*1024*1024)
    app.socketio = socketio
    session_buffers = {}

    @socketio.on('audio_chunk')
    def handle_audio_chunk(data):
        if request.sid not in session_buffers:
            session_buffers[request.sid] = bytearray()
        if isinstance(data, dict) and 'audio' in data:
            session_buffers[request.sid].extend(data['audio'])
        elif isinstance(data, (bytes, bytearray)):
            session_buffers[request.sid].extend(data)

    @socketio.on('stop_recording')
    def handle_stop_recording(data):
        start_time = time.time()
        if not isinstance(data, dict):
            data = {}
        
        buffer = session_buffers.pop(request.sid, bytearray())
        if not buffer:
            emit('command_result', {"error": "No audio received."})
            return

        frontend_context = data.get('context', {})
        page = data.get('page', 'unknown')

        dummy_audio = DummyFile(bytes(buffer))
        text, error = _process_audio(dummy_audio, frontend_context=frontend_context)
        
        if error:
            emit('command_result', {"text": "", "error": error})
            return
            
        if not text:
            emit('command_result', {"text": "", "message": "Could not understand audio."})
            return

        try:
            sid, ctx = app.session_manager.get_or_create(data.get('session_id'))
            if ctx is not None:
                ctx.set_frontend_context(frontend_context)

            classify_text = _normalize_category_browse_text(text)
            intent, confidence = agent["clf"].predict(classify_text)
            warn_threshold = _intent_warn_threshold(agent["config"], intent)

            if ctx is not None:
                setattr(ctx, "last_intent_confidence", confidence)
                setattr(ctx, "last_intent_warn_threshold", warn_threshold)

            if confidence < warn_threshold and intent != "OUT_OF_SCOPE" and not _is_confirmation_reply(text):
                if ctx is not None:
                    ctx.pending_action = {
                        "intent": intent,
                        "text": text,
                        "created_at": time.time(),
                    }
                emit('command_result', _clarification_response(text, intent, confidence, page))
                return
            
            cmd_result = agent["builder"].build(intent, text, agent["matcher"], ctx)
            actions = _extract_actions(cmd_result.get("json", ""))

            emit('command_result', {
                "text": text,
                "intent": cmd_result["intent"],
                "confidence": confidence,
                "message": cmd_result["message"],
                "actions": actions,
                "page": page,
                "low_conf": confidence < warn_threshold,
                "session_id": sid
            })
        except Exception as e:
            log.error(f"[WS] Error: {e}")
            emit('command_result', {"error": "Processing failed"})

    return app


def run_project(project_name, port, debug=False, production=False):
    """Run a single project on a given port."""
    if production:
        os.environ["VOICE_AGENT_PRODUCTION"] = "true"

    log.info("Starting %s agent on http://localhost:%s", project_name, port)
    app = create_app(project_name)

    if production:
        try:
            from waitress import serve
        except ImportError:
            log.error("Waitress is not installed. Run: pip install waitress")
            sys.exit(1)

        threads = _env_int("VOICE_AGENT_WORKER_THREADS", 8)
        log.info("Running in production mode with Waitress (threads=%s)", threads)
        # Waitress doesn't support WebSockets natively well with Flask-SocketIO without a proxy.
        # For simplicity, we use app.socketio.run even in prod if the user is using this script.
        app.socketio.run(app, host="0.0.0.0", port=port, debug=False)
        return

    app.socketio.run(app, host="0.0.0.0", port=port, debug=debug, use_reloader=False)


def run_all(production=False):
    """Run all projects simultaneously on different ports."""
    threads = []
    resolved_ports = {}
    for project, default_port in PROJECT_PORTS.items():
        try:
            resolved_port = _resolve_project_port(project, default_port, explicit_port=False)
            resolved_ports[project] = resolved_port
        except ValueError as e:
            log.error(f"[Startup] {project}: {e}")
            resolved_ports[project] = default_port
    
    for project, port in resolved_ports.items():
        t = threading.Thread(
            target=run_project,
            args=(project, port, False, production),
            daemon=True,
            name=f"ProjectThread-{project}"
        )
        threads.append(t)
        t.start()

    print("\n" + "="*55)
    print("  All Voice Agents Running:")
    for project, port in resolved_ports.items():
        print(f"    {project:12} -> http://localhost:{port}")
    print("="*55)
    print("  Press Ctrl+C to stop all agents\n")

    try:
        for t in threads:
            t.join()
    except KeyboardInterrupt:
        print("\n  Stopping all agents...")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Voice Agent Web Server")
    parser.add_argument("--project", default=None,
                        help="Project: cravehub | ecommerce | hospital | hotel | justbill")
    parser.add_argument("--port",    type=int, default=None,
                        help="Port number (default: auto per project)")
    parser.add_argument("--all",     action="store_true",
                        help="Run all projects simultaneously")
    parser.add_argument("--debug",   action="store_true",
                        help="Enable Flask debug mode")
    parser.add_argument("--production", action="store_true",
                        help="Run with Waitress production server")
    args = parser.parse_args()

    production_mode = args.production or _env_bool("VOICE_AGENT_PRODUCTION", False)
    if production_mode:
        os.environ["VOICE_AGENT_PRODUCTION"] = "true"

    if production_mode and args.debug:
        log.warning("Ignoring --debug in production mode")
    debug_mode = args.debug and not production_mode

    def _validate_or_exit(project_name, port):
        try:
            _validate_runtime_settings(project_name, port, production_mode)
        except ValueError as exc:
            log.error("%s", exc)
            sys.exit(1)

    if args.all:
        for project, project_port in PROJECT_PORTS.items():
            _validate_or_exit(project, project_port)
        run_all(production=production_mode)
    elif args.project:
        args.project = args.project.lower()
        if args.project not in AVAILABLE_PROJECTS:
            print(f"  Unknown project '{args.project}'. Choose: {', '.join(AVAILABLE_PROJECTS)}")
            sys.exit(1)
        requested_port = args.port if args.port is not None else PROJECT_PORTS[args.project]
        port = _resolve_project_port(args.project, requested_port, explicit_port=args.port is not None)
        _validate_or_exit(args.project, port)
        run_project(args.project, port, debug_mode, production_mode)
    else:
        # Interactive project selection
        print("\n  Available projects:")
        for i, p in enumerate(AVAILABLE_PROJECTS, 1):
            print(f"    {i}. {p}  (port {PROJECT_PORTS[p]})")
        print(f"    {len(AVAILABLE_PROJECTS)+1}. ALL projects")
        choice = input("\n  Select (name, number, or 'all'): ").strip().lower()

        if choice in (str(len(AVAILABLE_PROJECTS)+1), "all"):
            for project, project_port in PROJECT_PORTS.items():
                _validate_or_exit(project, project_port)
            run_all(production=production_mode)
        else:
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(AVAILABLE_PROJECTS):
                    choice = AVAILABLE_PROJECTS[idx]
                else:
                    print("Invalid."); sys.exit(1)

            if choice not in AVAILABLE_PROJECTS:
                print(f"  Unknown project '{choice}'. Choose: {', '.join(AVAILABLE_PROJECTS)}")
                sys.exit(1)

            requested_port = args.port if args.port is not None else PROJECT_PORTS.get(choice, 5000)
            port = _resolve_project_port(choice, requested_port, explicit_port=args.port is not None)
            _validate_or_exit(choice, port)
            run_project(choice, port, debug_mode, production_mode)
