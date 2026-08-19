#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

ensure_env_file() {
  local example_path="$1"
  local env_path="$2"
  if [[ ! -f "$env_path" ]]; then
    cp "$example_path" "$env_path"
    echo "Created ${env_path#"$ROOT_DIR/"}"
  fi
}

ensure_venv() {
  local service_dir="$1"
  if [[ ! -x "$service_dir/.venv/bin/python" ]]; then
    "$PYTHON_BIN" -m venv "$service_dir/.venv"
  fi
}

command -v "$PYTHON_BIN" >/dev/null || {
  echo "Python 3.12+ is required."
  exit 1
}
command -v npm >/dev/null || {
  echo "Node.js and npm are required."
  exit 1
}

ensure_env_file "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
ensure_env_file "$ROOT_DIR/backend/.env.example" "$ROOT_DIR/backend/.env"
ensure_env_file "$ROOT_DIR/ai-service/.env.example" "$ROOT_DIR/ai-service/.env"
ensure_env_file \
  "$ROOT_DIR/constraint-negotiator/.env.example" \
  "$ROOT_DIR/constraint-negotiator/.env"
ensure_env_file \
  "$ROOT_DIR/smart-trip-tracker/backend/.env.example" \
  "$ROOT_DIR/smart-trip-tracker/backend/.env"

ensure_venv "$ROOT_DIR/backend"
ensure_venv "$ROOT_DIR/ai-service"
ensure_venv "$ROOT_DIR/constraint-negotiator"
ensure_venv "$ROOT_DIR/smart-trip-tracker/backend"

"$ROOT_DIR/backend/.venv/bin/python" -m pip install -e "$ROOT_DIR/backend[dev]"
"$ROOT_DIR/ai-service/.venv/bin/python" -m pip install -e "$ROOT_DIR/ai-service[dev]"
"$ROOT_DIR/constraint-negotiator/.venv/bin/python" -m pip install \
  -r "$ROOT_DIR/constraint-negotiator/requirements.txt"
"$ROOT_DIR/smart-trip-tracker/backend/.venv/bin/python" -m pip install \
  -e "$ROOT_DIR/smart-trip-tracker/backend[dev]"
npm --prefix "$ROOT_DIR/frontend" ci

(
  cd "$ROOT_DIR/backend"
  .venv/bin/python -m alembic upgrade head
)

echo
echo "Local dependencies are ready."
echo "Set OPENAI_API_KEY in .env, then run: make dev"
