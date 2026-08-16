"""Offline loading interface for the Phase 2 GRU entry-classification artifact.

This module deliberately accepts already-prepared causal feature windows. It does not fetch
market data, invoke the scanner, or place orders; those activities are outside Phase 2 scope.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch

from app.ml.train_sequence_ensemble import GRUEntryClassifier

BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_ARTIFACT_PATH = BACKEND_DIR / "models" / "phase2" / "gru_4bars.pt"


def load_gru_model(artifact_path: Path = DEFAULT_ARTIFACT_PATH) -> tuple[GRUEntryClassifier, dict]:
    """Load the Phase 2 GRU and its preprocessing contract on CPU."""
    if not artifact_path.is_file():
        raise FileNotFoundError(
            f"GRU artifact not found at {artifact_path}. Run app.ml.train_sequence_ensemble first."
        )
    artifact = torch.load(artifact_path, map_location="cpu", weights_only=False)
    model = GRUEntryClassifier(
        feature_count=len(artifact["feature_columns"]), hidden_size=artifact["hidden_size"]
    )
    model.load_state_dict(artifact["model_state_dict"])
    model.eval()
    return model, artifact


def predict_sequence_probabilities(
    feature_windows: np.ndarray,
    model: GRUEntryClassifier | None = None,
    artifact: dict | None = None,
) -> np.ndarray:
    """Return entry probabilities for causal windows shaped [samples, window, features].

    The function validates the exact artifact window/feature contract and refuses missing or
    non-finite data. The returned probabilities are research scores, not execution instructions.
    """
    if model is None or artifact is None:
        model, artifact = load_gru_model()
    windows = np.asarray(feature_windows, dtype=np.float32)
    expected_shape = (
        int(artifact["sequence_window_bars"]),
        len(artifact["feature_columns"]),
    )
    if windows.ndim != 3 or tuple(windows.shape[1:]) != expected_shape:
        raise ValueError(
            "Expected feature windows shaped [samples, "
            f"{expected_shape[0]}, {expected_shape[1]}], got {tuple(windows.shape)}."
        )
    if not np.isfinite(windows).all():
        raise ValueError("Cannot score feature windows with non-finite values.")
    standardized = (windows - artifact["scaler_mean"]) / artifact["scaler_std"]
    with torch.no_grad():
        logits = model(torch.from_numpy(standardized.astype(np.float32, copy=False)))
    return torch.sigmoid(logits).cpu().numpy()
