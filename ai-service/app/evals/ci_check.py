"""CI gate (ADD-CI-01): python -m app.evals.ci_check [--margin 0.05] [--no-safety] [--record]
Exits NON-ZERO when (a) any safety test fails (SQL guard hostile queries, input guardrail, approval gate/forged risk, citation validator, fault injection,
prompt-injection handling) or (b) retrieval hit@5 / MRR of any ablation variant drops more than --margin below evals/baseline_metrics.json for the same embedding model.
Deterministic and free: no LLM call anywhere. Writes a Markdown summary to $GITHUB_STEP_SUMMARY when set."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.core.db import detect_capabilities, ensure_ai_schema, open_rw_pool
from app.core.embeddings import load_embedder
from app.evals import retrieval_ablation as ab

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
SAFETY_TESTS = ["tests/agents/test_sql_guard.py", "tests/agents/test_safety_units.py", "tests/agents/test_tools_unit.py", "tests/agents/test_graph_paths.py",
                "tests/agents/test_memory.py"]


def compare(rows: list[dict[str, Any]], baseline: dict[str, Any], margin: float) -> tuple[list[str], list[str]]:
    """Returns (regressions, notes)."""
    bad, notes = [], []
    have = {ab.key(r): r for r in rows if "skipped" not in r}
    for k, ref in baseline["variants"].items():
        r = have.get(k)
        if r is None:
            notes.append(f"{k}: not measured in this run (skipped)")
            continue
        for metric in ("hit5", "mrr"):
            if r[metric] < ref[metric] - margin - 1e-9:
                bad.append(f"{k}: {metric} {r[metric]:.3f} < baseline {ref[metric]:.3f} - margin {margin:.2f}")
    return bad, notes


def run_safety() -> int:
    import pytest
    if not os.environ.get("TEST_ADMIN_DSN"):
        print("ERROR: TEST_ADMIN_DSN is not set; the DB-backed safety tests would be skipped, which must not count as passing.")
        return 2
    return int(pytest.main(["-q", "-p", "no:cacheprovider", *[str(ROOT / t) for t in SAFETY_TESTS]]))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app.evals.ci_check")
    ap.add_argument("--margin", type=float, default=0.05)
    ap.add_argument("--no-safety", action="store_true")
    ap.add_argument("--record", action="store_true", help="no baseline for this embedding model yet: record it and exit 0")
    args = ap.parse_args(argv)
    summary: list[str] = ["# eval-ci", ""]
    code = 0
    if not args.no_safety:
        rc = run_safety()
        summary.append(f"- Safety tests: {'PASS' if rc == 0 else 'FAIL (exit ' + str(rc) + ')'}")
        code = code or (1 if rc else 0)
    settings = Settings()
    rw = open_rw_pool(settings)
    try:
        ensure_ai_schema(rw)
        rows = ab.run_ablation(settings, rw, detect_capabilities(rw), load_embedder(settings), reranker=ab.OverlapReranker())
    finally:
        rw.close()
    measured = [r for r in rows if "skipped" not in r]
    baselines = json.loads((HERE / "baseline_metrics.json").read_text()) if (HERE / "baseline_metrics.json").exists() else {}
    base = baselines.get(settings.embedding_model)
    if base is None:
        if args.record:
            print("Recorded baseline:", ab.update_baseline(rows, settings.embedding_model))
            summary.append(f"- Retrieval ablation: baseline recorded for {settings.embedding_model}")
        else:
            summary.append(f"- Retrieval ablation: NO BASELINE for embedding model '{settings.embedding_model}' (run with --record once, commit baseline_metrics.json)")
            code = code or 2
    else:
        bad, notes = compare(rows, base, args.margin)
        summary.append(f"- Retrieval ablation ({len(measured)} variants vs baseline {base['recordedAt']}): {'PASS' if not bad else 'FAIL'}")
        summary += [f"  - REGRESSION {b}" for b in bad] + [f"  - note: {n}" for n in notes]
        code = code or (1 if bad else 0)
    text = "\n".join(summary) + "\n\n" + "```\n" + "\n".join(f"{ab.key(r):28} hit5={r['hit5']:.3f} mrr={r['mrr']:.3f}" for r in measured) + "\n```\n"
    print(text)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        Path(os.environ["GITHUB_STEP_SUMMARY"]).write_text(text, encoding="utf-8")
    return code


if __name__ == "__main__":
    sys.exit(main())
