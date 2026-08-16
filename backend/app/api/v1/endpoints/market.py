from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.services.binance_service import BinanceService
from app.services.market_data_service import MarketDataService

router = APIRouter(tags=["market"])
binance = BinanceService()
market_data = MarketDataService()

DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT"]


@router.get("/overview")
async def overview() -> dict:
    try:
        summary = await binance.get_market_summary(DEFAULT_SYMBOLS)
        btc = next((item for item in summary if item["symbol"] == "BTCUSDT"), None)
        eth = next((item for item in summary if item["symbol"] == "ETHUSDT"), None)
        
        # Get enhanced market data
        enhanced_data = await market_data.get_enhanced_market_overview()
        
        return {
            "btc_price": btc["price"] if btc else None,
            "eth_price": eth["price"] if eth else None,
            "market_cap": enhanced_data["market_cap"],
            "fear_greed_index": enhanced_data["fear_greed_index"],
            "fear_greed_classification": enhanced_data["fear_greed_classification"],
            "btc_dominance": enhanced_data["btc_dominance"],
            "eth_dominance": enhanced_data["eth_dominance"],
            "volume_24h": enhanced_data["volume_24h"],
            "updated_at": enhanced_data["updated_at"],
            "summary": summary,
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Unable to load market overview: {exc}") from exc


@router.get("/summary")
async def summary() -> dict:
    try:
        return {
            "items": await binance.get_market_summary(DEFAULT_SYMBOLS),
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Unable to load market summary: {exc}") from exc


@router.get("/all")
async def all_cryptos(quote_asset: str = Query("USDT")) -> dict:
    try:
        return {
            "quote_asset": quote_asset.upper(),
            "items": await binance.get_all_prices(quote_asset=quote_asset),
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Unable to load crypto prices: {exc}") from exc


@router.get("/trending")
async def trending() -> dict:
    try:
        items = await binance.get_market_summary(DEFAULT_SYMBOLS)
        gainers = sorted(items, key=lambda item: item["change_24h"], reverse=True)
        losers = sorted(items, key=lambda item: item["change_24h"])
        return {
            "gainers": gainers[:3],
            "losers": losers[:3],
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Unable to load trending markets: {exc}") from exc


@router.get("/candles")
async def candles(
    symbol: str = Query(..., min_length=3),
    interval: str = Query("1h"),
    limit: int = Query(100, ge=10, le=500),
) -> dict:
    try:
        candle_payload = await binance.get_candles(symbol, interval=interval, limit=limit)
        return {
            "symbol": symbol.upper(),
            "interval": interval,
            "candles": BinanceService.candles_to_chart_payload(candle_payload),
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Unable to load candles: {exc}") from exc
