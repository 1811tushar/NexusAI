import http.client, time, os, sys, json
HOST=os.environ.get("NGINX_HOST","127.0.0.1"); PORT=int(os.environ.get("NGINX_PORT","80"))
def req(method, path, body=None, headers=None, timeout=30):
    c=http.client.HTTPConnection(HOST,PORT,timeout=timeout); c.request(method,path,body=body,headers=headers or {}); r=c.getresponse(); data=r.read(); return r.status, dict((k.lower(),v) for k,v in r.getheaders()), data
res=[]
def check(name, ok, info=""):
    res.append(ok); print(("PASS  " if ok else "FAIL  ")+name+(f"   [{info}]" if info and not ok else ""))
mb=lambda n: b"x"*(n*1024*1024)
s,h,b=req("POST","/api/documents",mb(3),{"Content-Type":"application/octet-stream"}); check("3 MB upload reaches backend (202)", s==202, f"{s} {b[:80]}")
s,h,b=req("POST","/api/documents",mb(21),{"Content-Type":"application/octet-stream"}); check("21 MB upload reaches backend, backend answers FILE_TOO_LARGE", s==413 and b"FILE_TOO_LARGE" in b, f"{s} {b[:80]}")
s,h,b=req("POST","/api/documents",mb(30),{"Content-Type":"application/octet-stream"}); check("30 MB upload rejected at the proxy (413)", s==413 and b"FILE_TOO_LARGE" not in b, f"{s}")
# SSE timing
c=http.client.HTTPConnection(HOST,PORT,timeout=15); t0=time.time(); c.request("GET","/api/investigations/1/stream",headers={"Accept":"text/event-stream","Last-Event-ID":"0"}); r=c.getresponse()
first=r.readline(); t_first=time.time()-t0
check("SSE: first event arrives immediately (buffering is off)", t_first<1.5 and b"id: 1" in first, f"{t_first:.2f}s {first!r}")
rest=r.read(); check("SSE: stream continues and terminates with done", b"event: done" in rest, rest[-60:])
s,h,b=req("GET","/actuator/health"); check("/actuator/health is reachable", s==200)
s,h,b=req("GET","/actuator/prometheus"); check("/actuator/prometheus is NOT exposed", s==404 and b"leak" not in b, f"{s}")
s,h,b=req("GET","/actuator/env"); check("other actuator endpoints are NOT exposed", s==404, f"{s}")
s,h,b=req("GET","/metrics"); check("/metrics is NOT exposed", s==404, f"{s}")
s,h,b=req("GET","/api/anything",headers={"X-Request-Id":"abc-123"}); check("X-Request-Id is forwarded to the backend", h.get("x-seen-request-id")=="abc-123", h.get("x-seen-request-id"))
s,h,b=req("GET","/api/anything"); check("X-Request-Id is generated when the client sends none", len(h.get("x-seen-request-id",""))>=16, h.get("x-seen-request-id"))
check("API responses carry security headers", "content-security-policy" in h and h.get("x-content-type-options")=="nosniff")
s,h,b=req("GET","/investigations/42"); check("SPA fallback serves index.html for client routes", s==200 and b"<title>nexus" in b.lower(), f"{s}")
check("index.html is no-cache", "no-cache" in h.get("cache-control",""), h.get("cache-control"))
s,h,b=req("GET","/assets/index-AbCdEf12.js"); check("fingerprinted asset is immutable", s==200 and "immutable" in h.get("cache-control",""), f"{s} {h.get('cache-control')}")
s,h,b=req("GET","/favicon.svg"); check("non-fingerprinted asset is NOT immutable", s==200 and "immutable" not in h.get("cache-control",""), f"{s} {h.get('cache-control')}")
print(f"\n{sum(res)}/{len(res)} passed"); sys.exit(0 if all(res) else 1)
