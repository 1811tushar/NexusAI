"""Thin LLM interface used by every node. Provider-agnostic (Gemini/Ollama/Groq via core.llm.get_llm) and trivially replaceable in tests
(ScriptedLlm in agents/testing.py). Calls are made with the tenacity backoff of core.llm; a persistent 429 surfaces as LlmRateLimited."""
from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Protocol

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
