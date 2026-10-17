"""BASELINE system (AI-EV-02): single-shot RAG over the documents ONLY. Retrieve once, answer once. No tools, no SQL, no verification, no memory, no guardrail,
no loop. Same retriever, same LLM provider as the agent, so the comparison isolates the architecture."""
from __future__ import annotations

import time
import uuid
from typing import Any

from app.agents.injection import wrap_untrusted
from app.agents.prompts_loader import render
from app.evals.metrics import RunRecord


def run_baseline(env: Any, item: dict[str, Any], *, k: int = 8) -> RunRecord:
    rec = RunRecord(item["id"], item["category"], "BASELINE")
    t0 = time.perf_counter()
    fault = (item.get("fault") or {}).get("rag_search")
    if fault in ("error", "vector_failure", "timeout"):          # the baseline has no failure policy: a retrieval failure ends the run
        rec.status, rec.error = "FAILED", "document search failed"
        rec.latency_ms = int((time.perf_counter() - t0) * 1000)
        return rec
    chunks = [] if fault == "empty" else env.retriever.search(item["question"], mode="HYBRID", k=k)
    evidence = []
    for c in chunks:
        evidence.append({"evidenceKey": str(uuid.uuid4()), "kind": "DOCUMENT", "title": c.document_title, "snippet": c.content[:900],
                         "source": {"documentId": c.document_id, "page": c.page}, "score": c.similarity})
    block = "\n".join(f"[E{i + 1}]\n" + wrap_untrusted(f"{e['title']}\n{e['snippet']}", f"E{i + 1} DOCUMENT") for i, e in enumerate(evidence)) or "(no passages)"
    system, user = render("baseline_rag", question=item["question"], evidence=block)
    reply = env.rt.llm.complete(tag="baseline_rag", system=system, user=user)
    rec.answer, rec.evidence = reply.text.strip(), evidence
    rec.in_tokens, rec.out_tokens = reply.input_tokens, reply.output_tokens
    rec.latency_ms = int((time.perf_counter() - t0) * 1000)
    return rec
