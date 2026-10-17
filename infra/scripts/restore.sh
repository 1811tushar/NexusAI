#!/usr/bin/env bash
# Restores a database dump and the uploads archive produced by backup.sh. DESTRUCTIVE: replaces data in the target database.
# The backend, AI service and frontend are stopped during the restore so nothing writes while objects are replaced,
# then started again. PostgreSQL stays up.
set -Eeuo pipefail
if [[ $# -ne 2 ]]; then echo "Usage: $0 <database.dump> <uploads.tar.gz>" >&2; exit 2; fi
[[ -f "$1" && -f "$2" ]] || { echo "Backup files not found: $1 / $2" >&2; exit 1; }
ENV_FILE="${ENV_FILE:-infra/.env}"
[[ -f "$ENV_FILE" ]] || { echo "Missing $ENV_FILE" >&2; exit 1; }
set -a; source "$ENV_FILE"; set +a
# Verify checksums when backup.sh wrote them next to the files.
for f in "$1" "$2"; do [[ -f "$f.sha256" ]] && { (cd "$(dirname "$f")" && sha256sum -c "$(basename "$f").sha256") || { echo "Checksum mismatch for $f" >&2; exit 1; }; }; done
echo "WARNING: this replaces data in database '$POSTGRES_DB' and the uploads volume. Make sure a fresh backup exists."
read -r -p "Type RESTORE to continue: " confirm
[[ "$confirm" == RESTORE ]] || { echo "Aborted."; exit 1; }
compose=(docker compose -f infra/docker-compose.yml --env-file "$ENV_FILE")
"${compose[@]}" up -d postgres --wait
"${compose[@]}" stop frontend backend ai-service
trap '"${compose[@]}" start ai-service backend frontend >/dev/null 2>&1 || true' EXIT
"${compose[@]}" exec -T postgres pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner < "$1"
# Uploads live in a named volume owned by the backend user: restore through a throwaway container that mounts the same volume.
volume="$("${compose[@]}" config --format json | jq -r '.volumes.uploads.name // empty')"
[[ -n "$volume" ]] || volume="${COMPOSE_PROJECT_NAME:-nexusai}_uploads"
docker run --rm -i -v "$volume:/data/uploads" alpine:3.20 sh -c 'rm -rf /data/uploads/* && tar -C /data -xzf - && chown -R 10001:10001 /data/uploads' < "$2"
echo "Restore complete. Services are starting; verify health with: docker compose -f infra/docker-compose.yml ps"
