"""Phase 3 offline, chronological self-learning simulation.

This program simulates decision logging and later outcome resolution across sequential portions of
Phase 1's held-out history.  At each later chunk, candidates are trained only on the original
training set plus audit-log outcomes resolved before the chunk begins.  It never accesses Binance,
changes live model files, schedules work, or sends orders.
"""

from __future__ import annotations

import gc
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import torch
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.utils.class_weight import compute_sample_weight
from torch import nn

from app.core.config import settings
from app.ml.dataset import FEATURE_COLUMNS, INTERVAL_TO_DELTA
from app.ml.learning_audit import (
    AUDIT_DIR,
    DEFAULT_AUDIT_DB_PATH,
    DecisionRecord,
    LearningAuditStore,
    ModelVersionRecord,
    OutcomeRecord,
)
from app.ml.sequence_data import SequencePartition, build_sequence_data, selected_horizon
from app.ml.train_baselines import DECISION_THRESHOLD, build_model, load_dataset_and_split
from app.ml.train_sequence_ensemble import (
    GRUEntryClassifier,
    build_loader,
    endpoint_frame,
    positive_weight,
    predict_probabilities,
    seed_everything,
    train_epoch,
)

BACKEND_DIR = Path(__file__).resolve().parents[2]
PHASE1_MODELS_DIR = BACKEND_DIR / "models" / "phase1"
PHASE2_MODELS_DIR = BACKEND_DIR / "models" / "phase2"
PHASE3_MODELS_DIR = BACKEND_DIR / "models" / "phase3"
REPORTS_DIR = BACKEND_DIR / "reports"
SUMMARY_PATH = REPORTS_DIR / "phase3_self_learning_summary.json"
CHUNK_METRICS_PATH = REPORTS_DIR / "phase3_chunk_metrics.csv"
PROMOTION_PATH = REPORTS_DIR / "phase3_promotion_log.csv"
PERFORMANCE_PATH = REPORTS_DIR / "phase3_performance_monitoring.csv"


def _iso(value: pd.Timestamp) -> str:
    return pd.Timestamp(value).isoformat()


def _model_version_name(prefix: str, chunk: int | None = None) -> str:
    return prefix if chunk is None else f"{prefix}_candidate_chunk_{chunk}"


def _load_incumbent_models() -> dict[str, Any]:
    """Load the approved Phase 1/2 research artifacts as simulation incumbents only."""
    models: dict[str, Any] = {}
    for name in ("random_forest", "hist_gradient_boosting"):
        artifact = joblib.load(PHASE1_MODELS_DIR / f"{name}_4bars.joblib")
        models[name] = artifact["model"]
    gru_artifact = torch.load(PHASE2_MODELS_DIR / "gru_4bars.pt", map_location="cpu", weights_only=False)
    gru = GRUEntryClassifier(len(gru_artifact["feature_columns"]), gru_artifact["hidden_size"])
    gru.load_state_dict(gru_artifact["model_state_dict"])
    gru.eval()
    models["gru"] = gru
    models["gru_artifact"] = gru_artifact
    return models


def _score_gru(data: Any, partition: SequencePartition, model: GRUEntryClassifier) -> np.ndarray:
    return predict_probabilities(model, build_loader(data, partition, settings.ml_neural_batch_size))


def _score_components(
    frame: pd.DataFrame,
    data: Any,
    partition: SequencePartition,
    models: dict[str, Any],
) -> dict[str, np.ndarray]:
    """Return aligned component probabilities and the fixed equal-weight ensemble."""
    outputs = {
        "random_forest": models["random_forest"].predict_proba(frame[FEATURE_COLUMNS])[:, 1],
        "hist_gradient_boosting": models["hist_gradient_boosting"].predict_proba(frame[FEATURE_COLUMNS])[:, 1],
        "gru": _score_gru(data, partition, models["gru"]),
    }
    if any(len(values) != len(frame) for values in outputs.values()):
        raise RuntimeError("Component prediction length does not match chronological endpoint metadata.")
    outputs["ensemble"] = np.mean(
        [outputs["random_forest"], outputs["hist_gradient_boosting"], outputs["gru"]], axis=0
    )
    return outputs


