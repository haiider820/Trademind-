from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check() -> dict:
    return {
        "success": True,
        "data": {
            "status": "ok",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }
