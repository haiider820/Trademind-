"""Train and evaluate leakage-safe Phase 1 tree-model entry-signal baselines."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.utils.class_weight import compute_sample_weight

from app.core.config import settings
from app.ml.dataset import (
    FEATURE_COLUMNS,
    PROCESSED_DATA_PATH,
    SPLIT_MANIFEST_PATH,
    configured_horizons,
    make_global_chronological_split,
)

BACKEND_DIR = Path(__file__).resolve().parents[2]
MODELS_DIR = BACKEND_DIR / "models" / "phase1"
REPORTS_DIR = BACKEND_DIR / "reports"
SUMMARY_PATH = REPORTS_DIR / "phase1_validation_metrics.json"
COMPARISON_PATH = REPORTS_DIR / "phase1_model_comparison.csv"
PAIR_METRICS_PATH = REPORTS_DIR / "phase1_pair_validation_metrics.csv"
SELECTED_MODEL_PATH = MODELS_DIR / "selected_model.json"
DECISION_THRESHOLD = 0.50
RANDOM_STATE = 42


@dataclass(frozen=True)
class CandidateResult:
    model_name: str
    horizon_bars: int
    artifact_path: str
    roc_auc: float
    average_precision: float
    brier_score: float
    balanced_accuracy: float
    f1: float
    precision: float
    recall: float
    predicted_signal_count: int
    predicted_signal_rate: float
    label_positive_rate: float
    backtest_win_rate: float | None
    mean_future_return: float | None
    median_future_return: float | None
    mean_excess_return: float | None
    pair_coverage: float
    pair_excess_precision_mean: float
    pair_excess_precision_std: float
    stability_score: float


def load_dataset_and_split() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load persisted features and reconstruct the exact documented global chronological split."""
    if not PROCESSED_DATA_PATH.is_file() or not SPLIT_MANIFEST_PATH.is_file():
        raise FileNotFoundError("Processed dataset or split manifest is missing. Run app.ml.dataset first.")
    dataset = pd.read_parquet(PROCESSED_DATA_PATH)
    dataset["timestamp"] = pd.to_datetime(dataset["timestamp"], utc=True)
    split = make_global_chronological_split(
        dataset,
        settings.trading_candle_interval.strip().lower(),
        configured_horizons(),
    )
    return split.train, split.validation


def build_model(model_name: str) -> RandomForestClassifier | HistGradientBoostingClassifier:
    """Return deliberately regularized, deterministic Phase 1 tree baselines."""
    if model_name == "random_forest":
        return RandomForestClassifier(
            # A single worker avoids duplicating a 1.2M-row feature matrix in multiple processes.
            n_estimators=96,
            max_depth=10,
            min_samples_leaf=100,
            max_features="sqrt",
            max_samples=0.50,
            class_weight="balanced_subsample",
            n_jobs=1,
            random_state=RANDOM_STATE,
        )
    if model_name == "hist_gradient_boosting":
        return HistGradientBoostingClassifier(
            learning_rate=0.08,
            max_iter=120,
            max_leaf_nodes=31,
            min_samples_leaf=125,
            l2_regularization=1.0,
            early_stopping=False,
            random_state=RANDOM_STATE,
        )
    raise ValueError(f"Unknown model: {model_name}")


def _safe_metric(metric: Any, y_true: pd.Series, values: np.ndarray) -> float | None:
    """Return None where a mathematically undefined metric should not be fabricated."""
    if y_true.nunique() < 2:
        return None
    return float(metric(y_true, values))


