from __future__ import annotations

import asyncio
import json
import time
from typing import Any
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.services.binance_service import BinanceService
from app.services.scanner_service import ScannerService
from app.services.market_data_service import MarketDataService
from app.services.gemini_service import GeminiService

router = APIRouter(tags=["ai"])
gemini_service = GeminiService()
binance_service = BinanceService()
market_data_service = MarketDataService()
scanner_service = ScannerService()
_RATE_LIMIT_WINDOW_SECONDS = 60
_RATE_LIMIT_MAX_REQUESTS = 12
_rate_limit_state: dict[str, tuple[float, int]] = {}
_context_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_CONTEXT_CACHE_TTL_SECONDS = 45


class AIChatRequest(BaseModel):
    message: str | None = Field(default=None)
    prompt: str | None = Field(default=None)
    question: str | None = Field(default=None)
    text: str | None = Field(default=None)
    market: str = "crypto"
    symbol: str | None = None
    timeframe: str | None = None
    history: list[dict[str, Any]] = Field(default_factory=list)
    context: str | None = None

    def get_text(self) -> str:
        return (self.message or self.prompt or self.question or self.text or "").strip()


def _fallback_reply(user_text: str) -> str:
    lowered = user_text.lower()
    if any(word in lowered for word in ["btc", "bitcoin", "eth", "crypto", "bull", "bear"]):
        return (
            "I could not reach Gemini just now, but here is a safe trading read: "
            "wait for confirmation, keep risk small, and avoid entering on emotional spikes. "
            "Check trend, volume, and your invalidation level before acting."
        )
    if any(word in lowered for word in ["eur", "usd", "forex", "gbp", "jpy", "gold"]):
        return (
            "I could not reach Gemini just now, but for forex keep position size small, "
            "respect session volatility, and only trade when structure and momentum agree."
        )
    return (
        "I could not reach Gemini just now. Please try again in a moment, or use the "
        "dashboard and scanner while the model service recovers."
    )


def _looks_like_price_query(text: str) -> bool:
    lowered = text.lower()
    return any(
        phrase in lowered
        for phrase in [
            "current btc price",
            "btc price",
            "bitcoin price",
            "current bitcoin price",
            "what is btc price",
            "what is bitcoin price",
            "btc usdt price",
        ]
    )


def _extract_crypto_symbol(text: str) -> str | None:
    normalized = text.upper()
    matches = re.findall(r"\b[A-Z0-9]{2,12}\b", normalized)
    crypto_candidates = {
        "BTC",
        "BITCOIN",
        "ETH",
        "ETHER",
        "BNB",
        "SOL",
        "XRP",
        "ADA",
        "DOGE",
        "AVAX",
        "LINK",
        "SUI",
        "LTC",
        "TRX",
        "TON",
        "DOT",
        "MATIC",
        "PEPE",
        "SHIB",
        "UNI",
        "XLM",
        "ATOM",
        "AAVE",
        "NEAR",
        "ARB",
        "OP",
        "FIL",
        "TIA",
        "INJ",
        "APT",
    }
    for candidate in matches:
        if candidate in crypto_candidates:
            return f"{'BTC' if candidate in {'BTC', 'BITCOIN'} else candidate}USDT"
    return None


async def _enforce_ai_rate_limit(user_id: str) -> None:
    now = time.monotonic()
    window_start, count = _rate_limit_state.get(user_id, (now, 0))
    if now - window_start >= _RATE_LIMIT_WINDOW_SECONDS:
        window_start, count = now, 0
    if count >= _RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(status_code=429, detail="AI rate limit exceeded. Please try again later.")
    _rate_limit_state[user_id] = (window_start, count + 1)


async def _ensure_chat_session(user_id: str) -> str:
    service = SupabaseService()
    rows = await service.select(
        "chat_sessions",
        query=f"user_id=eq.{user_id}&select=id&order=updated_at.desc&limit=1",
        use_service_key=True,
    )
    if rows:
        return str(rows[0]["id"])
    row = await service.insert(
        "chat_sessions",
        payload={"user_id": user_id, "title": "TradeMind Chat"},
        use_service_key=True,
    )
    return str(row["id"])


async def _log_chat_message(user_id: str, session_id: str, role: str, content: str) -> None:
    service = SupabaseService()
    await service.insert(
        "chat_messages",
        payload={
            "session_id": session_id,
            "user_id": user_id,
            "role": role,
            "content": content,
        },
        use_service_key=True,
    )


