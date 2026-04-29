import requests

from projects.justbill.database import ItemDB


class _DummyConfig:
    API_BASE_URL = "https://example.invalid"
    RELOAD_EVERY = 0
    FALLBACK_ITEMS = [
        {"id": 1001, "name": "Fallback Ring", "price": 999, "keywords": ["ring"]},
    ]


class _MockResponse:
    def __init__(self, payload):
        self._payload = payload
        self.content = b"{}"

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_database_strict_mode_without_fallback_marks_unready(monkeypatch):
    monkeypatch.setenv("VOICE_AGENT_PRODUCTION", "true")
    monkeypatch.setenv("JUSTBILL_STRICT_CATALOG", "true")
    monkeypatch.setenv("JUSTBILL_ALLOW_FALLBACK_IN_PRODUCTION", "false")
    monkeypatch.setenv("JUSTBILL_VERIFY_TLS", "true")

    db = ItemDB(_DummyConfig)

    def _raise_connection_error(*_args, **_kwargs):
        raise requests.exceptions.ConnectionError("upstream unavailable")

    db.session.post = _raise_connection_error

    items = db.load()
    health = db.get_health()

    assert items == []
    assert health["catalog_ready"] is False
    assert health["source"] == "empty"


def test_database_allows_fallback_when_enabled_in_production(monkeypatch):
    monkeypatch.setenv("VOICE_AGENT_PRODUCTION", "true")
    monkeypatch.setenv("JUSTBILL_STRICT_CATALOG", "false")
    monkeypatch.setenv("JUSTBILL_ALLOW_FALLBACK_IN_PRODUCTION", "true")
    monkeypatch.setenv("JUSTBILL_VERIFY_TLS", "true")

    db = ItemDB(_DummyConfig)

    def _raise_connection_error(*_args, **_kwargs):
        raise requests.exceptions.ConnectionError("upstream unavailable")

    db.session.post = _raise_connection_error

    items = db.load()
    health = db.get_health()

    assert len(items) == 1
    assert items[0]["name"] == "Fallback Ring"
    assert health["source"] == "fallback"
    assert health["is_degraded"] is True


def test_database_ignores_invalid_ca_bundle_path(monkeypatch):
    monkeypatch.delenv("VOICE_AGENT_PRODUCTION", raising=False)
    monkeypatch.setenv("JUSTBILL_CA_BUNDLE_PATH", "C:/not/a/real/ca-bundle.pem")

    db = ItemDB(_DummyConfig)
    assert db.ca_bundle_path == ""


def test_database_zero_reload_fetches_live_catalog_each_call(monkeypatch):
    monkeypatch.delenv("JUSTBILL_FETCH_LIVE_EVERY_REQUEST", raising=False)

    db = ItemDB(_DummyConfig)
    calls = {"count": 0}

    def _post(*_args, **_kwargs):
        calls["count"] += 1
        product_id = calls["count"]
        return _MockResponse(
            {
                "ml_product": [
                    {
                        "productID": product_id,
                        "productName": f"Live Product {product_id}",
                        "sellingPrice": 12345,
                        "isActive": True,
                    }
                ]
            }
        )

    db.session.post = _post

    first_name = db.load()[0]["name"]
    second_name = db.load()[0]["name"]

    assert calls["count"] == 2
    assert first_name == "Live Product 1"
    assert second_name == "Live Product 2"


def test_database_fetch_live_every_request_overrides_reload_interval(monkeypatch):
    monkeypatch.setenv("JUSTBILL_FETCH_LIVE_EVERY_REQUEST", "true")

    class _CachedConfig(_DummyConfig):
        RELOAD_EVERY = 300

    db = ItemDB(_CachedConfig)
    calls = {"count": 0}

    def _post(*_args, **_kwargs):
        calls["count"] += 1
        product_id = calls["count"]
        return _MockResponse(
            {
                "ml_product": [
                    {
                        "productID": product_id,
                        "productName": f"Fresh Product {product_id}",
                        "sellingPrice": 9999,
                        "isActive": True,
                    }
                ]
            }
        )

    db.session.post = _post

    db.load()
    db.load()

    assert db.reload_every_seconds == 0
    assert calls["count"] == 2


def test_database_normalize_product_keeps_category_and_attributes(monkeypatch):
    monkeypatch.delenv("JUSTBILL_FETCH_LIVE_EVERY_REQUEST", raising=False)
    db = ItemDB(_DummyConfig)

    normalized = db._normalize_product(
        {
            "productID": 77,
            "productName": "Heritage Bangle",
            "sellingPrice": 123456,
            "categoryName": "Bracelets",
            "metalType": "Gold",
            "purity": "22KT",
            "isActive": True,
        }
    )

    assert normalized is not None
    assert normalized["category"] == "Bracelets"
    assert normalized["attributes"]["metalType"] == "Gold"
    assert normalized["attributes"]["purity"] == "22KT"
