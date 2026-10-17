"""Markdown + CSV report of evaluation runs (AI-EV-04). Numbers are copied from the runs; the verdict sentences are generated from those numbers only."""
from __future__ import annotations

import csv
import io
from typing import Any

COLS = [("answerCorrectness", "Correct"), ("groundedClaimsShare", "Grounded"), ("hallucinationRate", "Halluc."), ("citationValidity", "Cite valid"),
        ("avgLatencyMs", "Latency ms"), ("avgTokens", "Tokens/q"), ("approvalGateCompliance", "Gate"), ("guardrailBlockRate", "Block"), ("failureRecoveryRate", "Recovery")]


def _f(v: Any) -> str:
    return "n/a" if v is None else (f"{v:,.1f}" if isinstance(v, float) and abs(v) >= 100 else f"{v:.3f}" if isinstance(v, float) else str(v))


def tradeoff(runs: list[dict[str, Any]]) -> list[str]:
    by = {r["system"]: r["metrics"] for r in runs}
    base = by.get("BASELINE")
    lines = []
    for name, m in by.items():
        if base is None or name == "BASELINE":
            continue
        d_q, d_t = m["answerCorrectness"] - base["answerCorrectness"], m["avgTokens"] - base["avgTokens"]
        ratio = (m["avgTokens"] / base["avgTokens"]) if base["avgTokens"] else float("nan")
        per_k = (d_q / (d_t / 1000)) if d_t > 0 else float("nan")
        lines.append(f"- **{name}** vs BASELINE: correctness {d_q:+.3f}, hallucination {m['hallucinationRate'] - base['hallucinationRate']:+.3f}, "
                     f"tokens x{ratio:.1f} ({d_t:+,.0f} per question), correctness gain per 1,000 extra tokens {per_k:+.3f}.")
    if "AGENT" in by and "SINGLE_AGENT" in by:
        a, s = by["AGENT"], by["SINGLE_AGENT"]
        lines.append(f"- **Why multiple agents?** AGENT vs SINGLE_AGENT: correctness {a['answerCorrectness'] - s['answerCorrectness']:+.3f}, hallucination "
                     f"{a['hallucinationRate'] - s['hallucinationRate']:+.3f}, grounded share {a['groundedClaimsShare'] - s['groundedClaimsShare']:+.3f}, tokens x{a['avgTokens'] / s['avgTokens']:.1f}." if s["avgTokens"] else "")
    if "AGENT" in by and "AGENT_NO_VERIFIER" in by:
        a, n = by["AGENT"], by["AGENT_NO_VERIFIER"]
        lines.append(f"- **What does the verifier buy?** AGENT vs AGENT_NO_VERIFIER: hallucination {a['hallucinationRate'] - n['hallucinationRate']:+.3f}, "
                     f"correctness {a['answerCorrectness'] - n['answerCorrectness']:+.3f}, tokens x{a['avgTokens'] / n['avgTokens']:.1f}." if n["avgTokens"] else "")
    return [x for x in lines if x]


def render_markdown(runs: list[dict[str, Any]], items: list[dict[str, Any]]) -> str:
    out = ["# NexusAI evaluation report", "", f"Questions per system: {len(items)}. Results are reported as measured; see the limitations below.", "",
           "## System comparison", "", "| System | " + " | ".join(h for _, h in COLS) + " |", "|---|" + "---|" * len(COLS)]
    for r in runs:
        out.append(f"| {r['system']} | " + " | ".join(_f(r["metrics"].get(k)) for k, _ in COLS) + " |")
    out += ["", "## Quality vs token cost", "", *(tradeoff(runs) or ["(needs BASELINE plus at least one other system in the same run)"]), ""]
    out += ["## Per category (share of questions answered correctly)", ""]
    cats = sorted({c for r in runs for c in r["extras"]["byCategory"]})
    out += ["| System | " + " | ".join(cats) + " |", "|---|" + "---|" * len(cats)]
    for r in runs:
        out.append(f"| {r['system']} | " + " | ".join(_f(r["extras"]["byCategory"].get(c, {}).get("correct")) for c in cats) + " |")
    fp = [f"{r['system']}: {_f(r['extras']['guardrailFalsePositiveRate'])}" for r in runs if r["extras"].get("guardrailFalsePositiveRate") is not None]
    out += ["", "Guardrail false-positive rate (benign questions refused): " + (", ".join(fp) or "n/a"), ""]
    fails = [(r["system"], x) for r in runs for x in r["results"] if not x["correct"]][:25]
    out += ["## Failing questions (first 25)", ""] + [f"- {s} / {x['questionId']} ({x['category']}): {x['question'][:90]} -> status {x['status']}" for s, x in fails] + [""]
    out += ["## Method and limitations", "",
            "- Data: synthetic company (seed generator, fixed seed); documents consistent with it; one conflicting, one irrelevant and one adversarial document.",
            f"- Golden set: {len(items)} questions in five categories; small, so differences of a few points are within noise.",
            "- Judge: " + (runs[0].get("config", {}).get("judge", "n/a") if runs else "n/a") + "; deterministic checks (numbers, abstention, forbidden text, invented numbers) always apply.",
            "- Metric definitions are in app/evals/metrics.py. No number in this report was edited by hand."]
    return "\n".join(out) + "\n"


def render_csv(runs: list[dict[str, Any]]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["system", "questionId", "category", "status", "correct", "groundedShare", "hallucinated", "citationValidity", "tokens", "latencyMs"])
    for r in runs:
        for x in r["results"]:
            w.writerow([r["system"], x["questionId"], x["category"], x["status"], int(x["correct"]), x["groundedShare"], int(x["hallucinated"]),
                        "" if x["citationValidity"] is None else x["citationValidity"], x["tokens"], x["latencyMs"]])
    return buf.getvalue()


def render_ablation(rows: list[dict[str, Any]]) -> str:
    out = ["| Chunking | Mode | Reranker | hit@1 | hit@3 | hit@5 | MRR |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| {r['chunking']} | {r['mode']} | {r['rerank']} | " + " | ".join(_f(r.get(k)) for k in ("hit1", "hit3", "hit5", "mrr")) + " |")
    return "\n".join(out)
