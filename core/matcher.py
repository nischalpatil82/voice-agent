"""
core/matcher.py — Enterprise Product Matcher
Multi-strategy matching: exact → keyword → fuzzy → semantic.
Returns top-N results with confidence scores.
"""

import re
import logging

from fuzzywuzzy import fuzz, process
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


LOG = logging.getLogger(__name__)

# Words that should never be matched to products
STOP_WORDS = {
    "add", "more", "another", "same", "it", "that", "this", "again",
    "the", "a", "an", "to", "of", "in", "on", "at", "for", "with",
    "and", "or", "but", "not", "my", "me", "i", "we", "you", "is",
    "are", "was", "were", "be", "been", "have", "has", "had", "do",
    "does", "did", "will", "would", "could", "should", "may", "might",
    "get", "set", "put", "give", "take", "make", "let", "some", "any",
    "all", "one", "two", "three", "four", "five", "six", "also", "just",
    "please", "show", "go", "open", "buy", "order", "want", "need",
    "remove", "delete", "clear", "update", "change", "increase", "decrease",
    "cart", "wishlist", "checkout", "search", "find", "look", "browse",
    "price", "cost", "how", "much", "what", "tell", "about", "details",
    "compare", "like", "love", "save", "favourite", "favorite",
    "can", "from", "into", "check", "see", "view", "display",
}

# Common ASR/spelling variants that appear in voice shopping commands.
TOKEN_NORMALIZATION = {
    "bangal": "bangle",
    "bangel": "bangle",
    "bansle": "bangle",
    "bracelets": "bracelet",
    "bangles": "bangle",
    "earrings": "earring",
    "rings": "ring",
    "chains": "chain",
    "pendants": "pendant",
    "necklaces": "necklace",
    "anklets": "anklet",
    "mangalsutra": "mangala_sutra",
    "mangalasutra": "mangala_sutra",
    "mangala": "mangala_sutra",
    "sutra": "mangala_sutra",
    "luxary": "luxury",
    "laxury": "luxury",
}

# Jewellery/domain-aware term equivalence for better semantic lookup.
TERM_EQUIVALENTS = {
    "bangle": {"bangle", "bracelet", "kada"},
    "bracelet": {"bracelet", "bangle", "kada"},
    "kada": {"kada", "bracelet", "bangle"},
    "chain": {"chain", "necklace"},
    "necklace": {"necklace", "chain"},
    "earring": {"earring", "stud"},
    "stud": {"stud", "earring"},
    "mangala_sutra": {"mangala_sutra", "mangalasutra"},
    "luxury": {"luxury", "premium", "royal", "signature"},
    "premium": {"premium", "luxury", "royal", "signature"},
}


MATERIALS = {"diamond", "gold", "silver", "platinum", "kundan", "pearl", "emerald", "ruby", "sapphire"}

