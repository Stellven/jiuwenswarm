"""Confinement for executor workers and agent-authored component code (B06, research.md R6).

Installed in each worker process after its imports and before any model or
component code loads:

* enforcement: `no_new_privs`, then a seccomp-BPF filter that denies socket(),
  socketpair(), execve(), execveat(), fork(), vfork(), clone() without
  CLONE_THREAD (threads stay possible) and clone3 (ENOSYS, so libc falls back
  to clone and the CLONE_THREAD rule applies);
* declared limits: RLIMIT_CPU, RLIMIT_AS, RLIMIT_FSIZE, RLIMIT_NOFILE, RLIMIT_CORE;
* recording: a Python audit hook that refuses and records network, process and
  credential-path access at the Python level, so a denial is visible in the
  attempt record. The audit hook is detection; seccomp is the enforcement that
  also holds against ctypes or native code.

The worker environment is credential-free: the runner spawns it with a fixed,
minimal environment (see runner/worker_env).
"""
from __future__ import annotations

import ctypes
import errno
import os
import platform
import re
import resource
import struct
import sys

PR_SET_NO_NEW_PRIVS = 38
PR_GET_SECCOMP = 21
PR_SET_SECCOMP = 22
SECCOMP_MODE_FILTER = 2
AUDIT_ARCH_X86_64 = 0xC000003E
SECCOMP_RET_KILL_PROCESS = 0x80000000
SECCOMP_RET_ERRNO = 0x00050000
SECCOMP_RET_ALLOW = 0x7FFF0000
CLONE_THREAD = 0x00010000

# x86_64 syscall numbers
NR = {"socket": 41, "connect": 42, "socketpair": 53, "clone": 56, "fork": 57, "vfork": 58, "execve": 59,
      "execveat": 322, "clone3": 435}

BPF_LD_W_ABS = 0x20
BPF_JEQ_K = 0x15
BPF_JSET_K = 0x45
BPF_RET_K = 0x06

CREDENTIAL_PATH = re.compile(r"(\.codex|\.claude|\.aws|\.ssh|\.config/gcloud|\.netrc|auth\.json|credentials|/run/secrets|"
                             r"\.pem$|\.key$|id_rsa|id_ed25519|token)", re.IGNORECASE)
DENIALS: list[dict] = []
_installed: dict = {}


class _Filter(ctypes.Structure):
    _fields_ = [("code", ctypes.c_ushort), ("jt", ctypes.c_ubyte), ("jf", ctypes.c_ubyte), ("k", ctypes.c_uint)]


class _Prog(ctypes.Structure):
    _fields_ = [("len", ctypes.c_ushort), ("filter", ctypes.POINTER(_Filter))]


def _program() -> list[tuple[int, int, int, int]]:
    deny_eacces = SECCOMP_RET_ERRNO | errno.EACCES
    deny_eperm = SECCOMP_RET_ERRNO | errno.EPERM
    enosys = SECCOMP_RET_ERRNO | errno.ENOSYS
    p: list[tuple[int, int, int, int]] = []
    p.append((BPF_LD_W_ABS, 0, 0, 4))                      # arch
    p.append((BPF_JEQ_K, 1, 0, AUDIT_ARCH_X86_64))
    p.append((BPF_RET_K, 0, 0, SECCOMP_RET_KILL_PROCESS))
    p.append((BPF_LD_W_ABS, 0, 0, 0))                      # syscall nr
    rules = [(NR["socket"], deny_eacces), (NR["socketpair"], deny_eacces), (NR["connect"], deny_eacces),
             (NR["execve"], deny_eperm), (NR["execveat"], deny_eperm), (NR["fork"], deny_eperm),
             (NR["vfork"], deny_eperm), (NR["clone3"], enosys)]
    for nr, ret in rules:
        p.append((BPF_JEQ_K, 0, 1, nr))
        p.append((BPF_RET_K, 0, 0, ret))
    # clone: allow only thread creation (flags in args[0], low 32 bits at offset 16)
    p.append((BPF_JEQ_K, 0, 4, NR["clone"]))
    p.append((BPF_LD_W_ABS, 0, 0, 16))
    p.append((BPF_JSET_K, 1, 0, CLONE_THREAD))
    p.append((BPF_RET_K, 0, 0, deny_eperm))
    p.append((BPF_RET_K, 0, 0, SECCOMP_RET_ALLOW))
    p.append((BPF_RET_K, 0, 0, SECCOMP_RET_ALLOW))
    return p


