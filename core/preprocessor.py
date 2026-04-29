"""
core/preprocessor.py
Enterprise-grade text preprocessing for voice commands.
Spell correction + phonetic normalization + voice-specific error handling.

Key design decisions:
- Normalizations are SAFE — never change words that could alter intent
- Phonetic map covers Indian English pronunciation patterns
- Spell checker uses domain-specific dictionary
- All transformations are logged for debugging
"""

from spellchecker import SpellChecker
import jellyfish
import re
from functools import lru_cache

# ── Domain-specific words that spellchecker should never change ──
DOMAIN_WORDS = [
    # Jewellery items
    "jewellery", "jewelry", "jewel", "necklace", "necklaces",
    "earring", "earrings", "bracelet", "bracelets",
    "bangle", "bangles", "anklet", "anklets",
    "pendant", "pendants", "mangala", "sutra", "mangalasutra",
    "choker", "chokers", "tiara", "tiaras", "brooch", "brooches",
    "cufflink", "cufflinks", "nosering", "noserings", "toe ring",
    # Metals & gems
    "diamond", "gold", "silver", "platinum", "pearl", "ruby",
    "emerald", "sapphire", "topaz", "amethyst", "opal", "garnet",
    "tanzanite", "zircon", "onyx", "turquoise", "coral", "kundan",
    "polki", "meenakari", "jadau", "antique", "oxidized",
    # Brand / product specific
    "zyra", "nova", "justbill",
    # Actions — must not be changed
    "wishlist", "checkout", "cart", "compare", "filter",
    "login", "signup", "logout", "register",
    # Categories
    "rings", "chains", "pendants", "kada", "payal", 
    "choker", "kara", "baju band", "kamarband", "tops",
]

HINGLISH_MAP = {
    "dikhao": "show", "dikha": "show",
    "dalo": "add", "dal do": "add",
    "hatao": "remove", "hata do": "remove",
    "kitna": "how much", "kitne": "how much",
    "dekho": "show", "buy": "buy",
    "chahiye": "want", "mangta": "want",
    "anguthi": "ring",
    "haar": "necklace",
    "kangan": "bangle",
    "payal": "anklet",
    "sasta": "cheap", "mehenga": "expensive",
    "achha": "good", "badhiya": "nice",
}

# ── Common pronunciation mistakes → correct word ──
# Only includes SAFE transformations that won't alter intent
PHONETIC_MAP = {
    # Jewellery mispronunciations
    "jwellery":     "jewellery",
    "jwellry":      "jewellery",
    "jewelery":     "jewellery",
    "jewlery":      "jewellery",
    "jewellry":     "jewellery",
    "joolery":      "jewellery",
    "julery":       "jewellery",
    "neklace":      "necklace",
    "neckless":     "necklace",
    "nekless":      "necklace",
    "necklas":      "necklace",
    "earing":       "earring",
    "earings":      "earrings",
    "eering":       "earring",
    "eerings":      "earrings",
    "erings":       "earrings",
    "braclet":      "bracelet",
    "bracelate":    "bracelet",
    "braslet":      "bracelet",
    "bansle":       "bangle",
    "bangal":       "bangle",
    "bangel":       "bangle",
    "dimand":       "diamond",
    "dimond":       "diamond",
    "dymond":       "diamond",
    "damond":       "diamond",
    "damand":       "diamond",
    "daimond":      "diamond",
    "peral":        "pearl",
    "perle":        "pearl",
    "parl":         "pearl",
    "mangalsutra":  "mangala sutra",
    "mangalasutra": "mangala sutra",
    "mangalasuthra":"mangala sutra",
    "mangulasutra": "mangala sutra",
    "platinam":     "platinum",
    "plantinum":    "platinum",
    "silvr":        "silver",
    "sylver":       "silver",
    "saphire":      "sapphire",
    "sappire":      "sapphire",
    "emrald":       "emerald",
    "rubby":        "ruby",
    "anklet":       "anklet",
    "anklate":      "anklet",
    # Cart/wishlist — safe transformations
    "crat":         "cart",
    "kart":         "cart",
    "wislist":      "wishlist",
    "whishlist":    "wishlist",
    "wishlit":      "wishlist",
    "wisslist":     "wishlist",
    "chekout":      "checkout",
    "checkaut":     "checkout",
    "chekcout":     "checkout",
    # Common Indian English pronunciations — safe only
    "addto":        "add to",
    "showme":       "show me",
    "gotto":        "go to",
    "goto":         "go to",
    "findme":       "find me",
    "giveme":       "give me",
    "takeme":       "take me",
    "sevice":       "service",
    "sevices":      "services",
    "sevicese":     "services",
    "servicese":    "services",
    "sarvice":      "service",
    "sarvices":     "services",
    "zara":         "zyra",
    "saira":        "zyra",
    "cyra":         "zyra",
    "jira":         "zyra",
    "zero":         "zyra",
    "nova":         "nova",
    "nowa":         "nova",
    "chuck":        "remove",
    "juck":         "remove",
}

