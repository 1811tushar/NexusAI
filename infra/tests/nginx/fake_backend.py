import json, time, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def _json(self, code, obj, extra=None):
        b = json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(b)))
        for k,v in (extra or {}).items(): self.send_header(k,v)
        self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if self.path.startswith("/actuator/health"): return self._json(200, {"status":"UP"})
        if self.path.startswith("/actuator/prometheus"): return self._json(200, {"leak":"metrics"})
        if "/stream" in self.path:
            self.send_response(200); self.send_header("Content-Type","text/event-stream"); self.send_header("Cache-Control","no-cache"); self.send_header("Transfer-Encoding","chunked"); self.end_headers()
            def chunk(s):
                d=s.encode(); self.wfile.write(b"%x\r\n"%len(d)+d+b"\r\n"); self.wfile.flush()
            chunk("id: 1\nevent: run_started\ndata: {}\n\n"); time.sleep(3)
            chunk(": ping\n\n"); time.sleep(1); chunk("id: 2\nevent: done\ndata: {}\n\n"); self.wfile.write(b"0\r\n\r\n"); return
        return self._json(200, {"ok":True,"path":self.path}, {"X-Seen-Request-Id": self.headers.get("X-Request-Id","")})
    def do_POST(self):
        n=0; 
        while True:
            c=self.rfile.read(min(65536, int(self.headers.get("Content-Length","0"))-n)) if self.headers.get("Content-Length") else b""
            if not c: break
            n+=len(c)
            if n>=int(self.headers.get("Content-Length","0")): break
        if n > 20*1024*1024: return self._json(413, {"success":False,"error":{"code":"FILE_TOO_LARGE"}})
        return self._json(202, {"success":True,"received":n})
    def log_message(self,*a): pass
import os
ThreadingHTTPServer((os.environ.get("FAKE_BACKEND_HOST","127.0.0.1"),8080),H).serve_forever()
