#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
. "$root/scripts/production-common.sh"
env_path=$(production_env_file "$root" "${1:-}")
require_production_env "$env_path"
validate_runtime_env "$env_path" false

timestamp=$(date -u +%Y%m%dT%H%M%SZ)
backup_name="tutumcp-$timestamp.db"
container_path="/data/.$backup_name.tmp"
host_path="$root/backups/$backup_name"

cleanup_container_backup() {
  compose "$root" "$env_path" exec -T backend python -c \
    "from pathlib import Path; Path('$container_path').unlink(missing_ok=True)" >/dev/null 2>&1 || true
}

trap cleanup_container_backup EXIT INT TERM
mkdir -p "$root/backups"
compose "$root" "$env_path" exec -T backend python -c \
  "import sqlite3; source=sqlite3.connect('/data/tutumcp.db'); target=sqlite3.connect('$container_path'); source.backup(target); target.close(); source.close()"
compose "$root" "$env_path" cp "backend:$container_path" "$host_path"
chmod 600 "$host_path"
cleanup_container_backup
trap - EXIT INT TERM

echo "Backup created: $host_path"
