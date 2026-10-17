"""SINGLE_AGENT system (ADD-EV-02): ONE tool-calling ReAct agent with ALL tools (same tools, same SQL guard, same read-only role), then one answer call with
citations. No supervisor, no planner, no verifier, no confidence loop, no approval gate (it cannot propose actions), no input guardrail."""
from __future__ import annotations

import threading
import time
from typing import Any

from app.agents.common import evidence_block
from app.agents.context import FaultSpec
from app.agents.prompts_loader import render
from app.agents.react import run_react_step
from app.api.schemas import InvestigateOptions
from app.evals.metrics import RunRecord

MAX_CALLS = 10


def run_single_agent(env: Any, item: dict[str, Any]) -> RunRecord:
    rec = RunRecord(item["id"], item["category"], "SINGLE_AGENT")
    t0 = time.perf_counter()
    events: list[Any] = []
    faults = FaultSpec(tool_faults=dict(item["fault"])) if item.get("fault") else None
    opts = InvestigateOptions.model_validate({"webSearch": False, "useMemory": False, "maxLoops": 1, "documentIds": None})
    ctx = env.rt.make_ctx(user_id=900001, investigation_id=0, thread_id="single-agent", options=opts, now="2026-10-14T09:00:00Z", emit=events.append,
                          cancel=threading.Event(), faults=faults, single_agent=True)
    ctx.sleep = lambda s: None
    state = {"question": item["question"], "now": ctx.now}
    evidence: list[dict[str, Any]] = []
    step = {"id": "sa1", "description": item["question"], "agent": "ANALYST", "status": "RUNNING"}
    _status, lims = run_react_step(ctx, state, agent="ANALYST", step=step, prompt="single_agent", evidence=evidence, max_calls=MAX_CALLS, tag="single_agent")
    system, user = render("single_agent_answer", question=item["question"], evidence=evidence_block(evidence))
    reply = ctx.llm_call("single_agent_answer", system, user)
    rec.answer, rec.evidence = reply.text.strip(), evidence
    usage = ctx.take_usage()
    rec.in_tokens, rec.out_tokens = usage["inputTokens"], usage["outputTokens"]
    rec.event_types = [e.type for e in events]
    rec.notes["toolFailures"] = lims                         # NOT shown to the user: the single agent has no 'Limitations' section by design
    rec.latency_ms = int((time.perf_counter() - t0) * 1000)
    return rec
