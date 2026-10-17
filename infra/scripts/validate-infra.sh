#!/usr/bin/env bash
# One command that proves the infrastructure layer on your machine (Docker + bash required; Windows: Git Bash or WSL).
set -euo pipefail
cd "$(dirname "$0")/../.."
step() { echo; echo "=== $*"; }
step "Shell syntax"; for f in infra/scripts/*.sh infra/postgres/init.sh; do bash -n "$f"; done; echo ok
if command -v shellcheck >/dev/null; then step "ShellCheck"; shellcheck -S warning -e SC1090,SC1091 infra/scripts/*.sh infra/postgres/init.sh; echo ok; fi
step "Compose files"
tmp="$(mktemp)"; cp infra/.env.example "$tmp"
for combo in "-f infra/docker-compose.yml" "-f infra/docker-compose.yml -f infra/docker-compose.fake-ai.yml" "-f infra/docker-compose.dev.yml"; do
  # shellcheck disable=SC2086
  docker compose $combo --env-file "$tmp" config --quiet && echo "ok: $combo"; done
docker compose -f infra/docker-compose.yml --env-file "$tmp" --profile monitoring --profile ollama config --quiet && echo "ok: monitoring + ollama profiles"; rm -f "$tmp"
step "Database role isolation (real Postgres)"; bash infra/scripts/db-privilege-probe.sh
step "nginx behaviour (real nginx)";            bash infra/scripts/nginx-test.sh
step "Fake AI stub contract";                    python3 infra/tests/fake-ai/test_fake_ai.py
echo; echo "INFRA VALIDATION PASSED"
