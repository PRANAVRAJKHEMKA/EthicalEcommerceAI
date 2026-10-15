"""Association Rule Mining & Synthetic History Engine for FairCart AI

Implements Apriori-style frequent itemset mining, Laplace-smoothed confidence,
and bounded lift metrics over reproducible synthetic transaction sessions (seed=42).

Mathematical guarantees:
1. Frequent itemsets mined with bounded itemset size (<= 4) and antecedent size (<= 3).
2. Minimum support count: minCount = max(3, ceil(0.005 * N)).
3. Laplace-smoothed confidence:
       conf_smooth(X -> p) = (count(X U {p}) + alpha) / (count(X) + 2 * alpha), alpha = 1.0
4. Lift metric:
       lift(X -> p) = conf(X -> p) / support(p), with safe positive denominator guards.
5. Bounded association strength:
       r_X = min(1.0, count(X U {p}) / minCount)
       L_X = max(0, ln(lift)) / (1 + max(0, ln(lift)))
       A(p, B) = max_{X subseteq B, 1 <= |X| <= 3} [ r_X * conf_smooth * L_X ]
6. Session-grouped 80/20 train/test split: rules are mined strictly from training baskets.
7. Explicit synthetic provenance markers on all generated records.
"""

from collections import defaultdict
from dataclasses import dataclass, field
import itertools
import math
import random
import sqlite3

# Context archetypes representing distinct setup personas
CONTEXT_ARCHETYPES: dict[str, list[list[str]]] = {
    "productivity": [
        ["item-001", "item-002", "item-003", "item-004", "item-013"],
        ["item-001", "item-002", "item-008", "item-025", "item-026"],
        ["item-003", "item-004", "item-011", "item-016", "item-029"],
    ],
    "gaming": [
        ["item-001", "item-004", "item-007", "item-021", "item-022"],
        ["item-005", "item-006", "item-007", "item-022", "item-026"],
        ["item-001", "item-006", "item-014", "item-021", "item-032"],
    ],
    "study": [
        ["item-008", "item-014", "item-015", "item-023", "item-024"],
        ["item-001", "item-002", "item-015", "item-024", "item-028"],
        ["item-003", "item-008", "item-010", "item-023", "item-027"],
    ],
    "travel": [
        ["item-003", "item-017", "item-018", "item-019", "item-020"],
        ["item-010", "item-016", "item-017", "item-019", "item-020"],
        ["item-002", "item-017", "item-018", "item-027", "item-028"],
    ],
    "wellness": [
        ["item-001", "item-002", "item-004", "item-013", "item-030"],
        ["item-002", "item-004", "item-008", "item-013", "item-031"],
        ["item-001", "item-004", "item-013", "item-024", "item-030"],
    ],
}

ALL_CONTEXTS = list(CONTEXT_ARCHETYPES.keys())

@dataclass
class SyntheticInteractionEvent:
    """Represents a validated synthetic shopper interaction event."""
    session_id: str
    event_type: str
    product_id: str
    shopping_context: str
    age_hours: float
    is_synthetic: bool = True

@dataclass
class SyntheticSession:
    """Represents a complete synthetic customer session with ground-truth preferences."""
    session_id: str
    shopping_context: str
    basket: set[str]
    viewed_product_ids: list[str]
    events: list[SyntheticInteractionEvent]
    latent_preference_vector: dict[str, float] = field(default_factory=dict)
    is_synthetic: bool = True

@dataclass(frozen=True)
class AssociationRule:
    """Represents an association rule: Antecedents X -> Consequent p."""
    antecedent_ids: tuple[str, ...]
    consequent_id: str
    antecedent_count: int
    union_count: int
    support: float
    confidence: float
    confidence_smooth: float
    lift: float
    is_multi_item: bool

@dataclass(frozen=True)
class AssociationMatch:
    """Result of evaluating candidate against active shopping basket."""
    candidate_id: str
    support: float
    confidence: float
    confidence_smooth: float
    lift: float
    matched_antecedent: tuple[str, ...]
    is_multi_item: bool
    explanation_note: str
    bounded_strength: float

