from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.services.scanner_service import ScannerService

router = APIRouter(tags=["scanner"])
scanner_service = ScannerService()


@router.get("/mtf")
async def mtf_scan(
    symbol: str = Query("BTCUSDT"),
    intervals: str = Query("15m,1h,4h"),
) -> dict:
    try:
        parts = [item.strip() for item in intervals.split(",") if item.strip()]
        result = await scanner_service.scan_watchlist([symbol], parts)
        return {"items": result}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Unable to run scanner: {exc}") from exc


@router.get("/symbol")
async def scan_symbol(
    symbol: str = Query("BTCUSDT"),
    interval: str = Query("1h"),
) -> dict:
    try:
        result = await scanner_service.scan_symbol(symbol, interval=interval)
        return {
            "symbol": result.symbol,
            "interval": result.interval,
            "trend": result.trend,
            "strength": result.strength,
            "rsi": result.rsi,
            "ema_fast": result.ema_fast,
            "ema_slow": result.ema_slow,
            "macd": result.macd,
            "last_price": result.last_price,
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Unable to run scanner: {exc}") from exc
