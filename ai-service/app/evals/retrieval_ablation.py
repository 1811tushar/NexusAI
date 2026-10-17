"""Retrieval ablation (ADD-EV-03): python -m app.evals.retrieval_ablation [--reranker auto|real|fake|off] [--update-baseline] [--store]
Compares fixed-size vs semantic (heading-aware) chunking x VECTOR vs KEYWORD vs HYBRID(RRF) x reranker off/on on retrieval_set.json.
Needs NO LLM: only the embedding model and Postgres. Each chunking mode is ingested into its own scratch table (ai.eval_chunks_ablation_*), so
production chunks are never touched; the scratch tables are dropped afterwards.
hit@k: a query is a hit if one of the top-k chunks comes from the expected document AND contains one of the expected key phrases. MRR: mean 1/rank of the first hit."""
from __future__ import annotations

import argparse
import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.api.schemas import SearchMode
from app.core.config import Settings
from app.core.db import detect_capabilities, ensure_ai_schema, open_rw_pool
from app.core.embeddings import load_embedder
from app.evals import report as report_mod
from app.evals.runtime import corpus_documents
from app.rag.ingest_pipeline import ingest_document
from app.rag.retriever import Retriever
from app.rag.vector_store import VectorStore

HERE = Path(__file__).parent
KS = (1, 3, 5)
MODES = ("VECTOR", "KEYWORD", "HYBRID")
log = logging.getLogger("ablation")


class OverlapReranker:
    """Deterministic stand-in for the cross-encoder (token overlap). Used by tests and `--reranker fake`; NOT a quality claim about the real model."""

    def score(self, query: str, texts: list[str]) -> list[float]:
        q = set(re.findall(r"[a-z0-9]+", query.lower()))
        return [len(q & set(re.findall(r"[a-z0-9]+", t.lower()))) / (len(q) or 1) for t in texts]


def load_set(path: Path | None = None) -> list[dict[str, Any]]:
    return json.loads((path or HERE / "retrieval_set.json").read_text(encoding="utf-8"))


def evaluate(retriever: Retriever, items: list[dict[str, Any]], mode: str, rerank: bool) -> dict[str, Any]:
    ranks: list[int | None] = []
    for it in items:
        chunks = retriever.search(it["question"], mode=SearchMode(mode), k=max(KS), rerank=rerank)
        rank = None
        for i, c in enumerate(chunks, start=1):
            if c.document_title == it["expectedDocument"] and any(p.lower() in c.content.lower() for p in it["mustContain"]):
                rank = i
                break
        ranks.append(rank)
    n = len(items) or 1
    out: dict[str, Any] = {f"hit{k}": round(sum(1 for r in ranks if r and r <= k) / n, 3) for k in KS}
    out["mrr"] = round(sum(1 / r for r in ranks if r) / n, 3)
    for style in ("lexical", "paraphrase"):
        idx = [i for i, it in enumerate(items) if it["style"] == style]
        out[f"hit5_{style}"] = round(sum(1 for i in idx if ranks[i] and ranks[i] <= 5) / (len(idx) or 1), 3)
    out["ranks"] = ranks
    return out


def run_ablation(settings: Settings, rw_pool: Any, caps: Any, embedder: Any, *, items: list[dict[str, Any]] | None = None, reranker: Any = None,
                 rerank_modes: tuple[bool, ...] = (False, True)) -> list[dict[str, Any]]:
    items = items or load_set()
    docs = corpus_documents()
    cfg = settings.model_copy(update={"retrieval_per_doc_cap": 100})          # no diversity cap: compare retrieval itself
    rows: list[dict[str, Any]] = []
    for chunking in ("fixed", "semantic"):
        store = VectorStore.create_scratch(rw_pool, caps, f"ablation_{chunking}")
        try:
            n_chunks = 0
            for d in docs:
                ingest_document(store=store, embedder=embedder, settings=cfg, document_id=d.doc_id, source_type=d.source_type, title=d.stem, filename=d.filename,
                                content=d.content, chunking_mode=chunking)
            n_chunks = store.count()
            retriever = Retriever(store, embedder, cfg, reranker=reranker)
            for mode in MODES:
                for rr in rerank_modes:
                    row = {"chunking": chunking, "mode": mode, "rerank": "on" if rr else "off", "chunks": n_chunks}
                    try:
                        row.update(evaluate(retriever, items, mode, rr))
                    except Exception as exc:  # noqa: BLE001  e.g. reranker model cannot be downloaded
                        row["skipped"] = f"{type(exc).__name__}: {str(exc)[:120]}"
                    rows.append(row)
        finally:
            store.drop()
    return rows


