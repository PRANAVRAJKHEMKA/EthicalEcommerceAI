"""FairCart AI — Offline Uplift Modeling & Causal Incentive Evaluation Engine (Step 5.19)

Provides an offline causal evaluation pipeline for incentive targeting:
1. Validates experimental uplift datasets (e.g., Criteo Uplift Prediction Benchmark schema).
2. Implements a Two-Model T-Learner using regularized classification models.
3. Evaluates held-out ranking performance via Qini curves, AUUC, and decile uplift.
4. Compares T-Learner causal targeting against Non-Causal Propensity and Random baselines.
5. Models three macro strategies: No Discount vs. Blanket Markdown vs. Uplift-Targeted.

Scientific & Policy Boundaries:
- Causal uplift estimation is strictly separated from live pricing authority.
- Live offers remain bounded by EconomicOptimizer margin floors, discount caps, and inventory checks.
- Uplift scores reflect modeled population incrementality, never guaranteed individual outcomes.
"""

from __future__ import annotations

import csv
import gzip
import logging
import math
import zlib
from pathlib import Path
from typing import Any, Sequence

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

logger = logging.getLogger("faircart.uplift")

# Directory resolution and allowed dataset locations
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent.parent
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_FIXTURE_PATH = BACKEND_DIR / "tests" / "fixtures" / "synthetic_uplift_data.csv"

# Permitted dataset directories for offline uplift evaluation (prevents arbitrary file read / path traversal)
ALLOWED_DATASET_DIRS = [
    (BACKEND_DIR / "tests" / "fixtures").resolve(),
    (WORKSPACE_ROOT / "data" / "uplift").resolve(),
    (BACKEND_DIR / "data" / "uplift").resolve(),
]

# Resource constraints for offline causal evaluation (DoS and memory protection)
MAX_DATASET_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB compressed file limit
MAX_DECOMPRESSED_BYTES = 100 * 1024 * 1024       # 100 MB decompressed size safety limit (prevents zip bombs)
MAX_DEFAULT_ROWS = 50_000                        # Cap reading at 50,000 samples
MAX_FIELD_SIZE_BYTES = 1024 * 1024              # 1 MB max per individual CSV cell

# Criteo benchmark feature specification
CRITEO_FEATURE_COLUMNS = [f"f{i}" for i in range(12)]
CRITEO_TREATMENT_COL = "treatment"
CRITEO_OUTCOME_COLS = ("conversion", "visit")


class UpliftDatasetSchemaError(ValueError):
    """Raised when an evaluation dataset fails required experimental or structural assumptions."""
    pass


class DecompressionSizeLimiter:
    """Wraps a text line stream and monitors cumulative decompressed bytes to prevent decompression bombs."""

    def __init__(self, stream: Any, max_bytes: int = MAX_DECOMPRESSED_BYTES):
        self.stream = stream
        self.max_bytes = max_bytes
        self.bytes_read = 0

    def __iter__(self):
        return self

    def __next__(self) -> str:
        line = next(self.stream)
        self.bytes_read += len(line.encode("utf-8", errors="replace"))
        if self.bytes_read > self.max_bytes:
            limit_mb = self.max_bytes // (1024 * 1024)
            raise UpliftDatasetSchemaError(
                f"Decompressed data size exceeded security threshold of {limit_mb} MB (decompression bomb protection)."
            )
        return line


