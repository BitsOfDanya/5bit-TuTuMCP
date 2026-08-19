#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RESPONSE_FILE="$(mktemp)"
HISTORY_FILE="$(mktemp)"
CONSTRAINT_URL="${CONSTRAINT_URL:-http://127.0.0.1:8010}"
AI_URL="${AI_URL:-http://127.0.0.1:8020}"
BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:8000}"
FRONTEND_URL="${FRONTEND_URL:-http://127.0.0.1:5173}"
trap 'rm -f "$RESPONSE_FILE" "$HISTORY_FILE"' EXIT

curl --fail --silent --show-error "$CONSTRAINT_URL/health" >/dev/null
curl --fail --silent --show-error "$AI_URL/ready" >/dev/null
curl --fail --silent --show-error "$BACKEND_URL/ready" >/dev/null
curl --fail --silent --show-error "$FRONTEND_URL/" >/dev/null

USER_ID="$(python3 -c 'import uuid; print(uuid.uuid4())')"
curl --fail --silent --show-error \
  --request POST \
  --header "Content-Type: application/json" \
  --data "{\"user_id\":\"$USER_ID\",\"message\":\"Нужен поезд из Москвы в Казань: туда 1 сентября 2026 после 10:00, обратно 5 сентября 2026, один пассажир, бюджет 30000 рублей.\"}" \
  --output "$RESPONSE_FILE" \
  "$FRONTEND_URL/api/v1/agent/chat"

python3 - "$RESPONSE_FILE" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as response_file:
    payload = json.load(response_file)

required = {
    "session_id",
    "response",
    "trip",
    "plan",
    "tools_used",
    "tool_statuses",
    "next_action",
}
missing = sorted(required - payload.keys())
if missing:
    raise SystemExit(f"Smoke response misses fields: {', '.join(missing)}")
if "negotiate_constraints" not in payload["tools_used"]:
    raise SystemExit("The full-chain request did not invoke negotiate_constraints")
constraint_status = payload["tool_statuses"].get("negotiate_constraints")
if constraint_status not in {"success", "negotiation_required", "no_options"}:
    raise SystemExit(f"Constraint negotiation failed: status={constraint_status!r}")

print("End-to-end chat passed")
print(f"session_id={payload['session_id']}")
print(f"next_action={payload['next_action']}")
print(f"tools_used={','.join(payload['tools_used'])}")
print(f"constraint_status={constraint_status}")
PY

SESSION_ID="$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["session_id"])' "$RESPONSE_FILE")"
curl --fail --silent --show-error \
  --output "$HISTORY_FILE" \
  "$FRONTEND_URL/api/v1/agent/users/$USER_ID/sessions/$SESSION_ID"

python3 - "$HISTORY_FILE" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as history_file:
    payload = json.load(history_file)

roles = [message["role"] for message in payload.get("messages", [])]
if roles != ["user", "assistant"]:
    raise SystemExit(f"Conversation was not persisted correctly: roles={roles}")
print("Conversation history persistence passed")
PY

echo "All local links are operational."
