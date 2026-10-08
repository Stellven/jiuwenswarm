"""Actual custody/lifetime locks and bounded fixture protocol denial.

These checks establish local control behavior, never live semantic acceptance
or availability of the required real POSIX-container model boundary.
"""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys

from fastapi import FastAPI
import httpx
import pytest

from jiuwenswarm.ai4research.bridge import LocalModelBridge, NativeCompletionBackend
from jiuwenswarm.ai4research.common import GovernanceError, canonical_json, hash_json
from jiuwenswarm.ai4research.http import trial_router
from jiuwenswarm.ai4research.identity import IdentityStore
from jiuwenswarm.ai4research import service as host
from tests.unit_tests.ai4research.test_m0_001 import FixtureService, invocation


def test_application_lease_actual_process_exclusion_and_release(tmp_path):
    state = tmp_path / "private-state"
    lease = host.ApplicationLease(state).acquire()
    program = (
        "import sys; from jiuwenswarm.ai4research.service import ApplicationLease; "
        "from jiuwenswarm.ai4research.common import GovernanceError\n"
        "try:\n lease=ApplicationLease(sys.argv[1]).acquire(); print('acquired'); lease.release()\n"
        "except GovernanceError as error:\n print(error.code)\n"
    )
    child = subprocess.run([sys.executable, "-c", program, str(state)], capture_output=True, text=True, timeout=15)
    assert child.returncode == 0 and child.stdout.strip() == "application_in_use"
    lease.release()
    lease.release()
    child = subprocess.run([sys.executable, "-c", program, str(state)], capture_output=True, text=True, timeout=15)
    assert child.returncode == 0 and child.stdout.strip() == "acquired"


def test_redirected_custody_is_rejected_without_touching_target(tmp_path):
    target = tmp_path / "foreign"
    target.mkdir()
    sentinel = target / "keep.txt"
    sentinel.write_text("unaltered", encoding="utf-8")
    redirect = tmp_path / "redirect"
    try:
        try:
            redirect.symlink_to(target, target_is_directory=True)
        except OSError:
            assert os.name == "nt"
            result = subprocess.run(["cmd", "/c", "mklink", "/J", str(redirect), str(target)], capture_output=True, timeout=15)
            assert result.returncode == 0
        with pytest.raises(GovernanceError, match="reparse|symlinks"):
            host.ApplicationLease(redirect).acquire()
        assert sentinel.read_text(encoding="utf-8") == "unaltered"
        assert not (target / "service.lock").exists()
    finally:
        if redirect.is_symlink():
            redirect.unlink()
        elif redirect.exists():
            os.rmdir(redirect)


def test_token_renewal_actual_identity_revokes_old_header_credential(tmp_path):
    root = tmp_path / "state"
    lease = host.ApplicationLease(root).acquire()
    try:
        identity = IdentityStore(root / "identity/product.sqlite")
        identity.initialize()
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        registered = identity.register_workspace(workspace)
        token_file = root / "session.token"
        first = host._renew_token(identity, registered.workspace_id, token_file)
        assert identity.authenticate(first).workspace_id == registered.workspace_id
        second = host._renew_token(identity, registered.workspace_id, token_file)
        assert second != first and token_file.read_text(encoding="utf-8") == second
        with pytest.raises(GovernanceError):
            identity.authenticate(first)
        assert identity.authenticate(second).workspace_id == registered.workspace_id
        assert not list(root.glob("session-*.tmp"))
        if os.name == "posix":
            assert token_file.stat().st_mode & 0o777 == 0o600
    finally:
        lease.release()


@pytest.mark.asyncio
async def test_failed_startup_releases_application_lease(tmp_path, monkeypatch):
    async def fail(*args, **kwargs):
        raise GovernanceError("environment_unavailable", "Fixture startup failure.")
    monkeypatch.setattr(host, "_bootstrap_owned", fail)
    with pytest.raises(GovernanceError, match="startup failure"):
        await host.bootstrap(tmp_path / "state", tmp_path / "workspace", origin="http://127.0.0.1:4311")
    lease = host.ApplicationLease(tmp_path / "state").acquire()
    lease.release()


