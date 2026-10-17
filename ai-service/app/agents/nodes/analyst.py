"""analyst (AI-AG-06): evidence -> discrete, checkable claims (isKey flagged, evidence keys). On a loop only the FOCUS claims are rewritten."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.agents import events as ev
from app.agents.common import evidence_block, labels_of, node
from app.agents.context import RunContext
from app.agents.prompts_loader import render
from app.agents.structured import call_structured

MAX_CLAIMS = 8


class ClaimIn(BaseModel):
    key: str | None = None
    text: str = Field(min_length=5, max_length=700)
    isKey: bool = False  # noqa: N815
    evidence: list[str] = []


class AnalystOut(BaseModel):
    claims: list[ClaimIn] = Field(max_length=12)


def _next_key(claims: list[dict[str, Any]]) -> str:
    nums = [int(c["claimKey"][1:]) for c in claims if c["claimKey"][1:].isdigit()]
    return f"c{(max(nums) + 1) if nums else 1}"


@node("analyst")
def analyst(state: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    ctx.emit(ev.agent_started("ANALYST"))
    evidence = state.get("evidence", [])
    claims = [dict(c) for c in state.get("claims", [])]
    focus_keys = state.get("focus", [])
    if not evidence:
        ctx.emit(ev.claims_drafted([]))
        return {"claims": claims}
    focus_claims = [c for c in claims if c["claimKey"] in focus_keys]
    focus_txt = "\n".join(f"{c['claimKey']}: {c['text']}" for c in focus_claims) or "(none - first pass)"
    system, user = render("analyst", question=state["question"], evidence=evidence_block(evidence), focus=focus_txt)
    out = call_structured(ctx, "analyst", system, user, AnalystOut)
    if out is None:
        return {"claims": claims, "limitations": ["The analysis step returned an invalid structure, so no new claims were formed from the evidence."]}
    labels = labels_of(evidence)
    changed: list[dict[str, Any]] = []
    for c in out.claims[:MAX_CLAIMS]:
        keys = [labels[x]["evidenceKey"] for x in dict.fromkeys(c.evidence) if x in labels]
        existing = next((x for x in claims if c.key and x["claimKey"] == c.key and c.key in focus_keys), None)
        new = {"claimKey": existing["claimKey"] if existing else _next_key(claims), "text": c.text.strip(), "isKey": bool(c.isKey), "evidenceKeys": keys}
        if existing:
            claims[claims.index(existing)] = new          # rewritten claim loses its old verification
        elif focus_keys and len(claims) >= MAX_CLAIMS:
            continue
        else:
            claims.append(new)
        changed.append(new)
    ctx.emit(ev.claims_drafted(changed))
    return {"claims": claims}
