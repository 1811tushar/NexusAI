"""Contract-shaped deterministic AI stub (API/Data contract v2.1) for integration smoke tests ONLY.

It never calls an LLM or any external service and keeps data in memory. Do not use it outside local/CI testing.
Scenarios are selected by the question text, so one stub can exercise every backend code path:
  default                         plan -> evidence -> claims -> confidence LOOP -> loop -> ACCEPT -> LOW action -> PII redaction
                                  -> approval_required (HIGH action) -> stream ends; resume -> report -> done COMPLETED
  contains "[no-approval]"        same, but only a LOW action: the run completes in one stream (no pause)
  contains "ignore previous"      input guardrail: guardrail_triggered BLOCKED -> done REFUSED
"""
from __future__ import annotations
import json, os, re, time, uuid
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

API_KEY = os.environ.get("INTERNAL_API_KEY", "")
EVENT_DELAY = float(os.environ.get("FAKE_AI_EVENT_DELAY", "0.15"))
DOCS: dict[int, dict] = {}
NS = uuid.UUID("6f1c0c1e-8a53-4f5e-9a47-2f0f6c1d9a10")
def ev_key(name: str) -> str: return str(uuid.uuid5(NS, name))
def jb(v) -> bytes: return json.dumps(v, separators=(",", ":")).encode()
NOW = lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

SQL_EVIDENCE = lambda: {
    "evidenceKey": ev_key("sql-1"), "kind": "SQL", "title": "Revenue by region, Q1 vs Q2 2026 (synthetic)",
    "snippet": "West revenue fell 31.4% quarter over quarter; North grew 6.2%.",
    "source": {"table": "sales", "sql": "SELECT region_id, SUM(revenue) FROM sales GROUP BY region_id LIMIT 200"},
    "data": {"columns": ["region", "q1_revenue", "q2_revenue"], "rows": [["West", 1000000, 686000], ["North", 800000, 849600]], "truncated": False},
    "chart": {"type": "bar", "x": ["West", "North"], "series": [{"name": "Q1", "values": [1000000, 800000]}, {"name": "Q2", "values": [686000, 849600]}]},
    "score": None, "createdAt": NOW()}
DOC_EVIDENCE = lambda: {
    "evidenceKey": ev_key("doc-1"), "kind": "DOCUMENT", "title": "Supplier incident report (synthetic)",
    "snippet": "A supplier stock-out in May and June limited Home category availability in the West region.",
    "source": {"documentId": 1, "page": 2}, "score": 0.83, "createdAt": NOW()}

def low_action(): return {"actionKey": "act-low-1", "actionType": "FLAG_FOR_REVIEW", "risk": "LOW", "title": "Flag West Home category for review",
    "description": "Deterministic test-only action.", "params": {"subject": "West Home category", "reason": "Revenue decline"},
    "rationale": "Revenue fell sharply in the West.", "evidenceKeys": [ev_key("sql-1")]}
def high_action(): return {"actionKey": "act-high-1", "actionType": "PAUSE_CAMPAIGN", "risk": "HIGH", "title": "Pause a synthetic campaign for review",
    "description": "Deterministic test-only action.", "params": {"regionId": 1, "channel": "paid_search", "weeks": 2},
    "rationale": "The synthetic evidence indicates lower campaign conversion.", "evidenceKeys": [ev_key("sql-1")]}

