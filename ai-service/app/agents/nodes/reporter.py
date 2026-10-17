"""reporter (AI-AG-09): streams report_delta tokens, validates citations programmatically (ADD-GR-03), assembles the final Markdown deterministically
(see report_builder), emits report_ready. States only VERIFIED claims as findings; others go under 'Unverified'; low-confidence banner; approval outcomes.
Citations leave the LLM as [E#] labels and are stored as [ev:<evidenceKey>]."""
from __future__ import annotations

from typing import Any

from app.agents import events as ev
from app.agents.citation_check import check_report, replace_labels
from app.agents.common import label_of_key, labels_of, node
from app.agents.context import RunContext
from app.agents.prompts_loader import render
from app.agents.report_builder import build_report, extract_summary, fallback_body
from app.core.llm import LlmRateLimited, LlmUnavailable


def _stream(ctx: RunContext, tag: str, system: str, user: str) -> str:
    chunks: list[str] = []
    for part in ctx.llm.stream(tag=tag, system=system, user=user):
        ctx.check_cancel()
        chunks.append(part)
        ctx.emit(ev.report_delta(part))
    text = "".join(chunks)
    ctx.add_usage((len(system) + len(user)) // 4, len(text) // 4)
    return text


@node("reporter")
def reporter(state: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    ctx.emit(ev.agent_started("REPORTER"))
    if state.get("trivial"):
        system, user = render("reporter_direct", question=state["question"])
        answer = _stream(ctx, "reporter_direct", system, user).strip() or "I can investigate business questions using company documents and data."
        ctx.emit(ev.report_ready(answer, answer[:400], [], 0.0))
        return {"report": answer, "summary": answer[:400], "status": "COMPLETED", "overall_confidence": None, "citation_validity": None}

    evidence, claims = state.get("evidence", []), state.get("claims", [])
    labels, lab_of = labels_of(evidence), label_of_key(evidence)
    verified = sorted([c for c in claims if c.get("status") == "VERIFIED"], key=lambda c: (not c.get("isKey"), -float(c.get("confidence") or 0)))
    unverified = [c for c in claims if c.get("status") != "VERIFIED"]
    claim_labels = {c["claimKey"]: [lab_of[k] for k in c["evidenceKeys"] if k in lab_of] for c in claims}
    fmt = lambda cs: "\n".join(f"- {c['text']} [{', '.join(claim_labels[c['claimKey']])}] (confidence {float(c.get('confidence') or 0):.2f})" for c in cs) or "(none)"  # noqa: E731
    system, user = render("reporter", question=state["question"], confidence=f"{float(state.get('overall_confidence') or 0):.2f}",
                          verified=fmt(verified), unverified=fmt(unverified))
    limitations: list[str] = []
    body = ""
    if verified:
        try:
            body = _stream(ctx, "reporter", system, user).strip()
        except (LlmRateLimited, LlmUnavailable):
            raise
        except Exception as exc:  # noqa: BLE001
            ctx.log.warning("reporter LLM failed: %s", type(exc).__name__)
    if not body or "## " not in body:
        if verified:
            limitations.append("The report writer returned no usable text, so the findings below are the verified claims as written by the analyst.")
        body = fallback_body(verified, claim_labels)
    res = check_report(body, labels)
    if res.moved:
        ctx.guardrail("OUTPUT", "FLAGGED", "INVALID_CITATION", res.detail())
    if "## Findings" not in res.markdown and verified:
        res.markdown += "\n\n## Findings\n" + "\n".join(f"- {c['text']} " + "".join(f"[{x}]" for x in claim_labels[c["claimKey"]]) for c in verified[:3])
    limits = list(state.get("limitations", [])) + limitations
    markdown = build_report(body=res.markdown, claims=claims, recommendations=state.get("recommendations", []), decisions=state.get("decisions", []),
                            limitations=limits, low_confidence=bool(state.get("low_confidence")), overall=state.get("overall_confidence"),
                            threshold=float(ctx.settings.confidence_min), moved=res.moved)
    markdown = replace_labels(markdown, labels)
    summary = extract_summary(res.markdown)
    overall = float(state.get("overall_confidence") or 0.0)
    ctx.emit(ev.report_ready(markdown, summary, state.get("recommendations", []), overall))
    return {"report": markdown, "summary": summary, "status": "COMPLETED", "citation_validity": res.validity, "limitations": limitations}
