#!/usr/bin/env bash
# start_all.sh — Start both backend and frontend from a single terminal.
#
# Usage:  ./start_all.sh
#
# Both processes run in the background.  Use ./stop_all.sh to shut them down.
# Logs are written to data/logs/ (backend.log, frontend.log).

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

mkdir -p data/logs

# ── Backend ──────────────────────────────────────────────────────────
echo ">>> Starting HomeAI backend..."
cd "$PROJECT_DIR/backend"

if [ ! -d .venv ]; then
    echo "ERROR: backend/.venv not found. Run the setup steps in readme.txt first." >&2
    exit 1
fi

source .venv/bin/activate
nohup uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 \
    > "$PROJECT_DIR/data/logs/backend.log" 2>&1 &
BACKEND_PID=$!
echo "$BACKEND_PID" > "$PROJECT_DIR/data/.backend_pid"
echo "  Backend started (PID $BACKEND_PID) — http://localhost:8000"

# ── Frontend ─────────────────────────────────────────────────────────
echo ">>> Starting HomeAI frontend..."
cd "$PROJECT_DIR/frontend"

if [ ! -d node_modules ]; then
    echo "ERROR: frontend/node_modules not found. Run 'npm install' in frontend/ first." >&2
    exit 1
fi

nohup npm run dev \
    > "$PROJECT_DIR/data/logs/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo "$FRONTEND_PID" > "$PROJECT_DIR/data/.frontend_pid"
echo "  Frontend started (PID $FRONTEND_PID) — http://localhost:3000"

# ── Done ─────────────────────────────────────────────────────────────
cd "$PROJECT_DIR"
echo ""
echo "HomeAI is running!"
echo "  Frontend  →  http://localhost:3000"
echo "  Backend   →  http://localhost:8000"
echo "  API docs  →  http://localhost:8000/docs"
echo ""
echo "Logs:        data/logs/backend.log  |  data/logs/frontend.log"
echo "Stop:        ./stop_all.sh"
echo ""