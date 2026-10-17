# Frontend integration report (Frontend A + Frontend B)

## Verification status (read first)
The sandbox has no network. `npm install`, ESLint, Vitest, `vite build` and Playwright were **never run**. What was checked: a TypeScript parse plus a type-check with library types absent, filtered to errors that do not depend on them (unused locals, unknown names, wrong local exports). That caught and fixed two real bugs (a wrong `tsconfig` path and a wrong type import). Type errors against real library types, failing tests and runtime bugs are still possible. Run the commands in README.md first and send me what fails.
Not measured: WCAG contrast, Lighthouse, bundle size, screen-reader behaviour, 360-1920 px layouts (written responsive, not viewed).

## Frontend B scope, by checklist ID
| ID | Status |
|---|---|
| FE-IV-01 | QuestionForm: 10-2000 chars, examples incl. the hero question, web toggle with the "queries leave the network" note, document scope, memory toggle, max loops, disabled until valid |
| FE-IV-02 | Live RunView from SSE: plan checklist, AgentTimeline (routing, agent start, tool calls with args/results, evidence, claims, confidence, loops, guardrails), evidence panel + growing gauge; auto-scroll pauses when scrolled up; tabs below 1024 px |
| FE-IV-03 | LoopNotice "Looping back n of m: reason, focus" + counter in the header |
| FE-IV-04 | ApprovalPauseBanner (read-only for analysts, decide link for approvers, owner note); view stays live and continues after decisions |
| FE-IV-05 | Cancel with confirmation; cancelled state |
| FE-IV-06 | Rebuild from `GET /steps`, then stream with `?after=lastSeq` (and `Last-Event-ID` via the library); reducer drops any seq already applied |
| FE-IV-07 | Rate-limit, AI-unavailable and failed-run cards with "Start again with the same question" |
| FE-IV-08 | Run is server-side; `RunWatcher` (mounted in the shell) polls watched runs and toasts completion / approval wait when you are elsewhere |
| FE-A11-03 | `announce()` polite live region: plan ready, approval needed, completed/failed only |
| FE-RP-01..06 | Report header (gauge, low-confidence banner, owner, duration, loops), summary, Markdown with table of contents, ClaimList (status chips, confidence, key marker, evidence chips, status filter), evidence drawer (document link with `?chunk=` when the evidence carries a chunk id, SQL text + table + truncated flag, stats table + chart, web link `noopener noreferrer`, memory), RecommendationList with approval/action status, Trace tab replay |
| FE-RP-07 | Export `report.md`, print stylesheet, feedback thumbs + comment |
| FE-HI-01 | Paged history: status filter, search, sort, owner column for approver/admin, empty state, row opens live view or report |
| FE-AP-01..04 | Pending/Decided tabs, cards (params readable, risk, rationale, confidence, evidence link, age, expiry), two-step DecisionDialog (comment required on reject, "simulated execution" summary, disabled with explanation for analysts/self-approval), INVALID_STATE and SELF_APPROVAL handling with refresh, detail page with claims and evidence chain |
| FE-SH-07 | uses Frontend A's 60 s poll and approver toast |
| Action log | ActionLogPage with status/action/how filters |
| FE-EV-01, ADD-FE-01 | Evaluation: four-system comparison table + chart, quality vs token-cost chart, per-category table, guardrail/recovery stats, retrieval ablation chart + table, question drill-down; all charts have an adjacent accessible table; Recharts is lazy |
| ADD-GR-01/03/05 | REFUSED card (reason, what did not run, how to rephrase), GuardrailChips in the timeline and a Guardrails list on the report, prominent "Limitations and failures" card |
| FE-Q-03 (mocks) | `runSimulator.ts`: normal, loop-once, loop cap, HIGH-risk pause + resume driven by the approvals handler, refused, redaction, tool failure with limitations, abstain, failed, rate-limited, cancelled; fixtures for every evidence kind and claim status; four-system eval + 7 ablation variants |
| FE-Q-05 | Vitest: runStore (normal, loop, pause/resume, error, refusal, cancel, reconnect-without-duplicates, replay equals incremental), DecisionDialog rules, claim filtering, recommendation status, table of contents |
| FE-Q-06 | Playwright (mocks): full hero flow across analyst and approver, refusal, rate limit, cancel, tool failure, self-approval, read-only approvals, owner column, evaluation, axe on run view, report and evaluation. `real-smoke.spec.ts` also runs against the real stack |

