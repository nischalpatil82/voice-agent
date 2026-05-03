"""
projects/justbill/database.py
Loads products live from JustBill .NET API with retry logic and error handling.
"""
import logging
import os
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


LOG = logging.getLogger(__name__)


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


def _safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


class ItemDB:
    def __init__(self, config):
        self.config      = config
        self.items       = []
        self.last_loaded = 0
        self.last_live_success_at = 0
        self.last_error = ""
        self.last_error_at = 0
        self.last_source = "empty"
        self.api_timeout_seconds = _env_int("JUSTBILL_API_TIMEOUT_SECONDS", 15)
        if self.api_timeout_seconds <= 0:
            LOG.warning("[JustBill API] Invalid JUSTBILL_API_TIMEOUT_SECONDS=%s; defaulting to 15", self.api_timeout_seconds)
            self.api_timeout_seconds = 15

        configured_reload_every = getattr(self.config, "RELOAD_EVERY", 300)
        if configured_reload_every is None:
            configured_reload_every = 300
        try:
            configured_reload_every = int(configured_reload_every)
        except (TypeError, ValueError):
            LOG.warning("[JustBill API] Invalid RELOAD_EVERY=%s; using 300", configured_reload_every)
            configured_reload_every = 300
        if configured_reload_every < 0:
            LOG.warning("[JustBill API] Invalid RELOAD_EVERY=%s; using 0", configured_reload_every)
            configured_reload_every = 0

        self.fetch_live_every_request = _env_bool("JUSTBILL_FETCH_LIVE_EVERY_REQUEST", False)
        self.reload_every_seconds = 0 if self.fetch_live_every_request else configured_reload_every
        if self.reload_every_seconds == 0:
            LOG.info("[JustBill API] Catalog cache disabled; fetching live catalog on each load()")

        self.failure_count = 0
        self.failure_threshold = max(1, _env_int("JUSTBILL_FAILURE_THRESHOLD", 3))
        self.circuit_open_seconds = max(5, _env_int("JUSTBILL_CIRCUIT_OPEN_SECONDS", 45))
        self.circuit_open_until = 0

        self.production_mode = _env_bool("VOICE_AGENT_PRODUCTION", False)
        self.strict_catalog = _env_bool("JUSTBILL_STRICT_CATALOG", self.production_mode)
        self.max_degraded_seconds = max(30, _env_int("JUSTBILL_MAX_DEGRADED_SECONDS", 900))
        self.allow_production_fallback = _env_bool("JUSTBILL_ALLOW_FALLBACK_IN_PRODUCTION", False)
        self.verify_tls = _env_bool("JUSTBILL_VERIFY_TLS", True)
        self.ca_bundle_path = os.getenv("JUSTBILL_CA_BUNDLE_PATH", "").strip()
        if self.ca_bundle_path and not os.path.isfile(self.ca_bundle_path):
            LOG.warning("[JustBill API] Ignoring invalid JUSTBILL_CA_BUNDLE_PATH: %s", self.ca_bundle_path)
            self.ca_bundle_path = ""

        if self.production_mode and not self.verify_tls:
            raise RuntimeError("JUSTBILL_VERIFY_TLS must be true in production mode")
        if not self.verify_tls:
            LOG.warning("[JustBill API] TLS verification disabled via JUSTBILL_VERIFY_TLS")

        # Configure session with retry logic
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods={"GET", "POST"},
            respect_retry_after_header=True,
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _can_use_fallback(self):
        if not self.production_mode:
            return True
        return self.allow_production_fallback

    def _verify_setting(self):
        if not self.verify_tls:
            return False
        if self.ca_bundle_path:
            return self.ca_bundle_path
        return True

    def _mark_failure(self, now, reason):
        self.last_error = str(reason)
        self.last_error_at = now
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self.circuit_open_until = now + self.circuit_open_seconds
            LOG.error(
                "[JustBill API] Circuit opened for %ss after %s failures (%s)",
                self.circuit_open_seconds,
                self.failure_count,
                reason,
            )
        else:
            LOG.warning("[JustBill API] Failure %s/%s: %s", self.failure_count, self.failure_threshold, reason)

    def _mark_success(self):
        self.failure_count = 0
        self.circuit_open_until = 0
        self.last_error = ""
        self.last_error_at = 0

    def get_health(self):
        now = time.time()
        live_age = None
        if self.last_live_success_at:
            live_age = int(max(0, now - self.last_live_success_at))

        degraded_reason = ""
        is_degraded = False
        using_cached_or_fallback = self.last_source in {"cache", "fallback", "live+fallback"}
        if self.last_source != "live" and not (using_cached_or_fallback and self.items):
            is_degraded = True
            degraded_reason = self.last_error or f"serving {self.last_source} catalog"

        if self.last_live_success_at and live_age is not None and live_age > self.max_degraded_seconds:
            is_degraded = True
            if not degraded_reason:
                degraded_reason = "live catalog stale"

        catalog_ready = True
        if self.strict_catalog:
            # Strict mode requires recent live catalog data.
            catalog_ready = bool(self.last_live_success_at) and bool(self.items)
            if live_age is not None:
                catalog_ready = catalog_ready and live_age <= self.max_degraded_seconds

        return {
            "source": self.last_source,
            "items": len(self.items),
            "strict_catalog": self.strict_catalog,
            "fallback_allowed": self._can_use_fallback(),
            "reload_every_seconds": self.reload_every_seconds,
            "fetch_live_every_request": bool(self.fetch_live_every_request),
            "catalog_ready": bool(catalog_ready),
            "is_degraded": bool(is_degraded),
            "degraded_reason": degraded_reason,
            "last_live_success_age_seconds": live_age,
            "last_error": self.last_error,
            "circuit_open": bool(self.circuit_open_until and now < self.circuit_open_until),
            "circuit_open_remaining_seconds": int(max(0, self.circuit_open_until - now)),
        }

    def _fallback_items(self):
        fallback = []
        for item in getattr(self.config, "FALLBACK_ITEMS", []):
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            category = str(item.get("category") or "").strip()
            attributes = item.get("attributes") if isinstance(item.get("attributes"), dict) else {}
            keywords = list(item.get("keywords") or self._generate_keywords(name))
            if category:
                keywords.extend(self._generate_keywords(category))
            for attr_value in attributes.values():
                keywords.extend(self._generate_keywords(str(attr_value)))
            fallback.append({
                "id": item.get("id"),
                "name": name,
                "price": _safe_float(item.get("price", 0)),
                "image": item.get("image"),
                "category": category,
                "attributes": attributes,
                "keywords": sorted({kw for kw in keywords if str(kw).strip()}),
            })
        return fallback

    def _normalize_product(self, raw_product):
        name = str(raw_product.get("productName") or "").strip()
        if not name:
            return None

        product_id = raw_product.get("productID")
        if product_id is None:
            return None

        category = str(
            raw_product.get("categoryName")
            or raw_product.get("productCategory")
            or raw_product.get("category")
            or ""
        ).strip()

        attribute_keys = (
            "metal",
            "metalType",
            "purity",
            "occasion",
            "gender",
            "collection",
            "style",
            "brand",
            "productType",
            "stone",
        )
        attributes = {}
        for key in attribute_keys:
            value = raw_product.get(key)
            cleaned = str(value).strip() if value is not None else ""
            if cleaned:
                attributes[key] = cleaned

        keywords = self._generate_keywords(name)
        if category:
            keywords.extend(self._generate_keywords(category))
        for attr_value in attributes.values():
            keywords.extend(self._generate_keywords(attr_value))

        return {
            "id": product_id,
            "name": name,
            "price": _safe_float(raw_product.get("sellingPrice") or raw_product.get("costPrice") or 0),
            "image": raw_product.get("primaryImageUrl"),
            "category": category,
            "attributes": attributes,
            "keywords": sorted({kw for kw in keywords if str(kw).strip()}),
        }

    def load(self):
        now = time.time()

        if self.reload_every_seconds > 0 and self.items and (now - self.last_loaded) < self.reload_every_seconds:
            if self.last_source == "empty":
                self.last_source = "cache"
            return self.items

        if self.circuit_open_until and now < self.circuit_open_until:
            if self.items:
                LOG.warning("[JustBill API] Circuit open - using cached/fallback data (%s items)", len(self.items))
                self.last_source = "cache"
                self.last_loaded = now
                return self.items
            if self._can_use_fallback():
                self.items = self._fallback_items()
                self.last_source = "fallback"
                self.last_loaded = now
                return self.items
            LOG.error("[JustBill API] Circuit open and fallback disabled; catalog unavailable")
            self.items = []
            self.last_source = "empty"
            self.last_loaded = now
            return self.items

        try:
            response = self.session.post(
                f"{self.config.API_BASE_URL}/api/Product/get_ProductList",
                json={
                    "messageInfo": {"returnValue": 0, "returnMessage": ""},
                    "userDBConnStr": ""
                },
                timeout=self.api_timeout_seconds,
                verify=self._verify_setting(),
            )
            response.raise_for_status()
            data = response.json() if response.content else {}
            if not isinstance(data, dict):
                data = {}
            products = data.get("ml_product", [])
            if not isinstance(products, list):
                products = []

            live_items = []
            for product in products:
                if not isinstance(product, dict):
                    continue
                if product.get("isActive") is False:
                    continue
                normalized = self._normalize_product(product)
                if normalized:
                    live_items.append(normalized)

            if live_items:
                self.items = live_items + self._fallback_items()
                self.last_loaded = now
                self.last_live_success_at = now
                self.last_source = "live+fallback"
                self._mark_success()
                LOG.info("[JustBill API] Loaded %s live products + fallback items", len(live_items))
                return self.items

            LOG.warning("[JustBill API] API returned no usable products; using fallback/cached data")
            self._mark_failure(now, "no usable products in response")
            if self.items:
                self.last_source = "cache"
                self.last_loaded = now
                return self.items

            if self._can_use_fallback():
                self.items = self._fallback_items()
                self.last_source = "fallback"
            else:
                self.items = []
                self.last_source = "empty"
                LOG.error("[JustBill API] No usable live products and fallback disabled")
            self.last_loaded = now
            return self.items

        except requests.exceptions.Timeout as exc:
            self._mark_failure(now, f"timeout: {exc}")
            if not self.items:
                if self._can_use_fallback():
                    self.items = self._fallback_items()
                    self.last_source = "fallback"
                    LOG.warning("[JustBill API] Timeout - using fallback data (%s items)", len(self.items))
                else:
                    self.items = []
                    self.last_source = "empty"
                    LOG.error("[JustBill API] Timeout and fallback disabled; catalog unavailable")
            else:
                self.last_source = "cache"
                LOG.warning("[JustBill API] Timeout - using cached data (%s items)", len(self.items))
            self.last_loaded = now
            return self.items
        except requests.exceptions.ConnectionError as exc:
            self._mark_failure(now, f"connection error: {exc}")
            if not self.items:
                if self._can_use_fallback():
                    self.items = self._fallback_items()
                    self.last_source = "fallback"
                    LOG.warning("[JustBill API] Connection failed - using fallback data (%s items)", len(self.items))
                else:
                    self.items = []
                    self.last_source = "empty"
                    LOG.error("[JustBill API] Connection failed and fallback disabled; catalog unavailable")
            else:
                self.last_source = "cache"
                LOG.warning("[JustBill API] Connection failed - using cached data (%s items)", len(self.items))
            self.last_loaded = now
            return self.items
        except Exception as e:
            self._mark_failure(now, f"unexpected error: {e}")
            if not self.items:
                if self._can_use_fallback():
                    self.items = self._fallback_items()
                    self.last_source = "fallback"
                    LOG.warning("[JustBill API] Error: %s - using fallback data (%s items)", e, len(self.items))
                else:
                    self.items = []
                    self.last_source = "empty"
                    LOG.error("[JustBill API] Error: %s - fallback disabled; catalog unavailable", e)
            else:
                self.last_source = "cache"
                LOG.warning("[JustBill API] Error: %s - using cached data", e)
            self.last_loaded = now
            return self.items

    def _generate_keywords(self, name):
        """Generate search keywords from product name — includes word fragments."""
        words = name.lower().split()
        keywords = list(words)
        # Add singular/plural variations
        for w in words:
            if w.endswith("s") and len(w) > 3:
                keywords.append(w[:-1])  # "rings" → "ring"
            elif not w.endswith("s"):
                keywords.append(w + "s")  # "ring" → "rings"
        return keywords