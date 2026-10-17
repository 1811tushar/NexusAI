"""One failure policy for every tool call (ADD-FH-01/02, AI-TL-02).
* every call has a timeout (registry) and at most MAX_TOOL_ATTEMPTS failed attempts per (step, tool);
* transient errors (timeout, connection) are retried with exponential backoff INSIDE the executor; fixable errors (SQL guard rejection, bad args)
  are fed back to the agent as an observation so it can correct its next attempt;
* after the last attempt: STOP and EXPLAIN. The failure is recorded as a limitation, the step is marked failed, the run continues with the remaining
  evidence. Nothing is invented and nothing is silently dropped."""
from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TypeVar

T = TypeVar("T")


@dataclass
class FailureTracker:
    max_attempts: int = 3
    failures: dict[tuple[str, str], list[str]] = field(default_factory=dict)   # (step_id, tool) -> reasons

    def record(self, step_id: str, tool: str, reason: str) -> int:
        self.failures.setdefault((step_id, tool), []).append(reason)
        return len(self.failures[(step_id, tool)])

    def exhausted(self, step_id: str, tool: str) -> bool:
        return len(self.failures.get((step_id, tool), [])) >= self.max_attempts

    def explanation(self, step_id: str, tool: str, what: str) -> str:
        reasons = self.failures.get((step_id, tool), [])
        last = reasons[-1] if reasons else "unknown error"
        return f"{what}: the '{tool}' tool failed {len(reasons)} time(s) and was stopped. Last reason: {last}"


def backoff_delay(attempt: int, base: float = 0.3, cap: float = 4.0) -> float:
    return min(cap, base * (2 ** max(0, attempt - 1)))


def call_with_transient_retry(fn: Callable[[], T], *, attempts: int, is_transient: Callable[[Exception], bool],
                              sleep: Callable[[float], None] = time.sleep) -> T:
    """Retry only transient failures, with exponential backoff; the last exception propagates."""
    last: Exception | None = None
    for n in range(1, max(1, attempts) + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            last = exc
            if not is_transient(exc) or n >= attempts:
                raise
            sleep(backoff_delay(n))
    raise last  # pragma: no cover
