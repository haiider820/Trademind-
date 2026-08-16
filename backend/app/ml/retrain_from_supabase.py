"""Daily offline retraining entry point for GitHub Actions.

The job resolves mature pending decisions from public Binance spot candles, fits candidates only
from resolved outcomes and the original labeled dataset, evaluates on a newer chronological window,
and writes an incumbent/candidate comparison to Supabase. It never places orders.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
import joblib
import numpy as np
import pandas as pd
import torch
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.utils.class_weight import compute_sample_weight
from torch import nn

from app.core.config import settings
from app.ml.dataset import FEATURE_COLUMNS, PROCESSED_DATA_PATH
from app.ml.model_bundle import BACKEND_DIR, DEFAULT_MANIFEST, ModelBundle
from app.ml.train_baselines import build_model
from app.ml.train_sequence_ensemble import GRUEntryClassifier
from app.services.supabase_service import SupabaseService

INTERVAL_MS = {"15m": 15 * 60 * 1000, "30m": 30 * 60 * 1000, "1h": 60 * 60 * 1000}
HORIZON = settings.ml_serving_horizon_bars
RUN_REPORT = BACKEND_DIR / "reports" / "phase4_retrain_result.json"


def interval_ms() -> int:
    try:
        return INTERVAL_MS[settings.trading_candle_interval.lower()]
    except KeyError as exc:
        raise ValueError("Phase 4 outcome resolution supports 15m, 30m, and 1h intervals.") from exc


async def fetch_pending_outcomes(service: SupabaseService) -> int:
    """Resolve only decisions whose complete forward candle is already available."""
    cutoff = datetime.now(timezone.utc) - timedelta(milliseconds=HORIZON * interval_ms())
    # Use Z notation in the URL filter; an unescaped '+' in ISO8601 offsets is
    # decoded as a space by PostgREST query parsing and causes HTTP 400.
    cutoff_query_value = cutoff.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    query = (
        "select=id,decision_id,decision_time,symbol,action,input_features,input_window_summary,"
        "target_horizon_bars&outcome_status=eq.pending&decision_time=lte."
        + cutoff_query_value
        + "&order=decision_time.asc&limit=1000"
    )
    pending = await service.select("ml_decision_logs", query=query, use_service_key=True)
    if not pending:
        return 0

    resolved = 0
    async with httpx.AsyncClient(timeout=20) as client:
        for row in pending:
            try:
                decision_time = pd.Timestamp(row["decision_time"])
                end_time_ms = int(decision_time.timestamp() * 1000) + HORIZON * interval_ms()
                response = await client.get(
                    f"{settings.binance_base_url}/api/v3/klines",
                    params={
                        "symbol": row["symbol"],
                        "interval": settings.trading_candle_interval,
                        "startTime": end_time_ms,
                        "endTime": end_time_ms + interval_ms(),
                        "limit": 2,
                    },
                )
                response.raise_for_status()
                candles = response.json()
                candle = next((item for item in candles if int(item[0]) == end_time_ms), None)
                if candle is None:
                    continue
                future_close = float(candle[4])
                summary = row.get("input_window_summary") or {}
                entry_price = float(summary["entry_price"])
                atr_pct = float((row.get("input_features") or {})["atr_pct_14"])
                threshold = max(settings.ml_entry_atr_multiple * atr_pct, settings.ml_round_trip_cost_floor)
                actual_return = (future_close / entry_price) - 1.0
                is_win = actual_return > threshold
                realized_pnl = actual_return - threshold if row["action"] == "enter" else 0.0
                await service.update(
                    "ml_decision_logs",
                    {
                        "outcome_status": "resolved",
                        "outcome_resolved_at": datetime.now(timezone.utc).isoformat(),
                        "actual_return": actual_return,
                        "realized_pnl": realized_pnl,
                        "outcome_label": bool(is_win),
                        "outcome_metadata": {
                            "future_close": future_close,
                            "entry_price": entry_price,
                            "entry_return_threshold": threshold,
                            "source": "Binance public spot klines",
                        },
                    },
                    query=f"decision_id=eq.{row['decision_id']}",
                    use_service_key=True,
                )
                resolved += 1
            except (KeyError, ValueError, httpx.HTTPError, IndexError):
                # One malformed or temporarily unavailable row must not discard other outcomes.
                continue
    return resolved


async def fetch_resolved_logs(service: SupabaseService) -> list[dict[str, Any]]:
    """Read all resolved outcomes in chronological pages; no random sampling is used."""
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        query = (
            "select=decision_id,decision_time,symbol,action,model_version_identifier,"
            "input_features,input_window_summary,outcome_resolved_at,actual_return,realized_pnl,"
            "outcome_label,target_horizon_bars&outcome_status=eq.resolved&"
            f"target_horizon_bars=eq.{HORIZON}&order=decision_time.asc&limit=1000&offset={offset}"
        )
        page = await service.select("ml_decision_logs", query=query, use_service_key=True)
        rows.extend(page)
        if len(page) < 1000:
            return rows
        offset += len(page)


def original_training_frame() -> pd.DataFrame:
    frame = pd.read_parquet(PROCESSED_DATA_PATH)
    label = f"entry_label_{HORIZON}b"
    return frame.dropna(subset=FEATURE_COLUMNS + [label]).copy()


def logged_training_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    records = []
    label = f"entry_label_{HORIZON}b"
    for row in rows:
        features = row.get("input_features") or {}
        if not all(column in features for column in FEATURE_COLUMNS):
            continue
        threshold = float((row.get("outcome_metadata") or {}).get("entry_return_threshold", 0.0))
        records.append(
            {
                "timestamp": row["decision_time"],
                "symbol": row["symbol"],
                **{column: float(features[column]) for column in FEATURE_COLUMNS},
                "entry_return_threshold": threshold,
                label: int(bool(row["outcome_label"])),
                "future_return": float(row["actual_return"]),
            }
        )
    return pd.DataFrame.from_records(records)


def chronological_partitions(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = frame.sort_values(["timestamp", "symbol"], kind="stable").reset_index(drop=True)
    cutoff = pd.to_datetime(frame["timestamp"], utc=True).quantile(0.80)
    purge = pd.Timedelta(minutes=15 * HORIZON)
    train = frame.loc[pd.to_datetime(frame["timestamp"], utc=True) < cutoff - purge].copy()
    evaluation = frame.loc[pd.to_datetime(frame["timestamp"], utc=True) >= cutoff].copy()
    if train.empty or evaluation.empty:
        raise ValueError("Chronological retraining split produced an empty partition.")
    return train, evaluation


def metrics(y: np.ndarray, probabilities: np.ndarray, returns: np.ndarray, thresholds: np.ndarray) -> dict[str, Any]:
    signals = probabilities >= 0.5
    signal_returns = returns[signals] - thresholds[signals]
    if len(signal_returns):
        curve = np.cumsum(signal_returns)
        drawdown = float(np.min(curve - np.maximum.accumulate(curve)))
        avg_pnl = float(signal_returns.mean())
        win_rate = float((returns[signals] > thresholds[signals]).mean())
    else:
        drawdown, avg_pnl, win_rate = 0.0, None, None
    return {
        "average_precision": float(average_precision_score(y, probabilities)),
        "roc_auc": float(roc_auc_score(y, probabilities)) if len(np.unique(y)) > 1 else None,
        "signal_count": int(signals.sum()),
        "win_rate": win_rate,
        "average_pnl": avg_pnl,
        "max_drawdown": drawdown,
        "mean_excess_return": float(signal_returns.mean()) if len(signal_returns) else None,
    }


def fit_trees(train: pd.DataFrame, evaluation: pd.DataFrame, version: str) -> dict[str, Any]:
    label = f"entry_label_{HORIZON}b"
    x_train, y_train = train[FEATURE_COLUMNS], train[label].astype(int)
    x_eval = evaluation[FEATURE_COLUMNS]
    output_dir = BACKEND_DIR / "models" / "candidates" / version
    output_dir.mkdir(parents=True, exist_ok=True)
    probabilities = {}
    for name in ("random_forest", "hist_gradient_boosting"):
        model = build_model(name)
        if name == "hist_gradient_boosting":
            model.fit(x_train, y_train, sample_weight=compute_sample_weight(class_weight="balanced", y=y_train))
        else:
            model.fit(x_train, y_train)
        probabilities[name] = model.predict_proba(x_eval)[:, 1]
        joblib.dump(
            {"model": model, "model_name": name, "horizon_bars": HORIZON,
             "decision_threshold": 0.5, "feature_columns": FEATURE_COLUMNS,
             "version_identifier": version},
            output_dir / f"{name}_{HORIZON}bars.joblib", compress=3,
        )
    return probabilities


def _time_key(value: Any) -> str:
    return pd.Timestamp(value).tz_convert("UTC").isoformat()


def _decision_key(symbol: Any, value: Any) -> str:
    return f"{symbol}|{_time_key(value)}"


def fit_gru(train: pd.DataFrame, evaluation: pd.DataFrame, logged_rows: list[dict[str, Any]], version: str) -> np.ndarray:
    """Fit the same compact GRU contract using only outcome-resolved stored windows."""
    examples = []
    for row in logged_rows:
        summary = row.get("input_window_summary") or {}
        values = summary.get("values")
        if values and _time_key(row["decision_time"]) < _time_key(train["timestamp"].max()):
            examples.append((np.asarray(values, dtype=np.float32), int(bool(row["outcome_label"]))))
    if len(examples) < 64:
        raise ValueError("At least 64 resolved causal windows are required before GRU retraining.")
    window = examples[0][0].shape
    x = np.stack([item[0] for item in examples])
    y = np.asarray([item[1] for item in examples], dtype=np.float32)
    mean = x.mean(axis=(0, 1), keepdims=True)
    std = x.std(axis=(0, 1), keepdims=True)
    std[std < 1e-6] = 1.0
    x = (x - mean) / std
    model = GRUEntryClassifier(len(FEATURE_COLUMNS), settings.ml_neural_hidden_size)
    optimizer = torch.optim.AdamW(model.parameters(), lr=settings.ml_neural_learning_rate, weight_decay=1e-4)
    positive = max(float(y.sum()), 1.0)
    loss_function = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([(len(y) - positive) / positive]))
    torch.set_num_threads(2)
    tensor_x, tensor_y = torch.from_numpy(x), torch.from_numpy(y)
    for _ in range(max(1, settings.ml_retraining_neural_epochs)):
        model.train()
        for start in range(0, len(y), settings.ml_neural_batch_size):
            optimizer.zero_grad(set_to_none=True)
            loss = loss_function(model(tensor_x[start:start + settings.ml_neural_batch_size]), tensor_y[start:start + settings.ml_neural_batch_size])
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
    output_dir = BACKEND_DIR / "models" / "candidates" / version
    torch.save(
        {"model_state_dict": model.state_dict(), "feature_columns": FEATURE_COLUMNS,
         "hidden_size": settings.ml_neural_hidden_size, "sequence_window_bars": window[0],
         "scaler_mean": mean.reshape(-1), "scaler_std": std.reshape(-1),
         "version_identifier": version},
        output_dir / f"gru_{HORIZON}bars.pt",
    )
    model.eval()
    window_by_key = {
        _decision_key(row["symbol"], row["decision_time"]): np.asarray((row.get("input_window_summary") or {}).get("values"), dtype=np.float32)
        for row in logged_rows
        if (row.get("input_window_summary") or {}).get("values")
    }
    eval_windows = [window_by_key[_decision_key(row["symbol"], row["timestamp"])] for _, row in evaluation.iterrows()]
    if len(eval_windows) != len(evaluation):
        raise ValueError("GRU evaluation requires complete causal windows for every evaluation row.")
    with torch.no_grad():
        logits = model(torch.from_numpy(((np.stack(eval_windows) - mean) / std).astype(np.float32)))
    return torch.sigmoid(logits).numpy()


def evaluate_bundle(bundle: ModelBundle, evaluation: pd.DataFrame, logged_rows: list[dict[str, Any]]) -> dict[str, Any]:
    lookup = {
        _decision_key(row["symbol"], row["decision_time"]): np.asarray((row.get("input_window_summary") or {}).get("values"), dtype=np.float32)
        for row in logged_rows
        if (row.get("input_window_summary") or {}).get("values")
    }
    probabilities = []
    for _, row in evaluation.iterrows():
        probabilities.append(bundle.score(lookup[_decision_key(row["symbol"], row["timestamp"])].tolist()).entry_probability)
    return metrics(evaluation[f"entry_label_{HORIZON}b"].to_numpy(), np.asarray(probabilities), evaluation["future_return"].to_numpy(), evaluation["entry_return_threshold"].to_numpy())


def promote_if_better(incumbent: dict[str, Any], candidate: dict[str, Any]) -> bool:
    return bool(
        candidate["average_precision"] >= incumbent["average_precision"] + settings.ml_promotion_min_average_precision_gain
        and (candidate["mean_excess_return"] or -np.inf) >= (incumbent["mean_excess_return"] or -np.inf)
        and (candidate["average_pnl"] if candidate["average_pnl"] is not None else -np.inf) >= (incumbent["average_pnl"] if incumbent["average_pnl"] is not None else -np.inf)
        and candidate["max_drawdown"] >= incumbent["max_drawdown"]
        and candidate["signal_count"] >= settings.ml_promotion_min_signal_count
    )


async def run() -> None:
    service = SupabaseService()
    resolved_now = await fetch_pending_outcomes(service)
    resolved_rows = await fetch_resolved_logs(service)
    if not resolved_rows:
        # A fresh deployment may have no resolved decisions yet. Treat this as a
        # successful no-op so the daily job remains observable without risking
        # an artifact change or masking a real retraining failure.
        RUN_REPORT.parent.mkdir(parents=True, exist_ok=True)
        RUN_REPORT.write_text(
            json.dumps(
                {
                    "status": "skipped_no_resolved_outcomes",
                    "resolved_pending_outcomes": resolved_now,
                    "resolved_outcome_count": 0,
                    "promotion_decision": "skipped",
                    "reason": "No resolved outcome logs are available for retraining.",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return
    logged = logged_training_frame(resolved_rows)
    if len(logged) < 128:
        RUN_REPORT.parent.mkdir(parents=True, exist_ok=True)
        RUN_REPORT.write_text(
            json.dumps(
                {
                    "status": "skipped_insufficient_resolved_outcomes",
                    "resolved_pending_outcomes": resolved_now,
                    "resolved_outcome_count": len(logged),
                    "promotion_decision": "skipped",
                    "reason": "At least 128 resolved decisions are required for a chronological retraining evaluation.",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return
    logged_train, evaluation = chronological_partitions(logged)
    original = original_training_frame()
    label = f"entry_label_{HORIZON}b"
    original = original.rename(columns={f"future_return_{HORIZON}b": "future_return"})
    train = pd.concat([original[["timestamp", "symbol", *FEATURE_COLUMNS, "entry_return_threshold", label, "future_return"]], logged_train], ignore_index=True)
    version = f"ensemble-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{os.getenv('GITHUB_SHA', 'local')[:12]}"
    tree_probs = fit_trees(train, evaluation, version)
    gru_probs = fit_gru(train, evaluation, resolved_rows, version)
    ensemble_probs = (tree_probs["random_forest"] + tree_probs["hist_gradient_boosting"] + gru_probs) / 3.0
    candidate_metrics = metrics(evaluation[label].to_numpy(), ensemble_probs, evaluation["future_return"].to_numpy(), evaluation["entry_return_threshold"].to_numpy())
    current_manifest = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
    incumbent_metrics = evaluate_bundle(ModelBundle(DEFAULT_MANIFEST), evaluation, resolved_rows)
    promoted = promote_if_better(incumbent_metrics, candidate_metrics)

    candidate_manifest = {
        "version_identifier": version, "model_family": "ensemble", "source_phase": "phase4",
        "decision_threshold": 0.5, "ensemble_weights": {"random_forest": 1/3, "gradient_boosting": 1/3, "gru": 1/3},
        "artifacts": {
            "random_forest": f"models/candidates/{version}/random_forest_{HORIZON}bars.joblib",
            "gradient_boosting": f"models/candidates/{version}/hist_gradient_boosting_{HORIZON}bars.joblib",
            "gru": f"models/candidates/{version}/gru_{HORIZON}bars.pt",
        },
        "target_contract": {"action_space": ["enter", "no_entry"], "market_mode": settings.trading_market_mode, "candle_interval": settings.trading_candle_interval, "horizon_bars": HORIZON},
        "training_window": {"start": str(train.timestamp.min()), "end": str(train.timestamp.max()), "rows": len(train)},
        "validation_window": {"start": str(evaluation.timestamp.min()), "end": str(evaluation.timestamp.max()), "rows": len(evaluation)},
        "metrics": candidate_metrics,
        "parent_version_identifier": current_manifest["version_identifier"],
    }
    if promoted:
        # Copy only after the gate passes. Stable paths keep the FastAPI contract unchanged across versions.
        candidate_dir = BACKEND_DIR / "models" / "candidates" / version
        current_dir = BACKEND_DIR / "models" / "current"
        stable_paths = {
            "random_forest": current_dir / f"random_forest_{HORIZON}bars.joblib",
            "gradient_boosting": current_dir / f"hist_gradient_boosting_{HORIZON}bars.joblib",
            "gru": current_dir / f"gru_{HORIZON}bars.pt",
        }
        source_paths = {
            "random_forest": candidate_dir / f"random_forest_{HORIZON}bars.joblib",
            "gradient_boosting": candidate_dir / f"hist_gradient_boosting_{HORIZON}bars.joblib",
            "gru": candidate_dir / f"gru_{HORIZON}bars.pt",
        }
        for key, source_path in source_paths.items():
            shutil.copy2(source_path, stable_paths[key])
        candidate_manifest["artifacts"] = {
            "random_forest": f"models/current/random_forest_{HORIZON}bars.joblib",
            "gradient_boosting": f"models/current/hist_gradient_boosting_{HORIZON}bars.joblib",
            "gru": f"models/current/gru_{HORIZON}bars.pt",
        }
        (BACKEND_DIR / "models" / "current" / "model_bundle.json").write_text(json.dumps(candidate_manifest, indent=2) + "\n", encoding="utf-8")
    run_identifier = f"retrain-{uuid.uuid4()}"
    await service.upsert(
        "ml_model_versions",
        {
            "version_identifier": version,
            "model_family": "ensemble",
            "artifact_location": f"repo:backend/models/candidates/{version}",
            "feature_schema_hash": hashlib.sha256(",".join(FEATURE_COLUMNS).encode()).hexdigest(),
            "target_contract": candidate_manifest["target_contract"],
            "training_window": candidate_manifest["training_window"],
            "validation_window": candidate_manifest["validation_window"],
            "metrics": candidate_metrics,
            "parent_version_identifier": current_manifest["version_identifier"],
            "lifecycle_status": "incumbent" if promoted else "rejected",
        },
        on_conflict="version_identifier",
        use_service_key=True,
    )
    await service.insert(
        "ml_retraining_runs",
        {
            "run_identifier": run_identifier,
            "run_kind": "future_offline_retraining",
            "incumbent_version_identifier": current_manifest["version_identifier"],
            "candidate_version_identifier": version,
            "outcome_cutoff_at": str(train.timestamp.max()),
            "candidate_training_window": candidate_manifest["training_window"],
            "evaluation_window": candidate_manifest["validation_window"],
            "resolved_outcome_count": len(resolved_rows),
            "incumbent_metrics": incumbent_metrics,
            "candidate_metrics": candidate_metrics,
            "promotion_decision": "promoted" if promoted else "rejected",
            "decision_rationale": {
                "required_average_precision_gain": settings.ml_promotion_min_average_precision_gain,
                "requires_non_regressive_pnl_and_drawdown": True,
            },
        },
        use_service_key=True,
    )
    RUN_REPORT.parent.mkdir(parents=True, exist_ok=True)
    RUN_REPORT.write_text(json.dumps({"run_identifier": run_identifier, "resolved_pending_outcomes": resolved_now, "resolved_outcome_count": len(resolved_rows), "promotion_decision": "promoted" if promoted else "rejected", "incumbent_metrics": incumbent_metrics, "candidate_metrics": candidate_metrics, "candidate_version": version}, indent=2) + "\n", encoding="utf-8")
    if not promoted:
        raise SystemExit("Candidate rejected by out-of-sample anti-regression gate; current bundle unchanged.")


if __name__ == "__main__":
    asyncio.run(run())