# ── Safe shorthand normalizations — ONLY ones that don't change meaning ──
# IMPORTANT: We do NOT normalize words that could be actual commands
# e.g., "no", "set", "change", "increase" are KEPT as-is
NORMALIZE_MAP = {
    "wanna":    "want to",
    "gonna":    "going to",
    "gimme":    "give me",
    "lemme":    "let me",
    "plz":      "please",
    "pls":      "please",
    "thx":      "thanks",
    "ty":       "thank you",
    "ur":       "your",
    "bcz":      "because",
    "bcoz":     "because",
    "coz":      "because",
    "nd":       "and",
    "w/o":      "without",
    "qty":      "quantity",
    "amt":      "amount",
    "nos":      "numbers",
    "fav":      "favourite",
    "favs":     "favourites",
    "acc":      "account",
    "del":      "delete",
    "rmv":      "remove",
    "cmpare":   "compare",
}


class TextPreprocessor:

    def __init__(self):
        self.spell = SpellChecker()
        # Add domain words so spellchecker doesn't change them
        self.spell.word_frequency.load_words(DOMAIN_WORDS)

    def load_catalog_words(self, items):
        """Dynamically add catalog items to spellchecker."""
        for item in items:
            name = item.get("name", "")
            if name:
                self.spell.word_frequency.load_words(name.lower().split())

    def preprocess(self, text: str) -> str:
        """Full preprocessing pipeline with caching for repeated commands."""
        normalized_input = str(text or "").lower().strip()
        if not normalized_input:
            return ""
        return self._preprocess_cached(normalized_input)

    @lru_cache(maxsize=2048)
    def _preprocess_cached(self, normalized_input: str) -> str:
        text = self._normalize_shortcuts(normalized_input)
        text = self._fix_phonetic(text)
        text = self._fix_spelling(text)
        text = self._clean(text)
        return text

    def _normalize_shortcuts(self, text: str) -> str:
        """Replace informal/shorthand words. Only safe substitutions."""
        words = text.split()
        out = []
        for w in words:
            if w in HINGLISH_MAP:
                out.append(HINGLISH_MAP[w])
            else:
                out.append(NORMALIZE_MAP.get(w, w))
        return " ".join(out)

    def _fix_phonetic(self, text: str) -> str:
        """Fix known pronunciation mistakes."""
        words = text.split()
        fixed = []
        for word in words:
            fixed.append(PHONETIC_MAP.get(word, word))
        return " ".join(fixed)

    def _fix_spelling(self, text: str) -> str:
        """Fix spelling mistakes using SpellChecker with phonetic similarity gate."""
        words = text.split()
        fixed = []
        for word in words:
            # Skip short words, numbers, domain words
            if len(word) <= 2 or word.isdigit() or word in DOMAIN_WORDS:
                fixed.append(word)
                continue

            # Skip words that are already in the phonetic map (already handled)
            if word in PHONETIC_MAP:
                fixed.append(word)
                continue

            # Get correction
            corrected = self.spell.correction(word)

            # Only use correction if it's reasonably similar
            if corrected and corrected != word:
                similarity = jellyfish.jaro_winkler_similarity(word, corrected)
                if similarity >= 0.85:
                    fixed.append(corrected)
                else:
                    fixed.append(word)
            else:
                fixed.append(word)
        return " ".join(fixed)

    def _clean(self, text: str) -> str:
        """Remove extra spaces and special characters (keep apostrophes for don't, etc.)."""
        text = re.sub(r"[^\w\s']", ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()