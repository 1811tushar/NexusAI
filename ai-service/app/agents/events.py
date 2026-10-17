"""Event builders: every function returns an AgentEvent built from the contract payload models of api/schemas.py (AI-AG-10),
so a malformed payload cannot be produced (pydantic raises). Spring-originated events (run_started, approval_decided, action_executed) are not built here."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.api import schemas as s
from app.api.schemas import AgentEvent


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def memory_recalled(items: list[dict[str, Any]]) -> AgentEvent:
    return AgentEvent.of(s.MemoryRecalled(items=[s.MemoryItem(**i) for i in items]))


def supervisor_routed(agents: list[str], reason: str) -> AgentEvent:
    return AgentEvent.of(s.SupervisorRouted(agents=agents, reason=reason[:500]))  # type: ignore[arg-type]


def plan(steps: list[dict[str, Any]]) -> AgentEvent:
    return AgentEvent.of(s.PlanEvent(steps=[s.PlanStep(id=p["id"], description=p["description"], agent=p["agent"], status=p["status"]) for p in steps]))


def step_status(step_id: str, status: str) -> AgentEvent:
    return AgentEvent.of(s.StepStatusEvent(step_id=step_id, status=status))  # type: ignore[arg-type]


def agent_started(agent: str, step_id: str | None = None) -> AgentEvent:
    return AgentEvent.of(s.AgentStarted(agent=agent, step_id=step_id))  # type: ignore[arg-type]


def tool_call(call_id: str, agent: str, tool: str, args: dict[str, Any]) -> AgentEvent:
    return AgentEvent.of(s.ToolCall(call_id=call_id, agent=agent, tool=tool, args=args))  # type: ignore[arg-type]


def tool_result(call_id: str, tool: str, ok: bool, summary: str, duration_ms: int) -> AgentEvent:
    return AgentEvent.of(s.ToolResult(call_id=call_id, tool=tool, ok=ok, summary=summary[:300], duration_ms=duration_ms))  # type: ignore[arg-type]


def evidence_added(evidence: dict[str, Any]) -> AgentEvent:
    return AgentEvent.of(s.EvidenceAdded(evidence=s.EvidenceDTO.model_validate(evidence)))


def claims_drafted(claims: list[dict[str, Any]]) -> AgentEvent:
    return AgentEvent.of(s.ClaimsDrafted(claims=[s.DraftClaim(claim_key=c["claimKey"], text=c["text"], is_key=c["isKey"],
                                                              evidence_keys=c["evidenceKeys"]) for c in claims]))


def claim_verified(c: dict[str, Any]) -> AgentEvent:
    return AgentEvent.of(s.ClaimVerified(claim_key=c["claimKey"], text=c["text"], status=c["status"], confidence=c["confidence"],
                                         evidence_keys=c["evidenceKeys"], reason=str(c.get("reason", ""))[:500]))


def confidence(overall: float, threshold: float, decision: str, loop: int) -> AgentEvent:
    return AgentEvent.of(s.ConfidenceEvent(overall=overall, threshold=threshold, decision=decision, loop=loop))  # type: ignore[arg-type]


def loop(loop_no: int, max_loops: int, reason: str, focus: list[str]) -> AgentEvent:
    return AgentEvent.of(s.LoopEvent(loop=loop_no, max_loops=max_loops, reason=reason[:500], focus=focus))


def action_proposed(a: s.ActionProposed) -> AgentEvent:
    return AgentEvent.of(a)


def approval_required(actions: list[s.ActionProposed]) -> AgentEvent:
    return AgentEvent.of(s.ApprovalRequired(actions=actions))


def guardrail(stage: str, action: str, category: str, detail: str) -> AgentEvent:
    return AgentEvent.of(s.GuardrailTriggered(stage=stage, action=action, category=category, detail=detail[:400]))  # type: ignore[arg-type]


def report_delta(text: str) -> AgentEvent:
    return AgentEvent.of(s.ReportDelta(text=text))


def report_ready(markdown: str, summary: str, recommendations: list[dict[str, Any]], confidence_value: float) -> AgentEvent:
    return AgentEvent.of(s.ReportReady(report_markdown=markdown, summary=summary[:1000],
                                       recommendations=[s.RecommendationDTO(id=r["id"], text=r["text"], risk=r["risk"], action_key=r.get("actionKey")) for r in recommendations],
                                       confidence=max(0.0, min(1.0, confidence_value))))


def memory_saved(memory_id: int, summary: str) -> AgentEvent:
    return AgentEvent.of(s.MemorySaved(id=memory_id, summary=summary))


def error(code: str, message: str, retryable: bool) -> AgentEvent:
    return AgentEvent.of(s.ErrorEvent(code=code, message=message[:500], retryable=retryable))  # type: ignore[arg-type]


def done(status: str, confidence_value: float | None, loops_used: int, input_tokens: int, output_tokens: int, latency_ms: int) -> AgentEvent:
    return AgentEvent.of(s.Done(status=status, confidence=confidence_value, loops_used=loops_used,  # type: ignore[arg-type]
                                usage=s.UsageTokens(input_tokens=input_tokens, output_tokens=output_tokens), latency_ms=latency_ms))


def new_key() -> str:
    return str(uuid.uuid4())
