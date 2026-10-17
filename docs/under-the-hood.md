# Under the hood: what is hand-written, what is delegated

NexusAI is built so that the parts that decide correctness and safety are plain, testable code. Frameworks are used for plumbing. This page is the map; at integration time each row is checked against the actual source and corrected if the code differs.

| Concern | Hand-written (core skill) | Delegated to a framework or library |
|---|---|---|
| Retrieval | Hybrid ranking in SQL: pgvector cosine and Postgres full-text lists merged with Reciprocal Rank Fusion (k=60); user/document scoping; heading-aware overlapping chunker with fixed-size mode for ablation | pgvector (index, distance), sentence-transformers (embedding model) |
| Agent safety | AST-based SQL guard (one SELECT, allow-listed tables, forced LIMIT, banned functions); read-only DB role and session; fixed-risk action catalogue; Pydantic parameter validation | sqlglot (parsing), PostgreSQL privileges |
| Confidence | Claim and overall confidence as pure functions (contract section 9) with unit tests for every branch | none |
| Control flow | The decisions (ACCEPT / LOOP / ACCEPT_LOW_CONFIDENCE, approval gate placement, failure policy) are code, not prompts | LangGraph (graph execution, Postgres checkpointer, `interrupt()` pause/resume) |
| Failure handling | One policy helper: timeouts, bounded attempts with the failure reason fed back, "stop and explain", Limitations section | tenacity (backoff for transient errors) |
| Guardrails | Input guard rules, PII redaction (patterns plus checksums), citation validator (keys, numbers, quotes), output schema validation | none (LLM classifier only for ambiguous inputs) |
| Long-running runs | Sequenced event persistence, replay by `Last-Event-ID`, many viewers, runs independent of browsers, restart recovery, state machine | Spring MVC and virtual threads, WebClient as an SSE client |
| Approvals | Role and self-approval checks, race-safe conditional update (`WHERE status='PENDING'`), execution by Spring only, simulated and logged | Spring Security (authentication), JPA |
| Auth | Rotating hashed refresh tokens with family reuse detection, lockout | JJWT, BCrypt |
| Evaluation | Golden set, four systems, retrieval ablation, deterministic checks, CI gate | pytest, an LLM as judge (documented, human spot-checked) |
| Infrastructure | Database role bootstrap proven by privilege probes; nginx limits and SSE settings proven by real-nginx tests; contract-shaped fake AI for deterministic integration | Docker Compose, nginx, GitHub Actions |

**Why this matters:** if LangGraph were replaced, the decisions, safety rules and numbers would still be the same code. If the LLM misbehaves, the system's guarantees (no HIGH-risk execution without approval, no write SQL, no invented citations) hold because they do not depend on the model.
