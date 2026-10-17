"""confidence_check (AI-AG-08): PURE CODE, no LLM. overall >= CONFIDENCE_MIN -> ACCEPT; else LOOP while loop < maxLoops (focus = weakest claims);
at the cap -> ACCEPT_LOW_CONFIDENCE. A loop that found no new evidence stops early (no progress) instead of burning the remaining loops."""
from __future__ import annotations

from typing import Any

from app.agents import confidence as cf
from app.agents import events as ev
from app.agents.common import node
from app.agents.context import RunContext


@node("confidence_check")
def confidence_check(state: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    claims = state.get("claims", [])
    threshold = float(ctx.settings.confidence_min)
    loop, max_loops = int(state.get("loop", 0)), int(state.get("max_loops", ctx.settings.max_loops))
    overall = cf.overall_confidence(claims)
    decision = cf.decide(overall, threshold, loop, max_loops)
    if ctx.variant == "AGENT_NO_VERIFIER":
        decision = "ACCEPT"
    elif decision == "LOOP" and loop > 0 and len(state.get("evidence", [])) <= int(state.get("evidence_count_at_loop_start", 0)):
        decision = "ACCEPT_LOW_CONFIDENCE"          # stagnation: the last loop added no evidence
    ctx.emit(ev.confidence(overall, threshold, decision, loop))
    update: dict[str, Any] = {"overall_confidence": overall, "decision": decision, "low_confidence": decision == "ACCEPT_LOW_CONFIDENCE"}
    if decision == "LOOP":
        weak = cf.weakest_claims(claims, threshold)
        focus_txt = [f"{c['text'][:110]} ({c.get('status')}, {float(c.get('confidence') or 0):.2f})" for c in weak] or [state["question"][:140]]
        reason = f"Overall confidence {overall:.2f} is below {threshold:.2f}; looking for stronger evidence for {len(weak) or 'the'} weakest claim(s)."
        ctx.emit(ev.loop(loop + 1, max_loops, reason, focus_txt))
        update.update({"loop": loop + 1, "focus": [c["claimKey"] for c in weak], "evidence_count_at_loop_start": len(state.get("evidence", []))})
    return update
