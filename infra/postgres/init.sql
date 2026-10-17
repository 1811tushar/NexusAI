-- NexusAI database bootstrap. Executed by init.sh (psql 16+, uses \getenv).
-- Idempotent: safe to run again against an existing database (used by CI).
\set ON_ERROR_STOP on
\getenv rw_user AI_DB_RW_USER
\getenv rw_pw   AI_DB_RW_PASSWORD
\getenv ro_user AI_DB_RO_USER
\getenv ro_pw   AI_DB_RO_PASSWORD

-- 1. Roles --------------------------------------------------------------------------------
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'rw_user', :'rw_pw')
 WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'rw_user') \gexec
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'ro_user', :'ro_pw')
 WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'ro_user') \gexec

-- ai_rw: read/write on schema "ai" ONLY. search_path lets it use the pgvector type from "public"
-- while LangGraph's checkpointer.setup() creates its tables inside "ai".
ALTER ROLE :"rw_user" SET search_path = ai, public;
-- ai_readonly: used ONLY by the agent's SQL tool. Read-only sessions, 5 s statement timeout.
-- Its SELECT grant on the five business tables is issued by Flyway migration V6 (tables do not exist yet).
ALTER ROLE :"ro_user" SET default_transaction_read_only = on;
ALTER ROLE :"ro_user" SET statement_timeout = '5s';
ALTER ROLE :"ro_user" SET search_path = public;

-- 2. Extension and schema ------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS ai;
REVOKE ALL ON SCHEMA ai FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA ai TO :"rw_user";   -- CREATE is required by checkpointer.setup()
GRANT USAGE ON SCHEMA public TO :"rw_user";       -- needed to resolve the vector type
-- nobody except the owner may create objects in public (explicit, even though PG15+ defaults to this)
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

-- 3. Tables (contract section 10.2) -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS ai.document_chunks (
    id          BIGSERIAL PRIMARY KEY,
    document_id BIGINT      NOT NULL,
    chunk_index INT         NOT NULL,
    page        INT,
    section     TEXT,
    content     TEXT        NOT NULL,
    embedding   vector(384) NOT NULL,
    tsv         tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    metadata    JSONB       NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON ai.document_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_chunks_tsv       ON ai.document_chunks USING gin (tsv);
CREATE INDEX IF NOT EXISTS idx_chunks_document  ON ai.document_chunks (document_id);

CREATE TABLE IF NOT EXISTS ai.memories (
    id                      BIGSERIAL PRIMARY KEY,
    user_id                 BIGINT      NOT NULL,
    summary                 TEXT        NOT NULL,
    embedding               vector(384) NOT NULL,
    importance              REAL        NOT NULL DEFAULT 0.5,
    source_investigation_id BIGINT,
    access_count            INT         NOT NULL DEFAULT 0,
    last_accessed_at        TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_memories_embedding ON ai.memories USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_memories_user      ON ai.memories (user_id);

CREATE TABLE IF NOT EXISTS ai.eval_runs (
    id         BIGSERIAL PRIMARY KEY,
    system     VARCHAR(20) NOT NULL,
    variant    VARCHAR(60),
    config     JSONB       NOT NULL,
    metrics    JSONB       NOT NULL,
    results    JSONB       NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 4. Privileges for ai_rw on everything created above ---------------------------------------------
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES    IN SCHEMA ai TO :"rw_user";
GRANT USAGE, SELECT, UPDATE          ON ALL SEQUENCES IN SCHEMA ai TO :"rw_user";
ALTER DEFAULT PRIVILEGES IN SCHEMA ai GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES    TO :"rw_user";
ALTER DEFAULT PRIVILEGES IN SCHEMA ai GRANT USAGE, SELECT, UPDATE          ON SEQUENCES TO :"rw_user";

-- LangGraph checkpoint tables are created by the AI service itself (checkpointer.setup()) as ai_rw,
-- inside schema ai (search_path above), so ai_rw owns them and nothing else is needed here.
-- ai_readonly intentionally has NO privilege on schema ai and NO grant on any private table.
