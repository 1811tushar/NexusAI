"""Hybrid retrieval (AI-RG-04/05/06): pgvector cosine + Postgres full-text merged with Reciprocal Rank Fusion (k=60).
Modes HYBRID / VECTOR / KEYWORD, optional document scope, per-document diversity cap, optional cross-encoder rerank.
`search()` takes mode/rerank/k per call and needs NO LLM, so evaluation (AI B) can run ablations offline."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.api.schemas import SearchMode
from app.core.config import Settings
from app.core.embeddings import Embedder
from app.rag.reranker import Reranker, get_reranker
from app.rag.vector_store import ChunkHit, VectorStore

RRF_K = 60


@dataclass
class RetrievedChunk:
    chunk_id: int
    document_id: int
    document_title: str
    chunk_index: int
    page: int | None
    section: str | None
    content: str
    score: float                    # 0..1 ranking score of the chosen mode (HYBRID: RRF normalised so rank-1-in-both = 1.0)
    similarity: float | None = None  # exact cosine similarity (0..1) when known: use this as evidence "quality"
    sources: tuple[str, ...] = field(default_factory=tuple)   # which retrievers found it: "vector", "keyword"
    rerank_score: float | None = None


def rrf_fuse(rankings: list[list[int]], k: int = RRF_K) -> dict[int, float]:
    """Reciprocal Rank Fusion: score(d) = sum over rankings of 1 / (k + rank), rank starting at 1."""
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    return scores


class Retriever:
    def __init__(self, store: VectorStore, embedder: Embedder, settings: Settings, reranker: Reranker | None = None) -> None:
        self.store, self.embedder, self.settings, self._reranker = store, embedder, settings, reranker

    def search(
        self,
        query: str,
        *,
        mode: SearchMode | str = SearchMode.HYBRID,
        k: int | None = None,
        document_ids: list[int] | None = None,
        rerank: bool | None = None,
        per_doc_cap: int | None = -1,   # -1 = default from settings; None = no cap
    ) -> list[RetrievedChunk]:
        mode = SearchMode(mode)
        k = k or self.settings.top_k
        rerank = self.settings.reranker_enabled if rerank is None else rerank
        docs = document_ids or None
        if per_doc_cap == -1:
            per_doc_cap = None if (docs and len(docs) == 1) else self.settings.retrieval_per_doc_cap
        n = max(k * 3, 30) if rerank else max(k * 4, 20)

        qvec = self.embedder.embed_query(query) if mode != SearchMode.KEYWORD else None
        vec_hits = self.store.vector_search(qvec, n, docs) if qvec is not None else []
        kw_hits = self.store.keyword_search(query, n, docs) if mode != SearchMode.VECTOR else []

        by_id: dict[int, ChunkHit] = {h.chunk_id: h for h in [*kw_hits, *vec_hits]}
        sim: dict[int, float] = {h.chunk_id: h.score for h in vec_hits}
        in_vec, in_kw = {h.chunk_id for h in vec_hits}, {h.chunk_id for h in kw_hits}

        if mode == SearchMode.VECTOR:
            ordered = [(h.chunk_id, h.score) for h in vec_hits]
        elif mode == SearchMode.KEYWORD:
            ordered = [(h.chunk_id, h.score) for h in kw_hits]
        else:
            fused = rrf_fuse([[h.chunk_id for h in vec_hits], [h.chunk_id for h in kw_hits]])
            top = 2.0 / (RRF_K + 1)
            ordered = sorted(((cid, s / top) for cid, s in fused.items()), key=lambda x: (-x[1], x[0]))

        missing = [cid for cid, _ in ordered if cid not in sim] if qvec is not None else []
        if missing:
            sim.update(self.store.similarities(qvec, missing))

        chunks = [
            RetrievedChunk(
                h.chunk_id, h.document_id, h.document_title, h.chunk_index, h.page, h.section, h.content,
                float(score), sim.get(cid),
                tuple(s for s, present in (("vector", cid in in_vec), ("keyword", cid in in_kw)) if present),
            )
            for cid, score in ordered
            for h in (by_id[cid],)
        ]

        if rerank and chunks:
            reranker = self._reranker or get_reranker(self.settings)
            scores = reranker.score(query, [c.content for c in chunks])
            for c, s in zip(chunks, scores, strict=True):
                c.rerank_score, c.score = s, s
            chunks.sort(key=lambda c: (-c.score, c.chunk_id))

        return _apply_cap(chunks, per_doc_cap, k)


def _apply_cap(chunks: list[RetrievedChunk], cap: int | None, k: int) -> list[RetrievedChunk]:
    if cap is None:
        return chunks[:k]
    counts: dict[int, int] = {}
    out: list[RetrievedChunk] = []
    for c in chunks:
        if counts.get(c.document_id, 0) >= cap:
            continue
        counts[c.document_id] = counts.get(c.document_id, 0) + 1
        out.append(c)
        if len(out) == k:
            break
    return out
