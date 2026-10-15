"""Engine A — Generalized Context-Aware Recommendation Engine

Responsibilities:
- Evaluate active cart contents against the authoritative SQLite catalog.
- Support multi-candidate ranking returning 3-5 relevant recommendations.
- Filter out items already in the cart and out-of-stock items.
- Score candidates using direct complementary links, category affinity, shopping context,
  tag overlap, and price rationality.
- Enforce catalog diversity so recommendations span distinct functional roles.
- Generate factual, explainable compatibility rationales for each candidate.

Machine Learning & Baseline Disclosure:
This implementation utilizes a deterministic, feature-weighted metadata ranking baseline.
It generalizes across shared product attributes, subcategories, context tags, and compatibility
matrixes without requiring manual pairwise enumeration. It does NOT claim to be a model
trained on user click/purchase telemetry.
"""

from collections import Counter
from dataclasses import dataclass
from backend.app.db.repository import ProductEntity

@dataclass(frozen=True)
class RecommendationCandidate:
    product: ProductEntity
    affinity_score: float
    compatibility_reason: str

# Generalized cross-category affinity matrix
CATEGORY_AFFINITY_MATRIX = {
    ("Keyboards", "Accessories"): 0.20,
    ("Keyboards", "Workspace"): 0.15,
    ("Keyboards", "Mice"): 0.15,
    ("Keyboards", "Lifestyle"): 0.15,
    ("Mice", "Accessories"): 0.20,
    ("Mice", "Workspace"): 0.15,
    ("Mice", "Lifestyle"): 0.15,
    ("Workspace", "Accessories"): 0.20,
    ("Workspace", "Power & Cables"): 0.20,
    ("Workspace", "Lifestyle"): 0.15,
    ("Audio & Video", "Accessories"): 0.20,
    ("Audio & Video", "Power & Cables"): 0.15,
    ("Audio & Video", "Lifestyle"): 0.15,
    ("Power & Cables", "Accessories"): 0.15,
    ("Lifestyle", "Workspace"): 0.15,
    ("Lifestyle", "Accessories"): 0.15,
}

class RecommenderEngine:
    """Engine A: Generalized context-aware content recommender."""

    def find_recommendations(
        self,
        cart_items: list[tuple[ProductEntity, int]],
        catalog: list[ProductEntity],
        shopping_context: str = "all",
        top_k: int = 4,
    ) -> list[RecommendationCandidate]:
        """Finds multiple relevant, diverse in-stock complementary products for the basket.
        
        Args:
            cart_items: List of (ProductEntity, quantity) tuples currently in cart.
            catalog: Full list of available ProductEntity catalog items.
            shopping_context: Active shopping intent ('all', 'productivity', 'gaming', 'study', 'travel', etc.).
            top_k: Number of ranked recommendations to return (default 4, within [3, 5]).
            
        Returns:
            List of RecommendationCandidate ranked by affinity score with diversity applied.
        """
        if not cart_items or not catalog:
            return []

        cart_product_ids = {item[0].id for item in cart_items}
        cart_subtotal_cents = sum(item[0].reference_price_cents * item[1] for item in cart_items)
        
        # Aggregate tags and categories present in cart
        cart_tags = set()
        for item, _ in cart_items:
            cart_tags.update(item.tags)

        scored_candidates: list[tuple[ProductEntity, float, str]] = []

        context_clean = shopping_context.strip().lower()

        for candidate in catalog:
            # Rule 1: Never recommend an item already in the cart
            if candidate.id in cart_product_ids:
                continue

            # Rule 2: Never recommend an out-of-stock item
            if candidate.inventory <= 0:
                continue

            score = 0.10  # Baseline catalog visibility
            reasons: list[str] = []
            matched_direct = False

            # Rule 3: Explicit complementary link check
            for parent, _ in cart_items:
                if candidate.id in parent.complementary_ids:
                    score += 0.50
                    reasons.append(f"Ergonomically aligned companion for {parent.name}")
                    matched_direct = True
                    break
                elif parent.id in candidate.complementary_ids:
                    score += 0.40
                    reasons.append(f"Designed to complement {parent.name} in your setup")
                    matched_direct = True
                    break

            # Rule 4: Cross-category affinity scoring
            if not matched_direct:
                for parent, _ in cart_items:
                    pair = (parent.category, candidate.category)
                    rev_pair = (candidate.category, parent.category)
                    boost = CATEGORY_AFFINITY_MATRIX.get(pair) or CATEGORY_AFFINITY_MATRIX.get(rev_pair)
                    if boost:
                        score += boost
                        reasons.append(f"{candidate.category} item frequently paired with {parent.category}")
                        break

            # Rule 5: Shopping context matching
            if context_clean != "all" and context_clean:
                if context_clean in candidate.use_cases:
                    score += 0.25
                    reasons.append(f"Tailored for your {context_clean.capitalize()} workflow")
                else:
                    # Minor penalty if product does not support user's declared context
                    score -= 0.05

            # Rule 6: Shared tag overlap (e.g. wireless, ergonomic, portable)
            common_tags = set(candidate.tags).intersection(cart_tags)
            if common_tags:
                tag_boost = min(len(common_tags) * 0.05, 0.15)
                score += tag_boost
                sample_tag = next(iter(common_tags))
                if not reasons:
                    reasons.append(f"Shares '{sample_tag}' workflow attributes with your cart")

            # Rule 7: Price rationality (accessories should not overwhelm main purchase)
            if cart_subtotal_cents > 0 and candidate.reference_price_cents <= (0.60 * cart_subtotal_cents):
                score += 0.05

            final_score = round(min(max(score, 0.05), 0.98), 2)
            primary_reason = ". ".join(reasons[:2]) + "." if reasons else "Compatible productivity companion."
            scored_candidates.append((candidate, final_score, primary_reason))

        # Sort descending by score
        scored_candidates.sort(key=lambda x: x[1], reverse=True)

        # Rule 8: Diversity enforcement across categories & subcategories
        selected: list[RecommendationCandidate] = []
        subcategory_counts = Counter()
        category_counts = Counter()

        # First pass: pick best candidate per subcategory/category
        for cand, score, reason in scored_candidates:
            if len(selected) >= top_k:
                break
            
            # If we already have 2 items from the same category or 1 from the exact same subcategory, defer
            if subcategory_counts[cand.subcategory] >= 1 or category_counts[cand.category] >= 2:
                continue

            selected.append(RecommendationCandidate(
                product=cand,
                affinity_score=score,
                compatibility_reason=reason,
            ))
            subcategory_counts[cand.subcategory] += 1
            category_counts[cand.category] += 1

        # Second pass: fill remaining slots if top_k not reached
        if len(selected) < top_k:
            for cand, score, reason in scored_candidates:
                if len(selected) >= top_k:
                    break
                if any(s.product.id == cand.id for s in selected):
                    continue
                selected.append(RecommendationCandidate(
                    product=cand,
                    affinity_score=score,
                    compatibility_reason=reason,
                ))

        return selected

    def find_recommendation(
        self,
        cart_items: list[tuple[ProductEntity, int]],
        catalog: list[ProductEntity],
        shopping_context: str = "all",
    ) -> RecommendationCandidate | None:
        """Convenience method returning the single highest ranked recommendation."""
        results = self.find_recommendations(cart_items, catalog, shopping_context=shopping_context, top_k=1)
        return results[0] if results else None
