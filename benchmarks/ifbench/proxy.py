"""A small local HTTP proxy that adds fixed fields to every JSON request body.

Used to run a benchmark tool with prompt caching off (cache_prompt=false) when the tool
itself has no option for it (e.g. infer-check). Streaming responses are passed through.
"""
import json, threading, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def start(upstream, inject, port=0, capture_path=None):
    """Start the proxy on 127.0.0.1:<port>. Returns (server, base_url). Stop with server.shutdown()."""
    upstream = upstream.rstrip("/")

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        def _forward(self, method):
            n = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(n) if n else None
            obj = None
            if body and "json" in (self.headers.get("Content-Type") or ""):
                try:
                    obj = json.loads(body)
                    if isinstance(obj, dict):
                        obj.update(inject)
                        body = json.dumps(obj).encode()
                except ValueError:
                    pass
            capture = None
            if capture_path and isinstance(obj, dict) and self.path.rstrip('/').endswith(('completions',)):
                from .requests import Capture
                capture = Capture(capture_path, self.path, obj)
            headers = {k: v for k, v in self.headers.items()
                       if k.lower() not in ("host", "content-length", "connection", "accept-encoding")}
            req = urllib.request.Request(upstream + self.path, data=body, headers=headers, method=method)
            try:
                resp = urllib.request.urlopen(req, timeout=3600)
            except urllib.error.HTTPError as e:
                resp = e
            except Exception as e:
                if capture:
                    capture.finish(502, error=repr(e))
                msg = repr(e).encode()
                self.send_response(502); self.send_header("Content-Length", str(len(msg))); self.end_headers()
                self.wfile.write(msg); return
            self.send_response(resp.status if hasattr(resp, "status") else resp.code)
            for k, v in resp.headers.items():
                if k.lower() not in ("transfer-encoding", "connection", "content-length"):
                    self.send_header(k, v)
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            raw_response = bytearray()
            error = None
            try:
                while True:
                    chunk = resp.read1(65536) if hasattr(resp, "read1") else resp.read(65536)
                    if not chunk:
                        break
                    if capture:
                        if obj.get('stream') and resp.status == 200:
                            capture.feed(chunk)
                            if capture.done:
                                capture.finish(resp.status)
                        else:
                            raw_response.extend(chunk)
                    self.wfile.write(b"%x\r\n%s\r\n" % (len(chunk), chunk)); self.wfile.flush()
                if capture:
                    capture.finish(resp.status, nonstream=raw_response)
                self.wfile.write(b"0\r\n\r\n"); self.wfile.flush()
            except Exception as exc:
                error = repr(exc)
            finally:
                resp.close()
                if capture:
                    capture.finish(resp.status, error=error, nonstream=raw_response)

        def do_GET(self):
            self._forward("GET")

        def do_POST(self):
            self._forward("POST")

    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"
