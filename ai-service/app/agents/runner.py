"""Streaming runner (AI-AG-10, route contract section 6): drives the graph in a background task, turns node events into SSE frames, guarantees ONE terminal
event (done | error) except that approval_required ends the stream after the interrupt. Client disconnect cancels the run unless it is paused.
Cancellation is cooperative (threading.Event checked between LLM/tool calls) plus task.cancel()."""
from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import AsyncIterator
from typing import Any

from langgraph.types import Command

from app.agents import events as ev
from app.agents.context import FaultSpec, RunCancelled
from app.agents.runtime import RunHandle, Runtime
from app.api.schemas import AgentEvent, InvestigateRequest, ResumeRequest
from app.core.llm import LlmConfigError, LlmError, LlmRateLimited

log = logging.getLogger(__name__)
KEEPALIVE_S = 15.0
ZERO_USAGE = {"inputTokens": 0, "outputTokens": 0}


def initial_state(req: InvestigateRequest) -> dict[str, Any]:
    return {"question": req.question, "user_id": req.user_id, "thread_id": req.thread_id, "investigation_id": req.investigation_id,
            "options": req.options.wire(), "now": req.now, "loop": 0, "max_loops": req.options.max_loops, "evidence": [], "claims": [], "plan": [],
            "limitations": [], "usage": dict(ZERO_USAGE), "elapsed_ms": 0, "rejected_actions": [], "proposed_actions": [], "decisions": [],
            "pending_high": [], "memories": [], "recommendations": [], "focus": [], "refused": False, "trivial": False}


def terminal_event(values: dict[str, Any]) -> AgentEvent:
    status = values.get("status") or "COMPLETED"
    usage = values.get("usage") or ZERO_USAGE
    conf = None if status == "REFUSED" or values.get("trivial") else values.get("overall_confidence")
    return ev.done(status, conf, int(values.get("loop", 0)), int(usage.get("inputTokens", 0)), int(usage.get("outputTokens", 0)), int(values.get("elapsed_ms", 0)))


def error_event(exc: BaseException) -> AgentEvent:
    """ADD-FH-03: whole-run failure -> readable explanation, no stack, no provider internals. The partial trace is already persisted by Spring."""
    if isinstance(exc, LlmRateLimited):
        return ev.error("LLM_RATE_LIMITED", "The language model is rate-limited right now. Wait a minute and start the investigation again.", True)
    if isinstance(exc, LlmConfigError):
        return ev.error("AI_SERVICE_UNAVAILABLE", "The language model is not configured on the AI service (missing provider key).", False)
    if isinstance(exc, LlmError) or type(exc).__name__ in ("OperationalError", "PoolTimeout"):
        return ev.error("AI_SERVICE_UNAVAILABLE", "A service the investigation depends on (language model or database) is unavailable. Try again shortly.", True)
    log.error("investigation failed: %s", type(exc).__name__, exc_info=True)
    return ev.error("INTERNAL_ERROR", "The investigation stopped because of an unexpected internal error.", False)


