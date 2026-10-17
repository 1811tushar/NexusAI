"""GET /internal/eval/runs and /internal/eval/runs/{id} (dashboard data). Runs are created by the CLI (python -m app.evals.run_eval), never by this API."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from app.api.schemas import ErrorCode, EvalMetrics, EvalResultItem, EvalRunDetailDTO, EvalRunDTO
from app.api.security import ApiError

router = APIRouter(prefix="/internal", tags=["eval"])


def _dto(r: dict[str, Any], detail: bool = False) -> EvalRunDTO | EvalRunDetailDTO:
    results = r["results"] or []
    fields = ("questionId", "category", "question", "expectedFacts", "answer", "correct", "groundedShare", "hallucinated", "latencyMs")
    base = dict(id=r["id"], created_at=r["created_at"].isoformat(), variant=r["variant"], system=r["system"], question_count=len(results),
                metrics=EvalMetrics.model_validate(r["metrics"]))
    if detail:
        return EvalRunDetailDTO(**base, results=[EvalResultItem.model_validate({k: x[k] for k in fields if k in x}) for x in results])
    return EvalRunDTO(**base)


@router.get("/eval/runs", response_model=list[EvalRunDTO], response_model_by_alias=True)
def list_runs(request: Request):
    with request.app.state.rw_pool.connection() as conn:
        rows = conn.execute("SELECT id, system, variant, metrics, results, created_at FROM ai.eval_runs ORDER BY created_at DESC, id DESC LIMIT 200").fetchall()
    return [_dto(r) for r in rows]


@router.get("/eval/runs/{run_id}", response_model=EvalRunDetailDTO, response_model_by_alias=True)
def get_run(request: Request, run_id: int):
    with request.app.state.rw_pool.connection() as conn:
        r = conn.execute("SELECT id, system, variant, metrics, results, created_at FROM ai.eval_runs WHERE id = %s", (run_id,)).fetchone()
    if r is None:
        raise ApiError(404, ErrorCode.NOT_FOUND, "Unknown evaluation run")
    return _dto(r, detail=True)
