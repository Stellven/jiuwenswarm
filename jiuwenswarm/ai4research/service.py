"""Single packaged local application service for the bounded trial."""
from __future__ import annotations

import argparse
import asyncio
from contextlib import asynccontextmanager
import json
import os
import secrets
import stat
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .application import IntentTrialApplication
from .admission import validate_admission_receipt
from .bridge import LocalModelBridge, NativeCompletionBackend, _safe_path
from .capsules import CapsuleLibrary
from .common import GovernanceError, canonical_json, sha256_bytes
from .http import trial_router
from .identity import IdentityStore
from .state import RunStore

PACKAGE = Path(__file__).parent


def _validate_custody(root):
    root = _safe_path(root)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    info = root.lstat()
    if not stat.S_ISDIR(info.st_mode):
        raise GovernanceError("security_unavailable", "Application custody must be a directory.")
    if os.name == "posix" and (info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700):
        raise GovernanceError("security_unavailable", "Application custody must be owned and private (0700).")
    # Native provider state also resides under this root. Reject redirected
    # credential/config/database custody before a native component resolves it.
    for directory, folders, files in os.walk(root, followlinks=False):
        for name in (*folders, *files):
            path = _safe_path(Path(directory) / name)
            item = path.lstat()
            if stat.S_ISREG(item.st_mode) and item.st_nlink != 1:
                raise GovernanceError("security_unavailable", "Hard-linked private custody files are prohibited.")
            if not (stat.S_ISDIR(item.st_mode) or stat.S_ISREG(item.st_mode) or stat.S_ISSOCK(item.st_mode)):
                raise GovernanceError("security_unavailable", "Unsupported private custody object.")
    return root


def _private_descriptor(path, flags):
    path = _safe_path(path)
    fd = os.open(path, flags | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        info = os.fstat(fd)
        current = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or
                (info.st_dev, info.st_ino) != (current.st_dev, current.st_ino) or
                (os.name == "posix" and info.st_uid != os.getuid())):
            raise GovernanceError("security_unavailable", "Private custody file identity is unsafe.")
        if os.name == "posix":
            os.fchmod(fd, 0o600)
        else:
            os.chmod(path, 0o600)
        return fd
    except BaseException:
        os.close(fd)
        raise


class ApplicationLease:
    """An OS-held lifetime lease precedes all recovery and session renewal."""

    def __init__(self, state_dir):
        self.state_dir = _validate_custody(state_dir)
        self.fd = None

    def acquire(self):
        if self.fd is not None:
            return self
        fd = _private_descriptor(self.state_dir / "service.lock", os.O_RDWR | os.O_CREAT)
        try:
            if os.fstat(fd).st_size == 0:
                os.write(fd, b"0")
                os.fsync(fd)
            os.lseek(fd, 0, os.SEEK_SET)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.fd = fd
            return self
        except OSError:
            os.close(fd)
            raise GovernanceError("application_in_use", "Another application process owns this state directory.") from None

    def release(self):
        if self.fd is not None:
            fd, self.fd = self.fd, None
            os.close(fd)


