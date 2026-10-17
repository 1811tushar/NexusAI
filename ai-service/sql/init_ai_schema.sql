-- =============================================================================
-- NexusAI: schema `ai` (contract 10.2). IDEMPOTENT. The infra stream copies this into infra/postgres/init.sql.
-- app/core/db.py runs this same file at startup (as role ai_rw) and skips the two statements that need
-- privileges (CREATE EXTENSION / CREATE SCHEMA) when the extension/schema already exist.
--
-- ROLE CREATION NOTES (run ONCE as a superuser/owner, BEFORE the statements below; use real passwords from env):
--   CREATE ROLE ai_rw       LOGIN PASSWORD '<AI_DB_RW_PASSWORD>';
--   CREATE ROLE ai_readonly LOGIN PASSWORD '<AI_DB_RO_PASSWORD>'
--        SET default_transaction_read_only = on  SET statement_timeout = 5000;   -- belt and braces; the pool also sets them
--   CREATE EXTENSION IF NOT EXISTS vector;
--   CREATE SCHEMA IF NOT EXISTS ai AUTHORIZATION ai_rw;
--   REVOKE ALL ON SCHEMA ai FROM PUBLIC;                     -- ai_readonly must NOT see schema ai
--   REVOKE CREATE ON SCHEMA public FROM PUBLIC;              -- optional hardening
--   -- then run the table DDL below AS ai_rw (SET ROLE ai_rw; ... RESET ROLE;) so ai_rw owns the tables.
--   -- ai_readonly gets SELECT on the five business tables ONLY, from Flyway V6 (guarded GRANT). Never on users/approvals/etc.
-- =============================================================================
CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS ai;

CREATE TABLE IF NOT EXISTS ai.document_chunks (id BIGSERIAL PRIMARY KEY, document_id BIGINT NOT NULL, chunk_index INT NOT NULL, page INT, section TEXT,
  content TEXT NOT NULL, embedding vector(384) NOT NULL,                       -- BAAI/bge-small-en-v1.5
  tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED, metadata JSONB NOT NULL DEFAULT '{}', created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON ai.document_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_chunks_tsv ON ai.document_chunks USING gin (tsv);
CREATE INDEX IF NOT EXISTS idx_chunks_document ON ai.document_chunks (document_id);
CREATE TABLE IF NOT EXISTS ai.memories (id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL, summary TEXT NOT NULL, embedding vector(384) NOT NULL,
  importance REAL NOT NULL DEFAULT 0.5, source_investigation_id BIGINT, access_count INT NOT NULL DEFAULT 0, last_accessed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE INDEX IF NOT EXISTS idx_memories_embedding ON ai.memories USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_memories_user ON ai.memories (user_id);
CREATE TABLE IF NOT EXISTS ai.eval_runs (id BIGSERIAL PRIMARY KEY, system VARCHAR(20) NOT NULL, variant VARCHAR(60), config JSONB NOT NULL, metrics JSONB NOT NULL, results JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now());
