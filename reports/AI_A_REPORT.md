# AI A report: ai-service foundation + ingestion + retrieval (revision 2, after independent verification)

Scope delivered: everything in the AI A prompt (items 1-7 + ADDENDUM 09). Out of scope and NOT touched: `agents/`, `tools/`, `memory/long_term.py`,
investigate/memories/admin_eval routes, `evals/`, Java, React, docker-compose.

## 0. What changed in this revision
An independent reviewer re-ran the delivery against the 7 requirement files (75/75 tests in a fresh PostgreSQL 16 + pgvector 0.6.0, ruff, a real uvicorn run, the smoke test). Fixes made:
1. **SEC-07 (P0): privacy disclosure added to `README.md`** (free-tier LLM/web providers may log requests; synthetic data only; embeddings are local; Ollama + `WEB_SEARCH_ENABLED=false` for local-only). Previously this was wrongly marked "n/a here".
2. **Sample files committed in `tests/data/`** (txt, md, 2-page pdf, encrypted pdf, scanned pdf, corrupt pdf, docx) plus `tests/test_sample_files.py` (7 new tests). The prompt asked for tiny samples there; before, they were only generated in code.
3. **Report corrections:** the smoke test prints **7** `[PASS]` lines (was written as 6); test count is now **75** (38 unit + 37 DB/API).
4. **Documented that chunk size is an estimate** (about 4 characters per token, no tokenizer at ingest) in README and below (decision 12).
5. README expanded: endpoints, key settings, behaviour notes (`extra="forbid"`, page-bounded chunks, no OCR), test commands.
No application logic was changed; only docs, sample files and tests.

## 1. What was verified, and how (honest status)

| Check | Result | How |
|---|---|---|
| 75 pytest tests (38 unit + 37 DB/API) | **75 passed** | real PostgreSQL 16 + **pgvector 0.6.0** (`TEST_ADMIN_DSN`), hashing embedder. Run by the author (68) and re-run independently by the reviewer (68, then 75 after this revision) |
| `ruff check` | clean | |
| Real `uvicorn app.main:create_app --factory` process | health 200, ingest 200, hybrid search OK, no-key 401, `/openapi.json` 404, smoke test 7/7 PASS | reviewer re-ran against a database prepared like `init.sql` |
| **NOT verified here** | | |
| Real BGE-small download + encode | not run | sandbox cannot reach huggingface.co. `SentenceTransformerEmbedder` is written but untested; first run on your machine downloads ~130 MB |
| pgvector >= 0.8 iterative scan | not run | sandbox has 0.6.0, so the **over-fetch fallback is tested, the `relaxed_order` branch is not**. `pgvector/pgvector:pg16` is >= 0.8 so you will exercise it |
| Cross-encoder reranker with the real model | not run | hook tested with a fake reranker; real `CrossEncoderReranker` untested |
| Docker image build / healthcheck | not run | no Docker in the sandboxes. Dockerfile written, never built |
| Testcontainers path | not run | `TEST_ADMIN_DSN` used instead (recommended on Windows because of the npipe issue) |
| Langfuse | not run | `core/observability.py` is a no-op without keys; masking is unit-tested, the Langfuse calls are not |
| Retrieval **quality** | not measured | hashing embedder is lexical only. No hit-rate number exists yet; that is AI B's ablation (ADD-EV-03) and must use the real BGE model |

## 2. Requirement IDs

