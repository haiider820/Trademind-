"""Leakage-safe rolling sequence construction for the Phase 2 neural benchmark."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from app.core.config import settings
from app.ml.dataset import FEATURE_COLUMNS, INTERVAL_TO_DELTA, PROCESSED_DATA_PATH, SPLIT_MANIFEST_PATH

BACKEND_DIR = Path(__file__).resolve().parents[2]
SEQUENCE_MANIFEST_PATH = BACKEND_DIR / "data" / "processed" / "phase2_sequence_manifest.json"


@dataclass(frozen=True)
class SymbolSeries:
    """One pair's causal features and Phase 1 target values in timestamp order."""

    features: np.ndarray
    timestamps_ns: np.ndarray
    labels: np.ndarray
    future_returns: np.ndarray
    thresholds: np.ndarray


@dataclass(frozen=True)
class SequencePartition:
    """Sequence endpoint references; each row is [symbol_index, endpoint_row_index]."""

    endpoints: np.ndarray


@dataclass(frozen=True)
class SequenceData:
    """All per-symbol arrays plus chronologically separated endpoint partitions."""

    symbols: list[str]
    series_by_symbol: dict[str, SymbolSeries]
    fit: SequencePartition
    inner_validation: SequencePartition
    final_train: SequencePartition
    validation: SequencePartition
    scaler_mean: np.ndarray
    scaler_std: np.ndarray
    inner_validation_start: pd.Timestamp
    final_validation_start: pd.Timestamp


def selected_horizon() -> int:
    """Read the Phase 1 stability-selected horizon rather than silently choosing a new target."""
    selection_path = BACKEND_DIR / "models" / "phase1" / "selected_model.json"
    if not selection_path.is_file():
        raise FileNotFoundError("Phase 1 selected-model manifest is missing. Complete Phase 1 first.")
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    return int(selection["selected_candidate"]["horizon_bars"])


def _phase1_cutoffs() -> tuple[pd.Timestamp, pd.Timestamp]:
    if not SPLIT_MANIFEST_PATH.is_file():
        raise FileNotFoundError("Phase 1 split manifest is missing. Run app.ml.dataset first.")
    manifest = json.loads(SPLIT_MANIFEST_PATH.read_text(encoding="utf-8"))
    return (
        pd.Timestamp(manifest["purged_train_end_utc"]),
        pd.Timestamp(manifest["global_validation_start_utc"]),
    )


def _validate_sequence_settings() -> tuple[int, int, pd.Timedelta, int]:
    interval = settings.trading_candle_interval.strip().lower()
    if interval not in INTERVAL_TO_DELTA:
        raise ValueError(f"Unsupported configured candle interval: {interval!r}")
    window = settings.ml_sequence_window_bars
    stride = settings.ml_sequence_training_stride
    if window < 8:
        raise ValueError("ML_SEQUENCE_WINDOW_BARS must be at least 8.")
    if stride < 1:
        raise ValueError("ML_SEQUENCE_TRAINING_STRIDE must be at least 1.")
    horizon = selected_horizon()
    return window, stride, INTERVAL_TO_DELTA[interval], horizon


def _endpoint_indexes(
    series: SymbolSeries,
    window: int,
    interval_delta: pd.Timedelta,
    endpoint_start_ns: int | None,
    endpoint_end_ns: int | None,
    stride: int,
) -> np.ndarray:
    """Generate valid sequence endpoints without crossing a source-data gap.

    A sequence ending at t is valid only when all `window` candles are contiguous and its own
    forward label exists.  The sequence features never contain future candles relative to t.
    """
    candidate_indexes = np.arange(window - 1, len(series.timestamps_ns), stride, dtype=np.int64)
    endpoint_times = series.timestamps_ns[candidate_indexes]
    start_times = series.timestamps_ns[candidate_indexes - (window - 1)]
    expected_span_ns = int((window - 1) * interval_delta.value)
    contiguous = (endpoint_times - start_times) == expected_span_ns
    valid = contiguous & ~np.isnan(series.labels[candidate_indexes])
    if endpoint_start_ns is not None:
        valid &= endpoint_times >= endpoint_start_ns
    if endpoint_end_ns is not None:
        valid &= endpoint_times < endpoint_end_ns
    return candidate_indexes[valid]


def _make_partition(
    symbols: list[str],
    series_by_symbol: dict[str, SymbolSeries],
    window: int,
    interval_delta: pd.Timedelta,
    endpoint_start: pd.Timestamp | None,
    endpoint_end: pd.Timestamp | None,
    stride: int,
) -> SequencePartition:
    start_ns = None if endpoint_start is None else endpoint_start.value
    end_ns = None if endpoint_end is None else endpoint_end.value
    parts: list[np.ndarray] = []
    for symbol_index, symbol in enumerate(symbols):
        indexes = _endpoint_indexes(
            series_by_symbol[symbol], window, interval_delta, start_ns, end_ns, stride
        )
        if len(indexes):
            parts.append(np.column_stack((np.full(len(indexes), symbol_index, dtype=np.int64), indexes)))
    if not parts:
        return SequencePartition(np.empty((0, 2), dtype=np.int64))
    endpoints = np.vstack(parts)
    # The model batches may iterate symbol by symbol, but this sort makes every partition's
    # chronology explicit for auditability and never mixes future rows into an earlier partition.
    endpoint_times = np.empty(len(endpoints), dtype=np.int64)
    for symbol_index, symbol in enumerate(symbols):
        symbol_mask = endpoints[:, 0] == symbol_index
        endpoint_times[symbol_mask] = series_by_symbol[symbol].timestamps_ns[
            endpoints[symbol_mask, 1]
        ]
    return SequencePartition(endpoints[np.argsort(endpoint_times, kind="stable")])


