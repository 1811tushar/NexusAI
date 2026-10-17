# NexusAI — API & Data Contracts (v2.1, FROZEN)

> v2.1 patch (also: section 12 observability/metrics contract, AI `/metrics` endpoint, test-only `fake` LLM provider; adds guardrails, refusal status, ablation systems, extra eval metrics): `REFUSED` investigation status; `guardrail_triggered` event; `done.status` may be `REFUSED`; eval `system` has 4 values; eval metrics gain `retrievalHitRate`, `citationValidity`, `guardrailBlockRate`, `failureRecoveryRate`; report has a Limitations section; `limitations` field on the detail DTO.

Product: **NexusAI — Autonomous Enterprise Intelligence & Decision Platform** (agentic RAG + multi-agent investigation with verification, confidence scoring, memory and human approval).
This file is the single source of truth that lets frontend, backend and AI service be built in parallel. These four must always match:

`frontend types.ts` <-> `Java DTOs` <-> `Python api/schemas.py` <-> `this file`

If a field changes, change it HERE first, then in all three code bases in the same sitting. Every Spring response carries header `X-Contract-Version: 2.1`.

---

## 1. Conventions

| Topic | Rule |
|---|---|
| JSON | `camelCase` fields, `UPPER_SNAKE` enum values |
| IDs | `number` (BIGINT). UUID strings for `threadId`, `requestId`, `evidenceKey`, `actionKey` |
| Timestamps | ISO-8601 UTC strings |
| Envelope | Every JSON endpoint returns `ApiResponse<T>`. SSE and file downloads are exempt |
| Auth (public) | `Authorization: Bearer <accessToken>`; refresh token = httpOnly cookie `nx_refresh` (Path=/api/auth, SameSite=Lax, Secure in prod) |
| Auth (internal) | `X-Internal-API-Key` (constant-time compare). Python is never exposed publicly |
| Correlation | `X-Request-Id` (UUID) set by the browser/Spring and forwarded to Python |
| Pagination | `page` (0-based), `size` (default 20, max 100), `sort` |
| Authorisation | Role checks in `SecurityConfig` + ownership/visibility checks in services (matrix in section 2) |

```ts
interface ApiResponse<T> { success: boolean; data: T | null; error: ApiError | null; }
interface ApiError { code: ErrorCode; message: string; details?: Record<string, string>; requestId?: string; }
interface PagedResponse<T> { items: T[]; page: number; size: number; totalItems: number; totalPages: number; }
```
**Error codes (HTTP):** `VALIDATION_FAILED` 400, `INVALID_CREDENTIALS` 401, `TOKEN_EXPIRED` 401, `UNAUTHENTICATED` 401, `FORBIDDEN` 403, `SELF_APPROVAL_NOT_ALLOWED` 403, `NOT_FOUND` 404, `DUPLICATE_RESOURCE` 409, `INVALID_STATE` 409, `FILE_TOO_LARGE` 413, `UNSUPPORTED_FILE_TYPE` 415, `QUOTA_EXCEEDED` 422, `INGESTION_FAILED` 422, `RATE_LIMITED` 429, `AI_SERVICE_UNAVAILABLE` 503, `LLM_RATE_LIMITED` 503, `INTERNAL_ERROR` 500 (vague message).

## 2. Roles and permission matrix

Single-organisation deployment. **Documents are shared company knowledge** (every authenticated role may query them). **Investigations are owned by their creator.**

| Capability | ANALYST | APPROVER | ADMIN |
|---|---|---|---|
| View/search documents | yes | yes | yes |
| Upload documents | yes | no | yes |
| Delete/reindex documents | own only | no | any |
| Start / cancel investigation | yes (own) | no | yes (any cancel) |
| View investigations | own | all (read-only) | all |
| View approvals | for own investigations (read-only) | all | all |
| Decide approvals | no | yes | yes |
| Self-approval (decide on an approval of an investigation you started) | n/a | **forbidden** | **forbidden** |
| Memories (list/delete) | own | own | own |
| Action log | own investigations | all | all |
| Dashboard summary | yes (scoped) | yes | yes |
| Evaluation dashboard | no | no | yes |
| User administration | no | no | yes |

Rules: a foreign investigation id returns `404` for an ANALYST (never reveals existence). Registration is controlled by `REGISTRATION_OPEN` (true in dev: new users become ANALYST; false in prod: ADMIN creates users). An initial ADMIN is bootstrapped from env.

## 3. Enums

