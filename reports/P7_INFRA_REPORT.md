# NexusAI P7 (Infra, CI/CD, repo scaffolding): final report (corrected and verified)

This archive is the infrastructure/repository layer. It contains no frontend, Spring Boot or AI-service application code; those streams are merged by the integration step.

## What was verified with real tools (and how)
| Area | Tool and evidence |
|---|---|
| Database bootstrap and role isolation | Real PostgreSQL 16 + pgvector. `infra/scripts/db-privilege-probe.sh --existing`: **22 of 22** checks pass (ai_readonly: SELECT on the five business tables only, cannot read users/refresh_tokens/approvals/schema ai, cannot write, 5 s timeout enforced; ai_rw: confined to schema ai, can create LangGraph-style tables there, 384-d vector insert, cosine and full-text queries, cannot read public data or create tables in public). Bootstrap run twice (idempotent) and with custom role names |
| nginx | Real nginx 1.24. `infra/tests/nginx/run_tests.py`: **16 of 16** pass: 3 MB upload accepted, 21 MB reaches Spring (FILE_TOO_LARGE), 30 MB rejected at the proxy; SSE first event arrives immediately and the stream completes; only `/actuator/health` is proxied (`/actuator/prometheus`, other actuator paths, `/metrics` return 404); X-Request-Id forwarded or generated; security headers; SPA fallback; no-cache index; immutable fingerprinted assets only |
| Fake AI stub | Contract conformance test `infra/tests/fake-ai/test_fake_ai.py`: all checks pass (event vocabulary, HIGH only in approval_required, LOW only in action_proposed, loop then accept, REFUSED path, no-approval path, API key, health, metrics) |
| End-to-end smoke test | `infra/scripts/smoke-test.sh --fake-ai` executed through the real nginx config and the real stub against a contract-faithful mock backend (not the real Spring service): **82 of 82** checks pass (front door, contract version header, HttpOnly refresh cookie, roles, upload, duplicate 409, ~2 MB and 22 MB uploads, SSE ids strictly increasing, Last-Event-ID replay without duplicates, late joiner, 404 for another analyst, pause, self-approval 403, analyst 403, reject-needs-comment, double decision 409, completion, claims, evidence, limitations, simulated-action labelling, LOW auto-executed, HIGH executed once after approval, REFUSED run, no-approval run, visibility) |
| Compose | Real Docker Compose v5 `config` on all combinations (main, fake-ai override, dev, all profiles): valid; required variables enforced; AI service has `expose` only; frontend is the only published application port; Grafana bound to loopback |
| Workflows | `actionlint 1.7.12`: clean. All pinned action SHAs verified against upstream tags (CodeQL moved to v4.38.3) |
| Shell | `bash -n` and ShellCheck: clean on every script |
| JSON/YAML | all parse; Postman collection covers all 37 contract endpoints (checked programmatically) |

## Defects found in the previous revision and fixed here
1. `frontend/nginx.conf` was **invalid** (unquoted `{8,}` regex): nginx would not start. Fixed and tested.
2. No `client_max_body_size`: every upload over 1 MB would fail with 413. Fixed (25 MB, above Spring's 20 MB) and tested.
3. `ai_rw` lacked `CREATE` on schema `ai` and a `search_path`: LangGraph's checkpointer (approval pause/resume) would fail. Fixed and proven.
4. `init.sql` hard-coded role names while `init.sh` allowed overrides, and `init.sql` also ran automatically. Rebuilt: one script reads names from the environment; SQL is idempotent.
5. `WEB_SEARCH_ENABLED` defaulted to false (your decision is ON with a kill switch). Fixed in Compose and all env examples.
6. `eval-ci` was red on every early push and its LLM job had no Postgres service and a circular baseline requirement. Fixed: safety checks gate; baseline comparison starts once metrics are measured; services that do not exist yet are skipped with a warning, not a failure.
7. `ai-ci` had no database bootstrap and no contract env vars; assumed `requirements.txt`. Fixed (both `requirements.txt` and `pyproject.toml` supported).
8. Release published images without checking tests. Added a gate job that verifies required checks on the tagged commit.
9. Trivy/npm audit would keep CI chronically red. Trivy ignores unfixed issues; production dependencies gate; dev tooling is reported only.
10. CodeQL used an older line and analysed languages that may not exist. Fixed (v4, per-language detection, categories).
11. Smoke test was not re-runnable, accepted REFUSED as success, and did not test SSE, replay, limits, roles, or the approval race. Rewritten (and it caught a bug in its own first draft).
12. AI Dockerfile: no layer caching, double torch download, compilers in runtime. Rewritten as multi-stage with CPU torch first. Backend Dockerfile: `exec java` for graceful shutdown, dependency caching.
13. `restore.sh` ran while services were writing; now stops them, verifies checksums, restores uploads through the volume. `backup.sh` no longer needs the backend. Added `backups/` to `.gitignore`.
14. Docs stubs replaced: real contract, architecture, checklist, differentiators, under-the-hood, engineering-stories skeleton, evaluation-report template, demo scripts, ADRs 008-011; full Postman collection; README badge placeholder script.
15. Grafana dashboard extended (agent nodes, tools, tokens, LLM errors, guardrails, run outcomes, ingestion); metric names are now fixed by contract section 12.

## What is NOT verified here (be exact)
- Docker image builds and `docker compose up` (Docker is not available in the sandbox); the Docker-based wrappers (`db-privilege-probe.sh` default mode, `nginx-test.sh`, `validate-infra.sh`) were not run in Docker, but the SQL and nginx logic they wrap was executed natively and passes.
- The smoke test against the REAL Spring Boot and AI services (they are not in this archive). The mock backend implements the contract's semantics but is not the real implementation; integration is where this is proven.
- Pinned Docker image tags `prometheus v3.7.3`, `grafana 12.2.1`, `ollama 0.12.6`, `trivy 0.67.2` exist as upstream releases; the image tags themselves were not pulled.
- GitHub Actions execution, real backup/restore, TLS, model-backed evaluation, free-tier deployment (OPS-10) and Git history.

## Commands
```bash
bash infra/scripts/validate-infra.sh                 # Docker + bash: lint, compose, DB roles, nginx, fake-AI
cp infra/.env.example infra/.env && bash infra/scripts/check-env.sh
docker compose -f infra/docker-compose.yml --env-file infra/.env up --build -d --wait
bash infra/scripts/smoke-test.sh                     # real AI (LLM key required)
docker compose -f infra/docker-compose.yml -f infra/docker-compose.fake-ai.yml --env-file infra/.env up --build -d --wait
bash infra/scripts/smoke-test.sh --fake-ai           # deterministic, no LLM
bash infra/scripts/backup.sh; bash infra/scripts/restore.sh backups/<db.dump> backups/<uploads.tar.gz>
```

## Dependencies this layer places on the other streams (all in contract v2.1 sections 11 to 13)
Backend: permitAll for `/actuator/health` and `/actuator/prometheus`; Micrometer histogram properties; metric names; 413 FILE_TOO_LARGE at 20 MB; `X-Contract-Version: 2.1`; `SPRING_DATASOURCE_*`/`POSTGRES_*` env. AI: `GET /metrics` without key; metric names; `LLM_PROVIDER=fake`; `python -m app.evals.ci_check` and `evals/baseline_metrics.json` formats; `requirements.txt` or `pyproject.toml`.
