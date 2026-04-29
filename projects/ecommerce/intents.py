"""
projects/ecommerce/intents.py — Ecommerce store training data + intent handler.
"""

WELCOME_HINT  = "Say 'show products', 'add headphones', or 'checkout'."
GREET_HINT    = "Browse and buy electronics, clothing, accessories and more!"
FALLBACK_HINT = "Try: add product, show cart, checkout, search, filter by price."
HELP_TEXT = ("I can: add/remove products, view cart, checkout, search products, "
             "check prices, filter by category or price, show order history.")

TRAINING_DATA = [
    # ADD_TO_CART
    ("add headphones","ADD_TO_CART"), ("add to cart","ADD_TO_CART"),
    ("buy shoes","ADD_TO_CART"), ("i want to buy laptop bag","ADD_TO_CART"),
    ("add 2 phone cases","ADD_TO_CART"), ("purchase smart watch","ADD_TO_CART"),
    ("get me a speaker","ADD_TO_CART"), ("order usb cable","ADD_TO_CART"),
    ("put headphones in cart","ADD_TO_CART"), ("one more of that","ADD_TO_CART"),
    # REMOVE_ITEM
    ("remove headphones","REMOVE_ITEM"), ("delete shoes from cart","REMOVE_ITEM"),
    ("i don't want the speaker","REMOVE_ITEM"), ("cancel headphones","REMOVE_ITEM"),
    ("take out the laptop bag","REMOVE_ITEM"),
    # SHOW_CART
    ("show cart","SHOW_CART"), ("my cart","SHOW_CART"),
    ("what's in my cart","SHOW_CART"), ("view cart","SHOW_CART"),
    ("open cart","SHOW_CART"), ("check cart","SHOW_CART"),
    # CLEAR_CART
    ("clear cart","CLEAR_CART"), ("empty cart","CLEAR_CART"),
    ("remove all items","CLEAR_CART"), ("reset cart","CLEAR_CART"),
    # CHECKOUT
    ("checkout","CHECKOUT"), ("place order","CHECKOUT"),
    ("pay now","CHECKOUT"), ("complete purchase","CHECKOUT"),
    ("proceed to payment","CHECKOUT"), ("pay with card","CHECKOUT"),
    ("confirm order","CHECKOUT"), ("buy now","CHECKOUT"),
    # SHOW_PRODUCTS
    ("show products","SHOW_PRODUCTS"), ("list products","SHOW_PRODUCTS"),
    ("what do you sell","SHOW_PRODUCTS"), ("show all items","SHOW_PRODUCTS"),
    ("browse products","SHOW_PRODUCTS"), ("show catalog","SHOW_PRODUCTS"),
    # SEARCH
    ("search headphones","SEARCH"), ("find shoes","SEARCH"),
    ("do you have a laptop bag","SEARCH"), ("is smart watch available","SEARCH"),
    ("look for cable","SEARCH"),
    # PRICE
    ("price of headphones","PRICE"), ("how much are the shoes","PRICE"),
    ("cost of smart watch","PRICE"), ("what does laptop bag cost","PRICE"),
    # SHOW_ORDERS
    ("my orders","SHOW_ORDERS"), ("order history","SHOW_ORDERS"),
    ("track my order","SHOW_ORDERS"), ("show past orders","SHOW_ORDERS"),
    # FILTER
    ("show items under 1000","FILTER"), ("filter by price","FILTER"),
    ("cheap products","FILTER"), ("electronics only","FILTER"),
    ("show clothing","FILTER"),
    # RECOMMEND
    ("what do you recommend","RECOMMEND"), ("popular products","RECOMMEND"),
    ("best sellers","RECOMMEND"), ("trending items","RECOMMEND"),
    # UNIVERSAL
    ("hello","GREET"), ("hi","GREET"), ("hey","GREET"),
    ("help","HELP"), ("what can you do","HELP"), ("commands","HELP"),
    ("thanks","THANKS"), ("thank you","THANKS"),
    ("bye","BYE"), ("goodbye","BYE"), ("exit","BYE"),
    ("dark mode","THEME_DARK"), ("light mode","THEME_LIGHT"),
    ("go to home","NAVIGATE"), ("go to login","NAVIGATE"),
    ("my account","NAVIGATE"), ("go to orders","NAVIGATE"),
]

