# NexusAI — Autonomous Enterprise Intelligence & Decision Platform

[![frontend-ci](https://github.com/1811tushar/NexusAI/actions/workflows/frontend-ci.yml/badge.svg)](https://github.com/1811tushar/NexusAI/actions/workflows/frontend-ci.yml)
[![backend-ci](https://github.com/1811tushar/NexusAI/actions/workflows/backend-ci.yml/badge.svg)](https://github.com/1811tushar/NexusAI/actions/workflows/backend-ci.yml)
[![ai-ci](https://github.com/1811tushar/NexusAI/actions/workflows/ai-ci.yml/badge.svg)](https://github.com/1811tushar/NexusAI/actions/workflows/ai-ci.yml)
[![integration-ci](https://github.com/1811tushar/NexusAI/actions/workflows/integration-ci.yml/badge.svg)](https://github.com/1811tushar/NexusAI/actions/workflows/integration-ci.yml)
[![eval-ci](https://github.com/1811tushar/NexusAI/actions/workflows/eval-ci.yml/badge.svg)](https://github.com/1811tushar/NexusAI/actions/workflows/eval-ci.yml)
[![security](https://github.com/1811tushar/NexusAI/actions/workflows/security.yml/badge.svg)](https://github.com/1811tushar/NexusAI/actions/workflows/security.yml)

> Run `bash infra/scripts/set-repo-slug.sh yourname/nexusai` after creating the GitHub repository to replace the `1811tushar/NexusAI` placeholders. A badge is not evidence that a workflow has passed.

NexusAI investigates business questions using hybrid retrieval, read-only SQL, statistics, multi-agent reasoning, claim verification, confidence checks, and human approval for high-risk simulated actions.

## Features
- Multi-agent investigation with bounded confidence/replanning loop.
- Citation-aware evidence and visible unsupported/contradicted claims.
- Hybrid RAG over shared documents and 384-dimensional pgvector embeddings.
- Read-only SQL access to allow-listed synthetic business tables.
- Role-based Analyst / Approver / Admin experience.
- Human-in-the-loop approvals; all execution is simulated and audited.
- Replayable SSE traces, long-term per-user memory, guardrails, PII redaction and evaluation.

## Architecture
Browser → React/Vite static SPA + nginx → Spring Boot API → internal FastAPI/LangGraph. Both services use one PostgreSQL 16 database: Spring/Flyway owns `public`; AI owns `ai`. See [architecture](docs/architecture.md) and [decisions](docs/decisions.md).

## Stack
React, TypeScript, Vite, nginx, Spring Boot 3, Java 21, Maven, FastAPI, LangGraph, PostgreSQL 16, pgvector, Docker Compose, GitHub Actions, Prometheus/Grafana (optional), Gemini/Ollama.

## Quick start (three commands)
After the parallel service implementations have been merged:
```bash
cp infra/.env.example infra/.env
# Edit infra/.env: replace every dev password/key; add GEMINI_API_KEY if using Gemini.
docker compose -f infra/docker-compose.yml --env-file infra/.env up --build -d --wait
```
Open http://localhost:3000 and sign in with `ADMIN_EMAIL` / `ADMIN_PASSWORD` from `infra/.env`. Create the demo analyst and approver with `bash infra/scripts/seed-demo-users.sh` (needs `bash`, `curl`, `jq`; on Windows use Git Bash or WSL). This is a development setup; do not expose it publicly without production secrets, TLS, and reviewed deployment configuration.

## Verify the infrastructure (before and after merging services)
```bash
bash infra/scripts/validate-infra.sh     # script lint, Compose validity, DB role isolation on real Postgres, real nginx behaviour, fake-AI contract
```
CI runs the same checks in `infra-ci`. The deterministic end-to-end approval flow (no LLM) is `docker compose -f infra/docker-compose.yml -f infra/docker-compose.fake-ai.yml --env-file infra/.env up --build -d --wait && bash infra/scripts/smoke-test.sh --fake-ai`.

## Configuration
| Variable group | Purpose |
|---|---|
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Database bootstrap and Spring datasource |
| `JWT_SECRET`, `JWT_ACCESS_MINUTES`, `JWT_REFRESH_DAYS`, `COOKIE_SECURE` | Access/refresh auth and cookie security |
| `REGISTRATION_OPEN`, `ADMIN_EMAIL`, `ADMIN_PASSWORD` | Registration policy and bootstrap administrator |
| `INTERNAL_API_KEY`, `AI_SERVICE_URL` | Internal Spring ↔ AI authentication and URL |
| `UPLOAD_DIR`, `MAX_UPLOAD_MB`, `MAX_DOCS_TOTAL` | Upload storage and limits |
| `APPROVAL_TTL_DAYS`, `MAX_CONCURRENT_RUNS_PER_USER`, `RATE_LIMIT_AUTH_PER_MIN` | Workflow limits |
| `CORS_ALLOWED_ORIGINS` | Development origins |
| `LLM_PROVIDER`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | Model provider selection |
| `EMBEDDING_MODEL`, `AI_DB_RW_*`, `AI_DB_RO_*`, `AI_DB_HOST`, `AI_DB_NAME` | Embeddings and AI DB access |
| `TAVILY_API_KEY`, `WEB_SEARCH_ENABLED` | Web retrieval. `WEB_SEARCH_ENABLED` is the global kill switch (default `true`); each investigation also has its own toggle (default on). Only the sub-task text, with PII redacted, leaves your network. Set it to `false` to remove web access entirely |
| `MAX_LOOPS`, `CONFIDENCE_MIN`, `TOP_K`, `SQL_ROW_LIMIT`, `SQL_TIMEOUT_MS`, `MAX_TOOL_ATTEMPTS` | Agent and SQL bounds |
| `GUARDRAILS_ENABLED`, `PII_REDACTION_ENABLED`, `RERANKER_ENABLED`, `CHUNKING_MODE` | Safety and retrieval behaviour |
| `LANGFUSE_*`, `LANGFUSE_MASK_CONTENT` | Optional tracing and content masking |
| `VITE_API_BASE_URL`, `VITE_USE_MOCKS` | Frontend build/runtime config |

See `infra/.env.example` and [runbook](docs/runbook.md) for defaults and operations. Change all development defaults before shared use.

## Testing
- Frontend: `cd frontend && npm install --no-audit --no-fund && npm run lint && npm run typecheck && npm run test -- --run && npm run build && npm run test:a11y && npm run test:e2e`
- Backend: `cd backend && mvn -B verify`
- AI: `cd ai-service && pip install -r requirements.txt && ruff check . && pytest -q`
- Deterministic eval: `cd ai-service && python -m app.evals.ci_check`
- Compose smoke: `bash infra/scripts/smoke-test.sh` (configured LLM required); for the full deterministic integration flow, start with `docker compose -f infra/docker-compose.yml -f infra/docker-compose.fake-ai.yml --env-file infra/.env up --build -d --wait`, then run `bash infra/scripts/smoke-test.sh --fake-ai`.

## Evaluation
**Measured results pending.** Populate `docs/evaluation-report.md` only from actual `evals` runs. Never use illustrative benchmark figures as project results.

## CI/CD
Service-scoped workflows run lint/tests/build, Testcontainers, fake-LLM AI tests, Compose integration, deterministic evaluation, security scans and tag-based GHCR image publishing. The weekly/manual LLM evaluation is informational.

## Repository structure
`frontend/` SPA, `backend/` Spring API, `ai-service/` internal FastAPI, `infra/` Compose/database/monitoring/scripts, `docs/` runbooks and decisions, `.github/` CI and contribution templates.

## Security and privacy
Use synthetic data with hosted LLM/web/tracing providers. Python is not public. Never store access tokens in local storage or pass secrets in URLs. `ai_readonly` must only read `regions`, `products`, `sales`, `marketing_spend`, and `customer_metrics`; it must never read users, refresh tokens, approvals or other private tables. Actions are simulated and high-risk actions require approval.

## Roadmap
- [ ] Merge service implementations and validate contract v2.1 end-to-end.
- [ ] Record deterministic and LLM evaluation results with baselines.
- [ ] Verify deployment, load tests, alert thresholds and secret management.

## License
MIT. See [LICENSE](LICENSE).

## References
- [API & Data Contracts](docs/api-contracts.md) (mirror the frozen contract v2.1 here during service integration)
- [Architecture](docs/architecture.md)
- [Runbook](docs/runbook.md)
