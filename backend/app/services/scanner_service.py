from __future__ import annotations

import asyncio
from dataclasses import dataclass

from app.services.binance_service import BinanceService
from app.services.indicator_service import build_trend_pack


@dataclass
class ScannerResult:
    symbol: str
    interval: str
    trend: str
    strength: str
    rsi: float | None
    ema_fast: float | None
    ema_slow: float | None
    macd: dict[str, float | None]
    last_price: float | None


class ScannerService:
    def __init__(self, binance_service: BinanceService | None = None) -> None:
        self.binance = binance_service or BinanceService()

    async def scan_symbol(self, symbol: str, interval: str = "1h", limit: int = 100) -> ScannerResult:
        candles = await self.binance.get_candles(symbol, interval=interval, limit=limit)
        pack = build_trend_pack(
            [
                {
                    "close": candle.close,
                    "open": candle.open,
                    "high": candle.high,
                    "low": candle.low,
                    "volume": candle.volume,
                }
                for candle in candles
            ]
        )
        last_price = candles[-1].close if candles else None
        return ScannerResult(
            symbol=symbol.upper(),
            interval=interval,
            trend=pack.trend,
            strength=pack.strength,
            rsi=pack.rsi,
            ema_fast=pack.ema_fast,
            ema_slow=pack.ema_slow,
            macd=pack.macd,
            last_price=last_price,
        )

    async def scan_watchlist(self, symbols: list[str], intervals: list[str] | None = None) -> list[dict]:
        intervals = intervals or ["15m", "1h", "4h"]
        tasks = [self._scan_symbol_intervals(symbol, intervals) for symbol in symbols]
        return await asyncio.gather(*tasks)

    async def _scan_symbol_intervals(self, symbol: str, intervals: list[str]) -> dict:
        row: dict[str, object] = {"symbol": symbol.upper(), "timeframes": []}
        tasks = [self.scan_symbol(symbol, interval=interval) for interval in intervals]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for interval, result in zip(intervals, results, strict=False):
            if isinstance(result, Exception):
                row["timeframes"].append(
                    {
                        "interval": interval,
                        "trend": "error",
                        "strength": "weak",
                        "error": str(result),
                    }
                )
                continue
            row["timeframes"].append(
                {
                    "interval": interval,
                    "trend": result.trend,
                    "strength": result.strength,
                    "rsi": result.rsi,
                    "last_price": result.last_price,
                }
            )
        return row
