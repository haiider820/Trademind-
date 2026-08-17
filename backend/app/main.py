from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.services.signal_monitor_service import signal_monitor_service

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
)

def _configured_cors_origins() -> list[str]:
    if settings.app_env.lower() not in {"development", "local", "test"}:
        return []
    return [origin.strip() for origin in settings.cors_local_origins.split(",") if origin.strip()]


local_cors_origins = _configured_cors_origins()

app.add_middleware(
    CORSMiddleware,
    allow_origins=local_cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


class _PredictionBodyTooLarge(Exception):
    pass


@app.exception_handler(RequestValidationError)
async def prediction_validation_exception_handler(request: Request, exc: RequestValidationError):
    if request.url.path == "/api/v1/prediction/predict":
        return JSONResponse(
            status_code=422,
            content={"detail": "Invalid prediction request"},
        )
    return await request_validation_exception_handler(request, exc)


@app.middleware("http")
async def limit_prediction_body(request: Request, call_next):
    """Reject oversized prediction JSON before Pydantic/model work begins."""
    prediction_path = "/api/v1/prediction/predict"
    if request.url.path != prediction_path:
        return await call_next(request)

    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > settings.prediction_max_body_bytes:
                return JSONResponse(
                    status_code=422,
                    content={"detail": "Invalid prediction request"},
                )
        except ValueError:
            return JSONResponse(
                status_code=422,
                content={"detail": "Invalid prediction request"},
            )

    receive = request._receive
    received_bytes = 0

    async def limited_receive():
        nonlocal received_bytes
        message = await receive()
        received_bytes += len(message.get("body", b""))
        if received_bytes > settings.prediction_max_body_bytes:
            raise _PredictionBodyTooLarge
        return message

    request._receive = limited_receive
    try:
        return await call_next(request)
    except _PredictionBodyTooLarge:
        return JSONResponse(
            status_code=422,
            content={"detail": "Invalid prediction request"},
        )

app.include_router(api_router, prefix="/api/v1")


@app.on_event("startup")
async def _startup() -> None:
    await signal_monitor_service.start()


@app.on_event("shutdown")
async def _shutdown() -> None:
    await signal_monitor_service.stop()
