#!/usr/bin/env bash
# Proves the database role model from the contract (section 10.2) with real SQL:
#   ai_readonly -> SELECT on exactly five business tables, nothing else, read-only, 5 s timeout
#   ai_rw       -> read/write on schema ai only; can create LangGraph tables there; cannot touch public data
# Usage:
#   bash infra/scripts/db-privilege-probe.sh            # starts a throwaway pgvector/pgvector:pg16 container (needs Docker)
#   bash infra/scripts/db-privilege-probe.sh --existing # uses PGHOST/PGPORT and a superuser (POSTGRES_USER, default nexus) on an EMPTY database
set -euo pipefail
cd "$(dirname "$0")/../.."
MODE=docker; [[ "${1:-}" == "--existing" ]] && MODE=existing
SU="${POSTGRES_USER:-nexus}"; DB="${POSTGRES_DB:-nexusai}"
RWPW="probe-rw-pw"; ROPW="probe-ro-pw"
CONTAINER="nexus-probe-$$"
pass=0; fail=0

cleanup() { [[ "$MODE" == docker ]] && docker rm -f "$CONTAINER" >/dev/null 2>&1 || true; }
trap cleanup EXIT

run_sql() { # run_sql <role> <password> <sql>   -> prints output, returns psql status
  local role="$1" pw="$2" sql="$3"
  if [[ "$MODE" == docker ]]; then
    docker exec -e PGPASSWORD="$pw" "$CONTAINER" psql -h 127.0.0.1 -U "$role" -d "$DB" -v ON_ERROR_STOP=1 -tA -c "$sql" 2>&1
  else
    PGPASSWORD="$pw" psql "host=${PGHOST:-localhost} port=${PGPORT:-5432} dbname=$DB user=$role" -v ON_ERROR_STOP=1 -tA -c "$sql" 2>&1
  fi
}
# shellcheck disable=SC2120
admin_sql() { # superuser, trust/password-less in both modes
  if [[ "$MODE" == docker ]]; then docker exec -i "$CONTAINER" psql -U "$SU" -d "$DB" -v ON_ERROR_STOP=1 -q "$@" 2>&1
  else psql -U "$SU" -d "$DB" -v ON_ERROR_STOP=1 -q "$@" 2>&1; fi
}
expect_ok()   { local name="$1"; shift; if out=$(run_sql "$@"); then echo "PASS  $name"; pass=$((pass+1)); else echo "FAIL  $name  -> $out"; fail=$((fail+1)); fi; }
expect_deny() { local name="$1" pattern="$2"; shift 2; if out=$(run_sql "$@"); then echo "FAIL  $name  (statement unexpectedly succeeded)"; fail=$((fail+1)); elif grep -qiE "$pattern" <<<"$out"; then echo "PASS  $name"; pass=$((pass+1)); else echo "FAIL  $name  (denied, but for an unexpected reason: $out)"; fail=$((fail+1)); fi; }

if [[ "$MODE" == docker ]]; then
  docker run -d --name "$CONTAINER" -e POSTGRES_USER="$SU" -e POSTGRES_DB="$DB" -e POSTGRES_PASSWORD=probe-admin \
    -e AI_DB_RW_PASSWORD="$RWPW" -e AI_DB_RO_PASSWORD="$ROPW" \
    -v "$PWD/infra/postgres/init.sh:/docker-entrypoint-initdb.d/00-nexus-init.sh:ro" \
    -v "$PWD/infra/postgres/init.sql:/opt/nexus/init.sql:ro" pgvector/pgvector:pg16 >/dev/null
  for _ in $(seq 1 60); do docker exec "$CONTAINER" pg_isready -U "$SU" -d "$DB" >/dev/null 2>&1 && \
     docker exec "$CONTAINER" psql -U "$SU" -d "$DB" -tAc "select to_regclass('ai.document_chunks')" 2>/dev/null | grep -q document_chunks && break; sleep 2; done
else
  export AI_DB_RW_PASSWORD="$RWPW" AI_DB_RO_PASSWORD="$ROPW" POSTGRES_USER="$SU" POSTGRES_DB="$DB"
  NEXUS_INIT_SQL="$PWD/infra/postgres/init.sql" sh infra/postgres/init.sh >/dev/null
fi