```ts
type Role = 'ADMIN' | 'ANALYST' | 'APPROVER';
type SourceType = 'PDF' | 'DOCX' | 'TXT' | 'MD';
type DocumentStatus = 'UPLOADED' | 'INGESTING' | 'READY' | 'FAILED' | 'DELETING';
type InvestigationStatus = 'RUNNING' | 'AWAITING_APPROVAL' | 'COMPLETED' | 'FAILED' | 'CANCELLED' | 'REFUSED';   // REFUSED = blocked by the input guardrail (nothing was executed)
type ClaimStatus = 'VERIFIED' | 'UNSUPPORTED' | 'CONTRADICTED';
type EvidenceKind = 'DOCUMENT' | 'SQL' | 'STATS' | 'WEB' | 'MEMORY';
type Risk = 'LOW' | 'HIGH';
type ApprovalStatus = 'PENDING' | 'APPROVED' | 'REJECTED' | 'EXPIRED';
type ActionType = 'FLAG_FOR_REVIEW' | 'CREATE_FOLLOWUP_TASK' | 'SAVE_INSIGHT'      // LOW risk, auto-executed
               | 'ADJUST_PRICE' | 'PAUSE_CAMPAIGN' | 'REALLOCATE_BUDGET';           // HIGH risk, need approval
type ActionStatus = 'EXECUTED' | 'REJECTED' | 'EXPIRED' | 'FAILED';
type AgentName = 'SUPERVISOR' | 'PLANNER' | 'RESEARCHER' | 'DATA_ANALYST' | 'ANALYST' | 'VERIFIER' | 'REPORTER';
type Theme = 'SYSTEM' | 'LIGHT' | 'DARK';
```
Risk is **defined by the action type in a fixed catalogue** (section 8), never by the LLM.

---

## 4. Public REST API (browser -> Spring Boot)

### 4.1 Auth, users
| Method + Path | Auth | Request | Response |
|---|---|---|---|
| POST `/api/auth/register` | public (if `REGISTRATION_OPEN`) | `RegisterRequest` | `AuthResponse` + cookie |
| POST `/api/auth/login` | public | `LoginRequest` | `AuthResponse` + cookie |
| POST `/api/auth/refresh` | cookie | none | `AuthResponse` (rotates; reuse revokes family) |
| POST `/api/auth/logout` | cookie | none | `null` |
| GET `/api/auth/me` | any | none | `UserDTO` |
| PATCH `/api/users/me` | any | `{ displayName }` | `UserDTO` |
| POST `/api/users/me/password` | any | `{ currentPassword, newPassword }` | `null` (revokes other sessions) |
| GET `/api/admin/users` | ADMIN | paged, `q`, `role` | `PagedResponse<UserDTO>` |
| POST `/api/admin/users` | ADMIN | `{ email, displayName, role, temporaryPassword }` | `UserDTO` |
| PATCH `/api/admin/users/{id}` | ADMIN | `{ role?, enabled? }` | `UserDTO` (cannot demote/disable the last ADMIN or yourself) |

```ts
interface RegisterRequest { email: string; password: string; displayName: string; }  // password >= 10 chars, letter + digit
interface LoginRequest { email: string; password: string; }
interface AuthResponse { accessToken: string; expiresInSeconds: number; user: UserDTO; }
interface UserDTO { id: number; email: string; displayName: string; role: Role; enabled: boolean; createdAt: string; }
```

### 4.2 Documents (company knowledge base)
| Method + Path | Auth | Notes |
|---|---|---|
| POST `/api/documents` | ADMIN, ANALYST | multipart `file` (PDF, DOCX, TXT, MD; 20 MB) -> `202` `DocumentDTO` |
| GET `/api/documents` | any | `q`, `status`, `sourceType`, paging |
| GET `/api/documents/{id}` | any | `DocumentDTO` |
| GET `/api/documents/{id}/chunks` | any | `page` query -> `PagedResponse<ChunkDTO>` (source viewer) |
| GET `/api/documents/{id}/file` | any | original bytes, safe headers |
| POST `/api/documents/{id}/reindex` | owner/ADMIN | `202` |
| DELETE `/api/documents/{id}` | owner/ADMIN | `204` (removes file, record, vectors; `DELETING` + retry if AI is down) |
| GET `/api/search` | any | `q`, `mode` (HYBRID/VECTOR/KEYWORD), `k` -> `SearchResultDTO[]` |
```ts
interface DocumentDTO { id: number; title: string; originalFilename: string; sourceType: SourceType; mimeType: string; sizeBytes: number;
  status: DocumentStatus; errorMessage: string | null; pageCount: number | null; chunkCount: number | null;
  uploadedBy: { id: number; displayName: string }; createdAt: string; ingestedAt: string | null; }
interface ChunkDTO { id: number; chunkIndex: number; page: number | null; section: string | null; content: string; }
interface SearchResultDTO { chunkId: number; documentId: number; documentTitle: string; page: number | null; section: string | null; snippet: string; score: number; }
```
Duplicate content hash (org-wide) -> `409 DUPLICATE_RESOURCE` with `details.existingDocumentId`.

### 4.3 Investigations (the core)
| Method + Path | Auth | Notes |
|---|---|---|
| POST `/api/investigations` | ADMIN, ANALYST | `StartInvestigationRequest` -> `202` `InvestigationDTO` (status RUNNING; run starts in the background and **continues even if the browser disconnects**) |
| GET `/api/investigations` | any (scoped) | paged; `status`, `q`, `mine=true` -> `PagedResponse<InvestigationDTO>` |
| GET `/api/investigations/{id}` | scoped | `InvestigationDetailDTO` |
| GET `/api/investigations/{id}/stream` | scoped | **SSE**. Replays persisted events then tails live. Supports `Last-Event-ID` header or `?after=seq`. Closes after the terminal event |
| GET `/api/investigations/{id}/steps` | scoped | `AgentStepDTO[]` (full persisted trace) |
| POST `/api/investigations/{id}/cancel` | owner/ADMIN | `204`; allowed in RUNNING or AWAITING_APPROVAL; else `INVALID_STATE` |
| GET `/api/investigations/{id}/report.md` | scoped | Markdown download (report + claims + citations + approvals) |
| POST `/api/investigations/{id}/feedback` | owner | `{ rating: 1 \| -1, comment? }` |
| GET `/api/dashboard/summary` | any (scoped) | `DashboardSummaryDTO` |

