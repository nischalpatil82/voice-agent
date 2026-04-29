"""
projects/justbill/intents.py
Covers EVERY automation on JustBill:
cart, wishlist, search, filter, compare, navigate,
orders, offers, account, theme, product info

python server.py --project justbill


"""

import json
import os
import re


def _env_float(name, default):
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


ACTION_CONFIRM_THRESHOLD = _env_float("JUSTBILL_ACTION_CONFIRM_THRESHOLD", 0.48)

WELCOME_HINT  = "Say 'show rings', 'add diamond ring to cart', or 'checkout'."
GREET_HINT    = "I can automate everything on Veloria - cart, wishlist, search, orders and more!"
FALLBACK_HINT = (
    "I help with jewellery shopping! Try:\n"
    "- 'show rings' or 'search diamond necklace'\n"
    "- 'add gold chain to cart'\n"
    "- 'my orders' or 'go to checkout'\n"
    "- 'help' for all commands"
)
HELP_TEXT = (
    "I can automate everything:\n"
    "- CART: 'add diamond ring', 'remove gold chain', 'clear cart', 'show cart'\n"
    "- WISHLIST: 'add to wishlist', 'remove from wishlist', 'show wishlist'\n"
    "- SEARCH: 'search pearl necklace', 'find gold earrings'\n"
    "- CATEGORIES: 'show rings', 'open necklaces', 'browse earrings'\n"
    "- FILTER: 'show rings under 2 lakhs', 'filter gold jewellery'\n"
    "- ORDERS: 'my orders', 'track order', 'order history'\n"
    "- OFFERS: 'show offers', 'any deals today', 'sale items'\n"
    "- COMPARE: 'compare this ring', 'add to compare'\n"
    "- ACCOUNT: 'my account', 'go to profile', 'login', 'logout'\n"
    "- NAVIGATE: 'go home', 'open cart', 'go to checkout'\n"
    "- THEME: 'dark mode', 'light mode'"
)

