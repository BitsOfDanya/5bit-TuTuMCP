#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
. "$root/scripts/production-common.sh"
env_path=$(production_env_file "$root" "${1:-}")
require_production_env "$env_path"
validate_runtime_env "$env_path" false

compose "$root" "$env_path" config --quiet
compose "$root" "$env_path" up --detach --build --remove-orphans --wait --wait-timeout 180
compose "$root" "$env_path" ps