| ID | Status | Evidence |
|---|---|---|
| AI-FD-01 | done | `/health` open; every `/internal/*` router gets `Depends(require_api_key)` (`app/main.py`); `hmac.compare_digest` (`api/security.py`); OpenAPI/docs disabled. Tests: `test_security.py`, `test_api.py::test_internal_routes_require_key` |
| AI-FD-02 | done | `core/config.py`: every contract-11 var typed; 3 required secrets have no default; placeholder key rejected; overlap < chunk. Test: `test_core.py` |
| AI-FD-03 | done (provider call paths untested) | `core/llm.py`: `get_llm()` gemini/ollama/groq (lazy imports), tenacity backoff, typed `LlmRateLimited`, `LlmUnavailable`, `LlmConfigError`. Backoff/classification unit-tested with stub errors; no real provider was called |
| AI-FD-04 | done (model download untested) | `core/embeddings.py`: `Embedder` protocol, BGE-small 384-d, normalised, batched, loaded once in lifespan; `HashingEmbedder` for tests |
| AI-FD-05 | done | `core/db.py`: rw pool (`ai_rw`, search_path `ai,public`) + separate ro pool (`ai_readonly`, `default_transaction_read_only=on`, `statement_timeout=SQL_TIMEOUT_MS`); both in `app.state`; `memory/checkpointer.py` no-op stub called at startup. `test_db_readonly.py` (7): select OK, INSERT rejected, **flag flipped off still cannot write**, cannot read `users` or `ai.*`, timeout enforced |
| AI-FD-06 | done | `core/logging.py`: JSON, request-id contextvar + pure-ASGI middleware (echoes `X-Request-Id`), messages PII-redacted and truncated to 500 chars, stack frames/args never logged |
| AI-RG-01 | done | `rag/loader.py` (PDF with pages, DOCX headings+tables, TXT, MD), `cleaner.py`, `chunker.py` (~500 tok, 90 overlap, heading-aware, page+section metadata). Tests incl. the committed samples in `tests/data` |
| AI-RG-02 | done | `vector_store.replace_document`: DELETE + INSERT in one transaction under `pg_advisory_xact_lock(documentId)`. Failed re-ingest and a mid-transaction DB error both keep the old chunks (tested) |
| AI-RG-03 | done | encrypted, corrupt, empty, scanned PDFs, bad DOCX, binary TXT, page/char/chunk limits, deadline: all `IngestionError` -> HTTP 422 `INGESTION_FAILED`, no stack trace. Tests: `test_loaders.py`, `test_sample_files.py`, `test_api.py` |
| AI-RG-04 | done | `retriever.py`: pgvector cosine + `to_tsquery` full-text, **RRF k=60**, HYBRID/VECTOR/KEYWORD, document scope; `citations.py` builds `EvidenceDTO` |
| AI-RG-05 | done (cap only) | per-document diversity cap (`RETRIEVAL_PER_DOC_CAP`, default 4, off when scoped to one document). **No MMR** |
| AI-RG-06 | reranker done / OCR **not done** | `rag/reranker.py` lazy CrossEncoder behind `RERANKER_ENABLED`; scanned PDFs are rejected with a clear message |
| SEC-02 | partly (this service's share) | constant-time key compare, key never logged |
| SEC-03 | done (this service's share) | all SQL parameterised; only the validated table name is interpolated (`^ai\.[a-z_][a-z0-9_]{0,40}$`); keyword query built from `[A-Za-z0-9]+` tokens only; ro pool + role |
| SEC-04 | partly | size cap (413) + magic-byte checks in loaders; extension/content-type/hash/random keys are Spring's job |
| SEC-07 | **done for this service (README)** | privacy and data-egress section in `README.md`. The Settings-page note is frontend work |
| ADD-GR-02 | helper done, wiring is AI B's | `core/pii.py`: EMAIL, CARD (Luhn), SSN, AADHAAR (Verhoeff), PAN, PHONE; never returns raw values; `to_guardrail_detail()` safe for events. Applied here in logs and `observability.mask()`. **Not** applied to stored chunks (the corpus's fake PII must stay retrievable). AI B must call it for web queries and the memory summary |
| ADD-EV-03 (hooks) | done | `Retriever.search(query, mode=, k=, rerank=, document_ids=)` needs no LLM; `VectorStore.create_scratch(pool, caps, "name")` makes `ai.eval_chunks_<name>` for fixed vs semantic side by side. Tested end to end |
| Chunking modes | done | `CHUNKING_MODE=fixed|semantic` or `chunking_mode=` per call; both tested and shown to differ |

## 3. Decisions and deviations (read these)

1. **Chunks never span two PDF pages.** Found by test: two short pages became one chunk and cited page 1 for page-2 text. A page break is now a hard boundary. Cost: no overlap across page breaks, slightly more and smaller chunks. Benefit: the page the UI opens (FE-DO-04/06) is always correct.
2. **Score semantics.** `SearchResultDTO.score`: HYBRID = RRF normalised so "rank 1 in both lists" = 1.0 (ranks well, NOT a quality signal); VECTOR = cosine; KEYWORD = `ts_rank_cd` normalised. Every `RetrievedChunk` also carries `similarity` (exact cosine). **`citations.py` uses `similarity` as evidence "quality" for the confidence model (contract 9).** AI B should use `Citation.score`, not `RetrievedChunk.score`.
3. **Keyword search is OR-semantics** (`why | did | q2 | revenue`, ranked by `ts_rank_cd`), not `plainto_tsquery` AND, because natural-language questions return nothing under AND.
4. **Scoped vector search.** HNSW filters after the scan. pgvector >= 0.8: `hnsw.iterative_scan = relaxed_order`. Older: over-fetch 10x (max 1000). Known limit on old pgvector: a document whose chunks are all outside the nearest 1000 of the corpus can return fewer than k.
5. **Schema DDL runs as `ai_rw`.** `ensure_ai_schema` skips `CREATE EXTENSION`/`CREATE SCHEMA` when they exist. If the extension is missing it tries and logs a warning; the real fix is `infra/postgres/init.sql` (header of `sql/init_ai_schema.sql` has the role notes). `sql/init_ai_schema.sql` is identical to contract 10.2 plus comments (verified by reviewer).
6. **Chunk title lives in `metadata->>'title'`** (no title column, no cross-schema join). Renaming a document needs a re-ingest; the contract has no rename.
7. **Schemas use `extra="forbid"`** so contract drift fails loudly (400 VALIDATION_FAILED). If Spring adds a field before the contract changes, this is where it shows up; loosen to `ignore` only if that becomes annoying.
8. **Error body of the internal API** (not in the contract, needed by Spring's error mapping): `{code, message, retryable, requestId, details?}`. 400 VALIDATION_FAILED, 401 UNAUTHENTICATED, 413 FILE_TOO_LARGE, 422 INGESTION_FAILED, 503 AI_SERVICE_UNAVAILABLE / LLM_RATE_LIMITED, 500 INTERNAL_ERROR. Please add `InternalError` to contract 06.
9. **Sync pools / sync routes.** FastAPI runs `def` routes in a thread pool, right for blocking psycopg + CPU embedding. LangGraph's `AsyncPostgresSaver` needs an async connection: use `app.core.db.conninfo(settings, "rw")` in `memory/checkpointer.py`.
10. **Provider keys are validated lazily** (`get_llm()` raises `LlmConfigError`), so ingestion-only deployments start without a Gemini key.
11. **Compatibility pins:** `requirements.txt` has lower bounds only (no versions from memory); run `uv pip compile requirements.txt -o requirements.lock` and commit the lock.
12. **Chunk size is estimated, not measured:** about 4 characters per token (`CHARS_PER_TOKEN` in `chunker.py`), so "500 tokens" is approximate. BGE-small truncates at 512 tokens, which leaves headroom. Swap in a real tokenizer only if the ablation shows it matters.
13. **DELETE returns `{deleted: <number of chunks removed>}`** (contract only says `{deleted}`). Spring should not treat it as a boolean.

## 4. For AI B (what exists, how to plug in)

- Register routes: append your routers to `INTERNAL_ROUTERS` in `app/main.py` (they get the API-key dependency automatically). State: `request.app.state.{settings, embedder, rw_pool, ro_pool, store, retriever, caps, checkpointer}`.
- SQL tool: use `app.state.ro_pool` (read-only + timeout, rows as dicts). Still do the sqlglot AST guard.
- Events: `app/api/schemas.py` has every payload model, `EVENT_PAYLOADS`, and `AgentEvent.of(payload).to_sse()`. Spring assigns `seq`, so Python frames carry only `event:` + `data:`.
- Retrieval: `retriever.search(q, mode=, k=, document_ids=, rerank=)` -> `build_citations(chunks, q)` -> `.to_evidence()` gives an `EvidenceDTO`.
- LLM: `get_llm(settings)` + `with_backoff` / `awith_backoff`; catch `LlmRateLimited` -> contract error `LLM_RATE_LIMITED`.
- Replace the stub in `app/memory/checkpointer.py` (returns the saver; stored in `app.state.checkpointer`).
- PII: `from app.core.pii import redact, redact_text`; `observability.mask(obj)` for Langfuse payloads.
- `ai.memories` and `ai.eval_runs` are created by `ensure_ai_schema`; no access code is provided (yours).
- Lifespan order: logging -> embedder -> rw pool -> ro pool -> DDL -> capabilities -> store/retriever -> checkpointer -> Langfuse.

## 5. For infra and Spring

- Infra: copy `sql/init_ai_schema.sql` into `infra/postgres/init.sql`, after creating roles/extension/schema as its header says. Image CMD: `uvicorn app.main:create_app --factory`. Mount a named volume at `/models` (HF cache). Healthcheck start-period is 180 s. Env: `.env.example`.
- Spring: `POST /internal/ingest` multipart parts `meta` (JSON, camelCase `IngestRequest`, no extra fields) + `file`; `422 INGESTION_FAILED` body `message` = reason to store on the document; `GET /internal/documents/{id}/chunks?page=0&size=20` (0-based); search body `{query, mode, k, documentIds}` returns a bare array. `/health` returns 503 when either DB pool fails.

## 6. Exact commands (Windows, PowerShell, Docker Desktop). One block at a time.

**Step 1: unzip, venv, dependencies** (from the folder containing the zip; use Python 3.11 or 3.12)
```powershell
Expand-Archive .\ai-service-final.zip -DestinationPath . -Force ; cd .\ai-service
python -m venv .venv ; .\.venv\Scripts\Activate.ps1
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```
Expected: prompt shows `(.venv)`; pip ends with `Successfully installed ...`.

**Step 2: start a pgvector Postgres**
```powershell
docker run -d --name nexus-pg -e POSTGRES_PASSWORD=postgres -p 5432:5432 pgvector/pgvector:pg16
```
Expected: prints a container id; `docker ps` shows `nexus-pg` Up.

**Step 3: run the tests**
```powershell
$env:TEST_ADMIN_DSN = "postgresql://postgres:postgres@localhost:5432/postgres"
pytest
```
Expected: `75 passed` (38 unit + 37 DB/API). If you see about 37 skipped, `TEST_ADMIN_DSN` is not set in this window.

**Step 4: create the dev database, roles, schema**
```powershell
Get-Content sql\dev_bootstrap.sql | docker exec -i nexus-pg psql -U postgres
```
Expected: `CREATE ROLE`, `CREATE ROLE`, `CREATE DATABASE`, `You are now connected to database "nexusai"`, `CREATE EXTENSION`, `CREATE SCHEMA`, `REVOKE`, `GRANT`.
(Do this on a fresh container. The test run in step 3 does not touch the `nexusai` database, but if you re-run the script you will see harmless "already exists" errors.)

**Step 5: configure and start the service**
```powershell
copy .env.example .env
notepad .env
```
Set `INTERNAL_API_KEY` (16+ chars), `AI_DB_RW_PASSWORD=dev_rw_password`, `AI_DB_RO_PASSWORD=dev_ro_password`, `AI_DB_HOST=localhost`. Then:
```powershell
uvicorn app.main:create_app --factory --port 8000
```
Expected: first start downloads BGE-small (~130 MB, 1-3 min), then a JSON log line `"msg": "ai-service ready"` with `pgvector` and `iterativeScan` (should be `true` on the Docker image). This is where the untested real-model path runs: if it fails, send the log line.

**Step 6: smoke test** (second PowerShell window, venv active)
```powershell
$env:INTERNAL_API_KEY = "<the same key as in .env>"
python scripts\smoke_test.py
```
Expected: **7** lines `[PASS] ...` then `ALL SMOKE CHECKS PASSED`.

**Step 7: lint**
```powershell
ruff check .
```
Expected: `All checks passed!`

**Docker image** (not built by me): `docker build -t nexus-ai-service .` (add `--build-arg PRELOAD_MODEL=1` to bake the model in).

**Regenerate `tests/data` samples** (only if you ever delete them), from `ai-service/` with the venv active:
```powershell
python -c "from pathlib import Path; from tests.helpers import make_pdf, encrypt_pdf; d=Path('tests/data'); p=make_pdf(['Quarterly report\nRevenue fell in the South region.','Supplier incident note\nA supplier delay caused stock-outs in June.']); (d/'sample.pdf').write_bytes(p); (d/'sample_encrypted.pdf').write_bytes(encrypt_pdf(p,'secret')); (d/'sample_scanned.pdf').write_bytes(make_pdf(['',''])); (d/'sample_corrupt.pdf').write_bytes(b'%PDF-1.4\nnot a real pdf\n')"
```
(`sample.txt`, `sample.md`, `sample.docx` are plain files; edit them by hand.)

## 7. Known gaps to tell AI B / me before integration
- No retrieval-quality number exists; do not quote any until AI B runs the ablation with real BGE.
- OCR is not implemented (scanned PDFs are refused with a clear reason).
- Document titles in chunk metadata are copied at ingest.
- `testcontainers[postgres]` is only needed if you use the Docker-started test DB instead of `TEST_ADMIN_DSN`.
- Still unverified anywhere: real BGE/reranker models, Docker build, pgvector >= 0.8 branch, Langfuse calls, real LLM providers.