@pytest.mark.asyncio
async def test_actual_bootstrap_recovers_only_under_lifetime_lease(tmp_path, monkeypatch):
    state = tmp_path / "state"
    observed = []
    original = host.RunStore.recover_interrupted
    def guarded_recovery(store):
        with pytest.raises(GovernanceError, match="Another application process"):
            host.ApplicationLease(state).acquire()
        observed.append("lease-before-recovery")
        return original(store)
    class UnreadyBridge(LocalModelBridge):
        async def start(self):
            # No native account probe or insecure substitute in this fixture.
            raise GovernanceError("environment_unavailable", "Fixture IPC unavailable.")
    monkeypatch.setattr(host.RunStore, "recover_interrupted", guarded_recovery)
    monkeypatch.setattr(host, "LocalModelBridge", UnreadyBridge)
    application, native, refresh, token_path = await host.bootstrap(state, tmp_path / "workspace",
        origin="http://127.0.0.1:4311")
    try:
        assert observed == ["lease-before-recovery"]
        assert token_path.is_file() and application.baseline is None
        assert application.prepare_submission is refresh
        assert native.transport.process is None
        assert (await application.readiness())["ready"] is False
        await refresh()
        assert native.transport.process is None
    finally:
        await application.shutdown()
        await application.bridge.close()
        application.process_lease.release()
    assert observed == ["lease-before-recovery", "lease-before-recovery"]
    reclaimed = host.ApplicationLease(state).acquire()
    reclaimed.release()


@pytest.mark.asyncio
async def test_same_fingerprint_new_epoch_cannot_run_old_admission(tmp_path):
    service = FixtureService(tmp_path)
    backend = NativeCompletionBackend(service)
    backend.bind_account(await backend.readiness())
    service.epoch = "different-generation"
    with pytest.raises(GovernanceError, match="generation changed"):
        await backend.complete(**invocation())
    assert not service.transport.requests


@pytest.mark.asyncio
async def test_frozen_runtime_identity_is_checked_before_dispatch(tmp_path):
    service = FixtureService(tmp_path)
    request = invocation()
    request["identities"]["runtime_identity"] = {"account_fingerprint": service.account_fingerprint,
        "account_epoch": "stale-epoch", "runtime_version": "0.144.4"}
    with pytest.raises(GovernanceError, match="Frozen runtime"):
        await NativeCompletionBackend(service).complete(**request)
    assert not service.transport.requests


@pytest.mark.asyncio
async def test_epoch_change_after_native_completion_still_blocks_and_closes(tmp_path):
    service = FixtureService(tmp_path)
    original = service.transport.request
    async def change(method, params):
        result = await original(method, params)
        if method == "turn/start":
            service.epoch = "changed-in-flight"
        return result
    service.transport.request = change
    with pytest.raises(GovernanceError, match="generation changed"):
        await NativeCompletionBackend(service).complete(**invocation())
    assert service.transport.closed
    assert len([m for m, _ in service.transport.requests if m == "turn/start"]) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["text", "thread_id", "turn_id", "model", "provider", "runtime_version",
                                  "provider_version", "elapsed_seconds", "model_calls", "usage", "cost", "seed",
                                  "effects", "is_mock", "mock", "usage_unavailable_reason", "cost_unavailable_reason",
                                  "seed_unavailable_reason", "requested_model", "configured_model", "configured_model_provider",
                                  "model_identity_basis", "served_model", "served_model_unavailable_reason",
                                  "account_fingerprint", "account_epoch", "unsupported_correlation"])
async def test_runtime_observations_cannot_be_overwritten_by_identity_payload(tmp_path, field):
    request = invocation()
    request["identities"][field] = "forged-fixture-observation"
    service = FixtureService(tmp_path)
    with pytest.raises(GovernanceError, match="runtime observations"):
        await NativeCompletionBackend(service).complete(**request)
    assert not service.transport.requests


@pytest.mark.asyncio
async def test_exact_frozen_runtime_identity_is_legitimate_optional_correlation(tmp_path):
    service = FixtureService(tmp_path)
    request = invocation()
    request["identities"]["runtime_identity"] = {"account_fingerprint": service.account_fingerprint,
        "account_epoch": service.epoch, "runtime_version": "0.144.4"}
    outcome = await NativeCompletionBackend(service).complete(**request)
    assert outcome["runtime_identity"] == request["identities"]["runtime_identity"]
    assert outcome["configured_model"] == "fixture-model" and outcome["served_model"] is None
    assert [method for method, _ in service.transport.requests] == ["thread/start", "turn/start"]


