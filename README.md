# MineGuard — ASIC Miner Anomaly Detection

> **Team 6** | Intelligent real-time monitoring for small crypto farms — detects hardware anomalies before they cause costly downtime.

A monitoring dashboard for ASIC cryptocurrency miners. Tracks hashrate, temperatures, and fan health in real time, learns what *normal* looks like for your specific hardware, and alerts you the moment something goes wrong — before it becomes an expensive repair.

---

## Why MineGuard?

This project was born from a real problem. A small crypto farm owner in Lebanon described how a single miner failure could mean **weeks or months of downtime** — not because the repair is complex, but because finding a qualified technician locally is extremely difficult. Every day offline is lost revenue, since miners must run 24/7 to be profitable.

Simple threshold alerts (e.g. "alert if temp > 90°C") miss the subtle early warning signs: a slowly burning chip causing voltage spikes, gradual board imbalance, or a fan starting to degrade. MineGuard uses machine learning to detect these patterns **before** they escalate into full failures — and its built-in AI chatbot can even guide the owner through self-repair when possible.

---

## Demo

**Fan blockage anomaly detected (YELLOW alert):**

<img width="795" height="430" alt="Fan blockage anomaly" src="https://github.com/user-attachments/assets/be08a1cd-e4ad-4fad-82f0-6b48015ddfa4" />

**Chatbot diagnosing the fan issue:**

<img width="818" height="430" alt="Chatbot fan diagnosis" src="https://github.com/user-attachments/assets/b2b2e053-46cb-486f-8bef-df610e0ed7b6" />

**Normal operation (GREEN):**

<img width="791" height="423" alt="Normal operation" src="https://github.com/user-attachments/assets/0e88f336-ecc7-4ff9-ab2f-cd1d5a07475d" />

---

## Features

- **Universal miner support** — works with Antminer (L3+, S9, S19, S21+), Whatsminer M30, and any miner with a cgminer-compatible TCP API on port 4028
- **Two-tier anomaly detection:**
  - *Tier 1:* Isolation Forest — real-time scoring on every poll
  - *Tier 2:* LSTM Autoencoder — deep temporal pattern detection every 5 minutes
- **Rule-based safety engine** — instant RED alerts for overheating, fan failure, zero hashrate
- **Traffic-light dashboard** — GREEN / YELLOW / RED status per miner with live WebSocket updates
- **AI chatbot** — powered by Google Gemini (free API key), uses live miner data to diagnose issues and suggest fixes
- **Data import / export** — export your collected data and trained model, import them on another machine
- **No cloud dependency** — all telemetry and models stored locally on your machine

---

## How It Works

### Machine Learning Pipeline

MineGuard trains on **29 features** extracted from your miner's API:

**14 raw features:** total hashrate (`GHS 5s`), PCB inlet temperatures (`temp1`, `temp3`, `temp4`), chip junction temperatures (`temp2_1`–`temp2_4`), fan speeds (`fan1`, `fan2`), and per-board hashrate (`chain_rate1`–`chain_rate4`).

**15 derived features:** hardware error rates per interval (`Hardware Errors_rate`, `chain_hw1_rate`–`chain_hw3_rate`), board hashrate deviation from mean (`chain_dev1`–`chain_dev4`), board imbalance index (`board_imbalance`), thermal ratio (`thermal_ratio`), fan-to-temperature ratio (`fan_temp_ratio`), and chip-to-PCB temperature deltas per board (`chip_pcb_delta1`–`chip_pcb_delta4`).

Cumulative counters, running averages, hardware constants, and pool metrics were deliberately excluded to prevent data leakage and noise.

### Training Protocol

1. The system collects baseline telemetry during normal operation (12+ hours recommended, ~2,880+ readings at 30s intervals)
2. Isolation Forest trains on 100% of this data, with anomaly threshold set at the **95th percentile** of training scores
3. LSTM Autoencoder trains on sliding windows of 20 timesteps, with reconstruction error threshold at the **95th percentile**
4. After training, the system monitors live data in real time

