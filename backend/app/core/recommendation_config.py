"""
Configurable recommendation scoring weights.
Editing these values changes recommendation ranking behaviour everywhere
without touching engine code. Weights should sum to 1.0.
"""

RECOMMENDATION_WEIGHTS = {
    "visual_similarity": 0.40,
    "category_match": 0.15,
    "color_match": 0.10,
    "style_match": 0.15,
    "pattern_match": 0.05,
    "budget_compatibility": 0.10,
    "user_preference": 0.05,
}

CLOTHING_CATEGORIES = [
    "T-Shirt",
    "Shirt",
    "Jeans",
    "Trousers",
    "Dress",
    "Skirt",
    "Shorts",
    "Jacket",
    "Hoodie",
    "Sweater",
    "Kurta",
    "Saree",
    "Shoes",
    "Sneakers",
    "Other",
]

STYLE_TAGS = [
    "Casual",
    "Formal",
    "Streetwear",
    "Party",
    "Traditional",
    "Minimal",
    "Sporty",
    "Vintage",
]
