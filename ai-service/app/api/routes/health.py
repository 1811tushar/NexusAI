from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.api.schemas import HealthResponse
from app.core.db import ping

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, response_model_by_alias=True)
def health(request: Request):
    st = request.app.state
    ok = ping(st.rw_pool) and ping(st.ro_pool)
    body = HealthResponse(status="ok" if ok else "degraded", embedding_model=st.embedder.name,
                          llm_provider=st.settings.llm_provider)
    return JSONResponse(body.wire(), status_code=200 if ok else 503)   # Docker healthcheck needs a failing code
