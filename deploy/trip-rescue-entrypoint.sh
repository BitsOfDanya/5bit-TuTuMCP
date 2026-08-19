#!/bin/sh
set -eu

: "${OPENAI_API_KEY:?OPENAI_API_KEY is required}"

if [ "${APP_DEBUG:-false}" != "false" ]; then
  echo "APP_DEBUG must be false in production" >&2
  exit 1
fi

exec "$@"
