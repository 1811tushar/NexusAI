"""LLM-as-judge (AI-EV-05, ADD-EV-04): the configured provider (same as the system under test; documented) judges, per expected fact, whether the answer states it,
and whether the answer hallucinates. Prompt: agents/prompts/judge.md. Deterministic checks (numbers, abstention, forbidden text, invented numbers) live in
metrics.py and ALWAYS run; the judge only adds coverage/hallucination opinions. mode='keyword' disables the LLM (CI, offline)."""
from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, ValidationError

from app.agents.llm_runtime import Llm, extract_json
from app.agents.prompts_loader import prompt_version, render

log = logging.getLogger(__name__)


class JudgeOut(BaseModel):
    covered: list[bool]
    hallucinated: bool = False
    explanation: str = ""


class Judge:
    def __init__(self, llm: Llm | None, mode: str = "llm") -> None:
        self.llm, self.mode = llm, mode
        self.tokens = 0

    @property
    def description(self) -> str:
        return f"{self.mode} judge, prompt judge.md v{prompt_version('judge')}"

    def evaluate(self, item: dict[str, Any], answer: str) -> dict[str, Any] | None:
        if self.mode != "llm" or self.llm is None or not item["expectedFacts"] or not answer.strip():
            return None
        if item["shouldBlock"] or item["mustAbstain"]:
            return None                                   # decided deterministically (status / abstention + no numbers)
        system, user = render("judge", question=item["question"], facts="\n".join(f"{i + 1}. {f}" for i, f in enumerate(item["expectedFacts"])), answer=answer[:5000])
        for _ in range(2):
            try:
                reply = self.llm.complete(tag="judge", system=system, user=user)
                self.tokens += reply.input_tokens + reply.output_tokens
                out = JudgeOut.model_validate(extract_json(reply.text))
                out.covered = (out.covered + [False] * len(item["expectedFacts"]))[:len(item["expectedFacts"])]
                return out.model_dump()
            except (ValueError, ValidationError):
                continue
            except Exception as exc:  # noqa: BLE001  a judge outage must not abort an evaluation
                log.warning("judge unavailable: %s", type(exc).__name__)
                return None
        return None
