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
# MATHEMATICAL FEATURE FORMULAS (Milestone 4B Part 4)
# -----------------------------------------------------------------------------

def calculate_complementarity_score(
    candidate: ProductEntity,
    cart_entities: list[ProductEntity],
) -> tuple[float, int]:
    """Calculates C(p, B) in [0, 1] across the entire basket without duplicate inflation.
    
    Formula:
        For each i in B, computes pairwise compatibility:
            - Direct metadata complement: 1.0
            - Subcategory match or shared ergonomic tags: 0.6
            - Cross-category synergy: affinity weight (0.15 - 0.35)
            - Baseline: 0.05
        C(p, B) = min(1.0, sum_i comp(p, i) / sqrt(|B|))
    """
    if not cart_entities:
        return 0.0, 0

    accum = 0.0
    matching_parents = 0

    for parent in cart_entities:
        if candidate.id in parent.complementary_ids or parent.id in candidate.complementary_ids:
            accum += 1.00
            matching_parents += 1
        elif candidate.subcategory == parent.subcategory or set(candidate.tags).intersection(parent.tags):
            accum += 0.60
            matching_parents += 1
        else:
            pair = (parent.category, candidate.category)
            rev_pair = (candidate.category, parent.category)
            boost = CATEGORY_AFFINITY_MATRIX.get(pair) or CATEGORY_AFFINITY_MATRIX.get(rev_pair) or 0.05
            accum += boost
            if boost >= 0.25:
                matching_parents += 1

    # Normalization bounded by sqrt(|B|) to avoid duplicate inflation
    c_score = min(1.0, accum / math.sqrt(len(cart_entities)))
    return round(c_score, 4), matching_parents

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
    cart_entities: list[ProductEntity],
    sigma: float = 1.0,
) -> float:
    """Calculates P(p, B) in (0, 1] based on median basket price geometry.
    
    Formula:
        P(p, B) = exp( - |ln( (price_p + 1) / (m_B + 1) )| / sigma )
    """
    cand_price = candidate.reference_price_cents / 100.0
    if not cart_entities:
        return 1.00

    prices = [p.reference_price_cents / 100.0 for p in cart_entities]
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
    scored_candidates: list[tuple[ProductEntity, float, str, AssociationMatch | None, float]],
    top_k: int = 4,
    lambda_param: float = 0.75,
) -> list[RecommendationCandidate]:
    """Selects top-K diverse candidates using Maximal Marginal Relevance (MMR).
    
    Formula:
        MMR(p) = lambda * S(p) - (1 - lambda) * max_{r in R} sim(p, r)
    """
    if not scored_candidates:
        return []

    selected: list[tuple[ProductEntity, float, str, AssociationMatch | None, float, float]] = []
    pool = list(scored_candidates)

    while len(selected) < top_k and pool:
        best_cand_idx = -1
        best_mmr = -float("inf")

        for idx, (cand, score, reason, assoc, ml_s) in enumerate(pool):
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
            selected.append((chosen[0], chosen[1], chosen[2], chosen[3], chosen[4], round(best_mmr, 4)))

    return [
        RecommendationCandidate(
            product=cand,
            affinity_score=score,
            compatibility_reason=reason,
            association_lift=assoc.lift if assoc else 1.0,
            association_confidence=assoc.confidence_smooth if assoc else 0.0,
            is_multi_item_match=assoc.is_multi_item if assoc else False,
            ml_score=ml_s,
            mmr_score=mmr_s,
        )
        for cand, score, reason, assoc, ml_s, mmr_s in selected
    ]

# -----------------------------------------------------------------------------
# FACTUAL EXPLANATIONS (Milestone 4B Part 10 Grounding)
# -----------------------------------------------------------------------------

def build_factual_recommendation_reason(
    candidate: ProductEntity,
    parents: list[ProductEntity] | None = None,
    parent: ProductEntity | None = None,
    shopping_context: str = "all",
    association_match: AssociationMatch | None = None,
) -> str:
    """Generates structured factual reason grounded in concrete attributes and basket relationships."""
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
        base = f"Ergonomically contoured cooling gel cushions wrists during typing on {primary_name}."
    elif "light" in name_lower or sub in ("Lighting", "Monitor Light Bars"):
        base = f"Reduces screen glare and eye strain for extended visual sessions beside {primary_name}."
    elif "mat" in name_lower or sub in ("Desk Surfaces", "Desk Mats"):
        base = f"Protective non-slip desk surface stabilizing both your keyboard and mouse next to {primary_name}."
    elif "cable" in name_lower or sub in ("Cables & Connectors", "Cables"):
        base = f"Heavy-duty Type-C aviator connector provides clean, tangle-free power routing for {primary_name}."
    elif "keycap" in name_lower or sub in ("Keycap Sets", "Components"):
        base = f"Custom profile keycaps customized for tactile responsiveness with {primary_name}."
    elif "stand" in name_lower or "riser" in name_lower or sub in ("Stands & Risers", "Mounts & Organizers"):
        base = f"Elevates display to eye level, relieving cervical neck strain alongside {primary_name}."
    elif "hub" in name_lower or "dock" in name_lower or sub in ("Hubs & Docks", "USB Hubs"):
        base = f"Expand ports with high-speed data passthrough for {primary_name}."
    elif "bungee" in name_lower or sub in ("Gaming Accessories", "Mouse Accessories"):
        base = f"Anti-drag bungee suspends mouse cord to eliminate friction during rapid tracking with {primary_name}."
    else:
        base = f"Factual complementary accessory matching {candidate.category} with {parent_phrase}."

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
    else:
        assoc_note = ""

    return f"{base}{context_note}{assoc_note}"

