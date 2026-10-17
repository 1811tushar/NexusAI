"""Ingestion + hybrid retrieval against a real pgvector Postgres (hashing embedder: lexical, deterministic)."""
import pytest

from app.api.schemas import SearchMode
from app.rag.citations import build_citations
from app.rag.ingest_pipeline import ingest_document
from app.rag.retriever import Retriever, rrf_fuse
from app.rag.vector_store import VectorStore, to_or_tsquery

REPORT = ("# Q2 2026 Revenue Report\n\n## Summary\n\nRevenue declined 12 percent in Q2 compared to Q1, mainly driven by the "
          "South region.\n\n## Supplier incident\n\nA supplier incident delayed shipments in the South region for six weeks.")
PRICING = ("# Pricing Policy\n\n## Approvals\n\nAny price change above 10 percent requires manager approval before it "
           "takes effect. Discounts below 5 percent are automatic.")
MARKETING = ("# Marketing Plan\n\n## West campaign\n\nThe campaign budget for the West region is flat. Email spend "
             "stays constant while social spend grows.")


def ingest(store, embedder, settings, doc_id, text, title, mode=None, **kw):
    return ingest_document(store=store, embedder=embedder, settings=settings, document_id=doc_id, source_type="MD",
                           title=title, filename=f"{title}.md", content=text.encode(), chunking_mode=mode, **kw)


@pytest.fixture
def corpus(store, embedder, settings):
    ingest(store, embedder, settings, 1, REPORT, "Quarterly Report")
    ingest(store, embedder, settings, 2, PRICING, "Pricing Policy")
    ingest(store, embedder, settings, 3, MARKETING, "Marketing Plan")


def test_rrf_math_and_ordering():
    s = rrf_fuse([[1, 2, 3], [3, 1, 4]])
    assert s[1] == pytest.approx(1 / 61 + 1 / 62) and s[3] == pytest.approx(1 / 63 + 1 / 61)
    assert [k for k, _ in sorted(s.items(), key=lambda x: -x[1])] == [1, 3, 2, 4]


def test_or_tsquery_is_injection_safe():
    assert to_or_tsquery("Why did Q2 revenue decline?") == "why | did | q2 | revenue | decline"
    assert to_or_tsquery("'; DROP TABLE x; -- & | ! ( )") == "drop | table | x"
    assert to_or_tsquery("?!?") is None


@pytest.mark.parametrize("mode", ["HYBRID", "VECTOR", "KEYWORD"])
def test_top_hit_is_the_right_document_in_every_mode(corpus, retriever, mode):
    top = retriever.search("why did revenue decline in the south region", mode=mode, k=3)[0]
    assert top.document_id == 1 and top.document_title == "Quarterly Report"
    top = retriever.search("price change approval", mode=mode, k=3)[0]
    assert top.document_id == 2


def test_hybrid_scores_and_sources(corpus, retriever):
    hits = retriever.search("supplier incident shipments south", k=5)
    assert hits[0].score <= 1.0 and all(0 <= h.score <= 1 for h in hits)
    assert [h.score for h in hits] == sorted((h.score for h in hits), reverse=True)
    assert set(hits[0].sources) == {"vector", "keyword"} and hits[0].score == pytest.approx(1.0)
    assert all(h.similarity is not None for h in hits)          # keyword-only hits get an exact cosine too


def test_document_scope_is_respected_in_all_modes(corpus, retriever):
    for mode in ("HYBRID", "VECTOR", "KEYWORD"):
        hits = retriever.search("revenue budget price approval", mode=mode, k=10, document_ids=[3])
        assert hits and {h.document_id for h in hits} == {3}
    assert retriever.search("revenue", k=10, document_ids=[999]) == []


def test_empty_and_nonsense_queries(corpus, retriever):
    assert retriever.search("?!?", mode="KEYWORD") == []
    assert isinstance(retriever.search("zzzzqqqq", mode=SearchMode.HYBRID), list)


def test_per_document_cap_gives_diversity(store, embedder, settings, retriever):
    big = "# Big\n\n" + "\n\n".join(f"## Part {i}\n\n" + ("revenue growth analysis detail " * 60) for i in range(8))
    ingest(store, embedder, settings, 10, big, "Big")
    ingest(store, embedder, settings, 11, "# Small\n\nRevenue note with revenue growth analysis detail.", "Small")
    capped = retriever.search("revenue growth analysis", k=6)
    assert sum(h.document_id == 10 for h in capped) <= settings.retrieval_per_doc_cap and any(h.document_id == 11 for h in capped)
    uncapped = retriever.search("revenue growth analysis", k=6, per_doc_cap=None)
    assert sum(h.document_id == 10 for h in uncapped) > settings.retrieval_per_doc_cap


