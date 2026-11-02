"""JSON-RPC 2.0 over a Unix domain socket in the data directory (PAS-M1-001 B09; research.md R5).

No TCP listener: SIMLAB opens no host port (PRD SL-9.B). One request per line,
one response per line. Errors carry the typed error object in `error.data`.
"""
from __future__ import annotations

import json
import os
import signal
import socket
import socketserver
import sys
import threading
import traceback
from pathlib import Path

from simlab.contracts import SimlabError

SOCKET_NAME = "runner.sock"
ERR_SIMLAB = -32000


MAX_SUN_PATH = 100  # AF_UNIX paths are limited to 108 bytes on Linux


def socket_path(data_dir: str | os.PathLike) -> Path:
    """<data dir>/runner.sock, or, when that path is too long for AF_UNIX, a short path in a private per-user
    runtime directory (mode 0700) derived from the data directory, so server and clients agree on it."""
    p = Path(data_dir).expanduser()
    direct = p / SOCKET_NAME
    if len(os.fsencode(str(direct))) <= MAX_SUN_PATH:
        return direct
    import hashlib  # noqa: PLC0415
    import tempfile  # noqa: PLC0415

    run_dir = Path(os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()) / f"simlab-{os.getuid()}"
    run_dir.mkdir(mode=0o700, exist_ok=True)
    if run_dir.stat().st_uid != os.getuid() or run_dir.stat().st_mode & 0o077:
        raise PermissionError(f"{run_dir} must be owned by this user with mode 0700")
    key = hashlib.sha256(str(p.resolve()).encode()).hexdigest()[:20]
    return run_dir / f"{key}.sock"


class _Handler(socketserver.StreamRequestHandler):
    def handle(self):
        service = self.server.service  # type: ignore[attr-defined]
        for raw in self.rfile:
            line = raw.strip()
            if not line:
                continue
            rid = None
            try:
                req = json.loads(line)
                rid = req.get("id")
                if req.get("jsonrpc") != "2.0" or not isinstance(req.get("method"), str):
                    raise SimlabError("E_INVALID_INPUT", "not a JSON-RPC 2.0 request")
                result = service.call(req["method"], req.get("params") or {})
                resp = {"jsonrpc": "2.0", "id": rid, "result": result}
            except SimlabError as e:
                resp = {"jsonrpc": "2.0", "id": rid, "error": {"code": ERR_SIMLAB, "message": e.message, "data": e.to_error()}}
            except json.JSONDecodeError as e:
                resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": f"parse error: {e}",
                                                              "data": {"code": "E_INVALID_INPUT", "message": str(e), "path": "", "severity": "error"}}}
            except Exception as e:  # infrastructure failure, reported as such
                resp = {"jsonrpc": "2.0", "id": rid, "error": {"code": -32603, "message": f"internal error: {type(e).__name__}: {e}",
                                                             "data": {"code": "E_INTERNAL", "message": traceback.format_exc()[-1500:],
                                                                      "path": "", "severity": "error"}}}
            self.wfile.write((json.dumps(resp, default=str) + "\n").encode())
            self.wfile.flush()


class _Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True
    allow_reuse_address = True


def serve(data_dir: str | None = None, *, ready: threading.Event | None = None) -> int:
    from simlab.interface.ops import Service  # noqa: PLC0415
    from simlab.store import Store  # noqa: PLC0415

    store = Store(data_dir)
    path = socket_path(store.root)
    if path.exists():
        try:
            with socket.socket(socket.AF_UNIX) as s:
                s.settimeout(1)
                s.connect(str(path))
            print(f"simlab serve: another service already listens on {path}", file=sys.stderr)
            return 2
        except OSError:
            path.unlink()
    service = Service(store)
    old = os.umask(0o077)
    try:
        server = _Server(str(path), _Handler)
    finally:
        os.umask(old)
    server.service = service  # type: ignore[attr-defined]

    def stop(*_):
        threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    print(json.dumps({"serving": str(path), "data_dir": str(store.root), "pid": os.getpid()}), flush=True)
    if ready is not None:
        ready.set()
    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        service.runner.close()
        server.server_close()
        path.unlink(missing_ok=True)
    return 0