def calculate_metrics(
    evaluation: pd.DataFrame,
    horizon: int,
    model_name: str,
) -> tuple[dict[str, float | int | None], list[dict[str, float | int | str | None]]]:
    """Calculate honest held-out classification and simple event-backtest metrics."""
    label_column = f"entry_label_{horizon}b"
    return_column = f"future_return_{horizon}b"
    y_true = evaluation[label_column].astype(int)
    probabilities = evaluation["predicted_probability"].to_numpy()
    predictions = evaluation["predicted_signal"].astype(int)
    signal_mask = predictions == 1

    # This is an event study, not a compounded equity curve: overlapping 15-minute signals
    # would otherwise double-count capital.  A win is exactly the predeclared ATR/cost-floor label.
    if signal_mask.any():
        signal_returns = evaluation.loc[signal_mask, return_column]
        excess_returns = signal_returns - evaluation.loc[signal_mask, "entry_return_threshold"]
        backtest_win_rate: float | None = float(y_true.loc[signal_mask].mean())
        mean_future_return: float | None = float(signal_returns.mean())
        median_future_return: float | None = float(signal_returns.median())
        mean_excess_return: float | None = float(excess_returns.mean())
    else:
        backtest_win_rate = None
        mean_future_return = None
        median_future_return = None
        mean_excess_return = None

    metrics: dict[str, float | int | None] = {
        "roc_auc": _safe_metric(roc_auc_score, y_true, probabilities),
        "average_precision": _safe_metric(average_precision_score, y_true, probabilities),
        "brier_score": float(brier_score_loss(y_true, probabilities)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, predictions)),
        "f1": float(f1_score(y_true, predictions, zero_division=0)),
        "precision": float(precision_score(y_true, predictions, zero_division=0)),
        "recall": float(recall_score(y_true, predictions, zero_division=0)),
        "predicted_signal_count": int(signal_mask.sum()),
        "predicted_signal_rate": float(signal_mask.mean()),
        "label_positive_rate": float(y_true.mean()),
        "backtest_win_rate": backtest_win_rate,
        "mean_future_return": mean_future_return,
        "median_future_return": median_future_return,
        "mean_excess_return": mean_excess_return,
    }

    pair_metrics: list[dict[str, float | int | str | None]] = []
    for symbol, pair in evaluation.groupby("symbol", sort=True):
        pair_y_true = pair[label_column].astype(int)
        pair_signal_mask = pair["predicted_signal"].astype(bool)
        pair_signal_count = int(pair_signal_mask.sum())
        pair_precision = (
            float(pair_y_true.loc[pair_signal_mask].mean()) if pair_signal_count else 0.0
        )
        pair_base_rate = float(pair_y_true.mean())
        pair_excess_precision = pair_precision - pair_base_rate
        pair_metrics.append(
            {
                "model": model_name,
                "horizon_bars": horizon,
                "symbol": symbol,
                "validation_rows": int(len(pair)),
                "label_positive_rate": pair_base_rate,
                "predicted_signal_count": pair_signal_count,
                "predicted_signal_rate": float(pair_signal_mask.mean()),
                "backtest_win_rate": pair_precision if pair_signal_count else None,
                "excess_precision_vs_base_rate": pair_excess_precision,
                "mean_future_return": (
                    float(pair.loc[pair_signal_mask, return_column].mean()) if pair_signal_count else None
                ),
            }
        )
    return metrics, pair_metrics


def stability_from_pair_metrics(pair_metrics: list[dict[str, float | int | str | None]]) -> dict[str, float]:
    """Reward candidates that improve win rate consistently across all configured pairs."""
    excess_precision = np.array(
        [float(metric["excess_precision_vs_base_rate"]) for metric in pair_metrics], dtype=float
    )
    coverage = float(
        sum(int(metric["predicted_signal_count"]) > 0 for metric in pair_metrics) / len(pair_metrics)
    )
    mean_excess = float(excess_precision.mean())
    std_excess = float(excess_precision.std(ddof=0))

    # A lower one-standard-deviation excess precision forces selection toward candidates that
    # improve over each pair's baseline rate broadly, rather than one isolated high-win-rate pair.
    return {
        "pair_coverage": coverage,
        "pair_excess_precision_mean": mean_excess,
        "pair_excess_precision_std": std_excess,
        "stability_score": mean_excess - std_excess,
    }


