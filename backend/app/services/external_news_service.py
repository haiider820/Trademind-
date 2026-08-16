from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timezone
from typing import Any

import feedparser
import httpx

from app.core.config import settings

RSS_SOURCES = [
    {"name": "CoinDesk", "url": "https://www.coindesk.com/arc/outboundfeeds/rss/", "category": "crypto"},
    {"name": "Cointelegraph", "url": "https://cointelegraph.com/rss", "category": "crypto"},
    {"name": "Decrypt", "url": "https://decrypt.co/feed", "category": "crypto"},
    {"name": "Binance", "url": "https://www.binance.com/en/support/announcement/rss", "category": "crypto"},
    {"name": "Reuters Markets", "url": "https://www.reutersagency.com/feed/?best-topics=business-finance", "category": "macro"},
]

NEWSAPI_QUERIES = ["crypto", "bitcoin", "ethereum", "altcoin", "blockchain", "binance", "solana"]

BULLISH_WORDS = {
    "surge",
    "rally",
    "breakout",
    "approval",
    "adoption",
    "buy",
    "bullish",
    "record high",
    "all-time high",
    "inflow",
}
BEARISH_WORDS = {
    "crash",
    "selloff",
    "hack",
    "lawsuit",
    "ban",
    "rejection",
    "liquidation",
    "outflow",
    "bearish",
    "drop",
}
FOREX_WORDS = {"eur/usd", "usd/jpy", "gbp/usd", "xau/usd", "dxy", "fed", "ecb", "boe"}


