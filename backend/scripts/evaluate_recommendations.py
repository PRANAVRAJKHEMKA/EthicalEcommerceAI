"""Offline Model & Ranker Quality Evaluation Harness for FairCart AI

Compares the Improved Multi-Signal Whole-Basket Ranker against the Baseline 1-to-1 Recommender.
Uses held-out synthetic baskets (seed=100) to evaluate:
- HitRate@K: Proportion of baskets where the held-out co-purchased item is in top-K.
- Recall@K: Proportion of relevant held-out items retrieved.
- NDCG@K: Normalized Discounted Cumulative Gain (ranking position sensitivity).
- Catalog Coverage: Percentage of catalog accessories recommended across all test sessions.
- Category Diversity: Average number of unique categories present in top-K recommendations.

DISCLAIMER & LIMITATIONS:
This evaluation uses synthetic transactions generated from archetypal desk configurations.
It validates pipeline mechanics, multi-item association integration, and diversity guardrails.
It does NOT prove real-world consumer conversion uplift or production commercial ROI.
"""

import math
from collections import Counter
from dataclasses import dataclass
from backend.app.db.repository import CatalogRepository, ProductEntity
from backend.app.engine.associations import generate_synthetic_transactions, AssociationRuleEngine
from backend.app.engine.recommender import RecommenderEngine

@dataclass
class EvaluationMetrics:
    hit_rate_at_k: float
    recall_at_k: float
    ndcg_at_k: float
    catalog_coverage_pct: float
    avg_category_diversity: float

def dcg_at_k(r: list[int], k: int) -> float:
    """Computes Discounted Cumulative Gain at rank K."""
    dcg = 0.0
    for i in range(min(len(r), k)):
        dcg += r[i] / math.log2(i + 2)
    return dcg

def ndcg_at_k(r: list[int], k: int) -> float:
    """Computes Normalized Discounted Cumulative Gain at rank K."""
    actual_dcg = dcg_at_k(r, k)
    ideal_dcg = dcg_at_k(sorted(r, reverse=True), k)
    if ideal_dcg <= 0.0:
        return 0.0
    return actual_dcg / ideal_dcg

def evaluate_baseline_recommender(
    test_cases: list[tuple[list[ProductEntity], str]],
    catalog: list[ProductEntity],
    k: int = 4,
) -> EvaluationMetrics:
    """Evaluates the simple 1-to-1 baseline recommender (using only the first cart item)."""
    hits = 0
    total_recall = 0.0
    total_ndcg = 0.0
    recommended_product_ids: set[str] = set()
    category_diversity_sum = 0.0
    num_eval = len(test_cases)

    catalog_by_id = {p.id: p for p in catalog}

    for input_entities, target_id in test_cases:
        if not input_entities:
            continue

        # Baseline logic: recommend based strictly on first product's complementary_ids
        primary = input_entities[0]
        recs = [catalog_by_id[cid] for cid in primary.complementary_ids if cid in catalog_by_id and cid != primary.id][:k]
        rec_ids = [p.id for p in recs]

        for rid in rec_ids:
            recommended_product_ids.add(rid)

        # HitRate & Recall
        relevance_vector = [1 if rid == target_id else 0 for rid in rec_ids]
        is_hit = 1 if target_id in rec_ids else 0
        hits += is_hit
        total_recall += is_hit
        total_ndcg += ndcg_at_k(relevance_vector, k)

        # Diversity
        cats = len({p.category for p in recs})
        category_diversity_sum += cats

    accessory_count = sum(1 for p in catalog if p.category in {"Accessories", "Power & Cables", "Workspace"})
    coverage = (len(recommended_product_ids) / max(1, accessory_count)) * 100.0

    return EvaluationMetrics(
        hit_rate_at_k=round(hits / num_eval, 4),
        recall_at_k=round(total_recall / num_eval, 4),
        ndcg_at_k=round(total_ndcg / num_eval, 4),
        catalog_coverage_pct=round(coverage, 2),
        avg_category_diversity=round(category_diversity_sum / num_eval, 2),
    )

