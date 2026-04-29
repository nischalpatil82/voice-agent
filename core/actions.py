"""
core/actions.py — Enterprise Action Builder
Smart contextual responses, structured JSON output, background Spring Boot sync.
"""
import re
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor

from core.entity_extractor import extract_quantity

LOG = logging.getLogger(__name__)


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


_API_TIMEOUT_SECONDS = max(0.2, _env_float("VOICE_AGENT_OUTBOUND_TIMEOUT", 2.0))
_API_EXECUTOR = ThreadPoolExecutor(max_workers=max(1, _env_int("VOICE_AGENT_OUTBOUND_WORKERS", 4)))
_MAX_QUANTITY = max(1, _env_int("VOICE_AGENT_MAX_QUANTITY", 50))
_PENDING_CONFIRM_TTL_SECONDS = max(10, _env_int("VOICE_AGENT_PENDING_CONFIRM_TTL_SECONDS", 120))

_CONFIRM_YES = {
    "yes", "y", "yeah", "yep", "sure", "ok", "okay", "confirm", "do it", "please do",
}
_CONFIRM_NO = {
    "no", "n", "nope", "nah", "cancel", "stop", "dont", "don't",
}


# Removed extract_quantity, imported from core.entity_extractor


def make_json(message, action_type=None, params=None):
    actions = []
    if action_type:
        actions = [{"type": action_type, "params": params or {}}]
    return json.dumps({"message": message, "actions": actions})


def send_to_spring_boot(api_base_url, json_string):
    """Send voice command JSON to Spring Boot in background thread."""
    if not api_base_url:
        return

    def _send():
        try:
            import urllib.request
            data = json_string.encode("utf-8")
            req = urllib.request.Request(
                f"{api_base_url}/api/voice/action",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=_API_TIMEOUT_SECONDS) as resp:
                LOG.debug("[API] Sent to Spring Boot OK (%s)", resp.status)
        except Exception as exc:
            # Spring Boot sync is optional. We keep this non-fatal and low-noise.
            LOG.debug("[API] Spring Boot sync skipped: %s", exc)

    try:
        _API_EXECUTOR.submit(_send)
    except Exception as exc:
        LOG.debug("[API] Unable to enqueue outbound sync: %s", exc)


