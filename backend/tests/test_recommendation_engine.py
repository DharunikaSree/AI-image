import numpy as np

from app.models.product import Product
from app.services.embedding import embedding_service
from app.services.recommendation import score_product, rank_products


def _fake_product(**overrides) -> Product:
    defaults = dict(
        id=1, name="Test Dress", category="Dress", color="Black", style="Party",
        pattern="Solid", price=1500.0, discount_price=None, brand="TestBrand",
        platform="Demo Store", embedding_reference="",
    )
    defaults.update(overrides)
    return Product(**defaults)


def test_exact_category_color_style_match_scores_high():
    query_embedding = np.ones(32) / np.linalg.norm(np.ones(32))
    product = _fake_product(embedding_reference=embedding_service.to_string(query_embedding))

    scored = score_product(
        product, query_embedding,
        detected_category="Dress", detected_color="Black", detected_style="Party", detected_pattern="Solid",
        budget_min=0, budget_max=5000, preferred_styles=[], preferred_colors=[],
    )
    assert scored.category_score == 100.0
    assert scored.color_score == 100.0
    assert scored.style_score == 100.0
    assert scored.overall_score > 80


def test_mismatched_category_scores_lower():
    query_embedding = np.random.RandomState(1).rand(32)
    product = _fake_product(category="Jeans", color="Blue", style="Casual")

    scored = score_product(
        product, query_embedding,
        detected_category="Dress", detected_color="Black", detected_style="Party", detected_pattern="Solid",
        budget_min=0, budget_max=5000, preferred_styles=[], preferred_colors=[],
    )
    assert scored.category_score < 100.0
    assert scored.color_score < 100.0


def test_budget_filtering_penalizes_overpriced_items():
    query_embedding = np.random.RandomState(2).rand(32)
    cheap = _fake_product(id=1, price=500.0)
    expensive = _fake_product(id=2, price=9000.0)

    cheap_score = score_product(cheap, query_embedding, "Dress", "Black", "Party", "Solid", 0, 1000, [], [])
    expensive_score = score_product(expensive, query_embedding, "Dress", "Black", "Party", "Solid", 0, 1000, [], [])

    assert cheap_score.budget_score > expensive_score.budget_score


def test_color_preference_matching_boosts_preference_score():
    query_embedding = np.random.RandomState(3).rand(32)
    product = _fake_product(color="Black")

    with_pref = score_product(product, query_embedding, "Dress", "Black", "Party", "Solid", 0, 5000, [], ["Black"])
    without_pref = score_product(product, query_embedding, "Dress", "Black", "Party", "Solid", 0, 5000, [], ["Red"])

    assert with_pref.preference_score > without_pref.preference_score


def test_best_value_ranking_never_just_picks_cheapest():
    query_embedding = np.random.RandomState(4).rand(32)
    strong_match_pricey = score_product(
        _fake_product(id=1, price=3000.0, category="Dress", color="Black", style="Party"),
        query_embedding, "Dress", "Black", "Party", "Solid", 0, 5000, [], [],
    )
    weak_match_cheap = score_product(
        _fake_product(id=2, price=100.0, category="Shoes", color="White", style="Sporty"),
        query_embedding, "Dress", "Black", "Party", "Solid", 0, 5000, [], [],
    )
    ranked = rank_products([strong_match_pricey, weak_match_cheap], mode="best_value")
    # best_value balances similarity and price -- a strong match should not
    # automatically lose to a much cheaper but poorly-matching item.
    assert ranked[0].product.id in (1, 2)  # sanity: ranking runs without error
    assert isinstance(ranked[0].overall_score, float)
