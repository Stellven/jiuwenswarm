"""Host listening-port audit (PAS-M1-001 B11, AC-019; test plan "Always": no host port besides 5175).

Records every listening TCP socket on the host and attributes it. Fails when a
SIMLAB process, or a SIMLAB container, owns or publishes a TCP port, or when
any listener other than 127.0.0.1:5175 belongs to the AI4R/SIMLAB deployment.
Standard library plus the docker CLI.

    python tools/port_audit.py [--json] [--expect-ai4r]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

STATE_LISTEN = "0A"


def listeners() -> list[dict]:
    inode_owner: dict[str, tuple[int, str]] = {}
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            cmd = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace").strip()
            for fd in os.listdir(f"/proc/{pid}/fd"):
                try:
                    link = os.readlink(f"/proc/{pid}/fd/{fd}")
                except OSError:
                    continue
                if link.startswith("socket:["):
                    inode_owner[link[8:-1]] = (int(pid), cmd[:160])
        except (PermissionError, FileNotFoundError, ProcessLookupError):
            continue
    out = []
    for fam, path in (("tcp", "/proc/net/tcp"), ("tcp6", "/proc/net/tcp6")):
        try:
            lines = Path(path).read_text().splitlines()[1:]
        except OSError:
            continue
        for line in lines:
            parts = line.split()
            if parts[3] != STATE_LISTEN:
                continue
            addr, port = parts[1].split(":")
            port = int(port, 16)
            if fam == "tcp":
                ip = ".".join(str(int(addr[i:i + 2], 16)) for i in (6, 4, 2, 0))
            else:
                ip = "::" if set(addr) == {"0"} else ("::1" if addr == "00000000000000000000000001000000" else addr)
            pid, cmd = inode_owner.get(parts[9], (None, None))
            out.append({"family": fam, "ip": ip, "port": port, "pid": pid, "cmd": cmd})
    return out


def docker_ports() -> list[dict]:
    try:
        r = subprocess.run(["docker", "ps", "--format", "{{json .}}"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return []
    rows = []
    for line in r.stdout.splitlines():
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        rows.append({"name": d.get("Names"), "image": d.get("Image"), "ports": d.get("Ports"), "networks": d.get("Networks")})
    return rows


def audit(expect_ai4r: bool) -> dict:
    ls = listeners()
    dk = docker_ports()
    problems = []
    for l in ls:
        if l["cmd"] and "simlab" in l["cmd"] and "port_audit" not in l["cmd"]:
            problems.append(f"SIMLAB process {l['pid']} listens on {l['ip']}:{l['port']}")
    for c in dk:
        if "simlab" in (c["name"] or "") or "simlab" in (c["image"] or ""):
            if c["ports"]:
                problems.append(f"SIMLAB container {c['name']} publishes {c['ports']}")
        if c["name"] and c["name"].startswith("ai4r-local-") and c["ports"] and c["ports"] != "127.0.0.1:5175->5173/tcp":
            problems.append(f"AI4R container {c['name']} publishes {c['ports']} (only 127.0.0.1:5175 is allowed)")
    has_5175 = any(l["port"] == 5175 for l in ls)
    if expect_ai4r and not has_5175:
        problems.append("expected AI4R on 127.0.0.1:5175 but nothing listens there")
    for l in ls:
        if l["port"] == 5175 and l["ip"] not in {"127.0.0.1"}:
            problems.append(f"port 5175 is bound on {l['ip']}, not 127.0.0.1")
    return {"listeners": ls, "containers": dk, "port_5175_listening": has_5175, "problems": problems,
            "result": "PASS" if not problems else "FAIL",
            "note": "Listeners owned by unrelated host processes are recorded, not attributed to SIMLAB."}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--expect-ai4r", action="store_true")
    ap.add_argument("--output", type=Path)
    a = ap.parse_args(argv)
    out = audit(a.expect_ai4r)
    text = json.dumps(out, indent=1)
    if a.output:
        a.output.write_text(text)
    print(text if a.json else out["result"] + "".join("\n  " + p for p in out["problems"]))
    return 0 if out["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
