"""ScriptedLlm + FaultyLlm: deterministic stand-ins for the LLM (tests, CI gate, offline eval smoke runs). Never used in production code paths."""
from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from typing import Any

from app.agents.llm_runtime import LlmReply


class ScriptedLlm:
    """script: tag -> item | [items] | callable(system, user, n). An item is str, dict/list (json-dumped) or an Exception (raised).
    A list is consumed in order; the LAST item repeats forever. Unscripted tags raise AssertionError so tests fail loudly."""

    def __init__(self, script: dict[str, Any], default: Any = None) -> None:
        self.script, self.default = dict(script), default
        self.calls: list[dict[str, str]] = []
        self._n: dict[str, int] = {}

    def _next(self, tag: str, system: str, user: str) -> Any:
        n = self._n.get(tag, 0)
        self._n[tag] = n + 1
        item = self.script.get(tag, self.default)
        if item is None:
            raise AssertionError(f"ScriptedLlm: no script for tag '{tag}'")
        if callable(item):
            return item(system, user, n)
        if isinstance(item, list):
            return item[min(n, len(item) - 1)]
        return item

    def complete(self, *, tag: str, system: str, user: str) -> LlmReply:
        self.calls.append({"tag": tag, "system": system, "user": user})
        item = self._next(tag, system, user)
        if isinstance(item, BaseException):
            raise item
        text = item if isinstance(item, str) else json.dumps(item)
        return LlmReply(text, (len(system) + len(user)) // 4, len(text) // 4)

    def stream(self, *, tag: str, system: str, user: str) -> Iterator[str]:
        text = self.complete(tag=tag, system=system, user=user).text
        for i in range(0, len(text), 40):
            yield text[i:i + 40]

    def tags(self) -> list[str]:
        return [c["tag"] for c in self.calls]


class FaultyLlm:
    """Wraps another Llm and injects a fault for one tag: mode 'rate_limit' (LlmRateLimited), 'unavailable', 'malformed' (not JSON), 'empty'."""

    def __init__(self, inner: Any, tag: str, mode: str, times: int = 10_000) -> None:
        self.inner, self.tag, self.mode, self.left = inner, tag, mode, times

    def _fault(self, tag: str) -> Callable[[], LlmReply] | None:
        if tag != self.tag or self.left <= 0:
            return None
        self.left -= 1
        from app.core.llm import LlmRateLimited, LlmUnavailable
        if self.mode == "rate_limit":
            raise LlmRateLimited("injected 429")
        if self.mode == "unavailable":
            raise LlmUnavailable("injected outage")
        text = "this is not json" if self.mode == "malformed" else ""
        return lambda: LlmReply(text, 1, 1)

    def complete(self, *, tag: str, system: str, user: str) -> LlmReply:
        f = self._fault(tag)
        return f() if f else self.inner.complete(tag=tag, system=system, user=user)

    def stream(self, *, tag: str, system: str, user: str) -> Iterator[str]:
        f = self._fault(tag)
        if f:
            yield f().text
            return
        yield from self.inner.stream(tag=tag, system=system, user=user)
