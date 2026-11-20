"""Thin LLM interface used by every node. Provider-agnostic (Gemini/Ollama/Groq via core.llm.get_llm) and trivially replaceable in tests
(ScriptedLlm in agents/testing.py). Calls are made with the tenacity backoff of core.llm; a persistent 429 surfaces as LlmRateLimited."""
from __future__ import annotations

import json
import threading
import time
from collections import deque
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Protocol

from app.core.config import get_settings
from app.core.llm import LlmUnavailable, classify_llm_error, with_backoff


@dataclass
class LlmReply:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0


class Llm(Protocol):
    def complete(self, *, tag: str, system: str, user: str) -> LlmReply: ...
    def stream(self, *, tag: str, system: str, user: str) -> Iterator[str]: ...


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(p if isinstance(p, str) else str(p.get("text", "")) for p in content if isinstance(p, (str, dict)))
    return str(content or "")


class _Pacer:
    """Sliding 60 s window over request count and estimated prompt tokens. Keeps a free-tier key under its per-minute limits by WAITING instead of
    hitting 429s (the retry backoff of core.llm only covers ~12 s, far less than a minute window). Disabled while both limits are 0."""

    def __init__(self, max_rpm: int, max_tpm: int) -> None:
        self.max_rpm, self.max_tpm = max_rpm, max_tpm
        self._lock = threading.Lock()
        self._events: deque[tuple[float, int]] = deque()

    def acquire(self, tokens: int) -> None:
        if not (self.max_rpm or self.max_tpm):
            return
        while True:
            with self._lock:
                now = time.monotonic()
                while self._events and now - self._events[0][0] >= 60.0:
                    self._events.popleft()
                used = sum(t for _, t in self._events)
                rpm_ok = not self.max_rpm or len(self._events) < self.max_rpm
                tpm_ok = not self.max_tpm or not self._events or used + tokens <= self.max_tpm
                if rpm_ok and tpm_ok:
                    self._events.append((now, tokens))
                    return
                wait = 60.0 - (now - self._events[0][0]) + 0.05
            time.sleep(max(wait, 0.05))


_PACERS: dict[str, _Pacer] = {}


def _pacer() -> _Pacer:
    """One process-wide window shared by every investigation."""
    if "llm" not in _PACERS:
        s = get_settings()
        _PACERS["llm"] = _Pacer(s.llm_max_rpm, s.llm_max_tpm)
    return _PACERS["llm"]


class LangChainLlm:
    """Wraps a LangChain chat model (the object returned by core.llm.get_llm)."""

    def __init__(self, model: Any, max_attempts: int = 4) -> None:
        self.model, self.max_attempts = model, max_attempts

    def _messages(self, system: str, user: str) -> list[Any]:
        from langchain_core.messages import HumanMessage, SystemMessage
        return [SystemMessage(content=system), HumanMessage(content=user)]

    def complete(self, *, tag: str, system: str, user: str) -> LlmReply:
        msgs = self._messages(system, user)
        try:
            _pacer().acquire((len(system) + len(user)) // 4)
            msg = with_backoff(self.model.invoke, msgs, max_attempts=self.max_attempts)
        except Exception as exc:  # noqa: BLE001
            if classify_llm_error(exc) is None and not type(exc).__name__.startswith("Llm"):
                raise LlmUnavailable("LLM call failed") from exc
            raise
        usage = getattr(msg, "usage_metadata", None) or {}
        text = _text(getattr(msg, "content", ""))
        return LlmReply(text, int(usage.get("input_tokens", (len(system) + len(user)) // 4)), int(usage.get("output_tokens", len(text) // 4)))

    def stream(self, *, tag: str, system: str, user: str) -> Iterator[str]:
        msgs = self._messages(system, user)
        try:
            _pacer().acquire((len(system) + len(user)) // 4)
            for chunk in self.model.stream(msgs):
                t = _text(getattr(chunk, "content", ""))
                if t:
                    yield t
        except Exception as exc:  # noqa: BLE001
            if classify_llm_error(exc) == "rate_limit":
                from app.core.llm import LlmRateLimited
                raise LlmRateLimited("LLM rate limit") from exc
            raise LlmUnavailable("LLM stream failed") from exc


def extract_json(text: str) -> Any:
    """First balanced JSON object/array in `text` (models wrap JSON in fences or add chatter). Raises ValueError."""
    s = text.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s
        s = s.rsplit("```", 1)[0]
    start = next((i for i, ch in enumerate(s) if ch in "{["), -1)
    if start < 0:
        raise ValueError("no JSON found")
    depth, in_str, esc = 0, False, False
    for i in range(start, len(s)):
        ch = s[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
            if depth == 0:
                return json.loads(s[start:i + 1])
    raise ValueError("unterminated JSON")
