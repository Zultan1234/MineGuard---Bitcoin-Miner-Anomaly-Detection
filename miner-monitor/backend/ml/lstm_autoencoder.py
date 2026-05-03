"""
LSTM Autoencoder — Tier-2 Deep Anomaly Detection

Part B changes:
- Keeps existing aggregate score and thresholds UNCHANGED
- Adds per-feature MSE breakdown: which features are hardest to reconstruct?
- Returns top-k features (default 3) with error magnitude + rank
- All outputs JSON-serializable
"""
import pickle, logging
import numpy as np
from pathlib import Path
from typing import Optional

logger = logging.getLogger("ml.lstm_autoencoder")

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

MODELS_DIR = Path(__file__).parent.parent / "data" / "models"
WINDOW_SIZE = 30          # 30 timesteps × 30s polling = 15 minutes per window
STEP_SIZE   = 2           # slide window by 2 timesteps (1 minute) — reduces redundancy
MIN_TRAINING_WINDOWS = 50


class LSTMAutoencoder(nn.Module if TORCH_AVAILABLE else object):
    def __init__(self, input_size: int, hidden_size: int = 64, latent_size: int = 16):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch required")
        super().__init__()
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.latent_size = latent_size

        self.encoder_lstm1 = nn.LSTM(input_size, hidden_size, batch_first=True)
        self.encoder_lstm2 = nn.LSTM(hidden_size, hidden_size // 2, batch_first=True)
        self.encoder_linear = nn.Linear(hidden_size // 2, latent_size)

        self.decoder_linear = nn.Linear(latent_size, hidden_size // 2)
        self.decoder_lstm1 = nn.LSTM(hidden_size // 2, hidden_size, batch_first=True)
        self.decoder_lstm2 = nn.LSTM(hidden_size, input_size, batch_first=True)

    def forward(self, x):
        batch_size, seq_len, _ = x.shape
        enc1, _ = self.encoder_lstm1(x)
        enc2, _ = self.encoder_lstm2(enc1)
        context = self.encoder_linear(enc2[:, -1, :])
        dec_in = self.decoder_linear(context).unsqueeze(1).repeat(1, seq_len, 1)
        dec1, _ = self.decoder_lstm1(dec_in)
        dec2, _ = self.decoder_lstm2(dec1)
        return dec2


class LSTMDetector:
    def __init__(self, miner_id: str):
        self.miner_id = miner_id
        self.model: Optional["LSTMAutoencoder"] = None
        self.feature_names: list[str] = []
        self.feature_mean: Optional[np.ndarray] = None
        self.feature_std: Optional[np.ndarray] = None
        self._threshold: float = 0.5
        self._is_trained = False
        self._available = TORCH_AVAILABLE
        # Per-feature error baselines from training (for normalization)
        self._feature_error_mean: Optional[np.ndarray] = None
        self._feature_error_std:  Optional[np.ndarray] = None

    @property
    def is_trained(self) -> bool:
        return self._is_trained and self._available

    def train(self, readings: list[dict], epochs: int = 30, lr: float = 1e-3) -> dict:
        if not TORCH_AVAILABLE:
            return {"error": "PyTorch not available"}
        if not readings:
            raise ValueError("No training data")

        all_keys = set(readings[0].keys()) - {"timestamp"}
        for r in readings: all_keys &= set(r.keys())
        self.feature_names = sorted([k for k in all_keys if k != "timestamp"])
        if not self.feature_names:
            raise ValueError("No common features")

        X_raw = np.array([[r[f] for f in self.feature_names] for r in readings], dtype=np.float32)
        self.feature_mean = X_raw.mean(axis=0)
        self.feature_std = X_raw.std(axis=0) + 1e-9
        X = (X_raw - self.feature_mean) / self.feature_std

        windows = self._make_windows(X)
        if len(windows) < MIN_TRAINING_WINDOWS:
            return {"error": f"Need {MIN_TRAINING_WINDOWS} windows, got {len(windows)}"}

        input_size = len(self.feature_names)
        self.model = LSTMAutoencoder(input_size)
        optimizer = torch.optim.Adam(self.model.parameters(), lr=lr)
        criterion = nn.MSELoss()

        X_tensor = torch.FloatTensor(windows)
        dataset = TensorDataset(X_tensor, X_tensor)
        loader = DataLoader(dataset, batch_size=32, shuffle=True)

        self.model.train()
        train_losses = []
        best_loss = float("inf")
        patience = 5; no_improve = 0

        for epoch in range(epochs):
            epoch_loss = 0.0
            for batch_x, batch_y in loader:
                optimizer.zero_grad()
                output = self.model(batch_x)
                loss = criterion(output, batch_y)
                loss.backward(); optimizer.step()
                epoch_loss += loss.item()
            avg = epoch_loss / len(loader)
            train_losses.append(avg)
            if avg < best_loss - 1e-5:
                best_loss = avg; no_improve = 0
            else:
                no_improve += 1
                if no_improve >= patience: break

        # Aggregate threshold from training errors
        errors = self._compute_errors_aggregate(windows)
        self._threshold = float(np.percentile(errors, 95))

        # Per-feature error baseline — needed to normalize at inference
        per_feat_errors = self._compute_errors_per_feature(windows)
        self._feature_error_mean = per_feat_errors.mean(axis=0)
        self._feature_error_std  = per_feat_errors.std(axis=0) + 1e-9

        self._is_trained = True

        return {
            "n_samples":       len(readings),
            "n_windows":       len(windows),
            "n_features":      len(self.feature_names),
            "epochs_trained":  len(train_losses),
            "final_loss":      round(best_loss, 6),
            "threshold":       round(self._threshold, 6),
        }

    def score_window(self, recent_readings: list[dict]) -> dict:
        """
        Score the most recent window. Returns:
        - lstm_error: aggregate reconstruction error (unchanged)
        - is_anomaly: bool (unchanged threshold logic)
        - per_feature_error: top-k features with highest reconstruction error
        """
        if not self.is_trained:
            return {"lstm_error": 0.0, "is_anomaly": False, "available": False,
                    "per_feature_error": []}

        if len(recent_readings) < WINDOW_SIZE:
            return {"lstm_error": 0.0, "is_anomaly": False, "available": True,
                    "note": "Insufficient history", "per_feature_error": []}

        X_raw = np.array(
            [[r.get(f, 0.0) for f in self.feature_names]
             for r in recent_readings[-WINDOW_SIZE:]],
            dtype=np.float32)
        X = (X_raw - self.feature_mean) / self.feature_std
        window = X[np.newaxis, :, :]

        # Aggregate error (existing logic — UNCHANGED)
        agg_errors = self._compute_errors_aggregate(window)
        error = float(agg_errors[0])

        # Per-feature error breakdown (NEW — Part B)
        per_feat = self._compute_per_feature_breakdown(window)

        return {
            "lstm_error":         round(error, 6),
            "threshold":          round(self._threshold, 6),
            "is_anomaly":         error > self._threshold,
            "available":          True,
            "per_feature_error":  per_feat,
        }

    def _compute_per_feature_breakdown(self, window: np.ndarray, top_k: int = 5) -> list[dict]:
        """
        Compute per-feature MSE over the time window.
        Normalize against training error baseline.
        Return top-k features with highest error relative to their training baseline.
        """
        if self.model is None or self._feature_error_mean is None:
            return []
        try:
            self.model.eval()
            with torch.no_grad():
                t = torch.FloatTensor(window)
                out = self.model(t)
                # Per-feature MSE averaged over time: shape (n_features,)
                per_feat_mse = ((t - out) ** 2).mean(dim=1).squeeze(0).numpy()

            # Normalize: how many training-stds above training-mean is this error?
            normalized = (per_feat_mse - self._feature_error_mean) / self._feature_error_std

            features = []
            for i, feat in enumerate(self.feature_names):
                features.append({
                    "feature":          feat,
                    "error":            round(float(per_feat_mse[i]), 6),
                    "error_normalized": round(float(normalized[i]), 4),
                    "rank":             0,  # set below
                })

            # Sort by normalized error descending
            features.sort(key=lambda f: -f["error_normalized"])
            for rank, f in enumerate(features):
                f["rank"] = rank + 1

            return features[:top_k]
        except Exception as e:
            logger.warning(f"Per-feature LSTM error failed: {e}")
            return []

    def _make_windows(self, X: np.ndarray) -> np.ndarray:
        """Create sliding windows with step size 2 to reduce redundancy."""
        n = len(X)
        if n < WINDOW_SIZE: return np.array([])
        return np.array([X[i:i+WINDOW_SIZE]
                         for i in range(0, n - WINDOW_SIZE + 1, STEP_SIZE)])

    def _compute_errors_aggregate(self, windows: np.ndarray) -> np.ndarray:
        """Aggregate MSE per window (existing logic)."""
        self.model.eval()
        with torch.no_grad():
            t = torch.FloatTensor(windows)
            out = self.model(t)
            errors = ((t - out) ** 2).mean(dim=(1, 2)).numpy()
        return errors

    def _compute_errors_per_feature(self, windows: np.ndarray) -> np.ndarray:
        """Per-feature MSE for each window: shape (n_windows, n_features)."""
        self.model.eval()
        with torch.no_grad():
            t = torch.FloatTensor(windows)
            out = self.model(t)
            # (n_windows, window_size, n_features) -> mean over time -> (n_windows, n_features)
            per_feat = ((t - out) ** 2).mean(dim=1).numpy()
        return per_feat

    def save(self) -> str:
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        path = MODELS_DIR / f"lstm_{self.miner_id}.pkl"
        state = self.model.state_dict() if self.model else None
        with open(path, "wb") as f:
            pickle.dump({
                "model_state":        state,
                "feature_names":      self.feature_names,
                "feature_mean":       self.feature_mean,
                "feature_std":        self.feature_std,
                "threshold":          self._threshold,
                "input_size":         len(self.feature_names),
                "feature_error_mean": self._feature_error_mean,
                "feature_error_std":  self._feature_error_std,
            }, f)
        return str(path)

    def load(self, path: str) -> bool:
        if not TORCH_AVAILABLE: return False
        try:
            with open(path, "rb") as f: data = pickle.load(f)
            self.feature_names      = data["feature_names"]
            self.feature_mean       = data["feature_mean"]
            self.feature_std        = data["feature_std"]
            self._threshold         = data["threshold"]
            self._feature_error_mean = data.get("feature_error_mean")
            self._feature_error_std  = data.get("feature_error_std")
            self.model = LSTMAutoencoder(data["input_size"])
            self.model.load_state_dict(data["model_state"])
            self.model.eval()
            self._is_trained = True
            return True
        except Exception as e:
            logger.error(f"Failed to load LSTM model: {e}")
            return False
