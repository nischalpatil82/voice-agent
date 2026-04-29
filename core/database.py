"""
core/database.py — Generic DB loader driven by project config schema.
Works for any project: food menus, products, doctors, rooms.
"""
import logging
import re
import time


LOG = logging.getLogger(__name__)
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _safe_identifier(value, label):
    cleaned = str(value or "").strip()
    if not _IDENTIFIER_RE.fullmatch(cleaned):
        raise ValueError(f"Invalid SQL identifier for {label}: {value!r}")
    return f"`{cleaned}`"


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

    def _fallback_items(self):
        fallback = []
        for raw_item in getattr(self.config, "FALLBACK_ITEMS", []):
            name = str(raw_item.get("name", "")).strip()
            if not name:
                continue
            fallback.append({
                "id": raw_item.get("id"),
                "name": name,
                "price": _safe_float(raw_item.get("price")),
                "keywords": list(raw_item.get("keywords") or name.lower().split()),
            })
        return fallback

    def load(self):
        now = time.time()
        if self.items and (now - self.last_loaded) < self.config.RELOAD_EVERY:
            return self.items

        conn = None
        cursor = None
        try:
            import mysql.connector
            conn   = mysql.connector.connect(**self.config.DB_CONFIG)
            cursor = conn.cursor(dictionary=True)
            tc     = self.config.TABLE_CONFIG

            id_col = _safe_identifier(tc["id_col"], "id_col")
            name_col = _safe_identifier(tc["name_col"], "name_col")
            price_col = _safe_identifier(tc["price_col"], "price_col")
            table_name = _safe_identifier(tc["table"], "table")

            select_cols = f"{id_col} AS id, {name_col} AS name, {price_col} AS price"
            query = f"SELECT {select_cols} FROM {table_name}"

            conditions = []
            if tc.get("active_col"):
                active_col = _safe_identifier(tc["active_col"], "active_col")
                conditions.append(f"{active_col} = 1")
            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            cursor.execute(query)
            rows = cursor.fetchall() or []

            self.items = [
                {
                    "id":       r["id"],
                    "name":     str(r["name"]),
                    "price":    _safe_float(r.get("price")),
                    "keywords": str(r["name"]).lower().split()
                }
                for r in rows
            ]
            self.last_loaded = now
            LOG.info("[DB] Loaded %s items from MySQL (%s)", len(self.items), self.config.PROJECT_NAME)
            return self.items

        except Exception as exc:
            if self.items:
                self.last_loaded = now
                LOG.warning("[DB] MySQL unavailable (%s) - using cached data (%s items)", exc, len(self.items))
                return self.items

            self.items = self._fallback_items()
            self.last_loaded = now
            LOG.warning("[DB] MySQL unavailable (%s) - using fallback data (%s items)", exc, len(self.items))
            return self.items

        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
