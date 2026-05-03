# Miner Monitor — ML-Powered ASIC Miner Anomaly Detection

Real-time monitoring system for cryptocurrency mining hardware (Antminer L3+, S9, S19, S21, Whatsminer M30) with unsupervised anomaly detection, per-feature explainability, and predictive diagnostics.

## Problem Statement

**Problem:** ASIC miners operate 24/7 in harsh environments. Hardware failures (fan degradation, chip burnout, overheating) cause costly downtime. Current monitoring tools use static thresholds that either miss gradual faults or flood operators with false alarms.

**Why ML, not simpler?** Rule-based monitoring (the non-AI baseline) cannot detect multivariate anomalies — a fan dropping 20% while temperatures rise 5°C individually looks within range but together indicates imminent cooling failure. Our Isolation Forest + LSTM hybrid catches these joint patterns. See `notebooks/04_evaluation.ipynb` for the quantitative comparison showing +28% F1 improvement.

**Users:** Mining farm operators, individual miners, hardware maintenance teams.

**Impact:** Early detection prevents chip damage ($200–$2000 per board), reduces downtime, and extends hardware lifespan.

**Success criteria:** F1 > 0.80 on synthetic test set, false positive rate < 5% during normal operation, detection latency < 2 minutes.

## Quick Start

### Option 1: Local (Windows)

```bash
# Terminal 1 — Backend
cd miner-monitor
python -m venv backend\.venv
backend\.venv\Scripts\activate
pip install -r backend/requirements.txt
set PYTHONPATH=.
set GEMINI_API_KEY=your_key_here   # optional, for chatbot
uvicorn backend.api.main:app --host 0.0.0.0 --port 5002 --reload

# Terminal 2 — Frontend
cd miner-monitor/frontend
npm install
npm run dev
```

Open http://localhost:5001

### Option 2: Docker

```bash
docker-compose up --build
```

Backend: http://localhost:5002 | Frontend: http://localhost:5001

### Option 3: Without a physical miner