class ActionBuilder:
    def __init__(self, config, intents_module):
        self.config  = config
        self.intents = intents_module
        self.action_api_base_url = self._resolve_action_api_base_url(config)

    @staticmethod
    def _resolve_action_api_base_url(config):
        """Use dedicated action-sync base URL when provided, else keep legacy fallback."""
        if hasattr(config, "ACTION_API_BASE_URL"):
            return str(getattr(config, "ACTION_API_BASE_URL") or "").strip()
        return str(getattr(config, "API_BASE_URL", "") or "").strip()

    def _sanitize_message(self, text):
        """Convert common Unicode UI symbols to ASCII-safe wording."""
        msg = str(text or "")
        replacements = {
            "\u20b9": "Rs ",
            "\u2705": "OK ",
            "\U0001F6D2": "Cart ",
            "\u00b7": "-",
            "\u2764\ufe0f": "",
            "\U0001F48E": "",
            "\U0001F319": "",
            "\u2600\ufe0f": "",
            "\U0001F44B": "",
            "\U0001F60A": "",
            "\u2014": "-",
            "\u2013": "-",
            "\u2022": "-",
        }
        for old, new in replacements.items():
            msg = msg.replace(old, new)

        # Final guard for mojibake/emoji rendering issues in clients.
        msg = msg.encode("ascii", "ignore").decode("ascii")
        msg = re.sub(r"^[^A-Za-z0-9]+(?=[A-Za-z0-9])", "", msg)
        msg = re.sub(r"[ \t]{2,}", " ", msg)
        msg = msg.replace("Cart Cart:", "Cart:")
        return "\n".join(line.rstrip() for line in msg.splitlines()).strip()

    @staticmethod
    def _normalize_short_text(text):
        return " ".join(str(text or "").lower().split()).strip()

    def _is_confirm_yes(self, text):
        t = self._normalize_short_text(text)
        return t in _CONFIRM_YES

    def _is_confirm_no(self, text):
        t = self._normalize_short_text(text)
        return t in _CONFIRM_NO

    def _resolve_pending_confirmation(self, text, matcher, ctx):
        pending = getattr(ctx, "pending_action", None)
        if not isinstance(pending, dict):
            return None

        created_at = pending.get("created_at", 0)
        try:
            created_at = float(created_at)
        except (TypeError, ValueError):
            created_at = 0.0

        if created_at and (time.time() - created_at) > _PENDING_CONFIRM_TTL_SECONDS:
            ctx.pending_action = None
            msg = "That confirmation timed out. Please say the command again."
            return {"intent": "CANCELLED", "message": self._sanitize_message(msg), "json": make_json(msg)}

        if self._is_confirm_no(text):
            ctx.pending_action = None
            msg = "Okay, cancelled."
            return {"intent": "CANCELLED", "message": self._sanitize_message(msg), "json": make_json(msg)}

        if not self._is_confirm_yes(text):
            return None

        pending_intent = pending.get("intent")
        pending_text = pending.get("text")
        if not pending_intent or not pending_text:
            ctx.pending_action = None
            msg = "I could not continue that action. Please say it again."
            return {"intent": "CANCELLED", "message": self._sanitize_message(msg), "json": make_json(msg)}

        ctx.pending_action = None
        setattr(ctx, "pending_action_bypass", True)
        try:
            confirmed = self.intents.handle_intent(
                pending_intent,
                pending_text,
                matcher,
                ctx,
                make_json,
                extract_quantity,
            )
        finally:
            setattr(ctx, "pending_action_bypass", False)

        if confirmed:
            confirmed["message"] = self._sanitize_message(confirmed.get("message", ""))
            send_to_spring_boot(self.action_api_base_url, confirmed.get("json", "{}"))
            return confirmed

        msg = "I could not complete that action. Please try again."
        return {"intent": "ERROR", "message": self._sanitize_message(msg), "json": make_json(msg)}

    def build(self, intent, text, matcher, ctx):
        t = text.lower()

        if ctx is not None and getattr(ctx, "pending_action", None):
            pending_result = self._resolve_pending_confirmation(text, matcher, ctx)
            if pending_result is not None:
                return pending_result

        # ── Out of scope — rejected by classifier ──
        if intent == "OUT_OF_SCOPE":
            # Recover common conversational help requests that ML may score low.
            if (
                "help" in t
                or "show commands" in t
                or t.startswith("can i ")
                or t.startswith("can you ")
                or "ask something" in t
                or "say something" in t
            ):
                help_text = getattr(self.intents, "HELP_TEXT", "I can help you navigate and interact.")
                return {"intent": "HELP", "message": self._sanitize_message(help_text), "json": "{}"}

            # Recover service/shop navigation phrases from noisy transcripts.
            nav_words = ("go", "open", "navigate", "take me", "show")
            if any(k in t for k in ("service", "services", "shopping", "shop", "collections")):
                if any(w in t for w in nav_words) or len(t.split()) <= 3:
                    target = "/service" if ("service" in t or "services" in t) else "/collections"
                    msg = "Navigating..."
                    j = make_json(msg, "navigate", {"url": target})
                    return {"intent": "NAVIGATE", "message": self._sanitize_message(msg), "json": j}

            fallback = getattr(self.intents, "FALLBACK_HINT",
                              "I can help with shopping, cart, wishlist, search, and navigation. Try: 'show rings' or 'add to cart'.")
            return {"intent": intent, "message": self._sanitize_message(f"I'm not sure I understand that.\n\n{fallback}"), "json": "{}"}

        # ── Universal intents ────────────────────────────────────────────────
        if intent == "GREET":
            count = len(matcher.db.load())
            hint  = getattr(self.intents, "GREET_HINT", "How can I help you?")
            msg   = f"Hello! Welcome to {self.config.PROJECT_NAME}! {hint} ({count} items available)"
            result = {"intent": intent, "message": self._sanitize_message(msg), "json": "{}"}
            send_to_spring_boot(self.action_api_base_url, result["json"])
            return result

        if intent == "HELP":
            help_text = getattr(self.intents, "HELP_TEXT", "I can help you navigate and interact.")
            return {"intent": intent, "message": self._sanitize_message(help_text), "json": "{}"}

        if intent == "THANKS":
            # Contextual thanks
            last = ctx.get_last_action() if hasattr(ctx, 'get_last_action') else None
            if last and last.get("intent") == "ADD_TO_CART":
                msg = "You're welcome! Your cart is ready. Say 'checkout' when you're done shopping! 🛒"
            elif last and last.get("intent") == "SEARCH":
                msg = "Glad I could help! Let me know if you'd like to add anything to your cart."
            else:
                msg = "You're welcome! Anything else I can help with? 😊"
            return {"intent": intent, "message": self._sanitize_message(msg), "json": "{}"}

        if intent == "BYE":
            cart_count = ctx.get_cart_count() if hasattr(ctx, 'get_cart_count') else 0
            if cart_count > 0:
                total = ctx.get_cart_total()
                msg = f"You have {cart_count} items (₹{total:,.0f}) in your cart. Don't forget to checkout! 👋"
            else:
                msg = f"Goodbye! Thank you for visiting {self.config.PROJECT_NAME}! 💎"
            j = make_json(msg, "bye")
            send_to_spring_boot(self.action_api_base_url, j)
            return {"intent": intent, "message": self._sanitize_message(msg), "json": j}

        if intent == "THEME_DARK":
            j = make_json("Dark mode on", "set_theme", {"theme": "dark"})
            send_to_spring_boot(self.action_api_base_url, j)
            return {"intent": intent, "message": self._sanitize_message("🌙 Switching to dark mode!"), "json": j}

        if intent == "THEME_LIGHT":
            j = make_json("Light mode on", "set_theme", {"theme": "light"})
            send_to_spring_boot(self.action_api_base_url, j)
            return {"intent": intent, "message": self._sanitize_message("☀️ Switching to light mode!"), "json": j}

        # ── Project-specific intents ─────────────────────────────────────────
        result = self.intents.handle_intent(intent, text, matcher, ctx,
                                            make_json, extract_quantity)
        if result:
            result["message"] = self._sanitize_message(result.get("message", ""))
            if ctx is not None:
                if result.get("intent") == "CLARIFY":
                    ctx.pending_action = {
                        "intent": intent,
                        "text": text,
                        "created_at": time.time(),
                    }
                else:
                    ctx.pending_action = None
            # Send to Spring Boot automatically
            send_to_spring_boot(self.action_api_base_url, result["json"])
            return result

        fallback_hint = getattr(self.intents, "FALLBACK_HINT",
                                "Try: help, show menu, or describe what you need.")
        return {"intent": "UNKNOWN", "message": self._sanitize_message(fallback_hint), "json": "{}"}
