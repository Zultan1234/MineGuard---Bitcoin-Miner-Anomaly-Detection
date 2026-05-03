#!/usr/bin/env bash
# start_dev.sh — Start the full Miner Monitor stack in development mode
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

echo ""
echo "  ╔══════════════════════════════════╗"
echo "  ║   Miner Monitor — Dev Startup    ║"
echo "  ╚══════════════════════════════════╝"
echo ""

# ── 1. Python env ──────────────────────────────────────────────────────────
if [ ! -d "$BACKEND/.venv" ]; then
  echo "  [1/4] Creating Python virtual environment..."
  python3 -m venv "$BACKEND/.venv"
fi

echo "  [1/4] Installing Python dependencies..."
"$BACKEND/.venv/bin/pip" install -q -r "$BACKEND/requirements.txt"

# ── 2. Node modules ────────────────────────────────────────────────────────
if [ ! -d "$FRONTEND/node_modules" ]; then
  echo "  [2/4] Installing Node.js dependencies..."
  cd "$FRONTEND" && npm install --silent
fi

# ── 3. Check Ollama ────────────────────────────────────────────────────────
echo "  [3/4] Checking Ollama..."
if command -v ollama &>/dev/null; then
  if ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
    echo "         Starting Ollama in background..."
    ollama serve &>/dev/null &
    sleep 2
  fi
  # Pull Mistral if not already present
  if ! ollama list 2>/dev/null | grep -q "mistral"; then
    echo "         Pulling Mistral 7B (this takes a few minutes on first run)..."
    ollama pull mistral
  fi
  echo "         Ollama ready ✓"
else
  echo "         ⚠  Ollama not found. Install from https://ollama.ai to enable the chatbot."
fi

# ── 4. Start services ──────────────────────────────────────────────────────
echo "  [4/4] Starting services..."
echo ""
echo "  Backend  → http://localhost:8000"
echo "  Frontend → http://localhost:3000"
echo "  API docs → http://localhost:8000/docs"
echo ""
echo "  Press Ctrl+C to stop all services"
echo ""

# Run backend and frontend in parallel, kill both on Ctrl+C
trap 'kill 0' INT TERM

cd "$BACKEND"
PYTHONPATH="$ROOT" .venv/bin/uvicorn api.main:app \
  --host 0.0.0.0 --port 8000 \
  --reload --reload-dir "$BACKEND" &

cd "$FRONTEND"
npm run dev -- --port 3000 &

wait
