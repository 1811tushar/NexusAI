"""verifier (AI-AG-07): per claim, support score from ONE structured LLM call (Pydantic JSON, one repair retry) + agreement + quality -> status/confidence by
contract section 9. Deterministic guards: no evidence -> UNSUPPORTED; VERIFIED needs support >= 0.5; CONTRADICTED capped 0.3, UNSUPPORTED capped 0.4.
Only claims without a verdict are (re)verified, so a loop does not redo finished work."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.agents import confidence as cf
from app.agents import events as ev
from app.agents.common import evidence_block, node
from app.agents.context import RunContext
from app.agents.prompts_loader import render
from app.agents.structured import call_structured


class VerOut(BaseModel):
    support: float = Field(ge=0, le=1)
    status: Literal["VERIFIED", "UNSUPPORTED", "CONTRADICTED"]
    reason: str = ""


@node("verifier")
def verifier(state: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    ctx.emit(ev.agent_started("VERIFIER"))
    evidence = state.get("evidence", [])
    by_key = {e["evidenceKey"]: e for e in evidence}
    claims = [dict(c) for c in state.get("claims", [])]
    for c in claims:
        if c.get("status"):
            continue
        ctx.check_cancel()
        cited = [by_key[k] for k in c["evidenceKeys"] if k in by_key]
        if ctx.variant == "AGENT_NO_VERIFIER":
            support, status, reason = 1.0, ("VERIFIED" if cited else "UNSUPPORTED"), "Verification skipped (evaluation variant without verifier)."
        elif not cited:
            support, status, reason = 0.0, "UNSUPPORTED", "No evidence is cited for this claim."
        else:
            system, user = render("verifier", claim=c["text"], evidence=evidence_block(evidence, [e["evidenceKey"] for e in cited]))
            out = call_structured(ctx, "verifier", system, user, VerOut)
            if out is None:
                support, status, reason = 0.0, "UNSUPPORTED", "The verification result was invalid, so the claim is treated as unsupported."
            else:
                support, reason = out.support, out.reason
                status = cf.normalise_status(out.status, support, True)
        c["support"] = round(support, 3)
        c["status"] = status
        c["confidence"] = cf.claim_confidence(support, cf.independent_sources(cited), cf.quality(cited), status)
        c["reason"] = reason
        ctx.emit(ev.claim_verified(c))
    return {"claims": claims}
