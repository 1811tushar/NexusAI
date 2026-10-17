"""Runtime: the long-lived objects the investigate routes and the eval runner share (built lazily from app.state so main.py needs only the router line)."""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

from app.agents.context import FaultSpec, RunContext
from app.agents.graph import build_graph
from app.agents.llm_runtime import LangChainLlm, Llm
from app.api.schemas import InvestigateOptions  # noqa: F401  (re-used by runner)
from app.core.llm import get_llm
from app.tools.builder import build_registry
from app.tools.registry import RunTools
from app.tools.web_tool import default_web_search

_LOCK = threading.Lock()


@dataclass
class RunHandle:
    cancel: threading.Event = field(default_factory=threading.Event)
    task: Any = None


class Runtime:
    def __init__(self, *, settings: Any, embedder: Any, retriever: Any, rw_pool: Any, ro_pool: Any, checkpointer: Any,
                 llm: Llm | None = None, web_search_fn: Any = None) -> None:
        self.settings, self.embedder, self.retriever = settings, embedder, retriever
        self.rw_pool, self.ro_pool, self.checkpointer = rw_pool, ro_pool, checkpointer
        self._llm, self._web = llm, web_search_fn
        self.graph = build_graph(checkpointer)
        self.runs: dict[str, RunHandle] = {}

    @property
    def llm(self) -> Llm:
        if self._llm is None:
            self._llm = LangChainLlm(get_llm(self.settings), max_attempts=4)      # raises LlmConfigError if the provider key is missing
        return self._llm

    def make_ctx(self, *, user_id: int, investigation_id: int, thread_id: str, options: InvestigateOptions, now: str, emit: Any,
                 cancel: threading.Event, resuming: bool = False, faults: FaultSpec | None = None, variant: str = "AGENT",
                 single_agent: bool = False) -> RunContext:
        web_ok = bool(options.web_search and self.settings.web_search_enabled)
        web_fn = self._web or (default_web_search(self.settings) if web_ok else None)
        from app.agents.failure import FailureTracker
        return RunContext(settings=self.settings, embedder=self.embedder, retriever=self.retriever, ro_pool=self.ro_pool, rw_pool=self.rw_pool,
                          llm=self.llm, tools=RunTools(build_registry(self.settings, web_enabled=web_ok, single_agent=single_agent)), user_id=user_id,
                          investigation_id=investigation_id, thread_id=thread_id, options=options, now=now, emit=emit, cancel=cancel,
                          web_search_fn=web_fn, faults=faults, resuming=resuming, variant=variant,
                          failures=FailureTracker(max_attempts=self.settings.max_tool_attempts))


def runtime_for(app: Any) -> Runtime:
    rt = getattr(app.state, "runtime", None)
    if rt is None:
        with _LOCK:
            rt = getattr(app.state, "runtime", None)
            if rt is None:
                s = app.state
                rt = Runtime(settings=s.settings, embedder=s.embedder, retriever=s.retriever, rw_pool=s.rw_pool, ro_pool=s.ro_pool, checkpointer=s.checkpointer)
                app.state.runtime = rt
    return rt
