"""App factory + lifespan (AI-FD-01..05). Run:  uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000

HOW AI B ADDS ROUTES (nothing else in this file needs to change):
    1. create app/api/routes/investigate.py (+ memories.py, admin_eval.py) exposing `router = APIRouter(prefix="/internal", ...)`
    2. add them to INTERNAL_ROUTERS below. They automatically get the X-Internal-API-Key dependency.
    3. build the graph in `build_state()` extension point or in your route using request.app.state.{settings, embedder,
       rw_pool, ro_pool, store, retriever, checkpointer}.
"""
from __future__ import annotations

import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import psycopg
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from psycopg_pool import PoolTimeout

from app.api.routes import admin_eval, health, ingest, investigate, memories, search
from app.api.schemas import ErrorCode, InternalError
from app.api.security import ApiError, require_api_key
from app.core import observability
from app.core.config import Settings, get_settings
from app.core.db import detect_capabilities, ensure_ai_schema, open_ro_pool, open_rw_pool
from app.core.embeddings import load_embedder
from app.core.llm import LlmError
from app.core.logging import configure_logging, request_id_var
from app.memory.checkpointer import close_checkpointer, setup_checkpointer
from app.rag.errors import IngestionError
from app.rag.retriever import Retriever
from app.rag.vector_store import VectorStore

log = logging.getLogger("app")

# AI B: append `investigate.router`, `memories.router`, `admin_eval.router` here.
INTERNAL_ROUTERS = [ingest.router, search.router, investigate.router, memories.router, admin_eval.router]


class RequestIdMiddleware:
    """Pure ASGI (does not buffer streams, so SSE routes by AI B are safe)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope["headers"])
        rid = (headers.get(b"x-request-id") or b"").decode()[:64] or str(uuid.uuid4())
        token = request_id_var.set(rid)

        async def send_with_id(message):
            if message["type"] == "http.response.start":
                message.setdefault("headers", []).append((b"x-request-id", rid.encode()))
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            request_id_var.reset(token)


def _error(status: int, code: ErrorCode, message: str, *, retryable: bool = False, details=None) -> JSONResponse:
    body = InternalError(code=code, message=message, retryable=retryable, request_id=request_id_var.get(), details=details)
    return JSONResponse(body.wire(), status_code=status)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging(settings.log_level)
        t0 = time.monotonic()
        app.state.settings = settings
        app.state.embedder = load_embedder(settings)                       # loaded ONCE
        app.state.rw_pool = open_rw_pool(settings)                         # role ai_rw, schema ai
        app.state.ro_pool = open_ro_pool(settings)                         # role ai_readonly, read-only session (AI B's sql tool)
        ensure_ai_schema(app.state.rw_pool)                                # idempotent DDL (contract 10.2)
        app.state.caps = detect_capabilities(app.state.rw_pool)
        app.state.store = VectorStore(app.state.rw_pool, app.state.caps)
        app.state.retriever = Retriever(app.state.store, app.state.embedder, settings)
        app.state.checkpointer = await setup_checkpointer(settings, app.state.rw_pool)   # AI B replaces the stub
        observability.init_observability(settings)
        log.info("ai-service ready", extra={"startupMs": int((time.monotonic() - t0) * 1000),
                                            "pgvector": app.state.caps.pgvector_version,
                                            "iterativeScan": app.state.caps.iterative_scan})
        try:
            yield
        finally:
            await close_checkpointer(app.state.checkpointer)
            observability.shutdown()
            app.state.rw_pool.close()
            app.state.ro_pool.close()

    app = FastAPI(title="NexusAI ai-service (internal)", version="2.1", lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)   # internal only; no public docs surface
    app.add_middleware(RequestIdMiddleware)
    app.include_router(health.router)
    for r in INTERNAL_ROUTERS:
        app.include_router(r, dependencies=[Depends(require_api_key)])

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError):
        return _error(exc.status_code, exc.code, exc.message, retryable=exc.retryable, details=exc.details)

    @app.exception_handler(IngestionError)
    async def _ingestion(_: Request, exc: IngestionError):
        return _error(422, ErrorCode.INGESTION_FAILED, str(exc))

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        details = {".".join(str(p) for p in e["loc"] if p != "body"): e["msg"] for e in exc.errors()}
        return _error(400, ErrorCode.VALIDATION_FAILED, "Request validation failed", details=details)

    @app.exception_handler(LlmError)
    async def _llm(_: Request, exc: LlmError):
        code = ErrorCode(exc.code) if exc.code in ErrorCode._value2member_map_ else ErrorCode.INTERNAL_ERROR
        return _error(503 if code != ErrorCode.INTERNAL_ERROR else 500, code, str(exc), retryable=True)

    @app.exception_handler(psycopg.OperationalError)
    @app.exception_handler(PoolTimeout)
    async def _db_down(_: Request, exc: Exception):
        log.error("database unavailable: %s", type(exc).__name__)
        return _error(503, ErrorCode.AI_SERVICE_UNAVAILABLE, "The AI service database is unavailable", retryable=True)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        log.error("unhandled error: %s", type(exc).__name__, exc_info=True)   # formatter logs the class only, no stack/args
        return _error(500, ErrorCode.INTERNAL_ERROR, "Internal error")

    return app
