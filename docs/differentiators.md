# NexusAI — Differentiators Addendum (v2.1): making the project stand out

Purpose: most "agentic RAG" portfolios look alike. The reference images you shared make five points (deep project, concrete metrics, failure handling, core skills over frameworks, technical stories) and show specific artefacts (evaluation harness, retrieval hit-rate ablation, single-prompt vs multi-agent trade-off, bounded retry loops, guardrails, permission layer, CI evaluation suite). This addendum states, honestly, what the pack already covered, what was missing, and the exact additions. Attach this file to every build prompt together with files 01 to 04 and 06 (contract is now v2.1).

The numbers in those images (82%, 71% -> 86% -> 91%, 62% vs 88%, 14/15 blocked) are the video's illustrations. **Your numbers must come from your own runs.** Never copy them.

---

## 1. Honest gap table

| Idea from the images | Already in the pack? | Gap | Addition (ID) |
|---|---|---|---|
| Heavy, deep project | Yes: 7 agents, verification loop, approvals, memory, replayable runs | none | none |
| Evaluation harness with 20-50 examples | Yes (golden set, 30-50) | Only agent vs one baseline | 3 systems + categories (ADD-EV-01, 02) |
| Retrieval hit-rate improvement (fixed -> semantic -> reranker) | Partly: semantic chunking existed, reranker was P2, **no ablation** | No measured retrieval experiment | Retrieval ablation (ADD-EV-03) |
| Single-prompt vs multi-agent quality/token trade-off | Partly: single-shot RAG baseline | No "single agent" and "no verifier" variants, no trade-off chart | Ablation systems + trade-off view (ADD-EV-02, ADD-FE-01) |
| Feedback loop, max 3 rounds | Yes (confidence loop, `maxLoops`) | none | none |
| Execute with bounded retries, then stop and explain failure | Partly (SQL retries bounded) | No uniform failure policy, no "explain failure" output, no fault injection | Failure-handling policy + Limitations section (ADD-FH-01..04) |
| Permission layer / confirmation before risky actions | Yes (approval gate, catalogue, self-approval ban) | none (confirmation is in-app approval, not e-mail) | none |
| Input guardrail | **No** (only document-injection defence) | Missing | Input guardrail + REFUSED status (ADD-GR-01) |
| PII redaction | **No** | Missing | PII redaction (ADD-GR-02) |
| Citation validation / output validation | Partly (verifier, Pydantic outputs) | No programmatic citation check | Citation validator (ADD-GR-03, 04) |
| Evaluation suite as a CI gate on git push | **No** (pack said LLM tests never run in CI) | Missing | `eval-ci` workflow (ADD-CI-01, 02) |
| Tracing: "how do you trace a bad answer?" | Yes (persisted steps + optional Langfuse) | Needs a documented debugging walkthrough | Story 5 (ADD-ST-01) |
| Core skills over frameworks | Mostly (own SQL guard, RRF, confidence math, state machine) | Not written down | "Under the hood" doc (ADD-ST-02) |
| Compelling technical stories | No | Missing | Engineering stories doc (ADD-ST-01) |

### What your previous project (NearNow) had, from the documents I can see
I checked the NearNow Final Checklist and the Parallel Build Prompts you uploaded (and earlier the repo README and design-decisions page). In those: AI answers with a **source citation line**, a **basic NLI-style groundedness check** on the RAG answer, **read-only tools** with a `requires_human_approval` flag for risky actions, JWT/API-key security, and CI. I found **no evaluation harness, golden set or baseline comparison, no retrieval metrics, no guardrails, no PII redaction and no prompt-injection work** in those documents. The AI roadmap you shared planned Langfuse tracing and a human-approval pass, but I cannot confirm from the documents that they were built. I have not read the repository's source code, so if an evaluation or guardrail module exists there, I have not seen it.

NexusAI therefore adds what NearNow lacked: measured evaluation, ablations, guardrails and a CI evaluation gate.

---

## 2. New requirements (added to the master checklist as section K)