def handle_intent(intent, text, matcher, ctx, make_json, extract_quantity):
    t = text.lower()

    if intent == "ADD_TO_CART":
        item = ctx.resolve_item(text, matcher)
        qty  = extract_quantity(text)
        if item:
            ctx.update(intent, item, qty)
            ctx.add_to_cart(item, qty)
            msg = f"Added {qty}x {item['name']} to cart! Rs.{item['price']*qty:.0f}"
            return {"intent": intent, "message": msg,
                    "json": make_json(msg, "add_to_cart", {"productId": item["id"], "quantity": qty})}
        return {"intent": intent, "message": "Which product? Try: add headphones, add shoes", "json": "{}"}

    if intent == "REMOVE_ITEM":
        item = ctx.resolve_item(text, matcher)
        if item:
            ctx.remove_from_cart(item)
            ctx.update(intent, item)
            msg = f"Removed {item['name']} from cart."
            return {"intent": intent, "message": msg,
                    "json": make_json(msg, "remove_from_cart", {"productId": item["id"]})}
        return {"intent": intent, "message": "Which product to remove?", "json": "{}"}

    if intent == "SHOW_CART":
        ctx.update(intent)
        summary = ctx.get_cart_summary()
        return {"intent": intent, "message": summary, "json": make_json(summary, "open_cart")}

    if intent == "CLEAR_CART":
        ctx.clear_cart(); ctx.update(intent)
        return {"intent": intent, "message": "Cart cleared!",
                "json": make_json("Cart cleared!", "clear_cart")}

    if intent == "CHECKOUT":
        method = "card" if any(w in t for w in ["card","upi","online"]) else "cod"
        ctx.clear_cart(); ctx.update(intent)
        msg = f"Order placed! Payment: {method.upper()}"
        return {"intent": intent, "message": msg,
                "json": make_json(msg, "checkout", {"paymentMethod": method})}

    if intent == "SHOW_PRODUCTS":
        items = matcher.db.load()
        listing = "\n".join(f"  {i['name']} — Rs.{i['price']:.0f}" for i in items)
        ctx.update(intent)
        return {"intent": intent, "message": f"Products:\n{listing}",
                "json": make_json("Showing products", "show_products")}

    if intent == "SEARCH":
        item  = matcher.find(text)
        query = item["name"] if item else text
        ctx.update(intent, item)
        return {"intent": intent, "message": f"Searching: {query}",
                "json": make_json(f"Searching {query}", "search", {"query": query})}

    if intent == "PRICE":
        item = ctx.resolve_item(text, matcher)
        if item:
            ctx.update(intent, item)
            msg = f"{item['name']} costs Rs.{item['price']:.0f}"
            return {"intent": intent, "message": msg, "json": make_json(msg)}
        return {"intent": intent, "message": "Which product?", "json": "{}"}

    if intent == "SHOW_ORDERS":
        ctx.update(intent)
        return {"intent": intent, "message": "Showing your order history.",
                "json": make_json("Showing orders", "show_orders")}

    if intent == "FILTER":
        import re
        params = {}
        nums = re.findall(r'\d+', text)
        if nums: params["maxPrice"] = int(nums[0])
        for cat in ["electronics","clothing","accessories","shoes","bags"]:
            if cat in t: params["category"] = cat
        return {"intent": intent, "message": "Filtering products...",
                "json": make_json("Filtering", "filter", params)}

    if intent == "RECOMMEND":
        return {"intent": intent, "message": "Top picks: Wireless Headphones, Smart Watch!",
                "json": make_json("Showing recommendations", "show_recommendations")}

    return None
