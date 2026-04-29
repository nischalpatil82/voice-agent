"""
core/context.py — Session-Based Conversation Memory
Enterprise-grade: isolated per-user sessions with TTL expiration.
Handles multi-turn dialogue for all project types.
"""

import time
import threading
import uuid
import logging
import re


LOG = logging.getLogger(__name__)
_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


class ConversationContext:
    """Single user's conversation context."""

    def __init__(self):
        self.last_intent   = None
        self.last_item     = None
        self.last_quantity = 1
        self.last_frontend_context = {}
        self.cart          = []       # used by CraveHub + Ecommerce
        self.booking       = {}       # used by Hospital + Hotel
        self.history       = []       # last N interactions for smart responses
        self.dialogue_state = "IDLE"  # IDLE, BROWSING, SELECTING, CONFIRMING
        self.search_results = []       # Last search results for positional refs
        self.pending_action = None     # For confirmation flows
        self.slot_filling = {}         # For multi-slot commands
        self.created_at    = time.time()
        self.last_active   = time.time()

    def set_frontend_context(self, frontend_context):
        if isinstance(frontend_context, dict):
            self.last_frontend_context = frontend_context
            self.sync_cart_from_snapshot(frontend_context.get("cart_snapshot"))
        else:
            self.last_frontend_context = {}

    def sync_cart_from_snapshot(self, cart_snapshot):
        """Mirror frontend cart state so assistant summaries stay consistent with UI."""
        if not isinstance(cart_snapshot, list):
            return

        synced_cart = []
        for raw_item in cart_snapshot[:50]:
            if not isinstance(raw_item, dict):
                continue

            item_id = raw_item.get("product_id") or raw_item.get("id")
            name = str(raw_item.get("name") or "").strip()
            if item_id is None or not name:
                continue

            try:
                qty = int(raw_item.get("quantity", 1))
            except (TypeError, ValueError):
                qty = 1
            qty = max(1, qty)

            try:
                price = float(raw_item.get("price", 0) or 0)
            except (TypeError, ValueError):
                price = 0.0

            synced_cart.append(
                {
                    "id": item_id,
                    "name": name,
                    "price": price,
                    "quantity": qty,
                }
            )

        if synced_cart or cart_snapshot == []:
            self.cart = synced_cart

    def touch(self):
        """Mark session as active."""
        self.last_active = time.time()

    def update(self, intent, item=None, qty=1):
        self.last_intent   = intent
        if item:
            self.last_item = item
        self.last_quantity = qty
        self.touch()

        # Keep last 20 interactions for context
        self.history.append({
            "intent": intent,
            "item": item["name"] if item else None,
            "qty": qty,
            "time": time.time(),
        })
        if len(self.history) > 20:
            self.history = self.history[-20:]

    def resolve_positional_reference(self, text):
        """Handle 'the first one', 'the second one', 'that one'"""
        ordinals = {"first": 0, "second": 1, "third": 2, "last": -1}
        lowered = text.lower().split()
        for word, idx in ordinals.items():
            if word in lowered:
                if self.search_results and len(self.search_results) > max(0, idx):
                    return self.search_results[idx]
        return None

    def resolve_item(self, text, matcher):
        """Find item from text, or fall back to last mentioned item."""
        # Try positional reference first
        pos_item = self.resolve_positional_reference(text)
        if pos_item:
            return pos_item
            
        request_context = self.last_frontend_context if isinstance(self.last_frontend_context, dict) else None
        item = matcher.find(text, request_context=request_context)
        if not item and self.last_item:
            refer_words = ["another", "more", "same", "it", "that", "those", "this", "again"]
            if any(w in text.lower().split() for w in refer_words):
                return self.last_item
        return item

    def get_last_action(self):
        """Get the most recent action for contextual responses."""
        if self.history:
            return self.history[-1]
        return None

    # ── Cart operations (CraveHub, Ecommerce, JustBill) ────────────────────
    def add_to_cart(self, item, qty):
        for c in self.cart:
            if c["id"] == item["id"]:
                c["quantity"] += qty
                return c["quantity"]  # Return new total
        self.cart.append({
            "id": item["id"], "name": item["name"],
            "price": item["price"], "quantity": qty
        })
        return qty

    def remove_from_cart(self, item):
        before = len(self.cart)
        self.cart = [c for c in self.cart if c["id"] != item["id"]]
        return before > len(self.cart)  # True if something was removed

    def get_cart_count(self):
        return sum(c["quantity"] for c in self.cart)

    def get_cart_total(self):
        return sum(c["price"] * c["quantity"] for c in self.cart)

    def get_cart_summary(self):
        if not self.cart:
            return "Your cart is empty."
        lines = [f"  {c['name']} x{c['quantity']} = Rs {c['price'] * c['quantity']:,.0f}" for c in self.cart]
        total = self.get_cart_total()
        count = self.get_cart_count()
        return "\n".join(lines) + f"\n\n  {count} items - Total: Rs {total:,.0f}"

    def clear_cart(self):
        count = len(self.cart)
        self.cart = []
        return count

    # ── Booking context (Hospital, Hotel) ──────────────────────────────────
    def set_booking(self, key, value):
        self.booking[key] = value

    def get_booking_summary(self):
        if not self.booking:
            return "No booking in progress."
        return "  " + ", ".join(f"{k}: {v}" for k, v in self.booking.items())

    def clear_booking(self):
        self.booking = {}

    # ── Universal summary ──────────────────────────────────────────────────
    def get_context_summary(self):
        parts = []
        if self.cart:
            parts.append(self.get_cart_summary())
        if self.booking:
            parts.append(self.get_booking_summary())
        if self.last_intent:
            parts.append(f"  Last intent: {self.last_intent}")
        return "\n".join(parts) if parts else "No active context."


