#!/usr/bin/env bash
set -Eeuo pipefail
ENV_FILE="${ENV_FILE:-infra/.env}"
[[ -f "$ENV_FILE" ]] || { echo "Missing $ENV_FILE. Copy infra/.env.example to infra/.env first." >&2; exit 1; }
set -a
source "$ENV_FILE"
set +a
profile="${SPRING_PROFILES_ACTIVE:-docker}"
if [[ ",$profile," == *",prod,"* ]]; then
  failures=()
  [[ "${COOKIE_SECURE:-false}" == "true" ]] || failures+=("COOKIE_SECURE must be true")
  [[ "${REGISTRATION_OPEN:-true}" == "false" ]] || failures+=("REGISTRATION_OPEN must be false")
  for name in POSTGRES_PASSWORD AI_DB_RW_PASSWORD AI_DB_RO_PASSWORD ADMIN_PASSWORD INTERNAL_API_KEY JWT_SECRET GRAFANA_ADMIN_PASSWORD; do
    value="${!name:-}"
    [[ -n "$value" ]] || failures+=("$name must be set")
    [[ "$value" != *"change-me"* && "$value" != *"ChangeMe"* && "$value" != *"dev-"* ]] || failures+=("$name still looks like a development placeholder")
  done
  [[ "${CORS_ALLOWED_ORIGINS:-}" != *"localhost"* ]] || failures+=("CORS_ALLOWED_ORIGINS must not contain localhost in production")
  internal_key="${INTERNAL_API_KEY:-}"
  jwt_secret="${JWT_SECRET:-}"
  admin_password="${ADMIN_PASSWORD:-}"
  [[ ${#internal_key} -ge 32 ]] || failures+=("INTERNAL_API_KEY must be at least 32 characters")
  [[ ${#jwt_secret} -ge 32 ]] || failures+=("JWT_SECRET must be at least 32 characters")
  [[ ${#admin_password} -ge 12 ]] || failures+=("ADMIN_PASSWORD must be at least 12 characters")
  if ((${#failures[@]})); then
    printf 'Production environment check failed:\n' >&2
    printf ' - %s\n' "${failures[@]}" >&2
    exit 1
  fi
fi
echo "Environment preflight passed for profile '$profile'. This check does not replace a secrets manager or TLS review."
