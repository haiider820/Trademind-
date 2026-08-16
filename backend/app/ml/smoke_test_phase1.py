"""Smoke-test the Phase 1 selected-model loading contract."""

from __future__ import annotations

import pandas as pd

from app.ml.dataset import FEATURE_COLUMNS, PROCESSED_DATA_PATH
from app.ml.predictor import load_selected_model, predict_entry_probabilities, predict_entry_signals


def main() -> None:
    artifact = load_selected_model()
    sample = pd.read_parquet(PROCESSED_DATA_PATH, columns=FEATURE_COLUMNS).tail(5)
    probabilities = predict_entry_probabilities(sample, artifact)
    signals = predict_entry_signals(sample, artifact)
    if len(probabilities) != len(sample) or len(signals) != len(sample):
        raise AssertionError("Scoring output length does not match input feature rows.")
    if not probabilities.between(0.0, 1.0).all():
        raise AssertionError("Model probabilities fall outside [0, 1].")
    print(
        f"Loaded {artifact['model_name']} ({artifact['horizon_bars']} bars); "
        f"scored {len(sample)} feature rows at threshold {artifact['decision_threshold']:.2f}."
    )


if __name__ == "__main__":
    main()
