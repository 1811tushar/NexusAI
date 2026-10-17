"""Helpers shared by the nodes: context access, node wrapper (timing, usage, tracing, cancellation), evidence bookkeeping, prompt formatting."""
from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from typing import Any

from langchain_core.runnables import RunnableConfig

from app.agents import events as ev
from app.agents.context import RunContext
from app.agents.injection import wrap_untrusted
from app.api.schemas import EvidenceDTO
from app.core import observability
from app.core.pii import redact_text
from app.tools.registry import EvidenceDraft


def get_ctx(config: dict[str, Any]) -> RunContext:
    return config["configurable"]["ctx"]


def node(name: str) -> Callable[[Callable[[dict[str, Any], RunContext], dict[str, Any] | None]], Callable[[dict[str, Any], RunnableConfig], dict[str, Any]]]:
    """Wrap a node `fn(state, ctx) -> update`: cooperative cancel check, per-node timing (AI-AG-11), Langfuse span (AI-OB-01), token accounting."""
    def deco(fn: Callable[[dict[str, Any], RunContext], dict[str, Any] | None]) -> Callable[[dict[str, Any], RunnableConfig], dict[str, Any]]:
        def wrapper(state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
            ctx = get_ctx(config)
            ctx.check_cancel()
            t0 = time.perf_counter()
            with observability.span(f"node.{name}", investigationId=ctx.investigation_id):
                update = dict(fn(state, ctx) or {})
            ms = int((time.perf_counter() - t0) * 1000)
            ctx.log.info("node %s finished in %d ms", name)
            update["elapsed_ms"] = ms
            update["usage"] = ctx.take_usage()
            return update
        # LangGraph decides whether to pass `config` by inspecting the signature: keep the wrapper's own (state, config), not the wrapped fn's
        wrapper.__name__, wrapper.__doc__ = fn.__name__, fn.__doc__
        return wrapper
    return deco


def labels_of(evidence: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {f"E{i + 1}": e for i, e in enumerate(evidence)}


def label_of_key(evidence: list[dict[str, Any]]) -> dict[str, str]:
    return {e["evidenceKey"]: f"E{i + 1}" for i, e in enumerate(evidence)}


def _fingerprint(kind: str, source: dict[str, Any], snippet: str) -> str:
    return hashlib.sha256((kind + json.dumps(source, sort_keys=True, default=str) + snippet[:200]).encode()).hexdigest()


def add_evidence(ctx: RunContext, evidence: list[dict[str, Any]], draft: EvidenceDraft) -> dict[str, Any]:
    """Append (and emit evidence_added) unless an identical item already exists; returns the stored evidence dict."""
    source = {k: v for k, v in draft.source.items() if v is not None}
    fp = _fingerprint(draft.kind, source, draft.snippet)
    for e in evidence:
        if _fingerprint(e["kind"], e.get("source", {}), e["snippet"]) == fp:
            return e
    dto = EvidenceDTO.model_validate({"evidenceKey": ev.new_key(), "kind": draft.kind, "title": draft.title, "snippet": draft.snippet,
                                      "source": source, "data": draft.data, "chart": draft.chart, "score": draft.score, "createdAt": ev.now_iso()})
    wire = dto.wire()
    evidence.append(wire)
    ctx.emit(ev.evidence_added(wire))
    return wire


def evidence_block(evidence: list[dict[str, Any]], keys: list[str] | None = None, max_chars: int = 900) -> str:
    """Prompt text for evidence items, every item wrapped as untrusted data and labelled E<n>."""
    labels = label_of_key(evidence)
    parts = []
    for e in evidence:
        if keys is not None and e["evidenceKey"] not in keys:
            continue
        lab = labels[e["evidenceKey"]]
        body = f"({e['kind']}) {e['title']}\n{e['snippet'][:max_chars]}"
        parts.append(f"[{lab}]\n" + wrap_untrusted(body, f"{lab} {e['kind']}"))
    return "\n".join(parts) or "(no evidence)"


def safe_args(args: Any) -> dict[str, Any]:
    """Tool args for events/traces: PII-redacted strings, bounded size."""
    def clean(v: Any) -> Any:
        if isinstance(v, str):
            return redact_text(v)[:400]
        if isinstance(v, dict):
            return {str(k): clean(x) for k, x in list(v.items())[:12]}
        if isinstance(v, list):
            return [clean(x) for x in v[:12]]
        return v
    return clean(args) if isinstance(args, dict) else {}
