"""Fetch the configured Phase 1 OHLCV inputs from the approved Kaggle dataset.

This module deliberately downloads selected files rather than the full all-pairs archive.  It
is an offline data-acquisition step only: it does not connect to, signal, or trade through the
live TradeMind services.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import kagglehub

from app.core.config import settings

BACKEND_DIR = Path(__file__).resolve().parents[2]
RAW_DATA_DIR = BACKEND_DIR / "data" / "raw"
MANIFEST_PATH = RAW_DATA_DIR / "phase1_data_manifest.json"

# Kaggle's source directory names differ from Binance interval identifiers.
KAGGLE_TIMEFRAME_DIRECTORIES = {
    "5m": "minute_5",
    "15m": "minute_15",
    "30m": "minute_30",
    "1h": "hour_1",
    "4h": "hour_4",
    "1d": "day_1",
}


def configured_symbols() -> list[str]:
    """Return normalized, unique symbols in their configured order."""
    symbols = [symbol.strip().upper() for symbol in settings.ml_training_symbols.split(",")]
    normalized = [symbol for symbol in symbols if symbol]
    if len(normalized) < 5:
        raise ValueError("ML_TRAINING_SYMBOLS must include BTCUSDT, ETHUSDT, and at least three liquid pairs.")
    if len(normalized) != len(set(normalized)):
        raise ValueError("ML_TRAINING_SYMBOLS contains duplicate symbols.")
    return normalized


def source_relative_path(symbol: str, interval: str) -> str:
    """Map a configured Binance interval to the selected Kaggle dataset directory."""
    try:
        kaggle_directory = KAGGLE_TIMEFRAME_DIRECTORIES[interval]
    except KeyError as exc:
        allowed = ", ".join(sorted(KAGGLE_TIMEFRAME_DIRECTORIES))
        raise ValueError(f"Unsupported TRADING_CANDLE_INTERVAL={interval!r}; allowed values: {allowed}.") from exc
    return f"{kaggle_directory}/{symbol}.csv"


def sha256(path: Path) -> str:
    """Create a stable checksum so every fitted artifact can be tied to exact raw inputs."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_one(symbol: str, interval: str, force: bool) -> dict[str, str | int]:
    """Download one source file via KaggleHub and copy it into the project-owned raw-data directory."""
    relative_path = source_relative_path(symbol, interval)
    local_path = RAW_DATA_DIR / f"{symbol}_{interval}.csv"

    downloaded = Path(
        kagglehub.dataset_download(
            f"{settings.ml_kaggle_dataset}/versions/{settings.ml_kaggle_dataset_version}",
            path=relative_path,
            force_download=force,
        )
    )

    # KaggleHub returns the downloaded file for a file request.  The fallback also handles
    # client versions that return a parent cache directory without relying on shell paths.
    source_path = downloaded
    if source_path.is_dir():
        source_path = source_path / relative_path
    if not source_path.is_file():
        raise FileNotFoundError(
            f"KaggleHub did not return {relative_path}; received {downloaded}. "
            "Check the dataset version and source file structure."
        )

    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, local_path)
    return {
        "symbol": symbol,
        "interval": interval,
        "kaggle_relative_path": relative_path,
        "local_path": str(local_path.relative_to(BACKEND_DIR)),
        "bytes": local_path.stat().st_size,
        "sha256": sha256(local_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch selected Phase 1 OHLCV files from Kaggle.")
    parser.add_argument("--force", action="store_true", help="Force KaggleHub to refresh cached source files.")
    args = parser.parse_args()

    interval = settings.trading_candle_interval.strip().lower()
    records = [fetch_one(symbol, interval, args.force) for symbol in configured_symbols()]
    manifest = {
        "source": "Kaggle",
        "dataset": settings.ml_kaggle_dataset,
        "dataset_version": settings.ml_kaggle_dataset_version,
        "interval": interval,
        "interval_status": "PROVISIONAL — confirm against TradeMind live configuration before production use.",
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "files": records,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Fetched {len(records)} Kaggle OHLCV files; manifest: {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