def resolve_and_validate_path(dataset_path: str | Path | None = None) -> Path:
    """Validates and resolves a dataset path against directory allowlists and security policies."""
    if not dataset_path:
        return DEFAULT_FIXTURE_PATH

    raw_path = Path(dataset_path)

    # 1. Simple filename lookup: if just a filename without path separators, search allowed dirs
    if not raw_path.is_absolute() and ("/" not in str(dataset_path) and "\\" not in str(dataset_path)):
        found = False
        for allowed_dir in ALLOWED_DATASET_DIRS:
            candidate = (allowed_dir / raw_path).resolve()
            if candidate.exists() and candidate.is_file():
                raw_path = candidate
                found = True
                break
        if not found:
            raw_path = (ALLOWED_DATASET_DIRS[0] / raw_path).resolve()

    # 2. Resolve to absolute path
    resolved = (WORKSPACE_ROOT / raw_path).resolve() if not raw_path.is_absolute() else raw_path.resolve()

    # 3. Check allowed directories (prevent path traversal / arbitrary file read)
    is_allowed = any(
        resolved == allowed_dir or (
            resolved.is_relative_to(allowed_dir) if hasattr(resolved, "is_relative_to")
            else str(resolved).startswith(str(allowed_dir))
        )
        for allowed_dir in ALLOWED_DATASET_DIRS
    )
    if not is_allowed:
        raise UpliftDatasetSchemaError(
            f"Access denied: dataset path '{dataset_path}' is outside permitted directories. "
            f"Permitted directories: {[str(d) for d in ALLOWED_DATASET_DIRS]}"
        )

    # 4. Check existence and file type
    if not resolved.exists():
        raise FileNotFoundError(f"Uplift dataset not found at '{resolved}'")
    if not resolved.is_file():
        raise UpliftDatasetSchemaError(f"Dataset path '{resolved}' is not a regular file.")

    # 5. Check extension
    name_lower = resolved.name.lower()
    if not (name_lower.endswith(".csv") or name_lower.endswith(".csv.gz")):
        raise UpliftDatasetSchemaError(
            f"Invalid file format for '{resolved.name}'. Only .csv and .csv.gz files are permitted."
        )

    # 6. Check file size (prevent DoS / OOM)
    file_size = resolved.stat().st_size
    if file_size > MAX_DATASET_FILE_SIZE_BYTES:
        mb = file_size / (1024 * 1024)
        raise UpliftDatasetSchemaError(
            f"Dataset file size ({mb:.1f} MB) exceeds maximum allowed limit of "
            f"{MAX_DATASET_FILE_SIZE_BYTES // (1024 * 1024)} MB."
        )

    return resolved


