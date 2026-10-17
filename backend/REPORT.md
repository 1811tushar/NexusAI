# Integrated backend (Backend A + Backend B) — delivery report

**Status: written, NOT compiled or executed (A and B).** The build sandbox had a JRE but no `javac`, no Maven and no network, so nothing
here has been compiled and no test has been run. I only ran a bracket-balance and package-name check over all Java files.
Expect a first `mvn verify` to surface some compile/validation errors; please send them back. Items most likely to need a nudge are
listed under "Risks to check first".

## Requirement IDs (built, unverified by execution)
| ID | Where |
|---|---|
| BE-AU-01 | `auth/AuthService.register/login`, `user/PasswordPolicy` (>=10, letter+digit, <=72 bytes), BCrypt strength from env |
| BE-AU-02 | `AuthService.refresh/logout`, `RefreshToken*`, `RefreshCookieFactory` (httpOnly, `/api/auth`, Lax, Secure from env), SHA-256 hashed tokens, family revocation on reuse |
| BE-AU-03 | `SecurityConfig` URL rules + service checks; `RoleMatrixIT` |
| BE-AU-04 | lockout (5 fails, 15 min, generic error), change password revokes other sessions (`sid` JWT claim), `RateLimitFilter` |
| BE-AU-05 | `UserService.create/patch`, `AdminUserController`, `AdminBootstrap`; `AdminUserRulesIT` |
| BE-DC-01 | `DocumentFileValidator` (extension + content type + magic bytes + size), `LocalFileStorage` random keys |
| BE-DC-02 | `DocumentIngestionService` (202, UPLOADED→INGESTING→READY/FAILED, reason stored), reindex, SHA-256 duplicate 409 |
| BE-DC-03 | list/filter/page/sort, get, download, chunk proxy, delete with DELETING + `DocumentSweeper` (stuck INGESTING, DELETING retry) |
| BE-DC-04 | owner/ADMIN rules in `DocumentService.requireManage`, approver read-only |
| BE-DC-05 | `MAX_DOCS_TOTAL` cap (422 QUOTA_EXCEEDED), `/api/search` |
| BE-PL-01/02 | `ApiResponse`, `GlobalExceptionHandler` (full catalogue, vague 500 + requestId), entities never returned |
| BE-PL-03 | V1, V2, V5 copied verbatim from contract 10.1; `ddl-auto=validate` |
| BE-PL-04 | `AiServiceClient` (timeouts, error mapping, request-id forwarding, retries only on idempotent calls) |
| BE-PL-05 | CORS from env, security headers, `ProdConfigValidator` fail-fast |
| BE-PL-06 | JSON logs with `requestId` in prod; no tokens/passwords/document text logged |
| BE-PL-07 | Bucket4j in-memory: auth (IP), upload and investigation start (user); constants in `RateLimitPolicy` |
| BE-PL-08 | Actuator health + Prometheus; springdoc dev-only (ADMIN-only JSON in prod); business metrics in `common/metrics` (`NexusMetrics`, `MetricsConfig`): `nexus_run_duration_seconds`, `nexus_run_loops`, `nexus_runs_finished_total{status}`, `nexus_approvals_pending` (gauge), `nexus_runs_live` (gauge), `nexus_ai_errors_total{code}`, `nexus_ingestion_duration_seconds{outcome}`; tested by `MetricsIT` |
| BE-PL-09 | `AuditService` (login ok/fail/blocked, reuse, password change, role change, user create/enable/disable, document upload/delete, approval hook) |
| BE-PL-10 | tests: see below |
| BE-PL-11 | `Dockerfile` |
| SEC-01..06, SEC-08 (partial), SEC-09 (partial) | as above; see decisions |

## Tests written
Unit: `JwtUtilTest`, `PasswordPolicyTest`, `DocumentFileValidatorTest`, `LocalFileStorageTest`, `RateLimitFilterTest`, plus Mockito service tests `AuthServiceTest`, `UserServiceTest`, `DocumentServiceTest` and `AiServiceClientTest` (error mapping, retry classification).
Integration (Testcontainers + WireMock): `AuthFlowIT`, `RegistrationClosedIT`, `AdminUserRulesIT`, `DocumentIngestionIT`, `RoleMatrixIT`.

