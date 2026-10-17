"""RunContext: everything a node needs that is NOT checkpointed (pools, LLM, emit, cancel flag, tool budgets, usage meter).
It travels in `config["configurable"]["ctx"]`; the checkpointed AgentState holds only JSON-able data."""
from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.agents import events as ev
from app.agents.failure import FailureTracker
from app.agents.llm_runtime import Llm, LlmReply
from app.api.schemas import AgentEvent, InvestigateOptions
from app.tools.registry import RunTools


class RunCancelled(Exception):
    """Raised cooperatively between LLM/tool calls when the run was cancelled (or the client disconnected)."""


@dataclass
class FaultSpec:
    """Fault injection for tests / the TOOL_FAILURE eval category: tool -> 'timeout' | 'error' | 'empty' | 'vector_failure'."""
    tool_faults: dict[str, str] = field(default_factory=dict)
    remaining: dict[str, int] = field(default_factory=dict)       # tool -> how many calls to fault (default: all)

    def take(self, tool: str) -> str | None:
        mode = self.tool_faults.get(tool)
        if mode is None:
            return None
        left = self.remaining.get(tool)
        if left is not None:
            if left <= 0:
                return None
            self.remaining[tool] = left - 1
        return mode


@dataclass
class RunContext:
    settings: Any
    embedder: Any
    retriever: Any
    ro_pool: Any
    rw_pool: Any
    llm: Llm
    tools: RunTools
    user_id: int
    investigation_id: int
    thread_id: str
    options: InvestigateOptions
    now: str
    emit: Callable[[AgentEvent], None] = lambda e: None
    cancel: threading.Event = field(default_factory=threading.Event)
    web_search_fn: Callable[[str, int], list[dict[str, Any]]] | None = None
    faults: FaultSpec | None = None
    resuming: bool = False
    variant: str = "AGENT"          # AGENT | AGENT_NO_VERIFIER (evaluation ablation)
    failures: FailureTracker = field(default_factory=FailureTracker)
    log: logging.Logger = field(default_factory=lambda: logging.getLogger("app.agents"))
    sleep: Callable[[float], None] = threading.Event().wait
    _in: int = 0
    _out: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)
    flagged_chunks: set[int] = field(default_factory=set)

    @property
    def document_ids(self) -> list[int] | None:
        return self.options.document_ids or None

    def check_cancel(self) -> None:
        if self.cancel.is_set():
            raise RunCancelled()

    def guardrail(self, stage: str, action: str, category: str, detail: str) -> None:
        self.emit(ev.guardrail(stage, action, category, detail))

    def llm_call(self, tag: str, system: str, user: str) -> LlmReply:
        self.check_cancel()
        reply = self.llm.complete(tag=tag, system=system, user=user)
        self.add_usage(reply.input_tokens, reply.output_tokens)
        return reply

    def add_usage(self, in_tokens: int, out_tokens: int) -> None:
        with self._lock:
            self._in += in_tokens
            self._out += out_tokens

    def take_usage(self) -> dict[str, int]:
        with self._lock:
            d = {"inputTokens": self._in, "outputTokens": self._out}
            self._in = self._out = 0
            return d