@pytest.mark.asyncio
@pytest.mark.parametrize("runtime_identity", [None, "forged", {},
    {"account_fingerprint": "fixture-account", "account_epoch": "fixture-epoch", "runtime_version": "0.144.4", "model": "forged"},
    {"account_fingerprint": "fixture-account", "account_epoch": "", "runtime_version": "0.144.4"},
    {"account_fingerprint": "fixture-account", "account_epoch": "x" * 257, "runtime_version": "0.144.4"},
    {"account_fingerprint": "fixture-account", "account_epoch": "fixture-epoch", "runtime_version": False},
])
async def test_runtime_identity_has_only_bounded_generation_fields(tmp_path, runtime_identity):
    service = FixtureService(tmp_path)
    request = invocation()
    request["identities"]["runtime_identity"] = runtime_identity
    with pytest.raises(GovernanceError) as halted:
        await NativeCompletionBackend(service).complete(**request)
    assert halted.value.code == "invalid_input" and not service.transport.requests


@pytest.mark.asyncio
async def test_cancelling_native_owned_turn_interrupts_and_closes_without_replay(tmp_path):
    service = FixtureService(tmp_path, "timeout")
    dispatched = asyncio.Event()
    original = service.transport.request
    async def observe(method, params):
        result = await original(method, params)
        if method == "turn/start":
            dispatched.set()
        return result
    service.transport.request = observe
    task = asyncio.create_task(NativeCompletionBackend(service).complete(**invocation()))
    await asyncio.wait_for(dispatched.wait(), 1)
    task.cancel()
    result = (await asyncio.gather(task, return_exceptions=True))[0]
    assert isinstance(result, asyncio.CancelledError)
    assert service.transport.closed
    assert [method for method, _ in service.transport.requests] == ["thread/start", "turn/start", "turn/interrupt"]
    assert not service.transport.listeners


@pytest.mark.asyncio
async def test_oversized_native_output_closes_once_without_replay(tmp_path):
    service = FixtureService(tmp_path)
    original = service.transport.request
    async def oversized(method, params):
        if method == "turn/start":
            for listener in tuple(service.transport.listeners):
                listener("item/agentMessage/delta", {"threadId": "fixture-thread-1", "turnId": "fixture-turn",
                    "delta": "x" * 131073})
        return await original(method, params)
    service.transport.request = oversized
    with pytest.raises(GovernanceError, match="output exceeded"):
        await NativeCompletionBackend(service).complete(**invocation())
    assert service.transport.closed
    assert len([m for m, _ in service.transport.requests if m == "turn/start"]) == 1


@pytest.mark.asyncio
async def test_readiness_is_inside_budget_and_busy_call_does_not_close_owner(tmp_path):
    service = FixtureService(tmp_path)
    entered = asyncio.Event()
    release = asyncio.Event()
    async def blocked():
        entered.set()
        await release.wait()
        return {"state": "ready"}
    service.status = blocked
    backend = NativeCompletionBackend(service)
    first = asyncio.create_task(backend.complete(**invocation()))
    await entered.wait()
    with pytest.raises(GovernanceError, match="already has an active"):
        await backend.complete(**invocation(ident="busy-second"))
    assert service.transport.closed is False and not service.transport.requests
    first.cancel()
    await asyncio.gather(first, return_exceptions=True)
    assert service.transport.closed and not service.transport.requests
    short = invocation()
    short["timeout_seconds"] = 0.01
    with pytest.raises(GovernanceError, match="during readiness"):
        await backend.complete(**short)
    assert not service.transport.requests


class ProtocolWriter:
    def __init__(self):
        self.frames = []
        self.closed = False
    def write(self, frame):
        self.frames.append(frame)
    async def drain(self):
        pass
    def close(self):
        self.closed = True
    async def wait_closed(self):
        pass


async def protocol_frame(bridge, request, token=None):
    reader = asyncio.StreamReader()
    reader.feed_data(canonical_json({"token": token or bridge.token, "request": request}) + b"\n")
    reader.feed_eof()
    writer = ProtocolWriter()
    await bridge._serve(reader, writer)
    assert writer.closed
    return json.loads(writer.frames[0])


@pytest.mark.asyncio
async def test_protected_scope_grant_is_exact_and_one_use(tmp_path):
    service = FixtureService(tmp_path)
    bridge = LocalModelBridge(tmp_path / "ipc", NativeCompletionBackend(service))
    request = invocation()
    bridge.grants["call-1"] = hash_json(request)
    denied = await protocol_frame(bridge, request, token="foreign-fixture-token")
    assert denied["error"]["code"] == "policy_denied" and not service.transport.requests
    changed = {**request, "model": "another-model"}
    denied = await protocol_frame(bridge, changed)
    assert denied["error"]["code"] == "policy_denied" and not service.transport.requests
    success = await protocol_frame(bridge, request)
    assert success["result"]["model_calls"] == 1 and success["result"]["text"] == "{}"
    bridge.grants["call-1"] = hash_json(request)
    replay = await protocol_frame(bridge, request)
    assert replay["error"]["code"] == "policy_denied"
    assert len([m for m, _ in service.transport.requests if m == "turn/start"]) == 1


