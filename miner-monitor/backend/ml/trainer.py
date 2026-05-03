"""
ML Trainer — 29-feature pipeline.

Features:
  14 raw instantaneous (hashrate, temps, fans, per-board rates)
  15 derived (error rates as deltas, board deviations, thermal ratios)

NO cumulative counters. NO startup-decay fields. NO pool metadata.
"""
import logging
import numpy as np
from datetime import datetime, timezone
from backend.ml.isolation_forest import IsolationForestDetector
from backend.ml.lstm_autoencoder import LSTMDetector
from backend.ml.baseline import compute_baseline, deviation_report
from backend.ml.explainer import explainer
from backend.ml.feature_config import CORE_RAW_FEATURES, ALL_FEATURES

logger = logging.getLogger("ml.trainer")

_if_models:  dict = {}
_lstm_models: dict = {}
_baselines:  dict = {}


def get_if_model(mid):   return _if_models.get(mid)
def get_lstm_model(mid):  return _lstm_models.get(mid)
def get_baseline(mid):   return _baselines.get(mid)


def _enrich(reading: dict, prev_reading: dict = None) -> dict:
    """
    Compute all 29 ML features from a raw cgminer reading.
    14 raw instantaneous + 15 derived.
    prev_reading needed for HW error rate (delta between readings).
    """
    out = {}

    def s(key, default=0.0):
        try: return float(reading.get(key, default))
        except: return default

    # ── 14 raw instantaneous fields ──────────────────────────────────────
    for f in CORE_RAW_FEATURES:
        if f in reading:
            try: out[f] = float(reading[f])
            except: pass

    # ── 4 rate features (delta from previous reading) ────────────────────
    # These convert cumulative HW error counters into per-interval rates.
    # Raw "Hardware Errors" = 500 is meaningless. But if it was 490 last
    # interval and 500 now, the RATE is 10 errors/interval — that's useful.
    rate_fields = [
        ("Hardware Errors", "Hardware Errors_rate"),
        ("chain_hw1",       "chain_hw1_rate"),
        ("chain_hw2",       "chain_hw2_rate"),
        ("chain_hw3",       "chain_hw3_rate"),
    ]
    if prev_reading:
        for raw_key, rate_name in rate_fields:
            curr = s(raw_key)
            try: prev = float(prev_reading.get(raw_key, 0) or 0)
            except: prev = 0.0
            delta = curr - prev
            out[rate_name] = max(0.0, delta)  # never negative (handles restarts)
    else:
        for _, rate_name in rate_fields:
            out[rate_name] = 0.0

    # ── 4 per-board hashrate deviations ──────────────────────────────────
    # How far each board is from the average of all 4 boards.
    # Healthy: all ~0. Failing board: one is negative, others positive.
    rates = [out.get(f"chain_rate{i}", 0) for i in range(1, 5)]
    mean_rate = float(np.mean(rates)) if rates else 1.0
    for i in range(1, 5):
        r = out.get(f"chain_rate{i}", 0)
        out[f"chain_dev{i}"] = (r - mean_rate) / max(mean_rate, 0.01)

    # ── board_imbalance ──────────────────────────────────────────────────
    # std of board hashrates / mean. 0 = perfectly balanced. High = one failing.
    out["board_imbalance"] = float(np.std(rates) / max(mean_rate, 0.01))

    # ── thermal_ratio ────────────────────────────────────────────────────
    # max chip temp / mean chip temp. ~1.0 = even heating. >1.1 = hot spot.
    chip_temps = [out.get(f"temp2_{i}", 0) for i in range(1, 5)]
    chip_temps = [t for t in chip_temps if t > 0]
    if chip_temps:
        mean_chip = float(np.mean(chip_temps))
        out["thermal_ratio"] = float(max(chip_temps) / max(mean_chip, 1.0))
    else:
        out["thermal_ratio"] = 1.0

    # ── fan_temp_ratio ───────────────────────────────────────────────────
    # mean fan RPM / max chip temp. Drops when cooling can't keep up.
    fan_mean = float(np.mean([out.get("fan1", 0), out.get("fan2", 0)]))
    max_chip = max(chip_temps) if chip_temps else 1.0
    out["fan_temp_ratio"] = fan_mean / max(max_chip, 1.0)

    # ── 4 chip-PCB deltas ────────────────────────────────────────────────
    # chip temp - PCB temp for each board. Shows heat transfer efficiency.
    # Large gap = poor thermal interface or damaged heat sink.
    pcb_map = {1: "temp1", 2: "temp2", 3: "temp3", 4: "temp4"}
    for i in range(1, 5):
        chip_t = out.get(f"temp2_{i}", 0)
        pcb_t = s(pcb_map.get(i, f"temp{i}"))
        out[f"chip_pcb_delta{i}"] = chip_t - pcb_t

    return out


def _drop_constants(readings: list[dict]) -> tuple[list[dict], list[str], list[str]]:
    """Remove features with zero variance (constant for this miner)."""
    if not readings: return [], [], []
    common = set(readings[0].keys())
    for r in readings: common &= set(r.keys())
    features = sorted(common)
    X = np.array([[r.get(f, 0) for f in features] for r in readings])
    kept, dropped = [], []
    for i, f in enumerate(features):
        if np.std(X[:, i]) > 1e-9: kept.append(f)
        else: dropped.append(f)
    filtered = [{f: r[f] for f in kept if f in r} for r in readings]
    return filtered, kept, dropped


