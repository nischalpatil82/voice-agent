"""
core/entity_extractor.py — Enterprise Entity Extraction
Fast regex/spaCy-light named entity recognition for voice commands.
Extracts PRODUCT, QUANTITY, PRICE, MATERIAL, and CATEGORY before matcher runs.
"""

import re
import logging

LOG = logging.getLogger(__name__)

# Constants for common jewellery terms
MATERIALS = {"gold", "silver", "diamond", "platinum", "pearl", "ruby", "emerald", "sapphire", "kundan", "polki"}
CATEGORIES = {"ring", "rings", "necklace", "necklaces", "earring", "earrings", 
              "bracelet", "bracelets", "bangle", "bangles", "chain", "chains", 
              "pendant", "pendants", "anklet", "anklets", "sutra", "mangala"}

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

def extract_quantity(text, product_mentioned=None):
    """Context-aware quantity extraction."""
    word_map = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "eleven": 11, "twelve": 12, "a dozen": 12, "dozen": 12,
        "half dozen": 6, "twenty": 20, "fifty": 50, "hundred": 100,
        "single": 1, "double": 2, "triple": 3,
        "couple": 2, "pair": 2, "few": 3, "several": 5,
    }
    t = text.lower()
    
    # Check for direct number + product if product is given to avoid matching "one" in "the one ring"
    if product_mentioned:
        # e.g., "2 rings", "two rings"
        p_words = product_mentioned.split()
        if p_words:
            core_product = p_words[-1] 
            pattern = r'\b(\d+|' + '|'.join(word_map.keys()) + r')\s+(?:of\s+)?(?:the\s+)?(?:' + re.escape(core_product) + r')\b'
            match = re.search(pattern, t)
            if match:
                val = match.group(1)
                return int(val) if val.isdigit() else word_map.get(val, 1)

    # Fallback to generic number search
    for w, n in word_map.items():
        if re.search(rf"\b{w}\b", t):
            # Guard against "a hundred" returning 100 arbitrarily if that's not what is meant usually
            if w == "hundred" and "a hundred" not in t:
                return n
            elif w != "hundred":
                return n
                
    nums = re.findall(r'\b(\d+)\b', t)
    qty = int(nums[0]) if nums else 1
    return max(1, min(50, qty))

class EntityExtractor:
    def __init__(self):
        pass

    def extract(self, text):
        """Extracts entities from the text into a structured dictionary."""
        t = text.lower()
        entities = {
            "quantity": None,
            "max_price": None,
            "min_price": None,
            "materials": [],
            "categories": [],
            "product_query": None,
        }

        # Price
        if any(w in t for w in ["under", "below", "less than", "max", "cheap"]):
            entities["max_price"] = _extract_price_value(t)
        elif any(w in t for w in ["above", "more than", "min", "expensive"]):
            entities["min_price"] = _extract_price_value(t)
        elif _extract_price_value(t):
             entities["max_price"] = _extract_price_value(t)

        # Materials
        for mat in MATERIALS:
            if re.search(rf"\b{mat}\b", t):
                entities["materials"].append(mat)
                
        # Categories
        for cat in CATEGORIES:
            if re.search(rf"\b{cat}\b", t):
                entities["categories"].append(cat)
                
        # Attempt to synthesize a product query by removing action/stop words
        stop_words = ["add", "remove", "show", "find", "search", "buy", "order", "get", "put", "cart", "wishlist", "to", "from", "in", "the", "a", "an", "for", "please", "me"]
        words = [w for w in t.split() if w not in stop_words and not w.isdigit()]
        
        # Heuristic product query from remaining words
        if words:
            query = " ".join(words)
            # Remove price terms from product query
            query = re.sub(r'(under|below|above)\s+\d+\s*(k|lakhs?|lacs?|crores?|cr|thousand)?', '', query)
            query = re.sub(r'\d+\s*(k|lakhs?|lacs?|crores?|cr|thousand)', '', query)
            entities["product_query"] = query.strip()
        
        # Quantity
        entities["quantity"] = extract_quantity(text, product_mentioned=entities["product_query"])
        
        LOG.debug("[NER] Extracted entities: %s", entities)
        return entities