def _normalize_text(text):
    cleaned = re.sub(r"[^a-z0-9\s]", " ", str(text or "").lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def _normalize_token(token):
    return TOKEN_NORMALIZATION.get(token, token)


def _extract_tokens(text):
    normalized = _normalize_text(text)
    if not normalized:
        return []
    return [_normalize_token(token) for token in normalized.split()]


def _expand_terms(tokens):
    expanded = set()
    for token in tokens:
        if not token:
            continue
        expanded.add(token)
        equivalents = TERM_EQUIVALENTS.get(token)
        if equivalents:
            expanded.update(equivalents)
    return expanded


def _meaningful_terms(tokens):
    return [token for token in tokens if token not in STOP_WORDS and len(token) >= 3]


def _item_terms(item):
    terms = _meaningful_terms(_extract_tokens(item.get("name", "")))
    keyword_terms = []
    for kw in item.get("keywords", []):
        keyword_terms.extend(_extract_tokens(kw))
    category_terms = _extract_tokens(item.get("category", ""))
    attribute_terms = []
    attributes = item.get("attributes")
    if isinstance(attributes, dict):
        for value in attributes.values():
            attribute_terms.extend(_extract_tokens(value))
    elif isinstance(attributes, (list, tuple, set)):
        for value in attributes:
            attribute_terms.extend(_extract_tokens(value))

    terms.extend(_meaningful_terms(keyword_terms))
    terms.extend(_meaningful_terms(category_terms))
    terms.extend(_meaningful_terms(attribute_terms))
    return set(terms)


def _semantic_document(item):
    tokens = []
    name_tokens = _extract_tokens(item.get("name", ""))
    tokens.extend(name_tokens)
    tokens.extend(_extract_tokens(item.get("category", "")))

    for kw in item.get("keywords", []):
        tokens.extend(_extract_tokens(kw))

    attributes = item.get("attributes")
    if isinstance(attributes, dict):
        for key, value in attributes.items():
            tokens.extend(_extract_tokens(key))
            tokens.extend(_extract_tokens(value))
    elif isinstance(attributes, (list, tuple, set)):
        for value in attributes:
            tokens.extend(_extract_tokens(value))

    # Add expanded domain equivalents so semantic retrieval catches variants.
    tokens.extend(sorted(_expand_terms(_meaningful_terms(tokens))))
    return " ".join(tokens).strip()


def _safe_text(value):
    return " ".join(str(value or "").split()).strip()


def _safe_number(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    raw = str(value).strip()
    if not raw:
        return None
    if raw.isdigit():
        return int(raw)
    return raw


def _with_confidence(item, confidence):
    result = dict(item)
    result["_confidence"] = confidence
    return result


class ItemMatcher:
    def __init__(self, db):
        self.db = db
        self._name_index = {}    # Inverted index: word -> {item_id: item}
        self._last_index_signature = None
        self._semantic_embedder = None
        self._semantic_matrix = None
        self._semantic_item_ids = []

    def _compute_signature(self, items):
        """Create a lightweight signature so index refreshes when catalog content changes."""
        signature_parts = []
        for item in items:
            item_id = str(item.get("id", ""))
            name = str(item.get("name", "")).lower()
            category = str(item.get("category", "")).lower()
            attributes = tuple(
                sorted(
                    (str(k).lower(), str(v).lower())
                    for k, v in (item.get("attributes") or {}).items()
                )
            )
            keywords = tuple(sorted(str(k).lower() for k in (item.get("keywords") or [])))
            signature_parts.append((item_id, name, category, attributes, keywords))
        return tuple(signature_parts)

    def _build_semantic_index(self, items):
        semantic_docs = []
        semantic_item_ids = []

        for item in items:
            item_id = item.get("id")
            if item_id is None:
                continue
            doc = _semantic_document(item)
            if not doc:
                continue
            semantic_docs.append(doc)
            semantic_item_ids.append(item_id)

        if not semantic_docs:
            self._semantic_embedder = None
            self._semantic_matrix = None
            self._semantic_item_ids = []
            return

        try:
            LOG.info("[ML] Loading SentenceTransformer for product matching...")
            self._semantic_embedder = SentenceTransformer('all-MiniLM-L6-v2')
            self._semantic_matrix = self._semantic_embedder.encode(semantic_docs)
            self._semantic_item_ids = semantic_item_ids
        except Exception as e:
            LOG.error(f"[ML] Failed to build semantic index: {e}")
            self._semantic_embedder = None
            self._semantic_matrix = None
            self._semantic_item_ids = []

    def _extract_request_context(self, request_context):
        selected_id = None
        selected_name = ""
        visible_ids = set()
        context_terms = []

        if not isinstance(request_context, dict):
            return {
                "selected_id": selected_id,
                "selected_name": selected_name,
                "visible_ids": visible_ids,
                "context_terms": context_terms,
            }

        selected = request_context.get("selected_product")
        if isinstance(selected, dict):
            selected_id = _safe_number(selected.get("id") or selected.get("product_id"))
            selected_name = _safe_text(selected.get("name"))
            if selected_name:
                context_terms.extend(_extract_tokens(selected_name))

        visible_products = request_context.get("visible_products") or []
        if isinstance(visible_products, list):
            for product in visible_products[:40]:
                if not isinstance(product, dict):
                    continue
                visible_id = _safe_number(product.get("id") or product.get("product_id"))
                if visible_id is not None:
                    visible_ids.add(visible_id)
                product_name = _safe_text(product.get("name"))
                if product_name:
                    context_terms.extend(_extract_tokens(product_name))

        active_filters = request_context.get("active_filters") or {}
        if isinstance(active_filters, dict):
            for value in list(active_filters.values())[:20]:
                context_terms.extend(_extract_tokens(value))

        cart_snapshot = request_context.get("cart_snapshot") or []
        if isinstance(cart_snapshot, list):
            for item in cart_snapshot[:30]:
                if not isinstance(item, dict):
                    continue
                item_name = _safe_text(item.get("name"))
                if item_name:
                    context_terms.extend(_extract_tokens(item_name))

        return {
            "selected_id": selected_id,
            "selected_name": selected_name,
            "visible_ids": visible_ids,
            "context_terms": _meaningful_terms(context_terms),
        }

    def _semantic_candidates(self, text_terms, request_features, top_k=8):
        if self._semantic_embedder is None or self._semantic_matrix is None:
            return {}

        query_terms = list(text_terms)
        if len(query_terms) <= 2:
            query_terms.extend(request_features.get("context_terms", [])[:12])

        query = " ".join(query_terms).strip()
        if not query:
            return {}

        try:
            query_vector = self._semantic_embedder.encode([query])
            similarities = cosine_similarity(query_vector, self._semantic_matrix).ravel()
        except Exception:
            return {}
        ranked = sorted(enumerate(similarities), key=lambda row: row[1], reverse=True)

        candidates = {}
        for idx, score in ranked[:top_k]:
            if score <= 0:
                continue
            item_id = self._semantic_item_ids[idx]
            candidates[item_id] = float(score)
        return candidates

    def _build_index(self, items):
        """Build inverted keyword index for fast lookups."""
        signature = self._compute_signature(items)
        if signature == self._last_index_signature:
            return

        self._name_index = {}
        for item in items:
            item_id = item.get("id")
            if item_id is None:
                continue

            index_terms = set()
            name_terms = _meaningful_terms(_extract_tokens(item.get("name", "")))
            for term in _expand_terms(name_terms):
                if term not in STOP_WORDS and len(term) >= 3:
                    index_terms.add(term)

            # Also index keywords
            keyword_terms = []
            for kw in item.get("keywords", []):
                keyword_terms.extend(_extract_tokens(kw))
            for term in _expand_terms(_meaningful_terms(keyword_terms)):
                if term not in STOP_WORDS and len(term) >= 3:
                    index_terms.add(term)

            for term in index_terms:
                if term not in self._name_index:
                    self._name_index[term] = {}
                self._name_index[term][item_id] = item

        self._build_semantic_index(items)
        self._last_index_signature = signature

    def find(self, text, threshold=82, request_context=None):
        """
        Find best matching product. Multi-strategy:
        1. Exact name substring match (highest confidence)
        2. Indexed keyword match (fast O(1) lookup)
        3. Fuzzy match with higher threshold
        Returns the best match or None.
        """
        items = self.db.load()
        if not items:
            return None

        self._build_index(items)
        items_by_id = {item.get("id"): item for item in items}
        query_tokens = _extract_tokens(text)
        text_lower = " ".join(query_tokens)
        text_terms = _meaningful_terms(query_tokens)
        expanded_terms = _expand_terms(text_terms)
        request_features = self._extract_request_context(request_context)

        # If user refers to currently selected UI product ("this", "that", "it"), trust UI context first.
        if request_features["selected_id"] is not None and any(
            token in {"this", "that", "it", "same", "again"} for token in query_tokens
        ):
            selected_item = items_by_id.get(request_features["selected_id"])
            if selected_item is not None:
                return selected_item

        # 1. Exact name match (full name contained in text)
        for item in items:
            name_lower = _normalize_text(item.get("name", ""))
            if name_lower and name_lower in text_lower:
                return _with_confidence(item, 1.0)

        # 2. Multi-word name matching (at least 2 words match)
        # Pre-compute query materials for material-consistency filtering
        query_materials = {m for m in MATERIALS if m in text_lower.split()}

        best_keyword_item = None
        best_keyword_rank = (-1, -1.0)  # (material_match, score)
        for item in items:
            name_words = _meaningful_terms(_extract_tokens(item.get("name", "")))
            if not name_words:
                continue
            matches = 0
            direct_matches = 0
            for word in name_words:
                if word in text_terms:
                    matches += 1
                    direct_matches += 1
                    continue
                equivalents = TERM_EQUIVALENTS.get(word, {word})
                if any(term in expanded_terms for term in equivalents):
                    matches += 1

            if len(text_terms) > 1 and direct_matches == 0:
                continue
            score = matches / len(name_words)

            # Material consistency: prefer items whose NAME matches the requested material
            item_name_lower = _normalize_text(item.get("name", ""))
            mat_match = 1
            if query_materials:
                item_name_materials = {m for m in MATERIALS if m in item_name_lower.split()}
                mat_match = 1 if query_materials & item_name_materials else 0

            rank = (mat_match, score)
            if matches >= 2 and rank > best_keyword_rank:
                best_keyword_rank = rank
                best_keyword_item = item
            elif matches == 1 and len(name_words) == 1 and rank > best_keyword_rank:
                best_keyword_rank = rank
                best_keyword_item = item

        if best_keyword_item and best_keyword_rank[1] >= 0.5:
            return _with_confidence(best_keyword_item, float(best_keyword_rank[1]))

        # 3. Indexed keyword lookup
        text_words = sorted(expanded_terms)

        candidate_scores = {}
        for word in text_words:
            for item_id, item in self._name_index.get(word, {}).items():
                if item_id not in candidate_scores:
                    candidate_scores[item_id] = {"item": item, "hits": 0, "semantic": 0.0}
                candidate_scores[item_id]["hits"] += 1

        semantic_scores = self._semantic_candidates(text_terms, request_features, top_k=10)
        for item_id, score in semantic_scores.items():
            item = items_by_id.get(item_id)
            if item is None:
                continue
            if item_id not in candidate_scores:
                candidate_scores[item_id] = {"item": item, "hits": 0, "semantic": 0.0}
            candidate_scores[item_id]["semantic"] = max(candidate_scores[item_id]["semantic"], score)

        if candidate_scores:
            meaningful = " ".join(text_terms)
            best_item = None
            best_rank = (-1, -1, -1, -1, -1, -1)
            best_metrics = None
            for data in candidate_scores.values():
                item = data["item"]
                hits = data["hits"]
                semantic_score = float(data.get("semantic", 0.0))
                item_terms = _item_terms(item)
                direct_hits = sum(1 for term in text_terms if term in item_terms)
                name_lower = _normalize_text(item.get("name", ""))
                item_id = item.get("id")
                context_bonus = 0
                if item_id == request_features.get("selected_id"):
                    context_bonus += 2
                if item_id in request_features.get("visible_ids", set()):
                    context_bonus += 1
                if any(term in item_terms for term in request_features.get("context_terms", [])):
                    context_bonus += 1
                contains_bonus = 1 if any(w in name_lower for w in text_words) else 0
                fuzzy_score = max(
                    fuzz.token_sort_ratio(meaningful, name_lower) if meaningful else 0,
                    fuzz.token_set_ratio(meaningful, name_lower) if meaningful else 0,
                )
                # Material Consistency Check — use product NAME only
                query_materials = {m for m in MATERIALS if m in text_lower.split()}
                item_name_materials = {m for m in MATERIALS if m in name_lower.split()}
                material_match = 1
                if query_materials:
                    material_match = 1 if query_materials & item_name_materials else 0

                semantic_scaled = int(round(semantic_score * 1000))
                rank = (material_match, direct_hits, context_bonus, semantic_scaled, hits, contains_bonus, fuzzy_score)
                if rank > best_rank:
                    best_rank = rank
                    best_item = item
                    best_metrics = {
                        "direct_hits": direct_hits,
                        "context_bonus": context_bonus,
                        "semantic_score": semantic_score,
                        "fuzzy_score": fuzzy_score,
                        "material_match": material_match,
                    }

            if best_item:
                # Avoid over-matching multi-word requests using only loose synonym expansion.
                direct_hits = best_metrics["direct_hits"] if best_metrics else 0
                context_bonus = best_metrics["context_bonus"] if best_metrics else 0
                semantic_score = best_metrics["semantic_score"] if best_metrics else 0.0
                fuzzy_score = best_metrics["fuzzy_score"] if best_metrics else 0
                if len(text_terms) > 1 and direct_hits == 0 and context_bonus == 0:
                    if semantic_score >= 0.60 and fuzzy_score >= max(threshold, 85):
                        return _with_confidence(best_item, round(semantic_score, 2))
                elif (
                    direct_hits > 0
                    or context_bonus >= 2
                    or semantic_score >= 0.30
                    or len(text_terms) <= 1
                    or fuzzy_score >= max(threshold, 85)
                ):
                    final_conf = max(semantic_score, fuzzy_score / 100.0)
                    if best_metrics and best_metrics.get("material_match") == 0:
                        final_conf *= 0.4  # Massive penalty for material mismatch
                    return _with_confidence(best_item, round(final_conf, 2))

        # 4. Fuzzy match — higher threshold to avoid false positives
        item_names = [i["name"] for i in items]
        best_item, best_score = None, 0

        # Try matching meaningful multi-word phrase first
        meaningful = " ".join(text_terms)
        if meaningful:
            match_data = process.extractOne(
                meaningful, item_names, scorer=fuzz.token_set_ratio
            )
            if match_data:
                match, score = match_data
            else:
                match, score = None, 0
            if match and score >= threshold:
                best_score = score
                best_item = next(i for i in items if i["name"] == match)

        # Try individual words if phrase didn't match well
        if best_score < threshold:
            for word in text_terms:
                if len(word) < 4:
                    continue
                match_data = process.extractOne(
                    word, item_names, scorer=fuzz.token_set_ratio
                )
                if not match_data:
                    continue
                match, score = match_data
                if score > best_score and score >= threshold:
                    best_score = score
                    best_item = next(i for i in items if i["name"] == match)

        if best_item:
            # Apply material penalty to fuzzy matches too
            if query_materials:
                bi_name = _normalize_text(best_item.get("name", ""))
                bi_name_materials = {m for m in MATERIALS if m in bi_name.split()}
                if not (query_materials & bi_name_materials):
                    best_score *= 0.4  # Heavy penalty
            if best_score >= threshold:
                return _with_confidence(best_item, round(best_score / 100.0, 2))

        return None

    def find_top_n(self, text, n=3, threshold=60):
        """
        Return top N matching products with scores.
        Useful for disambiguation ("Did you mean...?")
        """
        items = self.db.load()
        if not items:
            return []

        text_words = _meaningful_terms(_extract_tokens(text))
        meaningful = " ".join(text_words)
        if not meaningful:
            return []

        item_names = [i["name"] for i in items]
        results = process.extract(
            meaningful, item_names, scorer=fuzz.token_set_ratio, limit=n
        )

        matches = []
        for name, score in results:
            if score >= threshold:
                item = next(i for i in items if i["name"] == name)
                matches.append({"item": item, "score": score})

        return matches

    def search(self, query, limit=10, threshold=50):
        """
        Search products by query. More lenient than find() — used for SEARCH intent.
        Returns list of matching items.
        """
        items = self.db.load()
        if not items:
            return []

        query_tokens = _extract_tokens(query)
        query_lower = " ".join(query_tokens)
        results = []

        # Exact/partial name match
        for item in items:
            name_lower = _normalize_text(item.get("name", ""))
            if query_lower in name_lower or name_lower in query_lower:
                results.append({"item": item, "score": 100})

        # Keyword match
        query_words = sorted(_expand_terms(_meaningful_terms(query_tokens)))
        for item in items:
            if any(r["item"]["id"] == item["id"] for r in results):
                continue
            name_lower = _normalize_text(item.get("name", ""))
            for word in query_words:
                if word in name_lower:
                    results.append({"item": item, "score": 85})
                    break

        # Fuzzy match for remaining
        if len(results) < limit and query_words:
            item_names = [i["name"] for i in items]
            fuzzy_results = process.extract(
                " ".join(query_words), item_names,
                scorer=fuzz.token_set_ratio, limit=limit
            )
            existing_ids = {r["item"]["id"] for r in results}
            for name, score in fuzzy_results:
                if score >= threshold:
                    item = next(i for i in items if i["name"] == name)
                    if item["id"] not in existing_ids:
                        results.append({"item": item, "score": score})

        # Sort by score, limit
        results.sort(key=lambda r: r["score"], reverse=True)
        return [r["item"] for r in results[:limit]]