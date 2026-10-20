"""Fault endpoints exercise real IPC and the independently fixed core deadline."""
import asyncio
import multiprocessing
import os
import time

import pytest

from jiuwenswarm.research.router_client import RouterPort, PlatformIntegrityError, encode_frame, read_frame
from tests.integration.research.router.test_ipc_boundary import await_socket


def _fault_endpoint(path, fault):
    async def handle(reader, writer):
        try:
            await read_frame(reader)
            if fault == "hang":
                await asyncio.sleep(60); return
            if fault == "reset": return
            reply = {"protocol": "ai4r-router-ipc:1"}
            if fault == "integrity": reply.update(kind="integrity_fault", integrity_fault={"execution_id": "e"})
            elif fault == "unapproved": reply.update(kind="decision", decision={"selected_endpoint": "foreign"})
            elif fault == "invalid": reply.update(kind="unrecognized")
            elif fault == "no_route":
                from jiuwenswarm.research_router.engine import DecisionEngine
                reply.update(DecisionEngine.no_route("e", "AUDIT_UNAVAILABLE"))
            writer.write(encode_frame(reply)); await writer.drain()
        finally:
            writer.close(); await writer.wait_closed()
    async def main():
        server = await asyncio.start_unix_server(handle, path=path)
        os.chmod(path, 0o660)
        async with server: await server.serve_forever()
    asyncio.run(main())


def context():
    return {"call_function": "worker", "router": {"enabled": True, "deadline_s": 30,
            "profile_ref": {"id": "profile", "sha256": "a" * 64}},
            "route_request": {"execution_id": "e"}, "approved_model_ids": []}


@pytest.mark.parametrize("fault,expected", [("reset", "error"), ("invalid", "invalid_decision"),
    ("unapproved", "unapproved_model"), ("no_route", "no_route"), ("integrity", None), ("hang", "timeout")])
def test_real_prestart_faults_and_fixed_thirty_second_deadline(tmp_path, fault, expected, request):
    assert hasattr(os, "getuid"), "BLOCKED: Linux peer credentials required"
    path = tmp_path / "fault.sock"
    child = multiprocessing.Process(target=_fault_endpoint, args=(str(path), fault)); child.start()
    try:
        await_socket(child, path)
        start = time.monotonic()
        if fault == "integrity":
            with pytest.raises(PlatformIntegrityError): asyncio.run(RouterPort(path, peer_uid=os.getuid()).select(context()))
        else:
            choice = asyncio.run(RouterPort(path, peer_uid=os.getuid()).select(context()))
            assert choice.model_id == "codex-cli-default" and choice.decision_source == "codex_router_failed"
            assert choice.router_failure == expected and choice.route_decision_ref is None
            if fault == "no_route": assert choice.router_halt_code == "AUDIT_UNAVAILABLE"
        request.node.user_properties.extend([("actual_elapsed_s", time.monotonic() - start),
                                             ("core_deadline_s", 30)])
    finally:
        child.terminate(); child.join(5)
        assert not child.is_alive()


def test_missing_process_has_explicit_fixed_fallback(tmp_path):
    choice = asyncio.run(RouterPort(tmp_path / "absent.sock", peer_uid=os.getuid()).select(context()))
    assert choice.router_failure == "missing" and choice.decision_source == "codex_router_failed"
