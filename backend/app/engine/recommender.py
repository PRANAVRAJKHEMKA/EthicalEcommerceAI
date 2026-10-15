"""Engine A — Hybrid Context-Aware Recommendation Engine for FairCart AI

Implements the complete 10-stage hybrid recommendation pipeline:
1. Whole-basket candidate generation from direct complements, association rules, and browsing history.
2. Exact mathematical feature extraction:
       C(p, B): Whole-basket pairwise complementarity
       A(p, B): Mined association strength with bounded lift & Laplace smoothing
       U(p, c): Jaccard explicit shopping intent overlap
       E(p, h): Session interaction recency with exponential temporal decay (tau=24h)
       P(p, B): Basket price fit geometry
3. Baseline Deterministic Hybrid Ranking:
       S_hybrid(p | B, c, h) = 0.30*C + 0.30*A + 0.20*U + 0.15*E + 0.05*P
4. Supervised Machine Learning Ranking:
       HistGradientBoostingClassifier scoring on 14 candidate-level features with deterministic fallback.
5. Diversity-Aware Top-K Selection:
       Maximal Marginal Relevance (MMR) with lambda=0.75 and multi-attribute product similarity.
6. Factual Grounding:
       Structured, explainable synergy explanations without hallucination.
"""

from collections import Counter
from dataclasses import dataclass
import math
import numpy as np

from backend.app.db.repository import ProductEntity
from backend.app.engine.associations import (
    AssociationMatch,
    AssociationRuleEngine,
    get_association_engine,
)

@dataclass
class RecommendationAnchor:
    """Represents an anchor item providing context for recommendations (Milestone 4C)."""
    product_id: str
    source: str = "active_basket"  # 'active_basket', 'saved_cart', 'historical_order', 'product_view', 'search_interaction'
    weight: float = 1.0
    age_hours: float = 0.5
    view_count: int = 1

@dataclass
class RecommendationCandidate:
    """Represents a single scored candidate returned by Engine A."""
    product: ProductEntity
    affinity_score: float
    compatibility_reason: str
    association_lift: float = 1.0
    association_confidence: float = 0.0
    is_multi_item_match: bool = False
    ml_score: float | None = None
    mmr_score: float | None = None
    recommendation_source: str = "active_basket"
    provenance_label: str = ""

# Context keyword sets for exact Jaccard overlap U(p, c)
CONTEXT_KEYWORDS: dict[str, set[str]] = {
    "productivity": {"productivity", "ergonomic", "stand", "hub", "wireless", "organizer", "light", "screenbar"},
    "gaming": {"gaming", "mechanical", "custom", "rgb", "coiled", "bungee", "fast", "audio", "boom"},
    "study": {"study", "remote", "webcam", "microphone", "focus", "cooling", "pad", "compact", "audio"},
    "travel": {"travel", "portable", "compact", "gan", "charger", "cable", "sleeve", "wireless", "pouch"},
    "wellness": {"wellness", "ergonomic", "wrist-rest", "cushion", "lumbar", "stand", "comfort", "support"},
}

# Category affinity matrix reflecting workstation synergy
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

# -----------------------------------------------------------------------------
# MATHEMATICAL FEATURE FORMULAS (Milestones 4B & 4C)
# -----------------------------------------------------------------------------

# Documented catalog baseline popularity grounded in synthetic baseline transaction frequency
CATALOG_POPULARITY: dict[str, float] = {
    "item-001": 0.85,  # Ergonomic Mechanical Keyboard
    "item-002": 0.90,  # Memory Foam Wrist Rest
    "item-003": 0.88,  # Precision Vertical Wireless Mouse
    "item-004": 0.82,  # Extended Anti-Fray Felt Desk Mat
    "item-005": 0.70,  # Ultra-Lightweight Honeycomb Gaming Mouse
    "item-006": 0.75,  # Low-Profile Optical Mechanical Keyboard
    "item-007": 0.78,  # Custom Braided Coiled Type-C Cable
    "item-008": 0.80,  # Aluminum Laptop Stand Riser
    "item-011": 0.76,  # Stepless Dimming Monitor Light Bar
    "item-013": 0.79,  # Memory Foam Ergonomic Seat Cushion
    "item-016": 0.72,  # 7-in-1 Aluminum USB-C Hub
    "item-021": 0.68,  # Flexible Bungee Mouse Cable Holder
    "item-024": 0.74,  # Active Noise-Canceling Wireless Headphones
    "item-026": 0.65,  # Double-Shot PBT Backlit Keycaps
    "item-030": 0.71,  # Ergonomic Under-Desk Footrest
}