def generate_synthetic_sessions(
    num_sessions: int = 2000,
    seed: int = 42,
) -> list[SyntheticSession]:
    """Generates a reproducible dataset of synthetic sessions and baskets.
    
    The generator simulates distinct shopping personas, latent category affinities,
    and browsing interaction events with provenance markers.
    """
    rng = random.Random(seed)
    sessions: list[SyntheticSession] = []

    for idx in range(num_sessions):
        sess_id = f"synth-sess-{idx:04d}"
        context = rng.choice(ALL_CONTEXTS)
        archetypes = CONTEXT_ARCHETYPES[context]
        primary_arch = rng.choice(archetypes)

        # Basket size between 2 and 5 items
        basket_size = rng.randint(2, min(5, len(primary_arch)))
        basket = set(rng.sample(primary_arch, basket_size))

        # 25% chance of cross-pollinating a complementary item from another archetype
        if rng.random() < 0.25:
            other_context = rng.choice(ALL_CONTEXTS)
            other_item = rng.choice(rng.choice(CONTEXT_ARCHETYPES[other_context]))
            basket.add(other_item)

        # Browsing history: viewed items include basket items plus 1-3 browsed non-purchased items
        viewed = list(basket)
        extra_views = rng.sample(primary_arch, k=min(2, len(primary_arch)))
        for ev in extra_views:
            if ev not in viewed:
                viewed.append(ev)

        # Generate event timeline with decay timestamps
        events: list[SyntheticInteractionEvent] = []
        for v in viewed:
            age = round(rng.uniform(0.1, 48.0), 2)
            events.append(SyntheticInteractionEvent(
                session_id=sess_id,
                event_type="product_view",
                product_id=v,
                shopping_context=context,
                age_hours=age,
                is_synthetic=True,
            ))

        for b in basket:
            age = round(rng.uniform(0.05, 12.0), 2)
            events.append(SyntheticInteractionEvent(
                session_id=sess_id,
                event_type="add_to_cart",
                product_id=b,
                shopping_context=context,
                age_hours=age,
                is_synthetic=True,
            ))

        # Latent preference vector (unobserved by the model)
        latent_prefs = {
            "ergonomic_affinity": rng.uniform(0.1, 0.9),
            "aesthetic_affinity": rng.uniform(0.1, 0.9),
            "price_sensitivity": rng.uniform(0.2, 0.8),
            "performance_affinity": rng.uniform(0.1, 0.9),
        }

        sessions.append(SyntheticSession(
            session_id=sess_id,
            shopping_context=context,
            basket=basket,
            viewed_product_ids=viewed,
            events=events,
            latent_preference_vector=latent_prefs,
            is_synthetic=True,
        ))

    return sessions

def split_sessions(
    sessions: list[SyntheticSession],
    train_ratio: float = 0.8,
) -> tuple[list[SyntheticSession], list[SyntheticSession]]:
    """Performs a strict session-grouped split to ensure zero cross-split leakage."""
    split_idx = int(len(sessions) * train_ratio)
    train_sessions = sessions[:split_idx]
    test_sessions = sessions[split_idx:]
    return train_sessions, test_sessions