def train_models(miner_id: str, readings: list[dict]) -> dict:
    """Train on the 29-feature set with previous-reading rate computation."""
    if not readings:
        return {"error": "No readings provided"}
    logger.info(f"Training {miner_id} on {len(readings)} samples")

    # Step 1: enrich each reading (pass previous for rate computation)
    enriched = []
    for i, r in enumerate(readings):
        prev = readings[i - 1] if i > 0 else None
        enriched.append(_enrich(r, prev))

    # Step 2: drop any features constant for THIS miner
    filtered, kept, dropped_const = _drop_constants(enriched)

    if len(kept) < 5:
        return {"error": f"Only {len(kept)} features with variance. Need temps and hashrates."}
    if len(filtered) < 30:
        return {"error": f"Only {len(filtered)} readings after filtering. Need 30+."}

    logger.info(f"  Features: {len(kept)} kept, {len(dropped_const)} dropped (constant)")
    if dropped_const:
        logger.info(f"  Dropped: {dropped_const}")

    # Step 3: baseline
    baseline = compute_baseline(filtered)
    _baselines[miner_id] = baseline

    # Step 4: Isolation Forest
    if_model = IsolationForestDetector(miner_id)
    if_result = if_model.train(filtered)
    if_path = if_model.save()
    _if_models[miner_id] = if_model
    logger.info(f"  IF: {if_result['n_features']} features, "
                f"yellow@{if_result['threshold_yellow']:.3f}, "
                f"red@{if_result['threshold_red']:.3f}")

    # Step 5: LSTM
    lstm_model = LSTMDetector(miner_id)
    lstm_result = lstm_model.train(filtered)
    lstm_path = None
    if "error" not in lstm_result:
        lstm_path = lstm_model.save()
        _lstm_models[miner_id] = lstm_model
        logger.info(f"  LSTM: {lstm_result['n_windows']} windows, "
                     f"threshold={lstm_result['threshold']:.6f}")
    else:
        logger.info(f"  LSTM: {lstm_result.get('error')}")

    return {
        "miner_id": miner_id,
        "isolation_forest": if_result,
        "lstm_autoencoder": lstm_result,
        "baseline_features": list(baseline.keys()),
        "if_model_path": if_path,
        "lstm_model_path": lstm_path,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "feature_selection": {
            "input": len(ALL_FEATURES),
            "kept": kept,
            "dropped_constant": dropped_const,
        },
    }


def score_reading(miner_id: str, current_values: dict, recent_window: list) -> dict:
    """Score a single reading. Passes previous reading for rate computation."""
    if_model = _if_models.get(miner_id)
    lstm_model = _lstm_models.get(miner_id)
    baseline = _baselines.get(miner_id, {})

    # Enrich current reading (use last window reading as prev for rates)
    prev = recent_window[-1] if recent_window else None
    current = _enrich(current_values, prev)

    # Enrich window (each reading uses its predecessor)
    window = []
    for i, r in enumerate(recent_window):
        p = recent_window[i - 1] if i > 0 else None
        window.append(_enrich(r, p))

    # IF scoring
    if if_model and if_model.is_trained:
        if_result = if_model.score(current)
    else:
        if_result = {"anomaly_score": 0.0, "is_anomaly": False, "severity": "normal",
                     "feature_attributions": [], "threshold_yellow": 0.5, "threshold_red": 0.75}

    # LSTM scoring
    if lstm_model and lstm_model.is_trained:
        lstm_result = lstm_model.score_window(window)
    else:
        lstm_result = {"lstm_error": 0.0, "is_anomaly": False, "available": False,
                       "per_feature_error": []}

    # Fusion explanation
    explanation = explainer.explain(if_result, lstm_result, baseline, top_k=5)

    # Deviation report for dashboard display
    deviations = deviation_report(current, baseline)

    # ML status from severity
    severity = if_result.get("severity", "normal")
    ml_anomaly = if_result["is_anomaly"] or lstm_result.get("is_anomaly", False)

    if severity == "critical":                     ml_status = "RED"
    elif severity == "anomaly" or ml_anomaly:       ml_status = "YELLOW"
    else:                                           ml_status = "GREEN"

    return {
        "isolation_forest": if_result,
        "lstm": lstm_result,
        "explanation": explanation,
        "deviations": deviations,
        "ml_anomaly": ml_anomaly,
        "ml_status": ml_status,
        "severity": severity,
        "models_trained": if_model is not None and if_model.is_trained,
    }


def import_model(miner_id, model_path, baseline_data=None):
    m = IsolationForestDetector(miner_id)
    if not m.load(model_path): return False
    _if_models[miner_id] = m
    if baseline_data: _baselines[miner_id] = baseline_data
    return True


def load_saved_models(miner_id, if_path, lstm_path=None):
    loaded = False
    m = IsolationForestDetector(miner_id)
    if m.load(if_path): _if_models[miner_id] = m; loaded = True
    if lstm_path:
        l = LSTMDetector(miner_id)
        if l.load(lstm_path): _lstm_models[miner_id] = l
    return loaded
