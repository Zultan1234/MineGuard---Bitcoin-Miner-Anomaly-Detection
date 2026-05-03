"""
Feature Engineering — Production Module
Mirrors notebook 02: derives domain features + rolling features for the
anomaly detection pipeline. Used by trainer.py before fitting/scoring.
"""
import numpy as np

# 8 domain features added on top of the raw cgminer fields
FEATURE_NAMES = [
    "hash_efficiency",
    "temp_differential",
    "chain_rate_imbalance",
    "voltage_imbalance",
    "total_active_chips",
    "hashrate_per_chip",
    "fan_avg",
    "temp_max_minus_avg",
]


def add_domain_features(reading: dict) -> dict:
    """
    Given a single reading dict, add the 8 derived domain features.
    Returns a new dict — input unchanged.
    Missing fields are tolerated (resulting feature simply not added).
    """
    out = dict(reading)

    def safe(key, default=0):
        v = reading.get(key, default)
        try: return float(v)
        except: return default

    # hash_efficiency: GHS per watt
    p = safe("chain_power")
    if p > 0:
        out["hash_efficiency"] = safe("GHS 5s") / p

    # temp_differential: chip exhaust mean - PCB inlet mean
    pcb_temps  = [safe(k) for k in ["temp1","temp2","temp3","temp4"] if k in reading]
    chip_temps = [safe(k) for k in ["temp2_1","temp2_2","temp2_3","temp2_4"] if k in reading]
    if pcb_temps and chip_temps:
        out["temp_differential"] = np.mean(chip_temps) - np.mean(pcb_temps)

    # chain_rate_imbalance: std/mean of per-board hashrates
    rates = [safe(k) for k in ["chain_rate1","chain_rate2","chain_rate3","chain_rate4"] if k in reading]
    if rates and np.mean(rates) > 0:
        out["chain_rate_imbalance"] = float(np.std(rates) / np.mean(rates))

    # voltage_imbalance: std of voltages
    volts = [safe(k) for k in ["voltage1","voltage2","voltage3","voltage4"] if k in reading]
    if volts:
        out["voltage_imbalance"] = float(np.std(volts))

    # total_active_chips
    chips = [safe(k) for k in ["chain_acn1","chain_acn2","chain_acn3","chain_acn4"] if k in reading]
    if chips:
        total = sum(chips)
        out["total_active_chips"] = total
        if total > 0:
            out["hashrate_per_chip"] = safe("GHS 5s") / total

    # fan_avg
    fans = [safe(k) for k in ["fan1","fan2"] if k in reading]
    if fans:
        out["fan_avg"] = float(np.mean(fans))

    # temp_max_minus_avg: hot-spot indicator
    if chip_temps and "temp_max" in reading:
        out["temp_max_minus_avg"] = safe("temp_max") - float(np.mean(chip_temps))

    return out


def add_rolling_features(readings: list[dict], window: int = 5) -> list[dict]:
    """
    Given a list of readings (chronological), add rolling-window stats for key features.
    Used during training only — at inference time we use a different code path.
    """
    if not readings: return []
    key = ["GHS 5s","temp_max","fan1","fan2","voltage1"]
    out = [dict(r) for r in readings]
    for f in key:
        history = []
        for i, r in enumerate(out):
            if f in r:
                history.append(float(r[f]))
                window_vals = history[-window:]
                roll_mean = np.mean(window_vals)
                roll_std  = np.std(window_vals) if len(window_vals) > 1 else 0.0
                r[f"{f}_roll_mean"] = float(roll_mean)
                r[f"{f}_roll_std"]  = float(roll_std)
                r[f"{f}_roc"]       = float((float(r[f]) - roll_mean) / roll_mean) if roll_mean != 0 else 0.0
    return out
