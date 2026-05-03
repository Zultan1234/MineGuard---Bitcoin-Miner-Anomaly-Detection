# Miner Monitor — ML Pipeline Documentation

## What this is

An unsupervised anomaly detection system for ASIC cryptocurrency miners (Antminer L3+, S9, S19, S21, Whatsminer M30). Continuously monitors hardware telemetry (45+ fields per miner) and flags faults in real time with explanations.

## The ML problem

**Type:** Unsupervised time-series anomaly detection.

**Why unsupervised:** Real-world labeled miner-fault datasets do not exist at sufficient quality. We cannot ask operators to label every anomaly retroactively. The model must learn what "normal" looks like for each specific miner from its own data.

**Why this is hard:**
- Each individual miner has a different baseline (chip count, ambient temp, firmware tuning)
- Anomalies are rare — a healthy miner produces 99%+ normal readings
- Faults are multivariate — one feature out of range may not matter, but two together does
- Faults span timescales — voltage instability is instantaneous, chip degradation takes hours

## Approach

We deploy a **hybrid two-model anomaly detector** with explainability:

1. **Isolation Forest** — fast tree-based detector for point anomalies (single-reading outliers)
2. **LSTM Autoencoder** — sequence reconstruction for temporal anomalies (gradual drifts)
3. **SHAP TreeExplainer** — per-anomaly explanations (which features triggered the alert)
4. **Rule-based safeguard** — physics-aware absolute limits as a backstop

Score combination: an event is anomalous if either model flags it. Severity comes from the combined score and rule-based status.

## Why these models

| Approach | Why chosen |
|---|---|
| **Isolation Forest** | Best F1 on tabular data with mixed feature types. No assumption about data distribution. Fast inference (<10ms on 49 features). Tree structure enables SHAP. |
| **LSTM Autoencoder** | Captures temporal patterns — fan slowdown over many minutes, gradual chip degradation. A point detector would miss these. |
| **SHAP TreeExplainer** | Model-faithful attributions — tells us *exactly* which features drove the score, not approximations. Operator gets actionable info. |
| **Rules as backstop** | ML can drift or have edge cases. Hard physical limits (chip temp > 90°C is always RED) catch things ML might miss while rebuilding trust during deployment. |

## Synthetic data

Located in `notebooks/00_synthetic_data_generator.py`. Generates realistic L3+ telemetry:

- 48 hours of normal operation at 30-second intervals (5760 samples)
- 12 injected anomaly events across 6 fault types
- Realistic noise, correlations, and physical responses (e.g. fans speeding up when chips heat up)
- Each anomaly has a ground-truth label and type for evaluation

**6 fault types modeled:**

| Type | Symptoms in data | Real-world cause |
|---|---|---|
| `chip_degradation` | `chain_acn` decreases, `chain_rate` drops, `chain_hw` spikes | Chip wear or solder failure |
| `fan_failure` | `fan{1,2}` RPM drops, temperatures rise | Bearing failure, dust |
| `thermal_stress` | All temps rise together, fans speed up | Ambient temperature or cooling system failure |
| `voltage_instability` | `voltage` fluctuates, `chain_hw` spikes | PSU degradation, brownout |
| `frequency_throttle` | `frequency` drops, `chain_rate` follows, chip temp elevated | Firmware throttle response to overheating |
| `pool_reject_spike` | `Device Rejected%` and `no_matching_work` jump, hardware fields normal | Pool or network connectivity issue |

## Notebooks

| # | Notebook | Purpose |
|---|---|---|
| 0 | `00_synthetic_data_generator.py` | Generate the labeled dataset |
| 1 | `01_eda.ipynb` | Distributions, correlations, anomaly visualization |
| 2 | `02_feature_engineering.ipynb` | Domain features, rolling features, MI ranking |
| 3 | `03_model_selection.ipynb` | Compare 5 models × 3 feature sets, pick winner |
| 4 | `04_evaluation.ipynb` | Per-fault detection rate, latency, FP rate, vs rule baseline |
| 5 | `05_explainability.ipynb` | SHAP + LSTM reconstruction error explanations |
| 6 | `06_predictive_maintenance.ipynb` | Forward-looking proof of concept (research-grade) |

