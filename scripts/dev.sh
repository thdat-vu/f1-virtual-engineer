#!/bin/sh
set -eu

REPO_ROOT="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# Pre-flight: a stale `next dev` or `uvicorn` from a previous run will silently
# steal the port (Next falls back to 3001/3002, uvicorn just errors), and you
# only notice when something doesn't reload. Detect and report up front.
check_port() {
  port="$1"
  label="$2"
  pids="$(lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null || true)"
  if [ -n "$pids" ]; then
    echo "✗ Port $port ($label) is in use by:"
    # shellcheck disable=SC2086
    ps -o pid,command -p $pids 2>/dev/null || true
    echo "  Free it with: kill $pids"
    return 1
  fi
}

ports_busy=0
check_port 8000 backend  || ports_busy=1
check_port 3000 frontend || ports_busy=1
if [ "$ports_busy" -eq 1 ]; then
  echo
  echo "Refusing to start: kill the offending processes above, then retry."
  exit 1
fi

BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  echo "\nStopping dev processes..."
  if [ -n "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  if [ -n "$FRONTEND_PID" ] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
  wait 2>/dev/null || true
}

trap cleanup INT TERM EXIT

echo "Starting backend on http://localhost:8000 ..."
./scripts/run-backend.sh &
BACKEND_PID=$!

echo "Starting frontend (Next.js dev server) ..."
./scripts/run-frontend.sh &
FRONTEND_PID=$!

echo "\nDev environment is starting:"
echo "- Backend:  http://localhost:8000"
echo "- Docs:     http://localhost:8000/docs"
echo "- Frontend: http://localhost:3000"
echo "\nPress Ctrl+C to stop both."

wait "$BACKEND_PID" "$FRONTEND_PID"
