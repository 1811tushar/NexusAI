"""Database access (AI-FD-05): rw pool (role ai_rw, schema ai) and a SEPARATE read-only pool (role ai_readonly)
for AI B's SQL tool. The ro pool sets default_transaction_read_only=on + statement_timeout, and the role itself only
has SELECT on five business tables, so even `SET default_transaction_read_only=off` cannot write.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.core.config import Settings

log = logging.getLogger(__name__)
SCHEMA_SQL = Path(__file__).resolve().parents[2] / "sql" / "init_ai_schema.sql"


def conninfo(settings: Settings, role: str) -> str:
    """Plain libpq conninfo; AI B can reuse it for an AsyncConnectionPool (LangGraph checkpointer)."""
    user, pw = (
        (settings.ai_db_rw_user, settings.ai_db_rw_password)
        if role == "rw"
        else (settings.ai_db_ro_user, settings.ai_db_ro_password)
    )
    return (
        f"host={settings.ai_db_host} port={settings.ai_db_port} dbname={settings.ai_db_name} "
        f"user={user} password={_q(pw)} connect_timeout=10"
    )


def _q(v: str) -> str:
    return "'" + v.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _configure_rw(conn: psycopg.Connection) -> None:
    register_vector(conn)
    conn.commit()


def open_rw_pool(settings: Settings) -> ConnectionPool:
    pool = ConnectionPool(
        conninfo(settings, "rw"),
        min_size=settings.db_pool_min,
        max_size=settings.db_pool_max,
        kwargs={"row_factory": dict_row, "options": "-c search_path=ai,public"},
        configure=_configure_rw,
        open=False,
        name="ai_rw",
    )
    pool.open(wait=True, timeout=30)
    return pool


def open_ro_pool(settings: Settings) -> ConnectionPool:
    opts = f"-c default_transaction_read_only=on -c statement_timeout={int(settings.sql_timeout_ms)}"
    pool = ConnectionPool(
        conninfo(settings, "ro"),
        min_size=1,
        max_size=max(2, settings.db_pool_max // 2),
        kwargs={"row_factory": dict_row, "options": opts},
        open=False,
        name="ai_readonly",
    )
    pool.open(wait=True, timeout=30)
    return pool


def _split_statements(sql_text: str) -> list[str]:
    no_comments = "\n".join(re.sub(r"--.*$", "", line) for line in sql_text.splitlines())
    return [s.strip() for s in no_comments.split(";") if s.strip()]


def ensure_ai_schema(pool: ConnectionPool) -> None:
    """Idempotent DDL as ai_rw. Extension/schema creation is skipped when present (ai_rw usually lacks the privilege)."""
    with pool.connection() as conn:
        has_ext = conn.execute("SELECT 1 FROM pg_extension WHERE extname='vector'").fetchone() is not None
        has_schema = conn.execute("SELECT 1 FROM pg_namespace WHERE nspname='ai'").fetchone() is not None
        if not has_ext:
            log.warning("pgvector extension missing; trying to create it (needs privileges; normally done by init.sql)")
        for stmt in _split_statements(SCHEMA_SQL.read_text(encoding="utf-8")):
            head = stmt.upper()
            if head.startswith("CREATE EXTENSION") and has_ext:
                continue
            if head.startswith("CREATE SCHEMA") and has_schema:
                continue
            conn.execute(stmt)
        conn.commit()
    with pool.connection() as conn:  # make sure the vector type is known to this pool's connections
        register_vector(conn)


@dataclass(frozen=True)
class Capabilities:
    pgvector_version: str
    iterative_scan: bool   # pgvector >= 0.8.0 (hnsw.iterative_scan)


def detect_capabilities(pool: ConnectionPool) -> Capabilities:
    with pool.connection() as conn:
        row = conn.execute("SELECT extversion FROM pg_extension WHERE extname='vector'").fetchone()
    version = row["extversion"] if row else "0"
    nums = [int(x) for x in re.findall(r"\d+", version)[:3]] + [0, 0, 0]
    return Capabilities(version, tuple(nums[:3]) >= (0, 8, 0))


def ping(pool: ConnectionPool) -> bool:
    try:
        with pool.connection(timeout=3) as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:  # noqa: BLE001
        return False
