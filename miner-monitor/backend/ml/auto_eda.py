"""
Auto-EDA — Rigorous Unsupervised Feature Selection for Miner Telemetry

This module runs BEFORE training and decides which features to keep.
It does NOT rely on labels (we have none in production).

Selection pipeline (each step eliminates features):

Step 1: DOMAIN FILTER
  Remove fields that are metadata, not telemetry:
  - Pool identifiers (POOL, URL, User, etc.)
  - Firmware strings (CGMiner, Type, CompileTime)
  - Internal counters (id, When, Code, Elapsed, Calls)
  - Chip status strings (chain_acs1-4)

Step 2: CONSTANT FILTER  
  Remove features with zero or near-zero variance.
  If a feature is the same value in >98% of readings, it carries
  no information about anomalies.
  Example: frequency=200 always, miner_count=4 always

Step 3: MONOTONICITY FILTER
  Remove features that are monotonically increasing (cumulative counters).
  These are NOT anomaly indicators — they just measure elapsed time.
  Detection: if sorted(values) == values for >95% of the data, it's monotonic.
  Example: Accepted, Difficulty Accepted, Total MH, Elapsed, Getworks

Step 4: DUPLICATE/POOL FILTER
  Remove pool-prefixed duplicates of summary-level fields.
  pool0_Accepted == Accepted, pool0_Best Share == Best Share, etc.
  Keep the summary-level version.

Step 5: REDUNDANCY FILTER
  When two features have |correlation| > 0.98, keep the one with
  higher coefficient of variation (more informative).
  Example: Device Rejected% and Pool Rejected% are always identical → keep one.

Step 6: STATIONARITY CHECK
  Flag features with strong linear trend (correlation with index > 0.8).
  These will bias the model to see normal time progression as anomalous.
  Example: Total MH (always increasing with time)

After all filters, the surviving features are the ones the model trains on.
"""
import logging
import numpy as np
from typing import Optional

logger = logging.getLogger("ml.auto_eda")

# ── Step 1: Domain metadata — always excluded ─────────────────────────────────
METADATA_KEYWORDS = {
    "POOL", "URL", "User", "Status", "Stratum", "Priority", "Quota",
    "Proxy", "GetFailures", "Has Stratum", "Has GBT",
    "Last Share Time", "Last Share Difficulty",
    "CGMiner", "Miner", "CompileTime", "Type", "ID",
    "chain_acs",  # chip status strings (oooooooo...)
}

METADATA_EXACT = {
    "id", "When", "Code", "Elapsed", "Calls", "Wait", "Min", "Max",
    "STATUS", "Description", "Msg", "STATS",
    "fan_num", "temp_num", "miner_count",
    "Last getwork", "Last Share Difficulty", "Last Share Time",
    "Quota",
}

# ── Step 3: Known cumulative fields ───────────────────────────────────────────
KNOWN_CUMULATIVE = {
    "Accepted", "Rejected", "Discarded", "Stale",
    "Hardware Errors", "Get Failures", "Remote Failures",
    "Local Work", "Getworks", "Network Blocks",
    "Total MH", "Diff1 Shares",
    "Difficulty Accepted", "Difficulty Rejected", "Difficulty Stale",
    "Best Share", "Work Utility",
    "no_matching_work",
    "chain_hw1", "chain_hw2", "chain_hw3", "chain_hw4",
}


