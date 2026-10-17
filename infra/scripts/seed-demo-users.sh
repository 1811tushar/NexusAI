#!/usr/bin/env bash
set -Eeuo pipefail
BASE_URL="${BASE_URL:-http://localhost:3000}"
ENV_FILE="${ENV_FILE:-infra/.env}"
if [[ -f "$ENV_FILE" ]]; then set -a; source "$ENV_FILE"; set +a; fi
: "${ADMIN_EMAIL:=admin@nexusai.local}"
: "${ADMIN_PASSWORD:?Set ADMIN_PASSWORD}"
: "${DEMO_PASSWORD:=Demo-Only-Change-12345}"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
login="$(curl -fsS -H 'Content-Type: application/json' -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}" "$BASE_URL/api/auth/login")"
token="$(jq -r '.data.accessToken // empty' <<<"$login")"; [[ -n "$token" ]] || { echo "Admin login failed" >&2; exit 1; }
for spec in "analyst:ANALYST:Demo Analyst" "approver:APPROVER:Demo Approver"; do
  IFS=: read -r username role display <<<"$spec"
  body="$(jq -n --arg email "$username@nexusai.local" --arg role "$role" --arg displayName "$display" --arg temporaryPassword "$DEMO_PASSWORD" '{email:$email,role:$role,displayName:$displayName,temporaryPassword:$temporaryPassword}')"
  code="$(curl -sS -o "$tmp/result.json" -w '%{http_code}' -H "Authorization: Bearer $token" -H 'Content-Type: application/json' -d "$body" "$BASE_URL/api/admin/users")"
  if [[ "$code" == 2* ]]; then echo "Created $username@nexusai.local ($role)"
  elif [[ "$code" == 409 ]]; then echo "$username@nexusai.local already exists (left unchanged)"
  else echo "Create $username returned HTTP $code: $(cat "$tmp/result.json")" >&2; exit 1; fi
done
echo "Demo password was supplied via DEMO_PASSWORD. Change it before shared use."