def _performance_metrics(frame: pd.DataFrame, probabilities: np.ndarray, horizon: int) -> dict[str, float | int | None]:
    """Calculate non-compounded event P&L and drawdown for a fixed threshold.

    A notional event P&L subtracts the configured round-trip-cost floor only when a model enters.
    This deliberately avoids presenting overlapping 15-minute signals as a tradable compounded curve.
    """
    label_column = f"entry_label_{horizon}b"
    return_column = f"future_return_{horizon}b"
    labels = frame[label_column].astype(int).to_numpy()
    signals = probabilities >= DECISION_THRESHOLD
    event_returns = frame[return_column].to_numpy(dtype=float)
    pnl = np.where(signals, event_returns - settings.ml_round_trip_cost_floor, 0.0)
    cumulative = np.cumsum(pnl)
    running_peak = np.maximum.accumulate(np.concatenate(([0.0], cumulative)))[:-1]
    max_drawdown = float(np.min(cumulative - running_peak)) if len(cumulative) else 0.0
    if signals.any():
        signal_labels = labels[signals]
        signal_returns = event_returns[signals]
        thresholds = frame.loc[signals, "entry_return_threshold"].to_numpy(dtype=float)
        win_rate: float | None = float(signal_labels.mean())
        mean_excess: float | None = float((signal_returns - thresholds).mean())
        mean_signal_pnl: float | None = float(pnl[signals].mean())
    else:
        win_rate = None
        mean_excess = None
        mean_signal_pnl = None
    return {
        "roc_auc": float(roc_auc_score(labels, probabilities)) if len(np.unique(labels)) > 1 else None,
        "average_precision": float(average_precision_score(labels, probabilities)) if len(np.unique(labels)) > 1 else None,
        "brier_score": float(brier_score_loss(labels, probabilities)),
        "decision_count": int(len(frame)),
        "signal_count": int(signals.sum()),
        "signal_rate": float(signals.mean()),
        "label_positive_rate": float(labels.mean()),
        "win_rate": win_rate,
        "average_pnl": float(pnl.mean()),
        "average_signal_pnl": mean_signal_pnl,
        "mean_excess_return": mean_excess,
        "max_drawdown": max_drawdown,
    }


