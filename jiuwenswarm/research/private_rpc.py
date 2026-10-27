"""Finite authenticated Linux RPC for protected platform processes only.

Each server installs a fixed operation table in code. Payloads cannot select
modules, callables, paths or commands. Operation owners durably claim effects;
the client never retries a request whose delivery may have happened.
"""
from __future__ import annotations

import asyncio
import inspect
import os
import secrets
import stat
from pathlib import Path

from .bridge import BridgeError
from .router_client import (MAX_IPC_FRAME_BYTES, PlatformIntegrityError, close_writer,
                            encode_frame, peer_credentials, read_frame)


def fault_summary(error):
    """Exception class, short code and the innermost in-package frame (module:function:line)."""
    code = getattr(error, 'code', None)
    frames, tb = [], error.__traceback__
    while tb is not None:
        frames.append((tb.tb_frame.f_globals.get('__name__', ''), tb.tb_frame.f_code.co_name, tb.tb_lineno))
        tb = tb.tb_next
    inner = [f for f in frames if f[0].split('.')[0] == __name__.split('.')[0]]
    module, function, line = (inner or frames or [('', '', 0)])[-1]
    return {'exception_class': type(error).__name__,
            'code': code if isinstance(code, str) and code.isidentifier() and len(code) <= 64 else None,
            'frame': f'{module}:{function}:{line}'}


class PrivateRPCServer:
    def __init__(self, path, *, protocol, session_id, capability, handlers, allowed_uids,
                 socket_mode=0o600, directory_mode=0o700, group_id=None, operation_uids=None,
                 fault_recorder=None):
        self.fault_recorder = fault_recorder
        self.path = Path(path)
        self.protocol, self.session_id, self.capability = protocol, session_id, capability
        self.handlers, self.allowed_uids = dict(handlers), frozenset(allowed_uids)
        self.operation_uids={name:frozenset(uids) for name,uids in (operation_uids or {}).items()}
        if (set(self.operation_uids)-set(self.handlers)
                or any(not uids or not uids<=self.allowed_uids for uids in self.operation_uids.values())):
            raise ValueError('PRIVATE_RPC_OPERATION_POLICY_INVALID')
        self.socket_mode, self.directory_mode, self.gid = socket_mode, directory_mode, group_id
        if not self.handlers or not self.allowed_uids or socket_mode not in {0o600, 0o660} or directory_mode not in {0o700, 0o710, 0o2710}:
            raise ValueError('PRIVATE_RPC_POLICY_INVALID')
        self.server = None
        self.tasks = set()
        self.inode = None

    def _record_fault(self, operation, payload, error):
        """Keep the cause of a masked fault: class and code, never message or args."""
        if self.fault_recorder is None: return
        try:
            self.fault_recorder(operation, payload, fault_summary(error))
        except Exception:
            pass

    async def _handle(self, reader, writer):
        task = asyncio.current_task()
        self.tasks.add(task)
        try:
            _, uid, _ = peer_credentials(writer.get_extra_info('socket'))
            if uid not in self.allowed_uids:
                return
            async with asyncio.timeout(30):
                request = await read_frame(reader)
            if (set(request) != {'protocol', 'session_id', 'capability', 'operation', 'payload'}
                    or request['protocol'] != self.protocol or request['session_id'] != self.session_id
                    or not isinstance(request['capability'], str)
                    or not secrets.compare_digest(request['capability'], self.capability)
                    or request['operation'] not in self.handlers or not isinstance(request['payload'], dict)):
                return
            if uid not in self.operation_uids.get(request['operation'],self.allowed_uids):
                return
            try:
                result = self.handlers[request['operation']](request['payload'])
                if inspect.isawaitable(result): result = await result
                reply = {'protocol': self.protocol, 'result': result}
            except PlatformIntegrityError as error:
                self._record_fault(request['operation'], request['payload'], error)
                reply = {'protocol': self.protocol, 'error': 'PLATFORM_INTEGRITY_FAULT'}
            except Exception as error:
                # No exception message, credential, path or input is reflected.
                allowed = {'ENVIRONMENT_BLOCKED', 'DELIVERY_UNKNOWN', 'auth_failed', 'timeout',
                           'invalid_request', 'AUDIT_UNAVAILABLE'}
                code = getattr(error, 'code', None)
                if code not in allowed: self._record_fault(request['operation'], request['payload'], error)
                reply = {'protocol': self.protocol, 'error': code if code in allowed else 'PLATFORM_INTEGRITY_FAULT'}
            writer.write(encode_frame(reply))
            await writer.drain()
        except (ValueError, OSError, ConnectionError, TimeoutError, asyncio.IncompleteReadError):
            pass
        finally:
            await close_writer(writer)
            self.tasks.discard(task)

    async def start(self):
        self.path.parent.mkdir(mode=self.directory_mode, parents=True, exist_ok=True)
        if self.gid is not None: os.chown(self.path.parent, os.geteuid(), self.gid)
        custody = self.path.parent.lstat()
        if (not stat.S_ISDIR(custody.st_mode) or custody.st_uid != os.geteuid()
                or stat.S_IMODE(custody.st_mode) != self.directory_mode
                or self.path.exists() or self.path.is_symlink()):
            raise PlatformIntegrityError('PRIVATE_RPC_CUSTODY_INVALID')
        self.server = await asyncio.start_unix_server(self._handle, path=str(self.path), limit=MAX_IPC_FRAME_BYTES + 4)
        if self.gid is not None: os.chown(self.path, os.geteuid(), self.gid)
        self.path.chmod(self.socket_mode)
        self.inode = self.path.stat().st_ino
        return self

    async def close(self):
        self.capability = secrets.token_urlsafe(32)
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()
        for task in tuple(self.tasks): task.cancel()
        if self.tasks:
            await asyncio.wait_for(asyncio.gather(*self.tasks, return_exceptions=True), timeout=15)
        if self.path.exists() and self.path.lstat().st_ino == self.inode:
            self.path.unlink()


