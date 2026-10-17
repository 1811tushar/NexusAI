"""AgentState (architecture doc section 3). Plain JSON-able dicts/lists only (checkpointed by the Postgres saver).
Fields with reducers merge across nodes: usage/elapsed accumulate, limitations append."""
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


def merge_usage(a: dict[str, int] | None, b: dict[str, int] | None) -> dict[str, int]:
    a, b = a or {}, b or {}
    return {k: int(a.get(k, 0)) + int(b.get(k, 0)) for k in ("inputTokens", "outputTokens")}


class AgentState(TypedDict, total=False):
    # inputs
    question: str
    user_id: int
    thread_id: str
    investigation_id: int
    options: dict[str, Any]
    now: str
    # guard / routing
    refused: bool
    refusal: dict[str, str]
    trivial: bool
    route: dict[str, Any]
    memories: list[dict[str, Any]]
    # work products
    plan: list[dict[str, Any]]              # {id, description, agent, status}
    evidence: list[dict[str, Any]]          # EvidenceDTO wire dicts; labels E1.. = position+1
    claims: list[dict[str, Any]]            # {claimKey, text, isKey, evidenceKeys, status?, confidence?, support?, reason?}
    overall_confidence: float | None
    decision: str                           # ACCEPT | LOOP | ACCEPT_LOW_CONFIDENCE
    low_confidence: bool
    loop: int
    max_loops: int
    focus: list[str]                        # claim keys to strengthen
    evidence_count_at_loop_start: int
    # actions / approvals
    recommendations: list[dict[str, Any]]   # {id, text, risk, actionKey, actionType?}
    proposed_actions: list[dict[str, Any]]  # every validated proposal (wire dict of ActionProposed)
    pending_high: list[str]                 # actionKeys waiting for approval
    decisions: list[dict[str, Any]]
    rejected_actions: list[dict[str, Any]]   # {fingerprint, type, params}: never re-proposed in the same run
    # output
    report: str
    summary: str
    citation_validity: float | None
    cancelled: bool
    status: str                             # COMPLETED | REFUSED | CANCELLED
    # accumulators
    usage: Annotated[dict[str, int], merge_usage]
    elapsed_ms: Annotated[int, operator.add]
    limitations: Annotated[list[str], operator.add]