def calculate_anchor_complementarity_score(
    candidate: ProductEntity,
    anchors: list,
    catalog: list[ProductEntity] | None = None,
) -> tuple[float, int]:
    """Calculates bounded C_anchor(p, A) in [0, 1] across recommendation anchors without duplicate inflation.
    
    Formula:
        For each (parent, anchor) in A:
            comp_base = pairwise compatibility (1.0 for direct complement, 0.60 for subcat/tags, 0.15-0.35 category affinity, 0.05 baseline)
            repetition_guard = min(1.5, 1.0 + 0.2 * ln(1 + anchor.view_count))
            decay = exp(-anchor.age_hours / 24.0)
            effective_w = anchor.weight * decay * repetition_guard
            weighted_comp = effective_w * comp_base
        C_anchor(p, A) = min(1.0, sum(weighted_comp) / sqrt(sum(effective_w)))
    """
    if not anchors:
        return 0.0, 0

    catalog_map = {p.id: p for p in catalog} if catalog else {}

    accum = 0.0
    weight_sum = 0.0
    matching_parents = 0

    for item in anchors:
        if isinstance(item, tuple):
            parent, anchor = item
        elif isinstance(item, RecommendationAnchor):
            anchor = item
            parent = catalog_map.get(anchor.product_id)
            if not parent:
                continue
        else:
            continue

        rep_guard = min(1.5, 1.0 + 0.2 * math.log(1 + max(1, anchor.view_count)))
        decay = math.exp(-max(0.0, anchor.age_hours) / 24.0)
        eff_w = anchor.weight * decay * rep_guard
        weight_sum += eff_w

        if candidate.id in parent.complementary_ids or parent.id in candidate.complementary_ids:
            accum += eff_w * 1.00
            matching_parents += 1
        elif candidate.subcategory == parent.subcategory or set(candidate.tags).intersection(parent.tags):
            accum += eff_w * 0.60
            matching_parents += 1
        else:
            pair = (parent.category, candidate.category)
            rev_pair = (candidate.category, parent.category)
            boost = CATEGORY_AFFINITY_MATRIX.get(pair) or CATEGORY_AFFINITY_MATRIX.get(rev_pair) or 0.05
            accum += eff_w * boost
            if boost >= 0.25:
                matching_parents += 1

    if weight_sum <= 0:
        return 0.0, 0

    c_score = min(1.0, accum / math.sqrt(weight_sum))
    return round(c_score, 4), matching_parents

def calculate_complementarity_score(
    candidate: ProductEntity,
    cart_entities: list[ProductEntity],
) -> tuple[float, int]:
    """Calculates C(p, B) in [0, 1] across the entire basket without duplicate inflation.
    
    Backward-compatible wrapper around calculate_anchor_complementarity_score.
    """
    anchors = [
        (p, RecommendationAnchor(product_id=p.id, source="active_basket", weight=1.0, age_hours=0.0, view_count=1))
        for p in cart_entities
    ]
    return calculate_anchor_complementarity_score(candidate, anchors)

def calculate_cold_start_score(
    candidate: ProductEntity,
    shopping_context: str,
    catalog: list[ProductEntity],
) -> float:
    """Calculates deterministic S_cold(p | c) when no basket or anchors exist.
    
    Formula:
        S_cold(p | c) = 0.40 * U(p, c) + 0.35 * Popularity(p) + 0.15 * Connectivity(p) + 0.10 * PriceFit(p)
    """
    u_score = calculate_explicit_context_score(candidate, shopping_context)
    pop_score = CATALOG_POPULARITY.get(candidate.id, 0.50)
    
    max_comp_count = max((len(p.complementary_ids) for p in catalog), default=1)
    connectivity = min(1.0, len(candidate.complementary_ids) / max(1, max_comp_count))
    
    # Baseline reference price ~ $35.00
    cand_price = candidate.reference_price_cents / 100.0
    price_fit = math.exp(-abs(math.log((cand_price + 1.0) / (35.0 + 1.0))) / 1.5)
    
    score = (
        0.40 * u_score +
        0.35 * pop_score +
        0.15 * connectivity +
        0.10 * price_fit
    )
    return round(min(max(score, 0.05), 0.95), 4)

