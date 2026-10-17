"""Structured LLM outputs (AI-SF-02, ADD-GR-04): parse JSON -> validate with Pydantic -> ONE repair retry -> caller's safe fallback.
When the repair also fails a guardrail_triggered(OUTPUT, FLAGGED, INVALID_OUTPUT) event is emitted (detail has no model text)."""
from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.agents.context import RunContext
from app.agents.llm_runtime import extract_json

M = TypeVar("M", bound=BaseModel)


def call_structured(ctx: RunContext, tag: str, system: str, user: str, model: type[M], *, repair: bool = True) -> M | None:
    last_error = ""
    prompt_user = user
    for attempt in (0, 1) if repair else (0,):
        reply = ctx.llm_call(tag, system, prompt_user)
        try:
            return model.model_validate(extract_json(reply.text))
        except (ValueError, ValidationError) as exc:
            last_error = str(exc).splitlines()[0][:200]
            prompt_user = (user + "\n\nYour previous reply was not valid for the required JSON schema (" + last_error +
                           "). Reply again with ONLY the corrected JSON object, no extra text.")
            ctx.log.warning("structured output invalid for %s (attempt %d): %s", tag, attempt + 1, last_error)
    ctx.guardrail("OUTPUT", "FLAGGED", "INVALID_OUTPUT", f"The {tag} step returned an invalid structure twice; a safe fallback was used.")
    return None
