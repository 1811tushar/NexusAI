"""Action catalogue (AI-TL-05, contract section 8). Risk is FIXED here by action type; any risk the LLM supplies is ignored.
Params are validated by Pydantic; Spring validates again and executes (simulated). Python never executes an action."""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Any

from pydantic import Field, ValidationError, field_validator, model_validator

from app.api.schemas import ActionProposed, ActionType, CamelModel, Risk, Role


class FlagForReview(CamelModel):
    subject: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=500)


class CreateFollowupTask(CamelModel):
    title: str = Field(min_length=1, max_length=200)
    owner_role: Role
    due_in_days: int = Field(ge=1, le=90)


class SaveInsight(CamelModel):
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=2000)


class AdjustPrice(CamelModel):
    product_id: int = Field(ge=1)
    change_pct: float

    @field_validator("change_pct")
    @classmethod
    def _bounded(cls, v: float) -> float:
        if v == 0 or abs(v) > 30:
            raise ValueError("changePct must be non-zero and |changePct| <= 30")
        return v


class PauseCampaign(CamelModel):
    region_id: int = Field(ge=1)
    channel: str = Field(min_length=1, max_length=30)
    weeks: int = Field(ge=1, le=26)


class ReallocateBudget(CamelModel):
    from_region_id: int = Field(ge=1)
    to_region_id: int = Field(ge=1)
    amount: float = Field(gt=0)

    @model_validator(mode="after")
    def _different(self) -> ReallocateBudget:
        if self.from_region_id == self.to_region_id:
            raise ValueError("fromRegionId and toRegionId must differ")
        return self


@dataclass(frozen=True)
class ActionSpec:
    risk: Risk
    params_model: type[CamelModel]
    label: str


CATALOGUE: dict[ActionType, ActionSpec] = {
    ActionType.FLAG_FOR_REVIEW: ActionSpec(Risk.LOW, FlagForReview, "Flag for review"),
    ActionType.CREATE_FOLLOWUP_TASK: ActionSpec(Risk.LOW, CreateFollowupTask, "Create follow-up task"),
    ActionType.SAVE_INSIGHT: ActionSpec(Risk.LOW, SaveInsight, "Save insight"),
    ActionType.ADJUST_PRICE: ActionSpec(Risk.HIGH, AdjustPrice, "Adjust price"),
    ActionType.PAUSE_CAMPAIGN: ActionSpec(Risk.HIGH, PauseCampaign, "Pause campaign"),
    ActionType.REALLOCATE_BUDGET: ActionSpec(Risk.HIGH, ReallocateBudget, "Reallocate budget"),
}
assert set(CATALOGUE) == set(ActionType), "every ActionType must be in the catalogue"


class ActionRejected(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def risk_of(action_type: ActionType) -> Risk:
    return CATALOGUE[action_type].risk


def fingerprint(action_type: str, params: dict[str, Any]) -> str:
    """Stable id of (type, params): used to make sure a rejected action is never re-proposed in the same run."""
    return hashlib.sha256((action_type + json.dumps(params, sort_keys=True, default=str)).encode()).hexdigest()[:16]


def validate_proposal(raw: Any, *, rationale_default: str = "") -> ActionProposed:
    """Validate an LLM-supplied proposal. Returns the contract `ActionProposed` payload with risk taken from the catalogue.
    Raises ActionRejected (readable reason) for unknown types / invalid params. A `risk` field in `raw` is IGNORED."""
    if not isinstance(raw, dict):
        raise ActionRejected("proposal is not an object")
    try:
        atype = ActionType(str(raw.get("type") or raw.get("actionType") or "").strip().upper())
    except ValueError as exc:
        raise ActionRejected(f"unknown action type '{raw.get('type') or raw.get('actionType')}'") from exc
    spec = CATALOGUE[atype]
    try:
        params = spec.params_model.model_validate(raw.get("params") or {})
    except ValidationError as exc:
        msg = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()[:3])
        raise ActionRejected(f"invalid params for {atype.value}: {msg}") from exc
    wire = params.wire()
    rationale = str(raw.get("rationale") or rationale_default or "Recommended based on the verified findings.")[:600]
    title = str(raw.get("title") or spec.label)[:200]
    description = str(raw.get("description") or f"{spec.label}: {json.dumps(wire, sort_keys=True)}")[:1000]
    return ActionProposed(action_key=str(uuid.uuid4()), action_type=atype, risk=spec.risk, title=title, description=description,
                          params=wire, rationale=rationale, evidence_keys=[])


def catalogue_text() -> str:
    """Prompt-ready description of the catalogue (generated from the models, so prompt and validation cannot drift). Risk is NOT shown."""
    lines = []
    for atype, spec in CATALOGUE.items():
        fields = ", ".join(f"{(f.alias or name)}: {getattr(f.annotation, '__name__', str(f.annotation))}" for name, f in spec.params_model.model_fields.items())
        lines.append(f"- {atype.value}: params {{{fields}}}")
    return "\n".join(lines)
