# Evaluation how-to (AI-EV-04, ADD-EV-03, ADD-CI-01)

Everything runs from `ai-service/` with the venv active. Windows/PowerShell + Docker Desktop commands (same Postgres container as the AI A README: `nexus-pg`).

## 0. One-time: load the demo business data for LOCAL runs (without the Spring backend)
In the real stack Spring's Flyway creates the business tables (V6) and loads the seed (V7 = `app/evals/seed/V7__seed_business_data.sql`).
For local evaluation without Spring, create the same tables yourself, then load the seed. Do NOT do this next to Flyway.
```powershell
Get-Content app\evals\seed\local_business_schema.sql | docker exec -i nexus-pg psql -U postgres -d nexusai
Get-Content app\evals\seed\V7__seed_business_data.sql | docker exec -i nexus-pg psql -U postgres -d nexusai
docker exec -i nexus-pg psql -U postgres -d nexusai -c "SELECT count(*) FROM sales;"
```
Expected last line: `1008`. (The tables are owned by `postgres`; `ai_readonly` gets SELECT through the guarded GRANT inside `local_business_schema.sql`; `ai_rw` deliberately has NO access to them.)
Regenerating the seed is deterministic: `python -m app.evals.seed.generate_seed` (writes V7, `facts.json`, `story.md`; asserts the planted story is really in the numbers),
`python -m app.evals.seed.generate_corpus` (12 documents), `python -m app.evals.build_golden` (golden / retrieval / adversarial sets). A test fails if committed files differ from a fresh build.

## 1. Retrieval ablation: no LLM needed (ADD-EV-03)
```powershell
python -m app.evals.retrieval_ablation --reranker auto --store
```
Measures fixed vs semantic chunking x VECTOR / KEYWORD / HYBRID(RRF) x reranker off/on on 37 questions (hit@1/3/5 and MRR). `--reranker auto` loads the real cross-encoder
(first run downloads it), `--reranker fake` uses a deterministic token-overlap stand-in (offline), `off` skips it. `--store` saves every variant to `ai.eval_runs` (dashboard).
**Use the real BGE model for any number you quote** (`EMBEDDING_MODEL=BAAI/bge-small-en-v1.5`); with `EMBEDDING_MODEL=hashing` the vector rows are lexical only.
Record the baseline used by the CI gate once per embedding model, then commit `app/evals/baseline_metrics.json`:
```powershell
python -m app.evals.retrieval_ablation --reranker fake --update-baseline
```

## 2. Full evaluation: baseline vs agents (needs the LLM provider)
Prerequisites: step 0, `GEMINI_API_KEY` + `GEMINI_MODEL` in `.env` (confirm the model name in Google AI Studio; or `LLM_PROVIDER=ollama`), the real embedding model.
```powershell
python -m app.evals.run_eval --system both --limit 5 --sleep 4      # smoke: 5 questions, paced for free-tier limits
python -m app.evals.run_eval --system all --sleep 4                 # BASELINE, SINGLE_AGENT, AGENT_NO_VERIFIER, AGENT on all 44 questions
```
Options: `--category NORMAL|EDGE|ADVERSARIAL|MISSING_DATA|TOOL_FAILURE`, `--ids n01,n03`, `--judge keyword` (no LLM judge: deterministic checks only), `--label text`, `--no-store`.
Outputs: one `ai.eval_runs` row per system (visible via `GET /internal/eval/runs`), and `app/evals/results/eval-<timestamp>.md` + `.csv`.
Free-tier budgeting: the agent uses roughly 8-20 LLM calls per question; `--sleep` and `--limit` keep you under quota. Interrupted runs are cheap to repeat with `--ids`.

How the four systems differ (same tools, same retriever, same provider):
| System | What it is |
|---|---|
| BASELINE | retrieve once over documents, answer once. No SQL, no tools, no verification, no memory, no guardrail |
| SINGLE_AGENT | one ReAct agent with all tools (SQL guard + read-only role unchanged), one answer call. No supervisor / planner / verifier / loop / gate |
| AGENT_NO_VERIFIER | full pipeline; the verifier and the confidence loop are skipped |
| AGENT | full NexusAI |
When the agent pauses for approval the harness REJECTS the pending actions (it is not an approver) so the report can finish; gate compliance is judged on the events before the pause.

## 3. The CI gate (deterministic, free)
```powershell
$env:TEST_ADMIN_DSN = "postgresql://postgres:postgres@localhost:5432/postgres"
python -m app.evals.ci_check
```
Exit 0 = safety tests pass AND no variant's hit@5 / MRR dropped more than `--margin` (default 0.05) below `baseline_metrics.json` for the configured embedding model.
Exit 1 = regression or failing safety test. Exit 2 = no baseline for this embedding model (record it) or `TEST_ADMIN_DSN` missing (DB safety tests would silently skip).
The gate uses the stand-in reranker so it needs no model download for the reranker; the embedding model is the configured one. `docs/eval-ci.yml.example` is the GitHub Actions job.

## 4. Reading the results honestly
* The golden set is small (44). A few points of difference are noise; per-category n is 7-14.
* Correctness is deterministic first (numbers within rounding, keyword groups, forbidden text, abstention, invented numbers); the LLM judge only adds opinions. Definitions: `app/evals/metrics.py`.
* The judge uses the same provider as the systems under test; spot-check at least 10 answers by hand and record the agreement (ADD-EV-04): add them to `docs/evaluation-report.md`.
* Never copy numbers from another project. Every number in a report must come from a run you can re-run.
