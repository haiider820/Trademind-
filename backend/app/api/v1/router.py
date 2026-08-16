from fastapi import APIRouter

from app.api.v1.endpoints.ai import router as ai_router
from app.api.v1.endpoints.devices import router as devices_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.lessons import router as lessons_router
from app.api.v1.endpoints.market import router as market_router
from app.api.v1.endpoints.news import router as news_router
from app.api.v1.endpoints.notifications import router as notifications_router
from app.api.v1.endpoints.prediction import router as prediction_router
from app.api.v1.endpoints.liquidations import router as liquidations_router
from app.api.v1.endpoints.scanner import router as scanner_router
from app.api.v1.endpoints.signals import router as signals_router
from app.api.v1.endpoints.whales import router as whales_router
from app.api.v1.endpoints.watchlists import router as watchlists_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(market_router, prefix="/market", tags=["market"])
api_router.include_router(news_router, prefix="/news", tags=["news"])
api_router.include_router(signals_router, prefix="/signals", tags=["signals"])
api_router.include_router(ai_router, prefix="/ai", tags=["ai"])
api_router.include_router(scanner_router, prefix="/scanner", tags=["scanner"])
api_router.include_router(devices_router, prefix="/devices", tags=["devices"])
api_router.include_router(notifications_router, prefix="/notifications", tags=["notifications"])
api_router.include_router(prediction_router, prefix="/prediction", tags=["prediction"])
api_router.include_router(watchlists_router, prefix="/watchlists", tags=["watchlists"])
api_router.include_router(lessons_router, prefix="/lessons", tags=["lessons"])
api_router.include_router(whales_router, prefix="/whales", tags=["whales"])
api_router.include_router(liquidations_router, prefix="/liquidations", tags=["liquidations"])
