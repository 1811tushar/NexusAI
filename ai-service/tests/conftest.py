"""Test setup. DB tests need a pgvector Postgres:
  * set TEST_ADMIN_DSN=postgresql://postgres:postgres@localhost:5432/postgres  (superuser, any pgvector Postgres), or
  * have Docker running: testcontainers starts pgvector/pgvector:pg16 automatically.
Without either, DB tests are SKIPPED with a reason (unit tests still run)."""
from __future__ import annotations

import os
import uuid

import psycopg
import pytest

os.environ.setdefault("INTERNAL_API_KEY", "test-internal-key-0123456789")
os.environ.setdefault("AI_DB_RW_PASSWORD", "rw_test_pw")
os.environ.setdefault("AI_DB_RO_PASSWORD", "ro_test_pw")
os.environ.setdefault("EMBEDDING_MODEL", "hashing")

from app.core.config import Settings  # noqa: E402
from app.core.db import detect_capabilities, ensure_ai_schema, open_ro_pool, open_rw_pool  # noqa: E402
from app.core.embeddings import HashingEmbedder  # noqa: E402
from app.rag.retriever import Retriever  # noqa: E402
from app.rag.vector_store import VectorStore  # noqa: E402

API_KEY = os.environ["INTERNAL_API_KEY"]
HEADERS = {"X-Internal-API-Key": API_KEY}


@pytest.fixture(scope="session")
def pg():
    dsn = os.getenv("TEST_ADMIN_DSN")
    container = None
    if not dsn:
        try:
            from testcontainers.postgres import PostgresContainer

            container = PostgresContainer("pgvector/pgvector:pg16", username="postgres", password="postgres", dbname="postgres")
            container.start()
            dsn = (f"postgresql://postgres:postgres@{container.get_container_host_ip()}:"
                   f"{container.get_exposed_port(5432)}/postgres")
        except Exception as exc:  # noqa: BLE001
            pytest.skip(f"No test database: set TEST_ADMIN_DSN or start Docker ({type(exc).__name__})")
    dbname = f"nexus_test_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(dsn, autocommit=True) as admin:
        admin.execute(f'CREATE DATABASE "{dbname}"')
        info = admin.info
        host, port = info.host, info.port
    base = psycopg.conninfo.make_conninfo(dsn, dbname=dbname)
    with psycopg.connect(base, autocommit=True) as c:
        c.execute("CREATE EXTENSION IF NOT EXISTS vector")
        for role, pw in (("ai_rw", "rw_test_pw"), ("ai_readonly", "ro_test_pw")):
            exists = c.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,)).fetchone()
            c.execute(f"{'ALTER' if exists else 'CREATE'} ROLE {role} LOGIN PASSWORD '{pw}'")
        c.execute("CREATE SCHEMA ai AUTHORIZATION ai_rw")
        c.execute("REVOKE ALL ON SCHEMA ai FROM PUBLIC")
        c.execute(f'GRANT CONNECT ON DATABASE "{dbname}" TO ai_rw, ai_readonly')
        # what Flyway V6 does: business tables + guarded GRANT to ai_readonly; `users` is deliberately NOT granted
        c.execute("CREATE TABLE regions (id SMALLINT PRIMARY KEY, name VARCHAR(40) NOT NULL UNIQUE)")
        c.execute("INSERT INTO regions VALUES (1,'North'),(2,'South')")
        c.execute("CREATE TABLE users (id BIGSERIAL PRIMARY KEY, email TEXT, password_hash TEXT)")
        c.execute("INSERT INTO users (email, password_hash) VALUES ('a@b.c','x')")
        c.execute("GRANT USAGE ON SCHEMA public TO ai_readonly")
        c.execute("GRANT SELECT ON regions TO ai_readonly")
    yield {"host": host, "port": int(port), "dbname": dbname, "admin": base}
    with psycopg.connect(dsn, autocommit=True) as admin:
        admin.execute(f'DROP DATABASE IF EXISTS "{dbname}" WITH (FORCE)')
    if container:
        container.stop()


@pytest.fixture(scope="session")
def settings(pg) -> Settings:
    return Settings(_env_file=None, internal_api_key=API_KEY, ai_db_host=pg["host"], ai_db_port=pg["port"],
                    ai_db_name=pg["dbname"], ai_db_rw_password="rw_test_pw", ai_db_ro_password="ro_test_pw",
                    embedding_model="hashing", log_level="WARNING")


@pytest.fixture(scope="session")
def pools(settings):
    rw, ro = open_rw_pool(settings), open_ro_pool(settings)
    ensure_ai_schema(rw)
    yield rw, ro
    rw.close()
    ro.close()


@pytest.fixture(scope="session")
def caps(pools):
    return detect_capabilities(pools[0])


@pytest.fixture
def store(pools, caps):
    s = VectorStore(pools[0], caps)
    with pools[0].connection() as c:
        c.execute("TRUNCATE ai.document_chunks")
        c.commit()
    return s


@pytest.fixture(scope="session")
def embedder():
    return HashingEmbedder(384)


@pytest.fixture
def retriever(store, embedder, settings):
    return Retriever(store, embedder, settings)


@pytest.fixture(scope="session")
def client(settings):
    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app(settings), raise_server_exceptions=False) as c:
        yield c
