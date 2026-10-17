"""HTTP contract (section 6) incl. auth, errors and ingestion failure reasons, against the real app + real Postgres."""
import json

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import HEADERS
from tests.helpers import encrypt_pdf, make_docx, make_pdf

TXT = b"# Q2 Report\n\n## Supplier incident\n\nA supplier incident delayed shipments in the South region.\n"


def meta(doc_id, st, name):
    return {"meta": json.dumps({"documentId": doc_id, "uploadedByUserId": 1, "sourceType": st, "title": name, "filename": name})}


def post(client, doc_id, st, name, data, ctype="application/octet-stream", headers=HEADERS):
    return client.post("/internal/ingest", data=meta(doc_id, st, name), files={"file": (name, data, ctype)}, headers=headers)


@pytest.fixture(autouse=True)
def _clean(store):
    return store


def test_health_needs_no_key(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok", "embeddingModel": "hashing", "llmProvider": "gemini"}
    assert r.headers["x-request-id"]


def test_request_id_is_echoed(client):
    assert client.get("/health", headers={"X-Request-Id": "abc-123"}).headers["x-request-id"] == "abc-123"


@pytest.mark.parametrize("method,path", [("post", "/internal/ingest"), ("post", "/internal/search"),
                                         ("delete", "/internal/documents/1"), ("get", "/internal/documents/1/chunks")])
def test_internal_routes_require_key(client, method, path):
    assert getattr(client, method)(path).status_code == 401
    assert getattr(client, method)(path, headers={"X-Internal-API-Key": "wrong"}).status_code == 401


def test_ingest_search_chunks_delete_roundtrip(client):
    r = post(client, 101, "MD", "report.md", TXT)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["documentId"] == 101 and body["chunkCount"] >= 1 and body["pageCount"] is None and body["warnings"] == []

    s = client.post("/internal/search", json={"query": "supplier incident south", "mode": "HYBRID", "k": 3}, headers=HEADERS)
    assert s.status_code == 200
    top = s.json()[0]
    assert set(top) == {"chunkId", "documentId", "documentTitle", "page", "section", "snippet", "score"}
    assert top["documentId"] == 101 and top["documentTitle"] == "report.md" and "supplier" in top["snippet"].lower()

    scoped = client.post("/internal/search", json={"query": "supplier", "documentIds": [555]}, headers=HEADERS).json()
    assert scoped == []

    c = client.get("/internal/documents/101/chunks?page=0&size=1", headers=HEADERS).json()
    assert set(c) == {"items", "page", "size", "totalItems", "totalPages"} and c["totalItems"] == body["chunkCount"]
    assert set(c["items"][0]) == {"id", "chunkIndex", "page", "section", "content"}

    d = client.delete("/internal/documents/101", headers=HEADERS)
    assert d.json() == {"deleted": body["chunkCount"]}
    assert client.get("/internal/documents/101/chunks", headers=HEADERS).json()["totalItems"] == 0


def test_pdf_has_page_numbers_and_docx_works(client):
    r = post(client, 102, "PDF", "a.pdf", make_pdf(["Revenue overview page one.", "Supplier incident page two."]))
    assert r.status_code == 200 and r.json()["pageCount"] == 2
    hit = client.post("/internal/search", json={"query": "supplier incident", "mode": "KEYWORD"}, headers=HEADERS).json()[0]
    assert hit["page"] == 2
    r = post(client, 103, "DOCX", "b.docx", make_docx([("Heading 1", "Pricing"), ("Normal", "Changes above ten percent need approval.")]))
    assert r.status_code == 200 and r.json()["pageCount"] is None


@pytest.mark.parametrize("st,name,data,needle", [
    ("PDF", "enc.pdf", lambda: encrypt_pdf(make_pdf(["secret page content here"])), "password"),
    ("PDF", "bad.pdf", lambda: b"%PDF-1.4 garbage", "PDF"),
    ("PDF", "scan.pdf", lambda: make_pdf(["", ""]), "scanned"),
    ("DOCX", "bad.docx", lambda: b"not a docx", "DOCX"),
    ("TXT", "empty.txt", lambda: b"   \n  ", "no readable text"),
])
def test_ingestion_failures_are_clear_422s(client, st, name, data, needle):
    r = post(client, 104, st, name, data())
    assert r.status_code == 422
    b = r.json()
    assert b["code"] == "INGESTION_FAILED" and needle.lower() in b["message"].lower()
    assert "Traceback" not in r.text and b["requestId"]


def test_validation_errors_are_400_with_details(client):
    r = client.post("/internal/search", json={"query": "", "k": 500}, headers=HEADERS)
    assert r.status_code == 400 and r.json()["code"] == "VALIDATION_FAILED" and r.json()["details"]
    r = client.post("/internal/ingest", data={"meta": "{not json"}, files={"file": ("a.txt", b"x")}, headers=HEADERS)
    assert r.status_code == 400 and r.json()["code"] == "VALIDATION_FAILED"


def test_file_too_large_is_413(settings):
    small = settings.model_copy(update={"max_upload_mb": 1})
    with TestClient(create_app(small), raise_server_exceptions=False) as c:
        r = post(c, 105, "TXT", "big.txt", b"a" * (1024 * 1024 + 5))
    assert r.status_code == 413 and r.json()["code"] == "FILE_TOO_LARGE"


def test_no_stack_trace_on_unexpected_error(client, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("secret internals /etc/passwd")
    monkeypatch.setattr(client.app.state.retriever, "search", boom)
    r = client.post("/internal/search", json={"query": "x"}, headers=HEADERS)
    assert r.status_code == 500 and r.json()["code"] == "INTERNAL_ERROR" and "secret" not in r.text
