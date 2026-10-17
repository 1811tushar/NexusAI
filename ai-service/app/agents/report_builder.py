"""Deterministic report assembly (AI-AG-09, ADD-FH-02). The LLM writes ONLY the Executive summary and the Findings (from VERIFIED claims). CODE adds:
low-confidence banner, Recommendations (risk from the catalogue, approval outcomes), Unverified/contradicted claims, 'Limitations and failures'.
So an unverified claim can never be presented as a finding, and failures can never be silently dropped."""
from __future__ import annotations

import re
from typing import Any

from app.agents.citation_check import LABEL_RE, CitationResult

SIM_NOTE = "_Actions are simulated: no external system is changed._"


def extract_summary(body: str, limit: int = 400) -> str:
    m = re.search(r"##\s*Executive summary\s*\n(.*?)(?=\n##\s|\Z)", body, re.S | re.I)
    text = (m.group(1) if m else body).strip()
    text = re.sub(r"\s+", " ", LABEL_RE.sub("", text)).strip()
    text = re.sub(r"\[ev:[0-9a-f-]+\]", "", text).strip()
    return text[:limit]


def _decision_line(rec: dict[str, Any], decisions: list[dict[str, Any]]) -> str:
    if not rec.get("actionKey"):
        return ""
    d = next((x for x in decisions if x["actionKey"] == rec["actionKey"]), None)
    if rec["risk"] == "LOW":
        return " Low-risk action: recorded automatically as a simulation."
    if d is None:
        return " Awaiting approval."
    who = f" by {d['decidedBy']}" if d.get("decidedBy") else ""
    note = f" ({d['comment']})" if d.get("comment") else ""
    return (f" **Approved{who}**{note}: executed by the platform as a simulated action." if d["decision"] == "APPROVE"
            else f" **Rejected{who}**{note}: no action was taken.")


def build_report(*, body: str, claims: list[dict[str, Any]], recommendations: list[dict[str, Any]], decisions: list[dict[str, Any]],
                 limitations: list[str], low_confidence: bool, overall: float | None, threshold: float, moved: list[tuple[str, str]]) -> str:
    parts: list[str] = []
    if low_confidence:
        parts.append(f"> **Low confidence ({(overall or 0):.2f}, threshold {threshold:.2f}).** Some findings could not be verified; treat this report as preliminary.")
    parts.append(body.strip())
    parts.append("## Recommendations")
    if recommendations:
        parts.append("\n".join(f"- {r['text']} ({r['risk']} risk{', action proposed' if r.get('actionKey') else ', advice only'})." + _decision_line(r, decisions)
                               for r in recommendations))
        parts.append(SIM_NOTE)
    else:
        parts.append("No recommendations were made.")
    unverified = [c for c in claims if c.get("status") != "VERIFIED"]
    parts.append("## Unverified or contradicted claims")
    lines = [f"- [{c.get('status', 'UNSUPPORTED')}, confidence {float(c.get('confidence') or 0):.2f}] {c['text']}" + (f" - {c['reason']}" if c.get("reason") else "")
             for c in unverified]
    lines += [f"- [NOT VALIDATED, {reason}] {text}" for text, reason in moved]
    parts.append("\n".join(lines) if lines else "None: every claim was verified.")
    parts.append("## Limitations and failures")
    parts.append("\n".join(f"- {x}" for x in dict.fromkeys(limitations)) if limitations else "No tool failures or data gaps were recorded in this run.")
    return "\n\n".join(parts) + "\n"


def fallback_body(verified: list[dict[str, Any]], labels_of_claim: dict[str, list[str]]) -> str:
    """Safe fallback when the reporter LLM fails: findings straight from the verified claims, with their evidence labels."""
    if not verified:
        return "## Executive summary\nThe available documents and data could not answer this question with verified evidence.\n\n## Findings\n- No verified findings."
    bullets = "\n".join(f"- {c['text']} " + "".join(f"[{x}]" for x in labels_of_claim.get(c["claimKey"], [])) for c in verified)
    return f"## Executive summary\n{verified[0]['text']} " + "".join(f"[{x}]" for x in labels_of_claim.get(verified[0]["claimKey"], [])) + f"\n\n## Findings\n{bullets}"


def citation_issue_detail(res: CitationResult) -> str:
    return res.detail()
