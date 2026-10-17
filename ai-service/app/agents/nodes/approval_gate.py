"""approval_gate (AI-HL-01/02): emits approval_required for ALL pending HIGH-risk proposals, then interrupt(): the run is checkpointed (Postgres) and survives a
restart. On resume (Spring sends the stored decisions) the node continues; nothing is emitted twice (ctx.resuming). A missing decision is treated as REJECT:
nothing is ever approved implicitly. Rejected actions are remembered so they are never re-proposed in this run. Python executes nothing."""
from __future__ import annotations

from typing import Any

from langgraph.types import interrupt

from app.agents import events as ev
from app.agents.common import node
from app.agents.context import RunContext
from app.api.schemas import ActionProposed
from app.tools.action_catalogue import fingerprint


def normalise_decisions(raw: Any, pending: list[dict[str, Any]]) -> list[dict[str, Any]]:
    given: dict[str, dict[str, Any]] = {}
    items = raw.get("decisions", []) if isinstance(raw, dict) else (raw if isinstance(raw, list) else [])
    for d in items:
        if isinstance(d, dict) and d.get("actionKey"):
            given[str(d["actionKey"])] = d
    out = []
    for a in pending:
        d = given.get(a["actionKey"])
        approved = bool(d) and str(d.get("decision", "")).upper() == "APPROVE"
        out.append({"actionKey": a["actionKey"], "actionType": a["actionType"], "title": a["title"], "approvalId": (d or {}).get("approvalId"),
                    "decision": "APPROVE" if approved else "REJECT", "decidedBy": (d or {}).get("decidedBy"),
                    "comment": (d or {}).get("comment") if d else "No decision was received; treated as rejected."})
    return out


@node("approval_gate")
def approval_gate(state: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    pending = [a for a in state.get("proposed_actions", []) if a["actionKey"] in state.get("pending_high", [])]
    if not ctx.resuming:
        ctx.emit(ev.approval_required([ActionProposed.model_validate({k: v for k, v in a.items() if not k.startswith("_")}) for a in pending]))
    raw = interrupt({"waitingFor": [a["actionKey"] for a in pending]})
    decisions = normalise_decisions(raw, pending)
    rejected = list(state.get("rejected_actions", []))
    for d, a in zip(decisions, pending, strict=True):
        if d["decision"] == "REJECT":
            rejected.append({"fingerprint": fingerprint(a["actionType"], a["params"]), "type": a["actionType"], "params": a["params"]})
    return {"decisions": decisions, "rejected_actions": rejected, "pending_high": []}
