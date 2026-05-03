"""
Rule-Based Safety Engine — Physics-aware per-feature thresholds.

Each feature type has its own detection logic because different features
have completely different physical behavior:

  hashrate   — percentage deviation from baseline (±5% yellow, ±12% red)
  temp_pcb   — absolute ceiling AND absolute delta above baseline
  temp_chip  — absolute ceiling AND absolute delta above baseline  
  fan        — one-directional (only alert on drops, not speed increases)
  frequency  — very tight (firmware-set, should not change: ±2%/±5%)
  voltage    — tight percentage (±3%/±6%) plus hard absolute limits
  chips      — drop below baseline by N chips (not percentage — chips are discrete)
  hw_error   — spike in delta rate (stored as delta/interval already)
  power      — percentage deviation from baseline (±10%/±20%)

With no baseline: only fire on genuinely dangerous absolute values.
With baseline: use the physics-aware logic above.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class RuleViolation:
    rule_name:     str
    feature:       str
    value:         float
    threshold:     float
    direction:     str    # "above" | "below" | "deviation" | "drop"
    severity:      str    # "red" | "yellow"
    message:       str
    pct_deviation: Optional[float] = None


# ── No-baseline fallback — only fire on genuinely dangerous values ────────────
# These are deliberately conservative to avoid false positives before training.
ABSOLUTE_FALLBACK = [
    ("temp1",    "above", 72.0, 82.0,  "°C",   "PCB temp board 1"),
    ("temp2",    "above", 72.0, 82.0,  "°C",   "PCB temp board 2"),
    ("temp3",    "above", 72.0, 82.0,  "°C",   "PCB temp board 3"),
    ("temp4",    "above", 72.0, 82.0,  "°C",   "PCB temp board 4"),
    ("temp2_1",  "above", 80.0, 90.0,  "°C",   "Chip temp board 1"),
    ("temp2_2",  "above", 80.0, 90.0,  "°C",   "Chip temp board 2"),
    ("temp2_3",  "above", 80.0, 90.0,  "°C",   "Chip temp board 3"),
    ("temp2_4",  "above", 80.0, 90.0,  "°C",   "Chip temp board 4"),
    ("temp_max", "above", 80.0, 90.0,  "°C",   "Max temperature"),
    ("fan1",     "below", 1000, 500,   "RPM",  "Intake fan"),
    ("fan2",     "below", 1000, 500,   "RPM",  "Exhaust fan"),
    ("GHS 5s",   "below", 5.0,  1.0,  "GH/s", "Hashrate"),
    ("voltage1", "below", 9.2,  8.8,  "V",    "Board 1 voltage"),
    ("voltage2", "below", 9.2,  8.8,  "V",    "Board 2 voltage"),
    ("voltage3", "below", 9.2,  8.8,  "V",    "Board 3 voltage"),
    ("voltage4", "below", 9.2,  8.8,  "V",    "Board 4 voltage"),
    ("voltage1", "above", 10.9, 11.2, "V",    "Board 1 voltage high"),
    ("voltage2", "above", 10.9, 11.2, "V",    "Board 2 voltage high"),
    ("voltage3", "above", 10.9, 11.2, "V",    "Board 3 voltage high"),
    ("voltage4", "above", 10.9, 11.2, "V",    "Board 4 voltage high"),
]


# ── Feature type definitions ──────────────────────────────────────────────────

# Percentage deviation features — both directions matter
# (feature_name, yellow_pct, red_pct)
PCT_FEATURES = {
    "GHS 5s":       (5.0,  12.0),
    "GHS av":       (5.0,  12.0),
    "chain_rate1":  (7.0,  15.0),
    "chain_rate2":  (7.0,  15.0),
    "chain_rate3":  (7.0,  15.0),
    "chain_rate4":  (7.0,  15.0),
    "frequency":    (2.0,   5.0),
    "frequency1":   (2.0,   5.0),
    "frequency2":   (2.0,   5.0),
    "frequency3":   (2.0,   5.0),
    "frequency4":   (2.0,   5.0),
    "voltage1":     (3.0,   6.0),
    "voltage2":     (3.0,   6.0),
    "voltage3":     (3.0,   6.0),
    "voltage4":     (3.0,   6.0),
    "chain_power1": (10.0, 20.0),
    "chain_power2": (10.0, 20.0),
    "chain_power3": (10.0, 20.0),
    "chain_power4": (10.0, 20.0),
    "chain_power":  (10.0, 20.0),
}

# Temperature features — absolute ceiling + absolute delta above baseline
# (feature_name, warn_abs, crit_abs, yellow_delta_above_baseline, red_delta_above_baseline)
TEMP_FEATURES = {
    "temp1":   (65.0, 75.0, 12.0, 20.0),
    "temp2":   (65.0, 75.0, 12.0, 20.0),
    "temp3":   (65.0, 75.0, 12.0, 20.0),
    "temp4":   (65.0, 75.0, 12.0, 20.0),
    "temp2_1": (75.0, 85.0, 15.0, 25.0),
    "temp2_2": (75.0, 85.0, 15.0, 25.0),
    "temp2_3": (75.0, 85.0, 15.0, 25.0),
    "temp2_4": (75.0, 85.0, 15.0, 25.0),
    "temp_max":(75.0, 85.0, 15.0, 25.0),
}

# Fan features — one-directional (drop only) + absolute floor
# (feature_name, warn_abs_low, crit_abs_low, yellow_pct_drop, red_pct_drop)
FAN_FEATURES = {
    "fan1": (1200, 600, 20.0, 35.0),
    "fan2": (1200, 600, 20.0, 35.0),
}

# Chip count features — drop below baseline by N chips (discrete, not %)
# (feature_name, yellow_drop_chips, red_drop_chips, absolute_critical_floor)
CHIP_FEATURES = {
    "chain_acn1": (4, 10, 40),
    "chain_acn2": (4, 10, 40),
    "chain_acn3": (4, 10, 40),
    "chain_acn4": (4, 10, 40),
}

# Hardware error delta rate features — spike detection
# (feature_name, yellow_rate, red_rate) — errors per poll interval
HW_ERROR_FEATURES = {
    # These are handled by the ML model via _rate features.
    # The rule engine only fires if the rate is WAY above baseline (3x+).
    # This prevents false alarms on miners that normally have high error rates
    # (like your L3+ board 2 which normally produces ~11 errors/interval).
    # The multipliers below mean: yellow if 3x above baseline, red if 6x.
    # Hardware Errors and no_matching_work are CUMULATIVE counters.
    # They are NOT checked here. Only their RATE versions
    # (Hardware Errors_rate, chain_hw*_rate) are used — inside the ML model.
    "chain_hw1":       {"yellow_mult": 3.0, "red_mult": 6.0},
    "chain_hw2":       {"yellow_mult": 3.0, "red_mult": 6.0},
    "chain_hw3":       {"yellow_mult": 3.0, "red_mult": 6.0},
    "chain_hw4":       {"yellow_mult": 3.0, "red_mult": 6.0},
}

# Display thresholds for dashboard coloring (% deviation)
# Used by compute_deviations_with_status for the colored feature grid
DISPLAY_THRESHOLDS = {
    "GHS 5s":      (5.0,  12.0),
    "GHS av":      (5.0,  12.0),
    "chain_rate1": (7.0,  15.0),
    "chain_rate2": (7.0,  15.0),
    "chain_rate3": (7.0,  15.0),
    "chain_rate4": (7.0,  15.0),
    "frequency":   (2.0,   5.0),
    "frequency1":  (2.0,   5.0),
    "frequency2":  (2.0,   5.0),
    "frequency3":  (2.0,   5.0),
    "frequency4":  (2.0,   5.0),
    "voltage1":    (3.0,   6.0),
    "voltage2":    (3.0,   6.0),
    "voltage3":    (3.0,   6.0),
    "voltage4":    (3.0,   6.0),
    "chain_power1":(10.0, 20.0),
    "chain_power2":(10.0, 20.0),
    "chain_power3":(10.0, 20.0),
    "chain_power4":(10.0, 20.0),
    "chain_power": (10.0, 20.0),
    # Temperatures shown as delta from baseline in °C (converted to % for display)
    "temp1":       (10.0, 20.0),
    "temp2":       (10.0, 20.0),
    "temp3":       (10.0, 20.0),
    "temp4":       (10.0, 20.0),
    "temp2_1":     (12.0, 22.0),
    "temp2_2":     (12.0, 22.0),
    "temp2_3":     (12.0, 22.0),
    "temp2_4":     (12.0, 22.0),
    "temp_max":    (12.0, 22.0),
    # Fans — only downward deviation shown
    "fan1":        (15.0, 30.0),
    "fan2":        (15.0, 30.0),
    # Chips — shown as %
    "chain_acn1":  (5.0,  14.0),
    "chain_acn2":  (5.0,  14.0),
    "chain_acn3":  (5.0,  14.0),
    "chain_acn4":  (5.0,  14.0),
    "_default":    (12.0, 25.0),
}


def check_rules(
    values: dict,
    preset_features: list = None,
    baseline: dict = None,
) -> list[RuleViolation]:
    """
    Check all rules against current values.
    With baseline: physics-aware per-feature logic.
    Without baseline: conservative absolute fallback only.
    """
    violations: list[RuleViolation] = []
    seen = set()

    def add(v: RuleViolation):
        key = (v.feature, v.direction, v.rule_name)
        if key not in seen:
            seen.add(key)
            violations.append(v)

    if baseline:
        # ── BASELINE MODE ───────────────────────────────────────────────────

        for label, value in values.items():
            if not isinstance(value, (int, float)): continue
            if label.startswith("_"): continue

            # ── 1. Percentage-deviation features ────────────────────────────
            if label in PCT_FEATURES:
                if label not in baseline: continue
                mean = baseline[label].get("mean", 0)
                if mean == 0: continue
                y_pct, r_pct = PCT_FEATURES[label]
                pct = (value - mean) / abs(mean) * 100
                abs_pct = abs(pct)
                direction = "above" if pct > 0 else "below"
                if abs_pct > r_pct:
                    add(RuleViolation(
                        f"{label}_DEV_RED", label, value, mean, "deviation", "red",
                        f"{label}: {value:.2f} is {abs_pct:.1f}% {'above' if pct>0 else 'below'} "
                        f"baseline {mean:.2f} (limit ±{r_pct}%) — RED",
                        pct_deviation=round(pct, 1)))
                elif abs_pct > y_pct:
                    add(RuleViolation(
                        f"{label}_DEV_YELLOW", label, value, mean, "deviation", "yellow",
                        f"{label}: {value:.2f} is {abs_pct:.1f}% {'above' if pct>0 else 'below'} "
                        f"baseline {mean:.2f} (limit ±{y_pct}%) — YELLOW",
                        pct_deviation=round(pct, 1)))

            # ── 2. Temperature features (absolute ceiling + delta) ───────────
            elif label in TEMP_FEATURES:
                warn_abs, crit_abs, y_delta, r_delta = TEMP_FEATURES[label]
                # Absolute ceiling always applies
                if value >= crit_abs:
                    add(RuleViolation(
                        f"{label}_CRIT_HOT", label, value, crit_abs, "above", "red",
                        f"{label}: {value:.1f}°C ≥ {crit_abs}°C critical limit — RED"))
                elif value >= warn_abs:
                    add(RuleViolation(
                        f"{label}_HOT", label, value, warn_abs, "above", "yellow",
                        f"{label}: {value:.1f}°C ≥ {warn_abs}°C warning limit — YELLOW"))

                # Also check delta above baseline (catches "hotter than usual")
                if label in baseline:
                    mean = baseline[label].get("mean", value)
                    delta = value - mean
                    if delta >= r_delta:
                        add(RuleViolation(
                            f"{label}_HOT_DELTA_RED", label, value, mean, "above", "red",
                            f"{label}: {value:.1f}°C is {delta:.1f}°C above baseline "
                            f"{mean:.1f}°C (limit +{r_delta}°C) — RED"))
                    elif delta >= y_delta:
                        add(RuleViolation(
                            f"{label}_HOT_DELTA_YELLOW", label, value, mean, "above", "yellow",
                            f"{label}: {value:.1f}°C is {delta:.1f}°C above baseline "
                            f"{mean:.1f}°C (limit +{y_delta}°C) — YELLOW"))

            # ── 3. Fan features (drop only) ──────────────────────────────────
            elif label in FAN_FEATURES:
                warn_low, crit_low, y_drop_pct, r_drop_pct = FAN_FEATURES[label]
                # Absolute floor always applies
                if value < crit_low:
                    add(RuleViolation(
                        f"{label}_CRIT_SLOW", label, value, crit_low, "below", "red",
                        f"{label}: {value:.0f} RPM < {crit_low} RPM critical floor — RED"))
                elif value < warn_low:
                    add(RuleViolation(
                        f"{label}_SLOW", label, value, warn_low, "below", "yellow",
                        f"{label}: {value:.0f} RPM < {warn_low} RPM warning floor — YELLOW"))

                # Only alert on drops below baseline (fans speeding up is normal/good)
                if label in baseline:
                    mean = baseline[label].get("mean", value)
                    if mean > 0:
                        drop_pct = (mean - value) / mean * 100  # positive = dropped
                        if drop_pct >= r_drop_pct:
                            add(RuleViolation(
                                f"{label}_DROP_RED", label, value, mean, "drop", "red",
                                f"{label}: {value:.0f} RPM is {drop_pct:.1f}% below baseline "
                                f"{mean:.0f} RPM (limit -{r_drop_pct}%) — RED",
                                pct_deviation=round(-drop_pct, 1)))
                        elif drop_pct >= y_drop_pct:
                            add(RuleViolation(
                                f"{label}_DROP_YELLOW", label, value, mean, "drop", "yellow",
                                f"{label}: {value:.0f} RPM is {drop_pct:.1f}% below baseline "
                                f"{mean:.0f} RPM (limit -{y_drop_pct}%) — YELLOW",
                                pct_deviation=round(-drop_pct, 1)))

            # ── 4. Chip count features (discrete drop) ───────────────────────
            elif label in CHIP_FEATURES:
                y_drop, r_drop, abs_floor = CHIP_FEATURES[label]
                # Absolute floor always applies
                if value < abs_floor:
                    add(RuleViolation(
                        f"{label}_CRIT_FLOOR", label, value, abs_floor, "below", "red",
                        f"{label}: {int(value)} chips < {abs_floor} absolute minimum — RED"))

                # Drop below baseline (chip count is discrete — compare absolute)
                if label in baseline:
                    mean = baseline[label].get("mean", value)
                    drop = mean - value  # positive = fewer chips than baseline
                    if drop >= r_drop:
                        add(RuleViolation(
                            f"{label}_CHIP_LOSS_RED", label, value, mean, "drop", "red",
                            f"{label}: {int(value)} chips, {drop:.0f} fewer than baseline "
                            f"{mean:.0f} (limit -{r_drop} chips) — RED"))
                    elif drop >= y_drop:
                        add(RuleViolation(
                            f"{label}_CHIP_LOSS_YELLOW", label, value, mean, "drop", "yellow",
                            f"{label}: {int(value)} chips, {drop:.0f} fewer than baseline "
                            f"{mean:.0f} (limit -{y_drop} chips) — YELLOW"))

            # ── 5. Hardware error rate — baseline-relative ──────────────────
            elif label in HW_ERROR_FEATURES:
                cfg = HW_ERROR_FEATURES[label]
                # Only fire if we have a baseline to compare against
                if label in baseline:
                    mean = baseline[label].get("mean", 0)
                    if mean > 0:
                        y_limit = mean * cfg["yellow_mult"]
                        r_limit = mean * cfg["red_mult"]
                        if value >= r_limit:
                            add(RuleViolation(
                                f"{label}_SPIKE_RED", label, value, r_limit, "above", "red",
                                f"{label}: +{int(value)} errors/interval ({cfg['red_mult']:.0f}x above baseline {mean:.1f}) — RED"))
                        elif value >= y_limit:
                            add(RuleViolation(
                                f"{label}_SPIKE_YELLOW", label, value, y_limit, "above", "yellow",
                                f"{label}: +{int(value)} errors/interval ({cfg['yellow_mult']:.0f}x above baseline {mean:.1f}) — YELLOW"))
                # No baseline → no HW error rules fire (ML handles it)

    else:
        # ── NO BASELINE: conservative absolute fallback ─────────────────────
        for (match, direction, y_t, r_t, unit, desc) in ABSOLUTE_FALLBACK:
            for label, value in values.items():
                if not isinstance(value, (int, float)): continue
                if match.lower() != label.lower(): continue
                if direction == "above":
                    if value > r_t:
                        add(RuleViolation(f"{match}_HIGH", label, value, r_t, "above", "red",
                            f"{desc}: {value:.1f}{unit} > {r_t} (no baseline yet — RED)"))
                    elif value > y_t:
                        add(RuleViolation(f"{match}_WARN", label, value, y_t, "above", "yellow",
                            f"{desc}: {value:.1f}{unit} > {y_t} (no baseline yet — YELLOW)"))
                elif direction == "below":
                    if value < r_t:
                        add(RuleViolation(f"{match}_CRIT_LOW", label, value, r_t, "below", "red",
                            f"{desc}: {value:.1f}{unit} < {r_t} (no baseline yet — RED)"))
                    elif value < y_t:
                        add(RuleViolation(f"{match}_LOW", label, value, y_t, "below", "yellow",
                            f"{desc}: {value:.1f}{unit} < {y_t} (no baseline yet — YELLOW)"))

    violations.sort(key=lambda x: 0 if x.severity == "red" else 1)
    return violations


def determine_status_from_rules(violations: list[RuleViolation]) -> str:
    if not violations: return "GREEN"
    if any(v.severity == "red" for v in violations): return "RED"
    return "YELLOW"


def compute_deviations_with_status(values: dict, baseline: dict) -> list[dict]:
    """
    Compute deviation from baseline for features that are in the ML model.
    Excludes startup-decay fields (Device Rejected%, GHS av, Utility, etc.)
    and cumulative fields. Only shows the 29 model features.
    """
    if not baseline:
        return []

    # Only show features that are in the ML model's feature set
    from backend.ml.feature_config import ALL_FEATURES
    MODEL_FEATURES = set(ALL_FEATURES)

    # Fields that should NEVER appear in deviation display
    # (startup-decay, cumulative, pool duplicates)
    EXCLUDE = {
        "Device Rejected%", "Pool Rejected%", "Device Hardware%",
        "Pool Stale%", "GHS av", "Utility", "Work Utility",
        "Accepted", "Rejected", "Hardware Errors", "Discarded",
        "Total MH", "Getworks", "Best Share", "Elapsed",
        "Difficulty Accepted", "Difficulty Rejected",
        "no_matching_work", "chain_hw1", "chain_hw2", "chain_hw3", "chain_hw4",
    }

    result = []
    for label, value in values.items():
        if not isinstance(value, (int, float)): continue
        if label.startswith("_"): continue
        if label in EXCLUDE: continue
        if label not in baseline: continue

        mean = baseline[label].get("mean", 0)
        std  = baseline[label].get("std", 0)
        if mean == 0: continue

        # For fans — only show downward deviation
        if label in FAN_FEATURES:
            drop = mean - value
            pct  = drop / max(mean, 1) * 100
            y_pct, r_pct = DISPLAY_THRESHOLDS.get(label, DISPLAY_THRESHOLDS["_default"])
        else:
            pct  = (value - mean) / abs(mean) * 100
            y_pct, r_pct = DISPLAY_THRESHOLDS.get(label, DISPLAY_THRESHOLDS["_default"])

        abs_pct = abs(pct)
        if abs_pct > r_pct:   status = "red"
        elif abs_pct > y_pct: status = "yellow"
        else:                  status = "green"

        result.append({
            "feature":       label,
            "current":       round(value, 3),
            "baseline_mean": round(mean, 3),
            "baseline_std":  round(std, 3),
            "pct_deviation": round(pct, 2),
            "abs_pct":       round(abs_pct, 2),
            "status":        status,
            "yellow_pct":    y_pct,
            "red_pct":       r_pct,
        })

    # Sort: red first, then yellow, then by abs_pct
    sev_order = {"red": 0, "yellow": 1, "green": 2}
    result.sort(key=lambda x: (sev_order[x["status"]], -x["abs_pct"]))
    return result
