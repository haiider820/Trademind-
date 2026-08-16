"""Build leakage-safe Phase 1 feature and label datasets from validated OHLCV inputs.

Every feature at timestamp *t* uses candles available no later than the close of candle *t*.
Labels are created separately from future closes and are never available to the model at inference.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from app.core.config import settings

# Serving and retraining should not import Kaggle acquisition dependencies.
BACKEND_DIR = Path(__file__).resolve().parents[2]
RAW_DATA_DIR = BACKEND_DIR / "data" / "raw"
PROCESSED_DATA_PATH = BACKEND_DIR / "data" / "processed" / "phase1_features_labeled.parquet"
SPLIT_MANIFEST_PATH = BACKEND_DIR / "data" / "processed" / "phase1_split_manifest.json"

INTERVAL_TO_DELTA = {
    "5m": pd.Timedelta(minutes=5),
    "15m": pd.Timedelta(minutes=15),
    "30m": pd.Timedelta(minutes=30),
    "1h": pd.Timedelta(hours=1),
    "4h": pd.Timedelta(hours=4),
    "1d": pd.Timedelta(days=1),
}

FEATURE_COLUMNS = [
    "return_1",
    "return_4",
    "return_16",
    "rsi_14",
    "atr_pct_14",
    "volatility_16",
    "volatility_64",
    "ema_fast_slow_pct",
    "ema_cross_up",
    "ema_cross_down",
    "macd_pct",
    "macd_signal_pct",
    "macd_hist_pct",
    "bollinger_zscore_20",
    "bollinger_width_20",
    "candle_body_pct",
    "upper_wick_pct",
    "lower_wick_pct",
    "range_pct",
    "relative_volume_20",
    "quote_volume_zscore_20",
    "taker_buy_imbalance",
    "vwap_distance_20",
    "volume_concentration_20",
]


@dataclass(frozen=True)
class SplitFrames:
    """A globally chronological train/validation partition with no cross-boundary labels."""

    train: pd.DataFrame
    validation: pd.DataFrame
    validation_start: pd.Timestamp
    purged_train_end: pd.Timestamp


def configured_horizons() -> list[int]:
    """Parse and validate the forward-horizon candidates supplied through one config value."""
    try:
        horizons = sorted({int(value.strip()) for value in settings.ml_label_horizons_bars.split(",") if value.strip()})
    except ValueError as exc:
        raise ValueError("ML_LABEL_HORIZONS_BARS must contain positive integer bar counts.") from exc
    if not horizons or any(horizon <= 0 for horizon in horizons):
        raise ValueError("ML_LABEL_HORIZONS_BARS must contain at least one positive horizon.")
    return horizons


def _seeded_ema(values: pd.Series, period: int) -> pd.Series:
    """Calculate EMA with an SMA seed, matching the live scanner's EMA convention."""
    result = pd.Series(np.nan, index=values.index, dtype=float)
    if len(values) < period:
        return result

    multiplier = 2.0 / (period + 1.0)
    seed = float(values.iloc[:period].mean())
    result.iloc[period - 1] = seed
    previous = seed
    for index in range(period, len(values)):
        value = float(values.iloc[index])
        previous = (value - previous) * multiplier + previous
        result.iloc[index] = previous
    return result


def _wilder_smoothing(values: pd.Series, period: int) -> pd.Series:
    """Calculate Wilder smoothing with an SMA seed for RSI and ATR."""
    result = pd.Series(np.nan, index=values.index, dtype=float)
    valid_start = values.first_valid_index()
    if valid_start is None:
        return result
    start_position = values.index.get_loc(valid_start)
    seed_end = start_position + period
    if len(values) < seed_end:
        return result

    seed_slice = values.iloc[start_position:seed_end]
    if seed_slice.isna().any():
        return result
    previous = float(seed_slice.mean())
    result.iloc[seed_end - 1] = previous
    for index in range(seed_end, len(values)):
        value = values.iloc[index]
        if pd.isna(value):
            continue
        previous = ((previous * (period - 1)) + float(value)) / period
        result.iloc[index] = previous
    return result


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gains = delta.clip(lower=0.0)
    losses = (-delta.clip(upper=0.0)).astype(float)
    average_gain = _wilder_smoothing(gains, period)
    average_loss = _wilder_smoothing(losses, period)
    rs = average_gain / average_loss.replace(0.0, np.nan)
    result = 100.0 - (100.0 / (1.0 + rs))
    # A zero average loss means all observed changes in the smoothing window were non-negative.
    return result.mask((average_loss == 0.0) & (average_gain > 0.0), 100.0)


