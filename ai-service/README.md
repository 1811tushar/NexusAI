# ai-service (NexusAI) - foundation, ingestion, retrieval (AI A) + agents, tools, memory, evals (AI B)

Internal FastAPI service. Only the Spring backend calls it (`X-Internal-API-Key`, never published outside Docker).
This slice provides: config / LLM factory / embeddings / DB foundation, document ingestion, hybrid retrieval, library search.
The agent layer (AI B) adds the LangGraph investigation graph, tools, long-term memory, the SSE investigate/resume/cancel routes, memory and eval routes, and the evaluation harness.

## Privacy and data egress (SEC-07)
- Free-tier LLM providers (Gemini, Groq) and web-search providers (Tavily, ddgs) **may log or use the requests they receive**.
  Use only **synthetic or non-sensitive data** with them (this project's demo corpus is synthetic).
- **Documents and embeddings never leave your network from this slice**: embeddings are computed locally (BGE-small, CPU).
  Text leaves the network only when AI B's agents call the LLM provider or web search.
- For fully local operation set `LLM_PROVIDER=ollama` and `WEB_SEARCH_ENABLED=false`.
- Logs never contain document text; messages are PII-redacted and truncated (`app/core/logging.py`, `app/core/pii.py`).
  Langfuse tracing is off unless keys are set; payloads should go through `observability.mask()`.
- Web search has a global kill switch (`WEB_SEARCH_ENABLED`). PII redaction (emails, phones, cards, SSN, Aadhaar, PAN) is available as
  `app.core.pii.redact` and must be applied by the agents to web queries and memory summaries.

## Run locally (Windows / PowerShell)
```powershell
cd ai-service
python -m venv .venv ; .\.venv\Scripts\Activate.ps1
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
copy .env.example .env      # then fill INTERNAL_API_KEY and the two DB passwords
uvicorn app.main:create_app --factory --port 8000
```
Needs Postgres 16 + pgvector with the `ai` schema and roles from `sql/init_ai_schema.sql` (see its header; for dev use `sql/dev_bootstrap.sql`).
First start downloads BGE-small (~130 MB) into `HF_HOME`/`/models`.

## Endpoints (contract section 6)
| Method + path | Key | Notes |
|---|---|---|
| `GET /health` | no | `{status, embeddingModel, llmProvider}`; 503 when a DB pool fails |
| `POST /internal/ingest` | yes | multipart `meta` (JSON `IngestRequest`) + `file`; 413 too large, 422 `INGESTION_FAILED` |
| `DELETE /internal/documents/{id}` | yes | `{deleted}` = number of chunks removed |
| `GET /internal/documents/{id}/chunks?page=&size=` | yes | page is 0-based |
| `POST /internal/search` | yes | `{query, mode, k, documentIds?}` -> array of `SearchResultDTO` |

Error body: `{code, message, retryable, requestId, details?}`.

## Key settings (all in `.env.example`)
| Var | Default | Meaning |
|---|---|---|
| `INTERNAL_API_KEY` | required (>= 16 chars) | shared secret with Spring |
| `AI_DB_RW_*`, `AI_DB_RO_*`, `AI_DB_HOST`, `AI_DB_NAME` | passwords required | the two DB roles |
| `EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | `hashing` = deterministic test embedder, no download |
| `CHUNKING_MODE` | `semantic` | `fixed` is only for the retrieval ablation |
| `CHUNK_TOKENS` / `CHUNK_OVERLAP_TOKENS` | 500 / 90 | **token counts are estimated at ~4 characters per token** (no tokenizer at ingest); BGE-small truncates at 512 |
| `RERANKER_ENABLED` | false | lazy-loaded cross-encoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`) |
| `RETRIEVAL_PER_DOC_CAP` | 4 | per-document diversity cap (off when scoped to one document) |

## Behaviour worth knowing
- Request models use `extra="forbid"`: an unknown field from the caller returns 400 `VALIDATION_FAILED`, so contract drift shows up immediately.
- A PDF chunk never spans two pages, so the cited page is always correct.
- Scanned / image-only PDFs are rejected with a clear message (OCR is not implemented).

## Tests
```powershell
docker run -d --name nexus-pg -e POSTGRES_PASSWORD=postgres -p 5432:5432 pgvector/pgvector:pg16
$env:TEST_ADMIN_DSN = "postgresql://postgres:postgres@localhost:5432/postgres"
pytest                      # without TEST_ADMIN_DSN or Docker the DB tests are skipped
ruff check .
```
Sample documents live in `tests/data/` (see its README).

## Layout
`app/main.py` factory + lifespan | `app/api/` security, schemas (ALL contract models), routes | `app/core/` config, llm, embeddings, db,
logging, observability, pii | `app/rag/` loader, cleaner, chunker, vector_store, retriever, reranker, citations, ingest_pipeline |
`app/memory/checkpointer.py` stub for AI B | `sql/init_ai_schema.sql` contract 10.2.


## Agent layer (AI B)
Flow: `input_guard -> recall_memory -> supervisor -> planner -> researcher | data_analyst -> analyst -> verifier -> confidence_check -> (loop to planner | action_planning) -> approval_gate (only for HIGH-risk proposals) -> reporter -> save_memory`.
* **Honesty by construction:** the reporter states only VERIFIED claims; unverified/contradicted ones are listed as such; failures appear under "Limitations and failures"; actions are simulated.
* **The agent cannot change anything:** no tool writes data, sends data out or executes actions. It only *proposes* actions from the catalogue; risk is fixed by the action type (never by the LLM); HIGH-risk ones leave only through
  `approval_required`, after which the run is checkpointed (Postgres) and waits for Spring to call `/resume`.
* **Routes** (all need the API key): `POST /internal/investigate` (SSE), `POST /internal/investigate/{threadId}/resume` (SSE), `POST /internal/investigate/{threadId}/cancel`,
  `GET|DELETE /internal/memories`, `DELETE /internal/memories/{id}`, `DELETE /internal/users/{userId}` (memories + checkpoints), `GET /internal/eval/runs[/{id}]`.
* **Try it** (service running, LLM configured, demo data loaded - see `docs/evaluation-howto.md`): `python scripts/investigate_demo.py`.
* **Prompts** are versioned files in `app/agents/prompts/` (no prompt text in code). **Tests** run the real graph with a scripted LLM on a real seeded Postgres: `pytest tests/agents`.
* **Evaluation:** `python -m app.evals.run_eval`, `python -m app.evals.retrieval_ablation`, `python -m app.evals.ci_check` (see `docs/evaluation-howto.md`).
* **Windows:** the Postgres checkpointer uses psycopg async, which needs the SelectorEventLoop: run `uvicorn` WITHOUT `--reload`, or use the Docker image.
* The LLM is called through one small interface (`app/agents/llm_runtime.py`); tool calls use a provider-independent JSON "ReAct" protocol, so Gemini, Ollama and Groq behave the same.
