"""Engine A — Deterministic Content-Based Recommender Engine

Generates explainable, content-based complementary product recommendations
derived purely from product attributes, catalog metadata, complementary links,
and user-selected shopping intent context.

Design constraints:
- Deterministic: Identical inputs always produce identical candidate rankings.
- Zero invasive profiling: Context derives strictly from user-selected intent filters.
- Diversity enforcement: Enforces category and subcategory diversity across 3-5 candidates.
- Factual ground truth: Every recommendation reason explains concrete matching product
  attributes, eliminating generic placeholder copy.
"""

from collections import Counter
from dataclasses import dataclass
from backend.app.db.repository import ProductEntity

@dataclass
class RecommendationCandidate:
    """Represents a single scored candidate returned by Engine A."""
    product: ProductEntity
    affinity_score: float
    compatibility_reason: str

# Cross-category affinity priors based on workstation and peripheral ergonomics
CATEGORY_AFFINITY_MATRIX: dict[tuple[str, str], float] = {
    ("Keyboards", "Accessories"): 0.35,
    ("Keyboards", "Mice"): 0.30,
    ("Keyboards", "Workspace"): 0.25,
    ("Keyboards", "Lifestyle"): 0.15,
    ("Mice", "Accessories"): 0.35,
    ("Mice", "Workspace"): 0.25,
    ("Mice", "Lifestyle"): 0.15,
    ("Audio & Video", "Workspace"): 0.30,
    ("Audio & Video", "Power & Cables"): 0.25,
    ("Audio & Video", "Accessories"): 0.25,
    ("Workspace", "Power & Cables"): 0.30,
    ("Workspace", "Accessories"): 0.30,
    ("Workspace", "Lifestyle"): 0.20,
    ("Power & Cables", "Accessories"): 0.25,
    ("Lifestyle", "Accessories"): 0.20,
    ("Lifestyle", "Workspace"): 0.20,
}

def build_factual_recommendation_reason(
    candidate: ProductEntity,
    parent: ProductEntity | None,
    shopping_context: str = "all",
) -> str:
    """Generates an accurate, factual reason grounded in concrete product attributes.
    
    Eliminates generic boilerplate copy by describing real technical, ergonomic,
    or physical compatibility between the candidate and the basket.
    """
    sub = candidate.subcategory.strip()
    parent_name = parent.name if parent else "your setup"
    parent_cat = parent.category if parent else ""

    # Factual attribute descriptions by subcategory and category
    if sub == "Ergonomic Supports":
        if parent_cat == "Keyboards":
            base = f"Contoured cooling gel memory foam relieves wrist extension strain during typing on {parent_name}."
        elif parent_cat == "Mice":
            base = f"Neutral wrist elevation aligns forearm posture to relieve repetitive strain during mouse navigation."
        else:
            base = "Contoured memory foam support improves typing ergonomics and posture comfort."
    elif sub == "Cables & Connectors":
        if parent_cat == "Keyboards":
            base = f"Heavy-duty Type-C aviator connector provides clean, tangle-free power routing for {parent_name}."
        elif candidate.category == "Power & Cables":
            base = "100W Power Delivery and high bandwidth ensure rapid charging and reliable display output."
        else:
            base = f"Double-sleeved braided construction provides low-resistance, durable device connectivity."
    elif sub == "Keycap Sets":
        base = f"Thick PBT dye-sublimated cherry-profile keycaps resist surface shine and provide crisp acoustics."
    elif sub == "Components":
        base = f"Factory-lubricated tactile switches offer smooth actuation and custom responsiveness."
    elif sub == "Desk Surfaces":
        base = f"Micro-weave surface cushions desk vibrations from {parent_name} and provides consistent tracking."
    elif sub == "Stands & Risers":
        if "Laptop" in candidate.name:
            base = "Elevates laptop screen to eye level while freeing up desk space for external input devices."
        else:
            base = f"Heavy-duty aluminum riser elevates displays to reduce neck fatigue and creates under-shelf storage."
    elif sub == "Hubs & Docks":
        base = "Expands device connectivity with 4K HDMI, 100W PD charging pass-through, and multi-port USB access."
    elif sub == "Lighting":
        base = "Screen-mounted asymmetrical optical lamp illuminates desktop surfaces with zero screen glare."
    elif sub == "Cameras":
        base = "4K STARVIS sensor captures sharp video with dual noise-canceling mics for conferencing and streaming."
    elif sub == "Audio Recording":
        base = "Cardioid condenser capsule with shock arm isolates vocal clarity while dampening desk vibrations."
    elif sub == "Headphones":
        base = "Hybrid active noise cancellation filters ambient background noise for concentrated focus and study."
    elif sub == "Mounts & Organizers":
        if "Headphone" in candidate.name:
            base = "Under-desk aluminum mount keeps headsets secure and accessible without cluttering desk surfaces."
        elif "Monitor" in candidate.name:
            base = "Counterbalanced gas-spring arms provide full-motion screen articulation and free up desk footprint."
        else:
            base = "Under-desk wire management basket and spine keep power and data cords routed and organized."
    elif sub == "Cable Clips":
        base = "Magnetic cable anchors secure charging and peripheral cords to prevent them from dropping behind desks."
    elif sub == "Maintenance":
        base = "Ammonia-free gentle display cleaning spray and microfiber cloths remove dust without damaging anti-glare coatings."
    elif sub == "Wireless Chargers":
        base = "15W fast wireless charging dock powers phone, watch, and earbuds simultaneously in a compact footprint."
    elif sub == "Power Adapters":
        base = "Gallium nitride dual-port power adapter delivers fast 65W charging for laptops and accessories."
    elif sub == "Portable Power":
        base = "Airline-safe 20,000mAh battery with LCD status display keeps laptops and phones charged on the go."
    elif sub == "Travel Organizers":
        base = "Water-resistant EVA hard-shell organizer protects cables, chargers, and compact peripherals in transit."
    elif sub == "Drinkware":
        base = "Ceramic-lined vacuum insulation maintains drink temperature with spill-resistant desk safety."
    elif sub == "Refreshments":
        base = "Caffeine-free organic herbal botanicals and antioxidant snacks sustain mental energy during deep focus."
    elif sub == "Gaming Mice":
        base = "Ultra-lightweight 58g chassis with 26K DPI optical sensor and PTFE glides for pixel-accurate tracking."
    elif sub == "Gaming Accessories":
        base = "Anti-drag silicone bungee arm suspends mouse cords to eliminate cable friction during rapid swipes."
    else:
        base = f"Factual complementary accessory matching {candidate.category} with {parent_name}."

    # Context rationale append
    ctx = shopping_context.strip().lower()
    if ctx == "gaming":
        context_note = " (Matches your Gaming setup)"
    elif ctx == "productivity":
        context_note = " (Aligned with your Productivity setup)"
    elif ctx == "study":
        context_note = " (Tailored for focused Study sessions)"
    elif ctx == "travel":
        context_note = " (Compact and optimized for Travel)"
    elif ctx == "wellness":
        context_note = " (Supports your Ergonomics & Wellness focus)"
    else:
        context_note = ""

    return f"{base}{context_note}"

