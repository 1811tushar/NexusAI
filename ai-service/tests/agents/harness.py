"""Helpers to drive the real graph with a ScriptedLlm: collects the emitted events (the same objects the SSE routes serialise)."""
from __future__ import annotations

import asyncio
import re
import uuid
from typing import Any

from langgraph.checkpoint.memory import MemorySaver

from app.agents.runner import resume_stream, start_stream
from app.agents.runtime import Runtime
from app.api.schemas import AgentEvent, InvestigateOptions, InvestigateRequest, ResumeDecision, ResumeRequest

HERO = "Why did Q2 revenue decline compared to Q1, and what should management investigate?"


def mkreq(question: str = HERO, *, user_id: int = 1, thread_id: str | None = None, investigation_id: int = 1, **opts: Any) -> InvestigateRequest:
    o = {"webSearch": False, "useMemory": False, "maxLoops": 3, "documentIds": None} | opts
    return InvestigateRequest(investigation_id=investigation_id, thread_id=thread_id or str(uuid.uuid4()), user_id=user_id, question=question,
                              options=InvestigateOptions.model_validate(o), now="2026-10-14T09:00:00Z")


def make_runtime(biz, llm, *, checkpointer=None, web_fn=None) -> Runtime:
    return Runtime(settings=biz.settings, embedder=biz.embedder, retriever=biz.retriever, rw_pool=biz.rw, ro_pool=biz.ro,
                   checkpointer=checkpointer or MemorySaver(), llm=llm, web_search_fn=web_fn)


async def _collect(it) -> list[AgentEvent]:
    out = []
    async for x in it:
        if isinstance(x, AgentEvent):
            out.append(x)
    return out


def run(rt: Runtime, req: InvestigateRequest, **kw) -> list[AgentEvent]:
    return asyncio.run(_collect(start_stream(rt, req, **kw)))


def resume(rt: Runtime, req: InvestigateRequest, decisions: list[tuple[str, str, str | None]]) -> list[AgentEvent]:
    """decisions: (actionKey, 'APPROVE'|'REJECT', comment)"""
    rr = ResumeRequest(investigation_id=req.investigation_id, decisions=[
        ResumeDecision(action_key=k, approval_id=100 + i, decision=d, decided_by="approver@example.com", comment=c) for i, (k, d, c) in enumerate(decisions)])
    return asyncio.run(_collect(resume_stream(rt, req.thread_id, rr)))


def types(events: list[AgentEvent]) -> list[str]:
    return [e.type for e in events]


def of(events: list[AgentEvent], t: str) -> list[dict[str, Any]]:
    return [e.data for e in events if e.type == t]


_LABEL = re.compile(r"\[(E\d+)\]\n<untrusted_data source=\"E\d+ (\w+)\"")


def labels_by_kind(prompt: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for lab, kind in _LABEL.findall(prompt):
        out.setdefault(kind, []).append(lab)
    return out


def standard_script(*, hbq: str = "stats", action: dict | None = None, claims: list[dict] | None = None, verdicts: dict | None = None) -> dict[str, Any]:
    """A happy-path script for the hero question. `claims` items: {text, isKey, kinds:[DOCUMENT|STATS|SQL]} ; verdicts: text-substring -> (support, status)."""
    claims = claims or [
        {"text": "West Home revenue fell from 345150 to 189840 (-45.0%) between Q1 and Q2 2026.", "isKey": True, "kinds": ["STATS"]},
        {"text": "A supplier delay caused a stock-out of Home products in the West from May to June.", "isKey": True, "kinds": ["DOCUMENT"]},
    ]
    verdicts = verdicts or {}

    def analyst(system, user, n):
        lab = labels_by_kind(user)
        return {"claims": [{"key": None, "text": c["text"], "isKey": c.get("isKey", False),
                            "evidence": [lab[k][0] for k in c["kinds"] if lab.get(k)]} for c in claims]}

    def verifier(system, user, n):
        for sub, (support, status) in verdicts.items():
            if sub in user:
                return {"support": support, "status": status, "reason": "scripted"}
        return {"support": 0.95, "status": "VERIFIED", "reason": "evidence states it"}

    def reporter(system, user, n):
        lines = [m for m in re.findall(r"^- (.+?) \[((?:E\d+(?:, )?)+)\]", user.split("Unverified")[0], re.M)]
        findings = "\n".join(f"- {t} " + "".join(f"[{x.strip()}]" for x in labs.split(",")) for t, labs in lines) or "- No verified findings."
        first = lines[0] if lines else ("No answer", "")
        return f"## Executive summary\n{first[0]} " + "".join(f"[{x.strip()}]" for x in first[1].split(",") if x.strip()) + f"\n\n## Findings\n{findings}"

    act = {"recommendations": [{"text": "Review the West Home supply chain.", "action": None}]}
    if action:
        act = {"recommendations": [{"text": "Take the proposed action.", "action": action}]}
    return {
        "supervisor": {"route": "both", "reason": "Needs numbers and the explanation in documents."},
        "planner": {"steps": [{"description": "Find explanations in company documents", "agent": "RESEARCHER"},
                              {"description": "Quantify the Q2 vs Q1 revenue change by region and category", "agent": "DATA_ANALYST"}]},
        "researcher": [{"action": "call", "tool": "rag_search", "args": {"query": "supplier stock-out West Home Q2", "k": 3}}, {"action": "finish", "summary": "found"}],
        "data_analyst": [{"action": "call", "tool": "stats_contribution", "args": {"metric": "revenue", "dimension": "region_category",
                                                                              "period_a": {"start": "2026-01", "end": "2026-03"}, "period_b": {"start": "2026-04", "end": "2026-06"}}},
                         {"action": "finish", "summary": "computed"}],
        "analyst": analyst, "verifier": verifier, "reporter": reporter, "action_planning": act,
        "memory_summary": {"summary": "West Home revenue fell 45% in Q2 2026 vs Q1 due to a supplier stock-out; confidence high."},
    }


def ingest_supplier_doc(biz, doc_id: int = 501) -> None:
    from app.rag.ingest_pipeline import ingest_document
    text = ("# Supplier incident report\n\n## West Home stock-out\n\nThe supplier Helix Home Components delayed shipments of Home products to the West region "
            "from May 6 to June 24 2026, causing a stock-out of the Home category in the West.\n")
    ingest_document(store=biz.store, embedder=biz.embedder, settings=biz.settings, document_id=doc_id, source_type="MD",
                    title="Supplier incident report", filename="supplier.md", content=text.encode())
