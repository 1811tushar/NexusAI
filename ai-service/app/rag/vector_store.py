"""Postgres/pgvector storage + the two raw search paths (AI-RG-02/04). All SQL is parameterised; the only interpolated
value is the table name, which is validated against a strict pattern. `table` is configurable so the retrieval
ablation (AI B) can index the same corpus under different chunking modes in scratch tables WITHOUT touching production chunks."""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
from psycopg_pool import ConnectionPool

from app.core.db import Capabilities
from app.rag.chunker import ChunkRecord

DEFAULT_TABLE = "ai.document_chunks"
_TABLE_RE = re.compile(r"^ai\.[a-z_][a-z0-9_]{0,40}$")
_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


@dataclass
class ChunkHit:
    chunk_id: int
    document_id: int
    document_title: str
    chunk_index: int
    page: int | None
    section: str | None
    content: str
    score: float   # raw: cosine similarity (vector) or normalised ts_rank_cd (keyword)


def to_or_tsquery(query: str, max_terms: int = 24) -> str | None:
    """'Why did Q2 revenue decline?' -> 'why | did | q2 | revenue | decline'. Alphanumerics only, so it can never be a syntax error."""
    seen: list[str] = []
    for t in _TOKEN_RE.findall(query.lower()):
        if t not in seen:
            seen.append(t)
    return " | ".join(seen[:max_terms]) or None


