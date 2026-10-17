"""Tool registry (AI-TL-01): every tool has an args schema, a RISK TAG, the agents allowed to call it, a timeout and a per-run call budget.
Calls are validated BEFORE execution (unknown tool, wrong agent, bad args, budget exhausted -> ToolError with a readable reason the agent can use).
No tool in this registry can write data, send data to an arbitrary destination or execute an action (AI-SF-01): the only tags are read tags."""
from __future__ import annotations

import concurrent.futures as cf
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ValidationError

if TYPE_CHECKING:
    from app.agents.context import RunContext

READ_INTERNAL = "READ_INTERNAL"   # reads our own documents / read-only business tables / the user's own memories
READ_EXTERNAL = "READ_EXTERNAL"   # sends a (PII-redacted) sub-task query to a web search provider, reads results
RISK_TAGS = {READ_INTERNAL, READ_EXTERNAL}    # deliberately no write tag exists

_POOL = cf.ThreadPoolExecutor(max_workers=16, thread_name_prefix="tool")


class ToolError(Exception):
    """A tool call failed. `reason` is safe to show to the agent and to the user (no stack, no secrets)."""

    def __init__(self, reason: str, *, transient: bool = False) -> None:
        super().__init__(reason)
        self.reason = reason
        self.transient = transient


@dataclass
class EvidenceDraft:
    kind: str                     # DOCUMENT | SQL | STATS | WEB | MEMORY
    title: str
    snippet: str
    source: dict[str, Any] = field(default_factory=dict)
    data: dict[str, Any] | None = None
    chart: dict[str, Any] | None = None
    score: float | None = None


@dataclass
class ToolResult:
    summary: str                  # one line for the tool_result event
    observation: str              # what the agent sees (already wrapped as untrusted data where it contains outside text)
    evidence: list[EvidenceDraft] = field(default_factory=list)


@dataclass
class ToolSpec:
    name: str
    description: str
    args_model: type[BaseModel]
    risk_tag: str
    allowed_agents: frozenset[str]
    timeout_s: float
    budget: int
    fn: Callable[[RunContext, Any], ToolResult]

    def signature(self) -> str:
        fields = ", ".join(f"{k}: {_type_name(v.annotation)}{'' if v.is_required() else ' (optional)'}"
                           for k, v in self.args_model.model_fields.items())
        return f"{self.name}({fields}) - {self.description}"


def _type_name(t: Any) -> str:
    return getattr(t, "__name__", str(t)).replace("typing.", "")


class ToolRegistry:
    def __init__(self, specs: list[ToolSpec]) -> None:
        for s in specs:
            if s.risk_tag not in RISK_TAGS:
                raise ValueError(f"tool {s.name}: unknown risk tag {s.risk_tag}")
        self.specs = {s.name: s for s in specs}

    def names(self) -> list[str]:
        return sorted(self.specs)

    def for_agent(self, agent: str) -> list[ToolSpec]:
        return [s for s in self.specs.values() if agent in s.allowed_agents]

    def describe_for(self, agent: str) -> str:
        return "\n".join(f"- {s.signature()}" for s in self.for_agent(agent)) or "(no tools)"

    def validate(self, agent: str, name: str, raw_args: Any) -> tuple[ToolSpec, BaseModel]:
        spec = self.specs.get(name)
        if spec is None:
            raise ToolError(f"Unknown tool '{name}'. Available: {', '.join(s.name for s in self.for_agent(agent)) or 'none'}.")
        if agent not in spec.allowed_agents:
            raise ToolError(f"Tool '{name}' is not available to {agent}.")
        if not isinstance(raw_args, dict):
            raise ToolError("Tool arguments must be a JSON object.")
        try:
            return spec, spec.args_model.model_validate(raw_args)
        except ValidationError as exc:
            parts = [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()[:4]]
            raise ToolError("Invalid arguments for " + name + " -> " + "; ".join(parts)) from exc


class RunTools:
    """Per-run view: enforces the call budget and the timeout."""

    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry
        self.calls: dict[str, int] = {}
        self._lock = threading.Lock()

    def execute(self, ctx: RunContext, agent: str, name: str, raw_args: Any) -> ToolResult:
        spec, args = self.registry.validate(agent, name, raw_args)
        with self._lock:
            used = self.calls.get(name, 0)
            if used >= spec.budget:
                raise ToolError(f"Call budget for '{name}' is exhausted ({spec.budget} per investigation).")
            self.calls[name] = used + 1
        fut = _POOL.submit(spec.fn, ctx, args)
        try:
            return fut.result(timeout=spec.timeout_s)
        except cf.TimeoutError as exc:
            fut.cancel()
            raise ToolError(f"Tool '{name}' timed out after {spec.timeout_s:.0f}s.", transient=True) from exc
        except ToolError:
            raise
        except Exception as exc:  # noqa: BLE001  never leak internals
            ctx.log.error("tool %s crashed: %s", name, type(exc).__name__)
            raise ToolError(f"Tool '{name}' failed unexpectedly ({type(exc).__name__}).", transient=True) from exc