def load_and_validate_dataset(
    dataset_path: str | Path | None = None,
    outcome_col: str = "conversion",
    max_rows: int | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str], str]:
    """Loads a CSV or CSV.GZ dataset, validates schema assumptions, and extracts (X, treatment, outcome).

    Returns:
        X: (N, D) float array of features.
        treatment: (N,) binary integer array (0 = control, 1 = treated).
        outcome: (N,) binary integer array (0 = no event, 1 = event).
        feature_names: list of feature column headers.
        provenance_label: human-readable provenance and license description.
    """
    path = resolve_and_validate_path(dataset_path)

    is_synthetic = "synthetic" in path.name.lower() or "fixture" in str(path).lower()
    provenance = (
        "Synthetic Mechanics Fixture (CC0/FairCart, 1000 samples, ground-truth heterogeneous effects)"
        if is_synthetic
        else f"Evaluated from '{path.name}' (Criteo Uplift Benchmark schema, CC BY-NC-SA 4.0)"
    )

    try:
        csv.field_size_limit(MAX_FIELD_SIZE_BYTES)
    except (OverflowError, ValueError):
        pass

    effective_max_rows = min(max_rows, MAX_DEFAULT_ROWS) if max_rows else MAX_DEFAULT_ROWS
    is_gz = str(path).lower().endswith(".gz")

    if is_gz:
        # Pre-flight check: Verify gzip magic bytes (0x1f 0x8b) before attempting decompression
        try:
            with open(str(path), "rb") as raw_chk:
                magic = raw_chk.read(2)
                if magic != b"\x1f\x8b":
                    raise UpliftDatasetSchemaError(
                        f"Corrupted or invalid gzip file '{path.name}': Missing valid gzip magic header."
                    )
        except OSError as e:
            raise UpliftDatasetSchemaError(f"Failed to read file '{path.name}': {str(e)}")

    try:
        raw_stream = (
            gzip.open(str(path), mode="rt", encoding="utf-8", newline="", errors="strict")
            if is_gz
            else open(str(path), mode="r", encoding="utf-8", newline="", errors="strict")
        )
    except (gzip.BadGzipFile, zlib.error, EOFError, OSError) as e:
        raise UpliftDatasetSchemaError(f"Corrupted or unreadable dataset file '{path.name}': {str(e)}")

    try:
        safe_stream = DecompressionSizeLimiter(raw_stream, MAX_DECOMPRESSED_BYTES)
        reader = csv.reader(safe_stream)
        try:
            header = next(reader, None)
        except (gzip.BadGzipFile, zlib.error, EOFError, UnicodeDecodeError) as e:
            raise UpliftDatasetSchemaError(f"Error decoding dataset file '{path.name}': {str(e)}")

        if not header:
            raise UpliftDatasetSchemaError(f"Dataset file '{path}' is empty or missing a CSV header row.")

        header_lower = [h.strip().lower() for h in header]

        # Validate treatment column
        if CRITEO_TREATMENT_COL not in header_lower:
            raise UpliftDatasetSchemaError(
                f"Missing required treatment column '{CRITEO_TREATMENT_COL}'. Found headers: {header[:10]}..."
            )
        t_idx = header_lower.index(CRITEO_TREATMENT_COL)

        # Validate outcome column
        target_outcome = outcome_col.strip().lower()
        if target_outcome not in header_lower:
            raise UpliftDatasetSchemaError(
                f"Outcome column '{target_outcome}' not found in dataset. Supported outcomes: {CRITEO_OUTCOME_COLS}"
            )
        y_idx = header_lower.index(target_outcome)

        # Identify feature columns (prefer f0..f11 if present, otherwise any numeric non-target columns)
        criteo_features = [f"f{i}" for i in range(12)]
        has_criteo_features = all(cf in header_lower for cf in criteo_features)

        if has_criteo_features:
            feature_indices = [header_lower.index(cf) for cf in criteo_features]
            feature_names = criteo_features
        else:
            exclude_names = {CRITEO_TREATMENT_COL, "conversion", "visit", "exposure", "target"}
            feature_indices = [i for i, h in enumerate(header_lower) if h not in exclude_names]
            feature_names = [header[i] for i in feature_indices]

        if not feature_indices:
            raise UpliftDatasetSchemaError("No valid feature columns identified in dataset.")

        rows_x = []
        rows_t = []
        rows_y = []

        for row_idx, row in enumerate(reader):
            if effective_max_rows and row_idx >= effective_max_rows:
                break
            if not row or len(row) <= max(max(feature_indices), t_idx, y_idx):
                continue

            try:
                t_val = int(float(row[t_idx]))
                y_val = int(float(row[y_idx]))
                x_vals = [float(row[fi]) for fi in feature_indices]
            except (ValueError, TypeError):
                continue

            if t_val not in (0, 1):
                raise UpliftDatasetSchemaError(
                    f"Treatment column must be strictly binary (0 or 1). Found '{t_val}' at row {row_idx + 1}."
                )
            if y_val not in (0, 1):
                raise UpliftDatasetSchemaError(
                    f"Outcome column must be strictly binary (0 or 1). Found '{y_val}' at row {row_idx + 1}."
                )

            rows_x.append(x_vals)
            rows_t.append(t_val)
            rows_y.append(y_val)
    except (gzip.BadGzipFile, zlib.error, EOFError, UnicodeDecodeError) as e:
        raise UpliftDatasetSchemaError(f"Error reading compressed dataset stream '{path.name}': {str(e)}")
    finally:
        raw_stream.close()

    if len(rows_x) < 50:
        raise UpliftDatasetSchemaError(
            f"Dataset contains insufficient valid samples ({len(rows_x)} < 50 required for uplift evaluation)."
        )

    X = np.array(rows_x, dtype=np.float64)
    treatment = np.array(rows_t, dtype=np.int32)
    outcome = np.array(rows_y, dtype=np.int32)

    # Validate that both treatment and control groups exist
    n_treated = int(np.sum(treatment == 1))
    n_control = int(np.sum(treatment == 0))
    if n_treated == 0 or n_control == 0:
        raise UpliftDatasetSchemaError(
            f"Experimental balance assumption failed: treated={n_treated}, control={n_control}. "
            f"Both treated and control units are strictly required for uplift estimation."
        )

    return X, treatment, outcome, feature_names, provenance


