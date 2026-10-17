# Contributing

## Workflow
- Branches: `feat/<short-name>`, `fix/<short-name>`, `docs/<short-name>`, `chore/<short-name>`.
- Commit messages follow Conventional Commits: `feat(scope): ...`, `fix(scope): ...`, `docs(scope): ...`, `test(scope): ...`, `ci(scope): ...`.
- Keep the frozen contract (v2.1) synchronized across TypeScript, Java DTOs, and Python schemas.
- Do not commit secrets, personal data, generated model caches, or uploads.

## Local quality gates
```bash
cd frontend && npm install --no-audit --no-fund && npm run lint && npm run typecheck && npm test -- --run && npm run build && npm run test:a11y
cd backend && mvn -B verify
cd ai-service && python -m pip install -e '.[dev]' && ruff check . && pytest
docker compose -f infra/docker-compose.yml --env-file infra/.env up --build --wait
bash infra/scripts/smoke-test.sh
python -m app.evals.ci_check  # run from ai-service
```

## Pull request checklist
- [ ] Scope and related checklist IDs are stated.
- [ ] Tests cover behaviour, permissions, failure modes, and regression.
- [ ] No secrets or real personal/business data are included.
- [ ] API/data contract changes were made in the contract first and mirrored in all services.
- [ ] Accessibility and keyboard operation considered for UI changes.
- [ ] Logs redact sensitive values; no tokens or prompt secrets in traces.
- [ ] Docs/runbook and evaluation baseline updated when relevant.
- [ ] CI checks pass: `frontend-ci`, `backend-ci`, `ai-ci`, `integration-ci`, `eval-ci` (deterministic), `security`. Release workflow is tag-triggered. The scheduled/manual LLM eval is informational, not a required check.

## Required checks before merging to main
`frontend`, `verify` (backend), `test` (ai), `static`, `db-roles`, `nginx`, `fake-ai` (infra-ci), `deterministic` (eval-ci), `compose-smoke` (integration-ci) and the `security` workflow. The release workflow re-verifies these on the tagged commit.