def test_reingest_replaces_chunks_idempotently(store, embedder, settings, retriever):
    r1 = ingest(store, embedder, settings, 20, "# V1\n\nThis text mentions alphaunique only.", "Doc")
    ids_before = {r["id"] for r in store.list_chunks(20, 0, 100)[0]}
    assert retriever.search("alphaunique", mode="KEYWORD")
    r2 = ingest(store, embedder, settings, 20, "# V2\n\nCompletely different words betauniq here. " * 3, "Doc")
    rows, total = store.list_chunks(20, 0, 100)
    assert total == r2.chunk_count == store.count(20) and r1.chunk_count >= 1
    assert [r["chunk_index"] for r in rows] == list(range(total))
    assert not ({r["id"] for r in rows} & ids_before)
    assert retriever.search("alphaunique", mode="KEYWORD") == [] and retriever.search("betauniq", mode="KEYWORD")
    ingest(store, embedder, settings, 20, "# V2\n\nCompletely different words betauniq here. " * 3, "Doc")   # same input twice
    assert store.count(20) == total


def test_failed_reingest_keeps_old_chunks(store, embedder, settings):
    ingest(store, embedder, settings, 21, "# Keep\n\nKeep this content safe.", "Keep")
    n = store.count(21)
    from app.rag.errors import IngestionError
    with pytest.raises(IngestionError):
        ingest_document(store=store, embedder=embedder, settings=settings, document_id=21, source_type="PDF",
                        title="x", filename="x.pdf", content=b"%PDF-1.4 broken")
    assert store.count(21) == n


def test_delete_and_paged_listing(store, embedder, settings):
    long_doc = "# Long\n\n" + "\n\n".join(f"## Part {i}\n\n" + ("detail words about revenue " * 80) for i in range(4))
    ingest(store, embedder, settings, 30, long_doc, "Long")
    rows, total = store.list_chunks(30, 0, 1)
    assert len(rows) == 1 and total >= 4
    assert [r["chunk_index"] for r in store.list_chunks(30, 1, 2)[0]] == [2, 3]
    assert store.list_chunks(30, 99, 10)[0] == []
    assert store.delete_document(30) == total and store.count(30) == 0 and store.delete_document(30) == 0


def test_transaction_rolls_back_on_bad_embedding(store, embedder, settings):
    ingest(store, embedder, settings, 22, "# T\n\nOriginal content stays.", "T")
    from app.rag.chunker import ChunkRecord
    with pytest.raises(Exception):  # noqa: B017  wrong dimension -> DB error mid-transaction
        store.replace_document(22, [ChunkRecord(0, None, None, "new", {})], [[0.1] * 3])
    assert store.count(22) >= 1 and "Original" in store.list_chunks(22, 0, 5)[0][0]["content"]


class FakeReranker:
    def score(self, query, texts):
        return [0.99 if "supplier" in t.lower() else 0.1 for t in texts]


def test_reranker_hook_reorders_without_llm(corpus, store, embedder, settings):
    r = Retriever(store, embedder, settings, reranker=FakeReranker())
    hits = r.search("south region", k=3, rerank=True)
    assert "supplier" in hits[0].content.lower() and hits[0].rerank_score == pytest.approx(0.99)
    assert r.search("south region", k=3, rerank=False)[0].rerank_score is None


def test_chunking_ablation_on_scratch_tables_without_llm(pools, caps, store, embedder, settings):
    """Retrieval variants (fixed vs semantic) run side by side in scratch tables; production chunks are untouched."""
    sem = VectorStore.create_scratch(pools[0], caps, "abl_sem")
    fix = VectorStore.create_scratch(pools[0], caps, "abl_fix")
    try:
        for st, mode in ((sem, "semantic"), (fix, "fixed")):
            ingest_document(store=st, embedder=embedder, settings=settings, document_id=1, source_type="MD", title="Report",
                            filename="r.md", content=REPORT.encode(), chunking_mode=mode)
        assert sem.count() and fix.count() and store.count() == 0
        a = Retriever(sem, embedder, settings).search("supplier incident", k=1)[0]
        b = Retriever(fix, embedder, settings).search("supplier incident", k=1)[0]
        assert a.section and b.section is None
    finally:
        sem.drop(); fix.drop()  # noqa: E702
    with pytest.raises(ValueError):
        store.drop()
    with pytest.raises(ValueError):
        VectorStore(pools[0], caps, "ai.x; DROP TABLE users")


def test_citations_are_evidence_compatible(corpus, retriever):
    hits = retriever.search("supplier incident", k=2)
    cits = build_citations(hits, "supplier incident")
    ev = cits[0].to_evidence()
    assert ev.kind.value == "DOCUMENT" and ev.source.document_id == hits[0].document_id
    assert ev.title.startswith("Quarterly Report") and 0 <= ev.score <= 1 and ev.wire()["evidenceKey"]
    assert cits[0].score == pytest.approx(hits[0].similarity, abs=1e-3)
