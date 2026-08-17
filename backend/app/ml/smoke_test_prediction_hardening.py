"""Offline security smoke test for the hardened prediction route."""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import _configured_cors_origins, app
from app.ml.dataset import FEATURE_COLUMNS
from app.api.v1.endpoints import prediction
from app.services.signal_monitor_service import signal_monitor_service


class _FakeScore:
    action = "no_entry"
    entry_probability = 0.2
    decision_threshold = 0.5
    model_version_identifier = "smoke-model"
    component_probabilities = {"random_forest": 0.2, "gradient_boosting": 0.2, "gru": 0.2}
    feature_schema_hash = "smoke-schema"
    sequence_window_bars = 32


class _FakeBundle:
    version_identifier = "smoke-model"
    feature_schema_hash = "smoke-schema"
    weights = {"random_forest": 1 / 3, "gradient_boosting": 1 / 3, "gru": 1 / 3}
    manifest = {}

    def score(self, feature_window):
        return _FakeScore()


def _payload() -> dict:
    return {
        "symbol": "BTCUSDT",
        "decision_time": datetime.now(timezone.utc).isoformat(),
        "entry_price": 100.0,
        "feature_window": [[0.0] * len(FEATURE_COLUMNS) for _ in range(32)],
        "decision_id": "hardening-smoke-decision",
    }


def main() -> None:
    original_token = settings.prediction_service_token
    original_limit = settings.prediction_rate_limit_max_requests
    original_timeout = settings.prediction_timeout_seconds
    original_body_limit = settings.prediction_max_body_bytes
    settings.prediction_service_token = "smoke-service-token"
    settings.prediction_rate_limit_max_requests = 120
    settings.prediction_timeout_seconds = 8.0
    settings.prediction_max_body_bytes = 65536
    prediction._rate_limit_state.clear()

    try:
        with patch.object(prediction, "get_model_bundle", return_value=_FakeBundle()), patch.object(
            prediction, "_log_decision", new=AsyncMock()
        ), patch.object(signal_monitor_service, "start", new=AsyncMock()), patch.object(
            signal_monitor_service, "stop", new=AsyncMock()
        ):
            with TestClient(app) as client:
                missing = client.post("/api/v1/prediction/predict", json=_payload())
                assert missing.status_code == 401
                assert missing.json() == {"detail": "Invalid authentication"}

                wrong = client.post(
                    "/api/v1/prediction/predict",
                    headers={"Authorization": "Bearer wrong"},
                    json=_payload(),
                )
                assert wrong.status_code == 401
                assert wrong.json() == {"detail": "Invalid authentication"}

                invalid = _payload()
                invalid["feature_window"] = [[0.0] * len(FEATURE_COLUMNS)]
                response = client.post(
                    "/api/v1/prediction/predict",
                    headers={"Authorization": "Bearer smoke-service-token"},
                    json=invalid,
                )
                assert response.status_code == 422
                assert response.json() == {"detail": "Invalid prediction request"}

                success = client.post(
                    "/api/v1/prediction/predict",
                    headers={"Authorization": "Bearer smoke-service-token"},
                    json=_payload(),
                )
                assert success.status_code == 200, success.text
                assert success.json()["data"]["audit_logged"] is True

                prediction._rate_limit_state.clear()
                settings.prediction_rate_limit_max_requests = 1
                first = client.post(
                    "/api/v1/prediction/predict",
                    headers={"Authorization": "Bearer smoke-service-token"},
                    json=_payload(),
                )
                second = client.post(
                    "/api/v1/prediction/predict",
                    headers={"Authorization": "Bearer smoke-service-token"},
                    json=_payload(),
                )
                assert first.status_code == 200
                assert second.status_code == 429
                assert second.json() == {"detail": "Prediction rate limit exceeded"}
                assert second.headers.get("retry-after")

                settings.prediction_rate_limit_max_requests = 120
                settings.prediction_max_body_bytes = 64
                oversized = client.post(
                    "/api/v1/prediction/predict",
                    headers={"Authorization": "Bearer smoke-service-token"},
                    json=_payload(),
                )
                assert oversized.status_code == 422
                assert oversized.json() == {"detail": "Invalid prediction request"}

                settings.prediction_max_body_bytes = 65536
                production_cors = client.options(
                    "/api/v1/prediction/predict",
                    headers={
                        "Origin": "http://localhost:3000",
                        "Access-Control-Request-Method": "POST",
                    },
                )
                assert production_cors.status_code == 400, f"{production_cors.status_code}: {production_cors.text}"
                assert "access-control-allow-origin" not in production_cors.headers

                previous_env = settings.app_env
                settings.app_env = "development"
                assert "http://localhost:3000" in _configured_cors_origins()
                settings.app_env = previous_env

                cors_denied = client.options(
                    "/api/v1/prediction/predict",
                    headers={
                        "Origin": "https://unapproved.example",
                        "Access-Control-Request-Method": "POST",
                    },
                )
                assert cors_denied.status_code == 400, f"{cors_denied.status_code}: {cors_denied.text}"
                assert "access-control-allow-origin" not in cors_denied.headers

        async def slow_log(*args, **kwargs):
            await asyncio.sleep(0.05)

        settings.prediction_timeout_seconds = 0.01
        prediction._rate_limit_state.clear()
        with patch.object(prediction, "get_model_bundle", return_value=_FakeBundle()), patch.object(
            prediction, "_log_decision", new=slow_log
        ), patch.object(signal_monitor_service, "start", new=AsyncMock()), patch.object(
            signal_monitor_service, "stop", new=AsyncMock()
        ):
            with TestClient(app) as client:
                timed_out = client.post(
                    "/api/v1/prediction/predict",
                    headers={"Authorization": "Bearer smoke-service-token"},
                    json=_payload(),
                )
                assert timed_out.status_code == 503
                assert timed_out.json() == {"detail": "Prediction service temporarily unavailable"}

        print("prediction_hardening_smoke=passed")
    finally:
        settings.prediction_service_token = original_token
        settings.prediction_rate_limit_max_requests = original_limit
        settings.prediction_timeout_seconds = original_timeout
        settings.prediction_max_body_bytes = original_body_limit
        prediction._rate_limit_state.clear()


if __name__ == "__main__":
    main()