def calculate_explicit_context_score(
    candidate: ProductEntity,
    shopping_context: str,
) -> float:
    """Calculates U(p, c) via Jaccard overlap on use-case tags.
    
    Formula:
        U(p, c) = |K_p intersect K_c| / |K_p union K_c|
        If 'all' selected, returns neutral baseline 0.50.
    """
    ctx = shopping_context.strip().lower()
    if ctx == "all" or not ctx:
        return 0.50

    target_keywords = CONTEXT_KEYWORDS.get(ctx, {ctx})
    candidate_tokens = set(candidate.tags).union(candidate.use_cases)

    # Check direct use-case match first
    if ctx in candidate.use_cases:
        return 1.00

    intersection = candidate_tokens.intersection(target_keywords)
    union = candidate_tokens.union(target_keywords)
    if not union:
        return 0.0

    return round(len(intersection) / len(union), 4)

def calculate_session_interest_score(
    candidate_id: str,
    session_events: list | None = None,
    tau_hours: float = 24.0,
) -> float:
    """Calculates E(p, h) in [0, 1] using exponential recency decay.
    
    Formula:
        z(p, h) = sum_{e in E+} w_e * exp(-Delta t_e / tau) - sum_{e in E-} v_e * exp(-Delta t_e / tau)
        E(p, h) = 0.5 + 0.5 * tanh(z(p, h))
    """
    if not session_events:
        return 0.50  # Neutral baseline

    z = 0.0
    for evt in session_events:
        # Support both SyntheticInteractionEvent objects and dict records
        pid = getattr(evt, "product_id", None) or (evt.get("product_id") if isinstance(evt, dict) else "")
        if pid != candidate_id:
            continue

        etype = getattr(evt, "event_type", None) or (evt.get("event_type") if isinstance(evt, dict) else "")
        age = getattr(evt, "age_hours", None) or 1.0
        decay = math.exp(-age / tau_hours)

        if etype in ("product_view", "product_viewed"):
            z += 0.50 * decay
        elif etype in ("search_submitted",):
            z += 0.60 * decay
        elif etype in ("add_to_cart", "cart_item_added"):
            z += 1.00 * decay
        elif etype in ("recommendation_accepted",):
            z += 1.20 * decay
        elif etype in ("remove_from_cart", "cart_item_removed"):
            z -= 1.00 * decay

    score = 0.5 + 0.5 * math.tanh(z)
    return round(score, 4)

def calculate_price_fit_score(
    candidate: ProductEntity,
    cart_entities: list[ProductEntity] | None = None,
    anchor_entities: list[ProductEntity] | None = None,
    sigma: float = 1.0,
) -> float:
    """Calculates P(p, B or A) in (0, 1] based on median basket or anchor price geometry.
    
    Formula:
        P(p, B) = exp( - |ln( (price_p + 1) / (m_B + 1) )| / sigma )
    """
    cand_price = candidate.reference_price_cents / 100.0
    entities = cart_entities or anchor_entities
    if not entities:
        # Neutral cold-start fallback against catalog median $35.00
        ratio = (cand_price + 1.0) / (35.0 + 1.0)
        log_ratio = abs(math.log(ratio))
        return round(math.exp(-log_ratio / 1.5), 4)

    prices = [p.reference_price_cents / 100.0 for p in entities]
    m_b = float(np.median(prices))

    ratio = (cand_price + 1.0) / (m_b + 1.0)
    log_ratio = abs(math.log(ratio))
    score = math.exp(-log_ratio / sigma)
    return round(score, 4)

def calculate_hybrid_score(
    comp_score: float,
    assoc_score: float,
    context_score: float,
    session_score: float,
    price_fit_score: float,
) -> float:
    """Calculates exact deterministic S_hybrid.
    
    Formula:
        S_hybrid = 0.30*C + 0.30*A + 0.20*U + 0.15*E + 0.05*P
    """
    s = (
        0.30 * comp_score +
        0.30 * assoc_score +
        0.20 * context_score +
        0.15 * session_score +
        0.05 * price_fit_score
    )
    return round(min(max(s, 0.05), 0.98), 4)

# -----------------------------------------------------------------------------
# DIVERSITY & MMR (Milestone 4B Part 6)
# -----------------------------------------------------------------------------