async def _build_live_context(request: AIChatRequest) -> str:
    symbol = (request.symbol or "BTCUSDT").upper()
    market = (request.market or "crypto").lower()
    question = request.get_text().lower()
    educational_only = any(
        phrase in question
        for phrase in [
            "what is ",
            "explain ",
            "define ",
            "how does ",
            "difference between",
            "what does ",
        ]
    )

    if educational_only and not request.symbol:
        return ""

    parts: list[str] = []
    cache_key = f"{market}:{symbol}"
    cached = _context_cache.get(cache_key)
    now = time.monotonic()
    if cached and now - cached[0] <= _CONTEXT_CACHE_TTL_SECONDS:
        return json.dumps(cached[1], separators=(",", ":"))

    try:
        if market == "crypto":
            ticker, scan = await asyncio.gather(
                binance_service.get_ticker_24h(symbol),
                scanner_service.scan_symbol(symbol, interval=request.timeframe or "1h"),
            )
            payload = {
                "symbol": symbol,
                "market": market,
                "price": ticker["last_price"],
                "24h_change_percent": ticker["price_change_percent"],
                "high_24h": ticker["high_price"],
                "low_24h": ticker["low_price"],
                "volume_24h": ticker["volume"],
                "fear_greed": None,
                "trend": scan.trend,
                "strength": scan.strength,
                "rsi": scan.rsi,
                "ema_fast": scan.ema_fast,
                "ema_slow": scan.ema_slow,
                "macd": scan.macd,
                "last_price": scan.last_price,
            }
            _context_cache[cache_key] = (now, payload)
            return json.dumps(payload, separators=(",", ":"))
        else:
            return json.dumps({"symbol": symbol, "market": market, "question_type": "forex"}, separators=(",", ":"))
    except Exception as exc:
        parts.append(f"Live price lookup failed for {symbol}: {exc}")

    try:
        overview = await market_data_service.get_enhanced_market_overview()
        parts.append(
            "Market backdrop: "
            f"Fear & Greed={overview['fear_greed_index']} ({overview['fear_greed_classification']}), "
            f"BTC dominance={overview['btc_dominance']}%, "
            f"market cap={overview['market_cap']}."
        )
    except Exception as exc:
        parts.append(f"Market backdrop unavailable: {exc}")

    return "\n".join(parts)


@router.post("/chat")
async def chat(request: AIChatRequest, current_user: dict = Depends(get_current_user)) -> dict:
    await _enforce_ai_rate_limit(current_user.id)
    user_text = request.get_text()
    if not user_text:
        raise HTTPException(status_code=400, detail="Message is required")

    session_id = await _ensure_chat_session(current_user.id)
    await _log_chat_message(current_user.id, session_id, "user", user_text)

    live_context = await _build_live_context(request)
    detected_symbol = _extract_crypto_symbol(user_text)

    if _looks_like_price_query(user_text) or detected_symbol:
        try:
            symbol = detected_symbol or (request.symbol or "BTCUSDT").upper()
            price = await binance_service.get_price(symbol)
            reply_text = f"{symbol} is currently trading at ${price:,.2f} USD."
            await _log_chat_message(current_user.id, session_id, "assistant", reply_text)
            return {
                "reply": reply_text,
                "mode": "market_data",
                "model": "binance",
                "symbol": symbol,
                "price": price,
                "session_id": session_id,
            }
        except Exception as exc:
            return {
                "reply": _fallback_reply(user_text),
                "mode": "fallback",
                "model": "fallback",
                "error": str(exc),
                "session_id": session_id,
            }

    try:
        reply = await gemini_service.chat(
            user_text,
            history=request.history,
            context="\n".join(
                part for part in [request.context, live_context] if part and part.strip()
            ),
        )
        await _log_chat_message(current_user.id, session_id, "assistant", reply)
        return {
            "reply": reply,
            "mode": "gemini",
            "model": "gemini",
            "session_id": session_id,
        }
    except Exception as exc:
        return {
            "reply": _fallback_reply(user_text),
            "mode": "fallback",
            "model": "fallback",
            "error": str(exc),
            "session_id": session_id,
        }


@router.post("/analyze")
async def analyze(request: AIChatRequest, current_user: dict = Depends(get_current_user)) -> dict:
    await _enforce_ai_rate_limit(current_user.id)
    user_text = request.get_text()
    if not user_text:
        raise HTTPException(status_code=400, detail="Prompt is required")

    session_id = await _ensure_chat_session(current_user.id)
    await _log_chat_message(current_user.id, session_id, "user", user_text)

    try:
        detected_symbol = _extract_crypto_symbol(user_text)
        reply = await gemini_service.analyze_market(
            user_text,
            history=request.history,
            context="\n".join(
                part
                for part in [
                    request.context,
                    await _build_live_context(
                        AIChatRequest(
                            message=request.message,
                            prompt=request.prompt,
                            question=request.question,
                            text=request.text,
                            history=request.history,
                            context=(request.context or "")
                            + (f"\nDetected symbol: {detected_symbol}" if detected_symbol else ""),
                        )
                    ),
                ]
                if part and part.strip()
            ),
        )
        await _log_chat_message(current_user.id, session_id, "assistant", reply)
        return {
            "reply": reply,
            "mode": "gemini",
            "model": "gemini",
            "session_id": session_id,
        }
    except Exception as exc:
        return {
            "reply": _fallback_reply(user_text),
            "mode": "fallback",
            "model": "fallback",
            "error": str(exc),
            "session_id": session_id,
        }
