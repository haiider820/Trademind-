"""
Market Data Service - Provides Fear & Greed Index, Market Cap, and BTC Dominance
"""
from __future__ import annotations

import httpx
from datetime import datetime


class MarketDataService:
    """Service to fetch additional market data like Fear & Greed Index"""

    def __init__(self):
        self.fear_greed_url = "https://api.alternative.me/fng/"
        self.coingecko_global_url = "https://api.coingecko.com/api/v3/global"

    async def get_fear_greed_index(self) -> dict:
        """
        Fetch Fear & Greed Index from Alternative.me API
        Returns: {"value": 50, "classification": "Neutral"}
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.fear_greed_url)
                response.raise_for_status()
                data = response.json()
                
                if data.get("data") and len(data["data"]) > 0:
                    latest = data["data"][0]
                    return {
                        "value": int(latest.get("value", 50)),
                        "classification": latest.get("value_classification", "Neutral"),
                        "timestamp": latest.get("timestamp", ""),
                    }
        except Exception as e:
            print(f"Fear & Greed API error: {e}")
        
        # Fallback
        return {
            "value": 50,
            "classification": "Neutral",
            "timestamp": str(int(datetime.now().timestamp())),
        }

    async def get_global_market_data(self) -> dict:
        """
        Fetch global market data from CoinGecko
        Returns: {"market_cap": 2500000000000, "btc_dominance": 45.5}
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.coingecko_global_url)
                response.raise_for_status()
                data = response.json()
                
                if data.get("data"):
                    global_data = data["data"]
                    return {
                        "total_market_cap": global_data.get("total_market_cap", {}).get("usd", 0),
                        "btc_dominance": round(global_data.get("market_cap_percentage", {}).get("btc", 0), 2),
                        "eth_dominance": round(global_data.get("market_cap_percentage", {}).get("eth", 0), 2),
                        "total_volume_24h": global_data.get("total_volume", {}).get("usd", 0),
                        "active_cryptocurrencies": global_data.get("active_cryptocurrencies", 0),
                    }
        except Exception as e:
            print(f"CoinGecko API error: {e}")
        
        # Fallback
        return {
            "total_market_cap": 0,
            "btc_dominance": 0,
            "eth_dominance": 0,
            "total_volume_24h": 0,
            "active_cryptocurrencies": 0,
        }

    async def get_enhanced_market_overview(self) -> dict:
        """
        Combine Fear & Greed with global market data
        """
        fear_greed = await self.get_fear_greed_index()
        global_data = await self.get_global_market_data()
        
        return {
            "fear_greed_index": fear_greed["value"],
            "fear_greed_classification": fear_greed["classification"],
            "market_cap": global_data["total_market_cap"],
            "btc_dominance": global_data["btc_dominance"],
            "eth_dominance": global_data["eth_dominance"],
            "volume_24h": global_data["total_volume_24h"],
            "active_cryptocurrencies": global_data["active_cryptocurrencies"],
            "updated_at": datetime.utcnow().isoformat(),
        }
