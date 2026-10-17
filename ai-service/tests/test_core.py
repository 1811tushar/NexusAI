import json
import logging

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.embeddings import HashingEmbedder
from app.core.llm import LlmRateLimited, LlmUnavailable, classify_llm_error, with_backoff
from app.core.logging import JsonFormatter, _SafeFilter


def test_settings_fail_fast_without_secrets(monkeypatch):
    for k in ("INTERNAL_API_KEY", "AI_DB_RW_PASSWORD", "AI_DB_RO_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(ValidationError) as e:
        Settings(_env_file=None)
    assert {"internal_api_key", "ai_db_rw_password", "ai_db_ro_password"} <= {x["loc"][0] for x in e.value.errors()}


def test_settings_reject_placeholder_and_bad_overlap():
    base = dict(_env_file=None, ai_db_rw_password="x", ai_db_ro_password="y")
    with pytest.raises(ValidationError):
        Settings(internal_api_key="changeme", **base)
    with pytest.raises(ValidationError):
        Settings(internal_api_key="k" * 20, chunk_tokens=200, chunk_overlap_tokens=200, **base)


def test_hashing_embedder_deterministic_normalised_and_lexical():
    e = HashingEmbedder()
    a, b, c = e.embed_documents(["revenue fell south region", "revenue fell south region", "marketing budget west"])
    assert a == b and len(a) == 384 and abs(sum(x * x for x in a) - 1) < 1e-4
    q = e.embed_query("south revenue")
    assert sum(x * y for x, y in zip(q, a, strict=True)) > sum(x * y for x, y in zip(q, c, strict=True))


def test_logs_never_contain_document_text_or_pii():
    rec = logging.LogRecord("t", logging.INFO, "", 0, "email bob@corp.io " + "secret document text " * 100, (), None)
    _SafeFilter().filter(rec)
    out = json.loads(JsonFormatter().format(rec))
    assert "bob@corp.io" not in out["msg"] and len(out["msg"]) < 560 and "truncated" in out["msg"]


class _E(Exception):
    def __init__(self, status):
        super().__init__(f"http {status}")
        self.status_code = status


def test_llm_error_classification_and_backoff(monkeypatch):
    monkeypatch.setattr("tenacity.nap.time.sleep", lambda s: None)
    assert classify_llm_error(_E(429)) == "rate_limit" and classify_llm_error(_E(503)) == "server"
    assert classify_llm_error(ValueError("bad")) is None
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise _E(429)
        return "ok"

    assert with_backoff(flaky, max_attempts=5) == "ok" and calls["n"] == 3
    with pytest.raises(LlmRateLimited):
        with_backoff(lambda: (_ for _ in ()).throw(_E(429)), max_attempts=2)
    with pytest.raises(LlmUnavailable):
        with_backoff(lambda: (_ for _ in ()).throw(_E(500)), max_attempts=2)
    with pytest.raises(ValueError):                    # non-transient errors are not retried or wrapped
        with_backoff(lambda: (_ for _ in ()).throw(ValueError("x")), max_attempts=3)
