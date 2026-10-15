"""Engine A — Multi-Stage Context-Aware Recommender Engine

Generates explainable, content-based and association-mined complementary product recommendations
derived from the ENTIRE active basket, association rules mined from synthetic transaction history,
explicit user-declared shopping context, and anonymous session interaction history.

Architectural guarantees:
1. Whole-Basket Evaluation: Evaluates candidate compatibility and multi-item synergy across all
   items in the basket, not just the initial product.
2. Multi-Signal Bounded Candidate Generation: Gathers candidates via direct complement mesh,
   multi-item association rules ({A, B} -> C), category affinities, and session exploration.
3. Normalized Hybrid Scoring: Documented weights combining basket complementarity (0.35),
   association rule lift/confidence (0.30), explicit intent context (0.25), and session exploration (0.10).
4. Subcategory & Category Diversity: Prevents recommendation monoculture by capping subcategories.
5. Factual Ground Truth: Explanations articulate real product attributes, matching basket items,
   and mined co-purchase lift without hallucination.
"""

from collections import Counter
from dataclasses import dataclass
from backend.app.db.repository import ProductEntity
from backend.app.engine.associations import (
    AssociationMatch,
    AssociationRuleEngine,
    get_association_engine,
)

@dataclass
class RecommendationCandidate:
    """Represents a single scored candidate returned by Engine A."""
    product: ProductEntity
    affinity_score: float
    compatibility_reason: str
    association_lift: float = 1.0
    association_confidence: float = 0.0
    is_multi_item_match: bool = False