### K1. Guardrails (AI service; events per contract v2.1)
- **ADD-GR-01 (P0) Input guardrail.** First graph node `input_guard`. Deterministic rules first (length, known injection phrases, requests to ignore instructions/reveal prompts/run write SQL/approve actions), then an LLM classifier only for ambiguous cases. Categories: `PROMPT_INJECTION`, `OFF_TOPIC`, `UNSAFE_REQUEST`. Blocked input emits `guardrail_triggered` (stage INPUT, action BLOCKED) then `done` with status `REFUSED`; Spring stores status `REFUSED`; the UI shows a clear, polite refusal with the reason category. Nothing else runs. Must not block normal business questions (false-positive rate measured in the eval).
- **ADD-GR-02 (P0) PII redaction.** `core/pii.py`: regex + checksum redaction of emails, phone numbers, card-like numbers, national-ID-like numbers. Applied to (a) any text sent to web search, (b) text sent to Langfuse, (c) logs, (d) the memory summary before storage. Emits `guardrail_triggered` (action REDACTED, category PII) without the value. The synthetic corpus deliberately contains fake PII so redaction is demonstrable and testable.
- **ADD-GR-03 (P0) Citation validation.** After the Reporter, `agents/citation_check.py` verifies programmatically: every cited evidence key exists; numbers in a sentence appear in the cited evidence (SQL/STATS tables) within rounding tolerance; quoted document text is a substring/near-match of the chunk. Invalid citations are removed or the sentence is moved to "Unverified"; event `guardrail_triggered` (stage OUTPUT, category INVALID_CITATION). Metric: `citationValidity`.
- **ADD-GR-04 (P0) Output validation.** Report, recommendations and action params are validated against Pydantic schemas (catalogue params, risk fixed by catalogue); invalid output gets one repair attempt, then a safe fallback (category INVALID_OUTPUT).
- **ADD-GR-05 (P1) Tool-stage guard.** SQL guard, allow-listed tables, web search query redaction are reported as `guardrail_triggered` (stage TOOL) so they are visible in the timeline and traces.

### K2. Failure handling (the "stop and explain" policy)
One policy, implemented in a single helper (`agents/failure.py`) and used by every tool call:
- **ADD-FH-01 (P0)** Every tool call: timeout, `MAX_TOOL_ATTEMPTS` (default 3) with the failure reason fed back to the agent so it can fix its attempt (SQL error text, guard rejection reason), exponential backoff for transient errors.
- **ADD-FH-02 (P0)** After the last attempt: **stop and explain**. The failure is recorded (`tool_result ok:false` with a readable reason), the dependent claims lose confidence or become UNSUPPORTED, and the final report contains a **"Limitations and failures"** section listing what could not be checked and why. The run continues with remaining evidence; it never silently drops a failure and never invents the missing data.
- **ADD-FH-03 (P0)** Whole-run failure modes (LLM down, rate limit exhausted, database unreachable): the run ends FAILED with a human-readable explanation and the partial trace preserved.
- **ADD-FH-04 (P0)** Fault-injection tests: tool timeout, SQL error, empty retrieval, web search outage, malformed LLM JSON, LLM 429 storm, vector search failure. Each has an expected degraded behaviour asserted in tests and measured in the eval (`failureRecoveryRate` = share of fault-injected runs that end with an honest, useful partial report).