TRAINING_DATA = [

    # ── ADD_TO_CART (20 examples) ──
    ("add to cart",                          "ADD_TO_CART"),
    ("add diamond ring to cart",             "ADD_TO_CART"),
    ("add gold chain to cart",               "ADD_TO_CART"),
    ("add pearl necklace to cart",           "ADD_TO_CART"),
    ("add 2 diamond rings to cart",          "ADD_TO_CART"),
    ("add 3 gold chains to cart",            "ADD_TO_CART"),
    ("buy this ring",                        "ADD_TO_CART"),
    ("buy this necklace",                    "ADD_TO_CART"),
    ("buy diamond ring",                     "ADD_TO_CART"),
    ("i want to buy earrings",               "ADD_TO_CART"),
    ("purchase the bangle",                  "ADD_TO_CART"),
    ("put this in cart",                     "ADD_TO_CART"),
    ("put diamond ring in cart",             "ADD_TO_CART"),
    ("order mangala sutra",                  "ADD_TO_CART"),
    ("order 2 bangles",                      "ADD_TO_CART"),
    ("get me the bracelet",                  "ADD_TO_CART"),
    ("one more of that",                     "ADD_TO_CART"),
    ("i want this anklet",                   "ADD_TO_CART"),
    ("put the pendant in cart",              "ADD_TO_CART"),
    ("order this jewellery",                 "ADD_TO_CART"),
    ("i want to buy the diamond necklace",   "ADD_TO_CART"),
    ("buy diamond necklace",                 "ADD_TO_CART"),
    ("i will purchase the ring",            "ADD_TO_CART"),
    ("give me the gold chain",              "ADD_TO_CART"),
    ("i'll take that necklace",             "ADD_TO_CART"),
    ("chuck the gold ring in cart",         "ADD_TO_CART"),
    ("put the bangle in my bag",            "ADD_TO_CART"),

    # ── ADD_TO_WISHLIST (20 examples) ──
    ("add to wishlist",                      "ADD_TO_WISHLIST"),
    ("add diamond ring to wishlist",         "ADD_TO_WISHLIST"),
    ("add gold chain to wishlist",           "ADD_TO_WISHLIST"),
    ("add pearl necklace to wishlist",       "ADD_TO_WISHLIST"),
    ("add 2 diamond rings to wishlist",      "ADD_TO_WISHLIST"),
    ("save for later",                       "ADD_TO_WISHLIST"),
    ("save this ring to wishlist",           "ADD_TO_WISHLIST"),
    ("save gold chain to wishlist",          "ADD_TO_WISHLIST"),
    ("save diamond ring to wishlist",        "ADD_TO_WISHLIST"),
    ("save this necklace",                   "ADD_TO_WISHLIST"),
    ("add to favourites",                    "ADD_TO_WISHLIST"),
    ("add ring to favourites",               "ADD_TO_WISHLIST"),
    ("save this product",                    "ADD_TO_WISHLIST"),
    ("wishlist this",                        "ADD_TO_WISHLIST"),
    ("wishlist the diamond ring",            "ADD_TO_WISHLIST"),
    ("heart this",                           "ADD_TO_WISHLIST"),
    ("put in wishlist",                      "ADD_TO_WISHLIST"),
    ("put diamond ring in wishlist",         "ADD_TO_WISHLIST"),
    ("i like this add to wishlist",          "ADD_TO_WISHLIST"),
    ("mark as favourite",                    "ADD_TO_WISHLIST"),

    # ── REMOVE_ITEM (15 examples) ──
    ("remove from cart",                     "REMOVE_ITEM"),
    ("remove diamond ring from cart",        "REMOVE_ITEM"),
    ("remove gold chain from cart",          "REMOVE_ITEM"),
    ("delete gold chain from cart",          "REMOVE_ITEM"),
    ("delete diamond ring",                  "REMOVE_ITEM"),
    ("i don't want the ring",                "REMOVE_ITEM"),
    ("take out the necklace from cart",      "REMOVE_ITEM"),
    ("cancel the earrings from cart",        "REMOVE_ITEM"),
    ("remove this item from cart",           "REMOVE_ITEM"),
    ("drop the bangle from cart",            "REMOVE_ITEM"),
    ("take diamond ring out of cart",        "REMOVE_ITEM"),
    ("remove pearl necklace",                "REMOVE_ITEM"),
    ("i changed my mind remove ring",        "REMOVE_ITEM"),
    ("dont want gold chain anymore",         "REMOVE_ITEM"),
    ("undo add to cart",                     "REMOVE_ITEM"),

    # ── REMOVE_FROM_WISHLIST (12 examples) ──
    ("remove from wishlist",                 "REMOVE_FROM_WISHLIST"),
    ("remove diamond ring from wishlist",    "REMOVE_FROM_WISHLIST"),
    ("delete from wishlist",                 "REMOVE_FROM_WISHLIST"),
    ("delete gold chain from wishlist",      "REMOVE_FROM_WISHLIST"),
    ("unsave this",                          "REMOVE_FROM_WISHLIST"),
    ("unsave diamond ring",                  "REMOVE_FROM_WISHLIST"),
    ("remove from favourites",               "REMOVE_FROM_WISHLIST"),
    ("unfavourite the ring",                 "REMOVE_FROM_WISHLIST"),
    ("remove ring from saved items",         "REMOVE_FROM_WISHLIST"),
    ("i dont like this anymore remove",      "REMOVE_FROM_WISHLIST"),
    ("take off wishlist",                    "REMOVE_FROM_WISHLIST"),
    ("remove necklace from wishlist",        "REMOVE_FROM_WISHLIST"),

    # ── SHOW_CART (12 examples) ──
    ("show cart",                            "SHOW_CART"),
    ("show my cart",                         "SHOW_CART"),
    ("open cart",                            "SHOW_CART"),
    ("open my cart",                         "SHOW_CART"),
    ("my cart",                              "SHOW_CART"),
    ("view cart",                            "SHOW_CART"),
    ("view my cart",                         "SHOW_CART"),
    ("check cart",                           "SHOW_CART"),
    ("what is in my cart",                   "SHOW_CART"),
    ("cart items",                           "SHOW_CART"),
    ("see my cart",                          "SHOW_CART"),
    ("display cart",                         "SHOW_CART"),

    # ── CLEAR_CART (10 examples) ──
    ("clear cart",                           "CLEAR_CART"),
    ("clear my cart",                        "CLEAR_CART"),
    ("empty cart",                           "CLEAR_CART"),
    ("empty my cart",                        "CLEAR_CART"),
    ("remove all items from cart",           "CLEAR_CART"),
    ("reset cart",                           "CLEAR_CART"),
    ("delete everything from cart",          "CLEAR_CART"),
    ("start over cart",                      "CLEAR_CART"),
    ("wipe my cart",                         "CLEAR_CART"),
    ("remove all cart items",                "CLEAR_CART"),

    # ── CHECKOUT (12 examples) ──
    ("checkout",                             "CHECKOUT"),
    ("go to checkout",                       "CHECKOUT"),
    ("proceed to checkout",                  "CHECKOUT"),
    ("place order",                          "CHECKOUT"),
    ("place my order",                       "CHECKOUT"),
    ("pay now",                              "CHECKOUT"),
    ("complete purchase",                    "CHECKOUT"),
    ("complete my purchase",                 "CHECKOUT"),
    ("pay with card",                        "CHECKOUT"),
    ("confirm my order",                     "CHECKOUT"),
    ("buy now",                              "CHECKOUT"),
    ("proceed to payment",                   "CHECKOUT"),

    # ── SHOW_WISHLIST (10 examples) ──
    ("show wishlist",                        "SHOW_WISHLIST"),
    ("show my wishlist",                     "SHOW_WISHLIST"),
    ("open wishlist",                        "SHOW_WISHLIST"),
    ("open my wishlist",                     "SHOW_WISHLIST"),
    ("view wishlist",                        "SHOW_WISHLIST"),
    ("my wishlist",                          "SHOW_WISHLIST"),
    ("my favourites",                        "SHOW_WISHLIST"),
    ("show saved items",                     "SHOW_WISHLIST"),
    ("see my wishlist",                      "SHOW_WISHLIST"),
    ("show liked products",                  "SHOW_WISHLIST"),

    # ── SEARCH (15 examples) ──
    ("search diamond ring",                  "SEARCH"),
    ("search for diamond ring",              "SEARCH"),
    ("find gold chain",                      "SEARCH"),
    ("find me a necklace",                   "SEARCH"),
    ("show me pearl necklace",               "SEARCH"),
    ("do you have earrings",                 "SEARCH"),
    ("look for bangle",                      "SEARCH"),
    ("search for anklet",                    "SEARCH"),
    ("find mangala sutra",                   "SEARCH"),
    ("is diamond ring available",            "SEARCH"),
    ("look up gold chain",                   "SEARCH"),
    ("search pearl",                         "SEARCH"),
    ("find me something for wedding",        "SEARCH"),
    ("search zyra ring",                     "SEARCH"),
    ("find nova earrings",                   "SEARCH"),
    ("show diamond ring",                    "SEARCH"),
    ("show gold chain",                      "SEARCH"),
    ("show pearl necklace",                  "SEARCH"),

    # ── SHOW_CATEGORY (30+ examples with material + item combos) ──
    ("show rings",                           "SHOW_CATEGORY"),
    ("show all rings",                       "SHOW_CATEGORY"),
    ("open rings section",                   "SHOW_CATEGORY"),
    ("browse rings",                         "SHOW_CATEGORY"),
    ("show necklaces",                       "SHOW_CATEGORY"),
    ("show me necklace",                     "SHOW_CATEGORY"),
    ("show me necklaces",                    "SHOW_CATEGORY"),
    ("open necklaces",                       "SHOW_CATEGORY"),
    ("browse necklaces",                     "SHOW_CATEGORY"),
    ("show earrings",                        "SHOW_CATEGORY"),
    ("show me earrings",                     "SHOW_CATEGORY"),
    ("show me earring",                      "SHOW_CATEGORY"),
    ("open earrings",                        "SHOW_CATEGORY"),
    ("show bracelets",                       "SHOW_CATEGORY"),
    ("show chains",                          "SHOW_CATEGORY"),
    ("show me chains",                       "SHOW_CATEGORY"),
    ("show pendants",                        "SHOW_CATEGORY"),
    ("show me pendants",                     "SHOW_CATEGORY"),
    ("show bangles",                         "SHOW_CATEGORY"),
    ("browse earrings",                      "SHOW_CATEGORY"),
    ("show me rings",                        "SHOW_CATEGORY"),
    ("go to rings section",                  "SHOW_CATEGORY"),
    # Material + item combinations
    ("show gold rings",                      "SHOW_CATEGORY"),
    ("show gold necklaces",                  "SHOW_CATEGORY"),
    ("show gold earrings",                   "SHOW_CATEGORY"),
    ("show gold chain",                      "SHOW_CATEGORY"),
    ("show gold chains",                     "SHOW_CATEGORY"),
    ("show gold bangles",                    "SHOW_CATEGORY"),
    ("show gold bracelet",                   "SHOW_CATEGORY"),
    ("show diamond rings",                   "SHOW_CATEGORY"),
    ("show diamond necklaces",               "SHOW_CATEGORY"),
    ("show diamond earrings",                "SHOW_CATEGORY"),
    ("show silver rings",                    "SHOW_CATEGORY"),
    ("show silver necklaces",                "SHOW_CATEGORY"),
    ("show pearl necklaces",                 "SHOW_CATEGORY"),
    ("show pearl earrings",                  "SHOW_CATEGORY"),
    ("show platinum rings",                  "SHOW_CATEGORY"),
    ("show kundan jewellery",                "SHOW_CATEGORY"),
    ("show meenakari jewellery",             "SHOW_CATEGORY"),

    # ── FILTER (12 examples) ──
    ("show rings under 2 lakhs",             "FILTER"),
    ("show jewellery under 1 lakh",          "FILTER"),
    ("filter by price",                      "FILTER"),
    ("filter price under 500000",            "FILTER"),
    ("show cheap jewellery",                 "FILTER"),
    ("gold jewellery only",                  "FILTER"),
    ("diamond collection only",              "FILTER"),
    ("show sale items only",                 "FILTER"),
    ("sort by price low to high",            "FILTER"),
    ("sort by price high to low",            "FILTER"),
    ("show most expensive jewellery",        "FILTER"),
    ("show affordable rings",                "FILTER"),

    # ── PRICE (12 examples) ──
    ("price of diamond ring",                "PRICE"),
    ("what is the price of gold chain",      "PRICE"),
    ("how much is the gold chain",           "PRICE"),
    ("cost of pearl necklace",               "PRICE"),
    ("what does the bangle cost",            "PRICE"),
    ("how much are the earrings",            "PRICE"),
    ("price check mangala sutra",            "PRICE"),
    ("tell me the price of zyra ring",       "PRICE"),
    ("what is the cost of diamond ring",     "PRICE"),
    ("how much does nova earring cost",      "PRICE"),
    ("rate of gold chain",                   "PRICE"),
    ("price for anklet",                     "PRICE"),

    # ── PRODUCT_INFO (10 examples) ──
    ("tell me about diamond ring",           "PRODUCT_INFO"),
    ("details of the gold chain",            "PRODUCT_INFO"),
    ("more info about earrings",             "PRODUCT_INFO"),
    ("is the ring returnable",               "PRODUCT_INFO"),
    ("shipping days for necklace",           "PRODUCT_INFO"),
    ("delivery information for ring",        "PRODUCT_INFO"),
    ("tell me more about this",              "PRODUCT_INFO"),
    ("what material is the ring",            "PRODUCT_INFO"),
    ("describe the gold chain",              "PRODUCT_INFO"),
    ("show product details",                 "PRODUCT_INFO"),

    # ── ADD_TO_COMPARE (8 examples) ──
    ("compare this",                         "ADD_TO_COMPARE"),
    ("add to compare",                       "ADD_TO_COMPARE"),
    ("compare diamond ring",                 "ADD_TO_COMPARE"),
    ("compare these rings",                  "ADD_TO_COMPARE"),
    ("add ring to compare",                  "ADD_TO_COMPARE"),
    ("compare gold chain and diamond ring",  "ADD_TO_COMPARE"),
    ("i want to compare products",           "ADD_TO_COMPARE"),
    ("compare jewellery",                    "ADD_TO_COMPARE"),

    # ── SHOW_ORDERS (12 examples) ──
    ("my orders",                            "SHOW_ORDERS"),
    ("show my orders",                       "SHOW_ORDERS"),
    ("order history",                        "SHOW_ORDERS"),
    ("show order history",                   "SHOW_ORDERS"),
    ("track my order",                       "SHOW_ORDERS"),
    ("track order",                          "SHOW_ORDERS"),
    ("show past orders",                     "SHOW_ORDERS"),
    ("where is my order",                    "SHOW_ORDERS"),
    ("order status",                         "SHOW_ORDERS"),
    ("check my orders",                      "SHOW_ORDERS"),
    ("view my orders",                       "SHOW_ORDERS"),
    ("recent orders",                        "SHOW_ORDERS"),

    # ── SHOW_OFFERS (10 examples) ──
    ("show offers",                          "SHOW_OFFERS"),
    ("show current offers",                  "SHOW_OFFERS"),
    ("best deals",                           "SHOW_OFFERS"),
    ("any discounts",                        "SHOW_OFFERS"),
    ("sale items",                           "SHOW_OFFERS"),
    ("what is on sale",                      "SHOW_OFFERS"),
    ("show coupons",                         "SHOW_OFFERS"),
    ("any deals today",                      "SHOW_OFFERS"),
    ("current offers",                       "SHOW_OFFERS"),
    ("show promotions",                      "SHOW_OFFERS"),

    # ── RECOMMEND (10 examples) ──
    ("what do you recommend",               "RECOMMEND"),
    ("best jewellery",                       "RECOMMEND"),
    ("popular items",                        "RECOMMEND"),
    ("show popular items",                   "RECOMMEND"),
    ("trending jewellery",                   "RECOMMEND"),
    ("top picks",                            "RECOMMEND"),
    ("featured products",                    "RECOMMEND"),
    ("best sellers",                         "RECOMMEND"),
    ("what is popular",                      "RECOMMEND"),
    ("show me something nice",               "RECOMMEND"),

    # ── NAVIGATE (25+ examples) ──
    ("go home",                              "NAVIGATE"),
    ("go to home page",                      "NAVIGATE"),
    ("go to home",                           "NAVIGATE"),
    ("my account",                           "NAVIGATE"),
    ("go to account",                        "NAVIGATE"),
    ("go to profile",                        "NAVIGATE"),
    ("login",                                "NAVIGATE"),
    ("sign in",                              "NAVIGATE"),
    ("register",                             "NAVIGATE"),
    ("sign up",                              "NAVIGATE"),
    ("contact us",                           "NAVIGATE"),
    ("about us",                             "NAVIGATE"),
    ("read blogs",                           "NAVIGATE"),
    ("faq",                                  "NAVIGATE"),
    ("open collections",                     "NAVIGATE"),
    ("go to shopping",                       "NAVIGATE"),
    ("open shopping",                        "NAVIGATE"),
    ("go to shop",                           "NAVIGATE"),
    ("go to service",                        "NAVIGATE"),
    ("open service page",                    "NAVIGATE"),
    ("show services",                        "NAVIGATE"),
    ("navigate to services",                 "NAVIGATE"),
    ("go to services",                       "NAVIGATE"),
    ("open services",                        "NAVIGATE"),
    ("services page",                        "NAVIGATE"),
    ("take me to services",                  "NAVIGATE"),
    ("show service",                         "NAVIGATE"),

    # ── UNIVERSAL ──
    ("hello",              "GREET"),
    ("hi",                 "GREET"),
    ("hey",                "GREET"),
    ("good morning",       "GREET"),
    ("good evening",       "GREET"),
    ("help",               "HELP"),
    ("help me",            "HELP"),
    ("i need help",        "HELP"),
    ("what can you do",    "HELP"),
    ("can you help me",    "HELP"),
    ("can i ask something", "HELP"),
    ("can i say something", "HELP"),
    ("i want to ask something", "HELP"),
    ("show commands",      "HELP"),
    ("thanks",             "THANKS"),
    ("thank you",          "THANKS"),
    ("bye",                "BYE"),
    ("goodbye",            "BYE"),
    ("see you",            "BYE"),
    ("dark mode",          "THEME_DARK"),
    ("enable dark mode",   "THEME_DARK"),
    ("light mode",         "THEME_LIGHT"),
    ("enable light mode",  "THEME_LIGHT"),
    
    # ── UPDATE_CART (15 examples) ──
    ("increase to 3",                        "UPDATE_CART"),
    ("increase quantity to 3",               "UPDATE_CART"),
    ("change quantity to 2",                 "UPDATE_CART"),
    ("update cart quantity",                 "UPDATE_CART"),
    ("make it 3",                            "UPDATE_CART"),
    ("make it 2",                            "UPDATE_CART"),
    ("i want 2 of this",                     "UPDATE_CART"),
    ("change to 2 pieces",                   "UPDATE_CART"),
    ("update to 3",                          "UPDATE_CART"),
    ("change quantity",                      "UPDATE_CART"),
    ("set quantity to 4",                    "UPDATE_CART"),
    ("increase diamond ring to 3",           "UPDATE_CART"),
    ("make diamond ring quantity 2",         "UPDATE_CART"),
    ("update gold chain to 2",              "UPDATE_CART"),
    ("i need 3 of diamond ring",             "UPDATE_CART"),
    # Augmented Data
    ('add this to my app', 'ADD_TO_CART'),
    ('chuck it in the cart', 'ADD_TO_CART'),
    ('ill take it', 'ADD_TO_CART'),
    ('bhai add this', 'ADD_TO_CART'),
    ('add karna yar', 'ADD_TO_CART'),
    ('dal do cart me', 'ADD_TO_CART'),
    ('purchase karlo', 'ADD_TO_CART'),
    ('buy karna hai', 'ADD_TO_CART'),
    ('i will buy it', 'ADD_TO_CART'),
    ('add the ring please', 'ADD_TO_CART'),
    ('one piece of this', 'ADD_TO_CART'),
    ('yes add it', 'ADD_TO_CART'),
    ('add to bag', 'ADD_TO_CART'),
    ('put it in my bag', 'ADD_TO_CART'),
    ('toss it in the cart', 'ADD_TO_CART'),
    ('i want this one', 'ADD_TO_CART'),
    ('chuck the ring', 'REMOVE_ITEM'),
    ('nah remove it', 'REMOVE_ITEM'),
    ('put back the necklace', 'REMOVE_ITEM'),
    ('hatao cart se', 'REMOVE_ITEM'),
    ('hata do', 'REMOVE_ITEM'),
    ('remove d ring', 'REMOVE_ITEM'),
    ('take it out', 'REMOVE_ITEM'),
    ('i changed my mind', 'REMOVE_ITEM'),
    ('delete karna', 'REMOVE_ITEM'),
    ('remove from bag', 'REMOVE_ITEM'),
    ('drop it', 'REMOVE_ITEM'),
    ('no cancel it', 'REMOVE_ITEM'),
    ("don't want this", 'REMOVE_ITEM'),
    ('remove this piece', 'REMOVE_ITEM'),
    ('whats trending', 'RECOMMEND'),
    ('im looking for a gift', 'RECOMMEND'),
    ('what should i buy', 'RECOMMEND'),
    ('suggest something', 'RECOMMEND'),
    ('aacha kuch dikhao', 'RECOMMEND'),
    ('koi badhiya sa dikhao', 'RECOMMEND'),
    ('give me recommendations', 'RECOMMEND'),
    ('what are people buying', 'RECOMMEND'),
    ('show best pieces', 'RECOMMEND'),
    ('top selling items', 'RECOMMEND'),
    ('anything on discount', 'SHOW_OFFERS'),
    ('sale dikhao', 'SHOW_OFFERS'),
    ('offers chal raha hai kya', 'SHOW_OFFERS'),
    ('discounted items', 'SHOW_OFFERS'),
    ('is there a sale', 'SHOW_OFFERS'),
    ('show me deals', 'SHOW_OFFERS'),
    ('any promo codes', 'SHOW_OFFERS'),
    ('cheap items', 'SHOW_OFFERS'),
    ('low price best deals', 'SHOW_OFFERS'),
    ('how much for the bangles', 'PRICE'),
    ('kya price hai', 'PRICE'),
    ('kitne ka hai', 'PRICE'),
    ('whats the rate', 'PRICE'),
    ('tell me the cost', 'PRICE'),
    ('price check', 'PRICE'),
    ('how much is it', 'PRICE'),
    ('bhav kya hai', 'PRICE'),
    ('show me something in gold under 50k', 'FILTER'),
    ('do you have this in silver', 'FILTER'),
    ('filter by silver', 'FILTER'),
    ('sasta wala dikhao', 'FILTER'),
    ('mehenga wala dikhao', 'FILTER'),
    ('under 10000', 'FILTER'),
    ('50000 range items', 'FILTER'),
    ('budget 20000', 'FILTER'),
    ('yaar show me rings', 'SHOW_CATEGORY'),
    ('anguthi dikhao', 'SHOW_CATEGORY'),
    ('chain dikhana', 'SHOW_CATEGORY'),
    ('mangalsutra dikhao', 'SHOW_CATEGORY'),
    ('earrings open karo', 'SHOW_CATEGORY'),
    ('categories of necklaces', 'SHOW_CATEGORY'),
    ('what is the weather', 'OUT_OF_SCOPE'),
    ('book a flight', 'OUT_OF_SCOPE'),
    ('play music', 'OUT_OF_SCOPE'),
    ('tell me a joke', 'OUT_OF_SCOPE'),
    ('turn on lights', 'OUT_OF_SCOPE'),
    ('what time is it', 'OUT_OF_SCOPE'),
    ('who is the president', 'OUT_OF_SCOPE'),
    ('set an alarm', 'OUT_OF_SCOPE'),
    ('call mom', 'OUT_OF_SCOPE'),
    ('open youtube', 'OUT_OF_SCOPE'),
    # Fix CV=3 error 
    ('thanks a lot', 'THANKS'),
    ('thank you so much', 'THANKS'),
    ('turn dark mode on please', 'THEME_DARK'),
    ('dark theme on', 'THEME_DARK'),
    ('set to light theme', 'THEME_LIGHT'),
    ('switch to light', 'THEME_LIGHT'),
    ('light mode please', 'THEME_LIGHT'),
]

