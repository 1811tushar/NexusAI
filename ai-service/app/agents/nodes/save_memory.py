"""save_memory (AI-ME-02, ADD-GR-02): after completion, a concise factual summary of the VERIFIED findings is embedded into ai.memories for THIS user.
Skipped if useMemory=false, for trivial/refused runs, or when nothing was verified. The summary is PII-redacted and secret-stripped before storage;
near-duplicates are merged (cosine >= 0.92). Failure here never fails the run."""
from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from app.agents import events as ev
from app.agents.common import node
from app.agents.context import RunContext
from app.agents.prompts_loader import render
from app.agents.structured import call_structured
from app.core.pii import redact
from app.memory import long_term
from app.memory.scoring import importance_for

_SECRET = re.compile(r"(sk-[A-Za-z0-9_\-]{16,}|AIza[0-9A-Za-z_\-]{20,}|(?:api[_-]?key|password|secret|token)\s*[:=]\s*\S+|Bearer\s+[A-Za-z0-9._\-]{16,})", re.I)


class MemOut(BaseModel):
    summary: str = Field(min_length=10, max_length=600)


def sanitise_memory(text: str) -> tuple[str, int]:
    """Redact PII and strip secrets. Returns (clean text <= 500 chars, number of redactions)."""
    red = redact(text)
    clean, n_secret = _SECRET.subn("[REDACTED_SECRET]", red.text)
    return re.sub(r"\s+", " ", clean).strip()[:500], red.total + n_secret


@node("save_memory")
def save_memory(state: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    verified = [c for c in state.get("claims", []) if c.get("status") == "VERIFIED"]
    if not ctx.options.use_memory or state.get("trivial") or not verified:
        return {}
    try:
        system, user = render("memory_summary", question=redact(state["question"]).text, confidence=f"{float(state.get('overall_confidence') or 0):.2f}",
                              verified="\n".join(f"- {c['text']}" for c in verified[:6]))
        out = call_structured(ctx, "memory_summary", system, user, MemOut)
        text = out.summary if out else f"Q: {state['question'][:150]} Verified: " + "; ".join(c["text"] for c in verified[:2])
        clean, n = sanitise_memory(text)
        if n:
            ctx.guardrail("OUTPUT", "REDACTED", "PII", f"Redacted {n} sensitive value(s) from the memory summary before storing it.")
        importance = importance_for(state.get("overall_confidence"), len(verified), len(state.get("claims", [])))
        mid, _dup = long_term.save(ctx.rw_pool, ctx.embedder, ctx.user_id, clean, investigation_id=ctx.investigation_id, importance=importance)
        ctx.emit(ev.memory_saved(mid, clean))
    except Exception as exc:  # noqa: BLE001
        if type(exc).__name__ in ("LlmRateLimited", "LlmUnavailable"):
            ctx.log.warning("memory not saved: %s", type(exc).__name__)
        else:
            ctx.log.warning("memory not saved: %s", type(exc).__name__)
    return {}
