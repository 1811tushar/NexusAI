#!/usr/bin/env bash
# Backs up the whole database (including the ai schema, vectors, memories and LangGraph checkpoints) and the uploads volume.
# Usage: bash infra/scripts/backup.sh [output-dir]   (default: ./backups). PostgreSQL must be running; the backend may be stopped.
set -Eeuo pipefail
ENV_FILE="${ENV_FILE:-infra/.env}"
[[ -f "$ENV_FILE" ]] || { echo "Missing $ENV_FILE" >&2; exit 1; }
set -a; source "$ENV_FILE"; set +a
OUT_DIR="${1:-backups}"; mkdir -p "$OUT_DIR"; stamp="$(date -u +%Y%m%dT%H%M%SZ)"
compose=(docker compose -f infra/docker-compose.yml --env-file "$ENV_FILE")
dump="$OUT_DIR/nexusai-$stamp.dump"; uploads="$OUT_DIR/uploads-$stamp.tar.gz"
"${compose[@]}" exec -T postgres pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc > "$dump"
# Read the named volume through a throwaway container so this works even when the backend is not running.
volume="$("${compose[@]}" config --format json | jq -r '.volumes.uploads.name // empty')"
[[ -n "$volume" ]] || volume="${COMPOSE_PROJECT_NAME:-nexusai}_uploads"
docker run --rm -v "$volume:/data/uploads:ro" alpine:3.20 tar -C /data -czf - uploads > "$uploads"
for f in "$dump" "$uploads"; do (cd "$OUT_DIR" && sha256sum "$(basename "$f")" > "$(basename "$f").sha256"); done
echo "Backup complete:"; ls -lh "$dump" "$uploads"