# ── Category → URL slug ──
CATEGORY_SLUGS = {
    "ring": "rings", "rings": "rings", "band": "rings", "bands": "rings",
    "necklace": "necklaces", "necklaces": "necklaces",
    "earring": "earrings", "earrings": "earrings",
    "bracelet": "bracelets", "bracelets": "bracelets",
    "bangle": "bracelets", "bangles": "bracelets",
    "anklet": "bracelets",
    "chain": "chains", "chains": "chains",
    "pendant": "pendants", "pendants": "pendants",
}

# ── Page navigation map ──
PAGE_MAP = {
    "order tracking": "/order/tracking",
    "order history": "/account/order",
    "my orders": "/account/order",
    "track order": "/order/tracking",
    "home": "/", "main": "/",
    "cart": "/cart",
    "wishlist": "/wishlist",
    "checkout": "/checkout",
    "orders": "/account/order", "order": "/account/order",
    "account": "/account/dashboard", "profile": "/account/dashboard",
    "dashboard": "/account/dashboard",
    "login": "/auth/login", "signin": "/auth/login",
    "register": "/auth/register", "signup": "/auth/register",
    "contact": "/contact-us",
    "about": "/about-us",
    "blog": "/blogs", "blogs": "/blogs",
    "faq": "/faq",
    "offers": "/offers",
    "collection": "/collections", "collections": "/collections",
    "compare": "/compare",
    "search": "/search",
    "tracking": "/order/tracking",
    "service page": "/service",
    "services page": "/service",
    "service": "/service",
    "services": "/service",
    "shopping": "/collections",
    "shop": "/collections",
    "products": "/collections",
    "all products": "/collections",
}


