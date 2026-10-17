"""Optional cross-encoder reranker behind RERANKER_ENABLED (AI-RG-06). Lazy-loaded, CPU-friendly small model."""
from __future__ import annotations

import logging
import math
import threading
from typing import Protocol

from app.core.config import Settings

log = logging.getLogger(__name__)


class Reranker(Protocol):
    def score(self, query: str, texts: list[str]) -> list[float]:
        """Relevance probabilities in 0..1, same order as `texts`."""


class CrossEncoderReranker:
    def __init__(self, model_name: str) -> None:
        from sentence_transformers import CrossEncoder

        log.info("Loading reranker %s", model_name)
        self._model = CrossEncoder(model_name, device="cpu", max_length=512)

    def score(self, query: str, texts: list[str]) -> list[float]:
        if not texts:
            return []
        logits = self._model.predict([(query, t) for t in texts], show_progress_bar=False)
        return [1.0 / (1.0 + math.exp(-float(x))) for x in logits]


_lock = threading.Lock()
_instance: Reranker | None = None


def get_reranker(settings: Settings) -> Reranker:
    global _instance
    with _lock:
        if _instance is None:
            _instance = CrossEncoderReranker(settings.reranker_model)
        return _instance
