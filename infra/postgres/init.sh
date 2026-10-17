#!/bin/sh
# Runs once, on the first start of an empty data volume (docker-entrypoint-initdb.d).
# Creates extension, schema "ai", roles and the ai tables from the API/Data contract (section 10.2).
# Role names and passwords come from the environment so nothing is hard-coded in SQL.
set -e

: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_DB:?POSTGRES_DB is required}"
: "${AI_DB_RW_PASSWORD:?AI_DB_RW_PASSWORD is required}"
: "${AI_DB_RO_PASSWORD:?AI_DB_RO_PASSWORD is required}"
export AI_DB_RW_USER="${AI_DB_RW_USER:-ai_rw}"
export AI_DB_RO_USER="${AI_DB_RO_USER:-ai_readonly}"

# Compose mounts init.sql at /opt/nexus/init.sql (NOT in initdb.d, so it is not run twice).
SQL_FILE="${NEXUS_INIT_SQL:-/opt/nexus/init.sql}"
[ -f "$SQL_FILE" ] || SQL_FILE="$(dirname "$0")/init.sql"
[ -f "$SQL_FILE" ] || { echo "init.sql not found" >&2; exit 1; }

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -f "$SQL_FILE"
echo "NexusAI database bootstrap finished (roles: $AI_DB_RW_USER, $AI_DB_RO_USER)"
