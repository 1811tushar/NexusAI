"""supervisor (AI-AG-02): routes by question type (documents / data / both / web / direct) and records WHY. Trivial questions short-circuit to the reporter."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from app.agents import events as ev
from app.agents.common import node
from app.agents.context import RunContext
from app.agents.injection import wrap_untrusted
from app.agents.prompts_loader import render
from app.agents.structured import call_structured

ROUTE_AGENTS = {"documents": ["RESEARCHER"], "data": ["DATA_ANALYST"], "both": ["RESEARCHER", "DATA_ANALYST"], "web": ["RESEARCHER"], "direct": []}


class SupOut(BaseModel):
    route: Literal["documents", "data", "both", "web", "direct"]
    reason: str = ""


def web_allowed(ctx: RunContext) -> bool:
    return bool(ctx.options.web_search and ctx.settings.web_search_enabled)


@node("supervisor")
def supervisor(state: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    ctx.emit(ev.agent_started("SUPERVISOR"))
    mem = "\n".join(f"- {m['summary']}" for m in state.get("memories", []))
    system, user = render("supervisor", now=state["now"], web_allowed=str(web_allowed(ctx)).lower(), web_note=" and, if allowed, the web",
                          question=state["question"], memories=wrap_untrusted(mem, "memories") if mem else "(none)")
    out = call_structured(ctx, "supervisor", system, user, SupOut)
    if out is None:
        route, reason = "both", "Routing output was invalid, so both documents and data are used (safe default)."
    else:
        route, reason = out.route, out.reason or "No reason given."
    if route == "web" and not web_allowed(ctx):
        route, reason = "documents", reason + " (Web search is disabled, so company documents are used.)"
    agents = ROUTE_AGENTS[route]
    ctx.emit(ev.supervisor_routed(agents, reason))
    return {"route": {"route": route, "agents": agents, "reason": reason}, "trivial": route == "direct"}