def _fit_scaler(
    series_by_symbol: dict[str, SymbolSeries],
    cutoff: pd.Timestamp,
) -> tuple[np.ndarray, np.ndarray]:
    """Fit standardization parameters solely on the older inner-training period."""
    count = 0
    total = np.zeros(len(FEATURE_COLUMNS), dtype=np.float64)
    total_squares = np.zeros(len(FEATURE_COLUMNS), dtype=np.float64)
    cutoff_ns = cutoff.value
    for series in series_by_symbol.values():
        values = series.features[series.timestamps_ns < cutoff_ns].astype(np.float64, copy=False)
        count += len(values)
        total += values.sum(axis=0)
        total_squares += np.square(values).sum(axis=0)
    if count == 0:
        raise ValueError("Cannot fit sequence scaler on an empty inner-training period.")
    mean = total / count
    variance = np.maximum((total_squares / count) - np.square(mean), 1e-12)
    return mean.astype(np.float32), np.sqrt(variance).astype(np.float32)


def build_sequence_data() -> SequenceData:
    """Load Phase 1 feature rows and create leakage-safe neural train/validation endpoints."""
    if not PROCESSED_DATA_PATH.is_file():
        raise FileNotFoundError("Phase 1 feature dataset is missing. Run app.ml.dataset first.")
    window, stride, interval_delta, horizon = _validate_sequence_settings()
    purged_train_end, final_validation_start = _phase1_cutoffs()
    label_column = f"entry_label_{horizon}b"
    return_column = f"future_return_{horizon}b"
    columns = [
        "timestamp",
        "symbol",
        *FEATURE_COLUMNS,
        label_column,
        return_column,
        "entry_return_threshold",
    ]
    frame = pd.read_parquet(PROCESSED_DATA_PATH, columns=columns)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    symbols = sorted(frame["symbol"].unique().tolist())
    series_by_symbol: dict[str, SymbolSeries] = {}
    for symbol, group in frame.groupby("symbol", sort=True):
        group = group.sort_values("timestamp", kind="stable")
        series_by_symbol[symbol] = SymbolSeries(
            features=group[FEATURE_COLUMNS].to_numpy(dtype=np.float32, copy=True),
            timestamps_ns=group["timestamp"].astype("int64").to_numpy(copy=True),
            labels=group[label_column].to_numpy(dtype=np.float32, copy=True),
            future_returns=group[return_column].to_numpy(dtype=np.float32, copy=True),
            thresholds=group["entry_return_threshold"].to_numpy(dtype=np.float32, copy=True),
        )

    # Inner validation is within the older Phase 1 training portion.  It selects the best epoch
    # without touching the final Phase 1 holdout; a 4-bar purge protects forward labels here too.
    all_train_times = frame.loc[frame["timestamp"] < purged_train_end, "timestamp"]
    inner_validation_start = all_train_times.min() + (
        (all_train_times.max() - all_train_times.min()) * (1.0 - settings.ml_neural_inner_validation_fraction)
    )
    inner_validation_start = inner_validation_start.ceil(interval_delta)
    inner_fit_end = inner_validation_start - (horizon * interval_delta)
    scaler_mean, scaler_std = _fit_scaler(series_by_symbol, inner_fit_end)

    fit = _make_partition(
        symbols, series_by_symbol, window, interval_delta, None, inner_fit_end, stride
    )
    inner_validation = _make_partition(
        symbols, series_by_symbol, window, interval_delta, inner_validation_start, purged_train_end, 1
    )
    # Final model training may use every valid Phase 1 train endpoint after epoch count is chosen.
    final_train = _make_partition(
        symbols, series_by_symbol, window, interval_delta, None, purged_train_end, stride
    )
    validation = _make_partition(
        symbols, series_by_symbol, window, interval_delta, final_validation_start, None, 1
    )
    if not len(fit.endpoints) or not len(inner_validation.endpoints) or not len(validation.endpoints):
        raise ValueError("At least one sequence partition is empty; inspect window, split, and data coverage.")

    manifest = {
        "model_input": "rolling causal feature sequences",
        "selected_phase1_horizon_bars": horizon,
        "sequence_window_bars": window,
        "sequence_training_stride": stride,
        "feature_count": len(FEATURE_COLUMNS),
        "features": FEATURE_COLUMNS,
        "inner_fit_end_utc": inner_fit_end.isoformat(),
        "inner_validation_start_utc": inner_validation_start.isoformat(),
        "final_validation_start_utc": final_validation_start.isoformat(),
        "fit_sequence_count": int(len(fit.endpoints)),
        "inner_validation_sequence_count": int(len(inner_validation.endpoints)),
        "final_train_sequence_count": int(len(final_train.endpoints)),
        "final_validation_sequence_count": int(len(validation.endpoints)),
        "scaler_fit_period": "Older inner-training period only; no final-holdout feature rows used.",
    }
    SEQUENCE_MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return SequenceData(
        symbols=symbols,
        series_by_symbol=series_by_symbol,
        fit=fit,
        inner_validation=inner_validation,
        final_train=final_train,
        validation=validation,
        scaler_mean=scaler_mean,
        scaler_std=scaler_std,
        inner_validation_start=inner_validation_start,
        final_validation_start=final_validation_start,
    )


def main() -> None:
    data = build_sequence_data()
    print(
        "Built Phase 2 sequence partitions with "
        f"{len(data.final_train.endpoints):,} final-train and "
        f"{len(data.validation.endpoints):,} final-validation endpoints."
    )


if __name__ == "__main__":
    main()
