"""Validate raw Kaggle OHLCV files before feature engineering or model fitting."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from app.core.config import settings
from app.ml.fetch_historical_data import BACKEND_DIR, configured_symbols

RAW_DATA_DIR = BACKEND_DIR / "data" / "raw"
REPORT_PATH = BACKEND_DIR / "reports" / "phase1_data_quality.json"
REQUIRED_COLUMNS = {
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_asset_volume",
    "number_of_traders",
    "taker_buy_base_asset_volume",
    "taker_buy_quote_asset_volume",
}
INTERVAL_TO_DELTA = {
    "5m": pd.Timedelta(minutes=5),
    "15m": pd.Timedelta(minutes=15),
    "30m": pd.Timedelta(minutes=30),
    "1h": pd.Timedelta(hours=1),
    "4h": pd.Timedelta(hours=4),
    "1d": pd.Timedelta(days=1),
}


def validate_symbol(symbol: str, interval: str) -> dict[str, object]:
    """Return auditable quality metrics for one raw OHLCV file."""
    path = RAW_DATA_DIR / f"{symbol}_{interval}.csv"
    if not path.is_file():
        raise FileNotFoundError(f"Missing raw input: {path}. Run app.ml.fetch_historical_data first.")

    frame = pd.read_csv(path)
    missing_columns = sorted(REQUIRED_COLUMNS.difference(frame.columns))
    if missing_columns:
        raise ValueError(f"{path.name} is missing required columns: {', '.join(missing_columns)}")

    frame["open_time"] = pd.to_datetime(frame["open_time"], utc=True, errors="coerce")
    frame["close_time"] = pd.to_datetime(frame["close_time"], utc=True, errors="coerce")
    price_columns = ["open", "high", "low", "close", "volume", "quote_asset_volume"]
    for column in price_columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    timestamp_nulls = int(frame[["open_time", "close_time"]].isna().any(axis=1).sum())
    duplicate_timestamps = int(frame["open_time"].duplicated().sum())
    is_monotonic = bool(frame["open_time"].is_monotonic_increasing)
    delta = INTERVAL_TO_DELTA[interval]
    diffs = frame["open_time"].diff()

    # Exchange maintenance gaps are not fabricated or forward-filled.  The report makes the
    # gap count visible so later labelling can avoid horizons that cross a missing candle.
    gap_mask = diffs > delta
    gap_count = int(gap_mask.sum())
    missing_bar_estimate = int(((diffs[gap_mask] / delta) - 1).sum()) if gap_count else 0

    invalid_ohlc = int(
        (
            (frame["open"] <= 0)
            | (frame["high"] <= 0)
            | (frame["low"] <= 0)
            | (frame["close"] <= 0)
            | (frame["high"] < frame[["open", "close", "low"]].max(axis=1))
            | (frame["low"] > frame[["open", "close", "high"]].min(axis=1))
        ).sum()
    )
    negative_volume = int((frame["volume"] < 0).sum())

    return {
        "symbol": symbol,
        "rows": int(len(frame)),
        "first_open_time_utc": frame["open_time"].min().isoformat(),
        "last_open_time_utc": frame["open_time"].max().isoformat(),
        "timestamp_null_rows": timestamp_nulls,
        "duplicate_open_times": duplicate_timestamps,
        "chronologically_sorted": is_monotonic,
        "gaps_larger_than_interval": gap_count,
        "estimated_missing_bars": missing_bar_estimate,
        "invalid_ohlc_rows": invalid_ohlc,
        "negative_volume_rows": negative_volume,
    }


def main() -> None:
    interval = settings.trading_candle_interval.strip().lower()
    if interval not in INTERVAL_TO_DELTA:
        raise ValueError(f"No validation interval mapping for {interval!r}.")

    reports = [validate_symbol(symbol, interval) for symbol in configured_symbols()]
    failed_symbols = [
        report["symbol"]
        for report in reports
        if any(
            report[key]
            for key in (
                "timestamp_null_rows",
                "duplicate_open_times",
                "invalid_ohlc_rows",
                "negative_volume_rows",
            )
        )
        or not report["chronologically_sorted"]
    ]
    summary = {
        "interval": interval,
        "interval_status": "PROVISIONAL — confirm against TradeMind live configuration before production use.",
        "symbols": reports,
        "passed_schema_and_price_sanity": not failed_symbols,
        "failed_symbols": failed_symbols,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote data-quality report: {REPORT_PATH}")
    if failed_symbols:
        raise SystemExit(f"Data-quality checks failed for: {', '.join(failed_symbols)}")


if __name__ == "__main__":
    main()
