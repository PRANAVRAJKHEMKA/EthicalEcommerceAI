"""Association Rule Engine & Synthetic Transaction Miner for FairCart AI

Provides item-to-item and multi-item basket association mining based on reproducible
synthetic transaction history. Computes support, confidence, and lift metrics with strict
zero-denominator safeguards.

NOTE: All historical transactions are deterministically generated synthetic data (seed=42)
used to exercise multi-item basket algorithms and demonstrate association mechanics.
They do NOT represent real customer purchasing history.
"""

from dataclasses import dataclass
from collections import defaultdict
import itertools
import random
import sqlite3

@dataclass(frozen=True)
class AssociationRule:
    """Represents a directional association rule: Antecedents -> Consequent."""
    antecedent_ids: tuple[str, ...]
    consequent_id: str
    support: float       # P(Antecedent U Consequent)
    confidence: float    # P(Consequent | Antecedent)
    lift: float          # P(Antecedent U Consequent) / (P(Antecedent) * P(Consequent))
    co_occurrence_count: int
    is_multi_item: bool  # True if len(antecedent_ids) >= 2

@dataclass(frozen=True)
class AssociationMatch:
    """Evaluation result for a candidate product against an active shopping basket."""
    candidate_id: str
    support: float
    confidence: float
    lift: float
    matched_antecedent: tuple[str, ...]
    is_multi_item: bool
    explanation_note: str

# Archetypal basket seeds representing common tech desk configurations
BASKET_ARCHETYPES = [
    # 1. Ergonomic Productivity Setup
    ["item-001", "item-002", "item-003", "item-004", "item-013"],
    # 2. Mechanical Keyboard Customizer
    ["item-001", "item-002", "item-005", "item-006", "item-007"],
    # 3. Creator & Streaming Workstation
    ["item-008", "item-009", "item-010", "item-011", "item-012"],
    # 4. Focus, Study & Remote Work
    ["item-008", "item-014", "item-015", "item-023", "item-024"],
    # 5. Mobile & Road Warrior Setup
    ["item-003", "item-017", "item-018", "item-019", "item-020"],
    # 6. High-Performance Esports / Gaming
    ["item-001", "item-004", "item-007", "item-021", "item-022"],
    # 7. Desk Cable Management & Minimalist Power
    ["item-011", "item-016", "item-025", "item-029", "item-031"],
    # 8. Dual-Display Ergonomics
    ["item-004", "item-008", "item-029", "item-030", "item-031"],
    # 9. Compact Audio & Hydration
    ["item-014", "item-015", "item-023", "item-024"],
    # 10. Peripheral Core Essentials
    ["item-001", "item-002", "item-003", "item-006"],
]

def generate_synthetic_transactions(num_transactions: int = 600, seed: int = 42) -> list[list[str]]:
    """Generates a reproducible set of synthetic transactions with realistic co-purchases."""
    rng = random.Random(seed)
    transactions: list[list[str]] = []

    for _ in range(num_transactions):
        # Pick 1 or 2 archetypes as the base intent
        archetype = rng.choice(BASKET_ARCHETYPES)
        # Basket size between 2 and 5 items
        basket_size = rng.randint(2, min(5, len(archetype)))
        basket = set(rng.sample(archetype, basket_size))

        # 25% chance to add a cross-category complementary item
        if rng.random() < 0.25:
            secondary = rng.choice(BASKET_ARCHETYPES)
            basket.add(rng.choice(secondary))

        transactions.append(sorted(list(basket)))

    return transactions

