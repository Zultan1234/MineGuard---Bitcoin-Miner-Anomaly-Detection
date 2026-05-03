"""
Production preprocessor.
Wraps StandardScaler + handles missing features gracefully.
"""
import numpy as np
from sklearn.preprocessing import StandardScaler


class RobustPreprocessor:
    """
    Handles:
    - Consistent feature ordering
    - Missing feature -> zero (after scaling, becomes mean)
    - StandardScaler fit only on normal data
    - Stable transform at inference time
    """

    def __init__(self):
        self.scaler: StandardScaler | None = None
        self.feature_names: list[str] = []

    def fit(self, readings: list[dict], feature_names: list[str]):
        self.feature_names = feature_names
        X = np.array([[float(r.get(f, 0.0)) for f in feature_names] for r in readings])
        self.scaler = StandardScaler()
        self.scaler.fit(X)
        return self

    def transform(self, reading: dict) -> np.ndarray:
        if not self.scaler: raise RuntimeError("Preprocessor not fitted")
        x = np.array([[float(reading.get(f, 0.0)) for f in self.feature_names]])
        return self.scaler.transform(x)

    def transform_batch(self, readings: list[dict]) -> np.ndarray:
        if not self.scaler: raise RuntimeError("Preprocessor not fitted")
        X = np.array([[float(r.get(f, 0.0)) for f in self.feature_names] for r in readings])
        return self.scaler.transform(X)
