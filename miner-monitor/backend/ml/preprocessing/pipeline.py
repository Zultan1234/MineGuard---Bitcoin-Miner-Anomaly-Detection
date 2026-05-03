"""
Automatic Preprocessing Pipeline
Mirrors the logic from notebooks 01_eda and 02_preprocessing_and_features.

This runs automatically when the user clicks "Train Now" — no manual steps needed.

Steps (from the notebooks):
1. Startup transient removal — trim first N readings where Device Rejected% is settling
2. Zero-variance feature removal — drop features constant across all readings
3. Redundant feature reduction — drop features with |corr| > 0.95 (keep one from each pair)
4. Counter-to-delta conversion — Hardware Errors, chain_hw, etc. become rate-of-change
5. Domain feature engineering — thermal_ratio, board_imbalance, chip_temp_delta, fan_temp_ratio
6. Scaling — RobustScaler (resistant to outliers in the training data)

Output: a clean feature matrix ready for Isolation Forest and LSTM Autoencoder.
"""
import logging
import numpy as np
import pandas as pd
from typing import Optional
from sklearn.preprocessing import RobustScaler

logger = logging.getLogger("preprocessing")

# Counter features that are cumulative (always increasing)
COUNTER_FEATURES = {
    "Hardware Errors", "chain_hw1", "chain_hw2", "chain_hw3", "chain_hw4",
    "no_matching_work", "Accepted", "Rejected", "Discarded",
    "Device Hardware%",
}

# Features that are always constant on a given miner and should be dropped
ALWAYS_SKIP = {"miner_count", "fan_num", "temp_num", "frequency"}

# Known redundant pairs — when both present, drop the second
# (from notebook 02 correlation analysis: |r| > 0.95)
REDUNDANT_PAIRS = [
    ("GHS av", "GHS 5s"),          # GHS av tracks GHS 5s closely
    ("temp_max", "temp2_4"),       # temp_max is always max(temp2_1..4)
    ("no_matching_work", "Hardware Errors"),  # correlated counters
]


