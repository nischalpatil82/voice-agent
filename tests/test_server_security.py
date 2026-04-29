import types

import server
from core.context import ConversationContext


class DummyDB:
    def __init__(self):
        self.items = [
            {"id": 1001, "name": "Diamond Ring", "price": 149999, "keywords": ["diamond", "ring"]}
        ]
        self.last_loaded = 0
        self.catalog_ready = True

    def load(self):
        return list(self.items)

    def get_health(self):
        return {
            "source": "live",
            "items": len(self.items),
            "catalog_ready": self.catalog_ready,
            "is_degraded": not self.catalog_ready,
            "degraded_reason": "catalog unavailable" if not self.catalog_ready else "",
        }


class DummyClassifier:
    def predict(self, _text):
        return "HELP", 0.99


class LowConfidenceClassifier:
    def predict(self, _text):
        return "ADD_TO_CART", 0.2


class DummyBuilder:
    def build(self, _intent, _text, _matcher, _ctx):
        return {"intent": "HELP", "message": "ok", "json": "{}"}


class FailingBuilder:
    def build(self, _intent, _text, _matcher, _ctx):
        raise RuntimeError("sensitive internal details")


class MappingClassifier:
    def __init__(self, rows):
        self.rows = rows

    def predict(self, text):
        return self.rows.get(text, ("OUT_OF_SCOPE", 0.1))


def _build_fake_agent(classifier=None, db=None, builder=None):
    config = types.SimpleNamespace(
        PROJECT_NAME="JustBill Jewellery",
        CONFIDENCE_WARN=0.4,
        VOICE_MODEL="small",
        VOICE_COMPUTE_TYPE="int8",
    )
    return {
        "config": config,
        "intents": types.SimpleNamespace(TRAINING_DATA=[]),
        "db": db or DummyDB(),
        "matcher": object(),
        "clf": classifier or DummyClassifier(),
        "builder": builder or DummyBuilder(),
    }


def _create_test_client(monkeypatch, *, classifier=None, db=None, builder=None):
    monkeypatch.setenv("VOICE_AGENT_PRELOAD_WHISPER", "false")
    monkeypatch.setenv("VOICE_AGENT_MAX_TEXT_LENGTH", "50")
    monkeypatch.setenv("VOICE_AGENT_RATE_LIMIT_MAX", "1000")
    monkeypatch.setenv("VOICE_AGENT_REQUIRE_PUBLIC_TOKEN", "false")
    monkeypatch.delenv("VOICE_AGENT_ADMIN_TOKEN", raising=False)
    monkeypatch.delenv("VOICE_AGENT_PUBLIC_TOKEN", raising=False)
    monkeypatch.delenv("VOICE_AGENT_ENABLE_ANALYTICS", raising=False)

    monkeypatch.setattr(
        server,
        "create_agent",
        lambda _project: _build_fake_agent(classifier=classifier, db=db, builder=builder),
    )
    app = server.create_app("justbill")
    app.config.update(TESTING=True)
    return app.test_client()


def test_reload_requires_admin_token(monkeypatch):
    client = _create_test_client(monkeypatch)
    resp = client.post("/reload")
    assert resp.status_code == 403


def test_analytics_hidden_when_disabled(monkeypatch):
    client = _create_test_client(monkeypatch)
    resp = client.get("/analytics")
    assert resp.status_code == 404


def test_command_rejects_too_long_text(monkeypatch):
    client = _create_test_client(monkeypatch)
    resp = client.post("/command", json={"text": "x" * 80, "page": "menu"})
    assert resp.status_code == 400
    assert "Text too long" in resp.get_json()["error"]


def test_command_rejects_non_object_json(monkeypatch):
    client = _create_test_client(monkeypatch)
    resp = client.post("/command", data='["bad"]', content_type="application/json")
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "Invalid JSON payload"


def test_health_includes_security_headers(monkeypatch):
    client = _create_test_client(monkeypatch)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"


def test_resolve_project_port_falls_back_when_default_is_busy(monkeypatch):
    def fake_port_is_available(port, host="0.0.0.0"):
        return int(port) == 5005

    monkeypatch.setattr(server, "_port_is_available", fake_port_is_available)

    resolved = server._resolve_project_port("justbill", 5004, explicit_port=False)

    assert resolved == 5005