1. Start the system (either option above)
2. Add a dummy miner in Setup (use any IP)
3. Go to Training → **Import Data (CSV/Excel)** → upload `notebooks/data/miner_telemetry_synthetic.csv`
4. Click **Train on existing data**
5. Click **Simulate Live Feed** → upload the same CSV → watch the dashboard react in real time

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (React + Vite, port 5001)                         │
│  Dashboard │ Setup │ Training │ Chat                        │
│  MinerCard: deviations, anomaly score, explanation          │
│  WebSocket live updates                                     │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP + WS
┌──────────────────────▼──────────────────────────────────────┐
│  Backend (FastAPI, port 5002)                               │
│                                                             │
│  Poller ──→ Rule Engine ──→ ML Pipeline (29 features)       │
│  cgminer    physics-aware    IsolationForest + LSTM AE      │
│  TCP/HTTP   thresholds       Permutation attribution        │
│                              Fusion explainer                │
│                              Failure signatures              │
│                                                             │
│  SQLite DB          Gemini 2.0 Flash Chatbot                │
└─────────────────────────────────────────────────────────────┘
```

## ML Pipeline

### Task Formulation
Unsupervised time-series anomaly detection on 29 engineered features. No labels in production — synthetic data with injected faults used for evaluation only.

### Non-AI Baseline Comparison
Per-feature threshold rules (if temp > X → alert). Compared in `notebooks/04_evaluation.ipynb`: ML achieves ~28% higher F1, 4x fewer false positives, and 2x faster detection on multivariate faults.

### Method: Hybrid Isolation Forest + LSTM Autoencoder
- **Isolation Forest** (200 trees, 5% contamination): point anomaly detection. Permutation-based feature attribution for explainability.
- **LSTM Autoencoder** (window=30, step=2): temporal anomaly detection. Per-feature reconstruction error identifies which features break temporal patterns.
- **Fusion layer**: normalized score combination, confidence from model agreement, failure signature matching, human-readable narratives.

### 29-Feature Set (validated in notebooks)

| Group | Features | Why |
|---|---|---|
| Hashrate (5) | GHS 5s, chain_rate1–4 | Primary health indicator |
| Temperatures (7) | temp1, temp3, temp4, temp2_1–4 | Chip and PCB thermal state |
| Fans (2) | fan1, fan2 | Cooling system health |
| HW Error Rates (4) | Hardware Errors_rate, chain_hw1–3_rate | Error rate per interval (delta, not cumulative) |
| Board Deviations (4) | chain_dev1–4 | Per-board hashrate vs mean |
| Derived (7) | board_imbalance, thermal_ratio, fan_temp_ratio, chip_pcb_delta1–4 | Cross-feature physics ratios |

**Excluded:** Device Rejected% (startup-decay), GHS av (startup-decay), all cumulative counters, all constants, all pool duplicates. See `feature_config.py` for full justification.

### Evaluation Protocol
- 70/30 chronological split (preserves temporal order)
- Trained on normal samples only (true unsupervised)
- Metrics: ROC-AUC, PR-AUC, F1, per-fault detection rate, detection latency
- 6 fault types: chip degradation, fan failure, thermal stress, voltage instability, frequency throttle, pool reject spike

### Error Analysis
- Fastest detection: voltage instability (~30s), slowest: gradual chip degradation (~90s)
- False positive sources: fan RPM variance, pool rejection spikes → addressed by excluding startup-decay fields
- Per-fault detection rates in notebook 04

### Limitations & Trade-offs
- Evaluated on synthetic data — production performance may differ
- Per-miner training — no cross-miner transfer learning
- Cold start: 15 min rule-only period until LSTM window fills
- LSTM requires PyTorch — graceful fallback to IF-only
- Predictive maintenance (notebook 06) is methodology PoC only

## Responsible ML

### Explainability
- Permutation-based feature attribution: measures each feature's contribution to anomaly score
- LSTM per-feature reconstruction error: identifies temporally anomalous features
- Fusion: combined ranking with confidence (high/medium/low) and failure signature matching
- Narratives: "Probable cooling system issue. Check fan bearings, clean dust filters."

### Fairness & Bias
Hardware monitoring — no human subjects. Per-miner calibration prevents bias against atypical-but-healthy configurations (e.g. miner with 67/72 chips from factory).

### Privacy
All data local (SQLite). No external transmission except optional Gemini chatbot (sends only anonymized summaries). Model files contain only statistical parameters.

### Robustness
Baseline-relative thresholds adapt to seasonal temperature shifts. Firmware updates → retrain button. Hardware replacement → retrain captures new normal.

## Results

| Metric | Hybrid Model | Rule-Based Baseline | Improvement |
|---|---|---|---|
| ROC-AUC | ~0.97 | 0.78 | +24% |
| PR-AUC | ~0.92 | 0.62 | +48% |
| F1 | ~0.88 | 0.69 | +28% |
| False positive rate | <2% | 8% | 4× lower |
| Detection latency | 30–90s | 60–120s | ~2× faster |

## Repository Structure

```
miner-monitor/
├── README.md
├── docker-compose.yml
├── backend/
│   ├── Dockerfile, requirements.txt
│   ├── api/main.py, routes/{miners,training,anomaly,chat,ws}.py
│   ├── collector/{socket_client,poller,preset_registry}.py
│   ├── ml/{feature_config,trainer,isolation_forest,lstm_autoencoder,explainer,baseline}.py
│   ├── ml/preprocessing/{features,scaler}.py
│   ├── rules/safety_rules.py
│   ├── chatbot/ollama_client.py
│   └── db/{models,timeseries}.py
├── frontend/src/
│   ├── pages/{Dashboard,Setup,Training,Chat}.jsx
│   ├── components/{MinerCard,AnomalyChart,StatusBadge}.jsx
│   └── utils/api.js
└── notebooks/
    ├── README.md
    ├── 00_synthetic_data_generator.py
    ├── 01_eda.ipynb — 07_explainability_demo.ipynb
    └── data/miner_telemetry_synthetic.csv
```

## Chatbot Setup

1. Go to https://aistudio.google.com/apikey → Create API Key (free)
2. `set GEMINI_API_KEY=your_key` before starting backend
3. Or save to `backend/data/gemini_key.txt`

## Notebooks

| # | Notebook | Purpose |
|---|---|---|
| 00 | `00_synthetic_data_generator.py` | Physics-based L3+ data with 6 fault types |
| 01 | `01_eda.ipynb` | Distributions, correlations, anomaly signatures |
| 02 | `02_feature_engineering.ipynb` | Domain features, rolling windows, MI ranking |
| 03 | `03_model_selection.ipynb` | IF vs SVM vs LOF vs LSTM vs Hybrid |
| 04 | `04_evaluation.ipynb` | Per-fault detection, latency, FP rate, vs rules |
| 05 | `05_explainability.ipynb` | SHAP + LSTM reconstruction error |
| 06 | `06_predictive_maintenance.ipynb` | Forward-looking PoC |
| 07 | `07_explainability_demo.ipynb` | Full pipeline demo with old vs new comparison |
