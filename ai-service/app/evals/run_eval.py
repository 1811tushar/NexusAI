"""One command runs the systems and stores the results (AI-EV-04):
    python -m app.evals.run_eval --system agent|baseline|single_agent|no_verifier|both|all [--limit N] [--category NORMAL] [--judge llm|keyword]
Ingests the corpus, runs the golden questions, stores one ai.eval_runs row per system with per-question results, writes Markdown + CSV (evals/results/).
Results are reported AS MEASURED. Needs: Postgres with the business tables loaded (see docs/evaluation-howto.md) and the LLM provider configured."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.agents.context import FaultSpec
from app.agents.runner import resume_stream, start_stream
from app.api.schemas import AgentEvent, InvestigateOptions, InvestigateRequest, ResumeDecision, ResumeRequest
from app.evals import report as report_mod
from app.evals.baseline_rag import run_baseline
from app.evals.judge import Judge
from app.evals.metrics import RunRecord, aggregate, high_risk_gate_ok, score_record
from app.evals.runtime import EvalEnv, build_env, business_data_present, ensure_corpus
from app.evals.single_agent import run_single_agent

HERE = Path(__file__).parent
SYSTEMS = {"agent": "AGENT", "baseline": "BASELINE", "single_agent": "SINGLE_AGENT", "no_verifier": "AGENT_NO_VERIFIER"}
GROUPS = {"both": ["baseline", "agent"], "all": ["baseline", "single_agent", "no_verifier", "agent"]}
EVAL_USER = 900001
log = logging.getLogger("evals")


def load_questions(path: Path | None = None) -> list[dict[str, Any]]:
    return json.loads((path or HERE / "golden_questions.json").read_text(encoding="utf-8"))


def _fault(item: dict[str, Any]) -> FaultSpec | None:
    return FaultSpec(tool_faults=dict(item["fault"])) if item.get("fault") else None


async def _collect(it: Any) -> list[AgentEvent]:
    return [x async for x in it if isinstance(x, AgentEvent)]


def run_agent(env: EvalEnv, item: dict[str, Any], system: str, n: int) -> RunRecord:
    """Runs the real graph. If it pauses for approval, the harness REJECTS every pending action (it is not an approver) so the report can finish;
    gate compliance is judged on the events BEFORE the pause."""
    variant = "AGENT_NO_VERIFIER" if system == "AGENT_NO_VERIFIER" else "AGENT"
    rec = RunRecord(item["id"], item["category"], system)
    opts = InvestigateOptions.model_validate({"webSearch": False, "useMemory": False, "maxLoops": env.settings.max_loops, "documentIds": None})
    req = InvestigateRequest(investigation_id=n, thread_id=str(uuid.uuid4()), user_id=EVAL_USER, question=item["question"], options=opts,
                             now="2026-10-14T09:00:00Z")
    t0 = time.perf_counter()
    events = asyncio.run(_collect(start_stream(env.rt, req, faults=_fault(item), variant=variant)))
    rec.gate_ok = high_risk_gate_ok(events)
    if events and events[-1].type == "approval_required":
        pending = events[-1].data["actions"]
        rr = ResumeRequest(investigation_id=n, decisions=[ResumeDecision(action_key=a["actionKey"], approval_id=i + 1, decision="REJECT", decided_by="eval-harness",
                                                                         comment="Automatic rejection by the evaluation harness") for i, a in enumerate(pending)])
        events += asyncio.run(_collect(resume_stream(env.rt, req.thread_id, rr)))
    rec.latency_ms = int((time.perf_counter() - t0) * 1000)
    rec.event_types = [e.type for e in events]
    for e in events:
        if e.type == "evidence_added":
            rec.evidence.append(e.data["evidence"])
    ready = [e.data for e in events if e.type == "report_ready"]
    rec.answer = ready[-1]["reportMarkdown"] if ready else ""
    terminal = events[-1] if events else None
    if terminal is not None and terminal.type == "done":
        rec.status = terminal.data["status"]
        rec.in_tokens, rec.out_tokens = terminal.data["usage"]["inputTokens"], terminal.data["usage"]["outputTokens"]
    else:
        rec.status = "FAILED"
        rec.error = terminal.data.get("message") if terminal is not None and terminal.type == "error" else "no terminal event"
    if "## Limitations and failures" in rec.answer:
        body = rec.answer.split("## Limitations and failures", 1)[1]
        rec.limitation_text = "" if "No tool failures or data gaps" in body else body.strip()
    return rec


def run_one(env: EvalEnv, system: str, item: dict[str, Any], n: int) -> RunRecord:
    try:
        if system == "BASELINE":
            return run_baseline(env, item)
        if system == "SINGLE_AGENT":
            return run_single_agent(env, item)
        return run_agent(env, item, system, n)
    except Exception as exc:  # noqa: BLE001  one failing question must not abort the evaluation
        log.warning("question %s failed on %s: %s", item["id"], system, type(exc).__name__)
        return RunRecord(item["id"], item["category"], system, status="FAILED", error=f"{type(exc).__name__}")


def run_system(env: EvalEnv, system: str, items: list[dict[str, Any]], judge: Judge, *, sleep_s: float = 0.0,
               progress: Any = None) -> dict[str, Any]:
    results = []
    for n, item in enumerate(items, start=1):
        rec = run_one(env, system, item, n)
        results.append(score_record(item, rec, judge.evaluate(item, rec.answer) if rec.status == "COMPLETED" else None))
        if progress:
            progress(system, n, len(items), results[-1])
        if sleep_s:
            time.sleep(sleep_s)
    agg = aggregate(results, items, system=system)
    return {"system": system, "metrics": agg["metrics"], "extras": agg["extras"], "results": results}


def store_run(env: EvalEnv, run: dict[str, Any], *, variant: str | None, config: dict[str, Any]) -> int:
    with env.rw.connection() as c:
        row = c.execute("INSERT INTO ai.eval_runs (system, variant, config, metrics, results) VALUES (%s, %s, %s::jsonb, %s::jsonb, %s::jsonb) RETURNING id",
                        (run["system"], variant, json.dumps({**config, "extras": run["extras"]}), json.dumps(run["metrics"]), json.dumps(run["results"]))).fetchone()
        c.commit()
    return int(row["id"])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app.evals.run_eval")
    ap.add_argument("--system", default="both", choices=[*SYSTEMS, *GROUPS])
    ap.add_argument("--limit", type=int)
    ap.add_argument("--category")
    ap.add_argument("--ids", help="comma separated question ids")
    ap.add_argument("--judge", default="llm", choices=["llm", "keyword"])
    ap.add_argument("--label", help="variant label stored with the run")
    ap.add_argument("--sleep", type=float, default=0.0, help="seconds between questions (free-tier rate limits)")
    ap.add_argument("--no-store", action="store_true")
    ap.add_argument("--out", default=str(HERE / "results"))
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    items = load_questions()
    if args.category:
        items = [i for i in items if i["category"] == args.category.upper()]
    if args.ids:
        wanted = set(args.ids.split(","))
        items = [i for i in items if i["id"] in wanted]
    if args.limit:
        items = items[:args.limit]
    env = build_env()
    try:
        if not business_data_present(env):
            print("ERROR: business tables are empty or missing. Load them first (docs/evaluation-howto.md).")
            return 2
        ensure_corpus(env)
        judge = Judge(env.rt.llm if args.judge == "llm" else None, args.judge)
        systems = GROUPS.get(args.system, [args.system])
        runs = []
        for s in systems:
            print(f"== {SYSTEMS[s]}: {len(items)} question(s)")
            run = run_system(env, SYSTEMS[s], items, judge, sleep_s=args.sleep,
                             progress=lambda sy, n, tot, r: print(f"  [{n}/{tot}] {r['questionId']} {'OK ' if r['correct'] else 'BAD'} {r['status']} {r['latencyMs']}ms"))
            cfg = {"questions": len(items), "judge": judge.description, "llmProvider": env.settings.llm_provider, "embeddingModel": env.settings.embedding_model,
                   "maxLoops": env.settings.max_loops, "confidenceMin": env.settings.confidence_min, "createdAt": datetime.now(UTC).isoformat()}
            run["config"] = cfg
            if not args.no_store:
                run["id"] = store_run(env, run, variant=args.label, config=cfg)
            runs.append(run)
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        (out / f"eval-{stamp}.md").write_text(report_mod.render_markdown(runs, items), encoding="utf-8")
        (out / f"eval-{stamp}.csv").write_text(report_mod.render_csv(runs), encoding="utf-8")
        print(report_mod.render_markdown(runs, items))
        print(f"Wrote {out}/eval-{stamp}.md and .csv")
        return 0
    finally:
        env.close()


if __name__ == "__main__":
    raise SystemExit(main())
