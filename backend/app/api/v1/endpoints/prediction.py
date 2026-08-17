from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.routing import APIRoute
from pydantic import BaseModel, Field, FiniteFloat, field_validator

from app.api.deps import AuthUser, get_prediction_service_caller
from app.core.config import settings
from app.ml.dataset import FEATURE_COLUMNS
from app.ml.model_bundle import get_model_bundle
from app.services.supabase_service import SupabaseService

logger = logging.getLogger("trademind.prediction")


class PredictionTimeoutRoute(APIRoute):
    """Bound the complete prediction request, including dependency resolution and audit writes."""

    def get_route_handler(self):
        original_route_handler = super().get_route_handler()

        async def timed_route_handler(request: Request):
            try:
                async with asyncio.timeout(settings.prediction_timeout_seconds):
                    return await original_route_handler(request)
            except TimeoutError as exc:
                logger.warning("prediction_request_timeout")
                raise HTTPException(
                    status_code=503,
                    detail="Prediction service temporarily unavailable",
                ) from exc

        return timed_route_handler


router = APIRouter(route_class=PredictionTimeoutRoute)
_rate_limit_state: dict[str, tuple[float, int]] = {}


class PredictionRequest(BaseModel):
    """Causal rolling feature window ending at the completed decision candle."""

    symbol: str = Field(min_length=5, max_length=20, pattern=r"^[A-Z0-9]+$")
    decision_time: datetime
    entry_price: float = Field(gt=0)
    feature_window: list[list[FiniteFloat]] = Field(min_length=1)
    decision_id: str | None = Field(default=None, min_length=8, max_length=120)

    @field_validator("feature_window")
    @classmethod
    def validate_feature_window(cls, value: list[list[FiniteFloat]]) -> list[list[FiniteFloat]]:
        if len(value) != settings.ml_sequence_window_bars or any(
            len(row) != len(FEATURE_COLUMNS) for row in value
        ):
            raise ValueError("Invalid prediction request")
        return value


class PredictionResponse(BaseModel):
    decision_id: str
    symbol: str
    decision_time: datetime
    action: str
    entry_probability: float
    decision_threshold: float
    model_version_identifier: str
    component_probabilities: dict[str, float]
    sequence_window_bars: int
    feature_schema_hash: str
    audit_logged: bool


def _model_version_payload(bundle: Any) -> dict[str, Any]:
    return {
        "version_identifier": bundle.version_identifier,
        "model_family": "ensemble",
        "artifact_location": "repo:backend/models/current/model_bundle.json",
        "feature_schema_hash": bundle.feature_schema_hash,
        "target_contract": bundle.manifest.get("target_contract", {}),
        "training_window": {"source": "Phase 2 validated bootstrap artifacts"},
        "validation_window": {"source": "Phase 2 final chronological holdout"},
        "metrics": {
            "source": "backend/reports/phase2_sequence_ensemble_metrics.json",
            "ensemble_weights": bundle.weights,
        },
        "lifecycle_status": "incumbent",
    }


