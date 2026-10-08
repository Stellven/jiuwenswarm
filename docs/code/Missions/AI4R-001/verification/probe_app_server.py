"""Bounded real-process probe: initialize/account-read only, never login/turns.

Creates and retains a fresh evidence directory. No credential files are read,
copied or deleted. Responses and child stderr are not logged verbatim.
"""
import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import time
import uuid
import argparse

from codex_cli_bin import bundled_codex_path


def run_cycle(binary, home, workspace, guarded=False):
    allow = {"SYSTEMROOT", "WINDIR", "COMSPEC", "PATH", "PATHEXT", "TEMP", "TMP"}
    env = {k: v for k, v in os.environ.items() if k.upper() in allow}
    env.update(CODEX_HOME=str(home), HOME=str(workspace), USERPROFILE=str(workspace))
    args = [str(binary), "--config", 'forced_login_method="chatgpt"',
            "--config", 'cli_auth_credentials_store="file"',
            "--config", "analytics.enabled=false", "--config", "feedback.enabled=false",
            "app-server", "--listen", "stdio://"]
    if guarded:
        from guard_prototype import launch_signed_out_probe
        proc = launch_signed_out_probe(binary, home, workspace)
    else:
        proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
                                cwd=workspace, env=env,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    inbox = queue.Queue()

    def read():
        try:
            for line in proc.stdout:
                try:
                    inbox.put(json.loads(line))
                except ValueError:
                    inbox.put({"probe_error": "non_json_stdout"})
        finally:
            inbox.put({"probe_error": "stdout_closed"})

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    sent = []

    def send(method, params=None, identity=None):
        if method not in {"initialize", "initialized", "account/read"}:
            raise ValueError("operation outside probe scope")
        msg = {"method": method}
        if identity is not None:
            msg["id"] = identity
        if params is not None:
            msg["params"] = params
        proc.stdin.write(json.dumps(msg) + "\n")
        proc.stdin.flush()
        sent.append(method)

    def receive(identity):
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            msg = inbox.get(timeout=max(0.01, deadline - time.monotonic()))
            if "probe_error" in msg:
                raise RuntimeError(msg["probe_error"])
            if "method" in msg and "id" in msg:
                raise RuntimeError("unexpected_server_request")
            if msg.get("id") == identity:
                if "error" in msg:
                    raise RuntimeError("rpc_error_code=" + str(msg["error"].get("code")))
                if "result" not in msg:
                    raise RuntimeError("missing_result")
                return msg["result"]
        raise TimeoutError("response_timeout")

    record = {"methods": sent, "passed": False}
    try:
        send("initialize", {"clientInfo": {"name": "ai4r_feasibility", "version": "0.1"},
                            "capabilities": {"experimentalApi": True}}, 1)
        result = receive(1)
        record["initialized"] = isinstance(result, dict)
        send("initialized")
        send("account/read", {"refreshToken": False}, 2)
        account = receive(2)
        record["signed_out"] = isinstance(account, dict) and "account" in account and account["account"] is None
        if not record["initialized"] or not record["signed_out"]:
            raise RuntimeError("unexpected_initialization_or_account_state")
        record["passed"] = True
    except Exception as exc:
        # Exception class is enough; avoid accidental payload disclosure.
        record["failure_class"] = type(exc).__name__
    finally:
        proc.stdin.close()
        try:
            proc.wait(timeout=5)
            record["cleanup"] = "stdin_eof"
        except subprocess.TimeoutExpired:
            proc.terminate()
            try:
                proc.wait(timeout=5)
                record["cleanup"] = "terminate_owned_process"
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
                record["cleanup"] = "kill_owned_process"
        reader.join(timeout=2)
        proc.stdout.close()
        record["exit_code"] = proc.returncode
        record["process_stopped"] = proc.poll() is not None
        record["reader_stopped"] = not reader.is_alive()
        record["passed"] &= record["process_stopped"] and record["reader_stopped"]
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--guarded", action="store_true")
    options = parser.parse_args()
    evidence = Path(os.environ["LOCALAPPDATA"]) / "ai4r-tools/evidence/AI4R-001"
    root = evidence / ("isolated-probe-" + uuid.uuid4().hex)
    home, workspace = root / "codex-home", root / "workspace"
    home.mkdir(parents=True)
    workspace.mkdir()
    binary = Path(bundled_codex_path())
    result = {"binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
              "scope": "initialize, signed-out account/read, restart, owned-process cleanup",
              "guarded_launcher": options.guarded,
              "model_turns": 0, "login_operations": 0,
              "cycles": [run_cycle(binary, home, workspace, options.guarded) for _ in range(2)]}
    result["passed"] = all(c["passed"] for c in result["cycles"])
    path = root / "summary.json"
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"evidence": str(path), **result}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