@pytest.mark.asyncio
async def test_unready_ipc_never_probes_native_account(tmp_path):
    service = FixtureService(tmp_path)
    async def unexpected():
        raise AssertionError("Unsafe IPC must not probe provider credentials.")
    service.status = unexpected
    bridge = LocalModelBridge(tmp_path / "ipc", NativeCompletionBackend(service))
    report = await bridge.readiness()
    assert report["ready"] is False and report["security_ready"] is False
    assert report["authentication"] == "not_checked"


@pytest.mark.asyncio
async def test_cancelling_governed_ipc_client_joins_owned_backend(tmp_path, monkeypatch):
    service = FixtureService(tmp_path)
    entered = asyncio.Event()
    stopped = asyncio.Event()
    delayed_dispatches = []
    class BlockedBackend:
        def __init__(self):
            self.service = service
        async def complete(self, **request):
            entered.set()
            try:
                await asyncio.sleep(60)
                delayed_dispatches.append("must never dispatch")
                return {"text": "{}"}
            finally:
                stopped.set()
    bridge = LocalModelBridge(tmp_path / "ipc", BlockedBackend())
    bridge.server = object()  # Protocol fixture; no real POSIX security claim.
    handlers = []
    class ClientWriter(ProtocolWriter):
        def __init__(self, server_reader):
            super().__init__()
            self.server_reader = server_reader
        def write(self, frame):
            self.server_reader.feed_data(frame)
    async def connection(*args, **kwargs):
        server_reader = asyncio.StreamReader()
        server_writer = ProtocolWriter()
        handlers.append(asyncio.create_task(bridge._serve(server_reader, server_writer)))
        return asyncio.StreamReader(), ClientWriter(server_reader)
    monkeypatch.setattr(asyncio, "open_unix_connection", connection, raising=False)
    task = asyncio.create_task(bridge.complete(**invocation()))
    await asyncio.wait_for(entered.wait(), 1)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    assert stopped.is_set() and all(handler.done() for handler in handlers)
    assert not bridge.active and not bridge.handlers and not bridge.grants and not delayed_dispatches
    with pytest.raises(GovernanceError, match="cannot be replayed"):
        await bridge.complete(**invocation())


@pytest.mark.asyncio
async def test_authenticated_login_denies_active_trial_and_untrusted_host():
    class Identity:
        def authenticate(self, *args, **kwargs):
            return object()
        def custody_status(self):
            return {"ready": True}
    class Bridge:
        async def readiness(self):
            return {"ready": False, "security_ready": True, "authentication": "signed_out"}
    class App:
        identity = Identity()
        bridge = Bridge()
        baseline = {"fixture": True}
        _submit_lock = asyncio.Lock()
        tasks = {}
    class Model:
        called = 0
        async def login(self):
            self.called += 1
            return {"state": "signing_in"}
    application, model = App(), Model()
    application.tasks = {"active": asyncio.create_task(asyncio.sleep(60))}
    app = FastAPI()
    app.include_router(trial_router(application, expected_origin="http://127.0.0.1:4311", model_service=model))
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 4312)),
                base_url="http://127.0.0.1:4311", headers={"Authorization": "Bearer scoped-fixture"}) as client:
            foreign = await client.post("/api/intent-trial/model/login", headers={"Host": "foreign.example"})
            assert foreign.status_code == 403 and model.called == 0
            active = await client.post("/api/intent-trial/model/login")
            assert active.status_code == 409 and active.json()["detail"]["code"] == "model_busy"
            assert model.called == 0
            application.tasks["active"].cancel()
            await asyncio.gather(application.tasks["active"], return_exceptions=True)
            application.identity.custody_status = lambda: {"ready": False}
            unsafe = await client.post("/api/intent-trial/model/login")
            assert unsafe.status_code == 503 and model.called == 0
            application.identity.custody_status = lambda: {"ready": True}
            allowed = await client.post("/api/intent-trial/model/login")
            assert allowed.status_code == 200 and model.called == 1 and application.baseline is None
    finally:
        for task in application.tasks.values():
            task.cancel()
        await asyncio.gather(*application.tasks.values(), return_exceptions=True)
