"""One-operation local IPC server; no provider transport or credential access."""
import asyncio
import os
from pathlib import Path
import socket
import stat
import struct

from .request_validation import IntegrityFault, json_bytes, strict_json

PROTOCOL = "ai4r-router-ipc:1"
MAX_FRAME_BYTES = 4 * 1024 * 1024


def peer_uid(writer):
    sock = writer.get_extra_info("socket")
    if not hasattr(socket, "SO_PEERCRED"): raise PermissionError("Linux peer identity unavailable")
    return struct.unpack("3i", sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")))[1]


class RouterService:
    def __init__(self, engine, allowed_peer_uids):
        self.engine = engine
        self.allowed_peer_uids = frozenset(allowed_peer_uids)
        if not self.allowed_peer_uids: raise ValueError("empty router peer allowlist")

    async def handle(self, reader, writer):
        try:
            if peer_uid(writer) not in self.allowed_peer_uids: raise PermissionError("peer denied")
            header = await asyncio.wait_for(reader.readexactly(4), timeout=30)
            length = struct.unpack("!I", header)[0]
            if length == 0 or length > MAX_FRAME_BYTES: raise IntegrityFault("ipc_frame_size")
            frame = strict_json(await asyncio.wait_for(reader.readexactly(length), timeout=30))
            if not isinstance(frame, dict) or set(frame) != {"protocol", "op", "request"} or frame["protocol"] != PROTOCOL or frame["op"] != "route":
                raise IntegrityFault("ipc_protocol")
            # Work remains bounded by the independently enforced core timer; no provider can run here.
            reply = await asyncio.to_thread(self.engine.route, frame["request"])
            encoded = json_bytes({"protocol": PROTOCOL, **reply})
            if len(encoded) > MAX_FRAME_BYTES: raise IntegrityFault("ipc_reply_size")
            writer.write(struct.pack("!I", len(encoded)) + encoded)
            await writer.drain()
        except (PermissionError, IntegrityFault, asyncio.TimeoutError, asyncio.IncompleteReadError, ConnectionError):
            pass  # Refusal closes the transport; no input/credential is echoed.
        finally:
            writer.close()
            await writer.wait_closed()

    async def serve(self, path):
        if not hasattr(socket, "SO_PEERCRED"): raise RuntimeError("qualified Linux peer credentials required")
        path = Path(path)
        if path.exists() or path.is_symlink(): raise RuntimeError("router socket already exists; refuse foreign ownership")
        path.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
        server = await asyncio.start_unix_server(self.handle, path=str(path), limit=MAX_FRAME_BYTES + 4)
        os.chmod(path, 0o660)
        inode=path.lstat().st_ino
        try:
            async with server: await server.serve_forever()
        finally:
            server.close(); await server.wait_closed()
            if path.exists() and stat.S_ISSOCK(path.lstat().st_mode) and path.lstat().st_ino==inode: path.unlink()

