"""Supervised Machine Learning Ranker for FairCart AI (Milestone 4B Part 5)

Implements HistGradientBoostingClassifier candidate ranking trained on synthetic
shopper interaction sessions (seed=42).

Architectural & Scientific Guarantees:
1. Model: HistGradientBoostingClassifier(max_iter=100, learning_rate=0.08, max_leaf_nodes=15, l2_regularization=1.0, random_state=42).
2. Input Features: 14 candidate-level features combining mathematical hybrid signals (C, A, U, E, P),
   association rule parameters, basket structure, and price geometry.
3. Labeling: Grounded in an independent synthetic latent-preference simulator (combining latent user utility,
   price sensitivity, and Gaussian noise). The model never observes the simulator's hidden latent states.
4. Train/Test Separation: Strict session-grouped 80/20 split (1,600 training sessions, 400 held-out test sessions).
   Zero cross-session data leakage.
5. Deterministic Offline Fallback: If model artifact is missing, unpicklable, or incompatible,
   the engine falls back immediately to the deterministic hybrid score S_hybrid in sub-millisecond time.
6. Scientific Honesty: Output probability is used purely as a relative ranking score, NOT as a calibrated
   real-world customer purchase probability.
"""

from dataclasses import dataclass
import os
from pathlib import Path
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
import joblib

from backend.app.db.repository import ProductEntity
from backend.app.engine.associations import (
    AssociationRuleEngine,
    SyntheticSession,
    generate_synthetic_sessions,
    split_sessions,
    get_association_engine,
)

# Feature names for diagnostics and interpretability
FEATURE_NAMES = [
    "complementarity_C",
    "association_A",
    "context_relevance_U",
    "session_interest_E",
    "price_fit_P",
    "rule_lift",
    "rule_confidence_smooth",
    "rule_union_count",
    "is_multi_item",
    "num_basket_matches",
    "cart_size",
    "candidate_price",
    "basket_price_ratio",
    "category_code",
]

# Mapping category names to deterministic integer codes
CATEGORY_CODE_MAP = {
    "Keyboards": 1,
    "Mice": 2,
    "Accessories": 3,
    "Audio & Video": 4,
    "Workspace": 5,
    "Power & Cables": 6,
    "Lifestyle": 7,
}

MODEL_DIR = Path(__file__).parent / "artifacts"
MODEL_PATH = MODEL_DIR / "ranker_model.joblib"

class SyntheticShopperSimulator:
    """Independent synthetic shopper latent-preference simulator for label generation.
    
    Generates realistic binary acceptance decisions (y in {0, 1}) from hidden persona utilities.
    The model NEVER sees these hidden variables as input features.
    """

    def __init__(self, seed: int = 42):
        self.rng = np.random.default_rng(seed)

    def simulate_acceptance(
        self,
        candidate: ProductEntity,
        basket: set[str],
        session: SyntheticSession,
        catalog_by_id: dict[str, ProductEntity],
    ) -> int:
        """Determines whether synthetic shopper accepts candidate based on latent preferences."""
        latent = session.latent_preference_vector
        ergonomic_pref = latent.get("ergonomic_affinity", 0.5)
        aesthetic_pref = latent.get("aesthetic_affinity", 0.5)
        price_sens = latent.get("price_sensitivity", 0.5)
        perf_pref = latent.get("performance_affinity", 0.5)

        # Candidate attribute alignments
        is_ergo = 1.0 if any(t in candidate.tags for t in ["ergonomic", "wrist-rest", "comfort", "cushion"]) else 0.0
        is_aesthetic = 1.0 if any(t in candidate.tags for t in ["rgb", "retro", "custom", "desk-mat", "leather"]) else 0.0
        is_perf = 1.0 if any(t in candidate.tags for t in ["wireless", "mechanical", "4k", "fast", "aluminum"]) else 0.0

        # Context alignment
        context_align = 1.0 if session.shopping_context in candidate.use_cases else 0.2

        # Basket co-occurrence utility
        direct_comp = 0.0
        for b_id in basket:
            b_item = catalog_by_id.get(b_id)
            if b_item and candidate.id in b_item.complementary_ids:
                direct_comp = 1.0
                break

        # Price friction (higher price reduces utility based on price sensitivity)
        price_friction = (candidate.reference_price_cents / 10000.0) * price_sens

        # Latent utility equation
        utility = (
            0.30 * direct_comp +
            0.25 * context_align +
            0.20 * (is_ergo * ergonomic_pref + is_aesthetic * aesthetic_pref + is_perf * perf_pref) -
            0.20 * price_friction +
            self.rng.normal(0.0, 0.12)
        )

        return 1 if utility > 0.38 else 0

def extract_candidate_features(
    candidate: ProductEntity,
    cart_entities: list[ProductEntity],
    comp_score: float,
    assoc_score: float,
    context_score: float,
    session_score: float,
    price_fit_score: float,
    assoc_match,
    num_matches: int,
) -> list[float]:
    """Constructs the exact 14-dimensional feature vector for a candidate."""
    cart_size = float(len(cart_entities))
    cand_price = candidate.reference_price_cents / 100.0

    if cart_entities:
        median_basket_price = float(np.median([p.reference_price_cents / 100.0 for p in cart_entities]))
    else:
        median_basket_price = cand_price

    price_ratio = (cand_price + 1.0) / (median_basket_price + 1.0)
    cat_code = float(CATEGORY_CODE_MAP.get(candidate.category, 0))

    if assoc_match:
        rule_lift = float(assoc_match.lift)
        rule_conf = float(assoc_match.confidence_smooth)
        rule_count = float(assoc_match.support * 1600.0)
        is_multi = 1.0 if assoc_match.is_multi_item else 0.0
    else:
        rule_lift = 1.0
        rule_conf = 0.0
        rule_count = 0.0
        is_multi = 0.0

    return [
        float(comp_score),
        float(assoc_score),
        float(context_score),
        float(session_score),
        float(price_fit_score),
        rule_lift,
        rule_conf,
        rule_count,
        is_multi,
        float(num_matches),
        cart_size,
        cand_price,
        price_ratio,
        cat_code,
    ]