def common_prefix(refuse=False):
    if refuse:
        return [("guardrail_triggered", {"stage": "INPUT", "action": "BLOCKED", "category": "PROMPT_INJECTION", "detail": "Request tried to override system instructions."}),
                ("done", {"status": "REFUSED", "confidence": None, "loopsUsed": 0, "usage": {"inputTokens": 0, "outputTokens": 0}, "latencyMs": 1})]
    s1, s2 = ev_key("step-1"), ev_key("step-2")
    return [
        ("memory_recalled", {"items": []}),
        ("supervisor_routed", {"agents": ["PLANNER", "RESEARCHER", "DATA_ANALYST", "ANALYST", "VERIFIER", "REPORTER"], "reason": "needs documents and data"}),
        ("plan", {"steps": [{"id": s1, "description": "Compare revenue by region", "agent": "DATA_ANALYST", "status": "PENDING"},
                            {"id": s2, "description": "Find causes in documents", "agent": "RESEARCHER", "status": "PENDING"}]}),
        ("agent_started", {"agent": "DATA_ANALYST", "stepId": s1}),
        ("step_status", {"stepId": s1, "status": "RUNNING"}),
        ("tool_call", {"callId": ev_key("call-1"), "agent": "DATA_ANALYST", "tool": "sql_query", "args": {"sql": "SELECT region_id, SUM(revenue) FROM sales GROUP BY region_id"}}),
        ("tool_result", {"callId": ev_key("call-1"), "tool": "sql_query", "ok": True, "summary": "2 rows", "durationMs": 12}),
        ("evidence_added", {"evidence": SQL_EVIDENCE()}),
        ("step_status", {"stepId": s1, "status": "DONE"}),
        ("agent_started", {"agent": "RESEARCHER", "stepId": s2}),
        ("tool_call", {"callId": ev_key("call-2"), "agent": "RESEARCHER", "tool": "rag_search", "args": {"query": "West Home supply"}}),
        ("guardrail_triggered", {"stage": "TOOL", "action": "REDACTED", "category": "PII", "detail": "1 email-like value redacted from retrieved text."}),
        ("tool_result", {"callId": ev_key("call-2"), "tool": "rag_search", "ok": True, "summary": "1 chunk", "durationMs": 20}),
        ("evidence_added", {"evidence": DOC_EVIDENCE()}),
        ("step_status", {"stepId": s2, "status": "DONE"}),
        ("claims_drafted", {"claims": [
            {"claimKey": "c1", "text": "West revenue fell 31.4% quarter over quarter.", "isKey": True, "evidenceKeys": [ev_key("sql-1")]},
            {"claimKey": "c2", "text": "A supplier stock-out explains the West decline.", "isKey": True, "evidenceKeys": [ev_key("doc-1")]},
            {"claimKey": "c3", "text": "A competitor launched a rival product.", "isKey": False, "evidenceKeys": []}]}),
        ("claim_verified", {"claimKey": "c1", "text": "West revenue fell 31.4% quarter over quarter.", "status": "VERIFIED", "confidence": 0.95, "evidenceKeys": [ev_key("sql-1")], "reason": "Matches SQL result."}),
        ("claim_verified", {"claimKey": "c2", "text": "A supplier stock-out explains the West decline.", "status": "UNSUPPORTED", "confidence": 0.4, "evidenceKeys": [ev_key("doc-1")], "reason": "Document does not quantify impact."}),
        ("confidence", {"overall": 0.62, "threshold": 0.7, "decision": "LOOP", "loop": 0}),
        ("loop", {"loop": 1, "maxLoops": 3, "reason": "Key claim c2 is weakly supported", "focus": ["c2"]}),
        ("claim_verified", {"claimKey": "c2", "text": "A supplier stock-out explains the West decline.", "status": "VERIFIED", "confidence": 0.82, "evidenceKeys": [ev_key("doc-1"), ev_key("sql-1")], "reason": "Stock-out dates align with the decline."}),
        ("confidence", {"overall": 0.84, "threshold": 0.7, "decision": "ACCEPT", "loop": 1}),
        ("action_proposed", low_action()),
    ]

REPORT = ("## Deterministic smoke-test report\n\nThis report was produced by the test-only fake AI stub. No external system was changed.\n\n"
          "### Limitations and failures\n- Claim c3 (competitor launch) could not be verified: no evidence was found.\n")
def report_events(decision_note: str):
    return [
        ("report_delta", {"text": "## Deterministic smoke-test report\n"}),
        ("report_ready", {"reportMarkdown": REPORT + "\n" + decision_note, "summary": "Synthetic revenue evidence was reviewed; " + decision_note,
                          "recommendations": [{"id": "rec-1", "text": "Review campaign performance with the business owner.", "risk": "HIGH", "actionKey": "act-high-1"},
                                              {"id": "rec-2", "text": "Review the West Home category.", "risk": "LOW", "actionKey": "act-low-1"}], "confidence": 0.84}),
        ("memory_saved", {"id": 1, "summary": "Q2 revenue decline analysed (synthetic)."}),
        ("done", {"status": "COMPLETED", "confidence": 0.84, "loopsUsed": 1, "usage": {"inputTokens": 1200, "outputTokens": 400}, "latencyMs": 1500}),
    ]