class SessionManager:
    """
    Manages isolated conversation contexts per user session.
    Thread-safe with automatic TTL-based cleanup.
    """

    def __init__(self, session_ttl=1800, cleanup_interval=300):
        """
        Args:
            session_ttl: Seconds before inactive session expires (default 30 min)
            cleanup_interval: Seconds between cleanup sweeps (default 5 min)
        """
        self.sessions = {}
        self.session_ttl = session_ttl
        self._lock = threading.Lock()

        # Start background cleanup thread
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            args=(cleanup_interval,),
            daemon=True
        )
        self._cleanup_thread.start()

    def get_or_create(self, session_id=None):
        """Get existing session or create a new one."""
        provided_id = str(session_id or "").strip() or None
        if provided_id and not _SESSION_ID_RE.fullmatch(provided_id):
            LOG.warning("[Session] Ignoring invalid session id format")
            provided_id = None

        with self._lock:
            if provided_id and provided_id in self.sessions:
                ctx = self.sessions[provided_id]
                ctx.touch()
                return provided_id, ctx

            # Create new session
            new_id = provided_id or uuid.uuid4().hex
            ctx = ConversationContext()
            self.sessions[new_id] = ctx
            LOG.info("[Session] Created: %s (active: %s)", new_id, len(self.sessions))
            return new_id, ctx

    def get(self, session_id):
        """Get session by ID, or None if not found/expired."""
        with self._lock:
            ctx = self.sessions.get(session_id)
            if ctx:
                if time.time() - ctx.last_active > self.session_ttl:
                    del self.sessions[session_id]
                    return None
                ctx.touch()
            return ctx

    def delete(self, session_id):
        """Delete a session."""
        with self._lock:
            self.sessions.pop(session_id, None)

    def active_count(self):
        """Number of active sessions."""
        with self._lock:
            return len(self.sessions)

    def _cleanup_loop(self, interval):
        """Periodically remove expired sessions."""
        while True:
            time.sleep(interval)
            self._cleanup()

    def _cleanup(self):
        """Remove expired sessions."""
        now = time.time()
        with self._lock:
            expired = [
                sid for sid, ctx in self.sessions.items()
                if now - ctx.last_active > self.session_ttl
            ]
            for sid in expired:
                del self.sessions[sid]
            if expired:
                LOG.info(
                    "[Session] Cleaned up %s expired sessions (active: %s)",
                    len(expired),
                    len(self.sessions),
                )