class TLearnerUpliftModel:
    """Two-Model T-Learner for conditional average treatment effect (CATE / individual uplift) estimation.

    Fits two separate classification models:
    - Treatment Model mu_1(x) = P(Y=1 | X=x, T=1)
    - Control Model   mu_0(x) = P(Y=1 | X=x, T=0)
    Estimated individual uplift tau(x) = mu_1(x) - mu_0(x).
    """

    def __init__(self, random_state: int = 42):
        self.random_state = random_state
        self.model_treated = LogisticRegression(max_iter=500, random_state=random_state, C=1.0)
        self.model_control = LogisticRegression(max_iter=500, random_state=random_state, C=1.0)
        self.is_fitted = False

    def fit(self, X: np.ndarray, treatment: np.ndarray, outcome: np.ndarray) -> "TLearnerUpliftModel":
        """Fits treatment and control outcome models on their respective sub-populations."""
        treated_mask = treatment == 1
        control_mask = treatment == 0

        X_t, y_t = X[treated_mask], outcome[treated_mask]
        X_c, y_c = X[control_mask], outcome[control_mask]

        # Handle edge cases with zero outcome variance
        if len(np.unique(y_t)) > 1:
            self.model_treated.fit(X_t, y_t)
        else:
            self.model_treated = _DummyConstantClassifier(float(y_t[0]))

        if len(np.unique(y_c)) > 1:
            self.model_control.fit(X_c, y_c)
        else:
            self.model_control = _DummyConstantClassifier(float(y_c[0]))

        self.is_fitted = True
        return self

    def predict_uplift(self, X: np.ndarray) -> np.ndarray:
        """Predicts individual uplift tau(x) = P(Y=1 | x, T=1) - P(Y=1 | x, T=0)."""
        if not self.is_fitted:
            raise RuntimeError("TLearner model is not fitted yet.")

        p1 = self._predict_proba_class1(self.model_treated, X)
        p0 = self._predict_proba_class1(self.model_control, X)
        return p1 - p0

    def predict_propensity(self, X: np.ndarray) -> np.ndarray:
        """Returns baseline conversion probability under treatment mu_1(x) for non-causal comparison."""
        if not self.is_fitted:
            raise RuntimeError("TLearner model is not fitted yet.")
        return self._predict_proba_class1(self.model_treated, X)

    @staticmethod
    def _predict_proba_class1(model: Any, X: np.ndarray) -> np.ndarray:
        if isinstance(model, _DummyConstantClassifier):
            return np.full(X.shape[0], model.constant_val)
        probs = model.predict_proba(X)
        if probs.shape[1] == 1:
            return probs[:, 0]
        return probs[:, 1]


class _DummyConstantClassifier:
    """Fallback classifier when a subpopulation has uniform binary outcomes."""

    def __init__(self, constant_val: float):
        self.constant_val = constant_val

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        n = X.shape[0]
        p = self.constant_val
        return np.column_stack([1.0 - p, p]) if (0.0 <= p <= 1.0) else np.zeros((n, 2))


