"""
projects/cravehub/intents.py — CraveHub training data + intent handler.
Intents: ADD_TO_CART, REMOVE_ITEM, SHOW_CART, CLEAR_CART, CHECKOUT,
         SHOW_MENU, SEARCH, PRICE, SHOW_ORDERS, FILTER, RECOMMEND,
         COMPLAINT, GREET, HELP, THANKS, BYE, THEME_DARK, THEME_LIGHT, NAVIGATE
"""

WELCOME_HINT = "Say 'show menu', 'add pizza', or 'checkout'."
GREET_HINT   = "We have delicious food ready to order!"
FALLBACK_HINT = "Try: add pizza, show cart, checkout, show menu, help."
HELP_TEXT = ("I can: add/remove items, show cart, checkout, search items, "
             "check prices, filter by category, get recommendations, "
             "show orders, dark/light mode, navigate pages.")

TRAINING_DATA = [
    # ADD_TO_CART
    ("add pizza","ADD_TO_CART"), ("add 2 pizza","ADD_TO_CART"),
    ("add burger to cart","ADD_TO_CART"), ("i want pizza","ADD_TO_CART"),
    ("order pizza","ADD_TO_CART"), ("give me pizza","ADD_TO_CART"),
    ("get me a burger","ADD_TO_CART"), ("can i get pizza","ADD_TO_CART"),
    ("one pizza please","ADD_TO_CART"), ("two burgers please","ADD_TO_CART"),
    ("put pizza in cart","ADD_TO_CART"), ("i would like cake","ADD_TO_CART"),
    ("add another one","ADD_TO_CART"), ("add one more","ADD_TO_CART"),
    ("same again","ADD_TO_CART"), ("add 3 of those","ADD_TO_CART"),
    # REMOVE_ITEM
    ("remove pizza","REMOVE_ITEM"), ("delete burger","REMOVE_ITEM"),
    ("take out pizza","REMOVE_ITEM"), ("i don't want pizza","REMOVE_ITEM"),
    ("cancel pizza","REMOVE_ITEM"), ("drop the burger","REMOVE_ITEM"),
    # SHOW_CART
    ("show cart","SHOW_CART"), ("view cart","SHOW_CART"),
    ("my cart","SHOW_CART"), ("what is in my cart","SHOW_CART"),
    ("open cart","SHOW_CART"), ("check cart","SHOW_CART"),
    ("what have i ordered","SHOW_CART"),
    # CLEAR_CART
    ("clear cart","CLEAR_CART"), ("empty cart","CLEAR_CART"),
    ("remove everything","CLEAR_CART"), ("start over","CLEAR_CART"),
    ("reset cart","CLEAR_CART"), ("delete all","CLEAR_CART"),
    # CHECKOUT
    ("checkout","CHECKOUT"), ("place order","CHECKOUT"),
    ("pay now","CHECKOUT"), ("confirm order","CHECKOUT"),
    ("i want to pay","CHECKOUT"), ("proceed to checkout","CHECKOUT"),
    ("pay with cash","CHECKOUT"), ("cash on delivery","CHECKOUT"),
    ("pay with card","CHECKOUT"), ("complete my order","CHECKOUT"),
    # SHOW_MENU
    ("show menu","SHOW_MENU"), ("what do you have","SHOW_MENU"),
    ("list items","SHOW_MENU"), ("what food","SHOW_MENU"),
    ("menu please","SHOW_MENU"), ("what can i order","SHOW_MENU"),
    # SEARCH
    ("search pizza","SEARCH"), ("find burger","SEARCH"),
    ("look for tacos","SEARCH"), ("do you have pizza","SEARCH"),
    ("is pizza available","SEARCH"),
    # PRICE
    ("price of pizza","PRICE"), ("how much is burger","PRICE"),
    ("cost of tacos","PRICE"), ("what does pizza cost","PRICE"),
    ("how much does it cost","PRICE"),
    # SHOW_ORDERS
    ("show orders","SHOW_ORDERS"), ("my orders","SHOW_ORDERS"),
    ("order history","SHOW_ORDERS"), ("track my order","SHOW_ORDERS"),
    # FILTER
    ("show vegetarian items","FILTER"), ("filter by price","FILTER"),
    ("show cheap items","FILTER"), ("show items under 200","FILTER"),
    ("show desserts","FILTER"), ("show burgers only","FILTER"),
    # RECOMMEND
    ("what do you recommend","RECOMMEND"), ("suggest something","RECOMMEND"),
    ("what is popular","RECOMMEND"), ("best seller","RECOMMEND"),
    # COMPLAINT
    ("my order is wrong","COMPLAINT"), ("i got the wrong item","COMPLAINT"),
    ("i have a complaint","COMPLAINT"), ("the food is cold","COMPLAINT"),
    # UNIVERSAL
    ("hello","GREET"), ("hi","GREET"), ("hey","GREET"),
    ("good morning","GREET"), ("good evening","GREET"),
    ("help","HELP"), ("what can you do","HELP"),
    ("commands","HELP"), ("how do i order","HELP"),
    ("thanks","THANKS"), ("thank you","THANKS"),
    ("bye","BYE"), ("goodbye","BYE"), ("exit","BYE"),
    ("dark mode","THEME_DARK"), ("switch to dark","THEME_DARK"),
    ("night mode","THEME_DARK"),
    ("light mode","THEME_LIGHT"), ("switch to light","THEME_LIGHT"),
    ("go to home","NAVIGATE"), ("go to login","NAVIGATE"),("light mode","THEME_LIGHT"), ("switch to light","THEME_LIGHT"),
    ("change to light mode","THEME_LIGHT"), ("day mode","THEME_LIGHT"),
    ("white mode","THEME_LIGHT"), ("change to white mode","THEME_LIGHT"),
    ("switch to white","THEME_LIGHT"), ("bright mode","THEME_LIGHT"),
    ("turn on light mode","THEME_LIGHT"), ("normal mode","THEME_LIGHT"),
    ("go to orders","NAVIGATE"), ("open admin","NAVIGATE"),
]

