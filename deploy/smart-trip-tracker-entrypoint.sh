#!/bin/sh
set -eu

if [ "${TRIP_PROVIDER:-tutu}" != "tutu" ]; then
  echo "TRIP_PROVIDER must be tutu in production" >&2
  exit 1
fi

exec "$@"
