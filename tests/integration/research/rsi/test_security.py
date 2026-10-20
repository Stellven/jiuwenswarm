"""Finite IPC denial controls. The complete sandbox violation suite is separate."""
import asyncio
import json
import os
import struct

import pytest

from jiuwenswarm.research_rsi.ports import PrivatePort, request


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["wrong_peer", "final_operation", "unknown_field", "oversized", "malformed"])
async def test_actual_private_port_refuses_ungranted_effect_before_handler(tmp_path, fault):
    assert hasattr(os, "getuid"), "BLOCKED: Linux peer identity required"
    effects = []
    async def inspect(ref):
        effects.append(ref)
        return {"state": "inspection-only"}
    socket = tmp_path / "private.sock"
    port = PrivatePort({"session_inspect": inspect}, [os.getuid() + 1 if fault == "wrong_peer" else os.getuid()])
    server = asyncio.create_task(port.serve(socket))
    try:
        async with asyncio.timeout(5):
            while not socket.is_socket(): await asyncio.sleep(.01)
        body = {"protocol": "ai4r-rsi-ipc:1", "operation": "session_inspect", "ref": {"id": "not-an-authority", "sha256": "a" * 64}}
        if fault == "final_operation": body["operation"] = "custodian_final"
        if fault == "unknown_field": body["command"] = "forbidden-effect"
        raw = json.dumps(body).encode() if fault != "malformed" else b"{"
        reader, writer = await asyncio.open_unix_connection(socket)
        try:
            writer.write(struct.pack("!I", 4 * 1024 * 1024 + 1 if fault == "oversized" else len(raw)))
            if fault != "oversized": writer.write(raw)
            await writer.drain()
            try: reply = await asyncio.wait_for(reader.read(4096), 5)
            except ConnectionResetError: reply = b""
            assert not reply or b'"status":"blocked"' in reply
            assert b"forbidden-effect" not in reply and b"not-an-authority" not in reply
        finally:
            writer.close()
            try: await writer.wait_closed()
            except ConnectionResetError: pass
        assert effects == [], "Ungrantable operation reached an effect handler"
    finally:
        server.cancel(); await asyncio.gather(server, return_exceptions=True)
        assert not socket.exists()


@pytest.mark.asyncio
async def test_private_client_rejects_foreign_socket_custody_before_connect(tmp_path):
    socket = tmp_path / "private.sock"
    async def inspect(ref): raise AssertionError("Foreign socket reached handler")
    server = asyncio.create_task(PrivatePort({"session_inspect": inspect}, [os.getuid()]).serve(socket))
    try:
        async with asyncio.timeout(5):
            while not socket.is_socket(): await asyncio.sleep(.01)
        with pytest.raises(PermissionError):
            await request(socket, os.getuid() + 1, "session_inspect", {"id": "r", "sha256": "a" * 64})
    finally:
        server.cancel(); await asyncio.gather(server, return_exceptions=True)
