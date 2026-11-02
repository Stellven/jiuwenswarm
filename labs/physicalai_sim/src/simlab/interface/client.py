"""SIMLAB Python client (PAS-M1-001 B09; PRD SL-9.D).

    from simlab.interface.client import Client
    c = Client("/path/to/data")          # or SIMLAB_DATA_DIR
    d = c.draft_create(header={...})
    ...
    run = c.submit(experiment=exp)

Every operation in simlab.interface.ops.OPERATIONS is a method with the same
name and keyword parameters. Errors raise SimlabClientError carrying the typed
error object.
"""
from __future__ import annotations

import itertools
import json
import os
import socket
from pathlib import Path
from typing import Any

from simlab.interface.ops import OPERATIONS, RESERVED
from simlab.interface.rpc import socket_path


class SimlabClientError(Exception):
    def __init__(self, error: dict):
        super().__init__(f"{error.get('code')}: {error.get('message')}")
        self.error = error
        self.code = error.get("code")


class Client:
    def __init__(self, data_dir: str | os.PathLike | None = None, *, socket_file: str | os.PathLike | None = None, timeout: float = 3700.0):
        if socket_file is None:
            d = data_dir or os.environ.get("SIMLAB_DATA_DIR")
            if not d:
                raise ValueError("give data_dir or set SIMLAB_DATA_DIR")
            socket_file = socket_path(Path(d).expanduser())
        self.socket_file = str(socket_file)
        self.timeout = timeout
        self._ids = itertools.count(1)

    def call(self, method: str, **params: Any) -> Any:
        params = {k: v for k, v in params.items() if v is not None}
        req = {"jsonrpc": "2.0", "id": next(self._ids), "method": method, "params": params}
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(self.timeout)
            s.connect(self.socket_file)
            s.sendall((json.dumps(req) + "\n").encode())
            buf = b""
            while not buf.endswith(b"\n"):
                chunk = s.recv(1 << 20)
                if not chunk:
                    break
                buf += chunk
        resp = json.loads(buf)
        if "error" in resp:
            raise SimlabClientError(resp["error"].get("data") or {"code": "E_INTERNAL", "message": resp["error"].get("message")})
        return resp["result"]

    def __getattr__(self, name: str):
        if name in OPERATIONS or name in RESERVED:
            return lambda **kw: self.call(name, **kw)
        raise AttributeError(name)

    def run_and_wait(self, experiment: dict, timeout_s: float = 600) -> dict:
        r = self.submit(experiment=experiment)
        if "findings" in r:
            return r
        self.wait(run_id=r["run_id"], timeout_s=timeout_s)
        return self.result(run_id=r["run_id"])
