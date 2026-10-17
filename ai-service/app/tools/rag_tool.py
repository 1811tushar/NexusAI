"""rag_search tool (AI-TL-04): wraps AI A's Retriever. Returns chunks as DOCUMENT evidence + a wrapped observation. Document scope from the run options is
ENFORCED here (the agent cannot widen it). Retrieved text is untrusted data; injection-looking chunks are flagged (TOOL/FLAGGED/PROMPT_INJECTION)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from app.agents.injection import looks_like_injection, wrap_untrusted
from app.api.schemas import SearchMode
from app.rag.citations import make_snippet
from app.tools.registry import EvidenceDraft, ToolError, ToolResult

if TYPE_CHECKING:
    from app.agents.context import RunContext


class RagArgs(BaseModel):
    query: str = Field(min_length=3, max_length=300)
    mode: SearchMode = SearchMode.HYBRID
    k: int = Field(5, ge=1, le=10)


def rag_search(ctx: RunContext, args: RagArgs) -> ToolResult:
    fault = ctx.faults.take("rag_search") if ctx.faults else None
    if fault == "timeout":
        raise ToolError("Document search timed out.", transient=True)
    if fault in ("error", "vector_failure"):
        raise ToolError("Document search failed (vector index unavailable).")
    chunks = [] if fault == "empty" else ctx.retriever.search(args.query, mode=args.mode, k=args.k, document_ids=ctx.document_ids)
    if not chunks:
        return ToolResult("0 passages found", wrap_untrusted("(no matching passages)", "rag_search"), [])
    ev: list[EvidenceDraft] = []
    obs_parts: list[str] = []
    for c in chunks:
        if looks_like_injection(c.content) and c.chunk_id not in ctx.flagged_chunks:
            ctx.flagged_chunks.add(c.chunk_id)
            ctx.guardrail("TOOL", "FLAGGED", "PROMPT_INJECTION", f"A retrieved passage from '{c.document_title}' contains instruction-like text; it is treated as data only.")
        quality = c.similarity if c.similarity is not None else c.score
        where = f"{c.document_title}" + (f", p.{c.page}" if c.page else "") + (f" - {c.section}" if c.section else "")
        ev.append(EvidenceDraft("DOCUMENT", where[:250], make_snippet(c.content, args.query, 900),
                                {"documentId": c.document_id, "page": c.page}, score=round(max(0.0, min(1.0, float(quality))), 4)))
        obs_parts.append(f"[{where}]\n{make_snippet(c.content, args.query, 700)}")
    return ToolResult(f"{len(chunks)} passage(s) from {len({c.document_id for c in chunks})} document(s)",
                      wrap_untrusted("\n\n".join(obs_parts), "rag_search results"), ev)