```ts
interface StartInvestigationRequest { question: string;            // 10..2000 chars
  options?: { webSearch?: boolean; documentIds?: number[]; useMemory?: boolean; maxLoops?: number; }; }  // defaults: webSearch true, useMemory true, maxLoops from config (<= 5)
interface InvestigationDTO { id: number; question: string; status: InvestigationStatus; confidence: number | null; loopsUsed: number;
  summary: string | null; owner: { id: number; displayName: string }; pendingApprovals: number; createdAt: string; completedAt: string | null; }
interface InvestigationDetailDTO extends InvestigationDTO { plan: PlanStep[]; reportMarkdown: string | null; limitations: string[]; guardrailEvents: { stage: string; action: string; category: string; detail: string }[]; claims: ClaimDTO[]; evidence: EvidenceDTO[];
  recommendations: RecommendationDTO[]; approvals: ApprovalDTO[]; actions: ActionLogDTO[]; errorMessage: string | null;
  usage: { inputTokens: number; outputTokens: number; latencyMs: number } | null; feedbackRating: 1 | -1 | null; }
interface PlanStep { id: string; description: string; agent: AgentName; status: 'PENDING' | 'RUNNING' | 'DONE' | 'FAILED'; }
interface ClaimDTO { id: number; text: string; status: ClaimStatus; confidence: number; isKey: boolean; evidenceKeys: string[]; }
interface EvidenceDTO { evidenceKey: string; kind: EvidenceKind; title: string; snippet: string;
  source: { documentId?: number; page?: number; url?: string; sql?: string; table?: string; investigationId?: number };
  data?: { columns: string[]; rows: (string | number | null)[][]; truncated: boolean };            // SQL/STATS tabular result preview (<= 50 rows)
  chart?: { type: 'line' | 'bar'; x: string[]; series: { name: string; values: number[] }[] };    // optional chart-ready series
  score: number | null; createdAt: string; }
interface RecommendationDTO { id: string; text: string; risk: Risk; actionKey: string | null; }   // actionKey links to an action/approval when the recommendation is executable
interface DashboardSummaryDTO { investigationsByStatus: Record<InvestigationStatus, number>; pendingApprovals: number; documentsReady: number;
  avgConfidence30d: number | null; recent: InvestigationDTO[]; }
```

### 4.4 Approvals and actions
| Method + Path | Auth | Notes |
|---|---|---|
| GET `/api/approvals` | scoped | `status`, paging -> `PagedResponse<ApprovalDTO>`; `GET /api/approvals/pending-count` -> `{ count }` |
| GET `/api/approvals/{id}` | scoped | `ApprovalDTO` |
| POST `/api/approvals/{id}/decision` | APPROVER, ADMIN | `{ decision: 'APPROVE' \| 'REJECT', comment? }` (comment required on REJECT); `409 INVALID_STATE` if not PENDING; `403 SELF_APPROVAL_NOT_ALLOWED` |
| GET `/api/actions` | scoped | paged `ActionLogDTO` (audit view) |
```ts
interface ApprovalDTO { id: number; investigationId: number; investigationQuestion: string; actionKey: string; actionType: ActionType; title: string;
  description: string; params: Record<string, unknown>; risk: Risk; rationale: string; evidenceKeys: string[]; confidence: number | null;
  status: ApprovalStatus; requestedAt: string; decidedBy: { id: number; displayName: string } | null; decidedAt: string | null; comment: string | null; }
interface ActionLogDTO { id: number; investigationId: number; approvalId: number | null; actionType: ActionType; params: Record<string, unknown>;
  risk: Risk; status: ActionStatus; automatic: boolean; executedAt: string; note: string; }   // note always states: "Simulated execution; no external system was changed."
```
When the last pending approval of an investigation is decided, Spring executes approved actions (simulated, logged), then resumes the Python run (section 7). Rejected actions are logged as `REJECTED`.

### 4.5 Memory, admin eval, platform
| Method + Path | Auth | Notes |
|---|---|---|
| GET `/api/memories` | any | own, paged, `q` -> `PagedResponse<MemoryDTO>` |
| DELETE `/api/memories/{id}` / DELETE `/api/memories` | any | own; `204` |
| GET `/api/eval/runs`, `/api/eval/runs/{id}` | ADMIN | `EvalRunDTO[]` / `EvalRunDetailDTO` |
| GET `/actuator/health` | public | prometheus only on the internal network; Swagger dev only |
```ts
interface MemoryDTO { id: number; summary: string; sourceInvestigationId: number | null; importance: number; createdAt: string; lastAccessedAt: string | null; }
interface EvalRunDTO { id: number; createdAt: string; variant: string | null;   // e.g. chunking/reranker ablation label for retrieval runs
  system: 'BASELINE' | 'SINGLE_AGENT' | 'AGENT_NO_VERIFIER' | 'AGENT'; questionCount: number;
  metrics: { answerCorrectness: number; groundedClaimsShare: number; hallucinationRate: number; avgLatencyMs: number; avgTokens: number;
             approvalGateCompliance: number | null; retrievalHitRate: number | null; citationValidity: number | null;
             guardrailBlockRate: number | null; failureRecoveryRate: number | null; }; }
interface EvalRunDetailDTO extends EvalRunDTO { results: { questionId: string; category: 'NORMAL' | 'EDGE' | 'ADVERSARIAL' | 'MISSING_DATA' | 'TOOL_FAILURE'; question: string; expectedFacts: string[]; answer: string;
  correct: boolean; groundedShare: number; hallucinated: boolean; latencyMs: number }[]; }
```
Eval runs are started from the CLI (`python -m app.evals.run_eval`), never from the UI.