### Evaluation Results

Evaluated on a 70/30 chronological split (not shuffled, to preserve temporal order) against synthetic data with injected fault scenarios:

| Metric | Score |
|--------|-------|
| ROC-AUC | ~0.97 |
| PR-AUC | ~0.92 |
| F1 (optimal threshold) | ~0.88 |
| False positive rate (normal ops) | < 2% |
| Detection latency (fan blockage test) | < 60 seconds |

### Real Fault Test

We physically blocked the intake fan on a live **Antminer L3+ Hiveon**. Within 60 seconds:
- `fan1` RPM dropped ~35%
- Chip temperatures began rising across all boards
- Anomaly score climbed from ~5% to ~65%
- System identified: *"Probable cooling system issue"* with `fan1`, `thermal_ratio`, and `chip_pcb_delta4` as top contributing features

### Known Limitations

- **Miner restart transient:** The first ~30 seconds after a miner restart may produce one false spike. Mitigated by requiring the LSTM window to fill before scoring begins.
- **Very slow degradation:** Losing one chip per week produces changes too gradual for the 30-sample window to catch immediately. The system eventually detects it through `chain_dev` and `board_imbalance` shifting over days.
- **Single miner tested:** All real-hardware testing was performed on one Antminer L3+. Results on other models may vary.
- **Windows only:** The `start.bat` launcher is Windows-specific. Docker Compose works cross-platform for advanced users.

### Status Logic

```
if any RED rule triggered      → status = RED    (critical: overheating, fan stopped, zero hashrate)
elif ML anomaly OR YELLOW rule → status = YELLOW  (warning: unusual pattern detected)
else                           → status = GREEN   (all normal)
```

---

## Requirements

| Component | Version |
|-----------|---------|
| Python | 3.13 |
| Node.js | 18+ |
| NPM | comes with Node.js |

All three must be added to your system **PATH** for `start.bat` to work out of the box.

**Minimum hardware:** Runs on a standard laptop (tested on a ThinkPad with 16 GB RAM, no GPU required).

---

## Quick Start (Windows)

### Step 1 — Download and extract

Download the compressed project file and extract it to a folder of your choice.

<img width="568" height="93" alt="Extract files" src="https://github.com/user-attachments/assets/ba6edc7a-917f-425d-8bf2-00d4bf259be1" />

### Step 2 — (Optional) Set up the AI Chatbot

If you want the AI chatbot to diagnose your miners, you need a free Google Gemini API key:

