import json

from core.context import ConversationContext
from core.actions import extract_quantity, make_json
from projects.justbill.intents import handle_intent


class _DummyDB:
    def __init__(self, items):
        self._items = items

    def load(self):
        return list(self._items)


class _DummyMatcher:
    def __init__(self):
        self.items = [
            {"id": 101, "name": "Gold Chain", "price": 89999},
            {"id": 202, "name": "Traditional Anklet", "price": 34999},
        ]
        self.db = _DummyDB(self.items)

    def find(self, text, threshold=72, request_context=None):
        lowered = (text or "").lower()
        if "gold chain" in lowered:
            return self.items[0]
        if "traditional anklet" in lowered or "anklet" in lowered:
            return self.items[1]
        return None


class _LowConfidenceMatcher(_DummyMatcher):
    def find(self, text, threshold=72, request_context=None):
        item = super().find(text, threshold=threshold, request_context=request_context)
        if item is None:
            return None
        low = dict(item)
        low["_confidence"] = 0.41
        return low


class _ConfirmingBuilder:
    def __init__(self):
        self.calls = []

    def build(self, intent, text, matcher, ctx):
        self.calls.append((intent, text))
        if text == "need confirm":
            ctx.pending_action = {"intent": "ADD_TO_CART", "text": "add gold chain", "created_at": 0}
            return {"intent": "CLARIFY", "message": "Please confirm", "json": make_json("Please confirm", "clarify", {})}
        return {"intent": "ADD_TO_CART", "message": "Added Gold Chain", "json": make_json("Added Gold Chain", "add_to_cart", {"productId": 101, "quantity": 1, "name": "Gold Chain", "price": 89999})}


def test_add_to_cart_supports_multiple_items_in_one_command():
    matcher = _DummyMatcher()
    ctx = ConversationContext()

    result = handle_intent(
        "ADD_TO_CART",
        "add gold chain and traditional anklet to cart",
        matcher,
        ctx,
        make_json,
        extract_quantity,
    )

    assert result is not None
    assert result["intent"] == "ADD_TO_CART"
    assert "Gold Chain" in result["message"]
    assert "Traditional Anklet" in result["message"]

    payload = json.loads(result["json"])
    assert isinstance(payload.get("actions"), list)
    assert len(payload["actions"]) == 2
    assert ctx.get_cart_count() == 2


def test_add_to_cart_single_item_still_returns_single_action():
    matcher = _DummyMatcher()
    ctx = ConversationContext()

    result = handle_intent(
        "ADD_TO_CART",
        "add gold chain to cart",
        matcher,
        ctx,
        make_json,
        extract_quantity,
    )

    assert result is not None
    payload = json.loads(result["json"])
    assert len(payload.get("actions", [])) == 1
    assert ctx.get_cart_count() == 1


def test_add_to_cart_reports_unmatched_item_in_multi_command():
    matcher = _DummyMatcher()
    ctx = ConversationContext()

    result = handle_intent(
        "ADD_TO_CART",
        "add gold chain and moon brooch to cart",
        matcher,
        ctx,
        make_json,
        extract_quantity,
    )

    assert result is not None
    assert "Gold Chain" in result["message"]
    assert "Couldn't find:" in result["message"]
    assert "moon brooch" in result["message"]

    payload = json.loads(result["json"])
    assert len(payload.get("actions", [])) == 1
    assert ctx.get_cart_count() == 1


def test_filter_parses_lakh_amount_to_absolute_price():
    matcher = _DummyMatcher()
    ctx = ConversationContext()

    result = handle_intent(
        "FILTER",
        "show rings under 2 lakhs",
        matcher,
        ctx,
        make_json,
        extract_quantity,
    )

    payload = json.loads(result["json"])
    params = payload["actions"][0]["params"]
    assert params["maxPrice"] == 200000
    assert params["category"] == "rings"