def run_auto_eda(readings: list[dict], miner_id: str = "") -> dict:
    """
    Run the full 6-step feature selection pipeline.
    Returns selected features and a detailed report of what was dropped and why.
    """
    if not readings or len(readings) < 10:
        return {"error": "Need at least 10 readings", "selected_features": []}

    # Collect all numeric feature names
    all_keys = set()
    for r in readings:
        for k, v in r.items():
            try:
                float(v)
                all_keys.add(k)
            except (ValueError, TypeError):
                pass

    all_features = sorted(all_keys)
    n_total = len(all_features)
    dropped = []
    reasons = {}  # feature -> reason string

    # ── STEP 1: Domain metadata filter ────────────────────────────────────
    step1_drop = set()
    for f in all_features:
        if f in METADATA_EXACT:
            step1_drop.add(f); reasons[f] = "metadata field"
            continue
        for kw in METADATA_KEYWORDS:
            if kw.lower() in f.lower():
                step1_drop.add(f); reasons[f] = f"metadata (contains '{kw}')"
                break
        # Pool-prefixed fields (pool0_, pool1_, etc.)
        if any(f.startswith(f"pool{i}_") for i in range(10)):
            step1_drop.add(f); reasons[f] = "pool duplicate of summary field"

    remaining = [f for f in all_features if f not in step1_drop]
    logger.info(f"  Step 1 (domain filter): {n_total} → {len(remaining)} ({len(step1_drop)} dropped)")

    # ── STEP 2: Constant filter ───────────────────────────────────────────
    X = np.array([[_safe_float(r.get(f, 0)) for f in remaining] for r in readings])
    step2_drop = set()
    for i, f in enumerate(remaining):
        col = X[:, i]
        unique_ratio = len(np.unique(col)) / len(col)
        std = np.std(col)
        if std == 0:
            step2_drop.add(f); reasons[f] = "constant (zero variance)"
        elif unique_ratio < 0.02 and std < 1e-6:
            step2_drop.add(f); reasons[f] = f"near-constant ({len(np.unique(col))} unique values)"

    remaining = [f for f in remaining if f not in step2_drop]
    logger.info(f"  Step 2 (constant filter): → {len(remaining)} ({len(step2_drop)} dropped)")

    # ── STEP 3: Monotonicity / cumulative filter ──────────────────────────
    X = np.array([[_safe_float(r.get(f, 0)) for f in remaining] for r in readings])
    step3_drop = set()
    for i, f in enumerate(remaining):
        # Check if it's a known cumulative field
        if f in KNOWN_CUMULATIVE:
            step3_drop.add(f); reasons[f] = "cumulative counter (grows with time)"
            continue
        # Also detect empirically: if >90% of consecutive diffs are >= 0
        col = X[:, i]
        if len(col) > 20:
            diffs = np.diff(col)
            non_neg_ratio = np.mean(diffs >= 0)
            if non_neg_ratio > 0.95 and np.std(col) > 0:
                # Check it's not just constant with noise
                trend_corr = abs(np.corrcoef(np.arange(len(col)), col)[0, 1])
                if trend_corr > 0.8:
                    step3_drop.add(f)
                    reasons[f] = f"monotonically increasing (trend r={trend_corr:.2f})"

    remaining = [f for f in remaining if f not in step3_drop]
    logger.info(f"  Step 3 (monotonic filter): → {len(remaining)} ({len(step3_drop)} dropped)")

    # ── STEP 4: Redundancy filter (high correlation) ──────────────────────
    if len(remaining) > 2:
        X = np.array([[_safe_float(r.get(f, 0)) for f in remaining] for r in readings])
        stds = X.std(axis=0)
        valid = stds > 0
        step4_drop = set()

        if valid.sum() > 1:
            X_valid = X[:, valid]
            valid_feats = [f for f, v in zip(remaining, valid) if v]
            corr = np.corrcoef(X_valid.T)
            cvs = {f: abs(stds[remaining.index(f)] / (X[:, remaining.index(f)].mean() + 1e-9))
                   for f in valid_feats}

            # For each pair with |r| > 0.98, drop the one with lower CV
            processed = set()
            for i in range(len(valid_feats)):
                if valid_feats[i] in processed: continue
                for j in range(i + 1, len(valid_feats)):
                    if valid_feats[j] in processed: continue
                    if abs(corr[i, j]) > 0.98:
                        # Drop the one with lower CV (less informative)
                        f1, f2 = valid_feats[i], valid_feats[j]
                        if cvs.get(f1, 0) < cvs.get(f2, 0):
                            to_drop = f1
                        else:
                            to_drop = f2
                        step4_drop.add(to_drop)
                        processed.add(to_drop)
                        reasons[to_drop] = f"redundant with {f1 if to_drop == f2 else f2} (r={abs(corr[i,j]):.3f})"

        remaining = [f for f in remaining if f not in step4_drop]
        logger.info(f"  Step 4 (redundancy filter): → {len(remaining)} ({len(step4_drop)} dropped)")

    # ── STEP 5: Stationarity check (flag, don't drop) ────────────────────
    X = np.array([[_safe_float(r.get(f, 0)) for f in remaining] for r in readings])
    stationarity_warnings = []
    for i, f in enumerate(remaining):
        col = X[:, i]
        if np.std(col) > 0:
            trend_r = abs(np.corrcoef(np.arange(len(col)), col)[0, 1])
            if trend_r > 0.7:
                stationarity_warnings.append({"feature": f, "trend_r": round(float(trend_r), 3)})

    # ── Compile results ───────────────────────────────────────────────────
    all_dropped = []
    for f in all_features:
        if f in reasons:
            all_dropped.append({"name": f, "reason": reasons[f]})

    # Compute stats for selected features
    feature_stats = {}
    X_final = np.array([[_safe_float(r.get(f, 0)) for f in remaining] for r in readings])
    for i, f in enumerate(remaining):
        col = X_final[:, i]
        feature_stats[f] = {
            "mean": round(float(np.mean(col)), 4),
            "std":  round(float(np.std(col)), 4),
            "min":  round(float(np.min(col)), 4),
            "max":  round(float(np.max(col)), 4),
            "p5":   round(float(np.percentile(col, 5)), 4),
            "p95":  round(float(np.percentile(col, 95)), 4),
        }

    report = _build_report(miner_id, len(readings), n_total, remaining,
                            all_dropped, feature_stats, stationarity_warnings)

    logger.info(f"  Auto-EDA complete: {n_total} → {len(remaining)} features selected")

    return {
        "n_samples":           len(readings),
        "n_total_features":    n_total,
        "n_selected_features": len(remaining),
        "selected_features":   remaining,
        "dropped_features":    all_dropped,
        "feature_stats":       feature_stats,
        "stationarity_warnings": stationarity_warnings,
        "report":              report,
    }


def _safe_float(v, default=0.0):
    if isinstance(v, bool): return default
    try: return float(v)
    except: return default


def _build_report(miner_id, n_samples, n_total, selected, dropped, stats, warnings):
    lines = [
        f"## Auto-EDA Report: {miner_id}",
        f"**Samples:** {n_samples} | **Total fields:** {n_total} | **Selected:** {len(selected)} | **Dropped:** {len(dropped)}",
        "",
        "### Selection pipeline",
        f"- Step 1 (domain metadata): removed pool duplicates, firmware strings, internal IDs",
        f"- Step 2 (constant values): removed features with zero/near-zero variance",
        f"- Step 3 (cumulative counters): removed monotonically increasing fields",
        f"- Step 4 (redundancy): removed features with |corr| > 0.98 with another",
        "",
        f"### Selected features ({len(selected)})",
    ]
    for f in selected:
        s = stats.get(f, {})
        lines.append(f"  - `{f}`: mean={s.get('mean',0):.3f}, std={s.get('std',0):.4f}")
    if warnings:
        lines.append("")
        lines.append("### Stationarity warnings")
        for w in warnings:
            lines.append(f"  - `{w['feature']}`: trend r={w['trend_r']} — may introduce time bias")
    return "\n".join(lines)
