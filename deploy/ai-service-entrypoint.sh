#!/bin/sh
set -eu

: "${OPENAI_API_KEY:?OPENAI_API_KEY is required}"
: "${INTERNAL_API_TOKEN:?INTERNAL_API_TOKEN is required}"

exec "$@"