### K3. Evaluation upgrade (the centrepiece)
- **ADD-EV-01 (P0) Five question categories** in the golden set (30-50 total, at least 5 each): `NORMAL`, `EDGE` (ambiguous, multi-period, conflicting sources), `ADVERSARIAL` (injection, write-SQL attempts, forged approvals, PII fishing), `MISSING_DATA` (answer not in the data; correct behaviour is to say so), `TOOL_FAILURE` (fault injected). Report per-category results.
- **ADD-EV-02 (P0) Four systems on the same set:** `BASELINE` (single-shot RAG, documents only), `SINGLE_AGENT` (one tool-calling agent with all tools, no supervisor/verifier/loop), `AGENT_NO_VERIFIER` (full pipeline without verifier and confidence loop), `AGENT` (full NexusAI). Metrics for each: answer correctness, grounded-claims share, hallucination rate, citation validity, latency, tokens, guardrail block rate (adversarial), failure recovery rate (tool-failure), approval-gate compliance (must be 100% for agent systems that can propose actions). Show the quality vs token-cost trade-off and answer honestly whether the extra cost is worth it, per category (the "why were multiple agents needed?" answer comes from this data).
- **ADD-EV-03 (P0) Retrieval ablation (runs without any LLM, so it can run in CI).** A 30-50 item retrieval set (question -> expected document and page/section). Compare: fixed-size chunking vs semantic/heading-aware chunking; vector-only vs keyword-only vs hybrid RRF; with and without reranker (promoted from P2 to P1: implement a cross-encoder reranker behind `RERANKER_ENABLED`). Metric: retrieval hit rate@k (and MRR). Store each variant as a run (`variant` label). The result is a chart like the one in your images, but with your real numbers.
- **ADD-EV-04 (P1)** Judge model and prompts documented; deterministic checks for numbers and abstention; 10-answer human spot-check recorded; judge-vs-human agreement reported.
- **ADD-FE-01 (P1)** Evaluation dashboard additions: system comparison table, quality vs token-cost chart, per-category breakdown, retrieval ablation chart, guardrail block counts, drill-down to a failing question with its trace.

### K4. CI evaluation gate
- **ADD-CI-01 (P1) `eval-ci.yml` on every push/PR (deterministic, free):** guardrail and adversarial tests, SQL-guard tests, approval-gate compliance tests, citation-validator tests, fault-injection tests with a fake LLM, **retrieval ablation with local embeddings**, compared with a stored `evals/baseline_metrics.json`. The job fails if hit rate drops more than a set margin or any safety test fails. Metrics are posted as a job summary and uploaded as an artifact.
- **ADD-CI-02 (P1) LLM evaluation job:** `workflow_dispatch` plus a weekly schedule, using a repository secret for the LLM key, running a small subset (about 10 questions) against the full agent and baseline; results uploaded as an artifact and summarised. It is informational (free-tier limits and nondeterminism make it unsuitable as a hard gate); the deterministic job is the hard gate.

### K5. Stories and "core skills"
- **ADD-ST-01 (P0 for the report, P1 for the repo) `docs/engineering-stories.md`:** five short stories, each: problem, hypothesis, experiment, **your measured result**, decision, trade-off. Candidates: (1) chunking and reranker ablation; (2) multi-agent vs single-agent vs baseline cost/quality; (3) making agent SQL safe (guard + read-only role, with the hostile queries that were blocked); (4) the approval race condition and the conditional update; (5) debugging a bad answer using the persisted trace. Also an interview Q&A section answering: how do you prevent prompt injection, how do you trace a bad answer, how do you evaluate retrieval quality, how does the agent recover from failures, why were multiple agents needed.
- **ADD-ST-02 (P1) `docs/under-the-hood.md`:** what is hand-written versus delegated to a framework (hybrid RRF in SQL, AST SQL guard, confidence model as pure code, replayable SSE with sequence numbers, approval state machine and race-safe decisions, the chunker) and what LangGraph is used for (graph control flow, checkpointing, `interrupt`). Shows that the project demonstrates core skills, not just framework calls.

---

## 3. Contract impact (already applied in file 06 v2.1)
New status `REFUSED`; new event `guardrail_triggered`; `done.status` may be `REFUSED`; detail DTO has `limitations` and `guardrailEvents`; eval DTO has four `system` values, `variant`, per-result `category`, and new metrics. Backend and frontend must handle `REFUSED` everywhere a status is shown.

## 4. Prompt patches (already inserted into file 07)
P2 (Backend B): store `REFUSED`, `limitations`, `guardrailEvents`. P3 (AI A): chunking modes `fixed|semantic`, reranker, PII helper, retrieval-only eval hooks. P4 (AI B): guardrails, failure policy, citation check, four systems, categories, ablation, engineering stories skeleton. P5/P6 (Frontend): REFUSED state, guardrail chips in the timeline, limitations section, new eval views. P7 (Infra): `eval-ci.yml`.