class AutoPreprocessor:
    """
    Stateful preprocessor — fitted during training, applied during inference.
    Stores the fitted scaler, feature list, and baseline stats.
    """

    def __init__(self):
        self.scaler: Optional[RobustScaler] = None
        self.feature_names: list[str] = []
        self.dropped_features: list[str] = []
        self.baseline_means: dict[str, float] = {}
        self.baseline_stds: dict[str, float] = {}
        self._fitted = False

    @property
    def is_fitted(self):
        return self._fitted

    def fit_transform(self, readings: list[dict], trim_startup: bool = True) -> tuple[np.ndarray, list[str]]:
        """
        Full preprocessing pipeline on a list of reading dicts.
        Returns (X_scaled, feature_names).

        Steps:
        1. Convert to DataFrame
        2. Trim startup transient
        3. Drop constant features
        4. Convert counters to deltas
        5. Add engineered features
        6. Drop redundant features
        7. Fit RobustScaler
        """
        if not readings:
            raise ValueError("No readings to preprocess")

        # ── Step 1: to DataFrame ──────────────────────────────────────────
        df = pd.DataFrame(readings)
        logger.info(f"Preprocessing {len(df)} readings, {df.shape[1]} columns")

        # Drop timestamp and internal flags
        meta_cols = [c for c in df.columns if c in ("timestamp",) or c.startswith("_")]
        df = df.drop(columns=[c for c in meta_cols if c in df.columns], errors="ignore")

        # Keep only numeric columns
        df = df.select_dtypes(include=[np.number])

        # ── Step 2: Trim startup transient ───────────────────────────────
        if trim_startup and len(df) > 50:
            # Check if Device Rejected% shows startup decay
            if "Device Rejected%" in df.columns:
                dr = df["Device Rejected%"]
                early_mean = dr.iloc[:20].mean() if len(dr) > 20 else 0
                late_mean  = dr.iloc[-20:].mean() if len(dr) > 20 else 0
                if early_mean > late_mean * 2 and early_mean > 10:
                    # Find where it stabilizes (drops below 2x the steady-state)
                    threshold = late_mean * 2
                    stable_start = 0
                    for i in range(len(dr)):
                        if dr.iloc[i] < threshold:
                            stable_start = i
                            break
                    if stable_start > 10:
                        logger.info(f"Trimmed {stable_start} startup rows (Device Rejected% settling)")
                        df = df.iloc[stable_start:].reset_index(drop=True)

        # ── Step 3: Drop constant features ───────────────────────────────
        variances = df.var()
        zero_var = variances[variances == 0].index.tolist()
        skip_cols = [c for c in df.columns if c in ALWAYS_SKIP]
        drop_cols = list(set(zero_var + skip_cols))
        if drop_cols:
            logger.info(f"Dropping {len(drop_cols)} constant/skip columns: {drop_cols[:8]}")
            df = df.drop(columns=drop_cols, errors="ignore")

        # ── Step 4: Counter-to-delta ──────────────────────────────────────
        for col in COUNTER_FEATURES:
            if col in df.columns:
                raw = df[col].values
                delta = np.diff(raw, prepend=raw[0])
                delta = np.maximum(delta, 0)  # handle resets
                df[col] = delta

        # ── Step 5: Domain features ──────────────────────────────────────
        df = self._add_engineered_features(df)

        # ── Step 6: Drop redundant pairs ──────────────────────────────────
        for drop_col, keep_col in REDUNDANT_PAIRS:
            if drop_col in df.columns and keep_col in df.columns:
                corr = df[drop_col].corr(df[keep_col])
                if abs(corr) > 0.90:
                    df = df.drop(columns=[drop_col])
                    logger.info(f"Dropped redundant: {drop_col} (r={corr:.3f} with {keep_col})")

        # Also drop any remaining pairs with |r| > 0.95
        if df.shape[1] > 2:
            corr_matrix = df.corr().abs()
            to_drop = set()
            for i in range(len(corr_matrix.columns)):
                for j in range(i+1, len(corr_matrix.columns)):
                    if corr_matrix.iloc[i, j] > 0.95:
                        # Drop the one with lower mean variance contribution
                        col_i, col_j = corr_matrix.columns[i], corr_matrix.columns[j]
                        if col_j not in to_drop and col_i not in to_drop:
                            to_drop.add(col_j)
            if to_drop:
                logger.info(f"Dropping {len(to_drop)} highly correlated features: {to_drop}")
                df = df.drop(columns=list(to_drop), errors="ignore")

        # ── Step 7: Final cleanup ─────────────────────────────────────────
        # Drop any remaining NaN columns
        df = df.dropna(axis=1, how="all")
        # Fill remaining NaN with column median
        df = df.fillna(df.median())

        self.feature_names = list(df.columns)
        self.dropped_features = drop_cols

        # Compute baseline stats BEFORE scaling
        self.baseline_means = {col: float(df[col].mean()) for col in self.feature_names}
        self.baseline_stds  = {col: float(df[col].std())  for col in self.feature_names}

        # ── Step 8: RobustScaler ──────────────────────────────────────────
        self.scaler = RobustScaler()
        X = self.scaler.fit_transform(df.values)
        self._fitted = True

        logger.info(
            f"Preprocessing complete: {X.shape[0]} samples × {X.shape[1]} features. "
            f"Features: {self.feature_names[:6]}..."
        )
        return X, self.feature_names

    def transform(self, reading: dict) -> np.ndarray:
        """Transform a single reading dict using the fitted pipeline."""
        if not self._fitted:
            raise RuntimeError("Preprocessor not fitted — run fit_transform first")
        x = np.array([[float(reading.get(f, 0.0)) for f in self.feature_names]])
        return self.scaler.transform(x)

    def transform_batch(self, readings: list[dict]) -> np.ndarray:
        """Transform a list of reading dicts."""
        if not self._fitted:
            raise RuntimeError("Preprocessor not fitted")
        X = np.array([[float(r.get(f, 0.0)) for f in self.feature_names] for r in readings])
        return self.scaler.transform(X)

    def get_baseline(self) -> dict:
        """Return baseline stats per feature (for safety_rules deviation checks)."""
        baseline = {}
        for f in self.feature_names:
            baseline[f] = {
                "mean": self.baseline_means.get(f, 0),
                "std":  self.baseline_stds.get(f, 0),
            }
        return baseline

    def _add_engineered_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add domain features from notebook 02:
        - board_imbalance: how unevenly the 4 boards hash
        - thermal_ratio: hashrate / mean chip temp (efficiency proxy)
        - fan_temp_ratio: fan RPM / chip temp (cooling effectiveness)
        - chip_temp_delta_1..4: chip exhaust - PCB inlet per board
        """
        # Board imbalance
        rate_cols = [c for c in ["chain_rate1","chain_rate2","chain_rate3","chain_rate4"] if c in df.columns]
        if len(rate_cols) >= 2:
            rates = df[rate_cols]
            board_mean = rates.mean(axis=1)
            board_std  = rates.std(axis=1)
            df["board_imbalance"] = board_std / board_mean.replace(0, np.nan)
            df["board_imbalance"] = df["board_imbalance"].fillna(0)

        # Thermal ratio
        chip_cols = [c for c in ["temp2_1","temp2_2","temp2_3","temp2_4"] if c in df.columns]
        if chip_cols and "GHS 5s" in df.columns:
            mean_chip_temp = df[chip_cols].mean(axis=1)
            df["thermal_ratio"] = df["GHS 5s"] / mean_chip_temp.replace(0, np.nan)
            df["thermal_ratio"] = df["thermal_ratio"].fillna(0)

        # Fan-temperature ratio
        fan_cols = [c for c in ["fan1","fan2"] if c in df.columns]
        if fan_cols and chip_cols:
            mean_fan  = df[fan_cols].mean(axis=1)
            mean_chip = df[chip_cols].mean(axis=1)
            df["fan_temp_ratio"] = mean_fan / mean_chip.replace(0, np.nan)
            df["fan_temp_ratio"] = df["fan_temp_ratio"].fillna(0)

        # Per-board chip-to-PCB temperature delta
        pcb_chip_pairs = {
            "temp2_1": "temp1",
            "temp2_3": "temp3",
            "temp2_4": "temp4",
        }
        for chip_col, pcb_col in pcb_chip_pairs.items():
            if chip_col in df.columns and pcb_col in df.columns:
                board_num = chip_col[-1]
                df[f"chip_temp_delta_{board_num}"] = df[chip_col] - df[pcb_col]

        return df
