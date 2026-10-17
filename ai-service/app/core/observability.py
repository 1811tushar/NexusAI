"""Optional Langfuse tracing (AI-OB-01 foundation). No-op without keys; masks PII before anything leaves the service.
Thin helper only: AI B wires spans per node/tool. Not exercised against a live Langfuse in AI A's tests.
"""
from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from app.core.config import Settings
from app.core.pii import redact_text

log = logging.getLogger(__name__)
_client: Any = None


def init_observability(settings: Settings) -> bool:
    global _client
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        log.info("Langfuse disabled (no keys)")
        return False
    try:
        from langfuse import Langfuse

        _client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host or "https://cloud.langfuse.com",
        )
        log.info("Langfuse enabled")
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("Langfuse init failed, tracing disabled: %s", type(exc).__name__)
        _client = None
        return False


def mask(value: Any) -> Any:
    """Redact PII from strings (recursively in dict/list) before sending to a tracing backend."""
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {k: mask(v) for k, v in value.items()}
    if isinstance(value, list):
        return [mask(v) for v in value]
    return value


@contextmanager
def span(name: str, **metadata: Any) -> Iterator[None]:
    """`with span("retrieve", k=8): ...`. Never raises because of tracing."""
    ctx = None
    if _client is not None:
        try:
            ctx = _client.start_as_current_span(name=name, metadata=mask(metadata))
            ctx.__enter__()
        except Exception:  # noqa: BLE001
            ctx = None
    try:
        yield
    finally:
        if ctx is not None:
            try:
                ctx.__exit__(None, None, None)
            except Exception:  # noqa: BLE001
                pass


def shutdown() -> None:
    if _client is not None:
        try:
            _client.flush()
        except Exception:  # noqa: BLE001
            pass
