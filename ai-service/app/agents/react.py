"""Shared ReAct loop (literature: ReAct) used by the Researcher and the Data Analyst: the agent decides the next tool call as JSON, the code validates and
executes it under the uniform failure policy (agents/failure.py), the observation (wrapped as untrusted data) goes back into the next prompt."""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel

from app.agents import events as ev
from app.agents.common import add_evidence, safe_args
from app.agents.context import RunContext
from app.agents.failure import backoff_delay
from app.agents.prompts_loader import render
from app.agents.structured import call_structured
from app.tools.registry import EvidenceDraft, ToolError

MAX_CALLS_PER_STEP = 4


class ReactAction(BaseModel):
    action: Literal["call", "finish"]
    tool: str | None = None
    args: dict[str, Any] = {}
    summary: str | None = None


@dataclass
class Outcome:
    ok: bool
    observation: str
    drafts: list[EvidenceDraft] = field(default_factory=list)


def execute_tool_call(ctx: RunContext, agent: str, step_id: str, tool: str, args: dict[str, Any]) -> Outcome:
    """One logical tool call: tool_call event -> execute (timeout, budget, validation) -> transient retries with backoff -> tool_result event."""
    call_id = str(uuid.uuid4())
    ctx.emit(ev.tool_call(call_id, agent, tool, safe_args(args)))
    t0 = time.perf_counter()
    while True:
        ctx.check_cancel()
        try:
            res = ctx.tools.execute(ctx, agent, tool, args)
            ctx.emit(ev.tool_result(call_id, tool, True, res.summary, int((time.perf_counter() - t0) * 1000)))
            return Outcome(True, res.observation, res.evidence)
        except ToolError as exc:
            n = ctx.failures.record(step_id, tool, exc.reason)
            if exc.transient and n < ctx.failures.max_attempts:
                ctx.sleep(backoff_delay(n))
                continue
            ctx.emit(ev.tool_result(call_id, tool, False, exc.reason, int((time.perf_counter() - t0) * 1000)))
            return Outcome(False, f"ERROR: {exc.reason}")


def run_react_step(ctx: RunContext, state: dict[str, Any], *, agent: str, step: dict[str, Any], prompt: str, evidence: list[dict[str, Any]],
                   max_calls: int = MAX_CALLS_PER_STEP, tag: str | None = None) -> tuple[str, list[str]]:
    """Runs one plan step. Mutates `evidence` (appending new items). Returns (status DONE|FAILED, limitations)."""
    limitations: list[str] = []
    observations: list[str] = []
    made = successes = 0
    stopped_on_failure = False
    ok_tools: set[str] = set()
    bad_tools: list[str] = []
    while made < max_calls:
        ctx.check_cancel()
        system, user = render(prompt, tools=ctx.tools.registry.describe_for(agent), now=state["now"], question=state["question"],
                              step=step["description"], remaining=max_calls - made,
                              observations="\n".join(observations) or "(none yet)")
        action = call_structured(ctx, tag or agent.lower(), system, user, ReactAction)
        if action is None:
            limitations.append(f"{agent.title().replace('_', ' ')} could not produce a valid tool call for '{step['description'][:80]}'.")
            break
        if action.action == "finish":
            break
        if not action.tool:
            observations.append("ERROR: 'tool' is required when action is 'call'.")
            made += 1
            continue
        out = execute_tool_call(ctx, agent, step["id"], action.tool, action.args)
        made += 1
        observations.append(f"call {made}: {action.tool}({json.dumps(safe_args(action.args), default=str)[:300]}) -> {out.observation}")
        if out.ok:
            successes += 1
            ok_tools.add(action.tool)
            for d in out.drafts:
                add_evidence(ctx, evidence, d)
        else:
            bad_tools.append(action.tool)
        if not out.ok and ctx.failures.exhausted(step["id"], action.tool):
            limitations.append(ctx.failures.explanation(step["id"], action.tool, f"Could not complete '{step['description'][:90]}'"))
            stopped_on_failure = True
            break
    for tool in dict.fromkeys(bad_tools):          # a failure that was never recovered must not vanish (ADD-FH-02), even if the agent gave up early
        if tool not in ok_tools and not any(f"'{tool}' tool failed" in x for x in limitations):
            limitations.append(ctx.failures.explanation(step["id"], tool, f"Could not complete '{step['description'][:90]}'"))
    if made >= max_calls and successes == 0 and not stopped_on_failure and not limitations:
        limitations.append(f"No usable result was obtained for '{step['description'][:90]}' within the call limit.")
    status = "FAILED" if (successes == 0 and limitations) else "DONE"
    return status, limitations