def install_seccomp() -> dict:
    if platform.machine() != "x86_64":
        raise OSError("seccomp filter is defined for x86_64 only")
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "prctl(PR_SET_NO_NEW_PRIVS) failed")
    prog = _program()
    arr = (_Filter * len(prog))(*[_Filter(*ins) for ins in prog])
    fprog = _Prog(len(prog), ctypes.cast(arr, ctypes.POINTER(_Filter)))
    if libc.prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, ctypes.byref(fprog), 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "prctl(PR_SET_SECCOMP) failed")
    mode = libc.prctl(PR_GET_SECCOMP, 0, 0, 0, 0)
    return {"seccomp": "filter", "seccomp_mode": mode, "instructions": len(prog), "no_new_privs": True}


def _audit(event: str, args: tuple) -> None:
    if not _installed.get("audit"):
        return
    blocked = None
    if event in {"socket.__new__", "socket.connect", "socket.bind", "socket.getaddrinfo", "socket.gethostbyname"}:
        blocked = "network"
    elif event in {"subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.fork", "os.forkpty", "pty.spawn"}:
        blocked = "process"
    elif event == "open" and args:
        path = args[0]
        if isinstance(path, (str, bytes)):
            p = os.fsdecode(path)
            if CREDENTIAL_PATH.search(p) or re.match(r"^/proc/\d+/environ$", p) and not p.startswith(f"/proc/{os.getpid()}/"):
                blocked = "credential_path"
    elif event == "ctypes.dlopen" and _installed.get("components_loaded"):
        blocked = "native_library"
    if blocked:
        DENIALS.append({"kind": blocked, "event": event, "detail": repr(args[:1])[:200]})
        raise PermissionError(f"SIMLAB confinement: {blocked} access is not permitted ({event})")


def install(limits: dict) -> dict:
    """Install confinement; returns a record of what is in force. Fails closed."""
    info: dict = {"pid": os.getpid()}
    cpu = float(limits.get("cpu_s", 30.0))
    mem = int(limits.get("memory_mb", 1536))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
    resource.setrlimit(resource.RLIMIT_FSIZE, (2 * 2**30, 2 * 2**30))
    soft = max(1, int(cpu + 0.999))
    resource.setrlimit(resource.RLIMIT_CPU, (soft, soft + 5))
    resource.setrlimit(resource.RLIMIT_AS, (mem * 2**20, mem * 2**20))
    info["rlimits"] = {"cpu_s": soft, "address_space_mb": mem, "fsize_mb": 2048, "nofile": 256, "core": 0}
    info.update(install_seccomp())
    # Credential-free environment, enforced here too (defence in depth).
    leaked = [k for k in os.environ if re.search(r"(TOKEN|SECRET|PASSWORD|API_KEY|CREDENTIAL|AUTH)", k, re.I)]
    for k in leaked:
        del os.environ[k]
    info["env_credentials_removed"] = leaked
    _installed["audit"] = True
    sys.addaudithook(_audit)
    info["audit_hook"] = True
    return info


def mark_components_loaded() -> None:
    _installed["components_loaded"] = True


def selftest_bytes() -> bytes:
    """Program bytes, for the doctor and tests to inspect without installing."""
    return b"".join(struct.pack("HBBI", *ins) for ins in _program())