def _ctx_intent_confidence(ctx, default=1.0):
    try:
        return float(getattr(ctx, "last_intent_confidence", default))
    except (TypeError, ValueError):
        return default


def _item_match_confidence(item, default=1.0):
    if not isinstance(item, dict):
        return default
    try:
        return float(item.get("_confidence", default))
    except (TypeError, ValueError):
        return default


def _needs_risky_action_confirmation(ctx, item):
    # Ask confirmation only when both intent and entity confidence are weak.
    if getattr(ctx, "pending_action_bypass", False):
        return False
    intent_conf = _ctx_intent_confidence(ctx, default=1.0)
    item_conf = _item_match_confidence(item, default=1.0)
    return intent_conf < ACTION_CONFIRM_THRESHOLD and item_conf < ACTION_CONFIRM_THRESHOLD


def _clarify_risky_action(make_json, action_name, item):
    item_name = item.get("name") if isinstance(item, dict) else "this item"
    msg = f"I think you mean {item_name}. Say yes to confirm or no to cancel."
    return {
        "intent": "CLARIFY",
        "message": msg,
        "json": make_json(
            msg,
            "clarify",
            {
                "suggested_action": action_name,
                "item": item_name,
            },
        ),
    }


def handle_intent(intent, text, matcher, ctx, make_json, extract_quantity):
    t = text.lower()
    request_context = _get_request_context(ctx)

    # ── ADD_TO_CART ──
    # ── ADD_TO_CART ──
    if intent == "ADD_TO_CART":
        multi_matches, unmatched_parts = _extract_multi_cart_matches(
            text,
            matcher,
            extract_quantity,
            request_context=request_context,
        )
        if len(multi_matches) >= 2:
            actions = []
            lines = []

            for item, qty in multi_matches:
                ctx.update(intent, item, qty)
                ctx.add_to_cart(item, qty)
                lines.append(f"Added {qty}x {item['name']} to cart! (Rs {item['price'] * qty:,.0f})")
                actions.append(
                    {
                        "type": "add_to_cart",
                        "params": {
                            "productId": item["id"],
                            "quantity": qty,
                            "name": item["name"],
                            "price": item["price"],
                        },
                    }
                )

            msg = "\n".join(lines) + f"\nCart: {ctx.get_cart_count()} items - Rs {ctx.get_cart_total():,.0f}"
            return {
                "intent": intent,
                "message": msg,
                "json": json.dumps({"message": msg, "actions": actions}),
            }

        if len(multi_matches) == 1 and unmatched_parts:
            item, qty = multi_matches[0]
            ctx.update(intent, item, qty)
            ctx.add_to_cart(item, qty)

            missing = ", ".join(unmatched_parts)
            msg = (
                f"Added {qty}x {item['name']} to cart! (Rs {item['price'] * qty:,.0f})\n"
                f"Couldn't find: {missing}. Try saying exact product name.\n"
                f"Cart: {ctx.get_cart_count()} items - Rs {ctx.get_cart_total():,.0f}"
            )
            actions = [
                {
                    "type": "add_to_cart",
                    "params": {
                        "productId": item["id"],
                        "quantity": qty,
                        "name": item["name"],
                        "price": item["price"],
                    },
                }
            ]
            return {
                "intent": intent,
                "message": msg,
                "json": json.dumps({"message": msg, "actions": actions}),
            }

        qty = extract_quantity(text)

        # Check if user is referring to last item
        refer_words = ["more", "another", "same", "it", "that", "this", "again"]
        is_referring = any(w in t.split() for w in refer_words)

        if is_referring and ctx.last_item:
            item = ctx.last_item
        else:
            item = matcher.find(text, request_context=request_context)
            if not item:
                item = ctx.resolve_item(text, matcher)

        if item:
            if _needs_risky_action_confirmation(ctx, item):
                return _clarify_risky_action(make_json, "add_to_cart", item)
            ctx.update(intent, item, qty)
            ctx.add_to_cart(item, qty)
            msg = f"Added {qty}x {item['name']} to cart! (Rs {item['price']*qty:,.0f})"
            return {"intent": intent, "message": msg,
                    "json": make_json(msg, "add_to_cart", {
                        "productId": item["id"],
                        "quantity":  qty,
                        "name":      item["name"],
                        "price":     item["price"],
                    })}
        return {"intent": intent,
                "message": "Which jewellery would you like to add?\nTry: 'add diamond ring' or 'add gold chain'",
                "json": "{}"}

    # ── REMOVE_ITEM ──
    if intent == "REMOVE_ITEM":
        item = ctx.resolve_item(text, matcher)
        if item:
            if _needs_risky_action_confirmation(ctx, item):
                return _clarify_risky_action(make_json, "remove_from_cart", item)
            ctx.remove_from_cart(item)
            msg = f"Removed {item['name']} from your cart."
            return {"intent": intent, "message": msg,
                    "json": make_json(msg, "remove_from_cart", {"productId": item["id"]})}
        return {"intent": intent, "message": "Which item to remove? Say the product name.", "json": "{}"}

    if intent == "UPDATE_CART":
        qty  = extract_quantity(text)
        item = matcher.find(text, request_context=request_context)
        if not item:
            item = ctx.last_item

        if item and qty:
            if _needs_risky_action_confirmation(ctx, item):
                return _clarify_risky_action(make_json, "update_cart_qty", item)
            ctx.update(intent, item, qty)
            msg = f"Updated {item['name']} quantity to {qty}."
            return {"intent": intent, "message": msg,
                    "json": make_json(msg, "update_cart_qty", {
                        "productId": item["id"],
                        "quantity":  qty,
                        "name":      item["name"],
                    })}

        return {"intent": intent,
                "message": "Which item and what quantity?\nTry: 'set gold chain to 3'",
                "json": "{}"}
    # ── SHOW_CART ──
    if intent == "SHOW_CART":
        ctx.update(intent)
        summary = ctx.get_cart_summary()
        return {"intent": intent, "message": summary,
                "json": make_json(summary, "open_cart", {})}

    # ── CLEAR_CART ──
    if intent == "CLEAR_CART":
        ctx.clear_cart()
        msg = "Your cart has been cleared."
        return {"intent": intent, "message": msg,
                "json": make_json(msg, "clear_cart", {})}

    # ── CHECKOUT ──
    if intent == "CHECKOUT":
        msg = "Taking you to checkout..."
        return {"intent": intent, "message": msg,
                "json": make_json(msg, "navigate", {"url": "/checkout"})}

    # ── ADD_TO_WISHLIST ──
    if intent == "ADD_TO_WISHLIST":
        item = ctx.resolve_item(text, matcher)
        if item:
            ctx.update(intent, item)
            msg = f"Added {item['name']} to your wishlist."
            return {"intent": intent, "message": msg,
                    "json": make_json(msg, "add_to_wishlist", {"productId": item["id"], "name": item["name"]})}
        return {"intent": intent, "message": "Which item to add to wishlist? Say the product name.", "json": "{}"}

    # ── REMOVE_FROM_WISHLIST ──
    if intent == "REMOVE_FROM_WISHLIST":
        item = ctx.resolve_item(text, matcher)
        if item:
            msg = f"Removed {item['name']} from your wishlist."
            return {"intent": intent, "message": msg,
                    "json": make_json(msg, "remove_from_wishlist", {"productId": item["id"]})}
        return {"intent": intent, "message": "Which item to remove from wishlist?", "json": "{}"}

    # ── SHOW_WISHLIST ──
    if intent == "SHOW_WISHLIST":
        msg = "Opening your wishlist..."
        return {"intent": intent, "message": msg,
                "json": make_json(msg, "navigate", {"url": "/wishlist"})}

    # ── SEARCH ──
    if intent == "SEARCH":
        item  = matcher.find(text, request_context=request_context)
        query = item["name"] if item else _clean_query(t)
        ctx.update(intent, item)
        msg = f"Searching for '{query}'..."
        return {"intent": intent, "message": msg,
                "json": make_json(msg, "search", {"query": query})}

    # ── SHOW_CATEGORY ──
    if intent == "SHOW_CATEGORY":
        slug = None
        for word in t.split():
            if word in CATEGORY_SLUGS:
                slug = CATEGORY_SLUGS[word]
                break
        if slug:
            msg = f"Filtering to {slug.capitalize()} collection..."
            return {"intent": intent, "message": msg,
                    "json": make_json(msg, "filter", {"category": slug})}
        return {"intent": intent,
                "message": "Which category? Rings, Necklaces, Earrings, Bracelets, Chains, Pendants",
                "json": "{}"}

    # ── FILTER ──
    if intent == "FILTER":
        params = {}
        max_price = _extract_price_value(text)
        if max_price is not None:
            params["maxPrice"] = max_price
        for kw, slug in CATEGORY_SLUGS.items():
            if kw in t:
                params["category"] = slug
                break
        if "low to high" in t or "cheap" in t or "lowest" in t:
            params["sort"] = "price_asc"
        elif "high to low" in t or "expensive" in t or "highest" in t:
            params["sort"] = "price_desc"
        if "gold" in t:
            params["brand"] = "gold"
        if "diamond" in t:
            params["brand"] = "diamond"
        msg = "Filtering products..."
        return {"intent": intent, "message": msg,
                "json": make_json(msg, "filter", params)}

    # ── PRICE ──
    if intent == "PRICE":
        item = ctx.resolve_item(text, matcher)
        if item:
            msg = f"{item['name']}\nPrice: Rs {item['price']:,.0f}"
            return {"intent": intent, "message": msg, "json": make_json(msg)}
        return {"intent": intent, "message": "Which product? Say the name.", "json": "{}"}

    # ── PRODUCT_INFO ──
    if intent == "PRODUCT_INFO":
        item = ctx.resolve_item(text, matcher)
        if item:
            msg = (
                f"{item['name']}\n"
                f"Price: Rs {item['price']:,.0f}\n"
                "Opening product page..."
            )
            return {"intent": intent, "message": msg,
                    "json": make_json(msg, "navigate", {"url": f"/product/{item['id']}"})}
        return {"intent": intent, "message": "Which product?", "json": "{}"}

    # ── ADD_TO_COMPARE ──
    if intent == "ADD_TO_COMPARE":
        item = ctx.resolve_item(text, matcher)
        if item:
            msg = f"Added {item['name']} to compare list."
            return {"intent": intent, "message": msg,
                    "json": make_json(msg, "add_to_compare", {"productId": item["id"]})}
        return {"intent": intent, "message": "Which product to compare?", "json": "{}"}

    # ── SHOW_ORDERS ──
    if intent == "SHOW_ORDERS":
        msg = "Opening your orders..."
        return {"intent": intent, "message": msg,
                "json": make_json(msg, "navigate", {"url": "/account/order"})}

    # ── SHOW_OFFERS ──
    if intent == "SHOW_OFFERS":
        msg = "Opening offers and deals..."
        return {"intent": intent, "message": msg,
                "json": make_json(msg, "navigate", {"url": "/offers"})}

    # ── RECOMMEND ──
    if intent == "RECOMMEND":
        items = matcher.db.load()
        top   = items[:4] if items else []
        if top:
            listing = "\n".join(f"  - {i['name']} - Rs {i['price']:,.0f}" for i in top)
            msg = f"Our top picks:\n{listing}"
        else:
            msg = "Check out our featured jewellery collections!"
        return {"intent": intent, "message": msg,
                "json": make_json(msg, "navigate", {"url": "/collections"})}

    # ── NAVIGATE ──
    # ── NAVIGATE ──
    if intent == "NAVIGATE":
        url = "/"
        t_clean = t.strip()

        # Check longer phrases first so specific routes win over generic ones.
        for keyword in sorted(PAGE_MAP.keys(), key=len, reverse=True):
            if keyword in t_clean:
                url = PAGE_MAP[keyword]
                break

        msg = "Navigating..."
        return {"intent": intent, "message": msg,
                "json": make_json(msg, "navigate", {"url": url})}
    


    # ── THEME_DARK ──
    if intent == "THEME_DARK":
        msg = "Switching to dark mode"
        return {"intent": intent, "message": msg,
                "json": make_json(msg, "set_theme", {"theme": "dark"})}

    # ── THEME_LIGHT ──
    if intent == "THEME_LIGHT":
        msg = "Switching to light mode"
        return {"intent": intent, "message": msg,
                "json": make_json(msg, "set_theme", {"theme": "light"})}

    return None


