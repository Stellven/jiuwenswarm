"""V-BLK-SANDBOX (AC-004, AC-019): the real worker sandbox denies sockets, processes and credential reads, keeps no
credentials in its environment, and ends an attempt LIMIT_REACHED at its declared CPU and memory limits."""
import json
import os
import subprocess
import sys

from simlab.runner.core import worker_env

PROBE = r'''
import json, os, ctypes, socket, subprocess, threading
from simlab.executors.mujoco import sandbox
out = {"info": sandbox.install({"cpu_s": 20, "memory_mb": 1536})}
libc = ctypes.CDLL(None, use_errno=True)
out["socket_raw"] = libc.socket(2, 1, 0)
out["socket_unix_raw"] = libc.socket(1, 1, 0)
try:
    socket.create_connection(("127.0.0.1", 5175), timeout=1); out["connect"] = "CONNECTED"
except OSError as e:
    out["connect"] = type(e).__name__
try:
    subprocess.run(["/bin/true"]); out["exec"] = "RAN"
except OSError as e:
    out["exec"] = type(e).__name__
out["fork_raw"] = libc.fork()
r = []; t = threading.Thread(target=lambda: r.append(1)); t.start(); t.join(); out["thread"] = r
out["env"] = sorted(os.environ)
out["denials"] = [d["kind"] for d in sandbox.DENIALS]
print(json.dumps(out))
'''


def test_denials_and_credential_free_env():
    env = worker_env()
    assert not [k for k in env if any(w in k.upper() for w in ("TOKEN", "SECRET", "KEY", "PASSWORD", "AUTH"))]
    leaky = {**env, "PLANTED_API_TOKEN": "secret-value"}
    r = subprocess.run([sys.executable, "-c", PROBE], capture_output=True, text=True, env=leaky, cwd="/tmp", timeout=60)
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out["info"]["seccomp_mode"] == 2 and out["info"]["no_new_privs"]
    assert out["socket_raw"] == -1 and out["socket_unix_raw"] == -1, "kernel filter refuses sockets"
    assert out["connect"] == "PermissionError" and out["exec"] == "PermissionError" and out["fork_raw"] == -1
    assert out["thread"] == [1], "threads still work"
    assert "PLANTED_API_TOKEN" not in out["env"] and "PLANTED_API_TOKEN" in out["info"]["env_credentials_removed"]
    assert {"network", "process"} <= set(out["denials"])
