"""recall_memory tool (AI-TL-04): the CURRENT user's own past-investigation summaries only (user_id comes from the run context, never from the agent)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from app.agents.injection import wrap_untrusted
from app.memory import long_term
from app.tools.registry import EvidenceDraft, ToolResult

if TYPE_CHECKING:
    from app.agents.context import RunContext


class MemArgs(BaseModel):
    query: str = Field(min_length=3, max_length=300)


def recall_memory(ctx: RunContext, args: MemArgs) -> ToolResult:
    hits = long_term.recall(ctx.rw_pool, ctx.embedder, ctx.user_id, args.query)
    ev = [EvidenceDraft("MEMORY", f"Earlier investigation #{h.source_investigation_id or h.id}", h.summary,
                        {"investigationId": h.source_investigation_id}, score=round(h.relevance, 4)) for h in hits]
    obs = wrap_untrusted("\n".join(f"- {h.summary}" for h in hits) or "(no relevant memories)", "recall_memory")
    return ToolResult(f"{len(hits)} memor{'y' if len(hits) == 1 else 'ies'} recalled", obs, ev)
