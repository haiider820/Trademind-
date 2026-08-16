# Phase 4 Internal Prediction API

## Boundary

The prediction service is integrated into TradeMind's existing FastAPI process. It is **not** a separate public service, does not fetch candles, does not calculate indicators, does not retrain models in request handling, and never places orders. The existing signal-monitor process remains responsible for building causal feature windows from completed candles.

The endpoint is intended for the existing internal scanner, which evaluates approximately every 15 minutes across the seven configured pairs. Because the route is in-process, no Render keep-alive ping is needed and there is no separate prediction-service cold start. If the backend process restarts, its lazy model loader reads the committed current bundle on the first prediction request.

## Endpoints

| Method | Path | Authentication | Purpose |
| --- | --- | --- | --- |
| `GET` | `/api/v1/prediction/health` | None | Model readiness, current version, feature-schema hash, sequence length, and audit-store configuration status |
| `POST` | `/api/v1/prediction/predict` | Supabase bearer token | Score one causal rolling window, return the ensemble decision and version, and persist the decision audit record |

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
      "sequence_window_bars": 32,
      "artifact_manifest": ".../backend/models/current/model_bundle.json"
    },
    "audit_store_configured": true
  }
}
```

A degraded response has `success: false`, `data.status: "degraded"`, and `data.model_ready: false`. This endpoint checks the local artifact bundle but does not perform a database write.

## Prediction request

`POST /api/v1/prediction/predict` requires `Authorization: Bearer <supabase-access-token>` and accepts:

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

The route returns `422` for invalid shape, non-finite values, or incompatible model contracts; `401` for missing or invalid authentication; and `503` if the Supabase audit write is unavailable. The route returns only a model decision; the caller remains responsible for any separate trading-policy, risk, balance, and execution checks.

## Audit records

After successful scoring, the backend writes `ml_model_versions` and an idempotent `ml_decision_logs` row to Supabase using the server-only service-role key. The decision log contains the last-row feature snapshot plus the complete 32-row causal window so the scheduled retraining job can later train the GRU on resolved outcomes. Request logs record the decision ID, symbol, authenticated user ID, action, and model version; they do not log the feature window or service-role credentials.

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

