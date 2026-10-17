"""Provider-agnostic LLM factory (AI-FD-03): gemini (default) | ollama | groq (optional), tenacity backoff on 429/5xx,
typed errors. AI A ships it; AI B uses it. Imports of provider packages are lazy so ingestion needs none of them."""
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, TypeVar

from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.core.config import Settings

log = logging.getLogger(__name__)
T = TypeVar("T")


class LlmError(Exception):
    code = "INTERNAL_ERROR"


class LlmRateLimited(LlmError):
    """Retries exhausted on 429 / quota. Spring maps this to LLM_RATE_LIMITED."""

    code = "LLM_RATE_LIMITED"


class LlmUnavailable(LlmError):
    """Retries exhausted on 5xx / connection errors. Spring maps this to AI_SERVICE_UNAVAILABLE."""

    code = "AI_SERVICE_UNAVAILABLE"


class LlmConfigError(LlmError):
    pass


def classify_llm_error(exc: BaseException) -> str | None:
    """Return 'rate_limit', 'server' or None (not retryable) for provider-specific exceptions."""
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    resp = getattr(exc, "response", None)
    if status is None and resp is not None:
        status = getattr(resp, "status_code", None)
    name = type(exc).__name__.lower()
    text = str(exc).lower()
    if status == 429 or "ratelimit" in name or "resourceexhausted" in name or "429" in text[:200] or "quota" in text[:200]:
        return "rate_limit"
    if (isinstance(status, int) and 500 <= status < 600) or any(
        k in name for k in ("serviceunavailable", "internalservererror", "timeout", "connecterror", "connectionerror")
    ):
        return "server"
    return None


def _retryable(exc: BaseException) -> bool:
    return classify_llm_error(exc) is not None


def _wrap_final(retry_state: RetryCallState) -> Any:
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    kind = classify_llm_error(exc) if exc else None
    if kind == "rate_limit":
        raise LlmRateLimited("LLM rate limit persisted after retries") from exc
    raise LlmUnavailable("LLM provider unavailable after retries") from exc


def with_backoff(fn: Callable[..., T], *args: Any, max_attempts: int = 5, **kwargs: Any) -> T:
    """Call fn with exponential backoff + jitter on 429/5xx. Raises LlmRateLimited / LlmUnavailable at the end."""
    r = retry(
        retry=retry_if_exception(_retryable),
        stop=stop_after_attempt(max(1, max_attempts)),
        wait=wait_exponential_jitter(initial=1, max=20),
        retry_error_callback=_wrap_final,
        reraise=False,
    )
    return r(fn)(*args, **kwargs)


async def awith_backoff(fn: Callable[..., Any], *args: Any, max_attempts: int = 5, **kwargs: Any) -> Any:
    r = retry(
        retry=retry_if_exception(_retryable),
        stop=stop_after_attempt(max(1, max_attempts)),
        wait=wait_exponential_jitter(initial=1, max=20),
        retry_error_callback=_wrap_final,
        reraise=False,
    )
    return await r(fn)(*args, **kwargs)


def get_llm(settings: Settings, *, temperature: float = 0.0) -> Any:
    """Return a LangChain chat model for the configured provider. Models/keys come from env only."""
    p = settings.llm_provider
    if p == "gemini":
        if not (settings.gemini_api_key and settings.gemini_model):
            raise LlmConfigError("GEMINI_API_KEY and GEMINI_MODEL are required for LLM_PROVIDER=gemini")
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=settings.gemini_model, google_api_key=settings.gemini_api_key,
            temperature=temperature, max_retries=0, timeout=settings.llm_timeout_s,
        )
    if p == "ollama":
        if not settings.ollama_model:
            raise LlmConfigError("OLLAMA_MODEL is required for LLM_PROVIDER=ollama")
        from langchain_ollama import ChatOllama

        return ChatOllama(model=settings.ollama_model, base_url=settings.ollama_base_url, temperature=temperature)
    if p == "groq":
        if not (settings.groq_api_key and settings.groq_model):
            raise LlmConfigError("GROQ_API_KEY and GROQ_MODEL are required for LLM_PROVIDER=groq")
        from langchain_groq import ChatGroq

        return ChatGroq(model=settings.groq_model, api_key=settings.groq_api_key, temperature=temperature, max_retries=0)
    raise LlmConfigError(f"Unknown LLM_PROVIDER {p}")
