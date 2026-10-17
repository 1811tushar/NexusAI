"""POST /internal/investigate (SSE), POST /internal/investigate/{threadId}/resume (SSE), POST /internal/investigate/{threadId}/cancel (contract section 6).
Thin routes: all behaviour lives in app/agents. approval_required ends one stream; resume continues from the checkpoint."""
from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.agents import events as ev
from app.agents.runner import cancel_thread, resume_stream, sse, start_stream
from app.agents.runtime import runtime_for
from app.api.schemas import ErrorCode, InvestigateRequest, ResumeRequest
from app.api.security import ApiError

router = APIRouter(prefix="/internal", tags=["investigate"])
SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"}


def _thread(thread_id: str) -> str:
    try:
        return str(uuid.UUID(thread_id))
    except ValueError as exc:
        raise ApiError(400, ErrorCode.VALIDATION_FAILED, "threadId must be a UUID") from exc


@router.post("/investigate")
async def investigate(request: Request, req: InvestigateRequest) -> StreamingResponse:
    _thread(req.thread_id)
    rt = runtime_for(request.app)
    if req.thread_id in rt.runs:
        raise ApiError(409, ErrorCode.INVALID_STATE, "This investigation is already running")
    return StreamingResponse(sse(start_stream(rt, req)), media_type="text/event-stream", headers=SSE_HEADERS)


@router.post("/investigate/{thread_id}/resume")
async def resume(request: Request, thread_id: str, req: ResumeRequest) -> StreamingResponse:
    thread_id = _thread(thread_id)
    rt = runtime_for(request.app)
    snap = await rt.graph.aget_state({"configurable": {"thread_id": thread_id}})
    if not snap.values:
        raise ApiError(404, ErrorCode.NOT_FOUND, "Unknown investigation thread")
    if thread_id in rt.runs:
        raise ApiError(409, ErrorCode.INVALID_STATE, "This investigation is already running")
    if snap.values.get("cancelled"):
        async def cancelled() -> AsyncIterator[str]:
            u = snap.values.get("usage") or {}
            yield ev.done("CANCELLED", None, int(snap.values.get("loop", 0)), int(u.get("inputTokens", 0)), int(u.get("outputTokens", 0)),
                          int(snap.values.get("elapsed_ms", 0))).to_sse()
        return StreamingResponse(cancelled(), media_type="text/event-stream", headers=SSE_HEADERS)
    if not snap.next or "approval_gate" not in snap.next:
        raise ApiError(409, ErrorCode.INVALID_STATE, "This investigation is not waiting for approval decisions")
    return StreamingResponse(sse(resume_stream(rt, thread_id, req)), media_type="text/event-stream", headers=SSE_HEADERS)


@router.post("/investigate/{thread_id}/cancel")
async def cancel(request: Request, thread_id: str) -> dict[str, bool]:
    return {"cancelled": await cancel_thread(runtime_for(request.app), _thread(thread_id))}
