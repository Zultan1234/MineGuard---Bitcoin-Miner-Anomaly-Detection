"""
Feature Configuration — 29 validated features.

14 raw instantaneous fields from cgminer
15 derived features computed per-reading

EXCLUDED from ML model (and why):
  Device Rejected%  — startup-decay running average, not hardware state
  GHS av            — startup-decay running average
  Utility           — startup-decay (shares/minute elapsed)
  Work Utility      — same
  Device Hardware%  — startup-decay
  Pool Rejected%    — duplicate of Device Rejected%
  Accepted/Rejected — cumulative counters (grow with time)
  Hardware Errors   — cumulative counter (raw value) — only the RATE is used
  no_matching_work  — cumulative counter (raw value) — excluded entirely
  frequency*        — constant (firmware-set, never changes)
  voltage*          — constant on L3+ (10.11V always)
  chain_acn*        — constant per board (67 or 72, never changes during operation)
  chain_power*      — constant (105.5W per board always)
  pool*_*           — pool duplicates of summary fields
"""

# Raw instantaneous fields from cgminer (14)
CORE_RAW_FEATURES = [
    "GHS 5s",       # total hashrate, 5-second rolling average (GH/s)
    "temp1",         # board 1 PCB inlet temperature (°C)
    "temp3",         # board 3 PCB inlet temperature (°C)
    "temp4",         # board 4 PCB inlet temperature (°C)
    "temp2_1",       # board 1 chip junction temperature (°C)
    "temp2_2",       # board 2 chip junction temperature (°C)
    "temp2_3",       # board 3 chip junction temperature (°C)
    "temp2_4",       # board 4 chip junction temperature (°C)
    "fan1",          # intake fan speed (RPM)
    "fan2",          # exhaust fan speed (RPM)
    "chain_rate1",   # board 1 hashrate (GH/s)
    "chain_rate2",   # board 2 hashrate (GH/s)
    "chain_rate3",   # board 3 hashrate (GH/s)
    "chain_rate4",   # board 4 hashrate (GH/s)
]

# Fields read from cgminer for derived computation but NOT fed to model
RAW_DEPENDENCIES = [
    "Hardware Errors", "chain_hw1", "chain_hw2", "chain_hw3",
    "temp2",
]

# Derived features computed by _enrich() in trainer.py (15)
DERIVED_FEATURES = [
    "Hardware Errors_rate",  # HW errors THIS interval only (curr - prev)
    "chain_hw1_rate",        # board 1 HW error rate this interval
    "chain_hw2_rate",        # board 2 HW error rate this interval
    "chain_hw3_rate",        # board 3 HW error rate this interval
    "chain_dev1",            # board 1 hashrate deviation from board average
    "chain_dev2",            # board 2 deviation
    "chain_dev3",            # board 3 deviation
    "chain_dev4",            # board 4 deviation
    "board_imbalance",       # std(board hashrates) / mean
    "thermal_ratio",         # max(chip temps) / mean(chip temps)
    "fan_temp_ratio",        # mean(fan RPM) / max(chip temp)
    "chip_pcb_delta1",       # board 1: chip temp minus PCB temp (°C)
    "chip_pcb_delta2",       # board 2
    "chip_pcb_delta3",       # board 3
    "chip_pcb_delta4",       # board 4
]

ALL_FEATURES = CORE_RAW_FEATURES + DERIVED_FEATURES  # 29 total

FEATURE_DESCRIPTIONS = {
    "GHS 5s":              "Total hashrate (GH/s, 5s avg)",
    "temp1":               "Board 1 PCB inlet temp (°C)",
    "temp3":               "Board 3 PCB inlet temp (°C)",
    "temp4":               "Board 4 PCB inlet temp (°C)",
    "temp2_1":             "Board 1 chip temp (°C)",
    "temp2_2":             "Board 2 chip temp (°C)",
    "temp2_3":             "Board 3 chip temp (°C)",
    "temp2_4":             "Board 4 chip temp (°C)",
    "fan1":                "Intake fan (RPM)",
    "fan2":                "Exhaust fan (RPM)",
    "chain_rate1":         "Board 1 hashrate (GH/s)",
    "chain_rate2":         "Board 2 hashrate (GH/s)",
    "chain_rate3":         "Board 3 hashrate (GH/s)",
    "chain_rate4":         "Board 4 hashrate (GH/s)",
    "Hardware Errors_rate":"HW errors this interval (Δ)",
    "chain_hw1_rate":      "Board 1 HW errors this interval (Δ)",
    "chain_hw2_rate":      "Board 2 HW errors this interval (Δ)",
    "chain_hw3_rate":      "Board 3 HW errors this interval (Δ)",
    "chain_dev1":          "Board 1 hashrate vs average",
    "chain_dev2":          "Board 2 hashrate vs average",
    "chain_dev3":          "Board 3 hashrate vs average",
    "chain_dev4":          "Board 4 hashrate vs average",
    "board_imbalance":     "Hashrate imbalance across boards",
    "thermal_ratio":       "Chip temp hotspot ratio",
    "fan_temp_ratio":      "Fan RPM / chip temp ratio",
    "chip_pcb_delta1":     "Board 1 chip-PCB temp gap (°C)",
    "chip_pcb_delta2":     "Board 2 chip-PCB temp gap (°C)",
    "chip_pcb_delta3":     "Board 3 chip-PCB temp gap (°C)",
    "chip_pcb_delta4":     "Board 4 chip-PCB temp gap (°C)",
}