---

## 5. Agent event vocabulary and SSE stream

```ts
type AgentEventType = 'run_started' | 'memory_recalled' | 'supervisor_routed' | 'plan' | 'step_status' | 'agent_started' | 'tool_call' | 'tool_result'
  | 'evidence_added' | 'claims_drafted' | 'claim_verified' | 'confidence' | 'loop' | 'action_proposed' | 'approval_required'
  | 'approval_decided' | 'action_executed' | 'guardrail_triggered' | 'report_delta' | 'report_ready' | 'memory_saved' | 'error' | 'done';
```
SSE frame: `id: <seq>`, `event: <type>`, `data: <json>`. **seq is assigned by Spring** (monotonic per investigation) and is how replay/resume works. Spring also emits `: ping` every 15 s. Exactly one of `done` / `error` terminates a stream; `approval_required` ends one Python stream but NOT the investigation: the browser stream stays open (status AWAITING_APPROVAL, heartbeat continues) until the run resumes and finishes, or the browser disconnects (it may reconnect with `Last-Event-ID`).

| Event | Payload |
|---|---|
| `run_started` | `{ investigationId: number, threadId: string, startedAt: string }` (Spring) |
| `memory_recalled` | `{ items: { id: number, summary: string, score: number }[] }` |
| `supervisor_routed` | `{ agents: AgentName[], reason: string }` |
| `plan` | `{ steps: PlanStep[] }` |
| `step_status` | `{ stepId: string, status: 'RUNNING' \| 'DONE' \| 'FAILED' }` |
| `agent_started` | `{ agent: AgentName, stepId: string \| null }` |
| `tool_call` | `{ callId: string, agent: AgentName, tool: ToolName, args: object }` |
| `tool_result` | `{ callId: string, tool: ToolName, ok: boolean, summary: string, durationMs: number }` |
| `evidence_added` | `{ evidence: EvidenceDTO }` |
| `claims_drafted` | `{ claims: { claimKey: string, text: string, isKey: boolean, evidenceKeys: string[] }[] }` |
| `claim_verified` | `{ claimKey: string, text: string, status: ClaimStatus, confidence: number, evidenceKeys: string[], reason: string }` |
| `confidence` | `{ overall: number, threshold: number, decision: 'ACCEPT' \| 'LOOP' \| 'ACCEPT_LOW_CONFIDENCE', loop: number }` |
| `loop` | `{ loop: number, maxLoops: number, reason: string, focus: string[] }` |
| `action_proposed` | `{ actionKey: string, actionType: ActionType, risk: Risk, title: string, description: string, params: object, rationale: string, evidenceKeys: string[] }` |
| `approval_required` | `{ actions: { actionKey: string, ... same fields as action_proposed }[] }` (all HIGH-risk actions pending; Python then pauses via `interrupt()`) |
| `approval_decided` | `{ approvalId: number, actionKey: string, decision: 'APPROVE' \| 'REJECT', decidedBy: string, comment: string \| null }` (Spring, before resume) |
| `action_executed` | `{ actionLogId: number, actionKey: string, actionType: ActionType, status: ActionStatus, automatic: boolean, note: string }` (Spring) |
| `guardrail_triggered` | `{ stage: 'INPUT' \| 'TOOL' \| 'OUTPUT', action: 'BLOCKED' \| 'REDACTED' \| 'FLAGGED', category: 'PROMPT_INJECTION' \| 'OFF_TOPIC' \| 'UNSAFE_REQUEST' \| 'PII' \| 'INVALID_CITATION' \| 'INVALID_OUTPUT', detail: string }` (never contains the redacted value) |
| `report_delta` | `{ text: string }` (not persisted individually) |
| `report_ready` | `{ reportMarkdown: string, summary: string, recommendations: RecommendationDTO[], confidence: number }` |
| `memory_saved` | `{ id: number, summary: string }` |
| `error` | `{ code: ErrorCode, message: string, retryable: boolean }` |
| `done` | `{ status: 'COMPLETED' \| 'CANCELLED' \| 'REFUSED', confidence: number \| null, loopsUsed: number, usage: { inputTokens: number, outputTokens: number }, latencyMs: number }` |

`type ToolName = 'rag_search' | 'sql_query' | 'web_search' | 'stats_compare' | 'stats_contribution' | 'stats_anomaly' | 'recall_memory'`

Spring persistence of events: all events except `report_delta` go to `agent_steps`; `evidence_added` also writes `evidence`; `claim_verified` writes `claims`; `plan` and `step_status` update `investigations.plan`; `action_proposed` with LOW risk is executed automatically by Spring (`action_executed`); `approval_required` creates `approvals` rows; `report_ready` fills report/summary/recommendations/confidence.

---