def _promotion_gate(incumbent: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    """Apply the fixed conservative gate without seeing future chunks or tuning its thresholds."""
    ap_gain = float(candidate["average_precision"] - incumbent["average_precision"])
    economic_non_regression = float(candidate["mean_excess_return"]) >= float(incumbent["mean_excess_return"])
    average_pnl_non_regression = float(candidate["average_pnl"]) >= float(incumbent["average_pnl"])
    max_drawdown_non_regression = float(candidate["max_drawdown"]) >= float(incumbent["max_drawdown"])
    enough_signals = int(candidate["signal_count"]) >= settings.ml_promotion_min_signal_count
    promoted = (
        ap_gain >= settings.ml_promotion_min_average_precision_gain
        and economic_non_regression
        and average_pnl_non_regression
        and max_drawdown_non_regression
        and enough_signals
    )
    return {
        "promoted": promoted,
        "average_precision_gain": ap_gain,
        "minimum_average_precision_gain": settings.ml_promotion_min_average_precision_gain,
        "economic_non_regression": economic_non_regression,
        "average_pnl_non_regression": average_pnl_non_regression,
        "max_drawdown_non_regression": max_drawdown_non_regression,
        "minimum_signal_count_met": enough_signals,
        "minimum_signal_count": settings.ml_promotion_min_signal_count,
        "rule": "candidate AP improves by configured minimum, candidate mean excess return, average P&L, and maximum drawdown do not decline, and candidate emits enough signals",
    }


def _time_spaced_base_rows(frame: pd.DataFrame) -> pd.DataFrame:
    """Bound baseline rows deterministically without random sampling or discarding audit outcomes."""
    cap = settings.ml_retraining_tree_base_row_cap
    if cap < 10_000:
        raise ValueError("ML_RETRAINING_TREE_BASE_ROW_CAP must be at least 10,000.")
    if len(frame) <= cap:
        return frame.copy()
    positions = np.linspace(0, len(frame) - 1, num=cap, dtype=np.int64)
    return frame.iloc[positions].copy()


def _fit_tree_candidate(training: pd.DataFrame, model_name: str, horizon: int) -> Any:
    label_column = f"entry_label_{horizon}b"
    subset = training.dropna(subset=[label_column]).copy()
    model = build_model(model_name)
    if model_name == "random_forest":
        model.set_params(
            n_estimators=settings.ml_retraining_tree_n_estimators,
            max_samples=settings.ml_retraining_tree_max_samples,
        )
    features = subset[FEATURE_COLUMNS]
    labels = subset[label_column].astype(int)
    if model_name == "hist_gradient_boosting":
        model.fit(features, labels, sample_weight=compute_sample_weight(class_weight="balanced", y=labels))
    else:
        model.fit(features, labels)
    return model


def _partition_from_resolved_logs(
    data: Any,
    validation_frame: pd.DataFrame,
    resolved_rows: pd.DataFrame,
) -> SequencePartition:
    """Use audit-log timestamps to add only known resolved outcomes to GRU retraining."""
    resolved_keys = set(zip(resolved_rows["timestamp"].astype("int64"), resolved_rows["symbol"]))
    valid_keys = list(zip(validation_frame["timestamp"].astype("int64"), validation_frame["symbol"]))
    stride_mask = np.arange(len(validation_frame)) % settings.ml_sequence_training_stride == 0
    extra_positions = np.array(
        [index for index, key in enumerate(valid_keys) if stride_mask[index] and key in resolved_keys], dtype=int
    )
    if len(extra_positions):
        endpoints = np.vstack((data.final_train.endpoints, data.validation.endpoints[extra_positions]))
    else:
        endpoints = data.final_train.endpoints.copy()
    return SequencePartition(endpoints)


def _fit_gru_candidate(data: Any, partition: SequencePartition) -> GRUEntryClassifier:
    """Refit the same GRU only on original and audit-log-resolved sequence endpoints."""
    seed_everything()
    loader = build_loader(data, partition, settings.ml_neural_batch_size)
    model = GRUEntryClassifier(len(FEATURE_COLUMNS), settings.ml_neural_hidden_size)
    optimizer = torch.optim.AdamW(model.parameters(), lr=settings.ml_neural_learning_rate, weight_decay=1e-4)
    loss = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([positive_weight(data, partition)], dtype=torch.float32))
    for epoch in range(1, settings.ml_retraining_neural_epochs + 1):
        value = train_epoch(model, loader, optimizer, loss)
        print(f"Candidate GRU epoch {epoch}/{settings.ml_retraining_neural_epochs}: loss={value:.5f}", flush=True)
    return model


