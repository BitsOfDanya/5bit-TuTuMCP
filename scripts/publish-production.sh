#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
. "$root/scripts/production-common.sh"
env_path=$(production_env_file "$root" "${1:-}")
require_production_env "$env_path"

compose "$root" "$env_path" config --quiet
compose "$root" "$env_path" build --pull
compose "$root" "$env_path" push