## 6. Internal API (Spring -> Python); all need `X-Internal-API-Key`

| Method + Path | Purpose | Request | Response |
|---|---|---|---|
| GET `/health` | no key | | `{ status, embeddingModel, llmProvider }` |
| GET `/metrics` | no key (Docker-internal network only; never proxied) | | Prometheus text format, metric names in section 12 |
| POST `/internal/ingest` | multipart: `meta` JSON + `file`; sync, timeout 120 s | `IngestRequest` | `IngestResponse` |
| DELETE `/internal/documents/{documentId}` | remove chunks | | `{ deleted }` |
| GET `/internal/documents/{documentId}/chunks?page=&size=` | viewer | | `PagedResponse<ChunkDTO>` |
| POST `/internal/search` | library search | `{ query, mode, k, documentIds? }` | `SearchResultDTO[]` |
| POST `/internal/investigate` | **SSE** start a run | `InvestigateRequest` | events (section 5, minus Spring-originated ones) |
| POST `/internal/investigate/{threadId}/resume` | **SSE** continue after approvals | `ResumeRequest` | events |
| POST `/internal/investigate/{threadId}/cancel` | stop a running/paused run | | `{ cancelled: boolean }` |
| GET/DELETE `/internal/memories?userId=...` | list / delete one / delete all | | `PagedResponse<MemoryDTO>` / `{ deleted }` |
| DELETE `/internal/users/{userId}` | purge memories and checkpoints | | `{ memories, checkpoints }` |
| GET `/internal/eval/runs`, `/internal/eval/runs/{id}` | dashboard | | `EvalRunDTO` / detail |

```ts
interface IngestRequest { documentId: number; uploadedByUserId: number; sourceType: SourceType; title: string; filename: string; }
interface IngestResponse { documentId: number; pageCount: number | null; chunkCount: number; warnings: string[]; }
interface InvestigateRequest { investigationId: number; threadId: string; userId: number; question: string;
  options: { webSearch: boolean; documentIds: number[] | null; useMemory: boolean; maxLoops: number }; now: string; }
interface ResumeRequest { investigationId: number; decisions: { actionKey: string; approvalId: number; decision: 'APPROVE' | 'REJECT'; decidedBy: string; comment: string | null }[]; }
```
Python never receives passwords, tokens or role data other than `userId`. Failure mapping in Spring: connection/5xx -> `AI_SERVICE_UNAVAILABLE`; upstream 429 after retries -> `LLM_RATE_LIMITED`.

---

## 7. Run lifecycle (state machine)

`RUNNING` -> (high-risk action proposed) -> `AWAITING_APPROVAL` -> (all decided) -> `RUNNING` -> `COMPLETED`
Any non-terminal state -> `FAILED` (error event / upstream failure / startup recovery of orphaned runs) or `CANCELLED`.
Rules: high-risk actions are **never** executed before an APPROVE decision is stored; a REJECT is final for that action; if there are no HIGH-risk proposals the run never pauses; a run pending approval longer than `APPROVAL_TTL_DAYS` (default 7) expires: approvals -> `EXPIRED`, actions logged `EXPIRED`, run resumes to finish the report noting that no action was taken. On Spring startup, runs left `RUNNING` with no live relay are marked `FAILED` ("interrupted by restart") unless resumable from the checkpoint (P2).

---

## 8. Action catalogue (risk is fixed here)

| ActionType | Risk | Params | Behaviour (simulated; recorded in `action_log`) |
|---|---|---|---|
| `FLAG_FOR_REVIEW` | LOW | `{ subject: string, reason: string }` | auto-executed |
| `CREATE_FOLLOWUP_TASK` | LOW | `{ title: string, ownerRole: Role, dueInDays: number }` | auto-executed |
| `SAVE_INSIGHT` | LOW | `{ title: string, text: string }` | auto-executed |
| `ADJUST_PRICE` | HIGH | `{ productId: number, changePct: number }` (|changePct| <= 30) | after APPROVE |
| `PAUSE_CAMPAIGN` | HIGH | `{ regionId: number, channel: string, weeks: number }` | after APPROVE |
| `REALLOCATE_BUDGET` | HIGH | `{ fromRegionId: number, toRegionId: number, amount: number }` | after APPROVE |
The agent can only propose actions from this catalogue; params are validated by Pydantic in Python and again by Spring (unknown type or invalid params -> action rejected and logged `FAILED`).

## 9. Confidence model (documented so it can be evaluated)

- Claim confidence = `0.5*support + 0.3*agreement + 0.2*quality`, where `support` = verifier's 0..1 score that the evidence entails the claim; `agreement` = min(1, independentSources/2) (independent = distinct document, SQL result or web domain); `quality` = 1.0 for SQL/STATS numeric evidence, normalised retrieval score (0..1) for document/web evidence. CONTRADICTED claims are capped at 0.3; UNSUPPORTED at 0.4.
- Overall confidence = weighted mean of claim confidences (key claims weight 2, others 1).
- Decision: `overall >= CONFIDENCE_MIN` (default 0.7) -> `ACCEPT`; else `LOOP` while `loop < maxLoops` (the focus list names the weakest claims); at the limit -> `ACCEPT_LOW_CONFIDENCE`, and the report must carry a visible low-confidence banner. Unsupported/contradicted claims are shown as such, never silently dropped or presented as facts.

---