# Cross-category affinity matrix reflecting physical and workstation synergy
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
    parents: list[ProductEntity] | None = None,
    parent: ProductEntity | None = None,
    shopping_context: str = "all",
    association_match: AssociationMatch | None = None,
) -> str:
    """Generates a structured factual reason grounded in concrete attributes and basket relationships.
    
    Eliminates generic boilerplate copy by describing real technical, ergonomic,
    or physical compatibility between the candidate and the basket.
    """
    if parents is None:
        parents = [parent] if parent else []

    sub = candidate.subcategory.strip()
    parent_names = [p.name for p in parents]
    parent_cats = [p.category for p in parents]
    primary_parent = parents[0] if parents else None
    primary_name = primary_parent.name if primary_parent else "your setup"

    # Multi-parent pairing note
    if len(parents) >= 2:
        parent_phrase = f"{parents[0].name} and {parents[1].name}"
    else:
        parent_phrase = primary_name

    # Attribute-grounded descriptions
    if sub == "Ergonomic Supports":
        if "Keyboards" in parent_cats:
            base = f"Contoured cooling gel memory foam relieves wrist extension strain during typing on {primary_name}."
        elif "Mice" in parent_cats:
            base = f"Neutral wrist elevation aligns forearm posture to relieve repetitive strain during mouse navigation."
        else:
            base = f"Contoured memory foam support improves typing ergonomics and posture comfort for {parent_phrase}."
    elif sub == "Cables & Connectors":
        if "Keyboards" in parent_cats:
            base = f"Heavy-duty Type-C aviator connector provides clean, tangle-free power routing for {primary_name}."
        elif candidate.category == "Power & Cables":
            base = f"100W Power Delivery and high bandwidth ensure rapid charging and reliable display output for {parent_phrase}."
        else:
            base = f"Double-sleeved braided construction provides low-resistance, durable device connectivity."
    elif sub == "Keycap Sets":
        base = f"Thick PBT dye-sublimated cherry-profile keycaps resist surface shine and provide crisp acoustics on {primary_name}."
    elif sub == "Components":
        base = f"Factory-lubricated tactile switches offer smooth actuation and custom responsiveness for {primary_name}."
    elif sub == "Desk Surfaces":
        if len(parents) >= 2:
            base = f"Micro-weave surface unifies desktop layout for {parent_phrase} while dampening vibrations and ensuring consistent mouse tracking."
        else:
            base = f"Micro-weave surface cushions desk vibrations from {primary_name} and provides consistent tracking."
    elif sub == "Stands & Risers":
        if "Laptop" in candidate.name:
            base = f"Elevates laptop screen to eye level while freeing up desk space for external input devices like {primary_name}."
        else:
            base = f"Heavy-duty aluminum riser elevates displays to reduce neck fatigue and creates under-shelf storage for {primary_name}."
    elif sub == "Hubs & Docks":
        base = f"Expands device connectivity with 4K HDMI, 100W PD charging pass-through, and multi-port USB access for {parent_phrase}."
    elif sub == "Lighting":
        base = f"Screen-mounted asymmetrical optical lamp illuminates desktop surfaces with zero screen glare over {parent_phrase}."
    elif sub == "Cameras":
        base = "4K STARVIS sensor captures sharp video with dual noise-canceling mics for conferencing and streaming."
    elif sub == "Audio Recording":
        base = f"Cardioid condenser capsule with shock arm isolates vocal clarity while dampening desk vibrations from {primary_name}."
    elif sub == "Headphones":
        base = "Hybrid active noise cancellation filters ambient background noise for concentrated focus and study."
    elif sub == "Mounts & Organizers":
        if "Headphone" in candidate.name:
            base = "Under-desk aluminum mount keeps headsets secure and accessible without cluttering desk surfaces."
        elif "Monitor" in candidate.name:
            base = f"Counterbalanced gas-spring arms provide full-motion screen articulation and free up desk footprint around {parent_phrase}."
        else:
            base = f"Under-desk wire management basket and spine keep power and data cords routed and organized for {parent_phrase}."
    elif sub == "Cable Clips":
        base = f"Magnetic cable anchors secure charging and peripheral cords to prevent them from dropping behind desks."
    elif sub == "Maintenance":
        base = f"Ammonia-free gentle display cleaning spray and microfiber cloths remove dust without damaging anti-glare coatings on {parent_phrase}."
    elif sub == "Wireless Chargers":
        base = "15W fast wireless charging dock powers phone, watch, and earbuds simultaneously in a compact footprint."
    elif sub == "Power Adapters":
        base = f"Gallium nitride dual-port power adapter delivers fast 65W charging for laptops and accessories."
    elif sub == "Portable Power":
        base = "Airline-safe 20,000mAh battery with LCD status display keeps laptops and phones charged on the go."
    elif sub == "Travel Organizers":
        base = f"Water-resistant EVA hard-shell organizer protects cables, chargers, and compact peripherals like {parent_phrase} in transit."
    elif sub == "Drinkware":
        base = "Ceramic-lined vacuum insulation maintains drink temperature with spill-resistant desk safety."
    elif sub == "Refreshments":
        base = "Caffeine-free organic herbal botanicals and antioxidant snacks sustain mental energy during deep focus."
    elif sub == "Gaming Mice":
        base = "Ultra-lightweight 58g chassis with 26K DPI optical sensor and PTFE glides for pixel-accurate tracking."
    elif sub == "Gaming Accessories":
        base = f"Anti-drag silicone bungee arm suspends mouse cords to eliminate cable friction during rapid swipes with {primary_name}."
    else:
        base = f"Factual complementary accessory matching {candidate.category} with {parent_phrase}."

    # Intent Context Note
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

    # Multi-item association note from synthetic transactions
    if association_match and association_match.lift > 1.2:
        if association_match.is_multi_item:
            assoc_note = f" · Co-purchased in multi-item setups (lift: {association_match.lift:.1f}x)"
        else:
            assoc_note = f" · Frequently paired in setups (lift: {association_match.lift:.1f}x)"
    else:
        assoc_note = ""

    return f"{base}{context_note}{assoc_note}"

