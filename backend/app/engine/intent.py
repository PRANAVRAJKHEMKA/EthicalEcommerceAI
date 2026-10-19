"""FairCart AI — Continuous Recency-Weighted Markov Shopper Intent Engine (Slice 4)

Models shopper browsing trajectories using:
1. Exponential recency decay: w(Delta t) = exp(-gamma * Delta t)
2. 5-State Markov transition process:
   - DISCOVERY
   - PRODUCT_COMPARISON
   - PURCHASE_CONSIDERATION
   - CART_COMPLETION
   - REPLENISHMENT
3. Laplace-smoothed Bayesian transition matrices (alpha=1.0)
4. State entropy and purchase intent scoring
5. Price sensitivity estimation to protect margins against needless discounting
"""

import math
from datetime import datetime, timezone
from typing import Any

from backend.app.models.decision_twin_schemas import ShopperIntentState

INTENT_STATES = [
    "DISCOVERY",
    "PRODUCT_COMPARISON",
    "PURCHASE_CONSIDERATION",
    "CART_COMPLETION",
    "REPLENISHMENT",
]

# State conversion baseline priors P(Purchase | State)
STATE_CONVERSION_PRIORS = {
    "DISCOVERY": 0.08,
    "PRODUCT_COMPARISON": 0.22,
    "PURCHASE_CONSIDERATION": 0.42,
    "CART_COMPLETION": 0.68,
    "REPLENISHMENT": 0.58,
}

# Empirical transition frequency matrix prior between states
TRANSITION_PRIORS: dict[str, dict[str, float]] = {
    "DISCOVERY": {
        "DISCOVERY": 12.0,
        "PRODUCT_COMPARISON": 8.0,
        "PURCHASE_CONSIDERATION": 4.0,
        "CART_COMPLETION": 1.0,
        "REPLENISHMENT": 1.0,
    },
    "PRODUCT_COMPARISON": {
        "DISCOVERY": 3.0,
        "PRODUCT_COMPARISON": 15.0,
        "PURCHASE_CONSIDERATION": 9.0,
        "CART_COMPLETION": 3.0,
        "REPLENISHMENT": 1.0,
    },
    "PURCHASE_CONSIDERATION": {
        "DISCOVERY": 2.0,
        "PRODUCT_COMPARISON": 5.0,
        "PURCHASE_CONSIDERATION": 16.0,
        "CART_COMPLETION": 8.0,
        "REPLENISHMENT": 2.0,
    },
    "CART_COMPLETION": {
        "DISCOVERY": 1.0,
        "PRODUCT_COMPARISON": 2.0,
        "PURCHASE_CONSIDERATION": 4.0,
        "CART_COMPLETION": 20.0,
        "REPLENISHMENT": 2.0,
    },
    "REPLENISHMENT": {
        "DISCOVERY": 2.0,
        "PRODUCT_COMPARISON": 3.0,
        "PURCHASE_CONSIDERATION": 6.0,
        "CART_COMPLETION": 10.0,
        "REPLENISHMENT": 14.0,
    },
}


def compute_recency_weight(elapsed_seconds: float, gamma: float = 0.001) -> float:
    """Computes exponential recency weight for an interaction event.

    w(Delta t) = exp(-gamma * Delta t)
    For gamma=0.001/sec:
      t=0s   -> w=1.00
      t=60s  -> w=0.94
      t=300s -> w=0.74
      t=600s -> w=0.55
    """
    dt = max(0.0, float(elapsed_seconds))
    return round(math.exp(-gamma * dt), 4)


def get_laplace_smoothed_transitions(alpha: float = 1.0) -> dict[str, dict[str, float]]:
    """Calculates normalized Laplace-smoothed Markov transition probabilities.

    P(S_t = j | S_{t-1} = i) = (N_{ij} + alpha) / sum_k (N_{ik} + alpha)
    """
    matrix: dict[str, dict[str, float]] = {}
    num_states = len(INTENT_STATES)

    for from_state in INTENT_STATES:
        row_counts = TRANSITION_PRIORS.get(from_state, {})
        denom = sum(row_counts.get(to_state, 0.0) + alpha for to_state in INTENT_STATES)
        matrix[from_state] = {}
        for to_state in INTENT_STATES:
            numer = row_counts.get(to_state, 0.0) + alpha
            matrix[from_state][to_state] = round(numer / denom, 4)

    return matrix


SMOOTHED_TRANSITION_MATRIX = get_laplace_smoothed_transitions(alpha=1.0)


def compute_transition_entropy(probabilities: dict[str, float]) -> float:
    """Computes Shannon entropy H(S) = -sum p_i * log2(p_i) in bits.

    Lower entropy indicates higher shopper clarity/decisiveness.
    """
    entropy = 0.0
    for p in probabilities.values():
        if p > 1e-6:
            entropy -= p * math.log2(p)
    return round(entropy, 3)


