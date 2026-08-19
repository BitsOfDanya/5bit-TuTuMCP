#!/bin/sh

project_root() {
  CDPATH= cd -- "$(dirname -- "$0")/.." && pwd
}

production_env_file() {
  root=$1
  requested=${2:-"$root/.env.production"}
  case "$requested" in
    /*) printf '%s\n' "$requested" ;;
    *) printf '%s\n' "$root/$requested" ;;
  esac
}

require_production_env() {
  env_path=$1
  if [ ! -f "$env_path" ]; then
    echo "Production env file not found: $env_path" >&2
    echo "Create it from .env.production.example and fill all secrets." >&2
    exit 1
  fi
}

env_value() {
  env_path=$1
  key=$2
  awk -v key="$key" '
    index($0, key "=") == 1 {
      value = substr($0, length(key) + 2)
    }
    END { print value }
  ' "$env_path"
}

validate_runtime_env() {
  env_path=$1
  require_immutable_tag=${2:-false}

  for key in APP_DOMAIN PUBLIC_ORIGIN ACME_EMAIL OPENAI_API_KEY AUTH_SECRET_KEY AI_SERVICE_TOKEN IMAGE_TAG; do
    value=$(env_value "$env_path" "$key")
    if [ -z "$value" ]; then
      echo "$key must be set in $env_path" >&2
      exit 1
    fi
  done

  auth_secret=$(env_value "$env_path" AUTH_SECRET_KEY)
  service_token=$(env_value "$env_path" AI_SERVICE_TOKEN)
  auth_debug=$(env_value "$env_path" AUTH_DEBUG)
  image_tag=$(env_value "$env_path" IMAGE_TAG)

  if [ "${#auth_secret}" -lt 32 ] || [ "${#service_token}" -lt 32 ]; then
    echo "AUTH_SECRET_KEY and AI_SERVICE_TOKEN must contain at least 32 characters" >&2
    exit 1
  fi
  if [ "$auth_debug" != "false" ]; then
    echo "AUTH_DEBUG must be false" >&2
    exit 1
  fi
  if [ "$require_immutable_tag" = "true" ] && [ "$image_tag" = "latest" ]; then
    echo "IMAGE_TAG must be immutable for deployment; use a sha-* or version tag" >&2
    exit 1
  fi
  if [ "$require_immutable_tag" = "true" ]; then
    app_domain=$(env_value "$env_path" APP_DOMAIN)
    acme_email=$(env_value "$env_path" ACME_EMAIL)
    case "$app_domain $acme_email" in
      *example.com*)
        echo "Replace example.com values before production deployment" >&2
        exit 1
        ;;
    esac
  fi
}

compose() {
  root=$1
  env_path=$2
  shift 2
  docker compose --project-directory "$root" --env-file "$env_path" \
    -f "$root/compose.prod.yaml" "$@"
}
