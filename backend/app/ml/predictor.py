"""Offline loading interface for the selected Phase 1 entry-signal artifact.

This module accepts already-computed causal features.  It deliberately does not call Binance,
submit orders, or connect to the scanner; live integration remains outside Phase 1 scope.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_DIR = BACKEND_DIR / "models" / "phase1"


def load_selected_model(model_dir: Path = DEFAULT_MODEL_DIR) -> dict[str, Any]:
    """Load the selected Phase 1 artifact and verify its recorded selection metadata exists."""
    selection_path = model_dir / "selected_model.json"
    if not selection_path.is_file():
        raise FileNotFoundError(
            f"Selected-model manifest not found at {selection_path}. Run app.ml.train_baselines first."
        )
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    relative_artifact_path = selection["selected_candidate"]["artifact_path"]
    artifact_path = BACKEND_DIR / relative_artifact_path
    if not artifact_path.is_file():
        raise FileNotFoundError(f"Selected model artifact not found at {artifact_path}.")
    artifact = joblib.load(artifact_path)
    artifact["selection"] = selection
    return artifact


def predict_entry_probabilities(
    features: pd.DataFrame,
    artifact: dict[str, Any] | None = None,
) -> pd.Series:
    """Return long-entry probabilities in artifact-defined feature order.

    The caller is responsible for constructing features only from completed candles.  The output
    is not an execution instruction and must not be wired to trading without a later validation
    and integration phase.
    """
    artifact = artifact or load_selected_model()
    required_columns = artifact["feature_columns"]
    missing_columns = sorted(set(required_columns).difference(features.columns))
    if missing_columns:
        raise ValueError(f"Cannot score features; required columns are missing: {', '.join(missing_columns)}")
    if features[required_columns].isna().any().any():
        raise ValueError("Cannot score features containing missing values.")
    probabilities = artifact["model"].predict_proba(features[required_columns])[:, 1]
    return pd.Series(probabilities, index=features.index, name="entry_probability")


def predict_entry_signals(
    features: pd.DataFrame,
    artifact: dict[str, Any] | None = None,
) -> pd.Series:
    """Apply the recorded decision threshold to probabilities for a later offline consumer."""
    artifact = artifact or load_selected_model()
    probabilities = predict_entry_probabilities(features, artifact)
    return (probabilities >= artifact["decision_threshold"]).rename("entry_signal")