class ShopperIntentEngine:
    """Continuous recency-weighted Markov intent tracker and estimator."""

    def __init__(self, gamma: float = 0.001):
        self.gamma = gamma
        self.transition_matrix = SMOOTHED_TRANSITION_MATRIX

    def infer_intent_state(
        self,
        session_id: str,
        cart_items: list[dict[str, Any]] | None = None,
        viewed_product_ids: list[str] | None = None,
        hovered_product_ids: list[str] | None = None,
        historical_order_ids: list[str] | None = None,
        dwell_time_seconds: int = 30,
        search_query: str = "",
        category_affinity: str = "general",
    ) -> ShopperIntentState:
        """Infers the Markov state distribution, composite intent score, and price sensitivity."""
        cart_items = cart_items or []
        viewed_product_ids = viewed_product_ids or []
        hovered_product_ids = hovered_product_ids or []
        historical_order_ids = historical_order_ids or []

        # 1. Base evidence scoring
        has_cart = len(cart_items) > 0
        has_history = len(historical_order_ids) > 0
        dwell_recency = compute_recency_weight(dwell_time_seconds, self.gamma)
        effective_dwell = float(dwell_time_seconds) * dwell_recency

        evidence: dict[str, float] = {
            "DISCOVERY": 1.0,
            "PRODUCT_COMPARISON": 0.5,
            "PURCHASE_CONSIDERATION": 0.5,
            "CART_COMPLETION": 0.2,
            "REPLENISHMENT": 0.2,
        }

        # Dwell and search activity
        if search_query:
            evidence["DISCOVERY"] += 1.5
            evidence["PRODUCT_COMPARISON"] += 1.0

        # Comparative browsing (multiple items viewed)
        distinct_views = len(set(viewed_product_ids))
        if distinct_views >= 2:
            evidence["PRODUCT_COMPARISON"] += float(distinct_views) * 1.8
            evidence["DISCOVERY"] = max(0.5, evidence["DISCOVERY"] * 0.7)

        # Deep consideration (high dwell or hovered items)
        distinct_hovers = len(set(hovered_product_ids))
        if distinct_hovers > 0 or effective_dwell > 45:
            evidence["PURCHASE_CONSIDERATION"] += (float(distinct_hovers) * 3.0) + (effective_dwell / 20.0)

        # Cart active
        if has_cart:
            total_cart_units = sum(int(item.get("quantity", 1)) for item in cart_items)
            evidence["CART_COMPLETION"] += 14.0 + (float(total_cart_units) * 3.0)
            evidence["PURCHASE_CONSIDERATION"] += 2.0

        # Returning customer replenishment affinity
        if has_history:
            evidence["REPLENISHMENT"] += 6.0 + (float(len(historical_order_ids)) * 1.5)

        # 2. Normalize posterior state distribution
        total_ev = sum(evidence.values())
        state_probs: dict[str, float] = {}
        for s in INTENT_STATES:
            state_probs[s] = round(evidence[s] / total_ev, 4)

        # Identify dominant state
        dominant_state = max(state_probs.items(), key=lambda kv: kv[1])[0]

        # 3. Composite purchase intent score in [0.0, 1.0]
        # Weighted expectation of state conversion priors
        base_conversion = sum(state_probs[s] * STATE_CONVERSION_PRIORS[s] for s in INTENT_STATES)
        # Boost by dwell saturation and active cart commitment
        dwell_boost = min(0.12, (effective_dwell / 300.0) * 0.12)
        state_bonus = 0.10 if dominant_state == "CART_COMPLETION" else (0.05 if dominant_state == "PURCHASE_CONSIDERATION" else 0.0)
        intent_score = round(min(0.98, max(0.05, base_conversion + dwell_boost + state_bonus)), 3)

        # 4. State uncertainty / transition entropy
        entropy = compute_transition_entropy(state_probs)

        # 5. Price sensitivity estimation
        # High intent / cart completion -> lower price sensitivity (they already intend to buy!)
        # Discovery / Comparison -> higher sensitivity (a nudge can convert them, but don't give away margin on scarce stock)
        if dominant_state == "CART_COMPLETION":
            price_sens = 0.75 if intent_score > 0.65 else 0.90
        elif dominant_state == "PURCHASE_CONSIDERATION":
            price_sens = 1.05
        elif dominant_state == "PRODUCT_COMPARISON":
            price_sens = 1.35
        elif dominant_state == "REPLENISHMENT":
            price_sens = 0.85
        else:  # DISCOVERY
            price_sens = 1.20

        return ShopperIntentState(
            session_id=session_id,
            current_state=dominant_state,
            state_probabilities=state_probs,
            intent_score=intent_score,
            decayed_dwell_seconds=round(effective_dwell, 1),
            transition_entropy=entropy,
            top_category_affinity=category_affinity,
            price_sensitivity_estimate=round(price_sens, 2),
        )
