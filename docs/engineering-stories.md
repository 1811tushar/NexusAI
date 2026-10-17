# Engineering stories (ADD-ST-01) - SKELETON

**Rule: only measured numbers.** Every field marked `MEASURE:` must be filled from a run you can repeat (command given). Fields already filled below come from the test suite
or the code in this repository and say where to re-check them. Do not copy numbers from anyone else's project.

---
## Story 1 - Chunking, search mode and reranker: what actually finds the right passage?
* **Problem.** A cited answer is only as good as the passage retrieved. Which combination of chunking (fixed vs heading-aware), search (vector / keyword / hybrid RRF) and reranker is worth its cost?
* **Hypothesis.** MEASURE: write your hypothesis BEFORE running (e.g. "hybrid beats either alone; semantic chunking helps paraphrased questions; the reranker helps hit@1 more than hit@5").
* **Experiment.** 37 retrieval questions over the 12-document synthetic corpus (lexical and paraphrased phrasing), 12 variants, no LLM:
  `python -m app.evals.retrieval_ablation --reranker auto --store` with `EMBEDDING_MODEL=BAAI/bge-small-en-v1.5`.
* **Measured result.** MEASURE: paste the table the command prints (hit@1, hit@3, hit@5, MRR per variant) and the per-style split (`hit5_lexical`, `hit5_paraphrase`) from `app/evals/results/ablation-*.json`.
  *Pipeline smoke check only (NOT a result):* with the lexical `hashing` embedder and a token-overlap stand-in reranker the tool measured all 12 variants (e.g. semantic|KEYWORD|off hit@5 1.000);
  that run proves the harness works, it says nothing about BGE.
* **Decision.** MEASURE: which defaults (`CHUNKING_MODE`, search mode, `RERANKER_ENABLED`) you keep, and why.
* **Trade-off.** MEASURE: reranker latency per query (time it) vs the hit-rate gain; chunk count and index size of fixed vs semantic (`chunks` field in the output).

## Story 2 - Do multiple agents earn their tokens? (baseline vs single agent vs no verifier vs full)
* **Problem.** A supervisor + planner + specialists + verifier loop costs many LLM calls. Is the quality worth it, and for which question types?
* **Hypothesis.** MEASURE: write it first (e.g. "the baseline fails every SQL question; the verifier cuts hallucinations on conflicting-source questions; the full agent costs 4-8x the tokens").
* **Experiment.** 44 golden questions in 5 categories on 4 systems: `python -m app.evals.run_eval --system all --sleep 4`.
* **Measured result.** MEASURE: the "System comparison", "Quality vs token cost" and "Per category" sections of the generated `app/evals/results/eval-*.md`.
* **Decision.** MEASURE: which categories justify the full pipeline; whether `CONFIDENCE_MIN` / `MAX_LOOPS` should change after looking at the loop counts.
* **Trade-off.** MEASURE: tokens/question and latency/question per system (columns in the report).

## Story 3 - Making agent SQL safe (guard + read-only role + the hostile queries that were blocked)
* **Problem.** An LLM writes SQL. A prompt that says "SELECT only" is not a control.
* **Hypothesis.** One layer will not be enough; an AST check, a read-only transaction and a role with SELECT on five tables only must each independently stop a write.
* **Experiment.** `tests/agents/test_sql_guard.py`: 47 hostile queries (DROP/DELETE/UPDATE, stacked statements, data-modifying CTEs, UNION into `users`, `ai.*` and `pg_catalog`, `pg_sleep`,
  `pg_read_file`, `dblink`, `set_config`, `SELECT INTO`, `FOR UPDATE`, comment tricks, table functions ...) and 6 valid queries; plus raw writes through the `ai_readonly` pool.
* **Measured result.** 47/47 hostile queries rejected with a readable reason; 6/6 valid queries accepted with a forced `LIMIT 200`; the read-only role rejected INSERT/DELETE/UPDATE/TRUNCATE/DROP and could not read
  `users` or `ai.memories` even without the guard. The suite found two real gaps in the first version of the guard: `SELECT version()` passed (sqlglot models it as a typed function, not as "anonymous"), and comments
  survived re-rendering. Both were fixed and are now regression tests. Re-check: `pytest tests/agents/test_sql_guard.py -v`.
