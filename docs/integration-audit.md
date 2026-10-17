# NexusAI integration audit — pre-runtime status

Date: 2026-10-15

## Verdict

**Not certified as complete, defect-free, or production-ready.** The monorepo is assembled and several static checks pass, but the available evidence does not prove every P1–P7 prompt and all 197 master-checklist items are fulfilled.

## Verified in this audit environment

- Final ZIP archive integrity (`ZipFile.testzip()`): PASS.
- Python syntax compilation (`compileall` for `ai-service/app` and `ai-service/tests`): PASS.
- Backend `pom.xml` parses as XML: PASS (this is not Java compilation).
- Frontend `package.json` parses as JSON: PASS.
- Main, fake-AI and dev Compose files parse as YAML: PASS (this is not `docker compose config`).
- `bash -n` on the infrastructure scripts: PASS.
- `infra/tests/fake-ai/test_fake_ai.py`: 12/12 checks PASS on rerun.
- Follow-up static audit found and fixed CI detection conditions that incorrectly required `frontend/package-lock.json` despite no lockfile being present. `integration-ci.yml` and the container-scan gate in `security.yml` now detect `frontend/package.json`.

## Known gaps or outstanding evidence

1. **Checklist not closed:** `docs/checklist.md` contains 197 unchecked boxes. This is the source checklist, not proof that all features are missing; however, an exhaustive item-by-item audit with PASS/FAIL/NOT YET BUILT and code/test evidence has not been completed.
2. **Frontend lockfile absent:** `frontend/package-lock.json` is not present. The build uses `npm install`, which is less reproducible than a committed lockfile. Generate and commit the lockfile in a networked Node/npm environment.
3. **Maven Wrapper absent:** `backend/mvnw` and `.mvn/wrapper/` are not present. CI uses installed Maven; local instructions require Maven installed unless a wrapper is generated.
4. **Backend not compiled or tested here:** the backend stream report explicitly says Java sources and tests were not compiled/executed in its build environment.
5. **Frontend not built/tested here:** dependency installation timed out in the integration environment. TypeScript typecheck, lint, Vitest, Vite production build, Playwright and accessibility tests remain unverified on the merged tree.
6. **AI test claims are inherited, not rerun here:** AI A/B reports describe 316 tests passing in their own environments, but the complete AI pytest suite was not rerun against this exact ZIP here. Real provider/model calls, live web search and Langfuse spans remain unverified.
7. **Docker/Compose unverified:** Docker was unavailable. Image builds, Compose config with the Docker CLI, all profiles, service health and actual startup remain unverified.
8. **Real full-stack E2E unverified:** P7's 82/82 smoke report used a contract-faithful mock backend. It does not prove the merged real Spring Boot + AI service integration.
9. **Operations/security not verified end to end:** real backup/restore, TLS, GitHub Actions execution, release publishing, free-tier deployment and model-backed evaluation remain unverified.

## Follow-up checks that can be run on a machine with dependencies

```bash
# 1. Validate Compose combinations and infrastructure wrappers
bash infra/scripts/validate-infra.sh

# 2. Frontend
cd frontend
npm install --no-audit --no-fund
npm run lint
npm run typecheck
npm test -- --run
npm run build
npm run test:e2e

# 3. Backend (requires Java 21, Maven and Docker for Testcontainers)
cd ../backend
mvn -B verify

# 4. AI service (Python 3.11+, PostgreSQL/pgvector for integration tests)
cd ../ai-service
pip install -r requirements.txt
ruff check .
pytest -q

# 5. Full stack with deterministic fake AI
cd ..
cp infra/.env.example infra/.env
# Replace all development secrets before starting
docker compose -f infra/docker-compose.yml -f infra/docker-compose.fake-ai.yml --env-file infra/.env up --build -d --wait
bash infra/scripts/smoke-test.sh --fake-ai

# 6. Real AI path, after configuring a valid model/provider key
docker compose -f infra/docker-compose.yml --env-file infra/.env up --build -d --wait
bash infra/scripts/smoke-test.sh
```

Passing source-stream reports are retained under `reports/`. They are not a substitute for rerunning tests against the exact merged commit/archive.