def _renew_token(identity, workspace_id, token_path):
    old_token = None
    _safe_path(token_path)
    if token_path.exists():
        fd = _private_descriptor(token_path, os.O_RDONLY)
        with os.fdopen(fd, "rb") as stream:
            old_bytes = stream.read(1025)
        if len(old_bytes) > 1024:
            raise GovernanceError("security_unavailable", "Private session custody is malformed.")
        old_token = old_bytes.decode("utf-8")
    token = identity.issue_session(workspace_id, ttl_seconds=86400)
    temporary = token_path.with_name("session-" + secrets.token_hex(16) + ".tmp")
    try:
        fd = _private_descriptor(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        with os.fdopen(fd, "wb") as stream:
            stream.write(token.encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        _safe_path(token_path)
        os.replace(temporary, token_path)
        if old_token:
            identity.revoke_session(old_token)
        return token
    except BaseException:
        identity.revoke_session(token)
        temporary.unlink(missing_ok=True)
        raise


def validate_adaptation():
    record = json.loads((PACKAGE / "verification/upstream-adaptation.json").read_bytes())
    if record.get("profile_id") != "intent-fidelity-r2" or not record.get("adopted_checks") or not record.get("inapplicable"):
        raise GovernanceError("ineligible_profile", "Intent profile has no complete scoped upstream adaptation.")
    for source in record["sources"]:
        path = (PACKAGE / "verification" / source["path"]).resolve()
        if not path.is_relative_to((PACKAGE / "verification/upstream").resolve()) or sha256_bytes(path.read_bytes()) != source["sha256"]:
            raise GovernanceError("ineligible_profile", "Pinned upstream assessment source changed.")
    return record


async def bootstrap(state_dir, workspace, *, origin, model=None, admission_receipt=None):
    from jiuwenswarm.server.runtime.codex_subscription.service import SubscriptionService
    lease = ApplicationLease(state_dir).acquire()
    try:
        return await _bootstrap_owned(lease, workspace, origin=origin, model=model, service_type=SubscriptionService,
                                      admission_receipt=admission_receipt)
    except BaseException:
        try:
            if getattr(lease, "bridge", None):
                await lease.bridge.close()
            if getattr(lease, "identity", None) and getattr(lease, "token", None):
                lease.identity.revoke_session(lease.token)
        finally:
            lease.release()
        raise


async def _bootstrap_owned(lease, workspace, *, origin, model, service_type, admission_receipt=None):
    state_dir = lease.state_dir
    workspace = Path(workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    identity = IdentityStore(state_dir / "identity/product.sqlite")
    lease.identity = identity
    profile = identity.initialize()
    ws = identity.register_workspace(workspace)
    token_path = state_dir / "session.token"
    token = _renew_token(identity, ws.workspace_id, token_path)
    lease.token = token
    authority = object()
    store = RunStore(state_dir / "runs.sqlite", state_dir / "artifacts", gate_authority=authority,
                     forbidden_values=(token.encode("utf-8"),))
    store.recover_interrupted()
    library = CapsuleLibrary(state_dir / "library.sqlite", PACKAGE)
    definitions = library.seed_builtin()
    pins = {"compiler": definitions["intent_compiler"], "verifier": definitions["intent_verifier"]}
    service = service_type(state_dir / "subscription")
    bridge = LocalModelBridge(state_dir / "ipc", NativeCompletionBackend(service))
    lease.bridge = bridge
    # The process lease proves there is no running application to own a stale
    # endpoint. Only remove this exact private socket, never a file or redirect.
    if os.name == "posix" and bridge.socket_path.exists():
        endpoint = _safe_path(bridge.socket_path).lstat()
        if not stat.S_ISSOCK(endpoint.st_mode) or endpoint.st_uid != os.getuid() or stat.S_IMODE(endpoint.st_mode) != 0o600:
            raise GovernanceError("security_unavailable", "Stale model endpoint has unsafe custody.")
        bridge.socket_path.unlink()
    try:
        await bridge.start()
    except GovernanceError:
        pass
    application = IntentTrialApplication(identity=identity, library=library, store=store,
        bridge=bridge, baseline=None, gate_authority=authority, pins=pins)
    application.process_lease = lease
    application.admission_status = {"ready": False, "reason": "admission_evidence_missing"}
    refresh_lock = asyncio.Lock()

    async def refresh():
        async with refresh_lock:
            ready = await bridge.readiness()
            if not ready.get("ready") or not identity.custody_status().get("ready") or not store.readiness()["ready"]:
                application.baseline = None
                return
            runtime_identity = {"account_fingerprint": ready["account_fingerprint"],
                                "account_epoch": ready["account_epoch"], "runtime_version": ready["runtime_version"]}
            if any(not task.done() for task in application.tasks.values()):
                frozen = (application.baseline or {}).get("runtime_identity")
                if runtime_identity != frozen:
                    application.baseline = None
                return
            bridge.backend.bind_account(ready)
            models = ready["models"]
            selected = model or next((m["id"] for m in models if m.get("default")), models[0]["id"])
            if selected not in {m["id"] for m in models}:
                application.baseline = None
                return
            adaptation = validate_adaptation()
            try:
                observed_admission = validate_admission_receipt(admission_receipt, pins)
            except GovernanceError as exc:
                application.baseline = None
                application.admission_status = {"ready": False, "reason": exc.code}
                return
            application.admission_status = observed_admission
            receipt = {"readiness": ready, "adaptation_revision": adaptation["upstream_revision"],
                       "observed_definition_admission": observed_admission,
                       "definition_hashes": {r: p.sha256 for r, p in pins.items()},
                       "standing_authority": "Explicit user request for initial static TRIAL-1 implementation", "actor_id": profile.user_id}
            receipt_bytes = canonical_json(receipt)
            receipt_hash = sha256_bytes(receipt_bytes)
            receipt_path = state_dir / ("definition-validation-" + receipt_hash + ".json")
            if not receipt_path.exists():
                fd = _private_descriptor(receipt_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
                with os.fdopen(fd, "wb") as stream:
                    stream.write(receipt_bytes)
                    stream.flush()
                    os.fsync(stream.fileno())
            else:
                fd = _private_descriptor(receipt_path, os.O_RDONLY)
                with os.fdopen(fd, "rb") as stream:
                    if stream.read(len(receipt_bytes) + 1) != receipt_bytes:
                        raise GovernanceError("security_unavailable", "Definition validation receipt changed.")
            prerequisites = {"runtime_ready": True, "security_ready": True, "profile_ready": True,
                             "checks_passed": True, "review_passed": True, "scope": "real",
                             "evidence_refs": [{"ref": receipt_path.name, "sha256": receipt_hash},
                                               *observed_admission["evidence_refs"]]}
            current = {}
            for short, full in (("compiler", "intent_compiler"), ("verifier", "intent_verifier")):
                existing = library.get(pins[short].decl_hash)
                if existing.standing in {"suspended", "deprecated"}:
                    application.baseline = None
                    return
                if existing.standing != "active":
                    library.admit(full, prerequisites, decl_hash=pins[short].decl_hash)
                    library.activate(full, pins[short].decl_hash, human_authorized=True,
                        actor_id=profile.user_id, required_scope="real")
                current[short] = library.resolve(full, decl_hash=pins[short].decl_hash, required_scope="real")
            application.pins = current
            application.baseline = {"provider": "codex_subscription", "model_ids": [m["id"] for m in models],
                "model_roles": {"compiler": selected, "verifier": selected},
                "pins": {r: p.to_dict() for r, p in current.items()},
                "verification_profile": {"profile_id": "intent-fidelity-r2", "sha256": application.profile_sha256,
                                         "interface_revision": "M0-IF-007@r2"},
                "runtime_identity": runtime_identity,
                "timeout_seconds": 180, "max_calls": 2, "mode": "web"}
    try:
        await refresh()
    except BaseException:
        identity.revoke_session(token)
        await bridge.close()
        raise
    return application, service, refresh, token_path


def create_app(state_dir, workspace, *, origin="http://127.0.0.1:4311", model=None, frontend=None, admission_receipt=None):
    @asynccontextmanager
    async def lifespan(app):
        application, service, refresh, token_path = await bootstrap(state_dir, workspace, origin=origin, model=model,
                                                                  admission_receipt=admission_receipt)
        try:
            app.state.intent_trial = application
            app.include_router(trial_router(application, expected_origin=origin, model_service=service, refresh=refresh))
            yield
        finally:
            try:
                await application.shutdown()
            finally:
                try:
                    await application.bridge.close()
                finally:
                    application.process_lease.release()

    app = FastAPI(title="AI4Research Intent trial", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    frontend = Path(frontend) if frontend else PACKAGE.parent / "channels/web/frontend/dist"
    if (frontend / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=frontend / "assets"), name="native-assets")

    @app.get("/intent-trial")
    async def native_ui():
        if not (frontend / "index.html").is_file():
            from fastapi import HTTPException
            raise HTTPException(503, detail="Native frontend build is unavailable.")
        return FileResponse(frontend / "index.html")

    @app.get("/")
    async def entry():
        return RedirectResponse("/intent-trial")

    return app


def main():
    import uvicorn
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--port", type=int, default=4311)
    parser.add_argument("--model", help="Exact model ID from authenticated native discovery; no alternate provider.")
    parser.add_argument("--admission-receipt", type=Path, help="Retained exact definition checks and independent review evidence.")
    args = parser.parse_args()
    app = create_app(args.state_dir, args.workspace, origin=f"http://127.0.0.1:{args.port}", model=args.model,
                     admission_receipt=args.admission_receipt)
    uvicorn.run(app, host="127.0.0.1", port=args.port, workers=1, proxy_headers=False, access_log=False)


if __name__ == "__main__":
    main()
