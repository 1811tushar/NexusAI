"""Evaluation runtime: builds the same objects the service uses (pools, embedder, retriever, graph) for CLI runs, and ingests the synthetic corpus."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.agents.runtime import Runtime
from app.core.config import Settings
from app.core.db import detect_capabilities, ensure_ai_schema, open_ro_pool, open_rw_pool
from app.core.embeddings import load_embedder
from app.rag.ingest_pipeline import ingest_document
from app.rag.retriever import Retriever
from app.rag.vector_store import VectorStore

HERE = Path(__file__).parent
CORPUS_DIR = HERE / "corpus"
CORPUS_DOC_ID_BASE = 9_000_000          # ids 9_000_001.. are reserved for the evaluation corpus


@dataclass
class CorpusDoc:
    doc_id: int
    stem: str
    title: str
    filename: str
    source_type: str
    content: bytes


def corpus_documents() -> list[CorpusDoc]:
    docs = []
    for i, p in enumerate(sorted(CORPUS_DIR.iterdir()), start=1):
        if p.suffix.lower() not in (".md", ".txt"):
            continue
        raw = p.read_bytes()
        m = re.search(r"^#\s+(.+)$", raw.decode("utf-8"), re.M)
        docs.append(CorpusDoc(CORPUS_DOC_ID_BASE + i, p.stem, (m.group(1).strip() if m else p.stem)[:200], p.name, "MD" if p.suffix.lower() == ".md" else "TXT", raw))
    return docs


@dataclass
class EvalEnv:
    settings: Settings
    rw: Any
    ro: Any
    embedder: Any
    store: VectorStore
    retriever: Retriever
    caps: Any
    rt: Runtime

    def close(self) -> None:
        self.rw.close()
        self.ro.close()


def build_env(settings: Settings | None = None, *, llm: Any = None, embedder: Any = None, checkpointer: Any = None) -> EvalEnv:
    from langgraph.checkpoint.memory import MemorySaver
    s = settings or Settings()
    rw, ro = open_rw_pool(s), open_ro_pool(s)
    ensure_ai_schema(rw)
    caps = detect_capabilities(rw)
    emb = embedder or load_embedder(s)
    store = VectorStore(rw, caps)
    retriever = Retriever(store, emb, s)
    rt = Runtime(settings=s, embedder=emb, retriever=retriever, rw_pool=rw, ro_pool=ro, checkpointer=checkpointer or MemorySaver(), llm=llm)
    return EvalEnv(s, rw, ro, emb, store, retriever, caps, rt)


def ensure_corpus(env: EvalEnv) -> dict[int, str]:
    """Ingest (replace) the corpus into the production chunk table under reserved document ids. Returns {documentId: title}."""
    out = {}
    for d in corpus_documents():
        ingest_document(store=env.store, embedder=env.embedder, settings=env.settings, document_id=d.doc_id, source_type=d.source_type, title=d.title,
                        filename=d.filename, content=d.content)
        out[d.doc_id] = d.title
    return out


def business_data_present(env: EvalEnv) -> bool:
    try:
        with env.ro.connection() as c:
            return c.execute("SELECT count(*) AS n FROM sales").fetchone()["n"] > 0
    except Exception:  # noqa: BLE001
        return False
