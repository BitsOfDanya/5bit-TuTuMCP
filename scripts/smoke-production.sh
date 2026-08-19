#!/bin/sh
set -eu

base_url=${1:-}
if [ -z "$base_url" ]; then
  echo "Usage: $0 https://travel.example.com" >&2
  exit 1
fi

base_url=${base_url%/}
curl --fail --silent --show-error --retry 10 --retry-all-errors --retry-delay 2 \
  "$base_url/health" >/dev/null
curl --fail --silent --show-error --retry 10 --retry-all-errors --retry-delay 2 \
  "$base_url/ready" >/dev/null
curl --fail --silent --show-error --retry 10 --retry-all-errors --retry-delay 2 \
  "$base_url/" >/dev/null

echo "Production smoke check passed: $base_url"
