# AI B report: agents, tools, memory, evals, routes (on top of the verified AI A service)

Scope delivered: everything in the AI B prompt (items 1-5 + ADDENDUM 09). **Not touched (out of scope):** ingestion/loaders/chunker/vector_store internals, the FastAPI skeleton, Java, React, docker-compose.
The zip contains the COMPLETE `ai-service/` (AI A's verified code + AI B's additions), `docs/`, this report and `main.py.diff`.

## 0. What changed in AI A's files (4 files; everything else is new)
| File | Change |
|---|---|
| `app/main.py` | **registration diff below** (2 lines: the import and the router list). Nothing else |
| `app/memory/checkpointer.py` | the no-op stub is replaced by the real `AsyncPostgresSaver` (own async pool, tables in schema `ai`). Same two entry points `main.py` already called |
| `requirements.txt` | lower bounds for langgraph / langgraph-checkpoint-postgres, `httpx` added (tested with langgraph 1.2.15, checkpoint-postgres 3.1.3) |
| `README.md` | AI B section appended |

```diff
--- ai-service/app/main.py (AI A)
+++ ai-service/app/main.py
-from app.api.routes import health, ingest, search
+from app.api.routes import admin_eval, health, ingest, investigate, memories, search
...
-INTERNAL_ROUTERS = [ingest.router, search.router]
+INTERNAL_ROUTERS = [ingest.router, search.router, investigate.router, memories.router, admin_eval.router]
```
The runtime (graph, LLM, tools) is built lazily from `app.state` on the first investigation, so no other line of `main.py` changes. New: `app/agents/` (32 py files, 15 prompts), `app/tools/` (11), `app/memory/{long_term,scoring}.py`,
`app/api/routes/{investigate,memories,admin_eval}.py`, `app/evals/` (13 py files, 12 corpus documents, seed SQL, golden/retrieval/adversarial sets), `scripts/investigate_demo.py`, `tests/agents/` (241 tests), `docs/`.

## 1. What was verified, and how (honest status)
| Check | Result | How |
|---|---|---|
| Full suite: **316 tests** (AI A 75 + AI B 241) | **316 passed** | real PostgreSQL 16 + **pgvector 0.6.0**, scripted LLM, hashing embedder. AI B: graph paths 50, sql_guard 59, tools/stats/confidence 43, safety units 36, evals 23, memory 20, routes 9, happy path 1 |
| `ruff check` (target py311) | clean | it also caught Python-3.12-only syntax in my code, fixed (the project promises 3.11) |
| Real `uvicorn` process | starts; `checkpointer ready`; checkpoint tables created in schema `ai`; 401 without key; investigate without an LLM key returns one readable `error` event; memories/eval routes answer | run in the sandbox against a database prepared like `init.sql` |
| Pause -> **service restart** -> resume | passes | two separate app instances on the same DB, real Postgres checkpointer (`tests/agents/test_routes.py`) |
| Hostile SQL | 47/47 rejected, 6/6 valid accepted; read-only role rejects writes and private tables | `tests/agents/test_sql_guard.py` |
| Forged-risk fuzz (AI-HL-04) | 18/18 end at `approval_required`; none leaks a HIGH `action_proposed` | `test_graph_paths.py` (3 HIGH types x 6 forged risk values) + structural edge test |
| Planted story reproduced by the stats tools | yes: West/Home is the top driver (95.4% of the net change), South marketing -33.0%, East/Apparel small and also down in 2025, North/Electronics +20.8% | `test_tools_unit.py`, generator assertions |
| Retrieval ablation harness | runs end to end, 12 variants, 37 questions, scratch tables dropped, production chunks untouched, deterministic | `test_evals.py`; real run with the hashing embedder recorded in `baseline_metrics.json` |
| **NOT verified here** | | |
| **Any real LLM call** (Gemini, Ollama, Groq) | not run | no network/keys in the sandbox. `LangChainLlm`, `core.llm.get_llm`, streaming and token counts from real responses are untested. The prompts are written but never seen a real model |
| **Real BGE-small / real cross-encoder** | not run | no access to huggingface.co. Retrieval QUALITY is not measured |
| Tavily / ddgs real search | not run | the web tool is tested with an injected search function |
| Langfuse spans | not run | spans are no-ops without keys (`observability.span`) |
| pgvector >= 0.8 iterative scan, Docker build | not run | same as AI A |
| Windows + uvicorn event loop | not run | psycopg async needs the SelectorEventLoop; see decision 12 |
| **The full evaluation (baseline vs agents on 44 questions)** | **not run: no number exists** | needs the LLM. `run_eval` is tested end to end on a 3-question mini set with a scripted LLM only. **Do not quote any agent-vs-baseline number until you run it** |