def _enforce_rate_limit(caller_id: str) -> None:
    """Apply a bounded process-local limit; shared infrastructure is needed for multi-worker limits."""
    now = time.monotonic()
    window_seconds = settings.prediction_rate_limit_window_seconds
    max_requests = settings.prediction_rate_limit_max_requests

    # This route has one configured service identity, but prune expired keys so a future
    # caller-identity extension cannot grow this dictionary without bound.
    expired = [
        key
        for key, (window_start, _) in _rate_limit_state.items()
        if now - window_start >= window_seconds
    ]
    for key in expired:
        _rate_limit_state.pop(key, None)

    window_start, count = _rate_limit_state.get(caller_id, (now, 0))
    if now - window_start >= window_seconds:
        window_start, count = now, 0
    if count >= max_requests:
        retry_after = max(1, int(window_seconds - (now - window_start)))
        raise HTTPException(
            status_code=429,
            detail="Prediction rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )
    _rate_limit_state[caller_id] = (window_start, count + 1)


async def _log_decision(
    request: PredictionRequest,
    bundle: Any,
    score: Any,
    decision_id: str,
) -> None:
    """Persist one decision only after successful scoring; service-role access is server-only."""
    service = SupabaseService()
    await service.upsert(
        "ml_model_versions",
        _model_version_payload(bundle),
        on_conflict="version_identifier",
        use_service_key=True,
    )
    last_row = request.feature_window[-1]
    feature_snapshot = {
        name: float(value) for name, value in zip(FEATURE_COLUMNS, last_row, strict=True)
    }
    await service.upsert(
        "ml_decision_logs",
        {
            "decision_id": decision_id,
            "decision_time": request.decision_time.astimezone(timezone.utc).isoformat(),
            "symbol": request.symbol,
            "candle_interval": settings.trading_candle_interval,
            "market_mode": settings.trading_market_mode,
            "action": score.action,
            "model_version_identifier": score.model_version_identifier,
            "decision_threshold": score.decision_threshold,
            "model_probabilities": {
                "ensemble": score.entry_probability,
                **score.component_probabilities,
            },
            "input_features": feature_snapshot,
            "feature_schema_hash": score.feature_schema_hash,
            "input_window_summary": {
                "rows": len(request.feature_window),
                "features_per_row": len(last_row),
                "entry_price": request.entry_price,
                # The full causal window is retained for later GRU retraining; it contains no future values.
                "values": request.feature_window,
            },
            "outcome_status": "pending",
            "target_horizon_bars": settings.ml_serving_horizon_bars,
        },
        on_conflict="decision_id",
        use_service_key=True,
    )


@router.get("/health")
async def prediction_health() -> dict[str, Any]:
    """Unauthenticated liveness/readiness check for the in-process model bundle."""
    try:
        bundle = get_model_bundle()
        data = {
            "status": "ok",
            "model": bundle.health(),
            "audit_store_configured": bool(
                settings.supabase_url and settings.supabase_service_role_key
            ),
        }
        return {"success": True, "data": data}
    except Exception as exc:  # pragma: no cover - exact exception depends on artifact deployment
        logger.exception("prediction_health_failed", extra={"error_type": type(exc).__name__})
        return {
            "success": False,
            "data": {"status": "degraded", "model_ready": False},
        }


@router.post("/predict", response_model=dict[str, Any])
async def predict(
    request: PredictionRequest,
    caller: AuthUser = Depends(get_prediction_service_caller),
) -> dict[str, Any]:
    """Score the Phase 2 ensemble and append the decision to the Supabase audit store."""
    _enforce_rate_limit(caller.id)
    decision_id = request.decision_id or str(uuid4())
    logger.info(
        "prediction_request_received",
        extra={"decision_id": decision_id, "symbol": request.symbol, "caller_id": caller.id},
    )
    try:
        bundle = get_model_bundle()
        score = bundle.score(request.feature_window)
        await _log_decision(request, bundle, score, decision_id)
    except ValueError as exc:
        logger.warning(
            "prediction_request_rejected",
            extra={"decision_id": decision_id, "symbol": request.symbol, "error_type": type(exc).__name__},
        )
        raise HTTPException(status_code=422, detail="Invalid prediction request") from exc
    except (FileNotFoundError, RuntimeError, httpx.HTTPError) as exc:
        logger.exception(
            "prediction_service_unavailable",
            extra={"decision_id": decision_id, "symbol": request.symbol, "error_type": type(exc).__name__},
        )
        raise HTTPException(status_code=503, detail="Prediction service temporarily unavailable") from exc
    except Exception as exc:  # pragma: no cover - defensive public error boundary
        logger.exception(
            "prediction_service_failed",
            extra={"decision_id": decision_id, "symbol": request.symbol, "error_type": type(exc).__name__},
        )
        raise HTTPException(status_code=503, detail="Prediction service temporarily unavailable") from exc

    logger.info(
        "prediction_request_completed",
        extra={
            "decision_id": decision_id,
            "symbol": request.symbol,
            "action": score.action,
            "model_version_identifier": score.model_version_identifier,
        },
    )
    response = PredictionResponse(
        decision_id=decision_id,
        symbol=request.symbol,
        decision_time=request.decision_time,
        action=score.action,
        entry_probability=score.entry_probability,
        decision_threshold=score.decision_threshold,
        model_version_identifier=score.model_version_identifier,
        component_probabilities=score.component_probabilities,
        sequence_window_bars=score.sequence_window_bars,
        feature_schema_hash=score.feature_schema_hash,
        audit_logged=True,
    )
    return {"success": True, "data": response.model_dump(mode="json")}
