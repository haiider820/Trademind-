"""Durable, append-oriented offline audit records for the Phase 3 learning simulation.

The SQLite store mirrors the production-oriented Supabase migration but is deliberately local for
historical simulation.  It records decisions and outcomes separately, so future labels are never
present in a decision-time record.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from app.ml.dataset import FEATURE_COLUMNS

BACKEND_DIR = Path(__file__).resolve().parents[2]
AUDIT_DIR = BACKEND_DIR / "data" / "audit"
DEFAULT_AUDIT_DB_PATH = AUDIT_DIR / "phase3_learning_audit.sqlite3"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def feature_schema_hash() -> str:
    """Pin the ordered feature schema recorded with every decision and model version."""
    payload = json.dumps(FEATURE_COLUMNS, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class ModelVersionRecord:
    version_identifier: str
    model_family: str
    artifact_location: str
    target_horizon_bars: int
    training_window_start: str
    training_window_end: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class DecisionRecord:
    decision_id: str
    decision_time: str
    symbol: str
    candle_interval: str
    market_mode: str
    action: str
    model_version_identifier: str
    decision_threshold: float
    model_probabilities: dict[str, float]
    input_features: dict[str, float]
    target_horizon_bars: int
    window_start: str | None = None
    window_end: str | None = None


@dataclass(frozen=True)
class OutcomeRecord:
    decision_id: str
    resolved_at: str
    actual_return: float
    realized_pnl: float
    outcome_label: bool
    metadata: dict[str, Any]


class LearningAuditStore:
    """SQLite-backed, append-oriented audit store used only by the Phase 3 simulation.

    There is intentionally no method to mutate a decision's feature snapshot or model version.
    Outcomes are a separate immutable event keyed by the original decision ID.
    """

    def __init__(self, database_path: Path = DEFAULT_AUDIT_DB_PATH) -> None:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self.database_path = database_path
        self._create_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _create_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                pragma journal_mode = wal;
                create table if not exists model_versions (
                    version_identifier text primary key,
                    model_family text not null,
                    artifact_location text not null,
                    feature_schema_hash text not null,
                    target_horizon_bars integer not null,
                    training_window_start text not null,
                    training_window_end text not null,
                    metadata_json text not null,
                    created_at text not null
                );
                create table if not exists decisions (
                    decision_id text primary key,
                    decision_time text not null,
                    symbol text not null,
                    candle_interval text not null,
                    market_mode text not null,
                    action text not null check (action in ('enter', 'no_entry')),
                    model_version_identifier text not null references model_versions(version_identifier),
                    decision_threshold real not null,
                    model_probabilities_json text not null,
                    input_features_json text not null,
                    feature_schema_hash text not null,
                    target_horizon_bars integer not null,
                    window_start text,
                    window_end text,
                    created_at text not null
                );
                create table if not exists outcomes (
                    decision_id text primary key references decisions(decision_id),
                    resolved_at text not null,
                    actual_return real not null,
                    realized_pnl real not null,
                    outcome_label integer not null check (outcome_label in (0, 1)),
                    metadata_json text not null,
                    created_at text not null
                );
                create table if not exists retraining_runs (
                    run_identifier text primary key,
                    simulation_chunk integer not null,
                    component text not null,
                    incumbent_version_identifier text not null,
                    candidate_version_identifier text not null,
                    outcome_cutoff_at text not null,
                    evaluation_start text not null,
                    evaluation_end text not null,
                    resolved_outcome_count integer not null,
                    incumbent_metrics_json text not null,
                    candidate_metrics_json text not null,
                    promotion_decision text not null check (promotion_decision in ('promoted', 'rejected')),
                    decision_rationale_json text not null,
                    created_at text not null
                );
                create table if not exists performance_observations (
                    run_identifier text not null references retraining_runs(run_identifier),
                    model_version_identifier text not null,
                    observation_start text not null,
                    observation_end text not null,
                    decision_count integer not null,
                    resolved_count integer not null,
                    win_rate real,
                    average_pnl real,
                    max_drawdown real,
                    metrics_json text not null,
                    created_at text not null,
                    primary key (run_identifier, model_version_identifier)
                );
                create index if not exists idx_decisions_time on decisions(decision_time);
                create index if not exists idx_outcomes_resolved on outcomes(resolved_at);
                """
            )

    def register_model_version(self, record: ModelVersionRecord) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                insert or ignore into model_versions (
                    version_identifier, model_family, artifact_location, feature_schema_hash,
                    target_horizon_bars, training_window_start, training_window_end, metadata_json, created_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.version_identifier,
                    record.model_family,
                    record.artifact_location,
                    feature_schema_hash(),
                    record.target_horizon_bars,
                    record.training_window_start,
                    record.training_window_end,
                    json.dumps(record.metadata, sort_keys=True),
                    utc_now(),
                ),
            )

    def append_decisions(self, records: Iterable[DecisionRecord]) -> int:
        rows = []
        schema_hash = feature_schema_hash()
        for record in records:
            if record.action not in {"enter", "no_entry"}:
                raise ValueError(f"Unsupported action {record.action!r}.")
            if set(record.input_features) != set(FEATURE_COLUMNS):
                raise ValueError("Decision feature snapshot does not match the exact Phase 1 feature schema.")
            rows.append(
                (
                    record.decision_id,
                    record.decision_time,
                    record.symbol,
                    record.candle_interval,
                    record.market_mode,
                    record.action,
                    record.model_version_identifier,
                    record.decision_threshold,
                    json.dumps(record.model_probabilities, sort_keys=True),
                    json.dumps(record.input_features, sort_keys=True),
                    schema_hash,
                    record.target_horizon_bars,
                    record.window_start,
                    record.window_end,
                    utc_now(),
                )
            )
        if not rows:
            return 0
        with self._connect() as connection:
            connection.executemany(
                """
                insert into decisions (
                    decision_id, decision_time, symbol, candle_interval, market_mode, action,
                    model_version_identifier, decision_threshold, model_probabilities_json,
                    input_features_json, feature_schema_hash, target_horizon_bars,
                    window_start, window_end, created_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        return len(rows)

    def append_outcomes(self, records: Iterable[OutcomeRecord]) -> int:
        rows = [
            (
                record.decision_id,
                record.resolved_at,
                record.actual_return,
                record.realized_pnl,
                int(record.outcome_label),
                json.dumps(record.metadata, sort_keys=True),
                utc_now(),
            )
            for record in records
        ]
        if not rows:
            return 0
        with self._connect() as connection:
            connection.executemany(
                """
                insert into outcomes (
                    decision_id, resolved_at, actual_return, realized_pnl, outcome_label,
                    metadata_json, created_at
                ) values (?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        return len(rows)

    def resolved_feature_frame(self, resolved_before: pd.Timestamp) -> pd.DataFrame:
        """Return only outcomes actually resolved before the candidate-training cutoff."""
        query = """
            select d.decision_time as timestamp, d.symbol, d.input_features_json,
                   d.target_horizon_bars, o.actual_return, o.realized_pnl, o.outcome_label,
                   o.resolved_at, o.metadata_json
            from decisions d join outcomes o on o.decision_id = d.decision_id
            where o.resolved_at < ?
            order by d.decision_time, d.symbol
        """
        with self._connect() as connection:
            frame = pd.read_sql_query(query, connection, params=(resolved_before.isoformat(),))
        if frame.empty:
            return frame
        snapshots = pd.DataFrame([json.loads(value) for value in frame.pop("input_features_json")])
        metadata = [json.loads(value) for value in frame.pop("metadata_json")]
        frame = pd.concat([frame.reset_index(drop=True), snapshots], axis=1)
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
        frame["resolved_at"] = pd.to_datetime(frame["resolved_at"], utc=True)
        frame["entry_return_threshold"] = [float(value["entry_return_threshold"]) for value in metadata]
        return frame

    def write_retraining_run(
        self,
        run_identifier: str,
        simulation_chunk: int,
        component: str,
        incumbent_version_identifier: str,
        candidate_version_identifier: str,
        outcome_cutoff_at: pd.Timestamp,
        evaluation_start: pd.Timestamp,
        evaluation_end: pd.Timestamp,
        resolved_outcome_count: int,
        incumbent_metrics: dict[str, Any],
        candidate_metrics: dict[str, Any],
        promotion_decision: str,
        decision_rationale: dict[str, Any],
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                insert into retraining_runs values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_identifier,
                    simulation_chunk,
                    component,
                    incumbent_version_identifier,
                    candidate_version_identifier,
                    outcome_cutoff_at.isoformat(),
                    evaluation_start.isoformat(),
                    evaluation_end.isoformat(),
                    resolved_outcome_count,
                    json.dumps(incumbent_metrics, sort_keys=True),
                    json.dumps(candidate_metrics, sort_keys=True),
                    promotion_decision,
                    json.dumps(decision_rationale, sort_keys=True),
                    utc_now(),
                ),
            )

    def write_performance_observation(
        self,
        run_identifier: str,
        model_version_identifier: str,
        observation_start: pd.Timestamp,
        observation_end: pd.Timestamp,
        decision_count: int,
        resolved_count: int,
        win_rate: float | None,
        average_pnl: float | None,
        max_drawdown: float | None,
        metrics: dict[str, Any],
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                insert into performance_observations values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_identifier,
                    model_version_identifier,
                    observation_start.isoformat(),
                    observation_end.isoformat(),
                    decision_count,
                    resolved_count,
                    win_rate,
                    average_pnl,
                    max_drawdown,
                    json.dumps(metrics, sort_keys=True),
                    utc_now(),
                ),
            )

    def export_table(self, table_name: str) -> pd.DataFrame:
        """Export a named audit table for report generation after whitelisting the table name."""
        if table_name not in {"model_versions", "decisions", "outcomes", "retraining_runs", "performance_observations"}:
            raise ValueError(f"Unsupported audit table export: {table_name}")
        with self._connect() as connection:
            return pd.read_sql_query(f"select * from {table_name} order by rowid", connection)
