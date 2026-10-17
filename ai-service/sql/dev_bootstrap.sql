-- DEV ONLY: creates the database, roles and schema that infra/postgres/init.sql will create in the real stack.
-- Passwords below are dev defaults; put the same values in .env (AI_DB_RW_PASSWORD / AI_DB_RO_PASSWORD).
-- Run once:  Get-Content sql\dev_bootstrap.sql | docker exec -i nexus-pg psql -U postgres
CREATE ROLE ai_rw LOGIN PASSWORD 'dev_rw_password';
CREATE ROLE ai_readonly LOGIN PASSWORD 'dev_ro_password';
CREATE DATABASE nexusai;
\c nexusai
CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA ai AUTHORIZATION ai_rw;
REVOKE ALL ON SCHEMA ai FROM PUBLIC;
GRANT CONNECT ON DATABASE nexusai TO ai_rw, ai_readonly;
-- ai_readonly gets SELECT on the five business tables from Flyway V6 in the backend; not needed for this service to start.
