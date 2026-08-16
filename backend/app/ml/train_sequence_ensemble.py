"""Train a compact GRU benchmark and compare it with Phase 1 tree models and an ensemble.

No live market connection or execution integration is performed here.  The final validation
window is the Phase 1 holdout and is never used for model fitting, scaler fitting, epoch choice,
or ensemble-weight tuning.
"""

from __future__ import annotations

import copy
import json
import random
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import torch
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from torch import nn
from torch.utils.data import DataLoader, Dataset

from app.core.config import settings
from app.ml.dataset import FEATURE_COLUMNS
from app.ml.sequence_data import SequenceData, SequencePartition, build_sequence_data, selected_horizon

BACKEND_DIR = Path(__file__).resolve().parents[2]
PHASE1_MODELS_DIR = BACKEND_DIR / "models" / "phase1"
PHASE2_MODELS_DIR = BACKEND_DIR / "models" / "phase2"
REPORTS_DIR = BACKEND_DIR / "reports"
PHASE2_REPORT_PATH = REPORTS_DIR / "phase2_sequence_ensemble_metrics.json"
PHASE2_COMPONENT_PATH = REPORTS_DIR / "phase2_component_comparison.csv"
PHASE2_PAIR_PATH = REPORTS_DIR / "phase2_pair_validation_metrics.csv"
PHASE2_HISTORY_PATH = REPORTS_DIR / "phase2_gru_training_history.csv"
PHASE2_ARTIFACT_PATH = PHASE2_MODELS_DIR / "gru_4bars.pt"
SEED = 42
DECISION_THRESHOLD = 0.50


class RollingSequenceDataset(Dataset[tuple[torch.Tensor, torch.Tensor]]):
    """Materialize one contiguous, causal sequence at a time without duplicating all windows."""

    def __init__(self, data: SequenceData, partition: SequencePartition) -> None:
        self.data = data
        self.endpoints = partition.endpoints
        self.window = settings.ml_sequence_window_bars

    def __len__(self) -> int:
        return len(self.endpoints)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        symbol_index, end_index = self.endpoints[index]
        series = self.data.series_by_symbol[self.data.symbols[int(symbol_index)]]
        sequence = series.features[end_index - self.window + 1 : end_index + 1]
        # The mean/std use older inner-training rows only, never the Phase 1 final holdout.
        standardized = (sequence - self.data.scaler_mean) / self.data.scaler_std
        return torch.from_numpy(standardized.astype(np.float32, copy=False)), torch.tensor(
            series.labels[end_index], dtype=torch.float32
        )


class GRUEntryClassifier(nn.Module):
    """Small single-layer GRU suited to CPU-only, short-window financial-feature sequences."""

    def __init__(self, feature_count: int, hidden_size: int) -> None:
        super().__init__()
        self.gru = nn.GRU(feature_count, hidden_size, num_layers=1, batch_first=True)
        self.normalization = nn.LayerNorm(hidden_size)
        self.output = nn.Linear(hidden_size, 1)

    def forward(self, sequences: torch.Tensor) -> torch.Tensor:
        _, hidden = self.gru(sequences)
        return self.output(self.normalization(hidden[-1])).squeeze(-1)


def seed_everything() -> None:
    """Make the offline CPU benchmark reproducible across reruns on the same environment."""
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    torch.use_deterministic_algorithms(True)
    torch.set_num_threads(2)


def build_loader(data: SequenceData, partition: SequencePartition, batch_size: int) -> DataLoader:
    """Preserve endpoint order; no random sequence shuffle is used in this time-series workflow."""
    return DataLoader(
        RollingSequenceDataset(data, partition),
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
        pin_memory=False,
    )


def endpoint_frame(data: SequenceData, partition: SequencePartition, horizon: int) -> pd.DataFrame:
    """Return endpoint metadata and final-candle features for component and ensemble scoring."""
    rows: list[pd.DataFrame] = []
    for symbol_index, symbol in enumerate(data.symbols):
        symbol_endpoints = partition.endpoints[partition.endpoints[:, 0] == symbol_index, 1]
        if not len(symbol_endpoints):
            continue
        series = data.series_by_symbol[symbol]
        features = series.features[symbol_endpoints]
        metadata = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(series.timestamps_ns[symbol_endpoints], utc=True),
                "symbol": symbol,
                f"entry_label_{horizon}b": series.labels[symbol_endpoints].astype(int),
                f"future_return_{horizon}b": series.future_returns[symbol_endpoints],
                "entry_return_threshold": series.thresholds[symbol_endpoints],
            }
        )
        feature_frame = pd.DataFrame(features, columns=FEATURE_COLUMNS)
        rows.append(pd.concat([metadata, feature_frame], axis=1))
    return pd.concat(rows, ignore_index=True).sort_values(["timestamp", "symbol"], kind="stable").reset_index(drop=True)


