"""Private launcher child: wait for cgroup assignment, drop identity, exec.

Only a root-owned broker can use this entry. No caller shell or public CLI is
accepted. The broker supplies an already validated manifest over inherited FDs.
"""
from __future__ import annotations

import ctypes
import json
import os
import signal
import sys


def main():
    if os.name != "posix" or os.geteuid() != 0 or len(sys.argv) != 3:
        raise SystemExit("PROTECTED_EXECUTOR_BROKER_REQUIRED")
    gate_fd, manifest_fd = map(int, sys.argv[1:])
    libc = ctypes.CDLL(None, use_errno=True)
    parent = os.getppid()
    if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0 or os.getppid() != parent:
        raise SystemExit("EXECUTOR_PARENT_UNAVAILABLE")
    # EOF means the broker died before assigning this child to its own cgroup.
    if os.read(gate_fd, 1) != b"1":
        raise SystemExit("EXECUTOR_ADMISSION_ABORTED")
    os.close(gate_fd)
    with os.fdopen(manifest_fd, "r", encoding="utf-8") as stream:
        manifest = json.load(stream)
    os.setgroups([])
    os.setgid(manifest["gid"])
    os.setuid(manifest["uid"])
    if libc.prctl(38, 1, 0, 0, 0) != 0:
        raise SystemExit("EXECUTOR_NO_NEW_PRIVILEGES_FAILED")
    os.execve(manifest["argv"][0], manifest["argv"], manifest["environment"])


if __name__ == "__main__":
    main()
