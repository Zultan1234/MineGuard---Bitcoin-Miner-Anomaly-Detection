"""
Baseline Statistics
Computed during the calibration/learning phase.
Provides simple statistical bounds for the anomaly scorer
and human-readable summaries for the chatbot.
"""
import numpy as np
from typing import Optional


def compute_baseline(readings: list[dict]) -> dict:
    """
    Compute per-feature baseline statistics from calibration readings.
    Returns a dict keyed by feature name, with:
      mean, std, min, max, p5, p95, count
    """
    if not readings:
        return {}

    feature_names = [k for k in readings[0].keys() if k != "timestamp"]
    baseline = {}

    for feat in feature_names:
        values = [r[feat] for r in readings if feat in r and r[feat] is not None]
        if not values:
            continue
        arr = np.array(values, dtype=float)
        baseline[feat] = {
            "mean": round(float(arr.mean()), 4),
            "std": round(float(arr.std()), 4),
            "min": round(float(arr.min()), 4),
            "max": round(float(arr.max()), 4),
            "p5": round(float(np.percentile(arr, 5)), 4),
            "p95": round(float(np.percentile(arr, 95)), 4),
            "count": len(values),
        }

    return baseline


def summarize_baseline_for_chatbot(baseline: dict) -> str:
    """
    Convert baseline stats to a readable string for injection into the LLM prompt.
    """
    lines = ["Baseline (normal operating ranges):"]
    for feat, stats in baseline.items():
        lines.append(
            f"  {feat}: mean={stats['mean']:.2f}, std={stats['std']:.2f}, "
            f"range=[{stats['p5']:.2f}–{stats['p95']:.2f}]"
        )
    return "\n".join(lines)


def deviation_report(
    current_values: dict[str, float],
    baseline: dict,
) -> list[dict]:
    """
    Compare current values to baseline stats.
    Returns a list of {feature, current, mean, z_score, deviation_pct}
    for features that are more than 2 standard deviations from baseline mean.
    """
    deviations = []
    for feat, val in current_values.items():
        if feat not in baseline:
            continue
        b = baseline[feat]
        if b["std"] < 1e-9:
            continue
        z = (val - b["mean"]) / b["std"]
        if abs(z) > 2.0:
            deviations.append({
                "feature": feat,
                "current": round(val, 4),
                "baseline_mean": b["mean"],
                "z_score": round(z, 2),
                "deviation_pct": round((val - b["mean"]) / (abs(b["mean"]) + 1e-9) * 100, 1),
            })

    deviations.sort(key=lambda d: abs(d["z_score"]), reverse=True)
    return deviations