def predict_probabilities(model: GRUEntryClassifier, loader: DataLoader) -> np.ndarray:
    """Run deterministic CPU inference on already chronology-separated sequence endpoints."""
    model.eval()
    probabilities: list[np.ndarray] = []
    with torch.no_grad():
        for sequences, _ in loader:
            logits = model(sequences)
            probabilities.append(torch.sigmoid(logits).cpu().numpy())
    return np.concatenate(probabilities)


def labels_from_partition(data: SequenceData, partition: SequencePartition) -> np.ndarray:
    """Return labels in the DataLoader's partition order for epoch-level metrics."""
    labels = np.empty(len(partition.endpoints), dtype=np.float32)
    for index, (symbol_index, end_index) in enumerate(partition.endpoints):
        labels[index] = data.series_by_symbol[data.symbols[int(symbol_index)]].labels[end_index]
    return labels


def train_epoch(
    model: GRUEntryClassifier,
    loader: DataLoader,
    optimizer: torch.optim.Optimizer,
    loss_function: nn.BCEWithLogitsLoss,
) -> float:
    model.train()
    total_loss = 0.0
    total_examples = 0
    for sequences, labels in loader:
        optimizer.zero_grad(set_to_none=True)
        loss = loss_function(model(sequences), labels)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        total_loss += float(loss.item()) * len(labels)
        total_examples += len(labels)
    return total_loss / total_examples


def positive_weight(data: SequenceData, partition: SequencePartition) -> float:
    labels = labels_from_partition(data, partition)
    positive_count = float(labels.sum())
    negative_count = float(len(labels) - positive_count)
    if positive_count <= 0.0 or negative_count <= 0.0:
        raise ValueError("Sequence training partition has only one label class.")
    return negative_count / positive_count


def fit_inner_model(data: SequenceData) -> tuple[int, list[dict[str, float | int]], dict[str, torch.Tensor]]:
    """Select epoch count using only an inner chronological validation segment of Phase 1 train."""
    seed_everything()
    fit_loader = build_loader(data, data.fit, settings.ml_neural_batch_size)
    inner_loader = build_loader(data, data.inner_validation, settings.ml_neural_batch_size)
    inner_labels = labels_from_partition(data, data.inner_validation)
    model = GRUEntryClassifier(len(FEATURE_COLUMNS), settings.ml_neural_hidden_size)
    optimizer = torch.optim.AdamW(model.parameters(), lr=settings.ml_neural_learning_rate, weight_decay=1e-4)
    loss_function = nn.BCEWithLogitsLoss(
        pos_weight=torch.tensor([positive_weight(data, data.fit)], dtype=torch.float32)
    )

    history: list[dict[str, float | int]] = []
    best_epoch = 1
    best_average_precision = float("-inf")
    best_state = copy.deepcopy(model.state_dict())
    for epoch in range(1, settings.ml_neural_epochs + 1):
        training_loss = train_epoch(model, fit_loader, optimizer, loss_function)
        inner_probabilities = predict_probabilities(model, inner_loader)
        inner_average_precision = float(average_precision_score(inner_labels, inner_probabilities))
        inner_roc_auc = float(roc_auc_score(inner_labels, inner_probabilities))
        history.append(
            {
                "epoch": epoch,
                "training_loss": training_loss,
                "inner_validation_average_precision": inner_average_precision,
                "inner_validation_roc_auc": inner_roc_auc,
            }
        )
        if inner_average_precision > best_average_precision:
            best_epoch = epoch
            best_average_precision = inner_average_precision
            best_state = copy.deepcopy(model.state_dict())
        print(
            f"Epoch {epoch}/{settings.ml_neural_epochs}: loss={training_loss:.5f}, "
            f"inner AP={inner_average_precision:.5f}",
            flush=True,
        )
    return best_epoch, history, best_state


