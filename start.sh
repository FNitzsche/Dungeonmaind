#!/usr/bin/env bash
# Start Dungeon M-AI-nd locally (backend + frontend).
# Prerequisites: Python venv at .venv, frontend deps installed, ffmpeg on PATH.
# Ollama should already be running (`ollama serve`) with the model pulled.

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

cleanup() {
  if [[ -n "${BACKEND_PID:-}" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  if [[ -n "${FRONTEND_PID:-}" ]] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

if [[ ! -f .venv/bin/activate ]]; then
  echo "Missing .venv. Run: python -m venv .venv && source .venv/bin/activate && pip install -r backend/requirements.txt" >&2
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

if [[ ! -f backend/.env ]]; then
  cp backend/.env.example backend/.env
  echo "Created backend/.env from .env.example — edit tokens if needed."
fi

if [[ ! -d frontend/node_modules ]]; then
  echo "Installing frontend dependencies..."
  (cd frontend && npm install)
fi

echo "Starting backend on http://localhost:8000 ..."
(
  cd backend
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
) &
BACKEND_PID=$!

echo "Starting frontend on http://localhost:5173 ..."
(
  cd frontend
  npm run dev -- --host 0.0.0.0
) &
FRONTEND_PID=$!

echo
echo "Dungeon M-AI-nd is starting."
echo "  Frontend: http://localhost:5173"
echo "  Backend:  http://localhost:8000"
echo "  Ensure Ollama is running: ollama serve"
echo "Press Ctrl+C to stop both services."

wait