def compute_qini_curve(
    predicted_uplift: np.ndarray,
    treatment: np.ndarray,
    outcome: np.ndarray,
    n_bins: int = 10,
) -> tuple[np.ndarray, np.ndarray, float, float, list[dict[str, Any]]]:
    """Computes the empirical Qini curve, Qini coefficient, AUUC, and decile metrics.

    Formula:
        For top-k ranking:
        Q(k) = y_T(k) - y_C(k) * (N_T / N_C)
    """
    n_samples = len(predicted_uplift)
    order = np.argsort(-predicted_uplift)

    sorted_t = treatment[order]
    sorted_y = outcome[order]

    N_T = float(np.sum(sorted_t == 1))
    N_C = float(np.sum(sorted_t == 0))

    if N_T == 0 or N_C == 0:
        raise ValueError("Cannot calculate Qini: either N_T or N_C is 0.")

    scaling_ratio = N_T / N_C

    # Cumulative counts
    cum_yt = np.cumsum((sorted_t == 1) * sorted_y)
    cum_yc = np.cumsum((sorted_t == 0) * sorted_y)

    # Qini values at each sample
    qini_values = cum_yt - cum_yc * scaling_ratio

    # Normalization grid for AUUC (fraction of population from 0 to 1)
    grid_x = np.linspace(0.0, 1.0, 101)
    sample_fractions = np.linspace(1.0 / n_samples, 1.0, n_samples)
    interpolated_qini = np.interp(grid_x, np.concatenate(([0.0], sample_fractions)), np.concatenate(([0.0], qini_values)))

    # AUUC via trapezoidal integration
    auuc = float(np.trapezoid(interpolated_qini, grid_x))

    # Random baseline curve connects (0, 0) to (1.0, qini_values[-1])
    random_auuc = float(0.5 * qini_values[-1])

    # Normalized Qini: difference between model AUUC and random baseline
    qini_coefficient = float(auuc - random_auuc)

    # Compute decile metrics
    bin_size = max(1, n_samples // n_bins)
    decile_metrics = []

    for d in range(1, n_bins + 1):
        start_idx = (d - 1) * bin_size
        end_idx = n_samples if d == n_bins else d * bin_size

        sub_t = sorted_t[start_idx:end_idx]
        sub_y = sorted_y[start_idx:end_idx]

        t_count = int(np.sum(sub_t == 1))
        c_count = int(np.sum(sub_t == 0))
        t_conv = int(np.sum((sub_t == 1) * sub_y))
        c_conv = int(np.sum((sub_t == 0) * sub_y))

        t_rate = round(t_conv / t_count, 4) if t_count > 0 else 0.0
        c_rate = round(c_conv / c_count, 4) if c_count > 0 else 0.0
        inc_uplift = round(t_rate - c_rate, 4)
        cum_q = round(float(qini_values[end_idx - 1]), 2)

        decile_metrics.append({
            "decile": d,
            "treated_count": t_count,
            "control_count": c_count,
            "treated_conversions": t_conv,
            "control_conversions": c_conv,
            "treated_conversion_rate": t_rate,
            "control_conversion_rate": c_rate,
            "incremental_uplift": inc_uplift,
            "cumulative_qini": cum_q,
        })

    return grid_x, interpolated_qini, auuc, qini_coefficient, decile_metrics


def run_uplift_evaluation(
    dataset_path: str | Path | None = None,
    outcome_col: str = "conversion",
    test_size: float = 0.30,
    random_state: int = 42,
    max_rows: int | None = None,
) -> dict[str, Any]:
    """Executes the complete held-out offline uplift evaluation pipeline.

    Evaluates:
    1. Two-Model T-Learner (Causal Uplift Targeting)
    2. Conversion Propensity Baseline (Non-Causal Conversion Likelihood)
    3. Random Baseline (Uniform Random Targeting)

    Returns a structured dictionary matching the UpliftEvaluationResponse schema.
    """
    resolved_path = resolve_and_validate_path(dataset_path)
    X, treatment, outcome, feature_names, provenance = load_and_validate_dataset(
        dataset_path=resolved_path,
        outcome_col=outcome_col,
        max_rows=max_rows,
    )

    # Stratified train/test split to prevent outcome or treatment distribution drift
    strat_key = treatment * 2 + outcome
    X_train, X_test, t_train, t_test, y_train, y_test = train_test_split(
        X, treatment, outcome,
        test_size=test_size,
        random_state=random_state,
        stratify=strat_key if len(np.unique(strat_key)) > 1 else None,
    )

    # 1. Fit Two-Model T-Learner
    t_learner = TLearnerUpliftModel(random_state=random_state)
    t_learner.fit(X_train, t_train, y_train)

    # 2. Predict on held-out test data
    uplift_preds = t_learner.predict_uplift(X_test)
    propensity_preds = t_learner.predict_propensity(X_test)

    # 3. Random baseline predictions
    rng = np.random.RandomState(random_state)
    random_preds = rng.uniform(0.0, 1.0, size=len(t_test))

    # 4. Evaluate Qini for all 3 models
    _, _, auuc_tlearner, qini_tlearner, deciles = compute_qini_curve(uplift_preds, t_test, y_test)
    _, _, auuc_propensity, qini_propensity, _ = compute_qini_curve(propensity_preds, t_test, y_test)
    _, _, auuc_random, qini_random, _ = compute_qini_curve(random_preds, t_test, y_test)

    # Calculate normalized Qini scores relative to baseline
    denom = max(abs(auuc_tlearner), 1e-6)
    norm_tlearner = round(qini_tlearner / denom, 4)
    norm_propensity = round(qini_propensity / denom, 4)
    norm_random = 0.0

    treated_prop = float(np.mean(treatment == 1))
    control_prop = 1.0 - treated_prop

    models_summary = {
        "t_learner": {
            "model_name": "Two-Model T-Learner (Causal Uplift)",
            "auuc": round(auuc_tlearner, 4),
            "qini_coefficient": round(qini_tlearner, 4),
            "normalized_qini": norm_tlearner,
            "sample_size_train": len(X_train),
            "sample_size_test": len(X_test),
            "treated_proportion": round(treated_prop, 4),
            "control_proportion": round(control_prop, 4),
        },
        "propensity_baseline": {
            "model_name": "Conversion Propensity (Non-Causal)",
            "auuc": round(auuc_propensity, 4),
            "qini_coefficient": round(qini_propensity, 4),
            "normalized_qini": norm_propensity,
            "sample_size_train": len(X_train),
            "sample_size_test": len(X_test),
            "treated_proportion": round(treated_prop, 4),
            "control_proportion": round(control_prop, 4),
        },
        "random_baseline": {
            "model_name": "Random Targeting Baseline",
            "auuc": round(auuc_random, 4),
            "qini_coefficient": round(qini_random, 4),
            "normalized_qini": norm_random,
            "sample_size_train": len(X_train),
            "sample_size_test": len(X_test),
            "treated_proportion": round(treated_prop, 4),
            "control_proportion": round(control_prop, 4),
        },
    }

    # 5. Three-Strategy Comparison
    # Strategy 1: No Discount (treat 0%)
    c_rate_overall = float(np.mean(y_test[t_test == 0])) if np.sum(t_test == 0) > 0 else 0.0
    t_rate_overall = float(np.mean(y_test[t_test == 1])) if np.sum(t_test == 1) > 0 else 0.0

    # Strategy 3: Uplift Targeted (treat only units with positive predicted uplift tau > 0)
    targeted_mask = uplift_preds > 0.0
    targeted_pct = round(float(np.mean(targeted_mask)), 4)

    # Estimate counterfactual conversion under targeted policy:
    # Users targeted receive treated rate; untargeted receive control rate
    if targeted_pct > 0:
        y_target_treated = y_test[targeted_mask & (t_test == 1)]
        rate_targeted = float(np.mean(y_target_treated)) if len(y_target_treated) > 0 else t_rate_overall

        y_untarget_control = y_test[(~targeted_mask) & (t_test == 0)]
        rate_untargeted = float(np.mean(y_untarget_control)) if len(y_untarget_control) > 0 else c_rate_overall

        expected_targeted_rate = round(targeted_pct * rate_targeted + (1.0 - targeted_pct) * rate_untargeted, 4)
    else:
        expected_targeted_rate = round(c_rate_overall, 4)

    rel_lift_blanket = round(((t_rate_overall - c_rate_overall) / max(c_rate_overall, 1e-4)) * 100.0, 1)
    rel_lift_targeted = round(((expected_targeted_rate - c_rate_overall) / max(c_rate_overall, 1e-4)) * 100.0, 1)

    # Modeled discount expense relative index
    strategy_comparison = [
        {
            "strategy_id": "no_discount",
            "strategy_name": "Organic Baseline (No Discount)",
            "description": "Zero promotional incentives offered. All synthetic shoppers purchase at full reference price.",
            "targeted_percentage": 0.0,
            "expected_conversion_rate": round(c_rate_overall, 4),
            "relative_lift_vs_baseline": 0.0,
            "modeled_incentive_cost": 0.0,
        },
        {
            "strategy_id": "blanket_markdown",
            "strategy_name": "Blanket 15% Markdown",
            "description": "Indiscriminate promotional discounts offered to 100% of synthetic shoppers under offline simulation.",
            "targeted_percentage": 100.0,
            "expected_conversion_rate": round(t_rate_overall, 4),
            "relative_lift_vs_baseline": rel_lift_blanket,
            "modeled_incentive_cost": 100.0,
        },
        {
            "strategy_id": "uplift_targeted",
            "strategy_name": "FairCart Uplift-Targeted Incentive",
            "description": "Promotional incentives allocated strictly to persuadable synthetic shoppers where predicted incremental uplift is positive (tau > 0).",
            "targeted_percentage": round(targeted_pct * 100.0, 1),
            "expected_conversion_rate": expected_targeted_rate,
            "relative_lift_vs_baseline": rel_lift_targeted,
            "modeled_incentive_cost": round(targeted_pct * 100.0, 1),
        },
    ]

    is_synth = "synthetic" in provenance.lower()
    real_status = (
        "synthetic_fixture_pipeline_verification"
        if is_synth
        else "evaluated_from_file"
    )

    disclaimer = (
        "Offline causal uplift evaluation lab for experimental targeting research. "
        "Evaluates incremental conversion using held-out Qini curves and AUUC. "
        "All numerical metrics reflect synthetic pipeline evaluation from the local synthetic mechanics fixture "
        "(1,000 samples, 12 continuous features) designed to verify evaluation mechanics. "
        "Evaluation on the real full-scale Criteo Uplift Benchmark (2.3 GB / ~25M rows) remains pending and deferred to "
        "dedicated offline compute environments. "
        "The reported strategy conversion rates and incentive eligibility indices are derived from offline policy simulation "
        "under simplified experimental assumptions; targeting 75% of shoppers represents an eligibility index, "
        "not an audited financial measurement of net discount expenditure or dollar margin savings. "
        "This pipeline does not alter synchronous storefront pricing or override authoritative EconomicOptimizer margin floors."
    )

    return {
        "dataset_name": resolved_path.name,
        "dataset_provenance": provenance,
        "features_used": feature_names,
        "outcome_evaluated": outcome_col,
        "treatment_column": CRITEO_TREATMENT_COL,
        "train_samples": len(X_train),
        "test_samples": len(X_test),
        "models": models_summary,
        "decile_breakdown": deciles,
        "strategy_comparison": strategy_comparison,
        "methodology_disclaimer": disclaimer,
        "real_dataset_status": real_status,
    }