def calculate_product_similarity(p1: ProductEntity, p2: ProductEntity) -> float:
    """Calculates multi-attribute product similarity in [0, 1] for MMR reranking."""
    # 1. Category / subcategory component (weight 0.5)
    if p1.subcategory and p1.subcategory == p2.subcategory:
        cat_sim = 0.50
    elif p1.category == p2.category:
        cat_sim = 0.30
    else:
        cat_sim = 0.0

    # 2. Tag Jaccard similarity (weight 0.3)
    t1 = set(p1.tags)
    t2 = set(p2.tags)
    tag_sim = len(t1.intersection(t2)) / len(t1.union(t2)) if (t1 or t2) else 0.0

    # 3. Price closeness (weight 0.2)
    p1_price = p1.reference_price_cents / 100.0
    p2_price = p2.reference_price_cents / 100.0
    max_p = max(p1_price, p2_price, 1.0)
    price_sim = 1.0 - min(1.0, abs(p1_price - p2_price) / max_p)

    return cat_sim + 0.30 * tag_sim + 0.20 * price_sim

def apply_mmr_reranking(
    scored_candidates: list,
    top_k: int = 4,
    lambda_param: float = 0.75,
) -> list[RecommendationCandidate]:
    """Selects top-K diverse candidates using Maximal Marginal Relevance (MMR).
    
    Formula:
        MMR(p) = lambda * S(p) - (1 - lambda) * max_{r in R} sim(p, r)
    """
    if not scored_candidates:
        return []

    selected: list = []
    pool = list(scored_candidates)

    while len(selected) < top_k and pool:
        best_cand_idx = -1
        best_mmr = -float("inf")

        for idx, item in enumerate(pool):
            cand = item[0]
            score = item[1]
            if not selected:
                # First item selected purely on relevance
                mmr = score
            else:
                max_sim = max(calculate_product_similarity(cand, s[0]) for s in selected)
                mmr = lambda_param * score - (1.0 - lambda_param) * max_sim

            if mmr > best_mmr:
                best_mmr = mmr
                best_cand_idx = idx

        if best_cand_idx >= 0:
            chosen = pool.pop(best_cand_idx)
            selected.append(chosen + (round(best_mmr, 4),))

    result: list[RecommendationCandidate] = []
    for item in selected:
        cand = item[0]
        score = item[1]
        reason = item[2]
        assoc = item[3]
        ml_s = item[4]
        if len(item) >= 8:
            rec_src = item[5]
            prov_lbl = item[6]
            mmr_s = item[7]
        else:
            rec_src = getattr(cand, "recommendation_source", "active_basket")
            prov_lbl = getattr(cand, "provenance_label", "")
            mmr_s = item[5] if len(item) > 5 else None

        result.append(
            RecommendationCandidate(
                product=cand,
                affinity_score=score,
                compatibility_reason=reason,
                association_lift=assoc.lift if assoc else 1.0,
                association_confidence=assoc.confidence_smooth if assoc else 0.0,
                is_multi_item_match=assoc.is_multi_item if assoc else False,
                ml_score=ml_s,
                mmr_score=mmr_s,
                recommendation_source=rec_src,
                provenance_label=prov_lbl,
            )
        )

    return result

# -----------------------------------------------------------------------------
# FACTUAL EXPLANATIONS (Milestone 4B Part 10 Grounding)
# -----------------------------------------------------------------------------