* **Decision.** Defence in depth: AST guard (rejects with a reason the agent can use to fix its query) -> execution of the SQL RE-RENDERED from the AST -> read-only transaction -> statement timeout -> role privileges.
* **Trade-off.** The allow-list of functions is deliberately small: a legitimate but unusual function is rejected and the agent has to rewrite (bounded by `MAX_TOOL_ATTEMPTS`). MEASURE: how often a legitimate golden-set query was rejected in a real run (count `tool_result ok:false` with "SQL guard" in `agent_steps`).

## Story 4 - The approval gate that cannot be bypassed (and the race condition owned by the backend)
* **Problem.** The agent must never cause a HIGH-risk action without a stored human APPROVE, even if the LLM lies about risk or a document tells it to approve everything.
* **Hypothesis.** If risk comes only from the catalogue and HIGH proposals can only leave through `approval_required`, no prompt can change the outcome.
* **Experiment.** `tests/agents/test_graph_paths.py`: 3 HIGH action types x 6 forged risk values (`"LOW"`, `"low"`, `"none"`, `null`, `0`, `"HIGH"`) with a scripted LLM, invalid/unknown actions, a structural test of the graph edges,
  pause -> simulated service restart -> resume over HTTP with the real Postgres checkpointer (`tests/agents/test_routes.py`).
* **Measured result.** 18/18 forged-risk runs ended at `approval_required` with risk HIGH, none emitted a HIGH `action_proposed`, none produced a report or `done` before the decision; invalid params (`changePct` 90) and unknown types were dropped;
  a paused run resumed after a restart; a second resume returned 409. Re-check: `pytest tests/agents -k "forged or pause_survives or structure"`.
* **Decision.** Python only proposes; risk is looked up (`tools/action_catalogue.py`); the only edge from `action_planning` to `reporter` is taken when there are no HIGH proposals; a missing decision counts as REJECT.
* **Trade-off.** The eval harness auto-rejects pending actions so reports can finish; real approvals add latency by design. The race between two approvers (conditional update) belongs to the Spring backend: MEASURE it there (test + result) before telling that story.

## Story 5 - Debugging a bad answer with the trace
* **Problem.** An answer looks wrong. Where did it go wrong: retrieval, a tool, the claim, the verifier, the report?
* **Hypothesis.** The persisted event trace (plan, tool calls and results, evidence, claims, verdicts, confidence, guardrail events) is enough to localise the fault without re-running.
* **Experiment.** MEASURE: pick one real failing question from `eval-*.md` ("Failing questions"), open its investigation trace (`GET /api/investigations/{id}/steps`, or the `results[].answer` + events of the run) and walk it.
* **Measured result.** MEASURE: which step was at fault, with the event types and the evidence keys involved; how long it took; what you changed.
* **Decision.** MEASURE.
* **Trade-off.** MEASURE: trace storage per investigation (rows/bytes in `agent_steps`).

---
## Interview Q&A (answer each with YOUR measured numbers and the file that implements it)
1. **How do you prevent prompt injection?** Untrusted text is wrapped in `<untrusted_data>` delimiters with the closing tag neutralised (`agents/injection.py`); every agent prompt states it is data; injection-looking passages are flagged
   (`guardrail_triggered` TOOL/FLAGGED); the agent has NO tool that can write, send or execute; risk is catalogue-defined; deterministic input rules block overt attacks. MEASURE: guardrail block rate on the 7 adversarial questions and the false-positive rate on benign ones (`run_eval` report).
2. **How do you trace a bad answer?** See story 5. Entry points: `agent_steps` rows, `tool_result` reasons, `guardrail_triggered` events, Langfuse spans when keys are configured.
3. **How do you evaluate retrieval quality?** See story 1 (hit@k, MRR, no LLM, CI gate against a stored baseline).
4. **How does the agent recover from failures?** One policy (`agents/failure.py`): timeout, up to `MAX_TOOL_ATTEMPTS` with the reason fed back, exponential backoff for transient errors, then stop and explain in "Limitations and failures". MEASURE: `failureRecoveryRate` on the 7 TOOL_FAILURE questions.
5. **Why were multiple agents needed?** See story 2 - answer only from the measured comparison, per category.
