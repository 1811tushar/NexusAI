"""recall_memory node (AI-ME-02): top-5 of THIS user's memories by relevance + recency + importance; emits memory_recalled. Never fatal."""
from __future__ import annotations

from typing import Any

from app.agents import events as ev
from app.agents.common import node
from app.agents.context import RunContext
from app.core.pii import redact_text
from app.memory import long_term


@node("recall_memory")
def recall_memory_node(state: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    if not ctx.options.use_memory:
        return {"memories": []}
    try:
        hits = long_term.recall(ctx.rw_pool, ctx.embedder, ctx.user_id, redact_text(state["question"]))
    except Exception as exc:  # noqa: BLE001  memory is a helper, not a dependency
        ctx.log.warning("memory recall failed: %s", type(exc).__name__)
        ctx.emit(ev.memory_recalled([]))
        return {"memories": [], "limitations": ["Long-term memory was unavailable for this run."]}
    items = [{"id": h.id, "summary": h.summary, "score": h.score} for h in hits]
    ctx.emit(ev.memory_recalled(items))
    return {"memories": items}
