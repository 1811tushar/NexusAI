"""POST /internal/ingest (multipart: `meta` JSON + `file`), DELETE /internal/documents/{id}, GET .../chunks."""
from __future__ import annotations

import math

from fastapi import APIRouter, File, Form, Query, Request, UploadFile
from pydantic import ValidationError

from app.api.schemas import (
    ChunkDTO,
    DeleteDocumentResponse,
    ErrorCode,
    IngestRequest,
    IngestResponse,
    PagedResponse,
)
from app.api.security import ApiError
from app.rag.ingest_pipeline import ingest_document

router = APIRouter(prefix="/internal", tags=["ingest"])


@router.post("/ingest", response_model=IngestResponse, response_model_by_alias=True)
def ingest(request: Request, meta: str = Form(...), file: UploadFile = File(...)):
    st = request.app.state
    try:
        req = IngestRequest.model_validate_json(meta)
    except ValidationError as exc:
        raise ApiError(400, ErrorCode.VALIDATION_FAILED, "Invalid `meta` JSON",
                       details={".".join(map(str, e["loc"])): e["msg"] for e in exc.errors()}) from exc
    limit = st.settings.max_upload_bytes
    data = file.file.read(limit + 1)
    if len(data) > limit:
        raise ApiError(413, ErrorCode.FILE_TOO_LARGE, f"File exceeds {st.settings.max_upload_mb} MB")
    return ingest_document(
        store=st.store, embedder=st.embedder, settings=st.settings, document_id=req.document_id,
        source_type=req.source_type.value, title=req.title, filename=req.filename, content=data,
    )


@router.delete("/documents/{document_id}", response_model=DeleteDocumentResponse, response_model_by_alias=True)
def delete_document(request: Request, document_id: int):
    return DeleteDocumentResponse(deleted=request.app.state.store.delete_document(document_id))


@router.get("/documents/{document_id}/chunks", response_model=PagedResponse[ChunkDTO], response_model_by_alias=True)
def list_chunks(request: Request, document_id: int, page: int = Query(0, ge=0), size: int = Query(20, ge=1, le=100)):
    rows, total = request.app.state.store.list_chunks(document_id, page, size)
    return PagedResponse[ChunkDTO](
        items=[ChunkDTO(id=r["id"], chunk_index=r["chunk_index"], page=r["page"], section=r["section"], content=r["content"])
               for r in rows],
        page=page, size=size, total_items=total, total_pages=math.ceil(total / size) if total else 0,
    )