def key(row: dict[str, Any]) -> str:
    return f"{row['chunking']}|{row['mode']}|{row['rerank']}"


def store_rows(rw_pool: Any, rows: list[dict[str, Any]], items: list[dict[str, Any]], settings: Settings) -> None:
    for r in rows:
        if "skipped" in r:
            continue
        results = [{"questionId": it["id"], "category": "NORMAL", "question": it["question"], "expectedFacts": [it["expectedDocument"]],
                    "answer": f"first hit at rank {rank}" if rank else "no hit in top 5", "correct": bool(rank and rank <= 5), "groundedShare": 0.0,
                    "hallucinated": False, "latencyMs": 0} for it, rank in zip(items, r["ranks"], strict=True)]
        metrics = {"answerCorrectness": 0.0, "groundedClaimsShare": 0.0, "hallucinationRate": 0.0, "avgLatencyMs": 0.0, "avgTokens": 0.0, "approvalGateCompliance": None,
                   "retrievalHitRate": r["hit5"], "citationValidity": None, "guardrailBlockRate": None, "failureRecoveryRate": None}
        cfg = {"kind": "retrieval", "k": 5, "mrr": r["mrr"], "hit1": r["hit1"], "hit3": r["hit3"], "embeddingModel": settings.embedding_model, "chunks": r["chunks"]}
        with rw_pool.connection() as c:
            c.execute("INSERT INTO ai.eval_runs (system, variant, config, metrics, results) VALUES ('BASELINE', %s, %s::jsonb, %s::jsonb, %s::jsonb)",
                      (f"chunking={r['chunking']};mode={r['mode']};rerank={r['rerank']}", json.dumps(cfg), json.dumps(metrics), json.dumps(results)))
            c.commit()


def update_baseline(rows: list[dict[str, Any]], embedder_name: str, path: Path | None = None) -> Path:
    p = path or HERE / "baseline_metrics.json"
    data = json.loads(p.read_text()) if p.exists() else {}
    data[embedder_name] = {"k": 5, "recordedAt": datetime.now(UTC).strftime("%Y-%m-%d"), "questions": len(load_set()),
                           "variants": {key(r): {"hit5": r["hit5"], "mrr": r["mrr"]} for r in rows if "skipped" not in r}}
    p.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return p


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app.evals.retrieval_ablation")
    ap.add_argument("--reranker", default="auto", choices=["auto", "real", "fake", "off"])
    ap.add_argument("--update-baseline", action="store_true")
    ap.add_argument("--store", action="store_true", help="store each variant as an ai.eval_runs row for the dashboard")
    ap.add_argument("--out", default=str(HERE / "results"))
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    settings = Settings()
    rw = open_rw_pool(settings)
    try:
        ensure_ai_schema(rw)
        caps = detect_capabilities(rw)
        embedder = load_embedder(settings)
        reranker = OverlapReranker() if args.reranker == "fake" else None
        modes = (False,) if args.reranker == "off" else (False, True)
        items = load_set()
        rows = run_ablation(settings, rw, caps, embedder, items=items, reranker=reranker, rerank_modes=modes)
        ok = [r for r in rows if "skipped" not in r]
        print(f"Embedding model: {settings.embedding_model} | questions: {len(items)} | variants measured: {len(ok)}/{len(rows)}")
        print(report_mod.render_ablation(ok))
        for r in rows:
            if "skipped" in r:
                print(f"SKIPPED {key(r)}: {r['skipped']}")
        if settings.embedding_model == "hashing":
            print("NOTE: the hashing embedder is lexical only; VECTOR results are NOT a quality claim. Re-run with the real BGE model for reportable numbers.")
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        (out / f"ablation-{stamp}.json").write_text(json.dumps({"embeddingModel": settings.embedding_model, "rows": rows}, indent=2), encoding="utf-8")
        if args.update_baseline:
            print("Baseline updated:", update_baseline(rows, settings.embedding_model))
        if args.store:
            store_rows(rw, rows, items, settings)
        return 0
    finally:
        rw.close()


if __name__ == "__main__":
    raise SystemExit(main())