async def stream_events(rt: Runtime, *, thread_id: str, graph_input: Any, req_meta: dict[str, Any], resuming: bool,
                        faults: FaultSpec | None = None, variant: str = "AGENT") -> AsyncIterator[AgentEvent | str]:
    """Yields AgentEvent objects (and ': keepalive' comment strings). Used by the SSE routes and by the in-process eval runner."""
    queue: asyncio.Queue[Any] = asyncio.Queue()
    loop = asyncio.get_running_loop()
    handle = RunHandle()

    def emit(e: AgentEvent) -> None:                      # nodes run in worker threads
        try:
            loop.call_soon_threadsafe(queue.put_nowait, e)
        except RuntimeError:
            pass

    try:
        ctx = rt.make_ctx(emit=emit, cancel=handle.cancel, resuming=resuming, faults=faults, variant=variant, **req_meta)
    except Exception as exc:  # noqa: BLE001  e.g. LlmConfigError (no provider key): the stream has started, so report it as the terminal error event
        yield error_event(exc)
        return
    config = {"configurable": {"thread_id": thread_id, "ctx": ctx}, "metadata": {"user_id": req_meta["user_id"], "investigation_id": req_meta["investigation_id"]},
              "recursion_limit": 120}

    async def drive() -> None:
        try:
            async for _ in rt.graph.astream(graph_input, config, stream_mode="updates"):
                pass
            snap = await rt.graph.aget_state(config)
            queue.put_nowait(("paused", None) if snap.next else ("finished", dict(snap.values)))
        except (RunCancelled, asyncio.CancelledError):
            queue.put_nowait(("cancelled", None))
        except Exception as exc:  # noqa: BLE001
            queue.put_nowait(("error", exc))

    task = asyncio.create_task(drive())
    handle.task = task
    rt.runs[thread_id] = handle
    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=KEEPALIVE_S)
            except TimeoutError:
                yield ": keepalive\n\n"
                continue
            if isinstance(item, AgentEvent):
                yield item
                continue
            kind, payload = item
            if kind == "finished":
                yield terminal_event(payload)
            elif kind == "cancelled":
                snap = await rt.graph.aget_state(config)
                yield ev.done("CANCELLED", None, int(snap.values.get("loop", 0)), *_usage(snap.values), int(snap.values.get("elapsed_ms", 0)))
            elif kind == "error":
                yield error_event(payload)
            # "paused": approval_required was already emitted; the stream just ends
            while not queue.empty():                      # flush events emitted right before the control item
                late = queue.get_nowait()
                if isinstance(late, AgentEvent):
                    yield late
            return
    finally:
        if not task.done():                               # client disconnected (or generator closed): cancel cleanly
            handle.cancel.set()
            task.cancel()
        rt.runs.pop(thread_id, None)


def _usage(values: dict[str, Any]) -> tuple[int, int]:
    u = values.get("usage") or ZERO_USAGE
    return int(u.get("inputTokens", 0)), int(u.get("outputTokens", 0))


async def sse(it: AsyncIterator[AgentEvent | str]) -> AsyncIterator[str]:
    async for item in it:
        yield item if isinstance(item, str) else item.to_sse()


def start_stream(rt: Runtime, req: InvestigateRequest, faults: FaultSpec | None = None, variant: str = "AGENT") -> AsyncIterator[AgentEvent | str]:
    meta = {"user_id": req.user_id, "investigation_id": req.investigation_id, "thread_id": req.thread_id, "options": req.options, "now": req.now}
    return stream_events(rt, thread_id=req.thread_id, graph_input=initial_state(req), req_meta=meta, resuming=False, faults=faults, variant=variant)


async def resume_stream(rt: Runtime, thread_id: str, req: ResumeRequest) -> AsyncIterator[AgentEvent | str]:
    config = {"configurable": {"thread_id": thread_id}}
    snap = await rt.graph.aget_state(config)
    vals = snap.values
    from app.agents.runtime import InvestigateOptions
    meta = {"user_id": vals["user_id"], "investigation_id": req.investigation_id, "thread_id": thread_id,
            "options": InvestigateOptions.model_validate(vals["options"]), "now": vals["now"]}
    decisions = [d.wire() for d in req.decisions]
    async for item in stream_events(rt, thread_id=thread_id, graph_input=Command(resume={"decisions": decisions}), req_meta=meta, resuming=True):
        yield item


async def cancel_thread(rt: Runtime, thread_id: str) -> bool:
    handle = rt.runs.get(thread_id)
    if handle is not None:                                # running: cooperative flag + task cancellation
        handle.cancel.set()
        if handle.task is not None:
            handle.task.cancel()
        return True
    config = {"configurable": {"thread_id": thread_id}}
    snap = await rt.graph.aget_state(config)
    if snap.next:                                         # paused at the approval gate: mark cancelled so a later resume is refused
        await rt.graph.aupdate_state(config, {"cancelled": True, "status": "CANCELLED"})
        return True
    return False


_ = threading
