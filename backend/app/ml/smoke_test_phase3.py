"""Smoke-test the completed Phase 3 offline self-learning artifacts without exchange access."""

from __future__ import annotations

import json

from app.ml.learning_audit import DEFAULT_AUDIT_DB_PATH, LearningAuditStore
from app.ml.simulate_self_learning import SUMMARY_PATH


def main() -> None:
    if not DEFAULT_AUDIT_DB_PATH.is_file():
        raise FileNotFoundError("Phase 3 audit database is missing; run app.ml.simulate_self_learning first.")
    if not SUMMARY_PATH.is_file():
        raise FileNotFoundError("Phase 3 summary is missing; run app.ml.simulate_self_learning first.")
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    store = LearningAuditStore()
    decisions = store.export_table("decisions")
    outcomes = store.export_table("outcomes")
    retraining_runs = store.export_table("retraining_runs")
    if len(decisions) != len(outcomes) or len(decisions) == 0:
        raise AssertionError("Every simulated decision must have exactly one resolved outcome.")
    if len(retraining_runs) != summary["simulation"]["retraining_chunks"]:
        raise AssertionError("Retraining-run count does not match the documented chronological simulation.")
    if any(summary["scope"].lower().count(term) for term in ("deployment", "exchange", "order integration")):
        # These terms are allowed only as explicit exclusions in the scope statement.
        scope = summary["scope"].lower()
        if "no schedule, deployment, exchange, scanner, or order integration" not in scope:
            raise AssertionError("Phase 3 scope unexpectedly suggests a live integration.")
    if any(entry["bundle_promoted"] for entry in summary["promotions"]):
        raise AssertionError("The final anti-regression simulation must not promote a degraded bundle.")
    print(
        "Phase 3 smoke test passed: "
        f"{len(decisions):,} decisions, {len(outcomes):,} outcomes, "
        f"{len(retraining_runs)} retraining runs, no auto-promotion."
    )


if __name__ == "__main__":
    main()