## Performance

Evaluated on a held-out test set (30% of synthetic data, 1,728 samples with 144 anomalies).

| Metric | Hybrid Model | Rule-Based Baseline | Improvement |
|---|---|---|---|
| ROC-AUC | ~0.97 | 0.78 | +24% |
| PR-AUC | ~0.92 | 0.62 | +48% |
| F1 (best threshold) | ~0.88 | 0.69 | +28% |
| False positive rate | <2% | 8% | 4× lower |
| Detection latency (median) | 30-90s | 60-120s | ~2× faster |

The improvement on the rule-based baseline is most dramatic for **multivariate faults** like fan failure — where a single fan dropping 20% might not trip a threshold but combined with rising temperatures it is clearly anomalous. Rules cannot capture this; ML can.

## Production code mapping

| Notebook concept | Production file |
|---|---|
| Domain feature engineering | `backend/ml/preprocessing/features.py` |
| Standardization preprocessor | `backend/ml/preprocessing/scaler.py` |
| Isolation Forest with thresholds | `backend/ml/isolation_forest.py` |
| LSTM Autoencoder | `backend/ml/lstm_autoencoder.py` |
| SHAP explainer | `backend/ml/explainer.py` |
| Statistical baseline | `backend/ml/baseline.py` |
| Training orchestration | `backend/ml/trainer.py` |
| Physics-aware rules | `backend/rules/safety_rules.py` |

## Limitations and honest caveats

1. **Synthetic evaluation:** model is evaluated on synthetic data. Production performance may differ. The rule-based baseline is calibrated to the same data so the *relative* improvement is reliable.
2. **Cold start:** before training, the system uses conservative absolute fallback rules. After 30+ samples (15 minutes at 30s polling), the ML kicks in.
3. **Per-miner calibration:** the model trains on each miner individually because each has different baselines. A model trained on one miner does not transfer to another without retraining.
4. **Concept drift:** if a miner's normal behavior changes (firmware update, hardware swap, repair), the model needs retraining. We provide a manual "retrain" button.
5. **Predictive maintenance (notebook 6):** is a methodology demonstration. Real predictive maintenance needs months of real failure data, not 12 synthetic events.

## How to run the notebooks

```bash
cd notebooks
pip install pandas numpy matplotlib seaborn scikit-learn shap torch openpyxl jupyter
python 00_synthetic_data_generator.py     # creates data/miner_telemetry_synthetic.csv
jupyter notebook                            # then open each .ipynb in order
```

## Why we chose to build our own data

When researching this problem we found:
- Public mining datasets (e.g. Bitcoin difficulty, hashrate aggregates) are pool-level not device-level
- Manufacturer telemetry archives are proprietary
- The few public miner logs lack ground-truth fault labels at sample-level granularity

Synthetic data is the **standard methodology for unsupervised anomaly detection evaluation** in industrial ML. Without ground-truth labels the metrics (precision, recall) cannot be computed. The injected faults are based on real failure modes documented in mining hardware repair forums and Antminer service manuals. The physical model (heat transfer, fan PID, chip TDP) reflects published L3+ specifications.

## What this beats

- **Threshold-based monitoring** (HiveOS, Awesome Miner default alerts): catches obvious failures, misses gradual ones, drowns operators in false positives.
- **Single-feature anomaly detection**: misses multivariate signatures like fan-failure-induced thermal rise.
- **Pure deep learning**: better than what we deploy on huge datasets, but for per-miner training (limited samples) Isolation Forest matches or beats LSTM-only and is 100× faster.

## What's next

If we had unlimited time:
- LSTM autoencoder per-feature reconstruction error (currently aggregate)
- Active learning loop — operator confirms/denies anomalies, model retrains
- Cross-miner transfer learning — pre-train on aggregated normal patterns, fine-tune per miner
- Fault-type classification once enough labeled real anomalies exist
- Survival analysis for true predictive maintenance with confidence intervals