def build_factual_recommendation_reason(
    candidate: ProductEntity,
    parents: list[ProductEntity] | None = None,
    parent: ProductEntity | None = None,
    shopping_context: str = "all",
    association_match: AssociationMatch | None = None,
    provenance_source: str = "active_basket",
) -> str:
    """Generates structured factual reason grounded in concrete attributes, basket relationships, or cold-start baseline."""
    if parents is None:
        parents = [parent] if parent else []

    sub = candidate.subcategory.strip()
    primary_parent = parents[0] if parents else None
    primary_name = primary_parent.name if primary_parent else "your setup"

    if len(parents) >= 2:
        parent_phrase = f"{parents[0].name} and {parents[1].name}"
    elif parents:
        parent_phrase = primary_name
    else:
        parent_phrase = "your workstation"

    name_lower = candidate.name.lower()
    if "wrist" in name_lower or sub in ("Wrist Rests", "Ergonomic Supports"):
        base = f"Ergonomically contoured cooling gel cushions wrists during typing on {primary_name}." if parents else "Contoured cooling gel cushions wrists for ergonomic comfort across desk setups."
    elif "light" in name_lower or sub in ("Lighting", "Monitor Light Bars"):
        base = f"Reduces screen glare and eye strain for extended visual sessions beside {primary_name}." if parents else "Reduces screen glare and eye strain for extended visual workstation sessions."
    elif "mat" in name_lower or sub in ("Desk Surfaces", "Desk Mats"):
        base = f"Protective non-slip desk surface stabilizing both your keyboard and mouse next to {primary_name}." if parents else "Protective non-slip desk surface stabilizing peripherals across any workstation."
    elif "cable" in name_lower or sub in ("Cables & Connectors", "Cables"):
        base = f"Heavy-duty Type-C aviator connector provides clean, tangle-free power routing for {primary_name}." if parents else "Heavy-duty Type-C aviator connector provides clean, reliable peripheral power."
    elif "keycap" in name_lower or sub in ("Keycap Sets", "Components"):
        base = f"Custom profile keycaps customized for tactile responsiveness with {primary_name}." if parents else "Custom profile keycaps designed for tactile responsiveness on mechanical keyboards."
    elif "stand" in name_lower or "riser" in name_lower or sub in ("Stands & Risers", "Mounts & Organizers"):
        base = f"Elevates display to eye level, relieving cervical neck strain alongside {primary_name}." if parents else "Elevates display to eye level, relieving cervical neck strain."
    elif "hub" in name_lower or "dock" in name_lower or sub in ("Hubs & Docks", "USB Hubs"):
        base = f"Expand ports with high-speed data passthrough for {primary_name}." if parents else "Expands workstation ports with high-speed 100W PD data and display passthrough."
    elif "bungee" in name_lower or sub in ("Gaming Accessories", "Mouse Accessories"):
        base = f"Anti-drag bungee suspends mouse cord to eliminate friction during rapid tracking with {primary_name}." if parents else "Anti-drag bungee suspends mouse cord to eliminate cable friction."
    else:
        base = f"Factual complementary accessory matching {candidate.category} with {parent_phrase}." if parents else f"Versatile {candidate.category} accessory selected for multi-setup compatibility."

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

    if association_match and association_match.lift > 1.2:
        if association_match.is_multi_item:
            assoc_note = f" · Co-purchased in multi-item setups (lift: {association_match.lift:.1f}x)"
        else:
            assoc_note = f" · Frequently paired in setups (lift: {association_match.lift:.1f}x)"
    elif provenance_source == "catalog_popular":
        assoc_note = " · High catalog versatility"
    else:
        assoc_note = ""

    return f"{base}{context_note}{assoc_note}"

# -----------------------------------------------------------------------------
# ENGINE A: RECOMMENDER CLASS
# -----------------------------------------------------------------------------

