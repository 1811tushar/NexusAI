#!/usr/bin/env bash
# Runs the REAL nginx image with frontend/nginx.conf against a fake backend and verifies: large uploads, SSE streaming (no buffering),
# actuator lock-down, X-Request-Id, security headers, SPA fallback and cache rules. Needs Docker only.
set -euo pipefail
cd "$(dirname "$0")/../.."
NET="nx-test-net-$$"; BACK="nx-test-backend-$$"; PROXY="nx-test-proxy-$$"; WEB="$(mktemp -d)"
cleanup() { docker rm -f "$BACK" "$PROXY" >/dev/null 2>&1 || true; docker network rm "$NET" >/dev/null 2>&1 || true; rm -rf "$WEB"; }
trap cleanup EXIT
mkdir -p "$WEB/assets"
echo '<html><head><title>NexusAI</title></head><body>app</body></html>' > "$WEB/index.html"; echo 'x' > "$WEB/assets/index-AbCdEf12.js"; echo '<svg/>' > "$WEB/favicon.svg"
# mktemp -d creates a 0700 dir; the nginx worker (uid 101) inside the container must be able to read it (GitHub runners are Linux, no Docker Desktop mapping)
chmod -R a+rX "$WEB"
docker network create "$NET" >/dev/null
docker run -d --name "$BACK" --network "$NET" --network-alias backend -e FAKE_BACKEND_HOST=0.0.0.0 \
  -v "$PWD/infra/tests/nginx/fake_backend.py:/srv/fake_backend.py:ro" python:3.12-slim python /srv/fake_backend.py >/dev/null
docker run -d --name "$PROXY" --network "$NET" \
  -v "$PWD/frontend/nginx.conf:/etc/nginx/conf.d/default.conf:ro" \
  -v "$PWD/frontend/security-headers.conf:/etc/nginx/snippets/security-headers.conf:ro" \
  -v "$WEB:/usr/share/nginx/html:ro" nginx:1.30-alpine >/dev/null
sleep 3
docker exec "$PROXY" nginx -t
docker run --rm --network "$NET" -e NGINX_HOST="$PROXY" -e NGINX_PORT=80 -v "$PWD/infra/tests/nginx/run_tests.py:/t/run_tests.py:ro" python:3.12-slim python /t/run_tests.py