def test_resolve_project_port_rejects_explicit_busy_port(monkeypatch):
    monkeypatch.setattr(server, "_port_is_available", lambda _port, host="0.0.0.0": False)

    try:
        server._resolve_project_port("justbill", 5004, explicit_port=True)
    except ValueError as exc:
        assert "already in use" in str(exc)
    else:
        raise AssertionError("Expected ValueError for an occupied explicit port")


def test_conversation_context_syncs_cart_snapshot_from_frontend():
    ctx = ConversationContext()
    ctx.set_frontend_context(
        {
            "cart_snapshot": [
                {"product_id": 11, "name": "Luxury Bangle", "quantity": 2, "price": 1250},
                {"product_id": 22, "name": "Gold Chain", "quantity": 1, "price": 900},
            ]
        }
    )

    assert ctx.get_cart_count() == 3
    assert ctx.get_cart_total() == 3400
    assert ctx.get_cart_summary().startswith("  Luxury Bangle x2 = Rs 2,500")


def test_speak_returns_audio(monkeypatch):
    client = _create_test_client(monkeypatch)
    monkeypatch.setattr(server, "synthesize_audio_bytes", lambda _text, voice_hint="": b"ID3mockmp3")
    resp = client.post("/speak", json={"text": "Hello from JustBill"})
    assert resp.status_code == 200
    assert resp.headers.get("Content-Type", "").startswith("audio/mpeg")


def test_command_requires_public_token_when_enabled(monkeypatch):
    monkeypatch.setenv("VOICE_AGENT_PRELOAD_WHISPER", "false")
    monkeypatch.setenv("VOICE_AGENT_MAX_TEXT_LENGTH", "50")
    monkeypatch.setenv("VOICE_AGENT_RATE_LIMIT_MAX", "1000")
    monkeypatch.setenv("VOICE_AGENT_REQUIRE_PUBLIC_TOKEN", "true")
    monkeypatch.setenv("VOICE_AGENT_PUBLIC_TOKEN", "secret-token")
    monkeypatch.setattr(server, "create_agent", lambda _project: _build_fake_agent())

    app = server.create_app("justbill")
    app.config.update(TESTING=True)
    client = app.test_client()

    resp = client.post("/command", json={"text": "help", "page": "menu"})
    assert resp.status_code == 401
    assert resp.get_json()["error"] == "Unauthorized"


