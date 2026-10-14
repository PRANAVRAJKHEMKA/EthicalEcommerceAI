"""Engine A — Content-Based Recommendation Engine

Responsibilities:
- Evaluate active cart contents against the authoritative SQLite catalog.
- Filter out items already in the cart and out-of-stock items.
- Score candidate items using explicit complementary tags, category compatibility, and basket price ratios.
- Return the highest-affinity candidate with an explainable factual rationale.

Note on Heuristics:
Affinity scores are deterministic, explainable measures of product compatibility
derived from catalogue relationships. They are NOT calibrated purchase probabilities.
"""

from dataclasses import dataclass
from backend.app.db.repository import ProductEntity

@dataclass(frozen=True)
class RecommendationCandidate:
    product: ProductEntity
    affinity_score: float
    compatibility_reason: str

# Category compatibility weights (accessory/complement affinity)
CATEGORY_AFFINITY_MATRIX = {
    ("Keyboards", "Accessories"): 0.30,
    ("Keyboards", "Workspace"): 0.25,
    ("Keyboards", "Mice"): 0.20,
    ("Mice", "Accessories"): 0.30,
    ("Mice", "Workspace"): 0.25,
    ("Audio & Video", "Accessories"): 0.30,
    ("Audio & Video", "Power & Cables"): 0.25,
    ("Workspace", "Accessories"): 0.25,
    ("Workspace", "Power & Cables"): 0.20,
}

class RecommenderEngine:
    """Engine A: Deterministic content-based recommender."""

    def find_recommendation(
        self,
        cart_items: list[tuple[ProductEntity, int]],
        catalog: list[ProductEntity],
    ) -> RecommendationCandidate | None:
        """Finds the most relevant in-stock complementary product for the current basket.
        
        Args:
            cart_items: List of (ProductEntity, quantity) tuples currently in cart.
            catalog: Full catalog of available ProductEntity items.
            
        Returns:
            RecommendationCandidate or None if no valid candidate exists.
        """
        if not cart_items or not catalog:
            return None

        cart_product_ids = {item[0].id for item in cart_items}
        cart_subtotal_cents = sum(item[0].reference_price_cents * item[1] for item in cart_items)

        best_candidate: ProductEntity | None = None
        best_score = -1.0
        best_reason = ""

        for candidate in catalog:
            # Rule 1: Never recommend an item already in the cart
            if candidate.id in cart_product_ids:
                continue

            # Rule 2: Never recommend an out-of-stock item
            if candidate.inventory <= 0:
                continue

            score = 0.10  # Baseline catalog visibility score
            primary_reason = ""
            matched_direct = False

            # Rule 3: Direct complementary link check
            for parent, _ in cart_items:
                if candidate.id in parent.complementary_ids:
                    score += 0.50
                    primary_reason = f"Ergonomically aligned companion for {parent.name}."
                    matched_direct = True
                    break
                elif parent.id in candidate.complementary_ids:
                    score += 0.40
                    primary_reason = f"Designed to complement {parent.name} in your setup."
                    matched_direct = True
                    break

            # Rule 4: Category affinity scoring
            if not matched_direct:
                for parent, _ in cart_items:
                    pair = (parent.category, candidate.category)
                    rev_pair = (candidate.category, parent.category)
                    cat_boost = CATEGORY_AFFINITY_MATRIX.get(pair) or CATEGORY_AFFINITY_MATRIX.get(rev_pair)

                    if cat_boost:
                        score += cat_boost
                        primary_reason = f"{candidate.category} tool frequently paired with {parent.category}."
                        break
                    elif parent.category == candidate.category:
                        # Penalty for recommending duplicate category (e.g. second keyboard)
                        score -= 0.25

            # Rule 5: Price proportionality check (accessories between 10% and 50% of basket)
            if cart_subtotal_cents > 0:
                price_ratio = candidate.reference_price_cents / cart_subtotal_cents
                if 0.10 <= price_ratio <= 0.50:
                    score += 0.10

            # Rule 6: Inventory health boost
            if candidate.inventory >= 20:
                score += 0.05

            # Clamp score to [0.05, 0.98] and round to 2 decimals
            normalized_score = round(min(max(score, 0.05), 0.98), 2)

            if normalized_score > best_score:
                best_score = normalized_score
                best_candidate = candidate
                best_reason = primary_reason or f"Curated productivity accessory for your cart."

        if not best_candidate or best_score < 0.15:
            return None

        return RecommendationCandidate(
            product=best_candidate,
            affinity_score=best_score,
            compatibility_reason=best_reason,
        )