Bugs that the tests found in my own first version and that were fixed (so you know the tests bite): LangGraph did not pass `config` to wrapped nodes; an extra key broke `report_ready`; the SQL guard let `SELECT version()` through and kept comments;
the grounding metric dropped citation markers; a citation after the full stop (`... 2026. [E1]`) looked uncited; an agent that gave up after one failed tool call left no trace in "Limitations"; the single-agent loop shared a tag with the Analyst; a missing LLM key
raised inside an already-started SSE response; a Python-3.12-only generic definition.

## 2. Requirement IDs
| ID | Status | Evidence |
|---|---|---|
| AI-AG-01 | done | `agents/graph.py`: input_guard -> recall_memory -> supervisor -> planner -> researcher/data_analyst -> analyst -> verifier -> confidence_check -> (planner loop / action_planning) -> approval_gate (only if HIGH) -> reporter -> save_memory; `maxLoops` <= 5 (config + request); Postgres checkpointer by `thread_id`. Tests: accept, loop-then-accept, cap, stagnation, LOW action, HIGH pause, resume approve/reject, cancel |
| AI-AG-02 | done | `nodes/supervisor.py`: routes documents/data/both/web/direct with a reason; `direct` skips planner/tools (test `test_trivial_question_short_circuits`); web route falls back to documents when web search is off |
| AI-AG-03 | done | `nodes/planner.py`: one structured call, ordered steps with owning agent, `plan` + `step_status` events; on a loop it plans only for the focus claims (ids `l1s1`...) |
| AI-AG-04 | done | `nodes/researcher.py` + `agents/react.py`: tool loop over `rag_search`, `web_search` (only when allowed), `recall_memory`; <= 4 calls per step; evidence with sources |
| AI-AG-05 | done | `nodes/data_analyst.py`: `sql_query` + 3 stats tools; tables and chart-ready series in evidence |
| AI-AG-06 | done | `nodes/analyst.py`: discrete claims, `isKey`, evidence keys; on a loop only focus claims are rewritten |
| AI-AG-07 | done | `nodes/verifier.py` + `confidence.py`: per-claim structured verdict (one repair retry), agreement/quality, caps 0.3/0.4, no evidence => UNSUPPORTED, VERIFIED needs support >= 0.5 |
| AI-AG-08 | done | `nodes/confidence_check.py` (pure code): ACCEPT / LOOP with focus / ACCEPT_LOW_CONFIDENCE; plus a documented early stop when a loop adds no evidence (decision 8) |
| AI-AG-09 | done | `nodes/reporter.py` + `report_builder.py`: streams `report_delta`, `report_ready`; findings only from VERIFIED claims; code-generated sections: banner, recommendations with risk, approval outcomes, Unverified, Limitations |
| AI-AG-10 | done | `events.py` builds every payload from the contract models; conformance test over runs (`EVENT_PAYLOADS`, SSE frames have no `id:`); one terminal event; approval_required ends the stream; cancel and client disconnect tested |
| AI-AG-11 | done | `done.usage` + `latencyMs` accumulate across pause/resume via state reducers; per-node timing in logs and Langfuse spans (`common.node`) |
| AI-TL-01 | done | `tools/registry.py`: schema, risk tag (only READ tags exist), allowed agents, timeout, per-run budget; validated before execution; tests incl. timeout and budget |
| AI-TL-02 | done | `tools/sql_guard.py` (sqlglot AST: one SELECT, five tables, function allow-list, forced LIMIT, executes the AST re-rendering) + `sql_tool.py` (ro pool, READ ONLY transaction, statement timeout, readable reasons) + failure policy |
| AI-TL-03 | done | `tools/stats_tool.py`: compare / contribution (share of net change) / anomaly (z-score); fixed parameterised queries over the ro pool; table + chart series |
| AI-TL-04 | done (web untested live) | `rag_tool.py` (enforces document scope), `web_tool.py` (Tavily key else ddgs; query PII-redacted and capped; kill switch; registered only if allowed), `memory_tool.py` |
| AI-TL-05 | done | `tools/action_catalogue.py`: six actions, Pydantic params, risk fixed; LLM risk ignored (tested with 6 forged values) |
| AI-HL-01 | done | `nodes/approval_gate.py`: `approval_required` for ALL HIGH proposals then `interrupt()`; survives a restart (test with two app instances) |
| AI-HL-02 | done | resume route continues from the checkpoint; approve/reject reflected in the report; rejected fingerprints never re-proposed (unit test); missing decision = REJECT; second resume -> 409; cancel of a paused run blocks resume |
| AI-HL-03 | done | LOW proposals emit `action_proposed` and never pause |
| AI-HL-04 | done | forged-risk fuzz (18 runs), invalid/unknown actions dropped, structural edge test |
| AI-ME-01 | done | `memory/checkpointer.py` (state: question, plan, evidence, claims, decisions ...) |
| AI-ME-02 | done | `memory/long_term.py` + `scoring.py`: 0.5 relevance + 0.3 exp(-age/30) + 0.2 importance, top 5, relevance floor, dedupe >= 0.92, per-user filter in EVERY query (tests: isolation, mandatory user id, ordering), `memory_recalled`/`memory_saved` events, PII + secret sanitising |
| AI-ME-03 | done | memories routes (list/search, delete one, delete all, user purge incl. checkpoints via checkpoint metadata); `useMemory=false` touches nothing |
| AI-SF-01 | done | `agents/injection.py`: `<untrusted_data>` wrapper (closing tag neutralised), data rule in every agent prompt, no write/exfiltration/execute tool exists (registry test) |
| AI-SF-02 | done | `agents/structured.py`: Pydantic validation, one repair retry, safe fallback + `guardrail_triggered` INVALID_OUTPUT |
| AI-SF-03 | done | adversarial corpus document + `adversarial_cases.json` (18 cases): questions blocked, document text flagged and never followed, forged actions gated |
| AI-SF-04 | done | 15 versioned prompt files; tests: version header, no inline prompt text, every referenced prompt exists |
| AI-OB-01 | done (spans untested) | `observability.span` around every node; Langfuse only with keys; the persisted trace is the event stream that Spring stores |
| AI-DM-01 | done | `evals/seed/generate_seed.py` (fixed seed) -> `V7__seed_business_data.sql` (1008 sales rows, revenue = units x price exactly), `story.md`, `facts.json`; the generator asserts the planted story; deterministic (tested) |
| AI-DM-02 | done | 12 documents generated from the facts: reviews, supplier incident, competitor note, marketing plan, pricing and approval policies, seasonality memo (red herring), **conflicting** digest, **irrelevant** notice, fake-PII contacts, **adversarial** addendum; facts only in documents / only in SQL |
| AI-EV-01 | done | `golden_questions.json`: 44 questions (NORMAL 14, EDGE 9, MISSING_DATA 7, ADVERSARIAL 7, TOOL_FAILURE 7) incl. SQL-only, document-only, multi-source "why" (hero), unanswerable, ambiguous, action-triggering; expected facts computed from the seed (tests) |
| AI-EV-02 | done | `evals/baseline_rag.py` (retrieve once, answer once; no tools/verification/memory/guardrail) |
| AI-EV-03 | done (not yet run on a real LLM) | `evals/metrics.py`: correctness, grounded share, hallucination, latency, tokens, approval-gate compliance |
| AI-EV-04 | done (not yet run on a real LLM) | `python -m app.evals.run_eval --system agent\|baseline\|single_agent\|no_verifier\|both\|all`: ingests the corpus, runs, stores `ai.eval_runs`, writes Markdown + CSV |
| AI-EV-05 | partly | judge prompt + documented in `judge.py`/howto; deterministic checks always run. The 10-answer human spot-check is yours to do after a real run |
| AI-EV-06 | done | the pytest suites above; hostile SQL, stats on seed, confidence branches, graph paths with a fake LLM, memory isolation |
| ADD-GR-01 | done | `nodes/input_guard.py` + `injection.classify_input`: deterministic blocks, LLM only for ambiguous inputs (fails open), `guardrail_triggered` then `done REFUSED`; false positives measured in `run_eval` (`guardrailFalsePositiveRate`) |
| ADD-GR-02 | done | PII redaction (AI A's `core/pii.py`) applied to web queries, tool-call args in events, the question's trace note, memory summaries; events never contain the value (tests with an email in a web query and a card in a memory summary) |
| ADD-GR-03 | done | `agents/citation_check.py`: keys exist, numbers match evidence within rounding, quotes match; failing statements move to "Unverified"; `citationValidity` metric |
| ADD-GR-04 | done | catalogue param validation + one repair + fallback, `INVALID_OUTPUT` events |
| ADD-GR-05 | done | SQL rejections, PII-redacted web queries and injection-flagged passages are `guardrail_triggered` stage TOOL |
| ADD-FH-01 | done | `agents/failure.py` + `react.execute_tool_call`: timeout, `MAX_TOOL_ATTEMPTS` per (step, tool) with the reason fed back, exponential backoff on transient errors |
| ADD-FH-02 | done | after the last attempt (or when the agent gives up) the failure is recorded; "Limitations and failures" lists it; dependent claims lose confidence; no invented data (tests) |
| ADD-FH-03 | done | whole-run failures -> one `error` event (`LLM_RATE_LIMITED` retryable / `AI_SERVICE_UNAVAILABLE` / generic `INTERNAL_ERROR`), readable, no stack; partial trace already streamed |
| ADD-FH-04 | done | fault injection: tool timeout, SQL error, empty retrieval, web outage, malformed LLM JSON, LLM 429, LLM outage mid-run, vector failure; `failureRecoveryRate` metric |
| ADD-EV-01 | done | five categories, >= 5 each |
| ADD-EV-02 | done (not yet run on a real LLM) | four systems implemented and tested on a mini set; quality-vs-token section is generated from the run |
| ADD-EV-03 | done and **run** (hashing embedder only) | `retrieval_ablation.py`, 37 questions, 12 variants, no LLM; hit@1/3/5 + MRR |
| ADD-EV-04 | partly | judge documented; judge-vs-human agreement needs the human spot-check |
| ADD-CI-01 | done | `python -m app.evals.ci_check` (exit 0/1/2) + `docs/eval-ci.yml.example`; the real workflow file belongs to the infra stream |
| ADD-CI-02 | documented | recipe in the example workflow comments |
| ADD-ST-01 | skeleton | `docs/engineering-stories.md`: five stories + interview Q&A; only story 3 and 4 carry numbers (from the tests); every other result field says `MEASURE:` |

## 3. Decisions and deviations (read these)
1. **JSON "ReAct" tool calling instead of provider-native `bind_tools`.** The agent replies with `{"action":"call","tool":...}` or `{"action":"finish"}`; code validates and executes. Works the same on Gemini, Ollama and Groq (Ollama model support for native tools varies) and makes tests exact.
   Cost: slightly more prompt text. Untested against a real model: if a model keeps returning invalid JSON the repair retry then a fallback apply and a guardrail event shows it.
2. **`main.py` needs two changed lines** (import + list), not literally one; shown as a diff above.
3. **HIGH proposals are NOT emitted as `action_proposed`**; they leave only inside `approval_required`. Contract 5 says Spring executes `action_proposed` with LOW risk automatically; this guarantees a HIGH action can never reach that path.
4. **`report_delta` carries `[E#]` labels, `report_ready` carries `[ev:<evidenceKey>]`** (labels are converted after citation validation, and invalid sentences are moved out). Frontends should treat `report_ready` as authoritative.
5. **Trivial/direct answers:** `report_ready.confidence` is 0.0 and `done.confidence` is null (contract types `report_ready.confidence` as a required number). Please make it nullable in the contract.
6. **Approvals:** `ResumeRequest.decisions` only knows APPROVE/REJECT. A missing decision counts as REJECT (nothing is ever approved implicitly). For TTL expiry Spring should send REJECT with a comment such as "expired" (the report then says no action was taken).
7. **Reporter structure:** the LLM writes only "Executive summary" and "Findings"; code appends Recommendations (risk from the catalogue), approval outcomes, "Unverified or contradicted claims" and "Limitations and failures". An unverified claim cannot be presented as a finding, even by a misbehaving model.
8. **Early stop on stagnation** (not in the contract): if a loop adds no evidence the run ends ACCEPT_LOW_CONFIDENCE instead of burning the remaining loops. The `confidence` event still reports the true decision.
9. **Failure attempts are counted per (plan step, tool)**; a confidence loop creates new steps, so a permanently failing tool can be retried again (3 more attempts) in the next loop. Each is bounded and explained.
10. **Input guard fails open** when its LLM classifier output is invalid (so legitimate questions are not blocked by a broken classifier); overt attacks are caught by the deterministic rules before any LLM. The rules can have false positives (a business question that literally contains "delete from"); measure with `guardrailFalsePositiveRate`.
11. **Confidence `quality` for a claim with several evidence items is the mean** (contract section 9 does not say); `independentSources` counts distinct documents, SQL results and web domains. Memory relevance floor is 0.35 (`MIN_RELEVANCE`): **tune it with the real BGE model**; BGE cosine scores are usually higher than the hashing embedder's, so 0.35 may filter too little.
12. **Windows:** the Postgres checkpointer uses psycopg async and needs the SelectorEventLoop; run `uvicorn` without `--reload` on Windows or use Docker. The service refuses to start with a clear message on a Proactor loop.
13. **Checkpoint purge** relies on LangGraph storing `config.metadata` (we pass `user_id`) in `ai.checkpoints.metadata` (verified by test with the real saver). If a future LangGraph changes that, `DELETE /internal/users/{id}` would report `checkpoints: 0`; the test would fail.
14. **`ai_rw` has no privilege on the business tables** (by design). The eval harness, tests and the stats tools use the `ai_readonly` pool for business data.
15. **Citation validation is deliberately strict:** a number the LLM computed itself (not in any evidence) moves its sentence to "Unverified". That can cost recall; the stats tools exist so numbers come from code.
16. **Eval harness:** when an agent run pauses for approval the harness REJECTS the pending actions (it is not an approver) so the report can finish; the baseline has no failure policy, so a retrieval failure ends its run FAILED (that is the comparison, not a bug). The public eval API projects only the contract fields; extra drill-down fields stay in `ai.eval_runs.results`.
17. **`baseline_metrics.json` holds the baseline for the hashing embedder only** (rerank-on rows use a token-overlap stand-in). The CI gate returns exit 2 for any other embedding model until you run `--update-baseline` once with the real one. These hashing numbers prove the pipeline; they are not quality claims.
18. Contract asks for 06: error body `InternalError` (from AI A), `report_ready.confidence` nullable, document that `agent_started(SUPERVISOR)` is the first event, and that Python never emits `run_started`, `approval_decided`, `action_executed`.

## 4. Measured facts (all reproducible)
* Seed (seed 20260101): Q1 2026 revenue 2,768,725.00 -> Q2 2026 2,605,975.00 (-162,750.00, -5.9%). West/Home -45.0% (95.4% of the net change); South revenue -10.2% (41.0% of the net change) with South marketing spend -33.0% (68,364.20 -> 45,784.95);
  East/Apparel -4.6% (and -6.3% in Q2 2025: seasonal); North/Electronics +20.8%. Q2 2026 vs Q2 2025: -3.4%.
* Tests: 316 passed; hostile SQL 47/47 blocked; forged-risk 18/18 gated.
* Retrieval ablation, **hashing embedder + stand-in reranker (pipeline check, NOT quality)**: all 12 variants ran; e.g. semantic|KEYWORD|off hit@5 1.000, MRR 0.894; fixed|HYBRID|off hit@5 0.946, MRR 0.835. Re-run with BGE for real numbers.

## 5. For Spring and the frontend
* Call `POST /internal/investigate` (SSE). Events carry no `id:`; Spring assigns `seq`. First frame is `agent_started` (SUPERVISOR); `memory_recalled` is emitted when `useMemory` is true. Terminal: `done` (COMPLETED / CANCELLED / REFUSED) or `error`.
* After `approval_required` the stream ends and the run is checkpointed. Call `POST /internal/investigate/{threadId}/resume` with ALL decisions; it returns 404 for an unknown thread (e.g. after a user purge), 409 `INVALID_STATE` if the run is not waiting or already finished, and `done CANCELLED` if the paused run was cancelled.
* `POST .../cancel` returns `{cancelled:true}` for a running or paused run, `false` for an unknown/finished one. Closing the HTTP connection of a running (not paused) investigation cancels it.
* Errors before streaming (bad body, wrong key) use the AI A error body (400/401). Errors after streaming has begun are `error` events: `LLM_RATE_LIMITED` (retryable), `AI_SERVICE_UNAVAILABLE`, `INTERNAL_ERROR`.
* Memories: `GET /internal/memories?userId=&page=&size=&q=`, `DELETE /internal/memories/{id}?userId=`, `DELETE /internal/memories?userId=`, `DELETE /internal/users/{userId}` -> `{memories, checkpoints}`.
* Business tables: Spring's V6 creates them and V7 is `ai-service/app/evals/seed/V7__seed_business_data.sql` (copy it to the backend migrations folder). V6 must grant SELECT to `ai_readonly` (contract 10.1).

## 6. Exact commands (Windows PowerShell, Docker Desktop). One block at a time.
Steps 1-4 are the same as the AI A report (venv, `pgvector/pgvector:pg16` container named `nexus-pg`, `sql\dev_bootstrap.sql`, `.env`). Then:

**Step A: unzip and run the tests** (from the folder containing the zip; Python 3.11 or 3.12)
```powershell
Expand-Archive .\ai-service-ai-b.zip -DestinationPath . -Force ; cd .\ai-service
python -m venv .venv ; .\.venv\Scripts\Activate.ps1
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
$env:TEST_ADMIN_DSN = "postgresql://postgres:postgres@localhost:5432/postgres"
pytest
```
Expected: `316 passed`. (`pytest tests/agents` = the 241 AI B tests.) If you see many skipped, `TEST_ADMIN_DSN` is not set in this window.

**Step B: load the demo business data for local runs** (database `nexusai` from `dev_bootstrap.sql`)
```powershell
Get-Content app\evals\seed\local_business_schema.sql | docker exec -i nexus-pg psql -U postgres -d nexusai
Get-Content app\evals\seed\V7__seed_business_data.sql | docker exec -i nexus-pg psql -U postgres -d nexusai
docker exec -i nexus-pg psql -U postgres -d nexusai -c "SELECT count(*) FROM sales;"
```
Expected: `1008`.

**Step C: configure the LLM and start the service** (add to `.env`: `GEMINI_API_KEY=...` and `GEMINI_MODEL=...`, confirm the model name in Google AI Studio; for local-only use `LLM_PROVIDER=ollama` with a tool-capable model; use `EMBEDDING_MODEL=BAAI/bge-small-en-v1.5`)
```powershell
uvicorn app.main:create_app --factory --port 8000
```
Expected: log lines `checkpointer ready (AsyncPostgresSaver, schema ai)` and `ai-service ready`. (No `--reload` on Windows.)

**Step D: first real investigation** (second window, venv active; this is the first time a real LLM touches the prompts: if it misbehaves, send me the event output)
```powershell
$env:INTERNAL_API_KEY = "<the key in .env>"
python scripts\investigate_demo.py
```
Expected: events scroll by (plan, tool calls, evidence, claims, verification, confidence, possibly a loop), the report streams, `done COMPLETED`; if an action needs approval it pauses and the script asks you.

**Step E: retrieval ablation (no LLM) and baseline**
```powershell
python -m app.evals.retrieval_ablation --reranker auto --store
python -m app.evals.retrieval_ablation --reranker fake --update-baseline      # once per embedding model, then commit app\evals\baseline_metrics.json
python -m app.evals.ci_check
```
Expected: a table of 12 variants; `ci_check` ends with PASS and exit code 0 (`$LASTEXITCODE`).

**Step F: full evaluation (needs the LLM; paced for free-tier limits)**
```powershell
python -m app.evals.run_eval --system both --limit 5 --sleep 4
python -m app.evals.run_eval --system all --sleep 4
```
Expected: per-question `OK/BAD` lines, then `app\evals\results\eval-<time>.md` and `.csv`. Read `docs\evaluation-howto.md` section 4 before quoting anything.

## 7. Literature -> code
| Source | Idea | Implemented in |
|---|---|---|
| RAG [3] (retrieval-augmented generation) | retrieve evidence, answer from it with citations | `app/rag/retriever.py` (AI A), `tools/rag_tool.py`, `evals/baseline_rag.py` (the single-shot baseline), `agents/citation_check.py` (answer claims must match retrieved text) |
| ReAct [4] | interleave reasoning and tool actions with observations | `agents/react.py` (the shared loop), `nodes/researcher.py`, `nodes/data_analyst.py`, `evals/single_agent.py`, prompts `researcher.md`, `data_analyst.md` |
| LangGraph [2] | stateful graph, conditional edges, checkpointing, human interrupt | `agents/graph.py`, `agents/state.py`, `memory/checkpointer.py` (AsyncPostgresSaver), `nodes/approval_gate.py` (`interrupt`), `agents/runner.py` (resume) |
| AutoGPT [5] gaps | unbounded loops, no persistent state, no human control, silent failures | bounded loops (`confidence.decide`, `maxLoops`, stagnation stop), per-tool call budgets (`tools/registry.py`), persistent checkpointed state, approval gate + fixed-risk catalogue (`action_catalogue.py`), uniform failure policy + "Limitations" section (`failure.py`, `report_builder.py`), read-only tools only |

## 8. Known gaps to tell me before integration
* No real LLM was ever called: prompt quality, JSON compliance rates, loop behaviour and token costs are unmeasured. Expect to iterate on prompts after Step D.
* No agent-vs-baseline result exists; no retrieval-quality number with BGE exists.
* The CI workflow itself (`eval-ci.yml`) is an example for the infra stream; judge-vs-human agreement and the engineering stories' results must be filled after real runs.
* Web search (Tavily/ddgs), Langfuse, the real cross-encoder, Windows event-loop behaviour and the Docker image are untested.