class RecommenderEngine:
    """Engine A: Hybrid context-aware recommendation engine."""

    calculate_anchor_complementarity_score = staticmethod(calculate_anchor_complementarity_score)

    def __init__(
        self,
        association_engine: AssociationRuleEngine | None = None,
        ranking_mode: str = "hybrid",  # "hybrid" or "ml"
    ):
        self.association_engine = association_engine or get_association_engine()
        self.ranking_mode = ranking_mode

    def find_recommendations(
        self,
        cart_items: list[tuple[ProductEntity, int]] | None = None,
        catalog: list[ProductEntity] | None = None,
        shopping_context: str = "all",
        session_viewed_ids: list[str] | None = None,
        session_events: list | None = None,
        anchors: list[RecommendationAnchor] | None = None,
        search_query: str = "",
        top_k: int = 4,
        use_mmr: bool = True,
    ) -> list[RecommendationCandidate]:
        """Finds top-K ranked complementary or cold-start recommendations.
        
        Supports both active-basket recommendations and empty-basket personalized/cold-start recommendations.
        """
        if not catalog:
            return []

        cart_items = cart_items or []
        cart_product_ids = tuple(sorted(item[0].id for item in cart_items))
        cart_id_set = set(cart_product_ids)
        cart_entities = [item[0] for item in cart_items]
        catalog_by_id = {p.id: p for p in catalog}

        # ---------------------------------------------------------------------
        # STAGE 1: Recommendation Anchors Assembly
        # ---------------------------------------------------------------------
        resolved_anchors: list[tuple[ProductEntity, RecommendationAnchor]] = []
        if anchors:
            for a in anchors:
                if a.product_id in catalog_by_id:
                    resolved_anchors.append((catalog_by_id[a.product_id], a))
        else:
            if cart_entities:
                for p in cart_entities:
                    resolved_anchors.append((
                        p,
                        RecommendationAnchor(
                            product_id=p.id,
                            source="active_basket",
                            weight=1.0,
                            age_hours=0.0,
                            view_count=1,
                        )
                    ))
            elif session_viewed_ids:
                seen_vids = set()
                for vid in session_viewed_ids:
                    if vid in catalog_by_id and vid not in seen_vids:
                        seen_vids.add(vid)
                        resolved_anchors.append((
                            catalog_by_id[vid],
                            RecommendationAnchor(
                                product_id=vid,
                                source="product_view",
                                weight=0.60,
                                age_hours=0.5,
                                view_count=1,
                            )
                        ))

        # Determine primary provenance source and user-facing label
        if cart_entities:
            primary_source = "active_basket"
            primary_label = "Recommended for your current cart"
        elif any(a[1].source == "historical_order" for a in resolved_anchors):
            primary_source = "historical_order"
            primary_label = "Based on items in your previous FairCart order"
        elif any(a[1].source == "saved_cart" for a in resolved_anchors):
            primary_source = "saved_cart"
            primary_label = "Based on items in your saved cart"
        elif any(a[1].source in ("product_view", "product_views") for a in resolved_anchors):
            primary_source = "product_views"
            primary_label = "Inspired by products you've viewed"
        elif shopping_context.strip().lower() not in ("all", "general", ""):
            primary_source = "shopping_context"
            primary_label = f"Recommended for your selected {shopping_context.strip().capitalize()} setup"
        else:
            primary_source = "catalog_popular"
            primary_label = "Popular picks from our catalogue"

        # ---------------------------------------------------------------------
        # STAGE 2: Candidate Generation
        # ---------------------------------------------------------------------
        candidate_pool_ids: set[str] = set()

        if resolved_anchors:
            # Source A: Complements of anchors
            for parent, _ in resolved_anchors:
                for cid in parent.complementary_ids:
                    if cid not in cart_id_set:
                        candidate_pool_ids.add(cid)

            # Source B: Mined association rules from anchor antecedents
            anchor_pids = tuple(sorted(a[0].id for a in resolved_anchors))
            assoc_cands = self.association_engine.get_candidate_ids_for_basket(anchor_pids, max_candidates=15)
            for cid, _ in assoc_cands:
                if cid not in cart_id_set:
                    candidate_pool_ids.add(cid)

            # Source C: Category affinity with anchors
            for cand in catalog:
                if cand.id in cart_id_set or cand.inventory <= 0:
                    continue
                for parent, _ in resolved_anchors:
                    if (parent.category, cand.category) in CATEGORY_AFFINITY_MATRIX or (cand.category, parent.category) in CATEGORY_AFFINITY_MATRIX:
                        candidate_pool_ids.add(cand.id)
                        break

        # Source D: Search query match
        if search_query.strip():
            tokens = [tok.lower() for tok in search_query.strip().split() if len(tok) >= 2]
            for cand in catalog:
                if cand.id not in cart_id_set and cand.inventory > 0:
                    c_text = (cand.name + " " + cand.description + " " + " ".join(cand.tags)).lower()
                    if any(tok in c_text for tok in tokens):
                        candidate_pool_ids.add(cand.id)

        # Source E: Shopping context use-case alignment
        if shopping_context.strip().lower() != "all":
            ctx = shopping_context.strip().lower()
            for cand in catalog:
                if cand.id not in cart_id_set and cand.inventory > 0 and ctx in cand.use_cases:
                    candidate_pool_ids.add(cand.id)

        # Source F: Cold-start fallback pool filling
        if len(candidate_pool_ids) < 8:
            sorted_by_pop = sorted(
                catalog,
                key=lambda p: CATALOG_POPULARITY.get(p.id, 0.50),
                reverse=True,
            )
            for cand in sorted_by_pop:
                if cand.id not in cart_id_set and cand.inventory > 0:
                    candidate_pool_ids.add(cand.id)
                if len(candidate_pool_ids) >= 15:
                    break

        eligible_candidates = [
            catalog_by_id[cid]
            for cid in candidate_pool_ids
            if cid in catalog_by_id and catalog_by_id[cid].inventory > 0 and cid not in cart_id_set
        ][:30]

        # ---------------------------------------------------------------------
        # STAGE 3: Multi-Signal Feature Extraction & Scoring
        # ---------------------------------------------------------------------
        scored_candidates: list[tuple[ProductEntity, float, str, AssociationMatch | None, float, str, str]] = []

        ml_ranker = None
        if self.ranking_mode == "ml":
            try:
                from backend.app.engine.ml_ranker import get_ml_ranker
                ml_ranker = get_ml_ranker(auto_train_if_missing=True)
            except Exception:
                ml_ranker = None

        anchor_parents = [a[0] for a in resolved_anchors]
        anchor_pids = tuple(sorted(a.id for a in anchor_parents))

        for candidate in eligible_candidates:
            if resolved_anchors:
                c_score, num_m = calculate_anchor_complementarity_score(candidate, resolved_anchors)
                a_score, assoc_match = self.association_engine.evaluate_association_score(candidate.id, anchor_pids)
                u_score = calculate_explicit_context_score(candidate, shopping_context)
                e_score = calculate_session_interest_score(candidate.id, session_events)
                p_score = calculate_price_fit_score(candidate, anchor_entities=anchor_parents)

                hybrid_score = calculate_hybrid_score(c_score, a_score, u_score, e_score, p_score)

                ml_score = None
                if ml_ranker and ml_ranker.is_trained:
                    from backend.app.engine.ml_ranker import extract_candidate_features
                    feats = extract_candidate_features(
                        candidate=candidate,
                        cart_entities=cart_entities,
                        comp_score=c_score,
                        assoc_score=a_score,
                        context_score=u_score,
                        session_score=e_score,
                        price_fit_score=p_score,
                        assoc_match=assoc_match,
                        num_matches=num_m,
                    )
                    ml_score = ml_ranker.predict_score(feats)
                    score = round(ml_score, 4) if self.ranking_mode == "ml" else hybrid_score
                else:
                    score = hybrid_score

                reason = build_factual_recommendation_reason(
                    candidate=candidate,
                    parents=anchor_parents,
                    shopping_context=shopping_context,
                    association_match=assoc_match,
                    provenance_source=primary_source,
                )
            else:
                # True cold-start scoring
                score = calculate_cold_start_score(candidate, shopping_context, catalog)
                assoc_match = None
                ml_score = score
                reason = build_factual_recommendation_reason(
                    candidate=candidate,
                    parents=[],
                    shopping_context=shopping_context,
                    provenance_source=primary_source,
                )

            scored_candidates.append((
                candidate,
                score,
                reason,
                assoc_match,
                ml_score if ml_score else score,
                primary_source,
                primary_label,
            ))

        # Sort descending by primary score
        scored_candidates.sort(key=lambda x: x[1], reverse=True)

        # ---------------------------------------------------------------------
        # STAGE 4: Diversity-Aware MMR Selection
        # ---------------------------------------------------------------------
        if use_mmr:
            selected = apply_mmr_reranking(scored_candidates, top_k=top_k, lambda_param=0.75)
        else:
            selected = [
                RecommendationCandidate(
                    product=c[0],
                    affinity_score=c[1],
                    compatibility_reason=c[2],
                    association_lift=c[3].lift if c[3] else 1.0,
                    association_confidence=c[3].confidence_smooth if c[3] else 0.0,
                    is_multi_item_match=c[3].is_multi_item if c[3] else False,
                    ml_score=c[4],
                    recommendation_source=c[5],
                    provenance_label=c[6],
                )
                for c in scored_candidates[:top_k]
            ]

        return selected

    def recommend(
        self,
        cart_items: list[tuple[ProductEntity, int]],
        catalog: list[ProductEntity],
    ) -> RecommendationCandidate | None:
        """Backward-compatible single recommendation."""
        recs = self.find_recommendations(cart_items, catalog, shopping_context="all", top_k=1)
        return recs[0] if recs else None

    def find_recommendation(
        self,
        cart_items: list[tuple[ProductEntity, int]],
        catalog: list[ProductEntity],
    ) -> RecommendationCandidate | None:
        """Backward-compatible single recommendation alias."""
        return self.recommend(cart_items, catalog)
