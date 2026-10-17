"""End-to-end smoke test against a RUNNING service:  python scripts/smoke_test.py
Env: INTERNAL_API_KEY (required), AI_URL (default http://localhost:8000). Uses README.md as the sample document."""
import json
import os
import sys
from pathlib import Path

import httpx

URL = os.getenv("AI_URL", "http://localhost:8000")
KEY = os.environ["INTERNAL_API_KEY"]
H = {"X-Internal-API-Key": KEY}
DOC_ID = 987654


def check(name: str, ok: bool, extra: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {extra}")
    if not ok:
        sys.exit(1)


with httpx.Client(base_url=URL, timeout=120) as c:
    r = c.get("/health")
    check("health (no key needed)", r.status_code == 200, r.text)
    check("search without key -> 401", c.post("/internal/search", json={"query": "x"}).status_code == 401)
    meta = {"documentId": DOC_ID, "uploadedByUserId": 1, "sourceType": "MD", "title": "README", "filename": "README.md"}
    f = Path(__file__).resolve().parents[1] / "README.md"
    r = c.post("/internal/ingest", data={"meta": json.dumps(meta)}, files={"file": ("README.md", f.read_bytes(), "text/markdown")}, headers=H)
    check("ingest", r.status_code == 200 and r.json()["chunkCount"] >= 1, r.text)
    n = r.json()["chunkCount"]
    r = c.post("/internal/search", json={"query": "how does AI B add routes", "mode": "HYBRID", "k": 3}, headers=H)
    check("hybrid search", r.status_code == 200 and r.json() and r.json()[0]["documentId"] == DOC_ID, r.text[:200])
    r = c.get(f"/internal/documents/{DOC_ID}/chunks?page=0&size=2", headers=H)
    check("chunk listing", r.json()["totalItems"] == n, f"({n} chunks)")
    r = c.post("/internal/ingest", data={"meta": json.dumps({**meta, "sourceType": "PDF", "filename": "x.pdf"})},
               files={"file": ("x.pdf", b"%PDF-1.4 broken", "application/pdf")}, headers=H)
    check("corrupt PDF -> 422 INGESTION_FAILED", r.status_code == 422 and r.json()["code"] == "INGESTION_FAILED", r.text)
    r = c.delete(f"/internal/documents/{DOC_ID}", headers=H)
    check("delete", r.json()["deleted"] == n)
print("ALL SMOKE CHECKS PASSED")
