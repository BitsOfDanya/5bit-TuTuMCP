#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="$ROOT_DIR/.local"
LOG_DIR="$RUNTIME_DIR/logs"
PIDS=()
NAMES=()
START_FRONTEND=true

require_file() {
  if [[ ! -e "$1" ]]; then
    echo "Missing ${1#"$ROOT_DIR/"}. Run: make setup"
    exit 1
  fi
}

assert_port_free() {
  local port="$1"
  local service="$2"
  if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Port $port is already in use; cannot start $service."
    exit 1
  fi
}

start_service() {
  local name="$1"
  local directory="$2"
  shift 2
  (
    cd "$ROOT_DIR/$directory"
    exec "$@"
  ) >"$LOG_DIR/$name.log" 2>&1 &
  PIDS+=("$!")
  NAMES+=("$name")
  echo "Starting $name (log: .local/logs/$name.log)"
}

wait_for() {
  local name="$1"
  local url="$2"
  local attempts=60
  while (( attempts > 0 )); do
    if curl --fail --silent --show-error "$url" >/dev/null 2>&1; then
      echo "Ready: $name"
      return 0
    fi
    attempts=$((attempts - 1))
    sleep 0.5
  done
  echo "$name did not become ready: $url"
  tail -n 40 "$LOG_DIR/$name.log" || true
  return 1
}

cleanup() {
  trap - EXIT INT TERM
  if (( ${#PIDS[@]} > 0 )); then
    kill "${PIDS[@]}" >/dev/null 2>&1 || true
    wait "${PIDS[@]}" >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT INT TERM

require_file "$ROOT_DIR/backend/.venv/bin/python"
require_file "$ROOT_DIR/ai-service/.venv/bin/python"
require_file "$ROOT_DIR/constraint-negotiator/.venv/bin/python"
require_file "$ROOT_DIR/smart-trip-tracker/backend/.venv/bin/python"
require_file "$ROOT_DIR/trip-rescue/.venv/bin/python"
require_file "$ROOT_DIR/frontend/node_modules/.bin/vite"

assert_port_free 8010 "constraint-negotiator"
assert_port_free 8020 "ai-service"
assert_port_free 8000 "backend"
assert_port_free 8001 "smart-trip-tracker"
assert_port_free 8030 "trip-rescue"
if lsof -nP -iTCP:5173 -sTCP:LISTEN >/dev/null 2>&1; then
  if curl --fail --silent --show-error http://localhost:5173/ >/dev/null 2>&1; then
    START_FRONTEND=false
    echo "Reusing frontend already running on port 5173"
  else
    echo "Port 5173 is occupied, but the existing process is not a healthy frontend."
    exit 1
  fi
fi

mkdir -p "$LOG_DIR"
(
  cd "$ROOT_DIR/backend"
  .venv/bin/python -m alembic upgrade head
)

start_service \
  "constraint-negotiator" \
  "constraint-negotiator" \
  .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8010
start_service \
  "ai-service" \
  "ai-service" \
  .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8020
start_service \
  "smart-trip-tracker" \
  "smart-trip-tracker/backend" \
  .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
start_service \
  "trip-rescue" \
  "trip-rescue" \
  .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8030
start_service \
  "backend" \
  "backend" \
  .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
if [[ "$START_FRONTEND" == true ]]; then
  start_service \
    "frontend" \
    "frontend" \
    npm run dev -- --host 127.0.0.1 --port 5173
fi

wait_for "constraint-negotiator" "http://127.0.0.1:8010/health"
wait_for "ai-service chain" "http://127.0.0.1:8020/ready"
wait_for "smart-trip-tracker" "http://127.0.0.1:8001/health"
wait_for "trip-rescue" "http://127.0.0.1:8030/health"
wait_for "backend chain" "http://127.0.0.1:8000/ready"
wait_for "frontend" "http://localhost:5173/"

echo
echo "Local chain is ready: http://localhost:5173"
echo "Run 'make smoke' in another terminal for an end-to-end agent request."
echo "Press Ctrl+C to stop all services."

while true; do
  for index in "${!PIDS[@]}"; do
    if ! kill -0 "${PIDS[$index]}" >/dev/null 2>&1; then
      echo "${NAMES[$index]} stopped unexpectedly."
      tail -n 40 "$LOG_DIR/${NAMES[$index]}.log" || true
      exit 1
    fi
  done
  sleep 1
done
