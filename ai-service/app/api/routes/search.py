"""POST /internal/search: library search (hybrid by default)."""
from __future__ import annotations

from fastapi import APIRouter, Request

from app.api.schemas import SearchRequest, SearchResultDTO
from app.rag.citations import make_snippet

router = APIRouter(prefix="/internal", tags=["search"])


@router.post("/search", response_model=list[SearchResultDTO], response_model_by_alias=True)
def search(request: Request, req: SearchRequest):
    chunks = request.app.state.retriever.search(req.query, mode=req.mode, k=req.k, document_ids=req.document_ids)
    return [
        SearchResultDTO(chunk_id=c.chunk_id, document_id=c.document_id, document_title=c.document_title, page=c.page,
                        section=c.section, snippet=make_snippet(c.content, req.query), score=round(c.score, 6))
        for c in chunks
    ]