def _atr(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    previous_close = frame["close"].shift(1)
    true_range = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - previous_close).abs(),
            (frame["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return _wilder_smoothing(true_range, period)


def load_raw_ohlcv(symbol: str, interval: str) -> pd.DataFrame:
    """Load one validated source file and reject unexpected chronology defects."""
    path = RAW_DATA_DIR / f"{symbol}_{interval}.csv"
    if not path.is_file():
        raise FileNotFoundError(f"Raw file not found: {path}. Run app.ml.fetch_historical_data first.")

    frame = pd.read_csv(path)
    frame["open_time"] = pd.to_datetime(frame["open_time"], utc=True, errors="raise")
    for column in (
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_asset_volume",
        "number_of_traders",
        "taker_buy_base_asset_volume",
    ):
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    frame = frame.sort_values("open_time", kind="stable").reset_index(drop=True)
    if frame["open_time"].duplicated().any():
        raise ValueError(f"{path.name} contains duplicate open timestamps.")
    return frame


def build_symbol_dataset(symbol: str, interval: str, horizons: Iterable[int]) -> pd.DataFrame:
    """Create causal features and separately named forward labels for one trading pair."""
    frame = load_raw_ohlcv(symbol, interval)
    close = frame["close"]
    epsilon = 1e-12

    # All indicators in this block use rolling windows ending at the current completed candle.
    frame["return_1"] = np.log(close / close.shift(1))
    frame["return_4"] = np.log(close / close.shift(4))
    frame["return_16"] = np.log(close / close.shift(16))
    frame["rsi_14"] = _rsi(close, 14)
    frame["atr_14"] = _atr(frame, 14)
    frame["atr_pct_14"] = frame["atr_14"] / close
    frame["volatility_16"] = frame["return_1"].rolling(16, min_periods=16).std(ddof=0)
    frame["volatility_64"] = frame["return_1"].rolling(64, min_periods=64).std(ddof=0)

    ema_fast = _seeded_ema(close, 9)
    ema_slow = _seeded_ema(close, 21)
    frame["ema_fast_slow_pct"] = (ema_fast - ema_slow) / close
    prior_difference = (ema_fast - ema_slow).shift(1)
    current_difference = ema_fast - ema_slow
    frame["ema_cross_up"] = ((current_difference > 0.0) & (prior_difference <= 0.0)).astype(int)
    frame["ema_cross_down"] = ((current_difference < 0.0) & (prior_difference >= 0.0)).astype(int)

    macd = _seeded_ema(close, 12) - _seeded_ema(close, 26)
    macd_signal = _seeded_ema(macd.dropna().reset_index(drop=True), 9)
    macd_signal.index = macd.dropna().index
    frame["macd_pct"] = macd / close
    frame["macd_signal_pct"] = macd_signal / close
    frame["macd_hist_pct"] = (macd - macd_signal) / close

    rolling_mean = close.rolling(20, min_periods=20).mean()
    rolling_std = close.rolling(20, min_periods=20).std(ddof=0)
    frame["bollinger_zscore_20"] = (close - rolling_mean) / rolling_std.replace(0.0, np.nan)
    frame["bollinger_width_20"] = (4.0 * rolling_std) / rolling_mean

    candle_range = (frame["high"] - frame["low"]).replace(0.0, np.nan)
    frame["candle_body_pct"] = (frame["close"] - frame["open"]) / close
    frame["upper_wick_pct"] = (frame["high"] - frame[["open", "close"]].max(axis=1)) / close
    frame["lower_wick_pct"] = (frame[["open", "close"]].min(axis=1) - frame["low"]) / close
    frame["range_pct"] = candle_range / close

    rolling_volume = frame["volume"].rolling(20, min_periods=20)
    frame["relative_volume_20"] = frame["volume"] / rolling_volume.mean().replace(0.0, np.nan)
    quote_mean = frame["quote_asset_volume"].rolling(20, min_periods=20).mean()
    quote_std = frame["quote_asset_volume"].rolling(20, min_periods=20).std(ddof=0)
    frame["quote_volume_zscore_20"] = (frame["quote_asset_volume"] - quote_mean) / quote_std.replace(0.0, np.nan)
    frame["taker_buy_imbalance"] = (
        (2.0 * frame["taker_buy_base_asset_volume"]) - frame["volume"]
    ) / (frame["volume"] + epsilon)

    # OHLCV cannot reveal true volume-at-price.  These are causal bar-level volume-profile
    # proxies: rolling VWAP location and concentration of current volume in the recent window.
    typical_price = (frame["high"] + frame["low"] + frame["close"]) / 3.0
    rolling_vwap = (typical_price * frame["volume"]).rolling(20, min_periods=20).sum() / rolling_volume.sum()
    frame["vwap_distance_20"] = (close - rolling_vwap) / rolling_vwap
    frame["volume_concentration_20"] = frame["volume"] / rolling_volume.sum().replace(0.0, np.nan)

    atr_return_threshold = settings.ml_entry_atr_multiple * frame["atr_pct_14"]
    frame["entry_return_threshold"] = np.maximum(atr_return_threshold, settings.ml_round_trip_cost_floor)
    interval_delta = INTERVAL_TO_DELTA[interval]
    for horizon in horizons:
        future_close = close.shift(-horizon)
        future_timestamp = frame["open_time"].shift(-horizon)
        # A label cannot span a maintenance/data gap; doing so would make a nominal horizon ambiguous.
        contiguous_forward_window = (future_timestamp - frame["open_time"]) == (horizon * interval_delta)
        frame[f"future_return_{horizon}b"] = (future_close / close) - 1.0
        frame[f"entry_label_{horizon}b"] = np.where(
            contiguous_forward_window & future_close.notna(),
            (frame[f"future_return_{horizon}b"] > frame["entry_return_threshold"]).astype(float),
            np.nan,
        )

    frame["symbol"] = symbol
    frame = frame.rename(columns={"open_time": "timestamp"})
    requested_columns = [
        "timestamp",
        "symbol",
        "entry_return_threshold",
        "atr_14",
        *FEATURE_COLUMNS,
        *[f"future_return_{horizon}b" for horizon in horizons],
        *[f"entry_label_{horizon}b" for horizon in horizons],
    ]
    result = frame[requested_columns].replace([np.inf, -np.inf], np.nan)
    required_for_features = ["timestamp", "symbol", "entry_return_threshold", "atr_14", *FEATURE_COLUMNS]
    return result.dropna(subset=required_for_features).reset_index(drop=True)


def make_global_chronological_split(dataset: pd.DataFrame, interval: str, horizons: Iterable[int]) -> SplitFrames:
    """Split on one global cutoff, then purge all train labels touching the validation window."""
    if not 0.05 <= settings.ml_holdout_fraction < 0.5:
        raise ValueError("ML_HOLDOUT_FRACTION must be at least 0.05 and below 0.50.")
    interval_delta = INTERVAL_TO_DELTA[interval]
    max_horizon = max(horizons)
    global_start = dataset["timestamp"].min()
    global_end = dataset["timestamp"].max()
    validation_start = global_start + ((global_end - global_start) * (1.0 - settings.ml_holdout_fraction))
    validation_start = validation_start.ceil(interval_delta)
    purged_train_end = validation_start - (max_horizon * interval_delta)

    train = dataset.loc[dataset["timestamp"] < purged_train_end].copy()
    validation = dataset.loc[dataset["timestamp"] >= validation_start].copy()
    if train.empty or validation.empty:
        raise ValueError("Chronological split produced an empty train or validation partition.")
    if train["timestamp"].max() >= validation["timestamp"].min():
        raise AssertionError("Chronological split leakage guard failed.")
    return SplitFrames(train=train, validation=validation, validation_start=validation_start, purged_train_end=purged_train_end)


def build_and_persist_dataset() -> SplitFrames:
    """Build all pair datasets, persist features, and record the leakage-safe split contract."""
    interval = settings.trading_candle_interval.strip().lower()
    if interval not in INTERVAL_TO_DELTA:
        raise ValueError(f"Unsupported configured candle interval: {interval!r}")
    if settings.trading_market_mode.lower() != "spot":
        raise ValueError("Phase 1 labels are approved only for provisional spot-only execution mode.")
    if settings.ml_entry_atr_multiple <= 0.0:
        raise ValueError("ML_ENTRY_ATR_MULTIPLE must be positive.")
    if settings.ml_round_trip_cost_floor <= 0.0:
        raise ValueError("ML_ROUND_TRIP_COST_FLOOR must be positive.")

    horizons = configured_horizons()
    from app.ml.fetch_historical_data import configured_symbols

    datasets = [build_symbol_dataset(symbol, interval, horizons) for symbol in configured_symbols()]
    combined = pd.concat(datasets, ignore_index=True).sort_values(["timestamp", "symbol"], kind="stable")
    split = make_global_chronological_split(combined, interval, horizons)

    PROCESSED_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(PROCESSED_DATA_PATH, index=False)
    manifest = {
        "interval": interval,
        "interval_status": "PROVISIONAL — confirm against TradeMind live configuration before production use.",
        "market_mode": settings.trading_market_mode,
        "market_mode_status": "PROVISIONAL — confirm spot-only execution before production use.",
        "label_definition": {
            "target": "long-only entry / no-entry",
            "rule": "future close return > max(ATR(14) multiple at entry, round-trip cost floor)",
            "atr_multiple": settings.ml_entry_atr_multiple,
            "round_trip_cost_floor": settings.ml_round_trip_cost_floor,
            "candidate_horizons_bars": horizons,
        },
        "feature_count": len(FEATURE_COLUMNS),
        "feature_columns": FEATURE_COLUMNS,
        "rows_total": int(len(combined)),
        "global_validation_start_utc": split.validation_start.isoformat(),
        "purged_train_end_utc": split.purged_train_end.isoformat(),
        "rows_train": int(len(split.train)),
        "rows_validation": int(len(split.validation)),
        "rows_by_symbol": combined.groupby("symbol", sort=True).size().astype(int).to_dict(),
    }
    SPLIT_MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return split


def main() -> None:
    split = build_and_persist_dataset()
    print(
        "Persisted Phase 1 dataset with "
        f"{len(split.train):,} train rows and {len(split.validation):,} validation rows."
    )


if __name__ == "__main__":
    main()