class ExternalNewsService:
    async def get_news(self, limit: int = 20) -> list[dict]:
        rows = await self._fetch_combined_news(max(limit * 4, 40))
        if not rows:
            return [self._fallback_item()]

        # Use Gemini sentiment only for top headlines to control latency/cost.
        if settings.gemini_api_key and settings.news_use_gemini_sentiment:
            rows = await self._apply_gemini_sentiment(rows, max_items=min(limit, 8))

        rows.sort(key=lambda x: x["published_at"], reverse=True)
        return rows[:limit]

    async def _fetch_rss_news(self, fetch_limit: int) -> list[dict]:
        items: list[dict] = []
        seen: set[str] = set()
        async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
            results = await asyncio.gather(
                *(self._fetch_source(client, source) for source in RSS_SOURCES),
                return_exceptions=True,
            )
            for result in results:
                if isinstance(result, Exception):
                    continue
                for row in result:
                    if row["id"] in seen:
                        continue
                    seen.add(row["id"])
                    items.append(row)
                    if len(items) >= fetch_limit:
                        return items
        return items

    async def _fetch_combined_news(self, fetch_limit: int) -> list[dict]:
        sources: list[list[dict]] = [await self._fetch_rss_news(fetch_limit)]
        if settings.newsapi_api_key:
            sources.append(await self._fetch_newsapi(fetch_limit))
        if settings.finnhub_api_key:
            sources.append(await self._fetch_finnhub(fetch_limit))

        items: list[dict] = []
        seen: set[str] = set()
        for source_rows in sources:
            for row in source_rows:
                if row["id"] in seen:
                    continue
                seen.add(row["id"])
                items.append(row)
                if len(items) >= fetch_limit:
                    return items
        return items

    async def _fetch_newsapi(self, fetch_limit: int) -> list[dict]:
        if not settings.newsapi_api_key:
            return []
        query = " OR ".join(NEWSAPI_QUERIES)
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": query,
            "sortBy": "publishedAt",
            "pageSize": min(fetch_limit, 100),
            "language": "en",
            "apiKey": settings.newsapi_api_key,
        }
        try:
            async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data: dict[str, Any] = response.json()
                rows: list[dict] = []
                for article in data.get("articles", [])[:fetch_limit]:
                    title = (article.get("title") or "").strip()
                    if not title:
                        continue
                    source_name = (article.get("source") or {}).get("name") or "NewsAPI"
                    link = article.get("url", "")
                    rows.append(
                        {
                            "id": self._build_item_id("NewsAPI", title, link),
                            "title": title,
                            "sentiment": self._heuristic_sentiment(title),
                            "category": self._infer_category(title, "crypto"),
                            "source": source_name,
                            "published_at": self._parse_api_published_at(article.get("publishedAt")),
                        }
                    )
                return rows
        except Exception:
            return []

    async def _fetch_finnhub(self, fetch_limit: int) -> list[dict]:
        if not settings.finnhub_api_key:
            return []
        url = "https://finnhub.io/api/v1/news"
        params = {"category": "crypto", "token": settings.finnhub_api_key}
        try:
            async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                rows: list[dict] = []
                for article in data[:fetch_limit]:
                    title = (article.get("headline") or "").strip()
                    if not title:
                        continue
                    source_name = article.get("source") or "Finnhub"
                    link = article.get("url", "")
                    rows.append(
                        {
                            "id": self._build_item_id("Finnhub", title, link),
                            "title": title,
                            "sentiment": self._heuristic_sentiment(title),
                            "category": self._infer_category(title, "crypto"),
                            "source": source_name,
                            "published_at": self._parse_epoch_published_at(article.get("datetime")),
                        }
                    )
                return rows
        except Exception:
            return []

    async def _fetch_source(self, client: httpx.AsyncClient, source: dict[str, str]) -> list[dict]:
        try:
            response = await client.get(source["url"])
            response.raise_for_status()
            parsed = feedparser.parse(response.text)
            rows: list[dict] = []
            for entry in parsed.entries:
                title = (entry.get("title") or "").strip()
                if not title:
                    continue
                link = entry.get("link", "")
                item_id = self._build_item_id(source["name"], title, link)
                rows.append(
                    {
                        "id": item_id,
                        "title": title,
                        "sentiment": self._heuristic_sentiment(title),
                        "category": self._infer_category(title, source["category"]),
                        "source": source["name"],
                        "published_at": self._parse_published_at(entry),
                    }
                )
            return rows
        except Exception:
            return []

    async def _apply_gemini_sentiment(self, rows: list[dict], max_items: int) -> list[dict]:
        updated = []
        async with httpx.AsyncClient(timeout=15) as client:
            for index, row in enumerate(rows):
                if index >= max_items:
                    updated.append(row)
                    continue
                sentiment = await self._gemini_sentiment(client, row["title"])
                updated.append({**row, "sentiment": sentiment})
        return updated

    async def _gemini_sentiment(self, client: httpx.AsyncClient, title: str) -> str:
        prompt = (
            "Classify this trading headline sentiment as one label only: "
            "bullish, bearish, or neutral.\n"
            f"Headline: {title}\n"
            "Answer with one word only."
        )
        endpoint = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
        try:
            response = await client.post(
                endpoint,
                headers={"x-goog-api-key": settings.gemini_api_key},
                json={"contents": [{"parts": [{"text": prompt}]}]},
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            text = (
                data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "neutral")
                .strip()
                .lower()
            )
            if "bullish" in text:
                return "bullish"
            if "bearish" in text:
                return "bearish"
            return "neutral"
        except Exception:
            return self._heuristic_sentiment(title)

    def _build_item_id(self, source_name: str, title: str, link: str) -> str:
        base = f"{source_name}|{link}|{title}".encode("utf-8")
        return hashlib.sha1(base).hexdigest()[:20]

    def _parse_published_at(self, entry: dict) -> str:
        if entry.get("published_parsed"):
            dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            return dt.isoformat()
        if entry.get("updated_parsed"):
            dt = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
            return dt.isoformat()
        published = entry.get("published") or entry.get("updated")
        if isinstance(published, str):
            try:
                return datetime.fromisoformat(published).astimezone(timezone.utc).isoformat()
            except Exception:
                pass
        return datetime.now(timezone.utc).isoformat()

    def _parse_api_published_at(self, value: Any) -> str:
        if isinstance(value, str) and value:
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()
            except Exception:
                pass
        return datetime.now(timezone.utc).isoformat()

    def _parse_epoch_published_at(self, value: Any) -> str:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()
        return datetime.now(timezone.utc).isoformat()

    def _infer_category(self, title: str, default: str) -> str:
        text = title.lower()
        if any(term in text for term in FOREX_WORDS):
            return "forex"
        if "etf" in text or "sec" in text or "regulation" in text:
            return "macro"
        return default

    def _heuristic_sentiment(self, title: str) -> str:
        text = title.lower()
        if any(term in text for term in BULLISH_WORDS):
            return "bullish"
        if any(term in text for term in BEARISH_WORDS):
            return "bearish"
        return "neutral"

    def _fallback_item(self) -> dict:
        return {
            "id": "fallback_1",
            "title": "Market headlines unavailable. Retrying feeds shortly.",
            "sentiment": "neutral",
            "category": "crypto",
            "source": "TradeMind",
            "published_at": datetime.now(timezone.utc).isoformat(),
        }
