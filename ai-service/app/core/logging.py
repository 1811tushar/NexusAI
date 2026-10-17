"""JSON logging with request id. Never logs document text (AI-FD-06): messages are PII-redacted and truncated."""
from __future__ import annotations

import contextvars
import json
import logging
import sys
from datetime import UTC, datetime

from app.core.pii import redact_text

request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)
MAX_MESSAGE_CHARS = 500
_STD = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}


class _SafeFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        msg = redact_text(msg)
        if len(msg) > MAX_MESSAGE_CHARS:
            msg = msg[:MAX_MESSAGE_CHARS] + f"...[truncated {len(msg) - MAX_MESSAGE_CHARS} chars]"
        record.msg, record.args = msg, ()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out = {
            "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "requestId": request_id_var.get(),
        }
        for k, v in record.__dict__.items():  # structured extras, e.g. logger.info("x", extra={"documentId": 3})
            if k not in _STD and not k.startswith("_"):
                out[k] = v if isinstance(v, (int, float, bool, type(None))) else str(v)[:200]
        if record.exc_info:
            out["exc"] = record.exc_info[0].__name__ if record.exc_info[0] else None  # no stack/args (may hold text)
        return json.dumps(out, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(_SafeFilter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    for noisy in ("uvicorn.access", "httpx", "httpcore", "sentence_transformers"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
