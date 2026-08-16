from __future__ import annotations

from app.services.binance_service import BinanceService


class ExternalMarketService:
    def __init__(self) -> None:
        self.binance = BinanceService()

    async def get_overview(self) -> dict:
        summary = await self.binance.get_market_summary(["BTCUSDT", "ETHUSDT", "SOLUSDT"])
        btc = next((item for item in summary if item["symbol"] == "BTCUSDT"), None)
        eth = next((item for item in summary if item["symbol"] == "ETHUSDT"), None)
        return {
            "btc_price": btc["price"] if btc else None,
            "eth_price": eth["price"] if eth else None,
            "market_cap": None,
            "fear_greed_index": None,
            "btc_dominance": None,
            "summary": summary,
        }