class AssociationRuleEngine:
    """Apriori frequent-itemset miner and association rule engine for FairCart AI."""

    def __init__(
        self,
        sessions: list[SyntheticSession] | None = None,
        min_support_pct: float = 0.005,
        alpha: float = 1.0,
        seed: int = 42,
    ):
        self.alpha = alpha
        self.min_support_pct = min_support_pct
        self.seed = seed

        # If sessions not provided, generate deterministic training sessions
        if sessions is None:
            all_sessions = generate_synthetic_sessions(num_sessions=2000, seed=self.seed)
            train_sessions, _ = split_sessions(all_sessions, train_ratio=0.8)
            self.sessions = train_sessions
        else:
            self.sessions = sessions

        self.num_transactions = max(1, len(self.sessions))
        # Mathematical threshold: minCount = max(3, ceil(0.005 * N))
        self.min_count = max(3, math.ceil(self.min_support_pct * self.num_transactions))

        self.itemset_counts: dict[tuple[str, ...], int] = defaultdict(int)
        self.rules_by_antecedent: dict[tuple[str, ...], list[AssociationRule]] = defaultdict(list)
        self._mine_apriori()

    def _mine_apriori(self) -> None:
        """Mines frequent itemsets up to size 4 and rules with antecedent size <= 3."""
        # 1. Mine itemset frequencies for size 1, 2, 3, 4
        baskets = [sorted(list(s.basket)) for s in self.sessions]

        # L1: Frequent 1-itemsets
        c1: dict[str, int] = defaultdict(int)
        for b in baskets:
            for item in b:
                c1[item] += 1

        frequent_single_items = {k for k, v in c1.items() if v >= self.min_count}
        for item, cnt in c1.items():
            self.itemset_counts[(item,)] = cnt

        # Filter baskets to frequent items only
        pruned_baskets = [[item for item in b if item in frequent_single_items] for b in baskets]

        # L2, L3, L4: Candidate generation and frequency counting
        for k in (2, 3, 4):
            ck: dict[tuple[str, ...], int] = defaultdict(int)
            for b in pruned_baskets:
                if len(b) >= k:
                    for combo in itertools.combinations(b, k):
                        ck[combo] += 1
            for combo, cnt in ck.items():
                if cnt >= self.min_count:
                    self.itemset_counts[combo] = cnt

        # 2. Rule generation from frequent itemsets of size 2, 3, 4
        n = float(self.num_transactions)

        for itemset, union_count in self.itemset_counts.items():
            k = len(itemset)
            if k < 2 or union_count < self.min_count:
                continue

            itemset_set = set(itemset)
            rule_support = union_count / n

            # Consequent p can be any single item in the itemset
            for p in itemset:
                antecedent = tuple(sorted(itemset_set - {p}))
                if len(antecedent) > 3 or not antecedent:
                    continue

                ant_count = self.itemset_counts.get(antecedent, 0)
                if ant_count == 0:
                    continue

                consequent_sup = self.itemset_counts.get((p,), 0) / n
                if consequent_sup <= 0.0:
                    continue

                # Mathematical formulas from spec:
                raw_confidence = union_count / ant_count
                # Laplace-smoothed confidence: (count(X U {p}) + alpha) / (count(X) + 2 * alpha)
                smooth_confidence = (union_count + self.alpha) / (ant_count + 2.0 * self.alpha)
                # Lift: confidence / support(p)
                lift = raw_confidence / consequent_sup

                rule = AssociationRule(
                    antecedent_ids=antecedent,
                    consequent_id=p,
                    antecedent_count=ant_count,
                    union_count=union_count,
                    support=round(rule_support, 4),
                    confidence=round(raw_confidence, 4),
                    confidence_smooth=round(smooth_confidence, 4),
                    lift=round(lift, 4),
                    is_multi_item=(len(antecedent) >= 2),
                )
                self.rules_by_antecedent[antecedent].append(rule)

        # Sort rules by lift and confidence descending
        for ant in self.rules_by_antecedent:
            self.rules_by_antecedent[ant].sort(key=lambda r: (r.lift, r.confidence_smooth), reverse=True)

    def evaluate_association_score(
        self,
        candidate_id: str,
        cart_product_ids: tuple[str, ...],
    ) -> tuple[float, AssociationMatch | None]:
        """Calculates exact A(p, B) using bounded lift and Laplace confidence.
        
        Formula:
            r_X = min(1.0, count(X U {p}) / minCount)
            L_X = max(0, ln(lift)) / (1 + max(0, ln(lift)))
            A(p, B) = max_{X subseteq B, 1 <= |X| <= 3} [ r_X * conf_smooth * L_X ]
        """
        if not cart_product_ids or candidate_id in cart_product_ids:
            return 0.0, None

        best_score = 0.0
        best_match: AssociationMatch | None = None
        cart_set = set(cart_product_ids)

        # Check all subsets X subseteq B with 1 <= |X| <= min(3, len(B))
        for ant_size in range(1, min(4, len(cart_set) + 1)):
            for ant in itertools.combinations(sorted(cart_set), ant_size):
                rules = self.rules_by_antecedent.get(ant, [])
                for rule in rules:
                    if rule.consequent_id == candidate_id:
                        # 1. Support ratio r_X
                        r_x = min(1.0, rule.union_count / float(self.min_count))
                        # 2. Bounded lift L_X
                        ln_lift = math.log(max(rule.lift, 1e-9))
                        pos_ln_lift = max(0.0, ln_lift)
                        l_x = pos_ln_lift / (1.0 + pos_ln_lift)
                        # 3. Strength score
                        strength = r_x * rule.confidence_smooth * l_x

                        if strength > best_score:
                            best_score = strength
                            note = (
                                f"Multi-item co-purchase pattern (lift: {rule.lift:.1f}x, confidence: {int(rule.confidence_smooth * 100)}%)"
                                if rule.is_multi_item
                                else f"Frequently paired in completed desk setups (lift: {rule.lift:.1f}x)"
                            )
                            best_match = AssociationMatch(
                                candidate_id=candidate_id,
                                support=rule.support,
                                confidence=rule.confidence,
                                confidence_smooth=rule.confidence_smooth,
                                lift=rule.lift,
                                matched_antecedent=rule.antecedent_ids,
                                is_multi_item=rule.is_multi_item,
                                explanation_note=note,
                                bounded_strength=round(strength, 4),
                            )

        return round(best_score, 4), best_match

    def evaluate_basket_candidate(
        self,
        cart_product_ids: tuple[str, ...],
        candidate_id: str,
    ) -> AssociationMatch | None:
        """Backward-compatible helper evaluating best rule match for candidate."""
        _, match = self.evaluate_association_score(candidate_id, cart_product_ids)
        return match

    def get_candidate_ids_for_basket(
        self,
        cart_product_ids: tuple[str, ...],
        max_candidates: int = 15,
    ) -> list[tuple[str, float]]:
        """Returns candidate product IDs from mined rules matching cart antecedents."""
        candidates: dict[str, float] = defaultdict(float)
        cart_set = set(cart_product_ids)

        for ant_size in range(1, min(4, len(cart_set) + 1)):
            for ant in itertools.combinations(sorted(cart_set), ant_size):
                for rule in self.rules_by_antecedent.get(ant, []):
                    if rule.consequent_id not in cart_set:
                        score, _ = self.evaluate_association_score(rule.consequent_id, cart_product_ids)
                        candidates[rule.consequent_id] = max(candidates[rule.consequent_id], score)

        ranked = sorted(candidates.items(), key=lambda x: x[1], reverse=True)
        return ranked[:max_candidates]

    def sync_to_sqlite(self, conn: sqlite3.Connection) -> int:
        """Persists precomputed association rules to SQLite for inspection."""
        cursor = conn.cursor()
        cursor.execute("DELETE FROM basket_association_rules;")
        count = 0

        for ant, rules in self.rules_by_antecedent.items():
            ant_str = ",".join(ant)
            for r in rules:
                rule_id = f"rule-{ant_str}->{r.consequent_id}"
                cursor.execute("""
                    INSERT OR REPLACE INTO basket_association_rules
                    (id, antecedent_ids, consequent_id, support, confidence, lift, co_occurrence_count, is_synthetic)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1);
                """, (rule_id, ant_str, r.consequent_id, r.support, r.confidence_smooth, r.lift, r.union_count))
                count += 1

        conn.commit()
        return count

# Default singleton engine instance mined from training split of synthetic transactions
_default_engine: AssociationRuleEngine | None = None

def get_association_engine() -> AssociationRuleEngine:
    global _default_engine
    if _default_engine is None:
        _default_engine = AssociationRuleEngine()
    return _default_engine