## Decisions and deviations (please review)
1. **HTTP status for register/login/refresh/logout = 200.** The contract does not specify; 200 is what the MSW mocks most likely assume.
2. **Wrong current password on change-password = 400 `VALIDATION_FAILED`**, not 401, because a 401 would trigger the SPA's refresh-and-retry loop.
3. **Locked or disabled accounts return the same `INVALID_CREDENTIALS`** as a wrong password (no account-state leak).
4. **`sid` claim in the access JWT** = refresh-token family id. The refresh cookie has `Path=/api/auth`, so it is not sent to `/api/users/me/password`; `sid` is how "revoke other sessions" keeps the current one.
5. **Role/disable changes take effect on the next refresh** (<= `JWT_ACCESS_MINUTES`, default 15). Disabling a user revokes their refresh tokens immediately; their existing access token lives out its TTL. Per-request DB lookup was rejected for cost; say if you want it.
6. **No "must change temporary password" flag**: V1 DDL is frozen and has no column for it.
7. **Executors** (`AsyncConfig`): `virtualThreadExecutor` (ingestion, with a semaphore `INGEST_CONCURRENCY`=2 so the Python embedder is not flooded) and **`runRelayExecutor`** (bounded 4..16 threads, no queue, for Backend B's run relays).
8. **Flyway `out-of-order: true` in dev only**, so Backend B's V3/V4/V6/V7 apply on a dev DB that already holds V1/V2/V5. Fresh DBs and prod are unaffected.
9. **`/actuator/prometheus` is permitted without auth** because nginx proxies only `/api`; it must never be published. Contract text matches ("internal network only").
10. **Not 404 for foreign documents**: documents are shared knowledge, so a non-owner gets 403 on delete/reindex (contract section 2 only hides foreign *investigations*).
11. **Search results** are filtered to READY documents and titles are filled from the DB (Python has no titles).
12. **HTTP 405/415** from Spring are mapped to the nearest catalogue codes with the real status (not in the catalogue).
13. **Maven wrapper not generated** (needs network); command in README. The Dockerfile uses a Maven image, so it does not need it.
14. **Versions** (Boot 3.5.0, jjwt 0.12.6, springdoc 2.8.9, Bucket4j 8.14.0, logstash-encoder 8.1, WireMock 3.9.2) are from memory, as the stack doc forbids; bump to the latest stable and commit.

## ADDENDUM 09
Now implemented in Backend B (see below): `REFUSED` status, `guardrail_triggered` events, `limitations`, `guardrailEvents`, eval DTO v2.1.

## Final audit against both prompts
Every item of the Backend A and Backend B scope lists is implemented. Corrections made after the first integrated delivery: BE-PL-08 custom metrics
(were missing, now added and tested), a heartbeat test (was untested), and an immediate drop of slow stream viewers.
Still not verified by execution: everything (see Status). Not producible here: the Maven wrapper, a built Docker image, an executed Postman run.

## Not done / out of scope (whole backend)
**V7 seed migration** (generated by the AI stream; copy it in). No Postman run (collection provided, unexecuted). No per-service CI
workflow (OPS-06 belongs to Infra). Nothing in ai-service, frontend or infra.

## Risks to check first on the first build
- Hibernate `validate` against `citext` / `char(64)` columns (I used `columnDefinition = "citext"` / `"bpchar"` + `@JdbcTypeCode(CHAR)`); if it complains, relax those two columns' mapping.
- `ContentDisposition.builder("attachment")`, Bucket4j `refillGreedy` lambda API and WireMock imports are version-sensitive.
- `DocumentRepository.findAll(Specification, Pageable)` override with `@EntityGraph`.
- `IntegrationTestBase` needs Docker; `pgvector/pgvector:pg16` must be pullable.

---

# Backend B (added in this integrated delivery)

## Requirement IDs
| ID | Where |
|---|---|
| BE-IV-01 | `InvestigationService.start` (question 10-2000, options defaults/limits, document check, per-user cap via lock + count, UUID thread, 202), `RunRelayService.startAsync` on the bounded relay executor; the run is independent of any browser |
| BE-IV-02 | `RunRelayService` + `InvestigationEventPersister`: every event except `report_delta` stored in `agent_steps` with a Spring seq (row lock + atomic `UPDATE ... RETURNING`); plan/step_status, evidence (capped 50 rows), claims (history kept), loops, LOW auto-execution, approvals, report, terminal status, usage |
| BE-IV-03 | `InvestigationStreamService` + `StreamHub`: authorise, subscribe first, DB replay after `Last-Event-ID`/`?after`, live tail, gap repair from DB, dedupe, `: ping` 15 s, `Cache-Control: no-cache`, `X-Accel-Buffering: no`, closes after done/error, many viewers, slow viewers dropped (they reconnect) |
| BE-IV-04 | `InvestigationStateMachine` (invalid transitions rejected, tested); cancel in RUNNING and AWAITING_APPROVAL (409 otherwise) cancels upstream and expires pending approvals |
| BE-IV-05 | `requireVisible` (foreign id = 404 for analysts), scoped lists, approvals, actions, dashboard |
| BE-IV-06 | `InvestigationSweeper` (startup: RUNNING without relay -> FAILED "interrupted by restart" with a terminal `error` event; AWAITING_APPROVAL untouched; periodic check with grace), `ApprovalExpiryJob` |
| BE-IV-07 | `ReportExportService` (report.md), feedback, `DashboardService` |
| BE-IV-08 | evidence rows capped at 50 (`truncated=true`), per-user cap, start rate limit from Backend A |
| BE-AP-01 | `ApprovalService` (list/get/pending-count/decide; APPROVER/ADMIN; self-approval 403; comment required on REJECT; conditional UPDATE, one winner, loser 409) |
| BE-AP-02 | `ApprovalFlowService` (compare-and-set AWAITING->RUNNING so exactly one settler; execute APPROVED via `ActionExecutor`, log REJECTED/EXPIRED/FAILED, resume with all decisions, same seq counter); `ActionExecutor.executeApproved` refuses without a stored human APPROVE |
| BE-AP-03 | `ActionLog`, `ActionController` (`GET /api/actions`), every note ends with "Simulated execution; no external system was changed." |
| BE-ME-01 | `MemoryService/Controller`: proxy with the AUTHENTICATED user id only |
| BE-EV-01 | `EvalService/Controller` (ADMIN) incl. v2.1 DTO |
| BE-PL-03 | V3, V4, V6 verbatim from contract 10.1 (V7 comes from the AI stream) |
| BE-PL-10 | tests below |
| SEC-01/05 | `RoleMatrixBIT`, `ApprovalRulesIT`, `VisibilityIT`; separation of duties and race-safety tested |

## Tests (B)
Integration (Testcontainers + scripted Python SSE via WireMock): `RunRelayIT` (full sequence, seq contiguous, LOW auto-execution, forged Spring-only events dropped, loops, claim history, evidence cap, error event, connection drop, 429, stream end without terminal, REFUSED, cancel, **browser disconnect does not stop the run**, concurrency cap, validation, option forwarding), `ApprovalRulesIT` (pause -> approve -> execute -> resume with event order, reject needs comment, self-approval 403, roles, **same-approval race = one winner**, **two approvers at once = one resume**, forged/invalid actions, HIGH forged as LOW not executed, expiry, cancel while waiting, visibility), `StreamReplayIT` (full replay, Last-Event-ID, `?after`, header precedence, two viewers + late joiner, headers, JSON 404 for foreign ids even with `Accept: text/event-stream`), `VisibilityIT` (+ dashboard, actions, report.md, feedback), `RestartRecoveryIT`, `RoleMatrixBIT`, `MemoryEvalProxyIT`, `MetricsIT` (BE-PL-08 meters), and the stream heartbeat test in `StreamReplayIT` (`: ping` every `nexus.runs.heartbeat-seconds`, 15 in production, 1 in tests).
Unit: `InvestigationStateMachineTest`, `ActionCatalogueTest`, `ActionExecutorTest` (the HIGH-risk invariant), `LimitationsParserTest`, `StreamHubTest`.

## What B added to `ai/AiServiceClient` (marked `BACKEND B ADDITIONS`, A's methods untouched)
`investigateStream`, `resumeStream` (SSE as `Flux<AiEvent>`), `cancel`, `listMemories`, `deleteMemory`, `deleteAllMemories`, `purgeUser`, `evalRuns`, `evalRun`, `mapStreamError`. New classes in `ai/`: `AiEvent`, `AiInvestigateRequest`, `AiResumeRequest`, `AiCancelResponse`, `AiDeletedResponse`, `AiPurgeResponse`.

## What B changed in A's files (needed for the integration)
1. `SecurityConfig`: `dispatcherTypeMatchers(ASYNC, ERROR).permitAll()`. Without it an `SseEmitter` finishes through an async dispatch that has no Authorization header and fails after the stream. Everything else B needs (decision, start/cancel, `/api/eval/**`) was already declared by A.
2. `GlobalExceptionHandler`: error responses now set `Content-Type: application/json` explicitly; otherwise a client sending `Accept: text/event-stream` (fetch-event-source does) gets an empty 406 instead of the JSON 404/403.
3. `application.yml`, `application-test.yml`, `.env.example`: `nexus.runs.*` (`MAX_CONCURRENT_RUNS_PER_USER`, `APPROVAL_TTL_DAYS`, `MAX_LOOPS`). `RunProperties` has defaults, so no yml is strictly required.
4. `RoleMatrixIT` (A): `/api/eval/runs` for ADMIN is now 200 (stubbed) because B implemented it.

## Decisions and coordination (please read)
1. **Extra field `approvalId` inside each action of the `approval_required` event** (persisted and streamed). The contract does not list it; it lets the UI link a pause banner to `/approvals/{id}` without another call. Additive and optional.
2. **Memory endpoints on the Python side**: list `GET /internal/memories?userId&q&page&size`, delete one `DELETE /internal/memories/{id}?userId=` (returns `{deleted}`; 0 -> Spring answers 404), delete all `DELETE /internal/memories?userId=`. The contract line is ambiguous ("delete one" shares the path); the AI stream must match this or tell me.
3. **`limitations`**: taken from `report_ready.limitations` (string array) if the AI stream sends it, else parsed from the "Limitations and failures" section of the report Markdown (`LimitationsParser`). Not stored (no column in the frozen DDL).
4. **Python is not trusted for Spring-only events**: `run_started`, `approval_decided`, `action_executed` from Python are ignored; risk is looked up in the catalogue; an unknown action type or invalid params gets an approval row that is already REJECTED (no decider) and a FAILED action log, and the run still resumes with an explicit REJECT for it (decidedBy "system").
5. **Concurrent-run cap counts RUNNING runs only** (a run waiting for approval holds no relay thread). Exceeding it: 422 `QUOTA_EXCEEDED`. A saturated relay pool also answers 422 and marks the run FAILED.
6. **Expiry**: EXPIRED approvals are resumed as REJECT with comment "expired"; the job also settles any AWAITING_APPROVAL run that has no pending approval left (crash between last decision and resume).
7. **Cancel** while waiting: pending approvals become EXPIRED with an EXPIRED action log; nothing executes; a synthetic `done(CANCELLED)` event is persisted so every viewer's stream ends.
8. **`report_delta` has no seq and is never stored**: live viewers get it without an SSE `id`; replay and late joiners see only the final report.
9. **ApprovalDTO has no `expiresAt`** (contract frozen), although FE-AP-01 wants "expiry". Suggest adding it to contract v2.2 (the column exists).
10. **Low-risk action re-proposals** are de-duplicated by `actionKey` within one stream only.
11. Feedback requires a finished investigation and is owner-only (others who can see it get 403).

## Risks to check first on the first build (B)
- JSON columns use `JsonNode` with `@JdbcTypeCode(SqlTypes.JSON)`; if Hibernate rejects it, switch those fields to `String` + a converter.
- `numeric(4,3)` / `numeric(5,4)` mapped from `Double` via `columnDefinition` for `ddl-auto=validate`.
- `UPDATE ... RETURNING` through `JdbcTemplate.queryForObject` for `last_seq`.
- WireMock `withChunkedDribbleDelay` timing in the slow-stream tests; the SSE tests need Docker and a few seconds each.
- `Sinks`/`takeUntilOther` cancellation of the blocking iterator, and `toIterable()` on a `Flux` from `WebClient`.