def fit_final_model(data: SequenceData, epochs: int) -> GRUEntryClassifier:
    """Re-fit with the fixed selected epoch count on all pre-holdout sequence endpoints only."""
    seed_everything()
    loader = build_loader(data, data.final_train, settings.ml_neural_batch_size)
    model = GRUEntryClassifier(len(FEATURE_COLUMNS), settings.ml_neural_hidden_size)
    optimizer = torch.optim.AdamW(model.parameters(), lr=settings.ml_neural_learning_rate, weight_decay=1e-4)
    loss_function = nn.BCEWithLogitsLoss(
        pos_weight=torch.tensor([positive_weight(data, data.final_train)], dtype=torch.float32)
    )
    for epoch in range(1, epochs + 1):
        training_loss = train_epoch(model, loader, optimizer, loss_function)
        print(f"Final fit epoch {epoch}/{epochs}: loss={training_loss:.5f}", flush=True)
    return model


def _safe_metric(metric: Any, y_true: np.ndarray, values: np.ndarray) -> float | None:
    return None if len(np.unique(y_true)) < 2 else float(metric(y_true, values))


def calculate_metrics(
    evaluation: pd.DataFrame,
    probability_column: str,
    component_name: str,
    horizon: int,
) -> tuple[dict[str, float | int | None], list[dict[str, float | int | str | None]]]:
    """Use the same fixed threshold and non-compounded event-study definition as Phase 1."""
    label_column = f"entry_label_{horizon}b"
    return_column = f"future_return_{horizon}b"
    y_true = evaluation[label_column].astype(int).to_numpy()
    probabilities = evaluation[probability_column].to_numpy()
    predictions = (probabilities >= DECISION_THRESHOLD).astype(int)
    signal_mask = predictions == 1
    if signal_mask.any():
        signal_returns = evaluation.loc[signal_mask, return_column]
        excess_returns = signal_returns - evaluation.loc[signal_mask, "entry_return_threshold"]
        win_rate: float | None = float(y_true[signal_mask].mean())
        mean_future_return: float | None = float(signal_returns.mean())
        mean_excess_return: float | None = float(excess_returns.mean())
    else:
        win_rate = None
        mean_future_return = None
        mean_excess_return = None

    metrics: dict[str, float | int | None] = {
        "component": component_name,
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
        "backtest_win_rate": win_rate,
        "mean_future_return": mean_future_return,
        "mean_excess_return": mean_excess_return,
    }
    pair_metrics: list[dict[str, float | int | str | None]] = []
    for symbol, pair in evaluation.assign(predicted_signal=predictions).groupby("symbol", sort=True):
        pair_y = pair[label_column].astype(int)
        mask = pair["predicted_signal"].astype(bool)
        count = int(mask.sum())
        win = float(pair_y.loc[mask].mean()) if count else None
        base_rate = float(pair_y.mean())
        pair_metrics.append(
            {
                "component": component_name,
                "symbol": symbol,
                "validation_rows": int(len(pair)),
                "label_positive_rate": base_rate,
                "predicted_signal_count": count,
                "predicted_signal_rate": float(mask.mean()),
                "backtest_win_rate": win,
                "excess_precision_vs_base_rate": (win - base_rate) if win is not None else None,
                "mean_future_return": float(pair.loc[mask, return_column].mean()) if count else None,
            }
        )
    return metrics, pair_metrics


def tree_probabilities(frame: pd.DataFrame, artifact_name: str) -> np.ndarray:
    """Score one Phase 1 tree artifact in bounded batches to keep CPU memory predictable."""
    artifact_path = PHASE1_MODELS_DIR / artifact_name
    if not artifact_path.is_file():
        raise FileNotFoundError(f"Missing Phase 1 artifact: {artifact_path}")
    artifact = joblib.load(artifact_path)
    model = artifact["model"]
    outputs: list[np.ndarray] = []
    for start in range(0, len(frame), 50_000):
        outputs.append(model.predict_proba(frame.iloc[start : start + 50_000][FEATURE_COLUMNS])[:, 1])
    return np.concatenate(outputs)


