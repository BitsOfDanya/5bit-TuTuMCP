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
tracker_backup_name="smart-trip-tracker-$timestamp.db"
tracker_container_path="/data/.$tracker_backup_name.tmp"
tracker_host_path="$root/backups/$tracker_backup_name"
preferences_backup_name="preferences-$timestamp.json"
preferences_container_path="/data/.$preferences_backup_name.tmp"
preferences_host_path="$root/backups/$preferences_backup_name"

cleanup_container_backup() {
  compose "$root" "$env_path" exec -T backend python -c \
    "from pathlib import Path; Path('$container_path').unlink(missing_ok=True)" >/dev/null 2>&1 || true
  compose "$root" "$env_path" exec -T smart-trip-tracker python -c \
    "from pathlib import Path; Path('$tracker_container_path').unlink(missing_ok=True)" >/dev/null 2>&1 || true
  compose "$root" "$env_path" exec -T trip-rescue python -c \
    "from pathlib import Path; Path('$preferences_container_path').unlink(missing_ok=True)" >/dev/null 2>&1 || true
}

trap cleanup_container_backup EXIT INT TERM
mkdir -p "$root/backups"
compose "$root" "$env_path" exec -T backend python -c \
  "import sqlite3; source=sqlite3.connect('/data/tutumcp.db'); target=sqlite3.connect('$container_path'); source.backup(target); target.close(); source.close()"
compose "$root" "$env_path" cp "backend:$container_path" "$host_path"
compose "$root" "$env_path" exec -T smart-trip-tracker python -c \
  "import sqlite3; source=sqlite3.connect('/data/smart-trip-tracker.db'); target=sqlite3.connect('$tracker_container_path'); source.backup(target); target.close(); source.close()"
compose "$root" "$env_path" cp "smart-trip-tracker:$tracker_container_path" "$tracker_host_path"
compose "$root" "$env_path" exec -T trip-rescue python -c \
  "from pathlib import Path; import json; source=Path('/data/preferences.json'); data=json.loads(source.read_text()) if source.exists() else {}; Path('$preferences_container_path').write_text(json.dumps(data, ensure_ascii=False, indent=2))"
compose "$root" "$env_path" cp "trip-rescue:$preferences_container_path" "$preferences_host_path"
chmod 600 "$host_path" "$tracker_host_path" "$preferences_host_path"
cleanup_container_backup
trap - EXIT INT TERM

echo "Backups created:"
echo "  $host_path"
echo "  $tracker_host_path"
echo "  $preferences_host_path"