def test_command_accepts_public_token_when_enabled(monkeypatch):
    monkeypatch.setenv("VOICE_AGENT_PRELOAD_WHISPER", "false")
    monkeypatch.setenv("VOICE_AGENT_MAX_TEXT_LENGTH", "50")
    monkeypatch.setenv("VOICE_AGENT_RATE_LIMIT_MAX", "1000")
    monkeypatch.setenv("VOICE_AGENT_REQUIRE_PUBLIC_TOKEN", "true")
    monkeypatch.setenv("VOICE_AGENT_PUBLIC_TOKEN", "secret-token")
    monkeypatch.setattr(server, "create_agent", lambda _project: _build_fake_agent())

    app = server.create_app("justbill")
    app.config.update(TESTING=True)
    client = app.test_client()

    resp = client.post(
        "/command",
        json={"text": "help", "page": "menu"},
        headers={"X-Client-Token": "secret-token"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["intent"] == "HELP"


def test_ready_reports_unready_when_catalog_not_ready(monkeypatch):
    db = DummyDB()
    db.catalog_ready = False
    client = _create_test_client(monkeypatch, db=db)
    resp = client.get("/ready")
    assert resp.status_code == 503
    payload = resp.get_json()
    assert payload["ready"] is False
    assert payload["catalog_ready"] is False


def test_command_returns_clarify_on_low_confidence(monkeypatch):
    client = _create_test_client(monkeypatch, classifier=LowConfidenceClassifier())
    resp = client.post("/command", json={"text": "add ring maybe", "page": "menu"})
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["intent"] == "CLARIFY"
    assert payload["needs_confirmation"] is True
    assert payload["low_conf"] is True


def test_command_clarify_stores_pending_action_in_session(monkeypatch):
    monkeypatch.setenv("VOICE_AGENT_PRELOAD_WHISPER", "false")
    monkeypatch.setenv("VOICE_AGENT_MAX_TEXT_LENGTH", "50")
    monkeypatch.setenv("VOICE_AGENT_RATE_LIMIT_MAX", "1000")
    monkeypatch.setenv("VOICE_AGENT_REQUIRE_PUBLIC_TOKEN", "false")
    monkeypatch.setattr(
        server,
        "create_agent",
        lambda _project: _build_fake_agent(classifier=LowConfidenceClassifier()),
    )

    app = server.create_app("justbill")
    app.config.update(TESTING=True)
    client = app.test_client()

    resp = client.post("/command", json={"text": "add ring maybe", "page": "menu"})
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["intent"] == "CLARIFY"

    session_id = payload["session_id"]
    ctx = app.session_manager.get(session_id)
    assert ctx is not None
    assert isinstance(ctx.pending_action, dict)
    assert ctx.pending_action["intent"] == "ADD_TO_CART"


def test_command_error_does_not_leak_exception_details(monkeypatch):
    client = _create_test_client(monkeypatch, builder=FailingBuilder())
    resp = client.post("/command", json={"text": "help", "page": "menu"})
    assert resp.status_code == 500
    payload = resp.get_json()
    assert payload["error"] == "Internal server error"
    assert "sensitive internal details" not in str(payload)


def test_normalize_category_browse_text_variants():
    assert server._normalize_category_browse_text("show me necklace") == "show necklaces"
    assert server._normalize_category_browse_text("show me earrings") == "show earrings"
    assert server._normalize_category_browse_text("open earring") == "open earrings"
    assert server._normalize_category_browse_text("show me pearl necklace") == "show me pearl necklace"


def test_normalize_frontend_context_sanitizes_expected_fields():
    raw = {
        "page_url": "/collections?category=rings",
        "locale": "en-IN",
        "selected_product": {"id": 5, "name": "Luxury Bangle"},
        "visible_products": [
            {"id": 5, "name": "Luxury Bangle", "category": "bracelets", "keywords": ["bangle", "luxury"]},
            {"id": 9, "name": "Nova Drop Earrings", "keywords": ["earrings"]},
        ],
        "active_filters": {"category": "bracelets", "brand": "gold"},
        "cart_snapshot": [{"product_id": 5, "name": "Luxury Bangle", "quantity": 1}],
    }

    normalized = server._normalize_frontend_context(raw)
    assert normalized["locale"] == "en-IN"
    assert normalized["selected_product"]["name"] == "Luxury Bangle"
    assert len(normalized["visible_products"]) == 2
    assert normalized["active_filters"]["category"] == "bracelets"


def test_build_voice_terms_uses_full_catalog_and_context_terms():
    config = types.SimpleNamespace(
        VOICE_HINT_TERMS=["JustBill", "cart"],
        VOICE_HINT_PRODUCT_LIMIT=1,
        VOICE_HINT_USE_FULL_CATALOG=True,
        VOICE_HOTWORD_LIMIT=120,
        VOICE_CONTEXT_PRODUCT_LIMIT=10,
        VOICE_CONTEXT_TERM_LIMIT=20,
    )
    items = [
        {"name": "Luxury Bangle", "keywords": ["bangle", "luxury"]},
        {"name": "Gold Chain", "keywords": ["gold", "chain"]},
    ]
    frontend_context = {
        "selected_product": {"name": "Mangala Sutra 22K"},
        "visible_products": [{"name": "Nova Drop Earrings", "keywords": ["earrings"]}],
        "active_filters": {"category": "bracelets"},
    }

    terms = server._build_voice_terms(config, items, frontend_context=frontend_context)
    assert "Luxury Bangle" in terms
    assert "Gold Chain" in terms
    assert "Mangala Sutra 22K" in terms
    assert "Nova Drop Earrings" in terms


def test_wer_like_shift_reports_text_normalization_delta():
    unchanged = server._wer_like_shift("add to cart", "add to cart")
    corrected = server._wer_like_shift("add to card", "add to cart")
    assert unchanged == 0.0
    assert corrected > 0.0


def test_intent_warn_threshold_uses_per_intent_override():
    config = types.SimpleNamespace(
        CONFIDENCE_WARN=0.4,
        INTENT_WARN_THRESHOLDS={"ADD_TO_CART": 0.52},
    )
    assert server._intent_warn_threshold(config, "ADD_TO_CART") == 0.52
    assert server._intent_warn_threshold(config, "SEARCH") == 0.4


def test_select_transcript_candidate_prefers_higher_confidence_variant():
    clf = MappingClassifier(
        {
            "add to cart": ("ADD_TO_CART", 0.84),
            "add to card": ("ADD_TO_CART", 0.31),
        }
    )

    text, meta = server._select_transcript_candidate("add to card", "add to cart", clf)
    assert text == "add to cart"
    assert meta["selected"] == "normalized"
    assert meta["confidence"] == 0.84