def test_filter_parses_comma_price_amount():
    matcher = _DummyMatcher()
    ctx = ConversationContext()

    result = handle_intent(
        "FILTER",
        "filter price under 1,50,000",
        matcher,
        ctx,
        make_json,
        extract_quantity,
    )

    payload = json.loads(result["json"])
    params = payload["actions"][0]["params"]
    assert params["maxPrice"] == 150000


def test_navigate_prefers_specific_page_phrase():
    matcher = _DummyMatcher()
    ctx = ConversationContext()

    result = handle_intent(
        "NAVIGATE",
        "go to order tracking",
        matcher,
        ctx,
        make_json,
        extract_quantity,
    )

    payload = json.loads(result["json"])
    params = payload["actions"][0]["params"]
    assert params["url"] == "/order/tracking"


def test_show_category_emits_filter_action_not_category_navigation():
    matcher = _DummyMatcher()
    ctx = ConversationContext()

    result = handle_intent(
        "SHOW_CATEGORY",
        "show rings",
        matcher,
        ctx,
        make_json,
        extract_quantity,
    )

    payload = json.loads(result["json"])
    action = payload["actions"][0]
    assert action["type"] == "filter"
    assert action["params"]["category"] == "rings"


def test_show_orders_uses_account_order_route():
    matcher = _DummyMatcher()
    ctx = ConversationContext()

    result = handle_intent(
        "SHOW_ORDERS",
        "show my orders",
        matcher,
        ctx,
        make_json,
        extract_quantity,
    )

    payload = json.loads(result["json"])
    assert payload["actions"][0]["params"]["url"] == "/account/order"


def test_navigate_blog_uses_plural_route():
    matcher = _DummyMatcher()
    ctx = ConversationContext()

    result = handle_intent(
        "NAVIGATE",
        "open blog",
        matcher,
        ctx,
        make_json,
        extract_quantity,
    )

    payload = json.loads(result["json"])
    assert payload["actions"][0]["params"]["url"] == "/blogs"


def test_add_to_cart_low_confidence_requires_confirmation():
    matcher = _LowConfidenceMatcher()
    ctx = ConversationContext()
    ctx.last_intent_confidence = 0.43

    result = handle_intent(
        "ADD_TO_CART",
        "add gold chain",
        matcher,
        ctx,
        make_json,
        extract_quantity,
    )

    assert result["intent"] == "CLARIFY"
    assert "yes to confirm" in result["message"].lower()
    payload = json.loads(result["json"])
    assert payload["actions"][0]["type"] == "clarify"
    assert ctx.get_cart_count() == 0


def test_pending_confirmation_yes_executes_action():
    matcher = _DummyMatcher()
    builder = _ConfirmingBuilder()
    ctx = ConversationContext()
    result = builder.build("ADD_TO_CART", "need confirm", matcher, ctx)
    assert result["intent"] == "CLARIFY"

    from core.actions import ActionBuilder
    from projects.justbill import config as justbill_config
    from projects.justbill import intents as justbill_intents

    action_builder = ActionBuilder(justbill_config, justbill_intents)
    action_builder.intents = justbill_intents
    ctx.pending_action = {"intent": "ADD_TO_CART", "text": "add gold chain", "created_at": 0}
    confirmed = action_builder.build("GREET", "yes", matcher, ctx)

    assert confirmed["intent"] == "ADD_TO_CART"
    assert ctx.pending_action is None


def test_pending_confirmation_no_cancels_action():
    matcher = _DummyMatcher()
    ctx = ConversationContext()
    ctx.pending_action = {"intent": "ADD_TO_CART", "text": "add gold chain", "created_at": 0}

    from core.actions import ActionBuilder
    from projects.justbill import config as justbill_config
    from projects.justbill import intents as justbill_intents

    action_builder = ActionBuilder(justbill_config, justbill_intents)
    action_builder.intents = justbill_intents
    cancelled = action_builder.build("GREET", "no", matcher, ctx)

    assert cancelled["intent"] == "CANCELLED"
    assert ctx.pending_action is None
