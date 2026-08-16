"""Smoke-test the Phase 2 GRU artifact-loading contract."""

from __future__ import annotations

import numpy as np

from app.core.config import settings
from app.ml.sequence_data import build_sequence_data
from app.ml.sequence_predictor import load_gru_model, predict_sequence_probabilities


def main() -> None:
    data = build_sequence_data()
    window = settings.ml_sequence_window_bars
    samples: list[np.ndarray] = []
    for symbol_index, end_index in data.validation.endpoints[:5]:
        series = data.series_by_symbol[data.symbols[int(symbol_index)]]
        samples.append(series.features[end_index - window + 1 : end_index + 1])
    model, artifact = load_gru_model()
    probabilities = predict_sequence_probabilities(np.stack(samples), model, artifact)
    if len(probabilities) != len(samples) or not np.isfinite(probabilities).all():
        raise AssertionError("GRU smoke-test output is not finite or does not match input rows.")
    if not np.all((probabilities >= 0.0) & (probabilities <= 1.0)):
        raise AssertionError("GRU probability output falls outside [0, 1].")
    print(
        f"Loaded {artifact['architecture']} ({artifact['horizon_bars']} bars); "
        f"scored {len(samples)} rolling windows."
    )


if __name__ == "__main__":
    main()
