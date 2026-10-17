"""action_planning (AI-TL-05, AI-HL-03, ADD-GR-04): the LLM may propose actions ONLY from the catalogue. CODE assigns risk from the catalogue (any LLM risk is
ignored), validates params with Pydantic, drops invalid/duplicate/previously-rejected proposals. LOW -> action_proposed (Spring auto-executes, simulated).
HIGH -> collected in `pending_high`; they are NOT emitted as action_proposed, they only leave through approval_required after the approval gate."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.agents import events as ev
from app.agents.common import evidence_block, label_of_key, labels_of, node
from app.agents.context import RunContext
from app.agents.prompts_loader import render
from app.agents.structured import call_structured
from app.api.schemas import Risk
from app.tools.action_catalogue import ActionRejected, catalogue_text, fingerprint, validate_proposal

MAX_ACTIONS = 3
MAX_RECS = 4


class RecIn(BaseModel):
    text: str = Field(min_length=3, max_length=500)
    action: dict[str, Any] | None = None


class ActOut(BaseModel):
    recommendations: list[RecIn] = Field(max_length=8)


@node("action_planning")
def action_planning(state: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    verified = [c for c in state.get("claims", []) if c.get("status") == "VERIFIED"]
    if state.get("trivial") or not verified:
        return {"recommendations": [], "pending_high": [], "proposed_actions": state.get("proposed_actions", [])}
    evidence = state.get("evidence", [])
    labels, lab_of = labels_of(evidence), label_of_key(evidence)
    rejected = state.get("rejected_actions", [])
    ver_txt = "\n".join(f"- {c['text']} [{', '.join(lab_of[k] for k in c['evidenceKeys'] if k in lab_of)}]" for c in verified)
    system, user = render("action_planning", catalogue=catalogue_text(), question=state["question"], verified=ver_txt,
                          rejected=", ".join(f"{r['type']} {r['params']}" for r in rejected) or "none")
    out = call_structured(ctx, "action_planning", system, user, ActOut)
    recs: list[dict[str, Any]] = []
    proposed = list(state.get("proposed_actions", []))
    seen = {r["fingerprint"] for r in rejected} | {a["_fp"] for a in proposed if "_fp" in a}
    pending: list[str] = []
    n_actions = 0
    for i, r in enumerate((out.recommendations if out else [])[:MAX_RECS], start=1):
        rec = {"id": f"r{i}", "text": r.text.strip(), "risk": "LOW", "actionKey": None}
        if r.action is not None and n_actions < MAX_ACTIONS:
            try:
                prop = validate_proposal(r.action, rationale_default=r.text)
            except ActionRejected as exc:
                ctx.guardrail("OUTPUT", "FLAGGED", "INVALID_OUTPUT", f"A proposed action was dropped: {exc.reason}"[:300])
                recs.append(rec)
                continue
            fp = fingerprint(prop.action_type.value, prop.params)
            if fp in seen:
                recs.append(rec)
                continue
            seen.add(fp)
            raw_labels = r.action.get("evidence") or []
            prop.evidence_keys = [labels[x]["evidenceKey"] for x in raw_labels if isinstance(x, str) and x in labels]
            wire = prop.wire()
            wire["_fp"] = fp
            proposed.append(wire)
            rec.update({"risk": prop.risk.value, "actionKey": prop.action_key, "actionType": prop.action_type.value})
            n_actions += 1
            if prop.risk == Risk.LOW:
                ctx.emit(ev.action_proposed(prop))
            else:
                pending.append(prop.action_key)
        recs.append(rec)
    _ = evidence_block  # (kept for symmetry with other nodes)
    return {"recommendations": recs, "proposed_actions": proposed, "pending_high": pending}
