"""
Isolation Forest — clean rebuild.

No SHAP dependency. Feature attribution uses permutation importance
which works on ANY sklearn model, requires no extra install, and
gives reliable per-feature anomaly contribution.

When a reading is flagged as anomalous:
  For each feature, perturb it to its training mean.
  If the score drops significantly → that feature contributed to the anomaly.
  This is model-faithful (not z-score) and always works.
"""
import pickle, logging
import numpy as np
from pathlib import Path
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger("ml.isolation_forest")
MODELS_DIR = Path(__file__).parent.parent / "data" / "models"


class IsolationForestDetector:
    def __init__(self, miner_id: str):
        self.miner_id = miner_id
        self.model = None
        self.scaler = None
        self.feature_names = []
        self._threshold_yellow = 0.5
        self._threshold_red = 0.75
        self._score_min = 0.0
        self._score_max = 1.0
        self._is_trained = False
        self._train_means = None  # raw feature means from training

    @property
    def is_trained(self): return self._is_trained

    def train(self, readings: list[dict], contamination=0.05) -> dict:
        if not readings:
            raise ValueError("No training data")

        # Get features present in ALL readings
        common = set(readings[0].keys())
        for r in readings:
            common &= set(r.keys())
        self.feature_names = sorted(common)

        if len(self.feature_names) < 3:
            raise ValueError(f"Only {len(self.feature_names)} common features — need 3+")

        X = np.array([[r[f] for f in self.feature_names] for r in readings], dtype=float)
        self._train_means = X.mean(axis=0)

        self.scaler = StandardScaler()
        X_s = self.scaler.fit_transform(X)

        self.model = IsolationForest(
            n_estimators=200, contamination=contamination,
            random_state=42, n_jobs=-1)
        self.model.fit(X_s)
        self._is_trained = True

        # Score range from training for normalization
        raw = -self.model.decision_function(X_s)
        self._score_min = float(raw.min())
        self._score_max = float(raw.max())

        # Thresholds from training score distribution
        normed = self._norm_batch(raw)
        p95 = float(np.percentile(normed, 95))
        self._threshold_yellow = max(p95, 0.45)
        self._threshold_red = min(self._threshold_yellow + 0.25, 0.90)

        return {
            "n_samples": len(readings),
            "n_features": len(self.feature_names),
            "features": self.feature_names,
            "threshold_yellow": round(self._threshold_yellow, 4),
            "threshold_red": round(self._threshold_red, 4),
        }

    def score(self, values: dict) -> dict:
        if not self._is_trained:
            return self._empty()

        x = np.array([[values.get(f, 0.0) for f in self.feature_names]], dtype=float)
        x_s = self.scaler.transform(x)
        raw = float(-self.model.decision_function(x_s)[0])
        score = float(np.clip(self._norm_single(raw), 0, 1))

        if score >= self._threshold_red:     severity = "critical"
        elif score >= self._threshold_yellow: severity = "anomaly"
        else:                                 severity = "normal"

        is_anomaly = severity != "normal"

        # Feature attribution — ONLY for anomalies
        attributions = []
        if is_anomaly:
            attributions = self._feature_attribution(x, x_s, score)

        return {
            "anomaly_score": round(score, 4),
            "threshold_yellow": round(self._threshold_yellow, 4),
            "threshold_red": round(self._threshold_red, 4),
            "is_anomaly": is_anomaly,
            "severity": severity,
            "feature_attributions": attributions,
        }

    def _feature_attribution(self, x_raw, x_scaled, original_score) -> list:
        """
        Permutation-based attribution: for each feature, replace it with
        its training mean (in scaled space = 0). If the score drops,
        that feature was contributing to the anomaly.
        
        This is model-faithful, requires no extra packages, and always works.
        """
        attributions = []
        for i, fname in enumerate(self.feature_names):
            # Replace feature i with training mean (=0 in scaled space)
            x_perturbed = x_scaled.copy()
            x_perturbed[0, i] = 0.0  # training mean in scaled space

            raw_new = float(-self.model.decision_function(x_perturbed)[0])
            new_score = float(np.clip(self._norm_single(raw_new), 0, 1))

            # How much did the score drop when we "fixed" this feature?
            contribution = original_score - new_score  # positive = this feature caused anomaly

            raw_value = float(x_raw[0, i])
            train_mean = float(self._train_means[i])
            deviation = raw_value - train_mean
            pct_dev = (deviation / abs(train_mean) * 100) if train_mean != 0 else 0

            attributions.append({
                "feature": fname,
                "contribution": round(contribution, 4),
                "value": round(raw_value, 4),
                "baseline": round(train_mean, 4),
                "deviation": round(deviation, 4),
                "pct_deviation": round(pct_dev, 2),
                "direction": "anomaly" if contribution > 0.01 else "normal",
            })

        # Sort by contribution descending
        attributions.sort(key=lambda a: -a["contribution"])
        return attributions

    def _empty(self):
        return {"anomaly_score": 0.0, "is_anomaly": False, "severity": "normal",
                "feature_attributions": [],
                "threshold_yellow": 0.5, "threshold_red": 0.75}

    def _norm_batch(self, raw):
        mn, mx = raw.min(), raw.max()
        if mx == mn: return np.zeros_like(raw)
        return (raw - mn) / (mx - mn)

    def _norm_single(self, raw):
        if self._score_max == self._score_min: return 0.0
        return (raw - self._score_min) / (self._score_max - self._score_min)

    def save(self):
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        path = MODELS_DIR / f"if_{self.miner_id}.pkl"
        with open(path, "wb") as f:
            pickle.dump({
                "model": self.model, "scaler": self.scaler,
                "feature_names": self.feature_names,
                "threshold_yellow": self._threshold_yellow,
                "threshold_red": self._threshold_red,
                "score_min": self._score_min,
                "score_max": self._score_max,
                "train_means": self._train_means,
            }, f)
        return str(path)

    def load(self, path):
        try:
            with open(path, "rb") as f:
                d = pickle.load(f)
            self.model = d["model"]; self.scaler = d["scaler"]
            self.feature_names = d["feature_names"]
            self._threshold_yellow = d.get("threshold_yellow", 0.5)
            self._threshold_red = d.get("threshold_red", 0.75)
            self._score_min = d.get("score_min", 0.0)
            self._score_max = d.get("score_max", 1.0)
            self._train_means = d.get("train_means")
            self._is_trained = True
            return True
        except Exception as e:
            logger.error(f"Load failed: {e}")
            return False
