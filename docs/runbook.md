# Operations runbook

## Start / stop
From repository root, merge the three service implementations into `frontend/`, `backend/`, and `ai-service/` first. Copy `infra/.env.example` to `infra/.env`, replace development credentials, run `bash infra/scripts/check-env.sh`, then:
```bash
docker compose -f infra/docker-compose.yml --env-file infra/.env up --build -d --wait
docker compose -f infra/docker-compose.yml --env-file infra/.env ps
docker compose -f infra/docker-compose.yml --env-file infra/.env logs -f backend ai-service
docker compose -f infra/docker-compose.yml --env-file infra/.env down
```
The browser entry point is http://localhost:3000. Python port 8000 is internal only. PostgreSQL host port 5432 is published only by `docker-compose.dev.yml`.

## Logs and health
```bash
docker compose -f infra/docker-compose.yml --env-file infra/.env logs --tail=200 postgres ai-service backend frontend
curl -fsS http://localhost:3000/actuator/health
```
The Grafana UI is http://localhost:3001 when the `monitoring` profile is enabled.

## Backup / restore
```bash
bash infra/scripts/backup.sh
bash infra/scripts/restore.sh backups/<database.dump> backups/<uploads.tar.gz>
```
Restore is destructive and asks for an explicit `RESTORE` confirmation. It stops the frontend, backend and AI service during the restore (PostgreSQL stays up), verifies the `.sha256` checksums written by `backup.sh`, restores the uploads volume through a throwaway container, then starts the services again. Backups include the `ai` schema (vectors, memories, LangGraph checkpoints), so paused investigations survive a restore. Store backups encrypted and off-host; test restores regularly.

## Rotate secrets
1. Generate new unique values for `POSTGRES_PASSWORD`, `AI_DB_RW_PASSWORD`, `AI_DB_RO_PASSWORD`, `JWT_SECRET` (at least 32 random characters), `INTERNAL_API_KEY`, `ADMIN_PASSWORD`, and provider credentials.
2. Update the secret manager / `infra/.env` and all services that consume the value during a coordinated maintenance window.
3. PostgreSQL role passwords must be changed with `ALTER ROLE` (changing Compose variables does not rotate an existing DB role).
4. Recreate affected containers, verify health and authentication, then invalidate/revoke sessions as required.
5. Never paste secrets into issues or logs.

## Switch LLM provider
- Gemini: set `LLM_PROVIDER=gemini`, `GEMINI_API_KEY`, and a provider-verified `GEMINI_MODEL`.
- Ollama: start `--profile ollama`, set `LLM_PROVIDER=ollama`, `OLLAMA_BASE_URL=http://ollama:11434`, and a tool-calling-capable `OLLAMA_MODEL`. Pull it once:
  ```bash
  docker compose -f infra/docker-compose.yml --env-file infra/.env --profile ollama up -d ollama
  docker compose -f infra/docker-compose.yml --env-file infra/.env exec ollama ollama pull qwen2.5:7b
  ```
  Verify the selected model's tool-calling quality and available RAM before demo use. Model tags/capabilities can change.
- Web search: `WEB_SEARCH_ENABLED=true` (default) allows the agent to use web search when an investigation's toggle is on; set it to `false` to remove web access entirely. Only the sub-task text, with PII redacted, is sent out. Use only synthetic or non-sensitive data with hosted providers.

## Reset database (DESTRUCTIVE)
```bash
docker compose -f infra/docker-compose.yml --env-file infra/.env down
docker volume ls
# Identify the exact NexusAI postgres volume before removing it.
docker volume rm <confirmed-nexusai-postgres-volume>
docker compose -f infra/docker-compose.yml --env-file infra/.env up --build -d --wait
```
Never use `down -v` on a data-bearing environment unless intentional destruction is approved.

## Troubleshooting
- **Model download is slow:** first embedding-model initialization downloads weights into `model-cache`; allow extra healthcheck startup time, check outbound connectivity and volume write permissions, and avoid repeatedly recreating the volume.
- **Gemini 429:** free-tier quotas vary. Keep bounded retries/backoff, reduce concurrency, check provider quota/model availability, and retry later or switch to a configured Ollama model. Never silently mark incomplete answers successful.
- **SSE appears buffered/stalls:** verify nginx `proxy_buffering off`, `proxy_read_timeout 3600s`, `X-Accel-Buffering: no`, and that intermediaries do not buffer responses. Check backend stream logs and `Last-Event-ID`.
- **Postgres init changes do not apply:** Docker entrypoint scripts run only on an empty data directory. Apply a reviewed migration or reset only a disposable development volume.
- **Backend waits for AI health:** inspect `/health`, model download logs, DB credentials, and `INTERNAL_API_KEY` consistency.

## Smoke tests

Real model path (requires a configured provider):
```bash
bash infra/scripts/smoke-test.sh
```

Deterministic integration path (no LLM calls; the overlay replaces the AI service with a test-only stub):
```bash
docker compose -f infra/docker-compose.yml -f infra/docker-compose.fake-ai.yml --env-file infra/.env up --build -d --wait
bash infra/scripts/smoke-test.sh --fake-ai
docker compose -f infra/docker-compose.yml -f infra/docker-compose.fake-ai.yml --env-file infra/.env down
```
The deterministic stub emits a synthetic high-risk action so the test covers the approval pause, self-approval rejection, approver decision, resume and completion. Never use the fake overlay for a real demo/deployment.

## Infrastructure self-test
`bash infra/scripts/validate-infra.sh` proves, with real tools, that: scripts pass ShellCheck; all Compose combinations are valid; `ai_readonly` can only SELECT the five business tables and `ai_rw` is confined to schema `ai` (and can create LangGraph tables there); nginx accepts uploads up to 25 MB, streams SSE without buffering and exposes only `/actuator/health`; the fake AI stub follows the contract.

## Troubleshooting additions
- Document upload returns 413 for files over 1 MB: the proxy limit is missing. `frontend/nginx.conf` must contain `client_max_body_size 25m;` (a test covers this).
- Paused investigation never resumes after a restart: check that `ai_rw` has `CREATE` on schema `ai` and `search_path = ai, public` (the privilege probe covers this).
- Prometheus shows no custom panels: the services must emit the metric names in contract section 12; check `http://localhost:9090/targets` first.