def _clean_query(text):
    stop = ["search", "find", "show", "me", "for", "a", "an", "the",
            "do", "you", "have", "is", "available", "look", "i", "want"]
    words = [w for w in text.split() if w not in stop]
    return " ".join(words).strip() or "jewellery"


def _extract_price_value(text):
    """Extract numeric price with support for Indian units like lakh/crore."""
    lowered = str(text or "").lower()
    unit_multipliers = {
        "k": 1_000,
        "thousand": 1_000,
        "lac": 100_000,
        "lacs": 100_000,
        "lakh": 100_000,
        "lakhs": 100_000,
        "cr": 10_000_000,
        "crore": 10_000_000,
        "crores": 10_000_000,
    }

    unit_match = re.search(r"(\d+(?:\.\d+)?)\s*(k|thousand|lac|lacs|lakh|lakhs|cr|crore|crores)\b", lowered)
    if unit_match:
        value = float(unit_match.group(1))
        multiplier = unit_multipliers[unit_match.group(2)]
        return max(1, int(value * multiplier))

    number_match = re.search(r"\d[\d,]*", lowered)
    if number_match:
        digits = number_match.group(0).replace(",", "")
        if digits.isdigit():
            return max(1, int(digits))

    return None


def _extract_multi_cart_matches(text, matcher, extract_quantity, request_context=None):
    """Parse commands like 'add gold chain and anklet to cart'."""
    lowered = str(text or "").lower().strip()
    if not lowered:
        return [], []

    normalized = re.sub(r"\b(to|into|in)\s+(my\s+)?cart\b", " ", lowered)
    normalized = normalized.replace("&", " and ")

    if " and " not in normalized and "," not in normalized:
        return [], []

    parts = [part.strip(" ,") for part in re.split(r"\s+and\s+|\s*,\s*", normalized) if part.strip(" ,")]
    if len(parts) < 2:
        return [], []

    matches = []
    unmatched = []
    seen_ids = set()

    for part in parts:
        item = matcher.find(part, request_context=request_context)
        if not item:
            unmatched.append(part)
            continue
        item_id = item.get("id")
        if item_id in seen_ids:
            continue
        seen_ids.add(item_id)
        qty = extract_quantity(part)
        matches.append((item, qty))

    return matches, unmatched


def _get_request_context(ctx):
    if ctx is None:
        return None
    frontend_context = getattr(ctx, "last_frontend_context", None)
    if isinstance(frontend_context, dict):
        return frontend_context
    return None