def handle_intent(intent, text, matcher, ctx, make_json, extract_quantity):
    t = text.lower()

    if intent == "ADD_TO_CART":
        item = ctx.resolve_item(text, matcher)
        qty  = extract_quantity(text)
        if item:
            ctx.update(intent, item, qty)
            ctx.add_to_cart(item, qty)
            msg = f"Added {qty}x {item['name']}! Rs.{item['price']*qty:.0f}"
            return {"intent": intent, "message": msg,
                    "json": make_json(msg, "add_to_cart", {"menuId": item["id"], "quantity": qty})}
        return {"intent": intent, "message": "Which item? Try: add pizza, add burger", "json": "{}"}

    if intent == "REMOVE_ITEM":
        item = ctx.resolve_item(text, matcher)
        if item:
            ctx.remove_from_cart(item)
            ctx.update(intent, item)
            msg = f"Removed {item['name']} from cart."
            return {"intent": intent, "message": msg,
                    "json": make_json(msg, "remove_from_cart", {"menuId": item["id"]})}
        return {"intent": intent, "message": "Which item to remove?", "json": "{}"}

    if intent == "SHOW_CART":
        ctx.update(intent)
        summary = ctx.get_cart_summary()
        return {"intent": intent, "message": summary,
                "json": make_json(summary, "open_cart")}

    if intent == "CLEAR_CART":
        ctx.clear_cart(); ctx.update(intent)
        return {"intent": intent, "message": "Cart cleared!",
                "json": make_json("Cart cleared!", "clear_cart")}

    if intent == "CHECKOUT":
        method = "card" if any(w in t for w in ["card","online","upi"]) else "cod"
        ctx.clear_cart(); ctx.update(intent)
        msg = f"Order placed! Payment: {method.upper()}"
        return {"intent": intent, "message": msg,
                "json": make_json(msg, "checkout", {"paymentMethod": method})}

    if intent == "SHOW_MENU":
        items    = matcher.db.load()
        menu_str = "\n".join(f"  {i['name']} — Rs.{i['price']:.0f}" for i in items)
        ctx.update(intent)
        return {"intent": intent, "message": f"Menu:\n{menu_str}",
                "json": make_json("Showing menu", "show_menu")}

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
        return {"intent": intent, "message": "Which item?", "json": "{}"}

    if intent == "SHOW_ORDERS":
        ctx.update(intent)
        return {"intent": intent, "message": "Showing your orders.",
                "json": make_json("Showing orders", "show_orders")}

    if intent == "FILTER":
        import re
        params = {}
        nums = re.findall(r'\d+', text)
        if nums: params["maxPrice"] = int(nums[0])
        for cat in ["vegetarian","dessert","burger","pizza","tacos"]:
            if cat in t: params["category"] = cat
        return {"intent": intent, "message": "Filtering items...",
                "json": make_json("Filtering", "filter", params)}

    if intent == "RECOMMEND":
        return {"intent": intent, "message": "Most popular: Margherita Pizza, Classic Burger!",
                "json": make_json("Showing recommendations", "show_recommendations")}

    if intent == "COMPLAINT":
        return {"intent": intent, "message": "Sorry about that! Connecting you to support.",
                "json": make_json("Opening support", "open_support")}

    return None  # let core handle GREET, HELP, BYE, NAVIGATE etc.
