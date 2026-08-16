from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


def _closing_prices(candles: Iterable[dict]) -> list[float]:
    return [float(candle["close"]) for candle in candles]


def calculate_ema(values: list[float], period: int) -> float | None:
    if len(values) < period or period <= 0:
        return None
    multiplier = 2 / (period + 1)
    ema = sum(values[:period]) / period
    for value in values[period:]:
        ema = (value - ema) * multiplier + ema
    return round(ema, 8)


def calculate_rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) <= period:
        return None
    gains = 0.0
    losses = 0.0
    for i in range(1, period + 1):
        delta = values[i] - values[i - 1]
        if delta >= 0:
            gains += delta
        else:
            losses += abs(delta)
    avg_gain = gains / period
    avg_loss = losses / period
    for i in range(period + 1, len(values)):
        delta = values[i] - values[i - 1]
        gain = max(delta, 0.0)
        loss = max(-delta, 0.0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def calculate_macd(values: list[float]) -> dict[str, float | None]:
    ema12 = calculate_ema(values, 12)
    ema26 = calculate_ema(values, 26)
    if ema12 is None or ema26 is None:
        return {"macd": None, "signal": None, "histogram": None}

    macd_line = ema12 - ema26
    macd_source = []
    for idx in range(len(values)):
        short = calculate_ema(values[: idx + 1], 12)
        long = calculate_ema(values[: idx + 1], 26)
        if short is not None and long is not None:
            macd_source.append(short - long)

    signal = calculate_ema(macd_source, 9)
    histogram = None if signal is None else round(macd_line - signal, 8)
    return {
        "macd": round(macd_line, 8),
        "signal": signal,
        "histogram": histogram,
    }


@dataclass
class TrendPack:
    trend: str
    strength: str
    rsi: float | None
    ema_fast: float | None
    ema_slow: float | None
    macd: dict[str, float | None]


def build_trend_pack(candles: list[dict]) -> TrendPack:
    closes = _closing_prices(candles)
    ema_fast = calculate_ema(closes, 9)
    ema_slow = calculate_ema(closes, 21)
    rsi = calculate_rsi(closes)
    macd = calculate_macd(closes)

    trend = "neutral"
    if ema_fast is not None and ema_slow is not None:
        if ema_fast > ema_slow:
            trend = "bullish"
        elif ema_fast < ema_slow:
            trend = "bearish"

    strength = "weak"
    if rsi is not None:
        if 55 <= rsi <= 70 and trend == "bullish":
            strength = "strong"
        elif 30 <= rsi <= 45 and trend == "bearish":
            strength = "strong"
        elif 45 < rsi < 55:
            strength = "moderate"

    return TrendPack(
        trend=trend,
        strength=strength,
        rsi=rsi,
        ema_fast=ema_fast,
        ema_slow=ema_slow,
        macd=macd,
    )