def fit_and_evaluate_candidate(
    train: pd.DataFrame,
    validation: pd.DataFrame,
    horizon: int,
    model_name: str,
) -> tuple[CandidateResult, list[dict[str, float | int | str | None]]]:
    """Fit on pre-cutoff labels only, then score the untouched held-out period exactly once."""
    label_column = f"entry_label_{horizon}b"
    if label_column not in train or label_column not in validation:
        raise KeyError(f"Missing label column {label_column}.")

    # Each horizon excludes only rows whose own forward label is undefined.  Feature columns
    # remain wholly causal and were already computed before this horizon-specific filtering.
    train_subset = train.dropna(subset=[label_column]).copy()
    validation_subset = validation.dropna(subset=[label_column]).copy()
    x_train = train_subset[FEATURE_COLUMNS]
    y_train = train_subset[label_column].astype(int)
    x_validation = validation_subset[FEATURE_COLUMNS]

    model = build_model(model_name)
    if model_name == "hist_gradient_boosting":
        # Class weighting prevents the rare positive entry class from being ignored; it is fitted
        # using training labels only and never references the held-out window.
        model.fit(x_train, y_train, sample_weight=compute_sample_weight(class_weight="balanced", y=y_train))
    else:
        model.fit(x_train, y_train)

    probabilities = model.predict_proba(x_validation)[:, 1]
    evaluation = validation_subset[
        ["timestamp", "symbol", "entry_return_threshold", label_column, f"future_return_{horizon}b"]
    ].copy()
    evaluation["predicted_probability"] = probabilities
    evaluation["predicted_signal"] = (probabilities >= DECISION_THRESHOLD).astype(int)

    metrics, pair_metrics = calculate_metrics(evaluation, horizon, model_name)
    stability = stability_from_pair_metrics(pair_metrics)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    artifact_path = MODELS_DIR / f"{model_name}_{horizon}bars.joblib"
    artifact = {
        "model": model,
        "model_name": model_name,
        "horizon_bars": horizon,
        "decision_threshold": DECISION_THRESHOLD,
        "feature_columns": FEATURE_COLUMNS,
        "interval": settings.trading_candle_interval,
        "interval_status": "PROVISIONAL — confirm against TradeMind live configuration before production use.",
        "market_mode": settings.trading_market_mode,
        "market_mode_status": "PROVISIONAL — confirm spot-only execution before production use.",
        "label_definition": {
            "target": "long-only entry / no-entry",
            "atr_multiple": settings.ml_entry_atr_multiple,
            "round_trip_cost_floor": settings.ml_round_trip_cost_floor,
            "rule": "future close return > max(ATR(14) multiple at entry, round-trip cost floor)",
        },
        "trained_through_utc": train_subset["timestamp"].max().isoformat(),
        "validation_start_utc": validation_subset["timestamp"].min().isoformat(),
    }
    joblib.dump(artifact, artifact_path, compress=3)

    candidate = CandidateResult(
        model_name=model_name,
        horizon_bars=horizon,
        artifact_path=str(artifact_path.relative_to(BACKEND_DIR)),
        **metrics,
        **stability,
    )
    return candidate, pair_metrics


def choose_candidate(candidates: list[CandidateResult]) -> CandidateResult:
    """Choose the stable cross-pair candidate; ranking is fixed before examining results."""
    return max(
        candidates,
        key=lambda candidate: (
            candidate.stability_score,
            candidate.pair_coverage,
            candidate.average_precision if candidate.average_precision is not None else float("-inf"),
            candidate.backtest_win_rate if candidate.backtest_win_rate is not None else float("-inf"),
        ),
    )


def main() -> None:
    train, validation = load_dataset_and_split()
    candidates: list[CandidateResult] = []
    pair_metrics: list[dict[str, float | int | str | None]] = []
    for horizon in configured_horizons():
        for model_name in ("random_forest", "hist_gradient_boosting"):
            print(f"Training {model_name} for {horizon}-bar horizon …", flush=True)
            candidate, candidate_pair_metrics = fit_and_evaluate_candidate(
                train, validation, horizon, model_name
            )
            candidates.append(candidate)
            pair_metrics.extend(candidate_pair_metrics)

    selected = choose_candidate(candidates)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    comparison = pd.DataFrame([asdict(candidate) for candidate in candidates]).sort_values(
        ["stability_score", "pair_coverage", "average_precision"], ascending=[False, False, False]
    )
    comparison.to_csv(COMPARISON_PATH, index=False)
    pd.DataFrame(pair_metrics).sort_values(["horizon_bars", "model", "symbol"]).to_csv(
        PAIR_METRICS_PATH, index=False
    )

    with SPLIT_MANIFEST_PATH.open(encoding="utf-8") as source:
        split_manifest = json.load(source)
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "validation_protocol": {
            "split": "single global chronological 80/20 holdout",
            "train_label_purge": "the maximum 16-bar forward-label window before validation start is excluded from training",
            "decision_threshold": DECISION_THRESHOLD,
            "backtest": "non-compounded event study; overlapping signals are not compounded",
            "selection_rule": "maximize mean minus standard deviation of per-pair excess win rate over each pair's own base rate",
        },
        "split": split_manifest,
        "candidates": [asdict(candidate) for candidate in candidates],
        "selected_candidate": asdict(selected),
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    SELECTED_MODEL_PATH.write_text(
        json.dumps(
            {
                "selected_candidate": asdict(selected),
                "selection_rule": summary["validation_protocol"]["selection_rule"],
                "source_metrics": str(SUMMARY_PATH.relative_to(BACKEND_DIR)),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Selected {selected.model_name} at {selected.horizon_bars}-bar horizon.")
    print(f"Metrics: {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