class PrivateRPCClient:
    def __init__(self, path, *, protocol, session_id, capability, peer_uid, socket_mode=0o600):
        self.path = Path(path)
        self.protocol, self.session_id, self.capability = protocol, session_id, capability
        self.peer_uid, self.socket_mode = peer_uid, socket_mode

    async def call(self, operation, payload, *, timeout_s=30):
        if type(timeout_s) not in {int, float} or not 0 < timeout_s <= 3600:
            raise PlatformIntegrityError('PRIVATE_RPC_DEADLINE_INVALID')
        writer = None
        try:
            async with asyncio.timeout(timeout_s):
                custody = self.path.lstat()
                if (not stat.S_ISSOCK(custody.st_mode) or custody.st_uid != self.peer_uid
                        or stat.S_IMODE(custody.st_mode) != self.socket_mode):
                    raise PlatformIntegrityError('PRIVATE_RPC_CUSTODY_INVALID')
                reader, writer = await asyncio.open_unix_connection(str(self.path), limit=MAX_IPC_FRAME_BYTES + 4)
                _, uid, _ = peer_credentials(writer.get_extra_info('socket'))
                if uid != self.peer_uid: raise PlatformIntegrityError('PRIVATE_RPC_PEER_INVALID')
                writer.write(encode_frame({'protocol': self.protocol, 'session_id': self.session_id,
                    'capability': self.capability, 'operation': operation, 'payload': payload}))
                await writer.drain()
                reply = await read_frame(reader)
                if reply.get('protocol') != self.protocol:
                    raise PlatformIntegrityError('PRIVATE_RPC_PROTOCOL_INVALID')
                if reply.get('error') == 'PLATFORM_INTEGRITY_FAULT':
                    raise PlatformIntegrityError('PRIVATE_RPC_OPERATION_REJECTED')
                if reply.get('error'): raise BridgeError(reply['error'])
                if 'result' not in reply: raise PlatformIntegrityError('PRIVATE_RPC_REPLY_INVALID')
                return reply['result']
        except (OSError, ConnectionError, TimeoutError, asyncio.IncompleteReadError):
            raise BridgeError('DELIVERY_UNKNOWN') from None
        finally:
            if writer is not None: await close_writer(writer)
