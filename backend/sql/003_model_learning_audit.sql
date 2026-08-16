-- Phase 3: auditable self-learning records. This migration defines storage only; it does not
-- schedule retraining, load models, or connect any decision to live order execution.

create extension if not exists pgcrypto;

create table if not exists ml_model_versions (
    id uuid primary key default gen_random_uuid(),
    version_identifier text not null unique,
    model_family text not null check (model_family in ('random_forest', 'hist_gradient_boosting', 'gru', 'ensemble')),
    artifact_location text not null,
    feature_schema_hash text not null,
    target_contract jsonb not null,
    training_window jsonb not null,
    validation_window jsonb,
    metrics jsonb not null default '{}'::jsonb,
    parent_version_identifier text,
    lifecycle_status text not null default 'candidate'
        check (lifecycle_status in ('candidate', 'incumbent', 'rejected', 'archived')),
    created_at timestamptz not null default now(),
    promoted_at timestamptz,
    archived_at timestamptz
);

create table if not exists ml_decision_logs (
    id uuid primary key default gen_random_uuid(),
    decision_id text not null unique,
    decision_time timestamptz not null,
    symbol text not null,
    candle_interval text not null,
    market_mode text not null,
    action text not null check (action in ('enter', 'no_entry')),
    model_version_identifier text not null references ml_model_versions(version_identifier),
    decision_threshold numeric not null,
    model_probabilities jsonb not null,
    input_features jsonb not null,
    feature_schema_hash text not null,
    input_window_summary jsonb,
    outcome_status text not null default 'pending'
        check (outcome_status in ('pending', 'resolved', 'cancelled', 'invalid')),
    outcome_resolved_at timestamptz,
    target_horizon_bars integer not null,
    actual_return numeric,
    realized_pnl numeric,
    outcome_label boolean,
    outcome_metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    check (
        (outcome_status = 'pending' and outcome_resolved_at is null)
        or outcome_status in ('resolved', 'cancelled', 'invalid')
    )
);

create index if not exists idx_ml_decision_logs_pending_resolution
    on ml_decision_logs (outcome_status, decision_time);
create index if not exists idx_ml_decision_logs_model_time
    on ml_decision_logs (model_version_identifier, decision_time desc);
create index if not exists idx_ml_decision_logs_symbol_time
    on ml_decision_logs (symbol, decision_time desc);

create table if not exists ml_retraining_runs (
    id uuid primary key default gen_random_uuid(),
    run_identifier text not null unique,
    run_kind text not null check (run_kind in ('historical_simulation', 'future_offline_retraining')),
    incumbent_version_identifier text references ml_model_versions(version_identifier),
    candidate_version_identifier text references ml_model_versions(version_identifier),
    outcome_cutoff_at timestamptz not null,
    candidate_training_window jsonb not null,
    evaluation_window jsonb not null,
    resolved_outcome_count integer not null,
    incumbent_metrics jsonb not null,
    candidate_metrics jsonb not null,
    promotion_decision text not null check (promotion_decision in ('promoted', 'rejected', 'not_evaluated')),
    decision_rationale jsonb not null,
    created_at timestamptz not null default now()
);

create table if not exists ml_performance_observations (
    id uuid primary key default gen_random_uuid(),
    run_identifier text not null references ml_retraining_runs(run_identifier),
    model_version_identifier text not null references ml_model_versions(version_identifier),
    observation_start timestamptz not null,
    observation_end timestamptz not null,
    decision_count integer not null,
    resolved_count integer not null,
    win_rate numeric,
    average_pnl numeric,
    max_drawdown numeric,
    metrics jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    unique (run_identifier, model_version_identifier)
);

-- These records are system-owned and should only be written by trusted backend/service-role code.
alter table ml_model_versions enable row level security;
alter table ml_decision_logs enable row level security;
alter table ml_retraining_runs enable row level security;
alter table ml_performance_observations enable row level security;
