from fastapi import APIRouter, Depends, Query

from app.schemas.news import NewsItem
from app.services.external_news_service import ExternalNewsService
from app.services.supabase_service import SupabaseService

router = APIRouter()
news_service = ExternalNewsService()


@router.get("")
async def list_news(
    limit: int = Query(default=20, ge=1, le=100),
    sentiment: str | None = Query(default=None),
    category: str | None = Query(default=None),
) -> dict:
    rss_rows = await news_service.get_news(limit=limit)
    db_service = SupabaseService()

    for row in rss_rows:
        try:
            await db_service.upsert(
                "news",
                payload={
                    "external_id": row["id"],
                    "title": row["title"],
                    "content": row["title"],
                    "sentiment": row["sentiment"],
                    "category": row["category"],
                    "source": row["source"],
                    "published_at": row["published_at"],
                },
                on_conflict="external_id",
                use_service_key=True,
            )
        except Exception:
            continue

    try:
        query = "select=external_id,title,sentiment,category,source,published_at&order=published_at.desc"
        query += f"&limit={limit}"
        if sentiment:
            query += f"&sentiment=eq.{sentiment}"
        if category:
            query += f"&category=eq.{category}"
        stored_rows = await db_service.select("news", query=query, use_service_key=True)
        items = [
            NewsItem(
                id=row.get("external_id") or "",
                title=row["title"],
                sentiment=row["sentiment"],
                category=row["category"],
                source=row.get("source") or "Unknown",
                published_at=row["published_at"],
            ).model_dump()
            for row in stored_rows
        ]
        if not items:
            items = [NewsItem(**item).model_dump() for item in rss_rows]
    except Exception:
        items = [NewsItem(**item).model_dump() for item in rss_rows]
    if sentiment:
        items = [item for item in items if item["sentiment"] == sentiment]
    if category:
        items = [item for item in items if item["category"] == category]
    return {
        "success": True,
        "data": {
            "items": items,
            "filters": {"sentiment": sentiment, "category": category},
        },
    }