class Handler(BaseHTTPRequestHandler):
    server_version = "NexusAI-TestStub/2.1"
    def log_message(self, fmt, *args): print("fake-ai: " + (fmt % args))
    def send_json(self, status, payload):
        b = jb(payload); self.send_response(status); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def authorized(self): return bool(API_KEY) and self.headers.get("X-Internal-API-Key", "") == API_KEY
    def read_raw(self):
        # WebClient/Netty sends multipart uploads with Transfer-Encoding: chunked (no Content-Length): support both.
        if "chunked" in self.headers.get("Transfer-Encoding", "").lower():
            parts = []
            while True:
                size = int((self.rfile.readline().split(b";")[0].strip() or b"0"), 16)
                if size == 0:
                    while self.rfile.readline() not in (b"\r\n", b"\n", b""): pass   # optional trailers
                    break
                parts.append(self.rfile.read(size)); self.rfile.readline()
            return b"".join(parts)
        n = int(self.headers.get("Content-Length", "0"))
        return self.rfile.read(n) if n else b""
    def read_json(self):
        raw = self.read_raw() or b"{}"
        try: v = json.loads(raw or b"{}")
        except ValueError: v = {}
        return v if isinstance(v, dict) else {}
    def sse(self, events):
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Accel-Buffering", "no"); self.send_header("Connection", "close"); self.close_connection = True; self.end_headers()
        for name, payload in events:
            self.wfile.write(f"event: {name}\ndata: ".encode() + jb(payload) + b"\n\n"); self.wfile.flush(); time.sleep(EVENT_DELAY)
    def do_GET(self):
        u = urlparse(self.path); path = u.path
        if path == "/health": return self.send_json(200, {"status": "ok", "embeddingModel": "fake-stub", "llmProvider": "fake"})
        if path == "/metrics":
            body = b"# TYPE nexusai_ai_fake_up gauge\nnexusai_ai_fake_up 1\n"
            self.send_response(200); self.send_header("Content-Type", "text/plain; version=0.0.4"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
        if not self.authorized(): return self.send_json(401, {"detail": "invalid internal API key"})
        m = re.fullmatch(r"/internal/documents/(\d+)/chunks", path)
        if m:
            doc = DOCS.get(int(m.group(1))); did = int(m.group(1))
            chunks = [] if not doc else [{"id": did * 1000 + 1, "chunkIndex": 0, "page": 1, "section": None, "content": doc["text"]}]
            return self.send_json(200, {"items": chunks, "page": 0, "size": 20, "totalItems": len(chunks), "totalPages": 1 if chunks else 0})
        if path == "/internal/memories": return self.send_json(200, {"items": [], "page": 0, "size": 20, "totalItems": 0, "totalPages": 0})
        if path == "/internal/eval/runs": return self.send_json(200, [])
        if re.fullmatch(r"/internal/eval/runs/\d+", path): return self.send_json(404, {"detail": "not found"})
        self.send_json(404, {"detail": "not found"})
    def do_DELETE(self):
        if not self.authorized(): return self.send_json(401, {"detail": "invalid internal API key"})
        path = urlparse(self.path).path
        m = re.fullmatch(r"/internal/documents/(\d+)", path)
        if m: DOCS.pop(int(m.group(1)), None); return self.send_json(200, {"deleted": 1})
        if path == "/internal/memories" or re.fullmatch(r"/internal/memories/\d+", path): return self.send_json(200, {"deleted": 0})
        if re.fullmatch(r"/internal/users/\d+", path): return self.send_json(200, {"memories": 0, "checkpoints": 0})
        self.send_json(404, {"detail": "not found"})
    def do_POST(self):
        path = urlparse(self.path).path
        if not self.authorized(): return self.send_json(401, {"detail": "invalid internal API key"})
        if path == "/internal/ingest":
            raw = self.read_raw(); ctype = self.headers.get("Content-Type", "application/octet-stream")
            msg = BytesParser(policy=default).parsebytes(b"MIME-Version: 1.0\r\nContent-Type: " + ctype.encode() + b"\r\n\r\n" + raw)
            meta, content = {}, ""
            if msg.is_multipart():
                for part in msg.iter_parts():
                    name = part.get_param("name", header="content-disposition"); payload = part.get_payload(decode=True) or b""
                    if name == "meta":
                        try: meta = json.loads(payload.decode("utf-8"))
                        except (ValueError, UnicodeDecodeError): meta = {}
                    elif name == "file": content = payload.decode("utf-8", errors="replace")
            try: did = int(meta.get("documentId", 0))
            except (TypeError, ValueError): did = 0
            if not did: return self.send_json(422, {"detail": "meta.documentId is required"})
            DOCS[did] = {"title": str(meta.get("title") or meta.get("filename") or f"Document {did}"), "text": content[:20000]}
            return self.send_json(200, {"documentId": did, "pageCount": None, "chunkCount": 1, "warnings": ["Deterministic fake AI stub; no embeddings or LLM used."]})
        if path == "/internal/search":
            body = self.read_json(); query = str(body.get("query", "")).lower(); hits = []
            for did, doc in DOCS.items():
                content = str(doc.get("text", ""))
                if not content: continue
                terms = set(re.findall(r"[a-z0-9]+", query)); score = sum(1 for t in terms if t in content.lower()) / max(1, len(terms))
                if score > 0 or not query:
                    hits.append({"chunkId": did * 1000 + 1, "documentId": did, "documentTitle": str(doc.get("title")), "page": 1, "section": None, "snippet": content[:600], "score": max(score, 0.01)})
            hits.sort(key=lambda h: float(h["score"]), reverse=True)
            return self.send_json(200, hits[: int(body.get("k", 8) or 8)])
        if path == "/internal/investigate":
            body = self.read_json(); q = str(body.get("question", "")).lower()
            if "ignore previous" in q: return self.sse(common_prefix(refuse=True))
            if "[no-approval]" in q: return self.sse(common_prefix() + report_events("no approval was needed"))
            return self.sse(common_prefix() + [("approval_required", {"actions": [high_action()]})])
        m = re.fullmatch(r"/internal/investigate/([^/]+)/resume", path)
        if m:
            body = self.read_json(); decisions = body.get("decisions") or []
            rejected = [d for d in decisions if str(d.get("decision", "")).upper() != "APPROVE"]
            note = "the proposed action was rejected" if rejected else "the proposed action was approved"
            return self.sse(report_events(note))
        if re.fullmatch(r"/internal/investigate/[^/]+/cancel", path): return self.send_json(200, {"cancelled": True})
        self.send_json(404, {"detail": "not found"})

if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
