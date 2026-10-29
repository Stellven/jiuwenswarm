"""Protected M1 entrypoint and instance-owned native service supervision.

Only fixed native roles are launchable. The root parent prepares custody and
supervises the unprivileged tmux server; it never executes researcher commands.
"""
from __future__ import annotations

import argparse
import fcntl
import ipaddress
import json
import os
import shlex
import signal
import socket
import stat
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from .operator_config import ConfigError, OperatorConfiguration

APP_UID = APP_GID = 10001
ROLES = ("agentserver", "gateway", "frontend")


class StartupBlocked(RuntimeError):
    pass


def private_origin(origin, bind):
    """Check the published address, independently of internal container binds."""
    try:
        address = ipaddress.ip_address(bind)
        parsed = urlsplit(origin)
        host = ipaddress.ip_address(parsed.hostname)
        port = parsed.port
        if (address.is_unspecified or address.is_multicast or address.is_reserved
                or not (address.is_private or address.is_loopback)
                or not (host.is_private or host.is_loopback) or host.is_unspecified
                or parsed.scheme not in {"http", "https"} or parsed.username or parsed.password
                or parsed.path or parsed.query or parsed.fragment or port is None):
            raise ValueError
    except (ValueError, TypeError):
        raise StartupBlocked("PRIVATE_ORIGIN_INVALID") from None
    return origin


def _directory(path, *, uid=APP_UID, gid=APP_GID, mode=0o700):
    path = Path(path)
    if not path.is_absolute() or path.is_symlink():
        raise StartupBlocked("PROTECTED_DIRECTORY_INVALID")
    # Every existing ancestor must be a real directory. Never follow a
    # researcher-created link or recursively change saved artifact ownership.
    for parent in (path, *path.parents):
        if parent.is_symlink():
            raise StartupBlocked("PROTECTED_DIRECTORY_INVALID")
    path.mkdir(mode=mode, parents=True, exist_ok=True)
    metadata = path.stat()
    if not stat.S_ISDIR(metadata.st_mode):
        raise StartupBlocked("PROTECTED_DIRECTORY_INVALID")
    if os.geteuid() == 0:
        os.chown(path, uid, gid)
        path.chmod(mode)
    elif metadata.st_uid != uid or stat.S_IMODE(metadata.st_mode) != mode:
        raise StartupBlocked("PROTECTED_DIRECTORY_CUSTODY_INVALID")
    return path


def _private_json(path, value, *, uid=APP_UID, gid=APP_GID):
    raw = json.dumps(value, sort_keys=True, allow_nan=False).encode() + b"\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        if os.geteuid() == 0:
            os.fchown(fd, uid, gid)
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(fd)


def _read_json(path, *, uid=APP_UID):
    path = Path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        meta = os.fstat(fd)
        if (not stat.S_ISREG(meta.st_mode) or meta.st_uid != uid
                or stat.S_IMODE(meta.st_mode) != 0o600 or meta.st_nlink != 1 or meta.st_size > 65536):
            raise StartupBlocked("PRIVATE_RECORD_CUSTODY_INVALID")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            return json.loads(stream.read(65537))
    finally:
        os.close(fd)


class InstanceLease:
    def __init__(self, path):
        self.path = Path(path)
        self.fd = None

    def __enter__(self):
        self.fd = os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            meta = os.fstat(self.fd)
            if not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1 or meta.st_uid != os.geteuid():
                raise StartupBlocked("INSTANCE_LEASE_INVALID")
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, StartupBlocked):
            os.close(self.fd)
            self.fd = None
            raise StartupBlocked("INSTANCE_ALREADY_OWNED") from None
        return self

    def __exit__(self, *_):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None


def _configuration_is_valid(path, resolve_profile):
    """Validate only trusted operator bytes; failures permit inspection only."""
    try:
        path = Path(path)
        if (not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents))
                or not path.is_file() or path.stat().st_mode & 0o022):
            return False
        OperatorConfiguration.load(path, resolve_profile=resolve_profile)
        return True
    except (ConfigError, OSError, ValueError):
        return False


