#!/bin/sh
set -eu

: "${AUTH_SECRET_KEY:?AUTH_SECRET_KEY is required}"
: "${AI_SERVICE_TOKEN:?AI_SERVICE_TOKEN is required}"

if [ "${#AUTH_SECRET_KEY}" -lt 32 ]; then
  echo "AUTH_SECRET_KEY must contain at least 32 characters" >&2
  exit 1
fi

if [ "${AUTH_DEBUG:-false}" != "false" ]; then
  echo "AUTH_DEBUG must be false in production" >&2
  exit 1
fi

python -m alembic upgrade head
exec "$@"
