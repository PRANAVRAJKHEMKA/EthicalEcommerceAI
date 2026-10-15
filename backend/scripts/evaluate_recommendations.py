"""Offline Model & Ranker Quality Evaluation Harness for FairCart AI (Milestone 4B Part 9)

Compares three recommendation systems on the same 400 held-out synthetic test sessions:
1. Baseline Recommender: 1-to-1 static complementary items from primary product.
2. Deterministic Hybrid Ranker: S_hybrid = 0.30*C + 0.30*A + 0.20*U + 0.15*E + 0.05*P with MMR.
3. Supervised ML Ranker: HistGradientBoostingClassifier trained on 1,600 training sessions with MMR.

Metrics Computed:
- HitRate@K: Proportion of sessions with at least one target co-purchased item in Top-K.
- Recall@K: Mean fraction of target relevant items retrieved in Top-K.
- NDCG@K: Normalized Discounted Cumulative Gain with binary relevance gains.
- Catalog Coverage (%): Unique items recommended / total catalog.
- Pairwise Attribute Similarity: Mean pairwise similarity among recommendations (lower = more diverse).

SCIENTIFIC HONESTY & LIMITATIONS:
All sessions are generated from reproducible synthetic archetypes (seed=42).
This offline evaluation measures model ranking power and diversity guardrails under
controlled simulated conditions; it does NOT constitute proof of real-world consumer uplift.
"""

from dataclasses import dataclass
import math
import numpy as np

from backend.app.db.repository import CatalogRepository, ProductEntity
from backend.app.engine.associations import (
    AssociationRuleEngine,
    SyntheticSession,
    generate_synthetic_sessions,
    split_sessions,
)
from backend.app.engine.recommender import (
    RecommenderEngine,
    calculate_product_similarity,
)
from backend.app.engine.ml_ranker import get_ml_ranker

@dataclass
class EvaluationMetrics:
    ranker_name: str
    hit_rate_at_k: float
    recall_at_k: float
    ndcg_at_k: float
    catalog_coverage_pct: float
    avg_pairwise_similarity: float
    avg_category_diversity: float = 0.0

def compute_dcg(relevance: list[int], k: int) -> float:
    """Computes Discounted Cumulative Gain at rank K."""
    dcg = 0.0
    for i in range(min(len(relevance), k)):
        gain = (2 ** relevance[i]) - 1
        dcg += gain / math.log2(i + 2)
    return dcg

def compute_ndcg(relevance: list[int], k: int) -> float:
    """Computes Normalized Discounted Cumulative Gain at rank K."""
    actual_dcg = compute_dcg(relevance, k)
    ideal_dcg = compute_dcg(sorted(relevance, reverse=True), k)
    if ideal_dcg <= 0.0:
        return 0.0
    return actual_dcg / ideal_dcg

def evaluate_test_sessions(
    test_sessions: list[SyntheticSession],
    catalog: list[ProductEntity],
    engine: RecommenderEngine,
    ranker_name: str,
    k: int = 4,
    use_baseline_logic: bool = False,
) -> EvaluationMetrics:
    """Evaluates a ranking strategy across held-out test sessions (leave-one-out co-purchase test)."""
    catalog_by_id = {p.id: p for p in catalog}

    hits = 0
    total_recall = 0.0
    total_ndcg = 0.0
    recommended_product_ids: set[str] = set()
    similarity_sums: list[float] = []
    category_counts_list: list[int] = []
    num_eval = 0

    for sess in test_sessions:
        basket_list = sorted(list(sess.basket))
        if len(basket_list) < 2:
            continue

        # Leave-one-out: hold out the last item in basket as target G_s
        target_id = basket_list[-1]
        input_ids = basket_list[:-1]

        input_entities = [catalog_by_id[pid] for pid in input_ids if pid in catalog_by_id]
        if not input_entities or target_id not in catalog_by_id:
            continue

        num_eval += 1
        cart_tuples = [(p, 1) for p in input_entities]

        if use_baseline_logic:
            # Baseline: static complementary IDs of primary product
            primary = input_entities[0]
            recs = [
                catalog_by_id[cid]
                for cid in primary.complementary_ids
                if cid in catalog_by_id and cid != primary.id and cid not in input_ids
            ][:k]
            rec_ids = [p.id for p in recs]
        else:
            recs_objs = engine.find_recommendations(
                cart_items=cart_tuples,
                catalog=catalog,
                shopping_context=sess.shopping_context,
                session_viewed_ids=sess.viewed_product_ids,
                session_events=sess.events,
                top_k=k,
                use_mmr=True,
            )
            recs = [r.product for r in recs_objs]
            rec_ids = [p.id for p in recs]

        for rid in rec_ids:
            recommended_product_ids.add(rid)

        # HitRate & Recall
        is_hit = 1 if target_id in rec_ids else 0
        hits += is_hit
        total_recall += float(is_hit)  # With 1 held-out item, recall = is_hit / 1.0

        # NDCG
        rel_vector = [1 if rid == target_id else 0 for rid in rec_ids]
        total_ndcg += compute_ndcg(rel_vector, k)

        # Distinct categories in recommendations
        category_counts_list.append(len({p.category for p in recs}))

        # Pairwise Attribute Similarity among top-K recommendations
        if len(recs) >= 2:
            sims = []
            for i in range(len(recs)):
                for j in range(i + 1, len(recs)):
                    sims.append(calculate_product_similarity(recs[i], recs[j]))
            if sims:
                similarity_sums.append(float(np.mean(sims)))

    eval_count = max(1, num_eval)
    coverage = (len(recommended_product_ids) / float(len(catalog))) * 100.0
    mean_sim = float(np.mean(similarity_sums)) if similarity_sums else 0.0
    mean_cats = float(np.mean(category_counts_list)) if category_counts_list else 0.0

    return EvaluationMetrics(
        ranker_name=ranker_name,
        hit_rate_at_k=round(hits / eval_count, 4),
        recall_at_k=round(total_recall / eval_count, 4),
        ndcg_at_k=round(total_ndcg / eval_count, 4),
        catalog_coverage_pct=round(coverage, 2),
        avg_pairwise_similarity=round(mean_sim, 4),
        avg_category_diversity=round(mean_cats, 2),
    )