class SupervisedMLRanker:
    """Supervised gradient-boosted candidate ranker trained on synthetic sessions."""

    def __init__(self, model: HistGradientBoostingClassifier | None = None):
        self.model = model
        self.is_trained = model is not None

    @classmethod
    def train(
        cls,
        training_sessions: list[SyntheticSession],
        catalog: list[ProductEntity],
        assoc_engine: AssociationRuleEngine,
        random_state: int = 42,
    ) -> "SupervisedMLRanker":
        """Trains HistGradientBoostingClassifier strictly on training sessions with zero test leakage."""
        simulator = SyntheticShopperSimulator(seed=random_state)
        catalog_by_id = {p.id: p for p in catalog}

        X_rows: list[list[float]] = []
        y_rows: list[int] = []

        # Import feature calculator from recommender to guarantee exact consistency
        from backend.app.engine.recommender import (
            calculate_complementarity_score,
            calculate_explicit_context_score,
            calculate_session_interest_score,
            calculate_price_fit_score,
        )

        for session in training_sessions:
            basket_entities = [catalog_by_id[i] for i in session.basket if i in catalog_by_id]
            if not basket_entities:
                continue

            basket_ids = tuple(sorted(p.id for p in basket_entities))
            # Evaluate all non-basket catalog candidates
            for candidate in catalog:
                if candidate.id in session.basket or candidate.inventory <= 0:
                    continue

                # 1. Hybrid feature signals
                comp_s, num_m = calculate_complementarity_score(candidate, basket_entities)
                assoc_s, assoc_m = assoc_engine.evaluate_association_score(candidate.id, basket_ids)
                ctx_s = calculate_explicit_context_score(candidate, session.shopping_context)
                sess_s = calculate_session_interest_score(candidate.id, session.events)
                pfit_s = calculate_price_fit_score(candidate, basket_entities)

                features = extract_candidate_features(
                    candidate=candidate,
                    cart_entities=basket_entities,
                    comp_score=comp_s,
                    assoc_score=assoc_s,
                    context_score=ctx_s,
                    session_score=sess_s,
                    price_fit_score=pfit_s,
                    assoc_match=assoc_m,
                    num_matches=num_m,
                )

                label = simulator.simulate_acceptance(
                    candidate=candidate,
                    basket=session.basket,
                    session=session,
                    catalog_by_id=catalog_by_id,
                )

                X_rows.append(features)
                y_rows.append(label)

        X = np.array(X_rows, dtype=np.float32)
        y = np.array(y_rows, dtype=np.int32)

        # Explicit model configuration from specification
        clf = HistGradientBoostingClassifier(
            max_iter=100,
            learning_rate=0.08,
            max_leaf_nodes=15,
            l2_regularization=1.0,
            random_state=random_state,
        )
        clf.fit(X, y)

        ranker = cls(model=clf)
        # Save model artifact
        ranker.save(MODEL_PATH)
        return ranker

    def save(self, filepath: Path) -> None:
        """Saves model artifact to disk."""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.model, filepath)

    @classmethod
    def load(cls, filepath: Path = MODEL_PATH) -> "SupervisedMLRanker":
        """Loads model artifact from disk, with fallback if not found."""
        if not filepath.exists():
            return cls(model=None)
        try:
            model = joblib.load(filepath)
            return cls(model=model)
        except Exception:
            return cls(model=None)

    def predict_score(self, feature_vector: list[float]) -> float:
        """Returns positive class probability as relative ranking score."""
        if self.model is None or not self.is_trained:
            return 0.5  # Neutral fallback
        try:
            x = np.array([feature_vector], dtype=np.float32)
            prob = self.model.predict_proba(x)[0, 1]
            return float(round(prob, 4))
        except Exception:
            return 0.5

# Singleton global ML ranker instance
_default_ml_ranker: SupervisedMLRanker | None = None

def get_ml_ranker(auto_train_if_missing: bool = True) -> SupervisedMLRanker:
    global _default_ml_ranker
    if _default_ml_ranker is None:
        _default_ml_ranker = SupervisedMLRanker.load(MODEL_PATH)
        if _default_ml_ranker.model is None and auto_train_if_missing:
            # Train and persist model if artifact missing
            from backend.app.db.repository import CatalogRepository
            repo = CatalogRepository()
            catalog = repo.get_all_entities()
            all_sessions = generate_synthetic_sessions(num_sessions=2000, seed=42)
            train_sessions, _ = split_sessions(all_sessions, train_ratio=0.8)
            assoc_engine = get_association_engine()
            _default_ml_ranker = SupervisedMLRanker.train(
                training_sessions=train_sessions,
                catalog=catalog,
                assoc_engine=assoc_engine,
                random_state=42,
            )
    return _default_ml_ranker
