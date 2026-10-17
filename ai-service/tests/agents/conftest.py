"""AI B test fixtures: a SEPARATE database with the business tables (V6) + the deterministic seed (V7), the `ai` schema, both pools."""
from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace

import psycopg
import pytest

from app.core.config import Settings
from app.core.db import detect_capabilities, ensure_ai_schema, open_ro_pool, open_rw_pool
from app.core.embeddings import HashingEmbedder
from app.rag.retriever import Retriever
from app.rag.vector_store import VectorStore

SEED_DIR = Path(__file__).resolve().parents[2] / "app" / "evals" / "seed"


@pytest.fixture(scope="session")
def biz(pg, settings):
    name = f"nexus_b_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(pg["admin"], autocommit=True) as admin:
        admin.execute(f'CREATE DATABASE "{name}"')
    base = psycopg.conninfo.make_conninfo(pg["admin"], dbname=name)
    with psycopg.connect(base, autocommit=True) as c:
        c.execute("CREATE EXTENSION IF NOT EXISTS vector")
        c.execute("CREATE SCHEMA ai AUTHORIZATION ai_rw")
        c.execute("REVOKE ALL ON SCHEMA ai FROM PUBLIC")
        c.execute(f'GRANT CONNECT ON DATABASE "{name}" TO ai_rw, ai_readonly')
        c.execute("CREATE TABLE users (id BIGSERIAL PRIMARY KEY, email TEXT, password_hash TEXT)")
        c.execute("INSERT INTO users (email, password_hash) VALUES ('a@b.c','x')")
        c.execute((SEED_DIR / "local_business_schema.sql").read_text(encoding="utf-8"))
        c.execute((SEED_DIR / "V7__seed_business_data.sql").read_text(encoding="utf-8"))
    s = Settings(_env_file=None, internal_api_key=settings.internal_api_key, ai_db_host=pg["host"], ai_db_port=pg["port"], ai_db_name=name,
                 ai_db_rw_password="rw_test_pw", ai_db_ro_password="ro_test_pw", embedding_model="hashing", log_level="WARNING",
                 web_search_enabled=True, max_tool_attempts=3)
    rw, ro = open_rw_pool(s), open_ro_pool(s)
    ensure_ai_schema(rw)
    caps = detect_capabilities(rw)
    emb = HashingEmbedder(384)
    store = VectorStore(rw, caps)
    ns = SimpleNamespace(settings=s, rw=rw, ro=ro, caps=caps, embedder=emb, store=store, retriever=Retriever(store, emb, s), dbname=name)
    yield ns
    rw.close()
    ro.close()
    with psycopg.connect(pg["admin"], autocommit=True) as admin:
        admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


@pytest.fixture
def clean_memories(biz):
    with biz.rw.connection() as c:
        c.execute("TRUNCATE ai.memories")
        c.commit()
    return biz


@pytest.fixture(autouse=True)
def _no_backoff_sleep(monkeypatch):
    monkeypatch.setattr("app.agents.react.backoff_delay", lambda n: 0)