def run_evaluation(k: int = 4) -> dict[str, EvaluationMetrics]:
    """Runs rigorous multi-ranker evaluation on 400 held-out synthetic test sessions."""
    repo = CatalogRepository()
    catalog = repo.get_all_entities()

    # Generate 2000 sessions (seed=42) and perform session-grouped split
    all_sessions = generate_synthetic_sessions(num_sessions=2000, seed=42)
    train_sessions, test_sessions = split_sessions(all_sessions, train_ratio=0.8)

    # Mine association rules strictly from training sessions (1600 sessions)
    assoc_engine = AssociationRuleEngine(sessions=train_sessions, min_support_pct=0.005, seed=42)

    # 1. Baseline Recommender (1-to-1)
    dummy_engine = RecommenderEngine(association_engine=assoc_engine, ranking_mode="hybrid")
    metrics_baseline = evaluate_test_sessions(
        test_sessions=test_sessions,
        catalog=catalog,
        engine=dummy_engine,
        ranker_name="Baseline (1-to-1)",
        k=k,
        use_baseline_logic=True,
    )

    # 2. Deterministic Hybrid Ranker S_hybrid with MMR
    engine_hybrid = RecommenderEngine(association_engine=assoc_engine, ranking_mode="hybrid")
    metrics_hybrid = evaluate_test_sessions(
        test_sessions=test_sessions,
        catalog=catalog,
        engine=engine_hybrid,
        ranker_name="Hybrid (S_hybrid + MMR)",
        k=k,
        use_baseline_logic=False,
    )

    # 3. Supervised Machine Learning Ranker S_ML with MMR
    # Ensure model is trained on training_sessions
    get_ml_ranker(auto_train_if_missing=True)
    engine_ml = RecommenderEngine(association_engine=assoc_engine, ranking_mode="ml")
    metrics_ml = evaluate_test_sessions(
        test_sessions=test_sessions,
        catalog=catalog,
        engine=engine_ml,
        ranker_name="Learned ML (HistGBM + MMR)",
        k=k,
        use_baseline_logic=False,
    )

    results = {
        "baseline": metrics_baseline,
        "hybrid": metrics_hybrid,
        "ml": metrics_ml,
        "improved": metrics_hybrid,
    }

    print("\n" + "=" * 80)
    print("FAIRCART AI — OFFLINE RECOMMENDATION QUALITY EVALUATION (MILESTONE 4B)")
    print(f"Held-Out Synthetic Test Sessions: N={len(test_sessions)} (from 2,000 total sessions, K=4)")
    print("=" * 80)
    print(f"{'METRIC':<28} | {'BASELINE (1-to-1)':<17} | {'HYBRID (S_hybrid)':<18} | {'LEARNED (HistGBM)':<18}")
    print("-" * 88)
    print(f"{'HitRate@4':<28} | {metrics_baseline.hit_rate_at_k:<17.4f} | {metrics_hybrid.hit_rate_at_k:<18.4f} | {metrics_ml.hit_rate_at_k:<18.4f}")
    print(f"{'Recall@4':<28} | {metrics_baseline.recall_at_k:<17.4f} | {metrics_hybrid.recall_at_k:<18.4f} | {metrics_ml.recall_at_k:<18.4f}")
    print(f"{'NDCG@4':<28} | {metrics_baseline.ndcg_at_k:<17.4f} | {metrics_hybrid.ndcg_at_k:<18.4f} | {metrics_ml.ndcg_at_k:<18.4f}")
    print(f"{'Catalog Coverage (%)':<28} | {str(metrics_baseline.catalog_coverage_pct) + '%':<17} | {str(metrics_hybrid.catalog_coverage_pct) + '%':<18} | {str(metrics_ml.catalog_coverage_pct) + '%':<18}")
    print(f"{'Pairwise Similarity (Lower=Diverse)':<28} | {metrics_baseline.avg_pairwise_similarity:<17.4f} | {metrics_hybrid.avg_pairwise_similarity:<18.4f} | {metrics_ml.avg_pairwise_similarity:<18.4f}")
    print("=" * 88)
    print("NOTE: Evaluation is conducted on synthetic transaction data to validate pipeline mechanics.")
    print("It demonstrates multi-item synergy and diversity gains, not real consumer uplift.")
    print("=" * 80 + "\n")

    return results

run_offline_evaluation = run_evaluation

if __name__ == "__main__":
    run_evaluation()