def _save_candidate_artifacts(
    models: dict[str, Any],
    data: Any,
    chunk: int,
    horizon: int,
    training_end: pd.Timestamp,
) -> dict[str, str]:
    PHASE3_MODELS_DIR.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}
    for name in ("random_forest", "hist_gradient_boosting"):
        path = PHASE3_MODELS_DIR / f"{_model_version_name(name, chunk)}.joblib"
        joblib.dump(
            {
                "model": models[name],
                "model_name": name,
                "target_horizon_bars": horizon,
                "feature_columns": FEATURE_COLUMNS,
                "trained_through_utc": _iso(training_end),
                "source": "Phase 3 audit-log retraining simulation",
                "resource_bounds": {
                    "base_row_cap": settings.ml_retraining_tree_base_row_cap,
                    "random_forest_n_estimators": settings.ml_retraining_tree_n_estimators if name == "random_forest" else None,
                    "random_forest_max_samples": settings.ml_retraining_tree_max_samples if name == "random_forest" else None,
                },
            },
            path,
            compress=3,
        )
        paths[name] = str(path.relative_to(BACKEND_DIR))
    gru_path = PHASE3_MODELS_DIR / f"{_model_version_name('gru', chunk)}.pt"
    torch.save(
        {
            "model_state_dict": models["gru"].state_dict(),
            "architecture": "GRUEntryClassifier",
            "hidden_size": settings.ml_neural_hidden_size,
            "feature_columns": FEATURE_COLUMNS,
            "sequence_window_bars": settings.ml_sequence_window_bars,
            "scaler_mean": data.scaler_mean,
            "scaler_std": data.scaler_std,
            "target_horizon_bars": horizon,
            "trained_through_utc": _iso(training_end),
            "source": "Phase 3 audit-log retraining simulation",
        },
        gru_path,
    )
    paths["gru"] = str(gru_path.relative_to(BACKEND_DIR))
    return paths


def _register_versions(
    store: LearningAuditStore,
    chunk: int | None,
    paths: dict[str, str],
    horizon: int,
    training_start: pd.Timestamp,
    training_end: pd.Timestamp,
) -> None:
    names = ("random_forest", "hist_gradient_boosting", "gru", "ensemble")
    for name in names:
        version = _model_version_name(name, chunk)
        location = paths.get(name, "component probability average; no standalone serialized artifact")
        store.register_model_version(
            ModelVersionRecord(
                version_identifier=version,
                model_family=name if name != "ensemble" else "ensemble",
                artifact_location=location,
                target_horizon_bars=horizon,
                training_window_start=_iso(training_start),
                training_window_end=_iso(training_end),
                metadata={
                    "simulation_only": True,
                    "component": name,
                    "decision_threshold": DECISION_THRESHOLD,
                    "ensemble_rule": "fixed equal-weight average" if name == "ensemble" else None,
                },
            )
        )


def _append_chunk_decisions_and_outcomes(
    store: LearningAuditStore,
    frame: pd.DataFrame,
    probabilities: dict[str, np.ndarray],
    version_identifier: str,
    horizon: int,
) -> None:
    """Append decision-time snapshots first, then separate later-resolved outcome events in batches."""
    interval = settings.trading_candle_interval.strip().lower()
    delta = INTERVAL_TO_DELTA[interval]
    ensemble = probabilities["ensemble"]
    batch_size = 5_000
    for start in range(0, len(frame), batch_size):
        stop = min(start + batch_size, len(frame))
        decisions: list[DecisionRecord] = []
        outcomes: list[OutcomeRecord] = []
        for row_index, row in frame.iloc[start:stop].iterrows():
            local_index = row_index
            timestamp = pd.Timestamp(row["timestamp"])
            decision_id = f"{version_identifier}:{row['symbol']}:{timestamp.isoformat()}"
            action = "enter" if ensemble[local_index] >= DECISION_THRESHOLD else "no_entry"
            feature_snapshot = {name: float(row[name]) for name in FEATURE_COLUMNS}
            decisions.append(
                DecisionRecord(
                    decision_id=decision_id,
                    decision_time=_iso(timestamp),
                    symbol=str(row["symbol"]),
                    candle_interval=interval,
                    market_mode=settings.trading_market_mode,
                    action=action,
                    model_version_identifier=version_identifier,
                    decision_threshold=DECISION_THRESHOLD,
                    model_probabilities={name: float(probabilities[name][local_index]) for name in probabilities},
                    input_features=feature_snapshot,
                    target_horizon_bars=horizon,
                    window_start=_iso(timestamp - ((settings.ml_sequence_window_bars - 1) * delta)),
                    window_end=_iso(timestamp),
                )
            )
            actual_return = float(row[f"future_return_{horizon}b"])
            event_pnl = actual_return - settings.ml_round_trip_cost_floor if action == "enter" else 0.0
            outcomes.append(
                OutcomeRecord(
                    decision_id=decision_id,
                    resolved_at=_iso(timestamp + (horizon * delta)),
                    actual_return=actual_return,
                    realized_pnl=event_pnl,
                    outcome_label=bool(row[f"entry_label_{horizon}b"]),
                    metadata={
                        "entry_return_threshold": float(row["entry_return_threshold"]),
                        "label_definition": "future return exceeds stored ATR-or-cost threshold",
                        "simulation_only": True,
                    },
                )
            )
        store.append_decisions(decisions)
        store.append_outcomes(outcomes)


