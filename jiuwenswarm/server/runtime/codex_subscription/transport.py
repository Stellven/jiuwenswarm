"""Bounded stdio transport for the packaged Codex 0.144.4 App Server.

No raw protocol payloads, stderr or credentials are logged. Server requests are
rejected: the M1 chat slice does not yet implement host tools or approvals.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import subprocess
from importlib.metadata import version
from pathlib import Path
from typing import Callable


class CodexError(RuntimeError):
    """Only stable, credential-free error codes cross the product boundary."""


def child_environment(home: Path, source=None) -> dict[str, str]:
    source = os.environ if source is None else source
    allowed = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "TMPDIR", "HOME", "USERPROFILE", "LOCALAPPDATA", "APPDATA", "LANG", "LC_ALL", "PATHEXT", "COMSPEC"}
    env = {k: v for k, v in source.items() if k.upper() in allowed}
    env["CODEX_HOME"] = str(home.resolve())
    return env


class AppServerTransport:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.home = self.root / "codex-home"
        self.cwd = self.root / "chat-workspace"
        self.process = None
        self.listeners: set[Callable] = set()
        self.pending = {}
        self.sequence = 0
        self._start_lock = asyncio.Lock()
        self._write_lock = asyncio.Lock()
        self._reader = None
        self._ownership_handle = None

    def _claim_profile(self):
        handle = (self.root / "app-server.lock").open("a+b")
        try:
            if handle.tell() == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._ownership_handle = handle
        except OSError:
            handle.close()
            raise CodexError("PROFILE_IN_USE") from None

    async def start(self):
        async with self._start_lock:
            if self.process is not None and self.process.returncode is None:
                return
            if self.process is not None:
                await self.close()
            try:
                from codex_cli_bin import bundled_codex_path
                if version("openai-codex-cli-bin") != "0.144.4":
                    raise CodexError("RUNTIME_VERSION_MISMATCH")
                self.home.mkdir(parents=True, exist_ok=True)
                self.cwd.mkdir(parents=True, exist_ok=True)
                self._claim_profile()
                # This dedicated home is application-owned. Never load the IDE home.
                config = (
                    'forced_login_method = "chatgpt"\n'
                    'cli_auth_credentials_store = "file"\n'
                    'model_provider = "openai"\n'
                    'approval_policy = "untrusted"\n'
                    'sandbox_mode = "read-only"\n'
                    'web_search = "disabled"\n'
                    '[tools]\nview_image = false\n'
                    '[features]\nshell_tool = false\napps = false\n'
                    'js_repl = false\napply_patch_freeform = false\n'
                    'unified_exec = false\nskill_mcp_dependency_install = false\n'
                    '[mcp_servers]\n'
                )
                config_path = self.home / "config.toml"
                # Refuse an unexpected user-customized profile rather than silently
                # enabling providers/tools or overwriting their configuration.
                if config_path.exists() and config_path.read_text(encoding="utf-8") != config:
                    raise CodexError("PROFILE_CONFIG_CONFLICT")
                config_path.write_text(config, encoding="utf-8")
                kwargs = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
                self.process = await asyncio.create_subprocess_exec(
                    str(bundled_codex_path()), "app-server", "--listen", "stdio://",
                    cwd=self.cwd, env=child_environment(self.home),
                    stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL, limit=4 * 1024 * 1024, **kwargs,
                )
                self._reader = asyncio.create_task(self._read(self.process))
                await self.request("initialize", {"clientInfo": {"name": "ai4r", "version": "0.1.0"}, "capabilities": {"experimentalApi": False}})
                await self._send({"method": "initialized"})
            except BaseException as exc:
                await self.close()
                if isinstance(exc, (asyncio.CancelledError, CodexError)):
                    raise
                raise CodexError("RUNTIME_UNAVAILABLE") from None

    async def _send(self, message):
        async with self._write_lock:
            if not self.process or self.process.returncode is not None:
                raise CodexError("RUNTIME_DISCONNECTED")
            try:
                self.process.stdin.write((json.dumps(message) + "\n").encode())
                await self.process.stdin.drain()
            except (OSError, ConnectionError):
                raise CodexError("RUNTIME_DISCONNECTED") from None

    async def request(self, method, params=None):
        self.sequence += 1
        ident = self.sequence
        future = asyncio.get_running_loop().create_future()
        self.pending[ident] = future
        try:
            await self._send({"id": ident, "method": method, "params": params or {}})
            return await asyncio.wait_for(future, 30)
        except asyncio.TimeoutError:
            # A timed-out mutation may have been accepted. Close instead of replay.
            await self.close()
            raise CodexError("DELIVERY_UNKNOWN") from None
        finally:
            self.pending.pop(ident, None)

    def _notify(self, method, params):
        for callback in tuple(self.listeners):
            callback(method, params)

    async def _read(self, process):
        try:
            while line := await process.stdout.readline():
                message = json.loads(line)
                if not isinstance(message, dict):
                    raise ValueError("Invalid envelope")
                if "method" in message:
                    if "id" in message:
                        await self._send({"id": message["id"], "error": {"code": -32601, "message": "Tools and interactions are unavailable in this milestone."}})
                    else:
                        self._notify(message["method"], message.get("params") or {})
                else:
                    future = self.pending.get(message.get("id"))
                    if future is not None and not future.done():
                        if "error" in message:
                            future.set_exception(CodexError("RUNTIME_ERROR"))
                        else:
                            future.set_result(message.get("result") or {})
        except (ValueError, OSError, ConnectionError):
            pass
        finally:
            for future in tuple(self.pending.values()):
                if not future.done():
                    future.set_exception(CodexError("RUNTIME_DISCONNECTED"))
            self._notify("transport/closed", {})
            if process.returncode is None:
                with contextlib.suppress(ProcessLookupError):
                    process.terminate()

    async def close(self):
        process = self.process
        if process is None:
            if self._ownership_handle:
                self._ownership_handle.close()
                self._ownership_handle = None
            return
        if process.stdin:
            process.stdin.close()
        try:
            await asyncio.wait_for(process.wait(), 3)
        except asyncio.TimeoutError:
            with contextlib.suppress(ProcessLookupError):
                process.kill()
            await process.wait()
        if self._reader and self._reader is not asyncio.current_task():
            await self._reader
        self.process = None
        if self._ownership_handle:
            self._ownership_handle.close()
            self._ownership_handle = None