1. Go to [https://aistudio.google.com/api-keys](https://aistudio.google.com/api-keys) and create a free key
2. Navigate to `..\miner-monitor\backend\data\`
3. Create a text file named `gemini_key.txt`
4. Paste your API key into the file and save

<img width="616" height="185" alt="Create gemini_key.txt" src="https://github.com/user-attachments/assets/f212ca4e-9c89-4b87-8aa8-7adbdf0651bb" />

<img width="761" height="112" alt="Paste API key" src="https://github.com/user-attachments/assets/1b504ecf-ad5c-4a8f-afbb-05a8ade4f1c5" />

> The chatbot is entirely optional. Without it, all monitoring and anomaly detection features still work fully.

### Step 3 — Run the launcher

Open the `miner-monitor` folder and double-click `start.bat`. If Windows shows a security warning, click **Run anyway**.

<img width="498" height="274" alt="Run start.bat" src="https://github.com/user-attachments/assets/02df93af-7a64-4ec6-93d5-4e7a69776e4b" />

### Step 4 — Wait for installation

A CMD window will open and automatically install the required Python packages. **Do not close this window.** This may take a few minutes on first run.

<img width="862" height="449" alt="Installation in progress" src="https://github.com/user-attachments/assets/5a58f236-b19b-410f-86ea-0e543c1ddeaf" />

If the window closes before finishing, simply run `start.bat` again.

### Step 5 — Configure firewall (if needed)

If you cannot access the dashboard from another device on the network, you may need to allow ports **5001** (frontend) and **5002** (backend) through Windows Defender Firewall.

Set both **inbound** and **outbound** rules for TCP on these ports:

<img width="787" height="88" alt="Firewall ports" src="https://github.com/user-attachments/assets/6b2b9796-3703-4587-8430-70e27b7b915f" />

<img width="534" height="436" alt="Firewall rule 1" src="https://github.com/user-attachments/assets/b8650609-3203-40a5-a92c-b0ddc9962d70" />

<img width="527" height="429" alt="Firewall rule 2" src="https://github.com/user-attachments/assets/1f708869-f687-45e0-ae57-c75dd632ee33" />

<img width="535" height="428" alt="Firewall rule 3" src="https://github.com/user-attachments/assets/6a8bad64-4f87-4345-ad1a-797160709f0b" />

### Step 6 — Add your miners

The server must be on the **same local network** as your miners to reach their API.

To find your miners' IP addresses:
- Check your router's connected devices list
- Or run `arp -a` in CMD (works if you have previously accessed the miner from this computer)

<img width="938" height="431" alt="Dashboard view" src="https://github.com/user-attachments/assets/8737eba2-b816-4ac0-8ae5-671cfd126a83" />

In the dashboard, click **Add Miner** and enter:
- The miner's IP address
- The API port (most Antminer models use **4028**)
- Your preferred polling interval (we used 15 seconds during testing)

<img width="525" height="296" alt="Add miner form" src="https://github.com/user-attachments/assets/26476e47-0535-4b83-9ac1-c9530287806a" />

<img width="569" height="389" alt="Polling interval setting" src="https://github.com/user-attachments/assets/bbecde08-8ba0-42d8-8925-f0679a4edb2d" />

---

## Training the Model

1. Go to the **Training** tab in the dashboard
2. Make sure your miner is online and actively collecting data
3. Leave the system running during **normal operation** — no faults, no restarts
4. Wait until you have enough data points (2,000–3,000+ recommended; 12 hours of collection is ideal)
5. Click **Train Now** when ready

The model will learn what normal behavior looks like for your specific miner. After training, live monitoring begins automatically.

---

## Anomaly Detection

Once trained, MineGuard monitors every poll in real time:

| Status | Meaning |
|--------|---------|
| 🟢 **GREEN** | All values within learned baseline, no rule violations |
| 🟡 **YELLOW** | ML anomaly detected — unusual pattern flagged, investigate |
| 🔴 **RED** | Critical rule triggered — overheating, fan stopped, or zero hashrate |

Each miner card shows the anomaly score, top contributing features, and a live sparkline chart.

---

## AI Chatbot

If you set up the Gemini API key, the chatbot is available on every miner card and in the **Chat** tab. It has full context of the miner's current telemetry, anomaly scores, and which features are deviating — and can suggest diagnostic steps or self-repair actions.

Example questions:
- *"Why is this miner yellow?"*
- *"What does a high chip_pcb_delta mean?"*
- *"Should I be worried about these hardware errors?"*
- *"What can I check myself before calling a technician?"*

> **Privacy note:** The chatbot sends only anonymized metric summaries to the Gemini API — never raw telemetry, miner IPs, or personally identifiable information. All other data stays entirely on your local machine.

---

## Importing and Exporting Data

You can export your collected telemetry data and trained model, and import them on a different machine — useful for backup or sharing datasets.

<img width="498" height="384" alt="Import/export panel" src="https://github.com/user-attachments/assets/1b08d6c6-ac9d-4a80-8744-1ab44f3ea24c" />

**Data storage locations:**
- Telemetry database: `backend/data/miner_monitor.db` (SQLite)
- Trained models: `backend/data/models/*.pkl`

To fully remove all data, delete the `miner-monitor` folder.

---

## Sample Dataset

We provide two datasets collected from a real Antminer L3+ for testing and evaluation:

| File | Description | Size |
|------|-------------|------|
| `data/normal_operation.csv` | Clean baseline data, normal mining | ~13,000 readings |
| `data/anomaly_scenarios.csv` | Same data with injected fault events at the end | ~14,000 readings |

The anomaly dataset includes 6 fault types (fan blockage, chip overheating, board imbalance, hardware error spike, hashrate drop, thermal runaway) generated using a physics-based model calibrated against real L3+ baseline values.

---

## Docker Deployment (Advanced)

For users comfortable with Docker:

```bash
docker compose up --build
```

- Frontend: [http://localhost:3000](http://localhost:3000)
- Backend API: [http://localhost:8000](http://localhost:8000)
- API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

> Docker has been tested on Windows. Linux and macOS compatibility is not guaranteed.

---

## Project Structure

```
miner-monitor/
├── backend/
│   ├── api/
│   │   ├── main.py                  # FastAPI app, lifespan, CORS
│   │   └── routes/
│   │       ├── miners.py            # Miner CRUD + discovery + status
│   │       ├── training.py          # Learning phase + train-now
│   │       ├── anomaly.py           # Anomaly event queries
│   │       ├── chat.py              # Gemini chatbot + streaming
│   │       ├── presets.py           # Preset CRUD
│   │       └── ws.py                # WebSocket + live callbacks
│   ├── collector/
│   │   ├── socket_client.py         # TCP socket → JSON, field discovery
│   │   ├── poller.py                # APScheduler background polling
│   │   └── preset_registry.py       # Built-in + user-defined presets
│   ├── ml/
│   │   ├── isolation_forest.py      # Tier-1: real-time anomaly scoring
│   │   ├── lstm_autoencoder.py      # Tier-2: deep temporal patterns
│   │   ├── baseline.py              # Statistical baseline + deviation report
│   │   └── trainer.py               # Training orchestrator + model registry
│   ├── rules/
│   │   └── safety_rules.py          # Threshold rules → RED/YELLOW
│   ├── chatbot/
│   │   └── gemini_client.py         # Gemini API, context builder
│   ├── db/
│   │   ├── models.py                # SQLAlchemy ORM models
│   │   └── timeseries.py            # DB session + query helpers
│   └── data/                        # Local database + trained models (gitignored)
├── frontend/
│   └── src/
│       ├── pages/
│       │   ├── Dashboard.jsx        # Live miner grid
│       │   ├── Setup.jsx            # Add miner wizard
│       │   ├── Training.jsx         # Learning phase + baseline stats
│       │   └── Chat.jsx             # AI chatbot interface
│       ├── components/
│       │   ├── MinerCard.jsx        # Per-miner status tile + sparkline
│       │   ├── AnomalyChart.jsx     # Recharts time-series chart
│       │   ├── FeatureChecklist.jsx # Field selector
│       │   └── StatusBadge.jsx      # GREEN/YELLOW/RED badge
│       ├── hooks/
│       │   ├── useLiveSocket.js     # WebSocket with auto-reconnect
│       │   └── useMiners.js         # Shared miner state + WS patches
│       └── utils/
│           └── api.js               # All fetch() calls + stream helper
├── data/
│   ├── normal_operation.csv         # ~13k readings from real L3+
│   └── anomaly_scenarios.csv        # ~14k readings with injected faults
├── notebooks/
│   └── 04_evaluation.ipynb          # Full evaluation: ROC-AUC, F1, PR-AUC
├── docker-compose.yml
├── start.bat                        # Windows one-click launcher
└── README.md
```

---

## API Reference

Full interactive docs available at [http://localhost:5002/docs](http://localhost:5002/docs) once running.

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/miners/discover` | Discover all fields from a miner IP |
| POST | `/api/miners/` | Register a new miner |
| GET | `/api/miners/{id}/status` | Get current GREEN/YELLOW/RED status |
| GET | `/api/miners/{id}/telemetry` | Get historical telemetry readings |
| POST | `/api/training/{id}/start` | Start learning phase |
| POST | `/api/training/{id}/train-now` | Train immediately on collected data |
| GET | `/api/training/{id}/baseline` | Get computed baseline statistics |
| GET | `/api/anomaly/{id}/events` | Get historical anomaly events |
| POST | `/api/chat/stream` | Streaming AI chat (SSE) |
| WS | `/ws/live` | WebSocket live telemetry feed |

---

## Supported Miners

| Model | Firmware | Notes |
|-------|----------|-------|
| Antminer L3+ Hiveon | cgminer | **Tested with real hardware** |
| Antminer S9 | bmminer | Compatible via cgminer API |
| Antminer S19 / S19 Pro | bmminer 2.x | Compatible via cgminer API |
| Antminer S21 / S21+ | bmminer 3.x | Compatible via cgminer API |
| Whatsminer M30S | btminer | Compatible via cgminer API |
| Any cgminer API device | any | Port 4028 required |

---

## Responsible AI Notes

- **Explainability:** Every anomaly report names the top contributing features and their deviation from baseline, so you always know *why* an alert was raised — not just that it was.
- **Privacy:** All telemetry is stored locally. The optional Gemini chatbot sends only anonymized metric summaries — never raw data, IPs, or identifiers.
- **Limitations transparency:** The system is trained on a single Antminer L3+ model. Detection performance on other hardware may vary. Users should retrain the model on their own hardware for best results.
- **No automated actions:** MineGuard only alerts — it never automatically shuts down, overrides, or modifies miner settings.

---

<!-- ============================================================
     TELEGRAM ALERTS SECTION
     This section can be removed if the feature is not shipped.
     ============================================================ -->

## 📱 Telegram Alerts

MineGuard can send an instant Telegram message to your phone the moment an anomaly is detected on any of your miners — so you don't need to keep the dashboard open to stay informed.

**What you receive:**
- A message when any miner changes to YELLOW or RED status
- The miner name, alert type, and top contributing features
- An all-clear message when the status returns to GREEN

<img width="1080" height="1403" alt="Telegram notification" src="https://github.com/user-attachments/assets/732da950-87e6-4e4e-b502-58219e72d0e0" />

<img width="1080" height="2185" alt="Telegram message showing yellow state" src="https://github.com/user-attachments/assets/35f8b11f-39ba-4008-8761-6d9f5430ad1d" />

### Setting Up Telegram Alerts

**Step 1 — Create a Telegram bot and get your token**

1. Open Telegram and search for **@BotFather**
2. Send the command `/newbot` and follow the prompts to name your bot
3. BotFather will give you a **bot token** that looks like: `123456789:ABCdefGhIJKlmNoPQRstuVWXyz`

<img width="574" height="245" alt="BotFather setup" src="https://github.com/user-attachments/assets/93f846bb-2d98-4a6c-9d2e-74cda39e6a10" />

**Step 2 — Get your Chat ID**

1. Start a conversation with your new bot on Telegram (send it any message)
2. Open this URL in your browser, replacing `YOUR_TOKEN` with your bot token:
   ```
   https://api.telegram.org/botYOUR_TOKEN/getUpdates
   ```
3. Find the `"id"` value inside `"chat"` in the response — that is your Chat ID

**Step 3 — Save your credentials**

Navigate to `..\miner-monitor\backend\data\` and create two text files:

| File | Contents |
|------|----------|
| `telegram_chat_token.txt` | Your bot token from BotFather |
| `telegram_chat_id.txt` | Your Chat ID from Step 2 |

These files sit alongside `gemini_key.txt` in the same folder. Restart `start.bat` after saving them.

<!-- ============================================================
     END TELEGRAM ALERTS SECTION
     ============================================================ -->

---

## License

MIT
