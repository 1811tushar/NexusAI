"""Embedder interface, loaded once (AI-FD-04). BGE-small, 384-d, normalised, batch encode."""
from __future__ import annotations

import hashlib
import logging
import re
from typing import Protocol

import numpy as np

from app.core.config import Settings

log = logging.getLogger(__name__)
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class Embedder(Protocol):
    name: str
    dimension: int

    def embed_documents(self, texts: list[str], batch_size: int = 32) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str, dimension: int = 384) -> None:
        from sentence_transformers import SentenceTransformer  # heavy import, only when really used

        self.name = model_name
        self._model = SentenceTransformer(model_name, device="cpu")
        self._model.max_seq_length = 512
        got = self._model.get_sentence_embedding_dimension()
        if got != dimension:
            raise RuntimeError(f"Embedding model {model_name} has {got} dims, schema expects {dimension}")
        self.dimension = dimension
        self._is_bge = "bge" in model_name.lower()

    def embed_documents(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        if not texts:
            return []
        arr = self._model.encode(texts, batch_size=batch_size, normalize_embeddings=True, show_progress_bar=False)
        return arr.astype(np.float32).tolist()

    def embed_query(self, text: str) -> list[float]:
        t = BGE_QUERY_PREFIX + text if self._is_bge else text
        return self._model.encode([t], normalize_embeddings=True, show_progress_bar=False)[0].astype(np.float32).tolist()


class HashingEmbedder:
    """Deterministic bag-of-words hashing embedder. NO semantics, only lexical overlap.
    For unit tests and the LLM-free CI gate; never use for quality numbers you report."""

    name = "hashing"

    def __init__(self, dimension: int = 384) -> None:
        self.dimension = dimension

    def _vec(self, text: str) -> list[float]:
        v = np.zeros(self.dimension, dtype=np.float32)
        for tok in re.findall(r"[a-z0-9]+", text.lower()):
            h = int.from_bytes(hashlib.blake2b(tok.encode(), digest_size=8).digest(), "big")
            v[h % self.dimension] += 1.0 if (h >> 63) & 1 else -1.0
        n = float(np.linalg.norm(v))
        return (v / n if n else v).tolist()

    def embed_documents(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)


def load_embedder(settings: Settings) -> Embedder:
    if settings.embedding_model == "hashing":
        log.warning("Using the hashing test embedder (no semantics)")
        return HashingEmbedder(settings.embedding_dim)
    log.info("Loading embedding model %s", settings.embedding_model)
    return SentenceTransformerEmbedder(settings.embedding_model, settings.embedding_dim)
