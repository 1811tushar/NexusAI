"""Confidence model (AI-AG-07/08, contract section 9) as PURE functions: no I/O, no LLM. Unit tested branch by branch.

claim = 0.5*support + 0.3*agreement + 0.2*quality     agreement = min(1, independentSources/2)
quality = 1.0 for SQL/STATS, retrieval score (0..1) for DOCUMENT/WEB/MEMORY (mean over the cited evidence)
CONTRADICTED capped at 0.3, UNSUPPORTED capped at 0.4.  overall = weighted mean (key claims weight 2).
decision: overall >= threshold -> ACCEPT; else LOOP while loop < maxLoops; at the cap -> ACCEPT_LOW_CONFIDENCE."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any
from urllib.parse import urlparse

CAP_CONTRADICTED = 0.3
CAP_UNSUPPORTED = 0.4
W_SUPPORT, W_AGREEMENT, W_QUALITY = 0.5, 0.3, 0.2
MIN_SUPPORT_FOR_VERIFIED = 0.5


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def agreement(independent_sources: int) -> float:
    return min(1.0, max(0, independent_sources) / 2.0)


def source_id(ev: dict[str, Any]) -> str:
    """Identity of an evidence item for the 'independent source' count: distinct document, SQL result or web domain."""
    kind, src = ev.get("kind"), ev.get("source") or {}
    if kind == "DOCUMENT":
        return f"doc:{src.get('documentId')}"
    if kind == "WEB":
        return f"web:{urlparse(src.get('url') or '').netloc.lower() or ev.get('evidenceKey')}"
    if kind in ("SQL", "STATS"):
        return f"sql:{src.get('sql') or ev.get('evidenceKey')}"
    return f"{str(kind).lower()}:{src.get('investigationId') or ev.get('evidenceKey')}"


def independent_sources(evidence: Iterable[dict[str, Any]]) -> int:
    return len({source_id(e) for e in evidence})


def quality(evidence: Iterable[dict[str, Any]]) -> float:
    vals = [1.0 if e.get("kind") in ("SQL", "STATS") else clamp01(e.get("score") if e.get("score") is not None else 0.5) for e in evidence]
    return sum(vals) / len(vals) if vals else 0.0


def claim_confidence(support: float, n_sources: int, qual: float, status: str) -> float:
    c = W_SUPPORT * clamp01(support) + W_AGREEMENT * agreement(n_sources) + W_QUALITY * clamp01(qual)
    if status == "CONTRADICTED":
        c = min(c, CAP_CONTRADICTED)
    elif status == "UNSUPPORTED":
        c = min(c, CAP_UNSUPPORTED)
    return round(clamp01(c), 3)


def normalise_status(llm_status: str | None, support: float, has_evidence: bool) -> str:
    """Deterministic guard on the verifier's verdict: no evidence -> UNSUPPORTED; VERIFIED needs real support."""
    if not has_evidence:
        return "UNSUPPORTED"
    s = (llm_status or "").upper()
    if s == "CONTRADICTED":
        return "CONTRADICTED"
    if s == "VERIFIED" and support >= MIN_SUPPORT_FOR_VERIFIED:
        return "VERIFIED"
    return "UNSUPPORTED"


def overall_confidence(claims: Iterable[dict[str, Any]]) -> float:
    num = den = 0.0
    for c in claims:
        w = 2.0 if c.get("isKey") else 1.0
        num += w * float(c.get("confidence") or 0.0)
        den += w
    return round(num / den, 3) if den else 0.0


def decide(overall: float, threshold: float, loop: int, max_loops: int) -> str:
    if overall >= threshold:
        return "ACCEPT"
    return "LOOP" if loop < max_loops else "ACCEPT_LOW_CONFIDENCE"


def weakest_claims(claims: list[dict[str, Any]], threshold: float, n: int = 3) -> list[dict[str, Any]]:
    """Claims that hold the confidence down: not verified or below the threshold; key claims first, then lowest confidence."""
    weak = [c for c in claims if c.get("status") != "VERIFIED" or float(c.get("confidence") or 0) < threshold]
    weak.sort(key=lambda c: (not c.get("isKey"), float(c.get("confidence") or 0), c.get("claimKey", "")))
    return weak[:n]