class AssociationRuleEngine:
    """Mines and evaluates association rules over synthetic transaction history."""

    def __init__(self, min_support: float = 0.01, min_confidence: float = 0.08, seed: int = 42):
        self.min_support = min_support
        self.min_confidence = min_confidence
        self.seed = seed
        self._rules_by_antecedent: dict[tuple[str, ...], list[AssociationRule]] = defaultdict(list)
        self._single_item_support: dict[str, float] = {}
        self._total_transactions: int = 0
        self._mine_rules()

    def _mine_rules(self) -> None:
        """Mines pair and triplet association rules from synthetic transaction data."""
        transactions = generate_synthetic_transactions(num_transactions=600, seed=self.seed)
        self._total_transactions = len(transactions)
        n = float(self._total_transactions)

        # 1. Compute single item frequency
        item_counts: dict[str, int] = defaultdict(int)
        pair_counts: dict[tuple[str, str], int] = defaultdict(int)
        triplet_counts: dict[tuple[str, str, str], int] = defaultdict(int)

        for txn in transactions:
            txn_set = set(txn)
            for item in txn:
                item_counts[item] += 1
            for p1, p2 in itertools.combinations(sorted(txn), 2):
                pair_counts[(p1, p2)] += 1
            for p1, p2, p3 in itertools.combinations(sorted(txn), 3):
                triplet_counts[(p1, p2, p3)] += 1

        for item, count in item_counts.items():
            self._single_item_support[item] = count / n

        # 2. Mine Pair Rules: A -> B and B -> A
        for (a, b), count in pair_counts.items():
            pair_sup = count / n
            if pair_sup < self.min_support:
                continue

            sup_a = self._single_item_support.get(a, 0.0)
            sup_b = self._single_item_support.get(b, 0.0)

            # Rule A -> B
            if sup_a > 0.0 and sup_b > 0.0:
                conf_ab = pair_sup / sup_a
                lift_ab = pair_sup / (sup_a * sup_b)
                if conf_ab >= self.min_confidence:
                    rule = AssociationRule(
                        antecedent_ids=(a,),
                        consequent_id=b,
                        support=round(pair_sup, 4),
                        confidence=round(conf_ab, 4),
                        lift=round(lift_ab, 4),
                        co_occurrence_count=count,
                        is_multi_item=False,
                    )
                    self._rules_by_antecedent[(a,)].append(rule)

            # Rule B -> A
            if sup_b > 0.0 and sup_a > 0.0:
                conf_ba = pair_sup / sup_b
                lift_ba = pair_sup / (sup_a * sup_b)
                if conf_ba >= self.min_confidence:
                    rule = AssociationRule(
                        antecedent_ids=(b,),
                        consequent_id=a,
                        support=round(pair_sup, 4),
                        confidence=round(conf_ba, 4),
                        lift=round(lift_ba, 4),
                        co_occurrence_count=count,
                        is_multi_item=False,
                    )
                    self._rules_by_antecedent[(b,)].append(rule)

        # 3. Mine Triplet Rules: {A1, A2} -> B
        for (p1, p2, p3), count in triplet_counts.items():
            trip_sup = count / n
            if trip_sup < self.min_support:
                continue

            for antecedent, consequent in [
                ((p1, p2), p3),
                ((p1, p3), p2),
                ((p2, p3), p1),
            ]:
                ant_tuple = tuple(sorted(antecedent))
                # Antecedent support = count of pair
                ant_count = pair_counts.get(ant_tuple, 0)
                if ant_count == 0:
                    continue
                ant_sup = ant_count / n
                con_sup = self._single_item_support.get(consequent, 0.0)

                if ant_sup > 0.0 and con_sup > 0.0:
                    conf = trip_sup / ant_sup
                    lift = trip_sup / (ant_sup * con_sup)
                    if conf >= self.min_confidence:
                        rule = AssociationRule(
                            antecedent_ids=ant_tuple,
                            consequent_id=consequent,
                            support=round(trip_sup, 4),
                            confidence=round(conf, 4),
                            lift=round(lift, 4),
                            co_occurrence_count=count,
                            is_multi_item=True,
                        )
                        self._rules_by_antecedent[ant_tuple].append(rule)

        # Sort all rule sets descending by lift and confidence
        for k in self._rules_by_antecedent:
            self._rules_by_antecedent[k].sort(key=lambda r: (r.lift, r.confidence), reverse=True)

    def evaluate_basket_candidate(
        self,
        cart_product_ids: tuple[str, ...],
        candidate_id: str,
    ) -> AssociationMatch | None:
        """Evaluates whether any item or multi-item subset in the cart has association with candidate.
        
        Prioritizes multi-item combinations {A, B} -> C over single items A -> C.
        Guarantees zero-denominator safety.
        """
        if not cart_product_ids:
            return None

        best_rule: AssociationRule | None = None

        # Check multi-item combinations first (e.g. pairs in cart -> candidate)
        if len(cart_product_ids) >= 2:
            for pair in itertools.combinations(sorted(cart_product_ids), 2):
                rules = self._rules_by_antecedent.get(pair, [])
                for r in rules:
                    if r.consequent_id == candidate_id:
                        if best_rule is None or r.lift > best_rule.lift:
                            best_rule = r

        # Check single-item antecedents
        for item_id in cart_product_ids:
            rules = self._rules_by_antecedent.get((item_id,), [])
            for r in rules:
                if r.consequent_id == candidate_id:
                    # Prefer multi-item if available, else compare lift
                    if best_rule is None:
                        best_rule = r
                    elif not best_rule.is_multi_item and r.lift > best_rule.lift:
                        best_rule = r

        if not best_rule:
            return None

        # Format transparent, grounded note
        if best_rule.is_multi_item:
            note = f"Multi-item co-purchase pattern (lift: {best_rule.lift:.1f}x, confidence: {int(best_rule.confidence * 100)}%)"
        else:
            note = f"Frequently paired in completed desk setups (lift: {best_rule.lift:.1f}x)"

        return AssociationMatch(
            candidate_id=candidate_id,
            support=best_rule.support,
            confidence=best_rule.confidence,
            lift=best_rule.lift,
            matched_antecedent=best_rule.antecedent_ids,
            is_multi_item=best_rule.is_multi_item,
            explanation_note=note,
        )

    def get_candidate_ids_for_basket(
        self,
        cart_product_ids: tuple[str, ...],
        max_candidates: int = 15,
    ) -> list[tuple[str, float]]:
        """Returns candidate product IDs mined from association rules with antecedent matching."""
        candidate_scores: dict[str, float] = defaultdict(float)

        # 1. Multi-item antecedents
        if len(cart_product_ids) >= 2:
            for pair in itertools.combinations(sorted(cart_product_ids), 2):
                for r in self._rules_by_antecedent.get(pair, []):
                    if r.consequent_id not in cart_product_ids:
                        score = min(1.0, (r.lift - 1.0) / 4.0) * 0.6 + r.confidence * 0.4
                        candidate_scores[r.consequent_id] = max(candidate_scores[r.consequent_id], score)

        # 2. Single-item antecedents
        for item_id in cart_product_ids:
            for r in self._rules_by_antecedent.get((item_id,), []):
                if r.consequent_id not in cart_product_ids:
                    score = min(1.0, (r.lift - 1.0) / 4.0) * 0.5 + r.confidence * 0.5
                    candidate_scores[r.consequent_id] = max(candidate_scores[r.consequent_id], score)

        ranked = sorted(candidate_scores.items(), key=lambda x: x[1], reverse=True)
        return ranked[:max_candidates]

    def sync_to_sqlite(self, conn: sqlite3.Connection) -> int:
        """Persists precomputed association rules to SQLite for inspection and transparency."""
        cursor = conn.cursor()
        cursor.execute("DELETE FROM basket_association_rules;")
        count = 0

        for ant, rules in self._rules_by_antecedent.items():
            ant_str = ",".join(ant)
            for r in rules:
                rule_id = f"rule-{ant_str}->{r.consequent_id}"
                cursor.execute("""
                    INSERT OR REPLACE INTO basket_association_rules
                    (id, antecedent_ids, consequent_id, support, confidence, lift, co_occurrence_count, is_synthetic)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1);
                """, (rule_id, ant_str, r.consequent_id, r.support, r.confidence, r.lift, r.co_occurrence_count))
                count += 1

        conn.commit()
        return count

# Singleton in-memory engine instance initialized with deterministic seed
_default_association_engine: AssociationRuleEngine | None = None

def get_association_engine() -> AssociationRuleEngine:
    global _default_association_engine
    if _default_association_engine is None:
        _default_association_engine = AssociationRuleEngine()
    return _default_association_engine
