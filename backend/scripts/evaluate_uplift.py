"""FairCart AI — Offline Uplift Model CLI Evaluator (Step 5.19)

Usage:
    python backend/scripts/evaluate_uplift.py
    python backend/scripts/evaluate_uplift.py --dataset-path path/to/criteo.csv.gz --outcome visit
    python backend/scripts/evaluate_uplift.py --output-json uplift_results.json
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.engine.uplift import run_uplift_evaluation


def main():
    parser = argparse.ArgumentParser(
        description="FairCart AI Offline Uplift Modeling & Causal Incentive Evaluator"
    )
    parser.add_argument(
        "--dataset-path",
        type=str,
        default=None,
        help="Path to uplift dataset CSV or CSV.GZ (defaults to tests/fixtures/synthetic_uplift_data.csv)",
    )
    parser.add_argument(
        "--outcome",
        type=str,
        default="conversion",
        choices=["conversion", "visit"],
        help="Outcome target to evaluate (default: conversion)",
    )
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.30,
        help="Proportion of held-out test data for evaluation (default: 0.30)",
    )
    parser.add_argument(
        "--output-json",
        type=str,
        default=None,
        help="Optional path to write full evaluation results as JSON",
    )

    args = parser.parse_args()

    print("=" * 88)
    print("FAIRCART AI — OFFLINE UPLIFT MODELING & CAUSAL INCENTIVE EVALUATION (STEP 5.19)")
    print("=" * 88)

    try:
        results = run_uplift_evaluation(
            dataset_path=args.dataset_path,
            outcome_col=args.outcome,
            test_size=args.test_size,
        )
    except Exception as e:
        print(f"\n[ERROR] Uplift evaluation failed: {e}")
        sys.exit(1)

    print(f"\nDATASET AUDIT:")
    print(f"  Dataset Name       : {results['dataset_name']}")
    print(f"  Dataset Provenance : {results['dataset_provenance']}")
    print(f"  Outcome Evaluated  : {results['outcome_evaluated']}")
    print(f"  Features Analyzed  : {len(results['features_used'])} features ({', '.join(results['features_used'][:6])}...)")
    print(f"  Train Samples (70%): {results['train_samples']}")
    print(f"  Held-Out Test (30%): {results['test_samples']}")
    print(f"  Real Dataset Status: {results['real_dataset_status']}")

    print("\n" + "-" * 88)
    print("MODEL PERFORMANCE COMPARISON (HELD-OUT QINI & AUUC)")
    print("-" * 88)
    header = f"{'MODEL / STRATEGY':<38} | {'AUUC':<10} | {'QINI COEFF':<12} | {'NORM QINI':<10} | {'TEST N':<8}"
    print(header)
    print("-" * len(header))
    for key, m in results["models"].items():
        print(
            f"{m['model_name']:<38} | "
            f"{m['auuc']:<10.4f} | "
            f"{m['qini_coefficient']:<12.4f} | "
            f"{m['normalized_qini']:<10.4f} | "
            f"{m['sample_size_test']:<8}"
        )

    print("\n" + "-" * 88)
    print("T-LEARNER DECILE UPLIFT BREAKDOWN (TOP DECILES = HIGHEST PREDICTED UPLIFT)")
    print("-" * 88)
    d_header = f"{'DECILE':<8} | {'TREATED N':<10} | {'CTRL N':<8} | {'T_RATE':<10} | {'C_RATE':<10} | {'INC_UPLIFT':<12} | {'CUMULATIVE QINI':<15}"
    print(d_header)
    print("-" * len(d_header))
    for d in results["decile_breakdown"]:
        print(
            f"{d['decile']:<8} | "
            f"{d['treated_count']:<10} | "
            f"{d['control_count']:<8} | "
            f"{d['treated_conversion_rate']:<10.4f} | "
            f"{d['control_conversion_rate']:<10.4f} | "
            f"{d['incremental_uplift']:<+12.4f} | "
            f"{d['cumulative_qini']:<15.2f}"
        )

    print("\n" + "-" * 88)
    print("COUNTERFACTUAL MACRO STRATEGY COMPARISON (SYNTHETIC SIMULATION)")
    print("-" * 88)
    s_header = f"{'STRATEGY':<36} | {'TARGETED %':<12} | {'EXP CONV RATE':<15} | {'REL LIFT':<10} | {'ELIGIBILITY IDX':<15}"
    print(s_header)
    print("-" * len(s_header))
    for s in results["strategy_comparison"]:
        print(
            f"{s['strategy_name']:<36} | "
            f"{s['targeted_percentage']:<11.1f}% | "
            f"{s['expected_conversion_rate']:<15.4f} | "
            f"{s['relative_lift_vs_baseline']:<+9.1f}% | "
            f"{s['modeled_incentive_cost']:<14.1f}%"
        )

    print("\n" + "-" * 88)
    print("SCIENTIFIC & POLICY BOUNDARY NOTE")
    print("-" * 88)
    print(results["methodology_disclaimer"])
    print("=" * 88)

    if args.output_json:
        out_p = Path(args.output_json)
        with open(out_p, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"\nFull results written to {out_p.resolve()}")


if __name__ == "__main__":
    main()
