from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx


BINANCE_SPOT_BASE = "https://api.binance.com"
BINANCE_FUTURES_BASE = "https://fapi.binance.com"


@dataclass
class BinanceCandle:
    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time: int


class BinanceService:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=20.0)

    async def close(self) -> None:
        await self._client.aclose()

    async def _get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        response = await self._client.get(url, params=params)
        response.raise_for_status()
        return response.json()

    async def get_price(self, symbol: str) -> float:
        payload = await self._get_json(
            f"{BINANCE_SPOT_BASE}/api/v3/ticker/price",
            params={"symbol": symbol.upper()},
        )
        return float(payload["price"])

    async def get_all_prices(self, quote_asset: str = "USDT") -> list[dict[str, Any]]:
        payload = await self._get_json(f"{BINANCE_SPOT_BASE}/api/v3/ticker/price")
        symbols = [item for item in payload if item.get("symbol", "").endswith(quote_asset.upper())]

        tickers = await self._get_json(f"{BINANCE_SPOT_BASE}/api/v3/ticker/24hr")
        ticker_map = {
            item["symbol"]: item
            for item in tickers
            if isinstance(item, dict) and item.get("symbol", "").endswith(quote_asset.upper())
        }

        results: list[dict[str, Any]] = []
        for item in symbols:
            symbol = item["symbol"]
            ticker = ticker_map.get(symbol, {})
            results.append(
                {
                    "symbol": symbol,
                    "price": float(item["price"]),
                    "change_24h": float(ticker.get("priceChangePercent", 0) or 0),
                    "volume_24h": float(ticker.get("volume", 0) or 0),
                }
            )

        results.sort(key=lambda row: row["symbol"])
        return results

    async def get_ticker_24h(self, symbol: str) -> dict[str, Any]:
        payload = await self._get_json(
            f"{BINANCE_SPOT_BASE}/api/v3/ticker/24hr",
            params={"symbol": symbol.upper()},
        )
        return {
            "symbol": payload["symbol"],
            "last_price": float(payload["lastPrice"]),
            "price_change_percent": float(payload["priceChangePercent"]),
            "high_price": float(payload["highPrice"]),
            "low_price": float(payload["lowPrice"]),
            "volume": float(payload["volume"]),
            "quote_volume": float(payload["quoteVolume"]),
            "open_price": float(payload["openPrice"]),
            "open_time": int(payload["openTime"]),
            "close_time": int(payload["closeTime"]),
        }

    async def get_candles(self, symbol: str, interval: str = "1h", limit: int = 100) -> list[BinanceCandle]:
        payload = await self._get_json(
            f"{BINANCE_SPOT_BASE}/api/v3/klines",
            params={
                "symbol": symbol.upper(),
                "interval": interval,
                "limit": max(10, min(limit, 500)),
            },
        )
        candles: list[BinanceCandle] = []
        for row in payload:
            candles.append(
                BinanceCandle(
                    open_time=int(row[0]),
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[5]),
                    close_time=int(row[6]),
                )
            )
        return candles

    async def get_futures_open_interest(self, symbol: str) -> float | None:
        try:
            payload = await self._get_json(
                f"{BINANCE_FUTURES_BASE}/fapi/v1/openInterest",
                params={"symbol": symbol.upper()},
            )
            return float(payload["openInterest"])
        except Exception:
            return None

    async def get_market_summary(self, symbols: list[str]) -> list[dict[str, Any]]:
        async def _build(symbol: str) -> dict[str, Any] | None:
            try:
                ticker, ohlc, futures_interest = await asyncio.gather(
                    self.get_ticker_24h(symbol),
                    self.get_candles(symbol, interval="1h", limit=24),
                    self.get_futures_open_interest(symbol),
                )
                last_candle = ohlc[-1] if ohlc else None
                return {
                    "symbol": symbol.upper(),
                    "price": ticker["last_price"],
                    "change_24h": ticker["price_change_percent"],
                    "high_24h": ticker["high_price"],
                    "low_24h": ticker["low_price"],
                    "volume_24h": ticker["volume"],
                    "quote_volume_24h": ticker["quote_volume"],
                    "open_interest": futures_interest,
                    "last_candle_close": last_candle.close if last_candle else ticker["last_price"],
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            except Exception:
                return None

        results = await asyncio.gather(*[_build(symbol) for symbol in symbols])
        return [item for item in results if item is not None]

    @staticmethod
    def candles_to_chart_payload(candles: list[BinanceCandle]) -> list[dict[str, Any]]:
        return [
            {
                "open_time": candle.open_time,
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "volume": candle.volume,
                "close_time": candle.close_time,
            }
            for candle in candles
        ]
