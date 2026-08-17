"""Versioned in-process scorer for the validated Phase 2 ensemble.

The API accepts already-prepared causal feature windows. It deliberately does not fetch market
candles or place orders; the existing signal-monitor process remains responsible for preparing
features from completed candles.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import torch

from app.core.config import settings
from app.ml.dataset import FEATURE_COLUMNS
from app.ml.sequence_predictor import load_gru_model

BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = BACKEND_DIR / "models" / "current" / "model_bundle.json"


@dataclass(frozen=True)
class EnsembleScore:
    entry_probability: float
    action: str
    decision_threshold: float
    model_version_identifier: str
    component_probabilities: dict[str, float]
    feature_schema_hash: str
    sequence_window_bars: int


class ModelBundle:
    """Load one immutable ensemble manifest and all referenced artifacts into process memory."""

    def __init__(self, manifest_path: Path = DEFAULT_MANIFEST) -> None:
        self.manifest_path = manifest_path
        self.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.version_identifier = str(self.manifest["version_identifier"])
        self.threshold = float(self.manifest.get("decision_threshold", 0.5))
        self.weights = {
            key: float(value) for key, value in self.manifest["ensemble_weights"].items()
        }
        if abs(sum(self.weights.values()) - 1.0) > 1e-6:
            raise ValueError("Model bundle ensemble weights must sum to 1.0.")

        self.feature_schema_hash = hashlib.sha256(
            ",".join(FEATURE_COLUMNS).encode("utf-8")
        ).hexdigest()
        self._load_artifacts()

    def _resolve(self, relative_path: str) -> Path:
        path = BACKEND_DIR / relative_path
        if not path.is_file():
            raise FileNotFoundError(f"Model bundle artifact not found: {path}")
        return path

    def _load_artifacts(self) -> None:
        paths = self.manifest["artifacts"]
        self.random_forest_artifact = joblib.load(self._resolve(paths["random_forest"]))
        self.gradient_boosting_artifact = joblib.load(self._resolve(paths["gradient_boosting"]))
        self.gru_model, self.gru_artifact = load_gru_model(self._resolve(paths["gru"]))

        for name, artifact in (
            ("random_forest", self.random_forest_artifact),
            ("gradient_boosting", self.gradient_boosting_artifact),
        ):
            columns = list(artifact.get("feature_columns", []))
            if columns != FEATURE_COLUMNS:
                raise ValueError(f"{name} artifact feature contract differs from Phase 1.")
        if list(self.gru_artifact.get("feature_columns", [])) != FEATURE_COLUMNS:
            raise ValueError("GRU artifact feature contract differs from Phase 1.")

    def health(self) -> dict[str, Any]:
        return {
            "ready": True,
            "version_identifier": self.version_identifier,
            "feature_schema_hash": self.feature_schema_hash,
            "sequence_window_bars": int(self.gru_artifact["sequence_window_bars"]),
        }

    def score(self, feature_window: list[list[float]]) -> EnsembleScore:
        """Score one causal window; the last row is the completed decision candle."""
        windows = np.asarray(feature_window, dtype=np.float32)
        expected_window = int(self.gru_artifact["sequence_window_bars"])
        expected_shape = (expected_window, len(FEATURE_COLUMNS))
        if windows.shape != expected_shape:
            raise ValueError(
                f"Expected feature_window shape {expected_shape}; received {tuple(windows.shape)}."
            )
        if not np.isfinite(windows).all():
            raise ValueError("feature_window contains non-finite values.")

        last_row = pd.DataFrame(windows[-1:, :], columns=FEATURE_COLUMNS)
        rf_probability = float(
            self.random_forest_artifact["model"].predict_proba(last_row)[:, 1][0]
        )
        gb_probability = float(
            self.gradient_boosting_artifact["model"].predict_proba(last_row)[:, 1][0]
        )

        standardized = (
            windows - self.gru_artifact["scaler_mean"]
        ) / self.gru_artifact["scaler_std"]
        with torch.no_grad():
            logits = self.gru_model(
                torch.from_numpy(standardized.astype(np.float32, copy=False))
            )
        # The saved GRU may return a scalar for one window or a one-element batch.
        gru_probability = float(torch.sigmoid(logits).detach().cpu().reshape(-1)[0].item())

        components = {
            "random_forest": rf_probability,
            "gradient_boosting": gb_probability,
            "gru": gru_probability,
        }
        ensemble_probability = float(
            sum(self.weights[name] * components[name] for name in components)
        )
        return EnsembleScore(
            entry_probability=ensemble_probability,
            action="enter" if ensemble_probability >= self.threshold else "no_entry",
            decision_threshold=self.threshold,
            model_version_identifier=self.version_identifier,
            component_probabilities=components,
            feature_schema_hash=self.feature_schema_hash,
            sequence_window_bars=expected_window,
        )


@lru_cache(maxsize=1)
def get_model_bundle() -> ModelBundle:
    """Load once per process; a new committed bundle is picked up on process restart."""
    manifest_path = BACKEND_DIR / settings.ml_model_bundle_path
    return ModelBundle(manifest_path)
