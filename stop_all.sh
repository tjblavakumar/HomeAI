#!/usr/bin/env bash
# stop_all.sh — Stop backend and frontend started by start_all.sh.
#
# Usage:  ./stop_all.sh

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
ANY_STOPPED=false

# ── Backend ──────────────────────────────────────────────────────────
if [ -f "$PROJECT_DIR/data/.backend_pid" ]; then
    PID=$(cat "$PROJECT_DIR/data/.backend_pid")
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID" 2>/dev/null
        echo "Backend (PID $PID) stopped."
        ANY_STOPPED=true
    else
        echo "Backend already stopped (PID $PID not running)."
    fi
    rm "$PROJECT_DIR/data/.backend_pid"
else
    # Fallback — look for any lingering uvicorn serving this app
    FOUND=$(pgrep -f "uvicorn app.main:app" 2>/dev/null || true)
    if [ -n "$FOUND" ]; then
        pkill -f "uvicorn app.main:app" 2>/dev/null || true
        echo "Backend stopped (pkill fallback)."
        ANY_STOPPED=true
    else
        echo "Backend not running."
    fi
fi

# ── Frontend ─────────────────────────────────────────────────────────
if [ -f "$PROJECT_DIR/data/.frontend_pid" ]; then
    PID=$(cat "$PROJECT_DIR/data/.frontend_pid")
    # Kill the npm parent process; child (next) is usually in the same
    # process group and goes down too.
    kill "$PID" 2>/dev/null
    # Also try to kill any orphaned next.js dev server
    pkill -P "$PID" 2>/dev/null || true
    echo "Frontend (PID $PID) stopped."
    ANY_STOPPED=true
    rm "$PROJECT_DIR/data/.frontend_pid"
else
    FOUND=$(pgrep -f "next dev" 2>/dev/null || true)
    if [ -n "$FOUND" ]; then
        pkill -f "next dev" 2>/dev/null || true
        echo "Frontend stopped (pkill fallback)."
        ANY_STOPPED=true
    else
        echo "Frontend not running."
    fi
fi

echo ""
if [ "$ANY_STOPPED" = true ]; then
    echo "All services stopped."
else
    echo "No services were running."
fi