def _metrics_rows(chunk: int, role: str, values: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"simulation_chunk": chunk, "role": role, "component": name, **metrics} for name, metrics in values.items()]


def main() -> None:
    if settings.ml_retraining_chunk_count < 3:
        raise ValueError("ML_RETRAINING_CHUNK_COUNT must be at least 3 to produce sequential retraining gates.")
    horizon = selected_horizon()
    if horizon != 4:
        raise ValueError("Phase 3 preserves the approved Phase 1 4-bar target only.")
    if DEFAULT_AUDIT_DB_PATH.exists():
        DEFAULT_AUDIT_DB_PATH.unlink()
    PHASE3_MODELS_DIR.mkdir(parents=True, exist_ok=True)
    for path in PHASE3_MODELS_DIR.glob("*"):
        if path.is_file():
            path.unlink()

    store = LearningAuditStore()
    data = build_sequence_data()
    validation_frame = endpoint_frame(data, data.validation, horizon)
    if len(validation_frame) != len(data.validation.endpoints):
        raise RuntimeError("Final sequence endpoint metadata is not aligned with validation endpoints.")
    original_train, _ = load_dataset_and_split()
    original_train = original_train.dropna(subset=[f"entry_label_{horizon}b"]).copy()
    original_train_start = original_train["timestamp"].min()
    original_train_end = original_train["timestamp"].max()
    tree_base_train = _time_spaced_base_rows(original_train)
    # The full original frame is no longer needed once the deterministic tree baseline is formed.
    del original_train
    gc.collect()
    incumbent = _load_incumbent_models()
    if not np.allclose(data.scaler_mean, incumbent["gru_artifact"]["scaler_mean"]) or not np.allclose(
        data.scaler_std, incumbent["gru_artifact"]["scaler_std"]
    ):
        raise RuntimeError("Phase 2 GRU scaler does not match the current sequence-data contract.")

    baseline_paths = {
        "random_forest": str((PHASE1_MODELS_DIR / "random_forest_4bars.joblib").relative_to(BACKEND_DIR)),
        "hist_gradient_boosting": str((PHASE1_MODELS_DIR / "hist_gradient_boosting_4bars.joblib").relative_to(BACKEND_DIR)),
        "gru": str((PHASE2_MODELS_DIR / "gru_4bars.pt").relative_to(BACKEND_DIR)),
    }
    _register_versions(
        store,
        None,
        baseline_paths,
        horizon,
        original_train_start,
        original_train_end,
    )

    all_positions = np.arange(len(validation_frame))
    chunks = [positions for positions in np.array_split(all_positions, settings.ml_retraining_chunk_count) if len(positions)]
    metric_rows: list[dict[str, Any]] = []
    promotion_rows: list[dict[str, Any]] = []
    current_version = _model_version_name("ensemble")
    current_models = incumbent

    for chunk_index, positions in enumerate(chunks, start=1):
        chunk_frame = validation_frame.iloc[positions].reset_index(drop=True)
        chunk_partition = SequencePartition(data.validation.endpoints[positions])
        chunk_start = pd.Timestamp(chunk_frame["timestamp"].min())
        chunk_end = pd.Timestamp(chunk_frame["timestamp"].max())

        if chunk_index == 1:
            active_probabilities = _score_components(chunk_frame, data, chunk_partition, current_models)
            active_metrics = {
                name: _performance_metrics(chunk_frame, values, horizon) for name, values in active_probabilities.items()
            }
            metric_rows.extend(_metrics_rows(chunk_index, "initial_incumbent", active_metrics))
            _append_chunk_decisions_and_outcomes(store, chunk_frame, active_probabilities, current_version, horizon)
            print(f"Logged and resolved initial simulation chunk {chunk_index}/{len(chunks)}.", flush=True)
            continue

        # The only validation-period training rows originate in auditable outcomes resolved before
        # this chunk begins; outcomes inside the candidate evaluation chunk are unavailable here.
        resolved = store.resolved_feature_frame(chunk_start)
        training = pd.concat(
            [
                tree_base_train,
                resolved.rename(columns={"outcome_label": f"entry_label_{horizon}b", "actual_return": f"future_return_{horizon}b"}),
            ],
            ignore_index=True,
            sort=False,
        )
        print(
            f"Chunk {chunk_index}: retraining on {len(tree_base_train):,} time-spaced original rows plus {len(resolved):,} resolved audit outcomes.",
            flush=True,
        )
        candidate = {
            "random_forest": _fit_tree_candidate(training, "random_forest", horizon),
            "hist_gradient_boosting": _fit_tree_candidate(training, "hist_gradient_boosting", horizon),
        }
        # Tree estimators now own their fitted state; release the wide training DataFrame before GRU work.
        del training
        gc.collect()
        candidate_partition = _partition_from_resolved_logs(data, validation_frame, resolved)
        candidate["gru"] = _fit_gru_candidate(data, candidate_partition)
        candidate_probabilities = _score_components(chunk_frame, data, chunk_partition, candidate)
        incumbent_probabilities = _score_components(chunk_frame, data, chunk_partition, current_models)
        candidate_metrics = {
            name: _performance_metrics(chunk_frame, values, horizon) for name, values in candidate_probabilities.items()
        }
        incumbent_metrics = {
            name: _performance_metrics(chunk_frame, values, horizon) for name, values in incumbent_probabilities.items()
        }
        gates = {name: _promotion_gate(incumbent_metrics[name], candidate_metrics[name]) for name in candidate_metrics}
        bundle_promoted = all(gate["promoted"] for gate in gates.values())
        candidate_paths = _save_candidate_artifacts(candidate, data, chunk_index, horizon, chunk_start)
        _register_versions(
            store,
            chunk_index,
            candidate_paths,
            horizon,
            original_train_start,
            chunk_start,
        )
        candidate_ensemble_version = _model_version_name("ensemble", chunk_index)
        run_identifier = f"historical_simulation_chunk_{chunk_index}"
        store.write_retraining_run(
            run_identifier=run_identifier,
            simulation_chunk=chunk_index,
            component="ensemble_bundle",
            incumbent_version_identifier=current_version,
            candidate_version_identifier=candidate_ensemble_version,
            outcome_cutoff_at=chunk_start,
            evaluation_start=chunk_start,
            evaluation_end=chunk_end,
            resolved_outcome_count=len(resolved),
            incumbent_metrics=incumbent_metrics,
            candidate_metrics=candidate_metrics,
            promotion_decision="promoted" if bundle_promoted else "rejected",
            decision_rationale={
                "bundle_rule": "all three components and their fixed equal-weight ensemble must independently pass the conservative gate",
                "component_gates": gates,
                "historical_simulation_only": True,
            },
        )
        for version, metrics in ((current_version, incumbent_metrics["ensemble"]), (candidate_ensemble_version, candidate_metrics["ensemble"])):
            store.write_performance_observation(
                run_identifier=run_identifier,
                model_version_identifier=version,
                observation_start=chunk_start,
                observation_end=chunk_end,
                decision_count=int(metrics["decision_count"]),
                resolved_count=int(metrics["decision_count"]),
                win_rate=metrics["win_rate"],
                average_pnl=metrics["average_pnl"],
                max_drawdown=metrics["max_drawdown"],
                metrics=metrics,
            )
        metric_rows.extend(_metrics_rows(chunk_index, "incumbent", incumbent_metrics))
        metric_rows.extend(_metrics_rows(chunk_index, "candidate", candidate_metrics))
        for name, gate in gates.items():
            promotion_rows.append(
                {
                    "simulation_chunk": chunk_index,
                    "component": name,
                    "bundle_promoted": bundle_promoted,
                    "incumbent_version": current_version,
                    "candidate_version": candidate_ensemble_version,
                    **gate,
                }
            )

        # The candidate's evaluation chunk remains incumbent-controlled.  A passed candidate only
        # becomes eligible for the *next* unseen chunk, preventing post-evaluation look-ahead.
        execution_version = current_version
        _append_chunk_decisions_and_outcomes(
            store, chunk_frame, incumbent_probabilities, execution_version, horizon
        )
        if bundle_promoted:
            current_models = {**candidate, "gru_artifact": incumbent["gru_artifact"]}
            current_version = candidate_ensemble_version
        else:
            # Rejected models must not remain resident into the next retraining pass.
            del candidate
        del resolved, candidate_partition, candidate_probabilities, incumbent_probabilities
        gc.collect()
        print(
            f"Chunk {chunk_index}: bundle {'promoted' if bundle_promoted else 'rejected'}; "
            f"evaluation-chunk decisions retained {execution_version}; next chunk uses {current_version}.",
            flush=True,
        )

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    chunk_metrics = pd.DataFrame(metric_rows)
    promotions = pd.DataFrame(promotion_rows)
    performance = store.export_table("performance_observations")
    chunk_metrics.to_csv(CHUNK_METRICS_PATH, index=False)
    promotions.to_csv(PROMOTION_PATH, index=False)
    performance.to_csv(PERFORMANCE_PATH, index=False)
    audit_counts = {table: int(len(store.export_table(table))) for table in ("model_versions", "decisions", "outcomes", "retraining_runs", "performance_observations")}
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "offline chronological historical simulation only; no schedule, deployment, exchange, scanner, or order integration",
        "target_contract": {
            "target": "long-only enter/no-entry",
            "horizon_bars": horizon,
            "interval": settings.trading_candle_interval,
            "market_mode": settings.trading_market_mode,
            "provisional_values": ["trading_candle_interval", "trading_market_mode"],
        },
        "simulation": {
            "sequential_holdout_chunks": len(chunks),
            "tree_base_row_cap": settings.ml_retraining_tree_base_row_cap,
            "tree_base_rows_used": len(tree_base_train),
            "initial_chunk": "incumbent decisions/outcomes only",
            "retraining_chunks": len(chunks) - 1,
            "candidate_training": "all auditable decision outcomes resolved before evaluation chunk plus a deterministic time-spaced cap of original Phase 1 rows for tree-memory safety; GRU retains its full Phase 1 final-train endpoint set",
            "final_holdout_use": "sequentially simulated; a chunk is never used for its own candidate fit, promotion decision, or candidate-executed decisions. Promotion becomes eligible only for the next unseen chunk.",
        },
        "promotion_gate": {
            "minimum_average_precision_gain": settings.ml_promotion_min_average_precision_gain,
            "minimum_signal_count": settings.ml_promotion_min_signal_count,
            "economic_non_regression": "candidate mean excess return and average P&L must each be at least incumbent values; candidate maximum drawdown must be no worse than incumbent",
            "bundle_rule": "all component and ensemble gates must pass; otherwise candidate bundle is rejected",
        },
        "audit_database": str(DEFAULT_AUDIT_DB_PATH.relative_to(BACKEND_DIR)),
        "audit_record_counts": audit_counts,
        "promotions": promotion_rows,
        "reports": {
            "chunk_metrics": str(CHUNK_METRICS_PATH.relative_to(BACKEND_DIR)),
            "promotion_log": str(PROMOTION_PATH.relative_to(BACKEND_DIR)),
            "performance_monitoring": str(PERFORMANCE_PATH.relative_to(BACKEND_DIR)),
        },
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote self-learning simulation summary: {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