class VectorStore:
    def __init__(self, pool: ConnectionPool, caps: Capabilities, table: str = DEFAULT_TABLE) -> None:
        if not _TABLE_RE.match(table):
            raise ValueError(f"Invalid table name: {table!r}")
        self.pool, self.caps, self.table = pool, caps, table

    # ------------------------------------------------------------------ scratch tables (ablation / eval)
    @classmethod
    def create_scratch(cls, pool: ConnectionPool, caps: Capabilities, name: str) -> VectorStore:
        table = f"ai.eval_chunks_{name}"
        store = cls(pool, caps, table)
        with pool.connection() as conn:
            conn.execute(f"DROP TABLE IF EXISTS {table}")
            conn.execute(f"CREATE TABLE {table} (LIKE {DEFAULT_TABLE} INCLUDING ALL)")   # copies indexes + generated tsv
            conn.commit()
        return store

    def drop(self) -> None:
        if self.table == DEFAULT_TABLE:
            raise ValueError("refusing to drop the production chunk table")
        with self.pool.connection() as conn:
            conn.execute(f"DROP TABLE IF EXISTS {self.table}")
            conn.commit()

    # ------------------------------------------------------------------ writes
    def replace_document(self, document_id: int, chunks: list[ChunkRecord], embeddings: list[list[float]],
                         base_metadata: dict | None = None) -> int:
        """Delete old chunks and insert new ones in ONE transaction (idempotent re-ingest). Serialised per document."""
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings differ in length")
        import json

        rows = [
            (document_id, c.chunk_index, c.page, c.section, c.content, np.asarray(e, dtype=np.float32),
             json.dumps({**(base_metadata or {}), **c.metadata}))
            for c, e in zip(chunks, embeddings, strict=True)
        ]
        with self.pool.connection() as conn, conn.transaction():
            conn.execute("SELECT pg_advisory_xact_lock(%s)", (document_id,))
            conn.execute(f"DELETE FROM {self.table} WHERE document_id = %s", (document_id,))
            with conn.cursor() as cur:
                cur.executemany(
                    f"INSERT INTO {self.table} (document_id, chunk_index, page, section, content, embedding, metadata) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)", rows)
        return len(rows)

    def delete_document(self, document_id: int) -> int:
        with self.pool.connection() as conn, conn.transaction():
            cur = conn.execute(f"DELETE FROM {self.table} WHERE document_id = %s", (document_id,))
            return cur.rowcount

    # ------------------------------------------------------------------ reads
    def list_chunks(self, document_id: int, page: int, size: int) -> tuple[list[dict], int]:
        with self.pool.connection() as conn:
            total = conn.execute(f"SELECT count(*) AS n FROM {self.table} WHERE document_id = %s", (document_id,)).fetchone()["n"]
            rows = conn.execute(
                f"SELECT id, chunk_index, page, section, content FROM {self.table} WHERE document_id = %s "
                "ORDER BY chunk_index LIMIT %s OFFSET %s", (document_id, size, page * size)).fetchall()
        return rows, total

    def count(self, document_id: int | None = None) -> int:
        with self.pool.connection() as conn:
            if document_id is None:
                return conn.execute(f"SELECT count(*) AS n FROM {self.table}").fetchone()["n"]
            return conn.execute(f"SELECT count(*) AS n FROM {self.table} WHERE document_id = %s", (document_id,)).fetchone()["n"]

    def vector_search(self, qvec: list[float], limit: int, document_ids: list[int] | None = None) -> list[ChunkHit]:
        """Cosine nearest neighbours. With a document scope the HNSW index filters AFTER the scan, so:
        pgvector >= 0.8 -> hnsw.iterative_scan=relaxed_order; older -> over-fetch (10x, max 1000) and trim."""
        scoped = bool(document_ids)
        inner = limit
        if scoped and not self.caps.iterative_scan:
            inner = min(max(limit * 10, 100), 1000)
        q = np.asarray(qvec, dtype=np.float32)
        sql = (
            "WITH r AS MATERIALIZED ("
            "  SELECT id, document_id, chunk_index, page, section, content, metadata->>'title' AS title, "
            "         embedding <=> %(q)s AS dist "
            f"  FROM {self.table} "
            "  WHERE (%(docs)s::bigint[] IS NULL OR document_id = ANY(%(docs)s::bigint[])) "
            "  ORDER BY embedding <=> %(q)s LIMIT %(inner)s) "
            "SELECT * FROM r ORDER BY dist LIMIT %(k)s"
        )
        with self.pool.connection() as conn, conn.transaction():
            conn.execute("SELECT set_config('hnsw.ef_search', %s, true)", (str(min(1000, max(40, inner))),))
            if scoped and self.caps.iterative_scan:
                conn.execute("SELECT set_config('hnsw.iterative_scan', 'relaxed_order', true)")
            rows = conn.execute(sql, {"q": q, "docs": document_ids if scoped else None, "inner": inner, "k": limit}).fetchall()
        return [_hit(r, max(0.0, 1.0 - float(r["dist"]))) for r in rows]

    def keyword_search(self, query: str, limit: int, document_ids: list[int] | None = None) -> list[ChunkHit]:
        tsq = to_or_tsquery(query)
        if not tsq:
            return []
        sql = (
            "SELECT id, document_id, chunk_index, page, section, content, metadata->>'title' AS title, "
            "       ts_rank_cd(tsv, q, 32) AS rank "
            f"FROM {self.table}, to_tsquery('english', %(tsq)s) q "
            "WHERE tsv @@ q AND (%(docs)s::bigint[] IS NULL OR document_id = ANY(%(docs)s::bigint[])) "
            "ORDER BY rank DESC, id LIMIT %(k)s"
        )
        with self.pool.connection() as conn:
            rows = conn.execute(sql, {"tsq": tsq, "docs": document_ids or None, "k": limit}).fetchall()
        return [_hit(r, float(r["rank"])) for r in rows]

    def similarities(self, qvec: list[float], chunk_ids: list[int]) -> dict[int, float]:
        """Exact cosine similarity for given chunks (used to give keyword-only hits a comparable quality value)."""
        if not chunk_ids:
            return {}
        with self.pool.connection() as conn:
            rows = conn.execute(
                f"SELECT id, 1 - (embedding <=> %s) AS sim FROM {self.table} WHERE id = ANY(%s)",
                (np.asarray(qvec, dtype=np.float32), chunk_ids)).fetchall()
        return {r["id"]: max(0.0, float(r["sim"])) for r in rows}


def _hit(r: dict, score: float) -> ChunkHit:
    return ChunkHit(r["id"], r["document_id"], r["title"] or f"Document {r['document_id']}", r["chunk_index"],
                    r["page"], r["section"], r["content"], score)
