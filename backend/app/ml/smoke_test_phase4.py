"""Offline contract smoke test for Phase 4 serving integration."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import AuthUser
from app.api.v1.endpoints import prediction
from app.ml.dataset import FEATURE_COLUMNS
from app.ml.model_bundle import get_model_bundle


def main() -> None:
    app = FastAPI()
    app.include_router(prediction.router, prefix="/api/v1/prediction")
    app.dependency_overrides[prediction.get_current_user] = lambda: AuthUser("smoke-user", "smoke@example.com", "test")

    with TestClient(app) as client:
        health = client.get("/api/v1/prediction/health")
        assert health.status_code == 200
        assert health.json()["data"]["model"]["version_identifier"]

        bundle = get_model_bundle()
        feature_row = [0.0] * len(FEATURE_COLUMNS)
        sequence_window_bars = bundle.health()["sequence_window_bars"]
        feature_window = [feature_row[:] for _ in range(sequence_window_bars)]
        with patch.object(prediction, "_log_decision", new=AsyncMock()) as log_decision:
            response = client.post(
                "/api/v1/prediction/predict",
                json={
                    "symbol": "BTCUSDT",
                    "decision_time": datetime.now(timezone.utc).isoformat(),
                    "entry_price": 100.0,
                    "feature_window": feature_window,
                    "decision_id": "phase4-smoke-decision",
                },
            )
        assert response.status_code == 200, response.text
        payload = response.json()["data"]
        assert payload["model_version_identifier"] == bundle.version_identifier
        assert payload["audit_logged"] is True
        log_decision.assert_awaited_once()

    print("phase4_smoke=passed")


if __name__ == "__main__":
    main()