# Simulate what Flyway V1/V4/V6 create: private tables, business tables, and the V6 grant block (copied from the contract).
admin_sql <<'SQL'
CREATE TABLE IF NOT EXISTS users (id bigserial primary key, email text, password_hash text);
CREATE TABLE IF NOT EXISTS refresh_tokens (id bigserial primary key, token_hash text);
CREATE TABLE IF NOT EXISTS approvals (id bigserial primary key, status text);
CREATE TABLE IF NOT EXISTS regions (id smallint primary key, name text);
CREATE TABLE IF NOT EXISTS products (id int primary key, name text);
CREATE TABLE IF NOT EXISTS sales (id bigserial primary key, region_id smallint, revenue numeric);
CREATE TABLE IF NOT EXISTS marketing_spend (id bigserial primary key, spend numeric);
CREATE TABLE IF NOT EXISTS customer_metrics (id bigserial primary key, active_customers int);
INSERT INTO users(email,password_hash) VALUES ('a@b.c','hash') ON CONFLICT DO NOTHING;
INSERT INTO sales(region_id,revenue) VALUES (1,10) ON CONFLICT DO NOTHING;
DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ai_readonly') THEN
  GRANT USAGE ON SCHEMA public TO ai_readonly;
  GRANT SELECT ON regions, products, sales, marketing_spend, customer_metrics TO ai_readonly; END IF; END $$;
SQL

echo "== ai_readonly (agent SQL tool)"
expect_ok   "can SELECT sales"                          ai_readonly "$ROPW" "SELECT count(*) FROM sales"
expect_ok   "can SELECT all five business tables"       ai_readonly "$ROPW" "SELECT (SELECT count(*) FROM regions)+(SELECT count(*) FROM products)+(SELECT count(*) FROM marketing_spend)+(SELECT count(*) FROM customer_metrics)"
expect_deny "cannot read users"                         "permission denied" ai_readonly "$ROPW" "SELECT * FROM users"
expect_deny "cannot read refresh_tokens"                "permission denied" ai_readonly "$ROPW" "SELECT * FROM refresh_tokens"
expect_deny "cannot read approvals"                     "permission denied" ai_readonly "$ROPW" "SELECT * FROM approvals"
expect_deny "cannot read schema ai"                     "permission denied" ai_readonly "$ROPW" "SELECT * FROM ai.document_chunks"
expect_deny "cannot INSERT (read-only session)"         "read-only transaction|permission denied" ai_readonly "$ROPW" "INSERT INTO sales(region_id,revenue) VALUES (2,5)"
expect_deny "cannot UPDATE"                             "read-only transaction|permission denied" ai_readonly "$ROPW" "UPDATE sales SET revenue=0"
expect_deny "cannot DELETE"                             "read-only transaction|permission denied" ai_readonly "$ROPW" "DELETE FROM sales"
expect_deny "cannot DROP"                               "read-only transaction|must be owner|permission denied" ai_readonly "$ROPW" "DROP TABLE sales"
expect_deny "cannot CREATE in public"                   "read-only transaction|permission denied" ai_readonly "$ROPW" "CREATE TABLE x(id int)"
expect_deny "cannot opt out of read-only and write"     "permission denied" ai_readonly "$ROPW" "SET default_transaction_read_only=off; SET transaction_read_only=off; INSERT INTO sales(region_id,revenue) VALUES (3,1)"
expect_deny "statement timeout (5 s) is enforced"       "statement timeout" ai_readonly "$ROPW" "SELECT pg_sleep(8)"

echo "== ai_rw (AI service read/write pool)"
expect_ok   "can create a LangGraph-style table in ai"  ai_rw "$RWPW" "CREATE TABLE IF NOT EXISTS checkpoints_probe(thread_id text, blob bytea)"
expect_ok   "created table lives in schema ai"          ai_rw "$RWPW" "SELECT 1 FROM pg_tables WHERE schemaname='ai' AND tablename='checkpoints_probe'"
expect_ok   "can INSERT a 384-d vector chunk"           ai_rw "$RWPW" "INSERT INTO ai.document_chunks(document_id,chunk_index,content,embedding) VALUES (1,0,'probe', array_fill(0.1::real, ARRAY[384])::vector(384))"
expect_ok   "full-text column works"                    ai_rw "$RWPW" "SELECT count(*) FROM ai.document_chunks WHERE tsv @@ plainto_tsquery('english','probe')"
expect_ok   "cosine search works"                       ai_rw "$RWPW" "SELECT id FROM ai.document_chunks ORDER BY embedding <=> array_fill(0.1::real, ARRAY[384])::vector(384) LIMIT 1"
expect_ok   "can write memories and eval_runs"          ai_rw "$RWPW" "INSERT INTO ai.memories(user_id,summary,embedding) VALUES (1,'m', array_fill(0.2::real, ARRAY[384])::vector(384)); INSERT INTO ai.eval_runs(system,config,metrics,results) VALUES ('AGENT','{}','{}','[]')"
expect_deny "cannot read users"                         "permission denied" ai_rw "$RWPW" "SELECT * FROM users"
expect_deny "cannot read sales"                         "permission denied" ai_rw "$RWPW" "SELECT * FROM sales"
expect_deny "cannot create tables in public"            "permission denied" ai_rw "$RWPW" "CREATE TABLE public.leak(id int)"

echo
echo "Result: $pass passed, $fail failed"
[[ $fail -eq 0 ]]