## Changes to Frontend A files (all additive)
1. `src/app/AppShell.tsx`: mounts `<RunWatcher />`.
2. `src/app/router.tsx`: placeholders replaced by lazy routes. `src/app/Placeholder.tsx` is now unused.
3. `src/index.css`: `@media print` rules.
4. `src/common/components/EvidenceCard.tsx`: document link adds `?chunk=` when `source.chunkId` exists.
5. `src/common/types/evidence.ts`: optional `source.chunkId`.
6. `src/mocks/handlers/misc.ts`: dashboard reads from the simulator. `stubs.ts` deleted; `browser.ts`, `util.ts` (more status codes) updated.
7. `tsconfig.json`: `node` types, `./src/*` path mapping (bug fix). `package.json`: `@types/node`.
8. `e2e/playwright.config.ts`, `e2e/helpers.ts`: real-stack switch, `signIn/signOut`, speed-up.

## Contract gaps I had to work around (please decide)
- `ApprovalDTO` has no requester, no owner id and no `expiresAt`. The card shows the investigation question instead of a requester; expiry is derived as requested + 7 days (the contract default). Self-approval is only pre-blocked where the owner is known (detail page); elsewhere the server's 403 is shown. Suggest adding `requestedBy`, `investigationOwnerId`, `expiresAt`.
- `EvidenceDTO.source` has no chunk id, so the contract cannot deep-link to a cited passage. I added an optional `chunkId` (not in contract v2.1).
- `AgentStepDTO` is not defined in the contract. I assumed `{ seq, type, payload, createdAt }`.
- `ActionLogDTO` has no action key, so a low-risk recommendation is shown as executed if any automatic action ran.
- `GET /actions` has no filter parameters, so its filters apply to the loaded page only. The Decided approvals tab filters client-side for the same reason.
- The evaluation detail has no link to an investigation trace, so the drill-down shows the question, expected facts and answer but cannot open a trace.
- Low-confidence threshold is not on the detail DTO; the UI uses 0.7.

## Mock caveats
Eval numbers in `mocks/fixtures.ts` are sample data, not measurements. A page reload during a mock run resets it; the real backend does not.

## Final pass (added after the first integrated zip)
Done in this pass, all offline:
- WCAG contrast computed for every token pair in both themes: all text pairs pass AA (4.5:1). Input and button borders (`--border-strong`) were 1.8:1 and are now 3.3:1 (light) and 3.6:1 (dark) on surfaces (WCAG 1.4.11).
- `postinstall` runs `msw init`, so `public/mockServiceWorker.js` is created by `npm install` (no manual step).
- `components.json` added so `npx shadcn add` works against `@/common/components/ui`. Existing primitives are hand-written on Radix or native elements, not generated by the CLI.
- FE-DO-06: "View original PDF at page N" in the document viewer (browser PDF viewer in an iframe, loaded on demand) and "Download original". Needs `frame-src blob:` in the nginx CSP.
- New tests: `useInvestigationRun` (hydrate, `?after=lastSeq`, duplicate and older events ignored, pause, resume, completion closes the stream, failed run), `useSSE` (dedupe, JSON parsing, fatal 4xx, onClose), Register form.
- New Playwright: axe on every page in light and dark theme (analyst and admin pages, register), keyboard specs (Ctrl+K palette, dialog Escape returns focus, focusable timeline), PDF preview.
- Removed the unused `Placeholder.tsx`.

Verification: still no `npm install`, lint, test run, build or Playwright run was possible here. The contrast figures above were computed, not estimated.

## Still not done
- Nothing has been executed (see top). Expect to fix a few type or test failures on first run.
- Responsive layouts (360-1920 px) and print output were written but never viewed. Lighthouse, bundle size, `npm audit` and a screen-reader pass are not done.
- Primitives are not CLI-generated shadcn components.
- The full hero E2E needs the mock scenarios; only `real-smoke.spec.ts` runs against the real stack.
- Contract gaps listed above remain until the contract is extended.