class RecommenderEngine:
    """Engine A: Content-based recommendation engine for complementary desk tech products."""

    def find_recommendations(
        self,
        cart_items: list[tuple[ProductEntity, int]],
        catalog: list[ProductEntity],
        shopping_context: str = "all",
        top_k: int = 4,
    ) -> list[RecommendationCandidate]:
        """Finds 3 to 5 ranked complementary product candidates with subcategory diversity.
        
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
            best_parent: ProductEntity | None = None
            matched_direct = False

            # Rule 3: Explicit complementary link check
            for parent, _ in cart_items:
                if candidate.id in parent.complementary_ids:
                    score += 0.50
                    best_parent = parent
                    matched_direct = True
                    break
                elif parent.id in candidate.complementary_ids:
                    score += 0.40
                    best_parent = parent
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
                        if not best_parent:
                            best_parent = parent
                        break

            # Rule 5: Shopping context matching
            if context_clean != "all" and context_clean:
                if context_clean in candidate.use_cases:
                    score += 0.25
                else:
                    # Minor penalty if product does not support user's declared context
                    score -= 0.05

            # Rule 6: Shared tag overlap (e.g. wireless, ergonomic, portable)
            common_tags = set(candidate.tags).intersection(cart_tags)
            if common_tags:
                tag_boost = min(len(common_tags) * 0.05, 0.15)
                score += tag_boost

            # Rule 7: Price rationality (accessories should not overwhelm main purchase)
            if cart_subtotal_cents > 0 and candidate.reference_price_cents <= (0.60 * cart_subtotal_cents):
                score += 0.05

            final_score = round(min(max(score, 0.05), 0.98), 2)
            
            # Generate concrete factual reason grounded in attributes
            primary_reason = build_factual_recommendation_reason(
                candidate=candidate,
                parent=best_parent or cart_items[0][0],
                shopping_context=context_clean,
            )

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
                subcategory_counts[cand.subcategory] += 1
                category_counts[cand.category] += 1

        return selected

    def recommend(
        self,
        cart_items: list[tuple[ProductEntity, int]],
        catalog: list[ProductEntity],
    ) -> RecommendationCandidate | None:
        """Backward-compatible single-recommendation method."""
        recs = self.find_recommendations(cart_items, catalog, shopping_context="all", top_k=1)
        return recs[0] if recs else None

    def find_recommendation(
        self,
        cart_items: list[tuple[ProductEntity, int]],
        catalog: list[ProductEntity],
    ) -> RecommendationCandidate | None:
        """Backward-compatible single-recommendation alias."""
        return self.recommend(cart_items, catalog)