## 10. Database contract

### 10.1 `public` schema (Spring, Flyway; one migration per feature)

```sql
-- V1__create_users_auth.sql
CREATE EXTENSION IF NOT EXISTS citext;
CREATE TABLE users (id BIGSERIAL PRIMARY KEY, email CITEXT NOT NULL UNIQUE, password_hash VARCHAR(100) NOT NULL,
  display_name VARCHAR(80) NOT NULL, role VARCHAR(10) NOT NULL DEFAULT 'ANALYST', enabled BOOLEAN NOT NULL DEFAULT TRUE,
  failed_logins INT NOT NULL DEFAULT 0, locked_until TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE refresh_tokens (id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash CHAR(64) NOT NULL UNIQUE, family_id UUID NOT NULL, expires_at TIMESTAMPTZ NOT NULL, revoked_at TIMESTAMPTZ,
  user_agent VARCHAR(255), created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE INDEX idx_refresh_user ON refresh_tokens(user_id);

-- V2__create_documents.sql
CREATE TABLE documents (id BIGSERIAL PRIMARY KEY, uploaded_by BIGINT NOT NULL REFERENCES users(id),
  title VARCHAR(255) NOT NULL, original_filename VARCHAR(255) NOT NULL, source_type VARCHAR(8) NOT NULL, mime_type VARCHAR(100),
  size_bytes BIGINT NOT NULL, storage_key VARCHAR(255) NOT NULL, status VARCHAR(12) NOT NULL DEFAULT 'UPLOADED', error_message TEXT,
  page_count INT, chunk_count INT, content_hash CHAR(64) NOT NULL UNIQUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(), ingested_at TIMESTAMPTZ);
CREATE INDEX idx_documents_status ON documents(status);

-- V3__create_investigations.sql
CREATE TABLE investigations (id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL REFERENCES users(id), question TEXT NOT NULL,
  status VARCHAR(18) NOT NULL DEFAULT 'RUNNING', options JSONB NOT NULL DEFAULT '{}', thread_id UUID NOT NULL UNIQUE,
  plan JSONB NOT NULL DEFAULT '[]', report_markdown TEXT, summary TEXT, confidence NUMERIC(4,3), loops_used INT NOT NULL DEFAULT 0,
  recommendations JSONB NOT NULL DEFAULT '[]', usage JSONB, latency_ms INT, error_message TEXT, feedback_rating SMALLINT, feedback_comment TEXT,
  last_seq INT NOT NULL DEFAULT 0, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), completed_at TIMESTAMPTZ);
CREATE INDEX idx_inv_user_created ON investigations(user_id, created_at DESC);
CREATE INDEX idx_inv_status ON investigations(status);
CREATE TABLE agent_steps (id BIGSERIAL PRIMARY KEY, investigation_id BIGINT NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
  seq INT NOT NULL, type VARCHAR(30) NOT NULL, payload JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), UNIQUE (investigation_id, seq));
CREATE TABLE evidence (id BIGSERIAL PRIMARY KEY, investigation_id BIGINT NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
  evidence_key UUID NOT NULL, kind VARCHAR(10) NOT NULL, title VARCHAR(255) NOT NULL, snippet TEXT NOT NULL, source JSONB NOT NULL DEFAULT '{}',
  data JSONB, chart JSONB, score NUMERIC(5,4), created_at TIMESTAMPTZ NOT NULL DEFAULT now(), UNIQUE (investigation_id, evidence_key));
CREATE TABLE claims (id BIGSERIAL PRIMARY KEY, investigation_id BIGINT NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
  claim_key VARCHAR(40) NOT NULL, text TEXT NOT NULL, status VARCHAR(12) NOT NULL, confidence NUMERIC(4,3) NOT NULL, is_key BOOLEAN NOT NULL DEFAULT FALSE,
  evidence_keys JSONB NOT NULL DEFAULT '[]', loop INT NOT NULL DEFAULT 0, created_at TIMESTAMPTZ NOT NULL DEFAULT now());  -- latest verification per claim_key wins in the API

-- V4__create_approvals_actions.sql
CREATE TABLE approvals (id BIGSERIAL PRIMARY KEY, investigation_id BIGINT NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
  action_key VARCHAR(40) NOT NULL, action_type VARCHAR(24) NOT NULL, title VARCHAR(255) NOT NULL, description TEXT NOT NULL, params JSONB NOT NULL,
  risk VARCHAR(4) NOT NULL, rationale TEXT NOT NULL, evidence_keys JSONB NOT NULL DEFAULT '[]', status VARCHAR(10) NOT NULL DEFAULT 'PENDING',
  requested_at TIMESTAMPTZ NOT NULL DEFAULT now(), decided_by BIGINT REFERENCES users(id), decided_at TIMESTAMPTZ, comment TEXT, expires_at TIMESTAMPTZ NOT NULL,
  UNIQUE (investigation_id, action_key));
CREATE INDEX idx_approvals_status ON approvals(status);
CREATE TABLE action_log (id BIGSERIAL PRIMARY KEY, investigation_id BIGINT NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
  approval_id BIGINT REFERENCES approvals(id), action_type VARCHAR(24) NOT NULL, params JSONB NOT NULL, risk VARCHAR(4) NOT NULL,
  status VARCHAR(10) NOT NULL, automatic BOOLEAN NOT NULL, note TEXT NOT NULL, executed_at TIMESTAMPTZ NOT NULL DEFAULT now());

-- V5__create_audit_log.sql
CREATE TABLE audit_log (id BIGSERIAL PRIMARY KEY, user_id BIGINT, action VARCHAR(50) NOT NULL, entity VARCHAR(30), entity_id VARCHAR(50),
  ip VARCHAR(45), created_at TIMESTAMPTZ NOT NULL DEFAULT now());

-- V6__create_business_data.sql   (tables the SQL tool may read; synthetic company data)
CREATE TABLE regions (id SMALLINT PRIMARY KEY, name VARCHAR(40) NOT NULL UNIQUE);
CREATE TABLE products (id INT PRIMARY KEY, sku VARCHAR(20) NOT NULL UNIQUE, name VARCHAR(80) NOT NULL, category VARCHAR(30) NOT NULL,
  unit_price NUMERIC(10,2) NOT NULL, unit_cost NUMERIC(10,2) NOT NULL);
CREATE TABLE sales (id BIGSERIAL PRIMARY KEY, sale_month DATE NOT NULL, region_id SMALLINT NOT NULL REFERENCES regions(id),
  product_id INT NOT NULL REFERENCES products(id), units INT NOT NULL, revenue NUMERIC(14,2) NOT NULL, cost NUMERIC(14,2) NOT NULL,
  UNIQUE (sale_month, region_id, product_id));
CREATE TABLE marketing_spend (id BIGSERIAL PRIMARY KEY, month DATE NOT NULL, region_id SMALLINT NOT NULL REFERENCES regions(id),
  channel VARCHAR(30) NOT NULL, spend NUMERIC(12,2) NOT NULL, UNIQUE (month, region_id, channel));
CREATE TABLE customer_metrics (id BIGSERIAL PRIMARY KEY, month DATE NOT NULL, region_id SMALLINT NOT NULL REFERENCES regions(id),
  active_customers INT NOT NULL, new_customers INT NOT NULL, churned_customers INT NOT NULL, UNIQUE (month, region_id));
DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ai_readonly') THEN
  GRANT USAGE ON SCHEMA public TO ai_readonly;
  GRANT SELECT ON regions, products, sales, marketing_spend, customer_metrics TO ai_readonly; END IF; END $$;
-- V7__seed_business_data.sql   (generated deterministically by the seed generator; see Prompt 4). NEVER grant ai_readonly access to users, refresh_tokens, approvals, etc.
```