def evaluate_improved_recommender(
    test_cases: list[tuple[list[ProductEntity], str]],
    catalog: list[ProductEntity],
    engine: RecommenderEngine,
    k: int = 4,
) -> EvaluationMetrics:
    """Evaluates the multi-signal whole-basket context-aware ranker."""
    hits = 0
    total_recall = 0.0
    total_ndcg = 0.0
    recommended_product_ids: set[str] = set()
    category_diversity_sum = 0.0
    num_eval = len(test_cases)

    for input_entities, target_id in test_cases:
        cart_items = [(p, 1) for p in input_entities]
        recs = engine.find_recommendations(cart_items, catalog, shopping_context="productivity", top_k=k)
        rec_ids = [r.product.id for r in recs]

        for rid in rec_ids:
            recommended_product_ids.add(rid)

        relevance_vector = [1 if rid == target_id else 0 for rid in rec_ids]
        is_hit = 1 if target_id in rec_ids else 0
        hits += is_hit
        total_recall += is_hit
        total_ndcg += ndcg_at_k(relevance_vector, k)

        cats = len({r.product.category for r in recs})
        category_diversity_sum += cats

    accessory_count = sum(1 for p in catalog if p.category in {"Accessories", "Power & Cables", "Workspace"})
    coverage = (len(recommended_product_ids) / max(1, accessory_count)) * 100.0

    return EvaluationMetrics(
        hit_rate_at_k=round(hits / num_eval, 4),
        recall_at_k=round(total_recall / num_eval, 4),
        ndcg_at_k=round(total_ndcg / num_eval, 4),
        catalog_coverage_pct=round(coverage, 2),
        avg_category_diversity=round(category_diversity_sum / num_eval, 2),
    )

def run_offline_evaluation(k: int = 4) -> dict[str, EvaluationMetrics]:
    """Generates holdout test cases and runs comparative evaluation."""
    repo = CatalogRepository()
    catalog = repo.get_all_entities()
    catalog_by_id = {p.id: p for p in catalog}

    # Generate held-out test transactions with separate seed (seed=100)
    raw_txns = generate_synthetic_transactions(num_transactions=250, seed=100)
    test_cases: list[tuple[list[ProductEntity], str]] = []

    for txn in raw_txns:
        if len(txn) >= 3:
            # Mask the last item as the target co-purchase
            target_id = txn[-1]
            input_ids = txn[:-1]
            input_entities = [catalog_by_id[pid] for pid in input_ids if pid in catalog_by_id]
            if input_entities and target_id in catalog_by_id:
                test_cases.append((input_entities, target_id))

    # Evaluate baseline
    baseline_metrics = evaluate_baseline_recommender(test_cases, catalog, k=k)

    # Evaluate improved multi-signal ranker
    assoc_engine = AssociationRuleEngine(seed=42)
    improved_engine = RecommenderEngine(association_engine=assoc_engine)
    improved_metrics = evaluate_improved_recommender(test_cases, catalog, improved_engine, k=k)

    return {
        "baseline": baseline_metrics,
        "improved": improved_metrics,
    }

if __name__ == "__main__":
    print("=" * 70)
    print("FAIRCART AI — OFFLINE RECOMMENDATION QUALITY EVALUATION")
    print("Held-Out Synthetic Transactions (N=200+, K=4)")
    print("=" * 70)

    results = run_offline_evaluation(k=4)
    base = results["baseline"]
    impr = results["improved"]

    print(f"{'METRIC':<25} | {'BASELINE (1-to-1)':<18} | {'IMPROVED (Whole-Basket)':<20} | {'DELTA':<10}")
    print("-" * 75)
    print(f"{'HitRate@4':<25} | {base.hit_rate_at_k:<18.4f} | {impr.hit_rate_at_k:<20.4f} | {impr.hit_rate_at_k - base.hit_rate_at_k:+.4f}")
    print(f"{'Recall@4':<25} | {base.recall_at_k:<18.4f} | {impr.recall_at_k:<20.4f} | {impr.recall_at_k - base.recall_at_k:+.4f}")
    print(f"{'NDCG@4':<25} | {base.ndcg_at_k:<18.4f} | {impr.ndcg_at_k:<20.4f} | {impr.ndcg_at_k - base.ndcg_at_k:+.4f}")
    print(f"{'Catalog Coverage (%)':<25} | {base.catalog_coverage_pct:<18.1f}% | {impr.catalog_coverage_pct:<20.1f}% | {impr.catalog_coverage_pct - base.catalog_coverage_pct:+.1f}%")
    print(f"{'Avg Category Diversity':<25} | {base.avg_category_diversity:<18.2f} | {impr.avg_category_diversity:<20.2f} | {impr.avg_category_diversity - base.avg_category_diversity:+.2f}")
    print("=" * 75)
    print("NOTE: Evaluation is conducted on synthetic transaction data to validate pipeline mechanics.")
    print("It demonstrates multi-item synergy and diversity gains, not real consumer uplift.")