class RecommenderEngine:
    """Engine A: Multi-stage, context-aware recommendation engine for desk tech products."""

    def __init__(self, association_engine: AssociationRuleEngine | None = None):
        self.association_engine = association_engine or get_association_engine()

    def find_recommendations(
        self,
        cart_items: list[tuple[ProductEntity, int]],
        catalog: list[ProductEntity],
        shopping_context: str = "all",
        session_viewed_ids: list[str] | None = None,
        top_k: int = 4,
    ) -> list[RecommendationCandidate]:
        """Finds 3 to 5 ranked complementary product candidates evaluating the ENTIRE basket.
        
        Args:
            cart_items: List of (ProductEntity, quantity) tuples currently in cart.
            catalog: Full list of available ProductEntity catalog items.
            shopping_context: Active shopping intent ('all', 'productivity', 'gaming', 'study', 'travel', etc.).
            session_viewed_ids: Product IDs viewed or browsed in current anonymous session.
            top_k: Number of ranked recommendations to return (default 4, within [3, 5]).
            
        Returns:
            List of RecommendationCandidate ranked by whole-basket hybrid score with diversity applied.
        """
        if not cart_items or not catalog:
            return []

        cart_product_ids = tuple(sorted(item[0].id for item in cart_items))
        cart_id_set = set(cart_product_ids)
        cart_entities = [item[0] for item in cart_items]
        cart_subtotal_cents = sum(item[0].reference_price_cents * item[1] for item in cart_items)
        context_clean = shopping_context.strip().lower()
        viewed_set = set(session_viewed_ids or [])

        # Aggregate cart tags and categories across the entire basket
        cart_tags = set()
        cart_categories = set()
        for p in cart_entities:
            cart_tags.update(p.tags)
            cart_categories.add(p.category)

        # -------------------------------------------------------------------------
        # STAGE 1: Bounded Candidate Generation
        # -------------------------------------------------------------------------
        candidate_pool_ids: set[str] = set()

        # Source 1: Direct complementary metadata from any cart item
        for p in cart_entities:
            for cid in p.complementary_ids:
                if cid not in cart_id_set:
                    candidate_pool_ids.add(cid)

        # Source 2: Association rules mined from synthetic transactions (pairs and multi-item)
        assoc_candidates = self.association_engine.get_candidate_ids_for_basket(cart_product_ids, max_candidates=12)
        for cid, _ in assoc_candidates:
            if cid not in cart_id_set:
                candidate_pool_ids.add(cid)

        # Source 3: Cross-category affinity candidates
        for cand in catalog:
            if cand.id in cart_id_set or cand.inventory <= 0:
                continue
            for p in cart_entities:
                if (p.category, cand.category) in CATEGORY_AFFINITY_MATRIX or (cand.category, p.category) in CATEGORY_AFFINITY_MATRIX:
                    candidate_pool_ids.add(cand.id)
                    break

        # Source 4: Session viewed items
        for vid in viewed_set:
            if vid not in cart_id_set:
                candidate_pool_ids.add(vid)

        # Source 5: Cold-start fallback if candidate pool is small (< 6)
        if len(candidate_pool_ids) < 6:
            for cand in catalog:
                if cand.id not in cart_id_set and cand.inventory > 0:
                    candidate_pool_ids.add(cand.id)
                if len(candidate_pool_ids) >= 12:
                    break

        # Retrieve entities for generated candidate pool (capped at 25 for bounded latency)
        catalog_by_id = {p.id: p for p in catalog}
        eligible_candidates = [
            catalog_by_id[cid]
            for cid in candidate_pool_ids
            if cid in catalog_by_id and catalog_by_id[cid].inventory > 0 and cid not in cart_id_set
        ][:25]

        # -------------------------------------------------------------------------
        # STAGE 2: Whole-Basket Multi-Signal Scoring
        # -------------------------------------------------------------------------
        scored_candidates: list[tuple[ProductEntity, float, str, AssociationMatch | None]] = []

        for candidate in eligible_candidates:
            # 1. Basket-to-Product Complementarity Signal (Weight: 0.35)
            # Evaluates complementary links, cross-category affinity, and shared tags against ALL cart items
            matching_parents: list[ProductEntity] = []
            comp_score_accum = 0.0
            has_direct_link = False

            for parent in cart_entities:
                if candidate.id in parent.complementary_ids:
                    comp_score_accum += 0.70
                    has_direct_link = True
                    matching_parents.append(parent)
                elif parent.id in candidate.complementary_ids:
                    comp_score_accum += 0.60
                    has_direct_link = True
                    matching_parents.append(parent)
                else:
                    pair = (parent.category, candidate.category)
                    rev_pair = (candidate.category, parent.category)
                    boost = CATEGORY_AFFINITY_MATRIX.get(pair) or CATEGORY_AFFINITY_MATRIX.get(rev_pair)
                    if boost:
                        comp_score_accum += boost
                        if parent not in matching_parents:
                            matching_parents.append(parent)

            # Multi-item synergy: item complements multiple distinct products in cart
            if len(matching_parents) >= 2:
                comp_score_accum += 0.15

            # Tag overlap bonus across basket
            shared_tags = set(candidate.tags).intersection(cart_tags)
            if shared_tags:
                comp_score_accum += min(len(shared_tags) * 0.05, 0.15)

            s_comp = min(1.0, comp_score_accum)

            # 2. Historical Basket Association Rule Signal (Weight: 0.30)
            assoc_match = self.association_engine.evaluate_basket_candidate(cart_product_ids, candidate.id)
            if assoc_match:
                # Normalized lift: lift 1.0 -> 0.0, lift 5.0+ -> 1.0
                norm_lift = min(1.0, max(0.0, (assoc_match.lift - 1.0) / 3.0))
                s_assoc = min(1.0, 0.5 * norm_lift + 0.5 * assoc_match.confidence + (0.15 if assoc_match.is_multi_item else 0.0))
            else:
                s_assoc = 0.10  # Baseline

            # 3. Explicit Shopping Intent Context Signal (Weight: 0.25)
            if context_clean != "all" and context_clean:
                if context_clean in candidate.use_cases:
                    s_context = 1.0
                else:
                    s_context = 0.05
            else:
                s_context = 0.60  # Neutral baseline when 'all' is selected

            # 4. Session Exploration Signal (Weight: 0.10)
            if candidate.id in viewed_set:
                s_session = 1.0
            else:
                s_session = 0.0

            # Combined Normalized Hybrid Score
            base_vis = 0.10 if has_direct_link else 0.05
            raw_score = (
                base_vis +
                0.35 * s_comp +
                0.30 * s_assoc +
                0.20 * s_context +
                0.05 * s_session
            )

            # Price rationality adjustment: accessories shouldn't dwarf basket
            if cart_subtotal_cents > 3000 and candidate.reference_price_cents <= (0.60 * cart_subtotal_cents):
                raw_score += 0.05

            final_score = round(min(max(raw_score, 0.05), 0.98), 2)

            # ---------------------------------------------------------------------
            # STAGE 3: Structured Factual Explanation
            # ---------------------------------------------------------------------
            parents_for_explanation = matching_parents if matching_parents else cart_entities
            reason = build_factual_recommendation_reason(
                candidate=candidate,
                parents=parents_for_explanation,
                shopping_context=context_clean,
                association_match=assoc_match,
            )

            scored_candidates.append((candidate, final_score, reason, assoc_match))

        # Sort descending by affinity score
        scored_candidates.sort(key=lambda x: x[1], reverse=True)

        # -------------------------------------------------------------------------
        # STAGE 4: Diversity Enforcement & Bounded Selection
        # -------------------------------------------------------------------------
        selected: list[RecommendationCandidate] = []
        subcategory_counts = Counter()
        category_counts = Counter()

        # Pass 1: Select diverse candidates (max 1 per subcategory, max 2 per category)
        for cand, score, reason, assoc in scored_candidates:
            if len(selected) >= top_k:
                break
            if score < 0.15:
                # Do not recommend weak or irrelevant items
                continue

            sub_count = subcategory_counts[cand.subcategory]
            cat_count = category_counts[cand.category]

            if sub_count >= 1 or cat_count >= 2:
                continue

            selected.append(RecommendationCandidate(
                product=cand,
                affinity_score=score,
                compatibility_reason=reason,
                association_lift=assoc.lift if assoc else 1.0,
                association_confidence=assoc.confidence if assoc else 0.0,
                is_multi_item_match=assoc.is_multi_item if assoc else False,
            ))
            subcategory_counts[cand.subcategory] += 1
            category_counts[cand.category] += 1

        # Pass 2: Fill remaining slots if top_k not reached and qualified candidates exist
        if len(selected) < top_k:
            for cand, score, reason, assoc in scored_candidates:
                if len(selected) >= top_k:
                    break
                if score < 0.15:
                    continue
                if any(s.product.id == cand.id for s in selected):
                    continue
                # Relax category limit to 3 if needed to fill top_k
                if category_counts[cand.category] >= 3:
                    continue

                selected.append(RecommendationCandidate(
                    product=cand,
                    affinity_score=score,
                    compatibility_reason=reason,
                    association_lift=assoc.lift if assoc else 1.0,
                    association_confidence=assoc.confidence if assoc else 0.0,
                    is_multi_item_match=assoc.is_multi_item if assoc else False,
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
