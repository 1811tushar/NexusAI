# NexusAI frontend (Frontend A + B, integrated)

Node 20+. From this folder:

    npm install                           # also runs `msw init` (postinstall) to create public/mockServiceWorker.js
    cp .env.example .env                  # VITE_USE_MOCKS=true runs the whole UI with no backend
    npm run dev                           # http://localhost:5173   (UI gallery: /dev/ui)
    npm run lint && npm run typecheck && npm run test && npm run build
    npx playwright install chromium
    npm run test:e2e                      # against mocks (starts the dev server itself)
    npm run test:a11y                     # axe on login and documents

Infra build command: `npm install --no-audit --no-fund && npm run build`; output dir: `dist/`. API base is `/api` (same-origin proxy in dev and nginx).

## Mock logins (password `Passw0rd!!`)
analyst@nexus.test, approver@nexus.test, admin@nexus.test. Mock state lives in the page: a full browser reload resets runs and uploads (navigating inside the app does not).

## Mock agent scenarios (type these in the question box)
| Question contains | Scenario |
|---|---|
| "decline", "decrease", "drop" (the hero question) | Loops once, then pauses for approval of two HIGH-risk actions, resumes after decisions |
| (anything else) | Normal run, completes with one automatic low-risk action |
| "loop cap", "unclear", "best channel" | Hits the loop cap, finishes with a low-confidence banner |
| "ignore previous instructions", "approve all" | REFUSED by the input guardrail |
| "email", "phone", "contact" | Normal run with a PII redaction guardrail event |
| "outage", "times out" | Tool failure with a "Limitations and failures" section |
| "headcount", "salary", "satisfaction" | Abstains: the data cannot answer |
| "2030", "forecast" | Run fails (AI unavailable) |
| "rate limit" | Run fails (LLM rate limited) |
Cancel any running run from its page. Seeded data: a paused hero run owned by the analyst (approver can decide it) and one owned by the admin (self-approval is blocked).

## E2E against the real stack
    E2E_BASE_URL=http://localhost:3000 E2E_PASSWORD=<seeded demo password> npx playwright test -c e2e/playwright.config.ts real-smoke.spec.ts
Only `real-smoke.spec.ts` runs against the real stack (it asserts contract behaviour, not LLM wording). The other specs depend on mock scenarios and skip themselves when `E2E_BASE_URL` is set. Seed the three demo users first (`infra/scripts/seed-demo-users.sh`); set `E2E_ANALYST_EMAIL` if yours differs.

## Layout
`src/common` shared UI and plumbing, `src/features/*` one folder per feature, `src/mocks` MSW handlers and the run simulator, `e2e` Playwright specs.