### 10.2 `ai` schema (Python; created by `infra/postgres/init.sql`; LangGraph checkpoint tables by `checkpointer.setup()`)
```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS ai;
CREATE TABLE ai.document_chunks (id BIGSERIAL PRIMARY KEY, document_id BIGINT NOT NULL, chunk_index INT NOT NULL, page INT, section TEXT,
  content TEXT NOT NULL, embedding vector(384) NOT NULL,                       -- BAAI/bge-small-en-v1.5
  tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED, metadata JSONB NOT NULL DEFAULT '{}', created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE INDEX idx_chunks_embedding ON ai.document_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_chunks_tsv ON ai.document_chunks USING gin (tsv);
CREATE INDEX idx_chunks_document ON ai.document_chunks (document_id);
CREATE TABLE ai.memories (id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL, summary TEXT NOT NULL, embedding vector(384) NOT NULL,
  importance REAL NOT NULL DEFAULT 0.5, source_investigation_id BIGINT, access_count INT NOT NULL DEFAULT 0, last_accessed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE INDEX idx_memories_embedding ON ai.memories USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_memories_user ON ai.memories (user_id);
CREATE TABLE ai.eval_runs (id BIGSERIAL PRIMARY KEY, system VARCHAR(20) NOT NULL, variant VARCHAR(60), config JSONB NOT NULL, metrics JSONB NOT NULL, results JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now());
```
Roles: `nexus` (Spring + Flyway owner), `ai_rw` (read/write on schema `ai` only), `ai_readonly` (SELECT on the five business tables only, connection defaults: `default_transaction_read_only=on`, `statement_timeout=5000`). Deliberate decision: chunks carry **no** `user_id` because the knowledge base is organisation-wide; memories **are** per-user (`user_id` filter mandatory + test). Cross-schema consistency (delete document -> delete chunks) is application-level with the `DELETING` retry.
Memory recall score: `0.5*relevance + 0.3*exp(-ageDays/30) + 0.2*importance`, top 5, minimum relevance floor.

## 11. Configuration contract

