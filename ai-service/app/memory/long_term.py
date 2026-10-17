"""Long-term memory in ai.memories (AI-ME-01..03). EVERY query filters by user_id (isolation is tested); no function accepts user_id=None."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np
from psycopg_pool import ConnectionPool

from app.core.embeddings import Embedder
from app.memory.scoring import DEDUPE_SIMILARITY, MIN_RELEVANCE, TOP_N, recall_score

log = logging.getLogger(__name__)


@dataclass
class MemoryHit:
    id: int
    summary: str
    score: float
    relevance: float
    source_investigation_id: int | None


def _uid(user_id: int) -> int:
    if not isinstance(user_id, int) or isinstance(user_id, bool) or user_id <= 0:
        raise ValueError("a valid user_id is required for every memory operation")
    return user_id


def recall(pool: ConnectionPool, embedder: Embedder, user_id: int, query: str, *, top: int = TOP_N,
           now: datetime | None = None) -> list[MemoryHit]:
    uid = _uid(user_id)
    now = now or datetime.now(UTC)
    q = np.asarray(embedder.embed_query(query), dtype=np.float32)
    with pool.connection() as conn:
        rows = conn.execute(
            "SELECT id, summary, importance, source_investigation_id, created_at, 1 - (embedding <=> %s) AS relevance "
            "FROM ai.memories WHERE user_id = %s ORDER BY embedding <=> %s LIMIT 25", (q, uid, q)).fetchall()
        hits: list[MemoryHit] = []
        for r in rows:
            rel = max(0.0, float(r["relevance"]))
            if rel < MIN_RELEVANCE:
                continue
            age_days = (now - r["created_at"]).total_seconds() / 86400.0
            hits.append(MemoryHit(r["id"], r["summary"], round(recall_score(rel, age_days, float(r["importance"])), 4), rel,
                                  r["source_investigation_id"]))
        hits.sort(key=lambda h: (-h.score, h.id))
        hits = hits[:top]
        if hits:
            conn.execute("UPDATE ai.memories SET access_count = access_count + 1, last_accessed_at = now() "
                         "WHERE user_id = %s AND id = ANY(%s)", (uid, [h.id for h in hits]))
            conn.commit()
    return hits


def save(pool: ConnectionPool, embedder: Embedder, user_id: int, summary: str, *, investigation_id: int | None,
         importance: float) -> tuple[int, bool]:
    """Insert a memory unless a near-duplicate (cosine >= 0.92) already exists for this user -> returns (id, deduped)."""
    uid = _uid(user_id)
    vec = np.asarray(embedder.embed_documents([summary])[0], dtype=np.float32)
    with pool.connection() as conn, conn.transaction():
        dup = conn.execute(
            "SELECT id, importance, 1 - (embedding <=> %s) AS sim FROM ai.memories WHERE user_id = %s "
            "ORDER BY embedding <=> %s LIMIT 1", (vec, uid, vec)).fetchone()
        if dup and float(dup["sim"]) >= DEDUPE_SIMILARITY:
            conn.execute("UPDATE ai.memories SET importance = GREATEST(importance, %s), last_accessed_at = now() "
                         "WHERE id = %s AND user_id = %s", (importance, dup["id"], uid))
            return int(dup["id"]), True
        row = conn.execute(
            "INSERT INTO ai.memories (user_id, summary, embedding, importance, source_investigation_id) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING id", (uid, summary, vec, importance, investigation_id)).fetchone()
    return int(row["id"]), False


def list_memories(pool: ConnectionPool, user_id: int, page: int, size: int, q: str | None = None) -> tuple[list[dict], int]:
    uid = _uid(user_id)
    like = f"%{q.strip()}%" if q and q.strip() else None
    where, params = "user_id = %s" + (" AND summary ILIKE %s" if like else ""), [uid] + ([like] if like else [])
    with pool.connection() as conn:
        total = conn.execute(f"SELECT count(*) AS n FROM ai.memories WHERE {where}", params).fetchone()["n"]
        rows = conn.execute(
            f"SELECT id, summary, source_investigation_id, importance, created_at, last_accessed_at FROM ai.memories "
            f"WHERE {where} ORDER BY created_at DESC, id DESC LIMIT %s OFFSET %s", [*params, size, page * size]).fetchall()
    return rows, total


def delete_one(pool: ConnectionPool, user_id: int, memory_id: int) -> int:
    uid = _uid(user_id)
    with pool.connection() as conn, conn.transaction():
        return conn.execute("DELETE FROM ai.memories WHERE id = %s AND user_id = %s", (memory_id, uid)).rowcount


def delete_all(pool: ConnectionPool, user_id: int) -> int:
    uid = _uid(user_id)
    with pool.connection() as conn, conn.transaction():
        return conn.execute("DELETE FROM ai.memories WHERE user_id = %s", (uid,)).rowcount


def purge_checkpoints(pool: ConnectionPool, user_id: int) -> int:
    """Delete LangGraph checkpoints of this user's runs (the run's metadata carries user_id). Returns the number of threads removed."""
    uid = _uid(user_id)
    with pool.connection() as conn, conn.transaction():
        have = conn.execute("SELECT to_regclass('ai.checkpoints') AS t").fetchone()["t"]
        if not have:
            return 0
        rows = conn.execute("SELECT DISTINCT thread_id FROM ai.checkpoints WHERE metadata->>'user_id' = %s", (str(uid),)).fetchall()
        threads = [r["thread_id"] for r in rows]
        if threads:
            for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
                conn.execute(f"DELETE FROM ai.{table} WHERE thread_id = ANY(%s)", (threads,))   # fixed table names, parameterised ids
        return len(threads)


def purge_user(pool: ConnectionPool, user_id: int) -> dict[str, int]:
    return {"memories": delete_all(pool, user_id), "checkpoints": purge_checkpoints(pool, user_id)}