def prepare_environment(environ):
    env = dict(environ)
    # Only this boot's validation may enable execution. An inherited refusal
    # flag cannot stand in for validation and a corrected file needs a restart.
    env.pop('JIUWENSWARM_M1_REFUSAL_ONLY', None)
    if sys.platform != "linux" or os.geteuid() not in {0, APP_UID}:
        raise StartupBlocked("SUPPORTED_LINUX_IDENTITY_REQUIRED")
    private_origin(env.get("JIUWENSWARM_M1_ORIGIN", "http://127.0.0.1:5173"),
                   env.get("JIUWENSWARM_M1_BIND_ADDRESS", "127.0.0.1"))
    if env.get('JIUWENSWARM_M1_RSI_INBOX') not in {None, '/var/lib/ai4r-rsi-inbox'}:
        raise StartupBlocked('RSI_PUBLIC_INBOX_PATH_INVALID')
    state = _directory(env.get("JIUWENSWARM_M1_STATE", "/var/lib/ai4r"))
    accounts = _directory(env.get("JIUWENSWARM_M1_ACCOUNTS", "/var/lib/ai4r-accounts"))
    ipc = _directory("/run/ai4r")
    native = _directory(state / "native")
    _directory("/workspace/input")
    _directory("/var/lib/ai4r-executor", uid=0, gid=0, mode=0o711)
    _directory(accounts / "home")
    _directory(accounts / "home" / ".cache")
    # The product container must not receive custody mounts. Refuse even an
    # unreadable mount here rather than accidentally relaxing its permissions.
    for forbidden in ("/hidden-fixtures", "/var/lib/ai4r-referee", "/var/lib/ai4r-rsi/custodian"):
        if os.path.lexists(forbidden):
            raise StartupBlocked("HIDDEN_CUSTODY_MOUNT_PRESENT")
    configuration = Path(env.get("JIUWENSWARM_M1_CONFIG", "/etc/ai4r/config.yaml"))
    env.update({"JIUWENSWARM_M1_PROFILE": "1", "JIUWENSWARM_AGENT_SDK": "codex_subscription",
                "JIUWENSWARM_M1_ORIGIN": env.get("JIUWENSWARM_M1_ORIGIN", "http://127.0.0.1:5173"),
                "JIUWENSWARM_M1_STATE": str(state), "JIUWENSWARM_M1_ACCOUNTS": str(accounts),
                "JIUWENSWARM_M1_CONFIG": str(configuration), "JIUWENSWARM_DATA_DIR": str(native),
                "HOME": str(accounts / "home"), "JIUWENSWARM_HOME": str(accounts / "home"),
                "AGENT_SERVER_HOST": "127.0.0.1", "AGENT_SERVER_PORT": "18092", "AGENT_PORT": "18092",
                "AGENT_SERVER_URL": "ws://127.0.0.1:18092", "WEB_HOST": "127.0.0.1", "WEB_PORT": "19000",
                "WEB_PATH": "/ws", "GATEWAY_HOST": "127.0.0.1", "GATEWAY_PORT": "19001",
                "FRONTEND_HOST": "0.0.0.0", "FRONTEND_PORT": "5173", "PYTHONUNBUFFERED": "1",
                "JIUWENSWARM_M1_TOKEN_FILE": str(accounts / "sessions" / "session-token"),
                "JIUWENSWARM_M1_CLIENT_CONFIG": str(accounts / "sessions" / "client-defaults.json")})
    if (env.get('JIUWENSWARM_M1_LOCAL_RESEARCH') == '1'
            and not env.get('JIUWENSWARM_M1_BOOTSTRAP_BINDINGS')):
        # Explicit launcher selection captures defaults and bindings only.
        # Catalog admission, scientific resources and readiness remain separate.
        from .local_profile import PROFILE_NAME
        captured = state / 'operator' / PROFILE_NAME
        env['JIUWENSWARM_M1_CONFIG'] = str(captured / 'config.json')
        env['JIUWENSWARM_M1_BOOTSTRAP_BINDINGS'] = str(captured / 'bootstrap.json')
        result = subprocess.run([sys.executable, '-m', 'jiuwenswarm.research.local_profile'],
            env=env, cwd=native, preexec_fn=_drop_identity, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        if result.returncode:
            raise StartupBlocked('LOCAL_RESEARCH_CAPTURE_FAILED')
    # An explicitly supplied protected local capture must remain selected across
    # restarts. The config and gateway validations below still enforce its
    # ownership, exact configuration identity and bootstrap bindings.
    # Validation runs as the product identity so opening a new store never
    # leaves root-owned SQLite/WAL/artifact files in application custody.
    result = subprocess.run([sys.executable, "-m", "jiuwenswarm.research.bootstrap", "_validate-config"],
        env=env, cwd=native, preexec_fn=_drop_identity, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    if result.returncode == 2:
        env['JIUWENSWARM_M1_REFUSAL_ONLY'] = 'operator_configuration_unavailable'
    elif result.returncode:
        raise StartupBlocked("OPERATOR_CONFIGURATION_INVALID_OR_UNAVAILABLE")
    env["JIUWENSWARM_RUNTIME_WORKSPACE_READY"] = "1"
    return env, ipc


def _drop_identity():
    if os.geteuid() == 0:
        groups = [13100]
        if os.environ.get('JIUWENSWARM_M1_RSI_INBOX') == '/var/lib/ai4r-rsi-inbox':
            groups.append(13000)
        os.setgroups(groups)
        os.setgid(APP_GID)
        os.setuid(APP_UID)


def clear_stale_socket(path, *, uid, mode):
    path = Path(path)
    if not os.path.lexists(path):
        return
    meta = path.lstat()
    if not stat.S_ISSOCK(meta.st_mode) or meta.st_uid != uid or stat.S_IMODE(meta.st_mode) != mode:
        raise StartupBlocked("STALE_SOCKET_CUSTODY_INVALID")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.2)
        if probe.connect_ex(str(path)) == 0:
            raise StartupBlocked("PREVIOUS_PRIVATE_SERVICE_STILL_RUNNING")
    if path.lstat().st_ino != meta.st_ino:
        raise StartupBlocked("STALE_SOCKET_IDENTITY_CHANGED")
    path.unlink()


class NativeSessions:
    """One private tmux socket and exact session; no arbitrary shell API."""
    def __init__(self, root, boot_id, env):
        if not isinstance(boot_id, str) or len(boot_id) != 32 or any(c not in "0123456789abcdef" for c in boot_id):
            raise StartupBlocked("BOOT_ID_INVALID")
        self.root = Path(root)
        self.boot_id = boot_id
        self.name = "ai4r-" + boot_id
        self.socket = self.root / ("tmux-" + boot_id + ".sock")
        self.env = dict(env)
        self.panes = {}

    def _tmux(self, *arguments, check=True):
        return subprocess.run(["/usr/bin/tmux", "-S", str(self.socket), *arguments],
                              env=self.env, cwd=self.env["JIUWENSWARM_DATA_DIR"],
                              preexec_fn=_drop_identity, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, timeout=10, check=check)

    def start(self):
        if self.socket.exists() or self.socket.is_symlink():
            raise StartupBlocked("INSTANCE_SOCKET_EXISTS")
        try:
            log_root = _directory(Path(self.env['JIUWENSWARM_DATA_DIR']) / 'logs' / 'tmux')
            for index, role in enumerate(ROLES):
                gate = self.boot_id + '-' + role
                command = (shlex.join(['/usr/bin/tmux', '-S', str(self.socket), 'wait-for', gate])
                           + '; exec ' + shlex.join([sys.executable, "-m", "jiuwenswarm.research.native_entry", role]))
                arguments = (["new-session", "-d", "-s", self.name] if index == 0 else
                             ["split-window", "-d", "-t", "=" + self.name + ':'])
                pane = self._tmux(*arguments, "-P", "-F", "#{pane_id}", command).stdout.strip()
                if not pane.startswith("%") or not pane[1:].isdigit():
                    raise StartupBlocked("NATIVE_PANE_ID_INVALID")
                self.panes[role] = pane
                self._tmux("set-option", "-p", "-t", pane, "remain-on-exit", "on")
                log = log_root / (self.boot_id + '-' + role + '.log')
                descriptor = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                if os.geteuid() == 0:
                    os.fchown(descriptor, APP_UID, APP_GID)
                os.close(descriptor)
                self._tmux('pipe-pane', '-o', '-t', pane, 'exec /bin/cat >> ' + shlex.quote(str(log)))
            for role in ROLES:
                self._tmux('wait-for', '-S', self.boot_id + '-' + role)
        except BaseException:
            self.close()
            raise
        return dict(self.panes)

    def inspect(self):
        result = self._tmux("list-panes", "-t", "=" + self.name, "-F", "#{pane_id}\t#{pane_dead}\t#{pane_dead_status}", check=False)
        if result.returncode:
            return {"running": False, "panes": []}
        observed = []
        for line in result.stdout.splitlines():
            pane, dead, code = (line.split("\t") + [""] * 3)[:3]
            role = next((r for r, p in self.panes.items() if p == pane), None)
            if role is None:
                raise StartupBlocked("UNOWNED_NATIVE_PANE")
            observed.append({"role": role, "pane": pane, "running": dead == "0", "exit_code": int(code) if code else None})
        return {"running": len(observed) == len(ROLES) and all(p["running"] for p in observed), "panes": observed}

    def close(self):
        for pane in self.panes.values():
            self._tmux("send-keys", "-t", pane, "C-c", check=False)
        deadline = time.monotonic() + 10
        while self.panes and time.monotonic() < deadline:
            observed = self.inspect()
            if not any(p["running"] for p in observed["panes"]):
                break
            time.sleep(0.1)
        self._tmux("kill-session", "-t", "=" + self.name, check=False)


def supervise(env, ipc):
    boot = uuid.uuid4().hex
    _private_json(ipc / "session.json", {"session_id": boot, "capability": __import__("secrets").token_urlsafe(48)})
    sessions = NativeSessions(ipc, boot, env)
    stopped = False
    def stop(*_):
        nonlocal stopped
        stopped = True
    old = {signum: signal.signal(signum, stop) for signum in (signal.SIGINT, signal.SIGTERM)}
    broker = None
    router = None
    try:
        from .optional_router import OptionalRouter
        try:
            if not env.get('JIUWENSWARM_M1_REFUSAL_ONLY'):
                router = OptionalRouter.start(env)
        except Exception as exc:
            # Selection is optional. Keep diagnostic type without printing
            # protected config, prompts or credentials into public output.
            print(json.dumps({'event': 'optional-router-unavailable', 'error': type(exc).__name__}), flush=True)
        broker = subprocess.Popen([sys.executable, "-m", "jiuwenswarm.research.executor_rpc"],
            env=env, cwd=env["JIUWENSWARM_DATA_DIR"], stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
        panes = sessions.start()
        _private_json(ipc / "instance.json", {"schema": "ai4r-native-instance:1", "boot_id": boot, "panes": panes})
        announced = False
        while not stopped:
            if broker.poll() is not None:
                raise StartupBlocked("PROTECTED_EXECUTOR_BROKER_EXITED")
            request = ipc / "stop-request.json"
            if request.exists():
                if _read_json(request) != {"boot_id": boot}:
                    raise StartupBlocked("STOP_REQUEST_INVALID")
                request.unlink()
                stopped = True
                continue
            state = sessions.inspect()
            if not state["running"]:
                print(json.dumps({"event": "native-service-exit", **state}), flush=True)
                return 1
            handoff = ipc / "browser-bootstrap.json"
            if not announced and handoff.exists():
                value = _read_json(handoff)
                if set(value) != {"url"} or not isinstance(value["url"], str) or not value["url"].startswith(env["JIUWENSWARM_M1_ORIGIN"] + "/#"):
                    raise StartupBlocked("BROWSER_BOOTSTRAP_INVALID")
                # Deliberately stdout only, never a persisted service log.
                print("Open JiuwenSwarm: " + value["url"], flush=True)
                handoff.unlink()
                announced = True
            time.sleep(0.25)
        return 0
    finally:
        sessions.close()
        if router is not None:
            router.close()
        if broker is not None and broker.poll() is None:
            broker.terminate()
            try:
                broker.wait(timeout=15)
            except subprocess.TimeoutExpired:
                broker.kill()
                broker.wait(timeout=5)
        for name in ("session.json", "instance.json", "browser-bootstrap.json", "stop-request.json"):
            path = ipc / name
            if path.exists() and not path.is_symlink():
                path.unlink()
        for signum, handler in old.items():
            signal.signal(signum, handler)


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments == ["_validate-config"]:
        if os.geteuid() != APP_UID:
            raise StartupBlocked("CONFIG_VALIDATION_IDENTITY_INVALID")
        from .state import SQLiteRunStore
        store = SQLiteRunStore(os.environ["JIUWENSWARM_M1_STATE"], input_root='/workspace/input', recover=False)
        try:
            valid = _configuration_is_valid(os.environ["JIUWENSWARM_M1_CONFIG"], store.read_record)
        finally:
            store.close()
        from .native_logging import configure_native_logging
        configure_native_logging(Path(os.environ["JIUWENSWARM_DATA_DIR"]) / "logs" / "startup")
        from jiuwenswarm.common.utils import prepare_runtime_workspace
        prepare_runtime_workspace(cleanup_stale_descs=False, migrate_config=True)
        return 0 if valid else 2
    parser = argparse.ArgumentParser(prog="jiuwenswarm-start", description="Start the protected native M1 application.")
    parser.add_argument("mode", nargs="?", default="all", choices=["all"])
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--status", action="store_true")
    actions.add_argument("--stop", action="store_true")
    actions.add_argument("--attach", choices=ROLES)
    actions.add_argument("--detach", action="store_true")
    args = parser.parse_args(arguments)
    try:
        if args.status or args.stop or args.attach or args.detach:
            ipc = Path("/run/ai4r")
            record = _read_json(ipc / "instance.json")
            if set(record) != {"schema", "boot_id", "panes"} or record["schema"] != "ai4r-native-instance:1":
                raise StartupBlocked("INSTANCE_RECORD_INVALID")
            sessions = NativeSessions(ipc, record["boot_id"], {**os.environ,
                "JIUWENSWARM_DATA_DIR": os.environ.get("JIUWENSWARM_DATA_DIR", "/var/lib/ai4r/native")})
            panes = record["panes"]
            if (not isinstance(panes, dict) or set(panes) != set(ROLES)
                    or any(not isinstance(p, str) or not p.startswith("%") or not p[1:].isdigit() for p in panes.values())):
                raise StartupBlocked("INSTANCE_RECORD_INVALID")
            sessions.panes = panes
            if args.status:
                print(json.dumps(sessions.inspect()))
            elif args.stop:
                _private_json(ipc / "stop-request.json", {"boot_id": record["boot_id"]})
            elif args.detach:
                sessions._tmux("detach-client", "-s", "=" + sessions.name)
            else:
                sessions._tmux("select-pane", "-t", panes[args.attach])
                _drop_identity()
                os.execve("/usr/bin/tmux", ["tmux", "-S", str(sessions.socket), "attach-session", "-t", "=" + sessions.name], sessions.env)
            return 0
        # Lease outside app-writable state prevents duplicate startup and
        # accidental replacement of another live boot's private IPC session.
        lease_root = _directory("/run/ai4r-supervisor", uid=os.geteuid(), gid=os.getegid())
        with InstanceLease(lease_root / "launcher.lock"):
            env, ipc = prepare_environment(os.environ)
            for name in ("model.sock", "authorization.sock", "agent-status.sock"):
                clear_stale_socket(ipc / name, uid=APP_UID, mode=0o600)
            clear_stale_socket("/run/ai4r-executor/executor.sock", uid=0, mode=0o660)
            # Files remaining after an unclean container stop are from this
            # exclusive named volume, never another live launcher.
            for name in ("session.json", "instance.json", "browser-bootstrap.json", "stop-request.json"):
                path = ipc / name
                if path.is_symlink():
                    raise StartupBlocked("STALE_PRIVATE_RECORD_INVALID")
                if path.exists():
                    _read_json(path)
                    path.unlink()
            return supervise(env, ipc)
    except (StartupBlocked, ConfigError, OSError, subprocess.SubprocessError) as exc:
        # Do not include configuration values, credentials or child stderr.
        print("M1 startup blocked: " + (str(exc) if isinstance(exc, (StartupBlocked, ConfigError)) else type(exc).__name__), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