| Var | Used by | Default / meaning |
|---|---|---|
| `POSTGRES_DB/USER/PASSWORD` | postgres, backend | admin DB credentials |
| `JWT_SECRET`, `JWT_ACCESS_MINUTES`, `JWT_REFRESH_DAYS`, `COOKIE_SECURE` | backend | secret >= 32 chars; 15; 14; false dev / true prod |
| `REGISTRATION_OPEN`, `ADMIN_EMAIL`, `ADMIN_PASSWORD` | backend | true dev; bootstrap admin only if none exists |
| `INTERNAL_API_KEY`, `AI_SERVICE_URL` | backend, ai | shared secret; `http://ai-service:8000` |
| `UPLOAD_DIR`, `MAX_UPLOAD_MB`, `MAX_DOCS_TOTAL` | backend | `/data/uploads`, 20, 500 |
| `APPROVAL_TTL_DAYS`, `MAX_CONCURRENT_RUNS_PER_USER`, `RATE_LIMIT_AUTH_PER_MIN` | backend | 7, 2, 10 |
| `CORS_ALLOWED_ORIGINS` | backend | dev `http://localhost:5173` |
| `LLM_PROVIDER` | ai | `gemini` \| `ollama` (\| `groq`, optional) \| `fake` (TEST-ONLY scripted deterministic model used by CI and unit tests; makes no network call) |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | ai | model name MUST be confirmed in Google AI Studio |
| `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | ai | local fallback; model must support tool calling |
| `EMBEDDING_MODEL` | ai | `BAAI/bge-small-en-v1.5` |
| `TAVILY_API_KEY`, `WEB_SEARCH_ENABLED` | ai | key optional (ddgs fallback); global kill switch |
| `AI_DB_RW_USER/PASSWORD`, `AI_DB_RO_USER/PASSWORD`, `AI_DB_HOST`, `AI_DB_NAME` | ai | roles from init.sql |
| `MAX_LOOPS`, `CONFIDENCE_MIN`, `TOP_K`, `SQL_ROW_LIMIT`, `SQL_TIMEOUT_MS` | ai | 3, 0.7, 8, 200, 5000 |
| `MAX_TOOL_ATTEMPTS`, `GUARDRAILS_ENABLED`, `PII_REDACTION_ENABLED`, `RERANKER_ENABLED`, `CHUNKING_MODE` | ai | 3, true, true, false, `semantic` (`fixed` only for the ablation) |
| `LANGFUSE_PUBLIC_KEY/SECRET_KEY/HOST` | ai | optional tracing |
| `VITE_API_BASE_URL`, `VITE_USE_MOCKS` | frontend | `/api`, false |

## 12. Observability contract (metric names are fixed so the Grafana dashboard and alerts work)

**Backend (Micrometer; exposed at `/actuator/prometheus`, reachable only inside the Docker network).** Required properties: `management.endpoints.web.exposure.include=health,prometheus`; `management.metrics.distribution.percentiles-histogram.http.server.requests=true`; histograms enabled for every `nexusai.*` timer. `SecurityConfig` must `permitAll` for `/actuator/health` and `/actuator/prometheus` (the backend port is not published and nginx returns 404 for `/actuator/prometheus`).

| Prometheus name | Type | Labels | Emitted by |
|---|---|---|---|
| `nexusai_run_duration_seconds` | histogram (Timer `nexusai.run.duration`) | `status` = COMPLETED, FAILED, CANCELLED, REFUSED | investigation run relay, at terminal state |
| `nexusai_pending_approvals` | gauge | none | approval service (count of PENDING) |
| `nexusai_ai_request_duration_seconds` | histogram | `endpoint` = ingest, search, investigate, resume, memories, eval | `AiServiceClient` |
| `nexusai_ai_errors_total` | counter | `type` = unavailable, rate_limited, timeout, bad_response | `AiServiceClient` |
| `nexusai_ingestion_duration_seconds` | histogram | `status` = READY, FAILED | document ingestion |
| `nexusai_guardrail_events_total` | counter | `stage`, `action`, `category` | run relay, per persisted `guardrail_triggered` event |

**AI service (`prometheus-client`; `GET /metrics`, no API key, internal network only).**

| Prometheus name | Type | Labels |
|---|---|---|
| `nexusai_ai_node_duration_seconds` | histogram | `node` (graph node name) |
| `nexusai_ai_tool_calls_total` | counter | `tool`, `ok` (true/false) |
| `nexusai_ai_llm_tokens_total` | counter | `direction` (input/output) |
| `nexusai_ai_llm_errors_total` | counter | `type` (rate_limited, timeout, invalid_output, unavailable) |
| `nexusai_ai_guardrail_events_total` | counter | `stage`, `action`, `category` |
| `nexusai_ai_runs_total` | counter | `outcome` (completed, refused, failed, cancelled, paused) |

Metrics must never carry document text, questions, user identifiers or other high-cardinality or sensitive values in labels.

## 13. CI evaluation artefacts (file formats the `eval-ci` workflow reads and writes)
- `ai-service/evals/baseline_metrics.json`: `{ "status": "MEASURED" | "NOT_MEASURED", "metrics": { ...same keys as `EvalRunDTO.metrics` ... }, "recordedAt": "...", "commit": "..." }`. While `NOT_MEASURED`, CI warns and skips the regression comparison but still runs every safety check.
- `python -m app.evals.ci_check` (no LLM, no secrets, `LLM_PROVIDER=fake`, `EVAL_MODE=ci`): runs guardrail/adversarial, SQL-guard, approval-gate-compliance, citation-validator and fault-injection tests plus the retrieval ablation; writes `ai-service/evals/ci-results.json` (`{ "status": "PASS" | "FAIL", "metrics": { ... }, "failures": [ ... ] }`) and `ai-service/evals/results/` artefacts; exits non-zero on any safety failure or, when `EVAL_BASELINE_MEASURED=true`, on a retrieval-hit-rate regression larger than 2 percentage points.
- `python -m app.evals.run_eval --system both --limit N` (real LLM; manual or scheduled): writes rows to `ai.eval_runs` and `ai-service/evals/results/`.
