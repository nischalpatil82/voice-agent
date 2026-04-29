from core.matcher import ItemMatcher


class _MutableDB:
    def __init__(self, items):
        self.items = items

    def load(self):
        return list(self.items)


def test_matcher_rebuilds_index_when_catalog_changes_same_size():
    db = _MutableDB(
        [
            {"id": 1, "name": "Product Alpha", "price": 10, "keywords": ["emerald"]},
            {"id": 2, "name": "Product Beta", "price": 20, "keywords": ["ruby"]},
        ]
    )
    matcher = ItemMatcher(db)

    first = matcher.find("show ruby options")
    assert first is not None
    assert first["id"] == 2

    # Same item count, but keyword content changes.
    db.items = [
        {"id": 1, "name": "Product Alpha", "price": 10, "keywords": ["emerald"]},
        {"id": 2, "name": "Product Beta", "price": 20, "keywords": ["sapphire"]},
    ]

    second = matcher.find("show sapphire options")
    assert second is not None
    assert second["id"] == 2


def test_matcher_ranks_keyword_candidates_not_first_hit_only():
    db = _MutableDB(
        [
            {"id": 11, "name": "Product One", "price": 50, "keywords": ["ring"]},
            {"id": 22, "name": "Product Two", "price": 60, "keywords": ["ring", "diamond"]},
        ]
    )
    matcher = ItemMatcher(db)

    item = matcher.find("ring for diamond")
    assert item is not None
    assert item["id"] == 22


def test_matcher_supports_mangalsutra_compound_word():
    db = _MutableDB(
        [
            {"id": 7, "name": "Mangala Sutra 22K", "price": 200000, "keywords": ["bridal"]},
            {"id": 8, "name": "Diamond Ring", "price": 90000, "keywords": ["diamond", "ring"]},
        ]
    )
    matcher = ItemMatcher(db)

    item = matcher.find("add mangalsutra to cart")
    assert item is not None
    assert item["id"] == 7


def test_matcher_avoids_multiterm_synonym_overmatch_without_direct_overlap():
    db = _MutableDB(
        [
            {"id": 31, "name": "Premium Bracelet 22K", "price": 180000, "keywords": ["signature"]},
            {"id": 32, "name": "Classic Necklace", "price": 95000, "keywords": ["chain"]},
        ]
    )
    matcher = ItemMatcher(db)

    item = matcher.find("add a luxury bangle to cart")
    assert item is None


def test_matcher_multiterm_synonym_match_when_direct_term_exists():
    db = _MutableDB(
        [
            {"id": 41, "name": "Luxury Bracelet 22K", "price": 180000, "keywords": ["signature"]},
            {"id": 42, "name": "Classic Necklace", "price": 95000, "keywords": ["chain"]},
        ]
    )
    matcher = ItemMatcher(db)

    item = matcher.find("add a luxury bangle to cart")
    assert item is not None
    assert item["id"] == 41


def test_matcher_uses_category_and_attributes_for_semantic_match():
    db = _MutableDB(
        [
            {
                "id": 51,
                "name": "Aurelia Signature Set",
                "price": 210000,
                "keywords": ["aurelia"],
                "category": "bridal jewellery",
                "attributes": {"metal": "gold", "style": "kada"},
            },
            {
                "id": 52,
                "name": "Classic Office Necklace",
                "price": 87000,
                "keywords": ["office"],
                "category": "daily wear",
                "attributes": {"metal": "silver"},
            },
        ]
    )
    matcher = ItemMatcher(db)

    item = matcher.find("show bridal gold kada options")
    assert item is not None
    assert item["id"] == 51


def test_matcher_prefers_selected_product_for_reference_query():
    db = _MutableDB(
        [
            {"id": 61, "name": "Diamond Ring", "price": 130000, "keywords": ["diamond", "ring"]},
            {"id": 62, "name": "Classic Necklace", "price": 78000, "keywords": ["necklace"]},
        ]
    )
    matcher = ItemMatcher(db)

    item = matcher.find(
        "add this to cart",
        request_context={"selected_product": {"id": 62, "name": "Classic Necklace"}},
    )
    assert item is not None
    assert item["id"] == 62
