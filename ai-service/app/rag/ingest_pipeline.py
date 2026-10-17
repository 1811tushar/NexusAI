"""load -> clean -> chunk -> embed -> transactional upsert (AI-RG-01/02/03). Idempotent: re-ingesting replaces the old chunks.
Every expected failure is an IngestionError with a readable reason; nothing here hangs (deadline checked between stages)."""
from __future__ import annotations

import logging
import time

from app.api.schemas import IngestResponse
from app.core.config import Settings
from app.core.embeddings import Embedder
from app.rag.chunker import ChunkRecord, chunk_document
from app.rag.cleaner import clean_pages
from app.rag.errors import IngestionError
from app.rag.loader import load_document
from app.rag.vector_store import VectorStore

log = logging.getLogger(__name__)


def build_chunks(data: bytes, source_type: str, settings: Settings, *, chunking_mode: str | None = None,
                 deadline: float | None = None):
    """Load + clean + chunk only (no embedding, no DB). Returns (LoadedDocument, chunks)."""
    doc = load_document(data, source_type, max_pages=settings.max_pages, max_chars=settings.max_chars, deadline=deadline)
    doc.pages = clean_pages(doc.pages)
    if not any(p.text for p in doc.pages):
        raise IngestionError("The document contains no readable text after cleaning.")
    chunks = chunk_document(doc.pages, mode=chunking_mode or settings.chunking_mode,  # type: ignore[arg-type]
                            chunk_tokens=settings.chunk_tokens, overlap_tokens=settings.chunk_overlap_tokens)
    if not chunks:
        raise IngestionError("The document produced no text chunks.")
    if len(chunks) > settings.max_chunks_per_doc:
        raise IngestionError(f"The document is too large ({len(chunks)} chunks; limit {settings.max_chunks_per_doc}).")
    return doc, chunks


def ingest_document(
    *, store: VectorStore, embedder: Embedder, settings: Settings, document_id: int, source_type: str,
    title: str, filename: str, content: bytes, chunking_mode: str | None = None,
) -> IngestResponse:
    started = time.monotonic()
    deadline = started + settings.ingest_timeout_s
    doc, chunks = build_chunks(content, source_type, settings, chunking_mode=chunking_mode, deadline=deadline)
    if time.monotonic() > deadline:
        raise IngestionError("Ingestion took too long and was stopped. Try a smaller document.")
    try:
        embeddings: list[list[float]] = []
        for i in range(0, len(chunks), 64):   # batches; deadline checked between them
            embeddings += embedder.embed_documents([c.embed_text for c in chunks[i:i + 64]], batch_size=32)
            if time.monotonic() > deadline:
                raise IngestionError("Ingestion took too long and was stopped. Try a smaller document.")
    except IngestionError:
        raise
    except Exception as exc:  # noqa: BLE001
        log.error("embedding failed: %s", type(exc).__name__)
        raise IngestionError("Embedding the document failed. Try again later.") from exc

    meta = {"title": title, "filename": filename, "sourceType": source_type}
    store.replace_document(document_id, chunks, embeddings, meta)
    log.info("ingested document", extra={"documentId": document_id, "chunks": len(chunks), "pages": doc.page_count,
                                         "ms": int((time.monotonic() - started) * 1000)})
    return IngestResponse(document_id=document_id, page_count=doc.page_count, chunk_count=len(chunks), warnings=doc.warnings)


__all__ = ["ChunkRecord", "build_chunks", "ingest_document"]
