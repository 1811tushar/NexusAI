"""input_guard (ADD-GR-01): FIRST node. Deterministic rules decide clear cases; the LLM classifier only sees ambiguous ones (and fails OPEN: a failed
classifier never blocks a legitimate question, while the deterministic hard blocks and the no-write-tools design remain). Blocked -> guardrail_triggered
then the run ends REFUSED; nothing else runs."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.agents.common import node
from app.agents.context import RunContext
from app.agents.injection import InputVerdict, classify_input
from app.agents.prompts_loader import render
from app.agents.structured import call_structured
from app.core.pii import redact

_CATEGORIES = {"PROMPT_INJECTION", "OFF_TOPIC", "UNSAFE_REQUEST"}
_REASON = {"PROMPT_INJECTION": "The request tries to override the assistant's instructions.",
           "OFF_TOPIC": "The request is not about business analysis, so it was not run.",
           "UNSAFE_REQUEST": "The request asks for something the assistant must not do."}


class GuardOut(BaseModel):
    allowed: bool
    category: str | None = None
    reason: str = ""


@node("input_guard")
def input_guard(state: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    question = state["question"]
    red = redact(question)
    if red.total and ctx.settings.pii_redaction_enabled:
        ctx.guardrail("INPUT", "REDACTED", "PII", red.to_guardrail_detail() + " in the question; masked in traces, memory and web queries.")
    if not ctx.settings.guardrails_enabled:
        return {}
    verdict = classify_input(question)
    if verdict.verdict == "AMBIGUOUS":
        system, user = render("input_guard", question=question)
        out = call_structured(ctx, "input_guard", system, user, GuardOut, repair=False)
        if out is not None and not out.allowed:
            cat = out.category if out.category in _CATEGORIES else "OFF_TOPIC"
            verdict = InputVerdict("BLOCK", cat, out.reason or _REASON[cat])
        else:
            verdict = InputVerdict("ALLOW")
    if verdict.verdict == "BLOCK":
        cat = verdict.category or "UNSAFE_REQUEST"
        detail = verdict.detail or _REASON[cat]
        ctx.guardrail("INPUT", "BLOCKED", cat, detail)
        return {"refused": True, "status": "REFUSED", "refusal": {"category": cat, "detail": detail}}
    return {}
