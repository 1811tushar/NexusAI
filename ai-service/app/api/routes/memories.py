"""Memory routes (AI-ME-03): list/search, delete one, delete all, and the user purge (memories + checkpoints). EVERY query is scoped by userId."""
from __future__ import annotations

import math

from fastapi import APIRouter, Query, Request

from app.api.schemas import MemoryDTO, PagedResponse
from app.memory import long_term

router = APIRouter(prefix="/internal", tags=["memories"])


@router.get("/memories", response_model=PagedResponse[MemoryDTO], response_model_by_alias=True)
def list_memories(request: Request, user_id: int = Query(alias="userId", ge=1), page: int = Query(0, ge=0), size: int = Query(20, ge=1, le=100),
                  q: str | None = Query(None, max_length=200)):
    rows, total = long_term.list_memories(request.app.state.rw_pool, user_id, page, size, q)
    items = [MemoryDTO(id=r["id"], summary=r["summary"], source_investigation_id=r["source_investigation_id"], importance=float(r["importance"]),
                       created_at=r["created_at"].isoformat(), last_accessed_at=r["last_accessed_at"].isoformat() if r["last_accessed_at"] else None) for r in rows]
    return PagedResponse[MemoryDTO](items=items, page=page, size=size, total_items=total, total_pages=math.ceil(total / size) if total else 0)


@router.delete("/memories/{memory_id}")
def delete_memory(request: Request, memory_id: int, user_id: int = Query(alias="userId", ge=1)) -> dict[str, int]:
    return {"deleted": long_term.delete_one(request.app.state.rw_pool, user_id, memory_id)}


@router.delete("/memories")
def delete_all_memories(request: Request, user_id: int = Query(alias="userId", ge=1)) -> dict[str, int]:
    return {"deleted": long_term.delete_all(request.app.state.rw_pool, user_id)}


@router.delete("/users/{user_id}")
def purge_user(request: Request, user_id: int) -> dict[str, int]:
    return long_term.purge_user(request.app.state.rw_pool, user_id)
