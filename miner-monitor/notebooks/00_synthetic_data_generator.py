"""
Synthetic Antminer L3+ Telemetry Generator

WHY SYNTHETIC DATA?
This is unsupervised anomaly detection. We have no labels. To evaluate models
we need ground-truth labels — i.e. we need to know exactly when an anomaly
happened and what kind. The only reliable way is to generate the data ourselves
based on the actual physics of an Antminer L3+ Hiveon.

PHYSICAL MODEL (Antminer L3+ Hiveon):
- Hashrate: ~261 GH/s nominal, fluctuates ±2% normally (pool variance)
- Temperatures: PCB inlet ~39°C, chip exhaust ~46°C, both rise with ambient
- Fans: 2400-2500 RPM, scale up with temperature
- Frequency: 200 MHz fixed by firmware
- Voltage: 10.11 V, very stable (±0.05V noise)
- Active chips: 67-72 per board, occasional disable events
- Power: 105 W per board × 4 = 420 W total, scales with hashrate

ANOMALY TYPES INJECTED:
1. Chip degradation — slow chip count decrease + hashrate drop on one board
2. Fan failure — sudden RPM drop on one fan + temperature rise
3. Thermal stress — ambient temp rises, all temps go up
4. Voltage instability — voltage fluctuates abnormally
5. Frequency throttle — chip overheats, frequency drops to compensate
6. Pool reject spike — hashrate normal but rejection rate spikes
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

RNG = np.random.default_rng(42)


def generate_normal_hour(start_time: datetime, samples: int = 120,
                         ambient_c: float = 22.0) -> pd.DataFrame:
    """
    Generate one hour of normal operation at 30-second intervals.
    Realistic noise and natural correlations between fields.
    """
    rows = []
    for i in range(samples):
        ts = start_time + timedelta(seconds=30 * i)

        # Ambient temperature drift (small sine wave + noise)
        ambient = ambient_c + 0.5 * np.sin(i / 20) + RNG.normal(0, 0.2)

        # Hashrate fluctuates with pool variance (±2%)
        ghs_5s_pct = 1.0 + RNG.normal(0, 0.015)
        ghs_5s = 261.5 * ghs_5s_pct
        ghs_av = ghs_5s * (1.0 + RNG.normal(0, 0.005))

        # Per-board hashrates (slight imbalance — board 4 has 67/72 chips)
        board_factors = [1.00, 0.997, 1.003, 0.93]  # board 4 weaker
        chain_rates = [(ghs_5s / 4) * f * (1 + RNG.normal(0, 0.012))
                       for f in board_factors]

        # Temperatures correlate with ambient + hashrate load
        load_factor = ghs_5s_pct
        temp_pcb_base  = 39.0 + (ambient - 22.0) * 0.5
        temp_chip_base = 46.0 + (ambient - 22.0) * 0.7
        temps_pcb  = [temp_pcb_base  + RNG.normal(0, 0.6) for _ in range(4)]
        temps_chip = [temp_chip_base + RNG.normal(0, 0.8) for _ in range(4)]

        # Fans scale with chip temperature
        max_chip_temp = max(temps_chip)
        fan_base = 2200 + (max_chip_temp - 46) * 30
        fan1 = fan_base + RNG.normal(0, 25)
        fan2 = fan_base + 30 + RNG.normal(0, 25)

        # Frequency very stable
        freq = 200.0
        freqs = [freq] * 4

        # Voltage very stable
        voltages = [10.11 + RNG.normal(0, 0.04) for _ in range(4)]

        # Chip counts (board 4 starts with 67)
        chain_acn = [72, 72, 72, 67]

        # Hardware errors — occasional small spikes (delta per interval)
        chain_hw_delta = [int(RNG.poisson(0.3)) for _ in range(4)]

        # Power scales with hashrate
        power_per_board = 105.5 * load_factor + RNG.normal(0, 0.5)
        chain_powers = [power_per_board * (1 + RNG.normal(0, 0.01)) for _ in range(4)]
        chain_power_total = sum(chain_powers)

        # Rejection rate is mostly 0
        device_reject_pct = max(0, RNG.normal(2.0, 0.8))
        device_hw_pct     = max(0, RNG.normal(0.05, 0.05))
        no_matching_work  = int(RNG.poisson(0.2))

        rows.append({
            "timestamp": ts.isoformat(),
            "GHS 5s": round(ghs_5s, 3),
            "GHS av": round(ghs_av, 2),
            "Hardware Errors": int(RNG.poisson(0.4)),
            "Device Rejected%": round(device_reject_pct, 2),
            "Device Hardware%": round(device_hw_pct, 4),
            "no_matching_work": no_matching_work,
            "miner_count": 4,
            "frequency":  round(freq, 1),
            "frequency1": round(freqs[0], 1),
            "frequency2": round(freqs[1], 1),
            "frequency3": round(freqs[2], 1),
            "frequency4": round(freqs[3], 1),
            "fan1": round(fan1, 0),
            "fan2": round(fan2, 0),
            "temp1": round(temps_pcb[0], 1),
            "temp2": round(temps_pcb[1], 1),
            "temp3": round(temps_pcb[2], 1),
            "temp4": round(temps_pcb[3], 1),
            "temp2_1": round(temps_chip[0], 1),
            "temp2_2": round(temps_chip[1], 1),
            "temp2_3": round(temps_chip[2], 1),
            "temp2_4": round(temps_chip[3], 1),
            "temp_max": round(max(temps_pcb + temps_chip), 1),
            "chain_rate1": round(chain_rates[0], 3),
            "chain_rate2": round(chain_rates[1], 3),
            "chain_rate3": round(chain_rates[2], 3),
            "chain_rate4": round(chain_rates[3], 3),
            "chain_acn1": chain_acn[0],
            "chain_acn2": chain_acn[1],
            "chain_acn3": chain_acn[2],
            "chain_acn4": chain_acn[3],
            "chain_hw1": chain_hw_delta[0],
            "chain_hw2": chain_hw_delta[1],
            "chain_hw3": chain_hw_delta[2],
            "chain_hw4": chain_hw_delta[3],
            "chain_power1": round(chain_powers[0], 2),
            "chain_power2": round(chain_powers[1], 2),
            "chain_power3": round(chain_powers[2], 2),
            "chain_power4": round(chain_powers[3], 2),
            "chain_power":  round(chain_power_total, 2),
            "voltage1": round(voltages[0], 3),
            "voltage2": round(voltages[1], 3),
            "voltage3": round(voltages[2], 3),
            "voltage4": round(voltages[3], 3),
            "anomaly_label": "normal",
            "anomaly_type":  "none",
        })
    return pd.DataFrame(rows)


def inject_chip_degradation(df: pd.DataFrame, board: int = 4,
                             start_idx: int = None, duration: int = 60) -> pd.DataFrame:
    """Slow chip failure on one board — chips disable, hashrate drops on that chain."""
    df = df.copy()
    if start_idx is None:
        start_idx = len(df) // 2
    end_idx = min(start_idx + duration, len(df))

    initial_chips = df.loc[start_idx, f"chain_acn{board}"]
    chips_to_lose = 8

    for i, idx in enumerate(range(start_idx, end_idx)):
        progress = (i + 1) / duration
        chips_lost = int(progress * chips_to_lose)
        new_chip_count = max(initial_chips - chips_lost, 50)
        df.loc[idx, f"chain_acn{board}"] = new_chip_count
        # Hashrate on that chain drops proportionally to chip loss
        chip_factor = new_chip_count / initial_chips
        df.loc[idx, f"chain_rate{board}"] = df.loc[idx, f"chain_rate{board}"] * chip_factor
        # HW errors spike during degradation
        df.loc[idx, f"chain_hw{board}"] = int(RNG.poisson(8))
        # Total hashrate drops
        df.loc[idx, "GHS 5s"] = sum(df.loc[idx, f"chain_rate{j}"] for j in range(1, 5))
        df.loc[idx, "anomaly_label"] = "anomaly"
        df.loc[idx, "anomaly_type"]  = "chip_degradation"
    return df


def inject_fan_failure(df: pd.DataFrame, fan: int = 1,
                        start_idx: int = None, duration: int = 40) -> pd.DataFrame:
    """Fan slows down then fails. Temperatures rise as a consequence."""
    df = df.copy()
    if start_idx is None:
        start_idx = len(df) // 2
    end_idx = min(start_idx + duration, len(df))

    for i, idx in enumerate(range(start_idx, end_idx)):
        progress = (i + 1) / duration
        # Fan RPM drops from ~2400 to ~600
        fan_target = 2400 - progress * 1800
        df.loc[idx, f"fan{fan}"] = fan_target + RNG.normal(0, 30)
        # Temperatures rise (chip exhaust hits faster)
        temp_rise = progress * 18.0
        for j in range(1, 5):
            df.loc[idx, f"temp{j}"]   = df.loc[idx, f"temp{j}"]   + temp_rise * 0.6
            df.loc[idx, f"temp2_{j}"] = df.loc[idx, f"temp2_{j}"] + temp_rise
        df.loc[idx, "temp_max"] = max(
            df.loc[idx, f"temp2_{j}"] for j in range(1, 5))
        df.loc[idx, "anomaly_label"] = "anomaly"
        df.loc[idx, "anomaly_type"]  = "fan_failure"
    return df


def inject_thermal_stress(df: pd.DataFrame, start_idx: int = None,
                           duration: int = 50) -> pd.DataFrame:
    """Ambient temperature rises (e.g. AC failure)."""
    df = df.copy()
    if start_idx is None:
        start_idx = len(df) // 2
    end_idx = min(start_idx + duration, len(df))

    for i, idx in enumerate(range(start_idx, end_idx)):
        progress = (i + 1) / duration
        temp_rise = progress * 12.0
        for j in range(1, 5):
            df.loc[idx, f"temp{j}"]   = df.loc[idx, f"temp{j}"]   + temp_rise * 0.7
            df.loc[idx, f"temp2_{j}"] = df.loc[idx, f"temp2_{j}"] + temp_rise
        df.loc[idx, "temp_max"] = max(df.loc[idx, f"temp2_{j}"] for j in range(1, 5))
        # Fans speed up to compensate
        df.loc[idx, "fan1"] = df.loc[idx, "fan1"] + temp_rise * 25
        df.loc[idx, "fan2"] = df.loc[idx, "fan2"] + temp_rise * 25
        df.loc[idx, "anomaly_label"] = "anomaly"
        df.loc[idx, "anomaly_type"]  = "thermal_stress"
    return df


def inject_voltage_instability(df: pd.DataFrame, board: int = 1,
                                 start_idx: int = None, duration: int = 30) -> pd.DataFrame:
    """PSU instability — voltage on one board fluctuates."""
    df = df.copy()
    if start_idx is None:
        start_idx = len(df) // 2
    end_idx = min(start_idx + duration, len(df))

    for idx in range(start_idx, end_idx):
        df.loc[idx, f"voltage{board}"] = 10.11 + RNG.normal(0, 0.35)
        # Hardware errors spike with voltage instability
        df.loc[idx, f"chain_hw{board}"] = int(RNG.poisson(15))
        df.loc[idx, "anomaly_label"] = "anomaly"
        df.loc[idx, "anomaly_type"]  = "voltage_instability"
    return df


def inject_frequency_throttle(df: pd.DataFrame, board: int = 2,
                                start_idx: int = None, duration: int = 35) -> pd.DataFrame:
    """Chip overheating triggers firmware to drop frequency."""
    df = df.copy()
    if start_idx is None:
        start_idx = len(df) // 2
    end_idx = min(start_idx + duration, len(df))

    for i, idx in enumerate(range(start_idx, end_idx)):
        progress = (i + 1) / duration
        new_freq = 200 - progress * 30
        df.loc[idx, f"frequency{board}"] = new_freq
        # Hashrate on that board drops accordingly
        df.loc[idx, f"chain_rate{board}"] = df.loc[idx, f"chain_rate{board}"] * (new_freq / 200)
        df.loc[idx, "GHS 5s"] = sum(df.loc[idx, f"chain_rate{j}"] for j in range(1, 5))
        # Chip temp elevated
        df.loc[idx, f"temp2_{board}"] = df.loc[idx, f"temp2_{board}"] + 12
        df.loc[idx, "anomaly_label"] = "anomaly"
        df.loc[idx, "anomaly_type"]  = "frequency_throttle"
    return df


def inject_pool_reject_spike(df: pd.DataFrame, start_idx: int = None,
                                duration: int = 25) -> pd.DataFrame:
    """Pool connectivity issue — hashrate fine, rejections spike."""
    df = df.copy()
    if start_idx is None:
        start_idx = len(df) // 2
    end_idx = min(start_idx + duration, len(df))
    for idx in range(start_idx, end_idx):
        df.loc[idx, "Device Rejected%"] = 25.0 + RNG.normal(0, 4)
        df.loc[idx, "no_matching_work"] = int(RNG.poisson(40))
        df.loc[idx, "anomaly_label"] = "anomaly"
        df.loc[idx, "anomaly_type"]  = "pool_reject_spike"
    return df


def generate_dataset(n_normal_hours: int = 48, n_anomaly_events: int = 12,
                     output_path: str = None) -> pd.DataFrame:
    """
    Generate a complete labeled dataset.
    n_normal_hours hours of normal operation at 30s intervals.
    n_anomaly_events random anomalies of various types injected.
    """
    print(f"Generating {n_normal_hours} hours of normal operation...")
    start = datetime(2024, 1, 1, 0, 0, 0)
    df = generate_normal_hour(start, samples=int(n_normal_hours * 120),
                               ambient_c=22.0)

    print(f"Injecting {n_anomaly_events} anomaly events...")
    anomaly_funcs = [
        ("chip_degradation",     inject_chip_degradation),
        ("fan_failure",          inject_fan_failure),
        ("thermal_stress",       inject_thermal_stress),
        ("voltage_instability",  inject_voltage_instability),
        ("frequency_throttle",   inject_frequency_throttle),
        ("pool_reject_spike",    inject_pool_reject_spike),
    ]

    used_ranges = []
    for i in range(n_anomaly_events):
        name, func = anomaly_funcs[i % len(anomaly_funcs)]
        # Pick a random non-overlapping start
        for _ in range(50):
            start_idx = int(RNG.uniform(120, len(df) - 120))
            if not any(abs(start_idx - u) < 80 for u in used_ranges):
                used_ranges.append(start_idx)
                break
        df = func(df, start_idx=start_idx)
        print(f"  Injected {name} at index {start_idx}")

    if output_path:
        df.to_csv(output_path, index=False)
        print(f"\nSaved to {output_path}")
        print(f"Total samples: {len(df)}")
        print(f"Normal:  {(df['anomaly_label']=='normal').sum()}")
        print(f"Anomaly: {(df['anomaly_label']=='anomaly').sum()}")
        print(f"Anomaly types: {df['anomaly_type'].value_counts().to_dict()}")
    return df


if __name__ == "__main__":
    df = generate_dataset(
        n_normal_hours=48,
        n_anomaly_events=12,
        output_path=str(DATA_DIR / "miner_telemetry_synthetic.csv"),
    )
