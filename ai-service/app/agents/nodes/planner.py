"""planner (AI-AG-03): ONE structured LLM call -> ordered sub-tasks, each owned by an allowed agent. On a loop it plans ONLY for the focus claims."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.agents import events as ev
from app.agents.common import node
from app.agents.context import RunContext
from app.agents.prompts_loader import render
from app.agents.structured import call_structured

MAX_STEPS = 5


class StepIn(BaseModel):
    description: str = Field(min_length=3, max_length=400)
    agent: Literal["RESEARCHER", "DATA_ANALYST"]


class PlanOut(BaseModel):
    steps: list[StepIn] = Field(min_length=1, max_length=8)


@node("planner")
def planner(state: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    ctx.emit(ev.agent_started("PLANNER"))
    allowed = state["route"]["agents"]
    loop = int(state.get("loop", 0))
    existing = [dict(s) for s in state.get("plan", [])]
    focus_keys = state.get("focus", [])
    focus = "\n".join(f"- {c['text']} (status {c.get('status')}, confidence {c.get('confidence')})" for c in state.get("claims", []) if c["claimKey"] in focus_keys)
    done = "\n".join(f"- {s['description']} [{s['status']}]" for s in existing) or "(none)"
    system, user = render("planner", now=state["now"], agents=", ".join(allowed), question=state["question"], focus=focus or "(none - first plan)", done_steps=done)
    out = call_structured(ctx, "planner", system, user, PlanOut)
    if out is None:
        new = [{"description": f"Find evidence relevant to: {state['question'][:200]}", "agent": a} for a in allowed]
    else:
        new = [{"description": s.description, "agent": s.agent if s.agent in allowed else allowed[0]} for s in out.steps[:MAX_STEPS]]
    prefix = "" if loop == 0 else f"l{loop}"
    plan = existing + [{"id": f"{prefix}s{i + 1}", "description": s["description"], "agent": s["agent"], "status": "PENDING"} for i, s in enumerate(new)]
    ctx.emit(ev.plan(plan))
    return {"plan": plan, "evidence_count_at_loop_start": len(state.get("evidence", []))}
