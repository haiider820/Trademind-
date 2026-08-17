# Phase 4 Internal Prediction API

## Boundary

The prediction service is integrated into TradeMind's existing FastAPI process. It is **not** a separate public service, does not fetch candles, does not calculate indicators, does not retrain models in request handling, and never places orders. The existing signal-monitor process remains responsible for building causal feature windows from completed candles.

The endpoint is intended for the existing internal scanner, which evaluates approximately every 15 minutes across the seven configured pairs. Because the route is in-process, no Render keep-alive ping is needed and there is no separate prediction-service cold start. If the backend process restarts, its lazy model loader reads the committed current bundle on the first prediction request.

## Endpoints

| Method | Path | Authentication | Purpose |
| --- | --- | --- | --- |
| `GET` | `/api/v1/prediction/health` | None | Model readiness, current version, feature-schema hash, sequence length, and audit-store configuration status |
| `POST` | `/api/v1/prediction/predict` | Dedicated internal service bearer token | Score one causal rolling window, return the ensemble decision and version, and persist the decision audit record |

## Health response

`GET /api/v1/prediction/health` returns a response shaped like:

```json
{
  "success": true,
  "data": {
    "status": "ok",
    "model": {
      "ready": true,
      "version_identifier": "phase2-bootstrap-ensemble-20260814",
      "feature_schema_hash": "sha256:derived-from-feature-order",
      "sequence_window_bars": 32
    },
    "audit_store_configured": true
  }
}
```

A degraded response has `success: false`, `data.status: "degraded"`, and `data.model_ready: false`. This endpoint checks the local artifact bundle but does not perform a database write.

## Prediction request

`POST /api/v1/prediction/predict` requires `Authorization: Bearer <prediction-service-token>` and accepts:

The token is a dedicated server-to-server credential configured as `PREDICTION_SERVICE_TOKEN`. It is not a Supabase user access token, the Supabase anonymous key, or the Supabase service-role key. The backend compares it in constant time and never logs or returns it. The current repository has no scanner caller wired to this route, so the token must remain provisioned only for the future internal caller and the FastAPI runtime.

```json
{
  "symbol": "BTCUSDT",
  "decision_time": "2026-08-16T03:15:00Z",
  "entry_price": 118500.25,
  "feature_window": [[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "... 31 more rows ..."],
  "decision_id": "optional-idempotency-key"
}
```

The production request must contain exactly **32 rows × 24 columns**, where each row is ordered according to the Phase 1 `FEATURE_COLUMNS` contract:

```
return_1, return_4, return_16, rsi_14, atr_pct_14, volatility_16,
volatility_64, ema_fast_slow_pct, ema_cross_up, ema_cross_down, macd_pct,
macd_signal_pct, macd_hist_pct, bollinger_zscore_20, bollinger_width_20,
candle_body_pct, upper_wick_pct, lower_wick_pct, range_pct,
relative_volume_20, quote_volume_zscore_20, taker_buy_imbalance,
vwap_distance_20, volume_concentration_20
```

The last row is the completed decision candle. Every earlier row must be a contiguous completed candle for the same symbol and interval. The request must not contain future values, labels, realized returns, or any TP/SL fields. `decision_time` and `entry_price` are audit/outcome metadata, not model features.

## Prediction response

A successful response returns:

```json
{
  "success": true,
  "data": {
    "decision_id": "uuid-or-client-id",
    "symbol": "BTCUSDT",
    "decision_time": "2026-08-16T03:15:00Z",
    "action": "enter",
    "entry_probability": 0.57,
    "decision_threshold": 0.5,
    "model_version_identifier": "phase2-bootstrap-ensemble-20260814",
    "component_probabilities": {
      "random_forest": 0.61,
      "gradient_boosting": 0.55,
      "gru": 0.55
    },
    "sequence_window_bars": 32,
    "feature_schema_hash": "sha256:derived-from-feature-order",
    "audit_logged": true
  }
}
```

The route returns `422` with the stable public detail `Invalid prediction request` for invalid JSON shape, non-finite values, oversized bodies, or incompatible request contracts; `401` with `Invalid authentication` for missing or invalid service authentication; `429` with `Prediction rate limit exceeded` and a `Retry-After` header when the process-local limit is exceeded; and `503` with `Prediction service temporarily unavailable` when the service token is unconfigured, model/audit work fails, or the hard timeout expires. These responses do not include exception text, stack traces, file paths, feature values, or model architecture details. The successful response fields are unchanged. The caller remains responsible for any separate trading-policy, risk, balance, and execution checks.

The route enforces exactly **32 rows × 24 columns**, finite numeric values, a **64 KiB** maximum request body, and an **8-second** end-to-end timeout. The default rate limit is **120 requests per 60 seconds per configured service identity**. It is process-local; a multi-worker or multi-instance deployment would require a shared limiter such as Redis for a global limit.

## Audit records

After successful scoring, the backend writes `ml_model_versions` and an idempotent `ml_decision_logs` row to Supabase using the server-only service-role key. The decision log contains the last-row feature snapshot plus the complete 32-row causal window so the scheduled retraining job can later train the GRU on resolved outcomes. Request logs record the decision ID, symbol, fixed internal caller label, action, and model version; they do not log the feature window, bearer token, service token, or service-role credentials.

## CORS and runtime settings

CORS has no allowed production origins. Explicit local-development origins are enabled only when `APP_ENV` is `development`, `local`, or `test`, using `CORS_LOCAL_ORIGINS`; the production configuration must set `APP_ENV=production`. Allowed methods and headers are limited to `GET`, `POST`, `OPTIONS`, `Authorization`, and `Content-Type`.

The hardening settings are environment-driven: `PREDICTION_SERVICE_TOKEN`, `PREDICTION_RATE_LIMIT_WINDOW_SECONDS`, `PREDICTION_RATE_LIMIT_MAX_REQUESTS`, `PREDICTION_MAX_BODY_BYTES`, `PREDICTION_TIMEOUT_SECONDS`, and `CORS_LOCAL_ORIGINS`. The service token is intentionally blank in source control and must be provisioned in the runtime secret store.

## Daily retraining workflow

The repository workflow is `.github/workflows/daily-retrain.yml`. It runs at **03:17 UTC daily** or manually through `workflow_dispatch`. It requires the following GitHub Actions repository secrets:

```
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
```

The workflow resolves mature pending outcomes from public Binance spot klines, trains tree and GRU candidates from the original data plus older resolved logs, evaluates on a newer chronological resolved-log window, and persists the comparison to Supabase. It copies candidates to `backend/models/current` and commits them only after the Phase 3 anti-regression gate passes. A rejected candidate leaves the incumbent bundle unchanged and is treated as a successful, auditable workflow outcome rather than an infrastructure failure.

The GitHub token used by the automation must have `contents: write`. GitHub Actions secret write access is intentionally not encoded in the repository; add the two secrets under **Repository Settings → Secrets and variables → Actions**. The service-role key must never be committed, placed in `.env.example`, or returned by the health endpoint.

The API process loads the bundle once per process. After a promoted artifact commit, restart or recycle the FastAPI process before expecting it to load the new bundle; this avoids replacing an in-memory model during active request handling.

## Render guidance

No separate Render prediction web service or keep-alive is used. This matches the actual call pattern: the existing internal monitor calls the in-process route about every 15 minutes, so a second service would add cold starts and model-file synchronization without reducing latency. Render's free web-service spin-down behavior therefore does not affect prediction requests in this architecture. GitHub Actions is the selected scheduled-compute boundary; it is not a Render background worker or cron job.

