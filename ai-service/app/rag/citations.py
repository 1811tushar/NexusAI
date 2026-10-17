"""Citation builder (AI-RG-04): turns retrieved chunks into EvidenceDTO-compatible objects for the Researcher (AI B)."""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from app.api.schemas import EvidenceDTO, EvidenceKind, EvidenceSource


def make_snippet(content: str, query: str | None = None, max_chars: int = 320) -> str:
    text = " ".join(content.split())
    if len(text) <= max_chars:
        return text
    start = 0
    if query:
        low = text.lower()
        positions = [low.find(t) for t in re.findall(r"[a-z0-9]{3,}", query.lower())]
        positions = [p for p in positions if p >= 0]
        if positions:
            start = max(0, min(positions) - max_chars // 4)
    if start:
        nxt = text.find(" ", start)
        start = nxt + 1 if 0 <= nxt < start + 40 else start
    end = min(len(text), start + max_chars)
    return ("..." if start else "") + text[start:end].strip() + ("..." if end < len(text) else "")


@dataclass(frozen=True)
class Citation:
    document_id: int
    document_title: str
    page: int | None
    section: str | None
    chunk_id: int
    snippet: str
    score: float     # quality in 0..1: cosine similarity when known, else the ranking score

    @property
    def label(self) -> str:
        loc = f", p.{self.page}" if self.page else ""
        return f"{self.document_title}{loc}"

    def to_evidence(self, evidence_key: str | None = None, created_at: str | None = None) -> EvidenceDTO:
        return EvidenceDTO(
            evidence_key=evidence_key or str(uuid.uuid4()),
            kind=EvidenceKind.DOCUMENT,
            title=self.label[:255],
            snippet=self.snippet,
            source=EvidenceSource(document_id=self.document_id, page=self.page),
            score=round(self.score, 4),
            created_at=created_at or datetime.now(UTC).isoformat(timespec="seconds"),
        )


def build_citations(chunks: list, query: str | None = None) -> list[Citation]:
    """`chunks`: list[RetrievedChunk] (duck-typed to avoid an import cycle)."""
    out = []
    for c in chunks:
        quality = c.similarity if getattr(c, "similarity", None) is not None else c.score
        out.append(Citation(c.document_id, c.document_title, c.page, c.section, c.chunk_id,
                            make_snippet(c.content, query), float(min(1.0, max(0.0, quality)))))
    return out