def main() -> None:
    data = build_sequence_data()
    horizon = selected_horizon()
    if horizon != 4:
        raise ValueError("Phase 2 benchmark is approved for the Phase 1 selected 4-bar entry target only.")

    print("Selecting GRU epoch count using older inner chronological validation …", flush=True)
    best_epoch, history, _ = fit_inner_model(data)
    print(f"Selected epoch count: {best_epoch}", flush=True)
    print("Refitting GRU on all pre-holdout endpoints …", flush=True)
    final_model = fit_final_model(data, best_epoch)

    validation_loader = build_loader(data, data.validation, settings.ml_neural_batch_size)
    gru_probabilities_partition_order = predict_probabilities(final_model, validation_loader)
    validation_frame = endpoint_frame(data, data.validation, horizon)
    # endpoint_frame sorts by time/symbol whereas DataLoader preserves partition order.  Rebuild
    # the same ordering metadata and merge probabilities explicitly to prevent silent misalignment.
    loader_order_frame = endpoint_frame(data, data.validation, horizon)
    loader_order_frame["gru_probability"] = gru_probabilities_partition_order
    validation_frame = loader_order_frame.sort_values(["timestamp", "symbol"], kind="stable").reset_index(drop=True)

    validation_frame["random_forest_probability"] = tree_probabilities(
        validation_frame, "random_forest_4bars.joblib"
    )
    validation_frame["hist_gradient_boosting_probability"] = tree_probabilities(
        validation_frame, "hist_gradient_boosting_4bars.joblib"
    )
    # Equal weights are fixed before final-holdout evaluation; no validation-based weight tuning.
    validation_frame["equal_weight_ensemble_probability"] = (
        validation_frame["gru_probability"]
        + validation_frame["random_forest_probability"]
        + validation_frame["hist_gradient_boosting_probability"]
    ) / 3.0

    components = {
        "gru": "gru_probability",
        "random_forest": "random_forest_probability",
        "hist_gradient_boosting": "hist_gradient_boosting_probability",
        "equal_weight_ensemble": "equal_weight_ensemble_probability",
    }
    component_metrics: list[dict[str, float | int | None]] = []
    pair_metrics: list[dict[str, float | int | str | None]] = []
    for component_name, probability_column in components.items():
        metrics, pairs = calculate_metrics(validation_frame, probability_column, component_name, horizon)
        component_metrics.append(metrics)
        pair_metrics.extend(pairs)

    PHASE2_MODELS_DIR.mkdir(parents=True, exist_ok=True)
    artifact = {
        "architecture": "GRUEntryClassifier",
        "feature_columns": FEATURE_COLUMNS,
        "sequence_window_bars": settings.ml_sequence_window_bars,
        "hidden_size": settings.ml_neural_hidden_size,
        "selected_epoch_count": best_epoch,
        "decision_threshold": DECISION_THRESHOLD,
        "horizon_bars": horizon,
        "scaler_mean": data.scaler_mean,
        "scaler_std": data.scaler_std,
        "model_state_dict": final_model.state_dict(),
        "interval": settings.trading_candle_interval,
        "interval_status": "PROVISIONAL — confirm against TradeMind live configuration before production use.",
        "market_mode": settings.trading_market_mode,
        "market_mode_status": "PROVISIONAL — confirm spot-only execution before production use.",
    }
    torch.save(artifact, PHASE2_ARTIFACT_PATH)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(history).to_csv(PHASE2_HISTORY_PATH, index=False)
    pd.DataFrame(component_metrics).to_csv(PHASE2_COMPONENT_PATH, index=False)
    pd.DataFrame(pair_metrics).to_csv(PHASE2_PAIR_PATH, index=False)
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "architecture": "single-layer GRU with LayerNorm and linear output",
        "architecture_rationale": "GRU retains ordered information with fewer gates/parameters than an LSTM and is more CPU-efficient than a Transformer for a 32-bar offline baseline.",
        "chronology_contract": {
            "final_validation_start_utc": data.final_validation_start.isoformat(),
            "final_holdout_usage": "evaluation only; not used for scaler fit, epoch choice, model fitting, or ensemble-weight selection",
            "inner_epoch_selection": "chronological inner validation within older Phase 1 training data",
            "sequence_window_bars": settings.ml_sequence_window_bars,
            "selected_phase1_target_horizon_bars": horizon,
            "ensemble": "fixed equal-weight average of GRU, Random Forest, and HistGradientBoosting probabilities",
        },
        "epoch_selection": {"selected_epoch_count": best_epoch, "history": history},
        "components": component_metrics,
    }
    PHASE2_REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote Phase 2 report: {PHASE2_REPORT_PATH}")


if __name__ == "__main__":
    main()