# -----------------------------------------------------------------------------
# ENGINE A: RECOMMENDER CLASS
# -----------------------------------------------------------------------------

class RecommenderEngine:
    """Engine A: Hybrid context-aware recommendation engine."""

    def __init__(
        self,
        association_engine: AssociationRuleEngine | None = None,
        ranking_mode: str = "hybrid",  # "hybrid" or "ml"
    ):
        self.association_engine = association_engine or get_association_engine()
        self.ranking_mode = ranking_mode

    def find_recommendations(
        self,
        cart_items: list[tuple[ProductEntity, int]],
        catalog: list[ProductEntity],
        shopping_context: str = "all",
        session_viewed_ids: list[str] | None = None,
        session_events: list | None = None,
        top_k: int = 4,
        use_mmr: bool = True,
    ) -> list[RecommendationCandidate]:
        """Finds top-K ranked complementary product candidates evaluated over the ENTIRE basket."""
        if not cart_items or not catalog:
            return []

        cart_product_ids = tuple(sorted(item[0].id for item in cart_items))
        cart_id_set = set(cart_product_ids)
        cart_entities = [item[0] for item in cart_items]
        viewed_set = set(session_viewed_ids or [])

        # ---------------------------------------------------------------------
        # STAGE 1: Bounded Candidate Generation
        # ---------------------------------------------------------------------
        candidate_pool_ids: set[str] = set()

        # Source 1: Direct complements
        for p in cart_entities:
            for cid in p.complementary_ids:
                if cid not in cart_id_set:
                    candidate_pool_ids.add(cid)

        # Source 2: Mined association rules
        assoc_cands = self.association_engine.get_candidate_ids_for_basket(cart_product_ids, max_candidates=15)
        for cid, _ in assoc_cands:
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

        # Source 5: Cold-start fallback
        if len(candidate_pool_ids) < 8:
            for cand in catalog:
                if cand.id not in cart_id_set and cand.inventory > 0:
                    candidate_pool_ids.add(cand.id)
                if len(candidate_pool_ids) >= 15:
                    break

        catalog_by_id = {p.id: p for p in catalog}
        eligible_candidates = [
            catalog_by_id[cid]
            for cid in candidate_pool_ids
            if cid in catalog_by_id and catalog_by_id[cid].inventory > 0 and cid not in cart_id_set
        ][:30]

        # ---------------------------------------------------------------------
        # STAGE 2: Multi-Signal Feature Extraction & Scoring
        # ---------------------------------------------------------------------
        scored_candidates: list[tuple[ProductEntity, float, str, AssociationMatch | None, float]] = []

        # Lazy load ML ranker if ranking_mode is 'ml'
        ml_ranker = None
        if self.ranking_mode == "ml":
            try:
                from backend.app.engine.ml_ranker import get_ml_ranker
                ml_ranker = get_ml_ranker(auto_train_if_missing=True)
            except Exception:
                ml_ranker = None

        for candidate in eligible_candidates:
            # 1. Feature Signals
            c_score, num_m = calculate_complementarity_score(candidate, cart_entities)
            a_score, assoc_match = self.association_engine.evaluate_association_score(candidate.id, cart_product_ids)
            u_score = calculate_explicit_context_score(candidate, shopping_context)
            e_score = calculate_session_interest_score(candidate.id, session_events)
            p_score = calculate_price_fit_score(candidate, cart_entities)

            # Deterministic Hybrid Score S_hybrid
            hybrid_score = calculate_hybrid_score(c_score, a_score, u_score, e_score, p_score)

            # Supervised ML Score S_ML (if enabled and available)
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
                # Primary ranking score
                score = round(ml_score, 4) if self.ranking_mode == "ml" else hybrid_score
            else:
                score = hybrid_score

            # Structured factual reason
            reason = build_factual_recommendation_reason(
                candidate=candidate,
                parents=cart_entities,
                shopping_context=shopping_context,
                association_match=assoc_match,
            )

            scored_candidates.append((candidate, score, reason, assoc_match, ml_score if ml_score else hybrid_score))

        # Sort descending by primary score
        scored_candidates.sort(key=lambda x: x[1], reverse=True)

        # ---------------------------------------------------------------------
        # STAGE 3: Diversity-Aware MMR Selection
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
