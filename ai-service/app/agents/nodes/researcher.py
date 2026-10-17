"""researcher (AI-AG-04): ReAct tool loop over rag_search / web_search (only when allowed) / recall_memory; evidence with sources; bounded calls."""
from __future__ import annotations

from typing import Any

from app.agents import events as ev
from app.agents.common import node
from app.agents.context import RunContext
from app.agents.react import run_react_step


def run_agent_steps(state: dict[str, Any], ctx: RunContext, agent: str, prompt: str) -> dict[str, Any]:
    plan = [dict(s) for s in state.get("plan", [])]
    evidence = list(state.get("evidence", []))
    limitations: list[str] = []
    for step in plan:
        if step["agent"] != agent or step["status"] != "PENDING":
            continue
        ctx.check_cancel()
        ctx.emit(ev.agent_started(agent, step["id"]))
        ctx.emit(ev.step_status(step["id"], "RUNNING"))
        step["status"] = "RUNNING"
        status, lims = run_react_step(ctx, state, agent=agent, step=step, prompt=prompt, evidence=evidence)
        step["status"] = status
        limitations += lims
        ctx.emit(ev.step_status(step["id"], status))
    return {"plan": plan, "evidence": evidence, "limitations": limitations}


@node("researcher")
def researcher(state: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    return run_agent_steps(state, ctx, "RESEARCHER", "researcher")
