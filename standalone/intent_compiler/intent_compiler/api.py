"""Ordinary authenticated client boundary implementing M0-IF-001@r1.

The HTTP submission is an intake transport wrapper. Protected qualification
creates the catalog's complete Client_Submission.json, including host-owned refs.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
import hashlib
import inspect
import io
import json
from pathlib import Path
import secrets
import threading
from typing import Any, Literal
from urllib.parse import urlsplit
import uuid
import zipfile

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .config import Config
from .intake import IntakeError, qualify
from .store import Store, StoreError

VERSION = "1.0.0"
OPERATIONS = ["readiness", "submit", "reconcile", "status", "cancel", "retrieve", "consume"]
TERMINAL = {"completed", "halted", "blocked", "cancelled", "paused", "rejected"}


class Submission(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1.0.0"]
    id: str = Field(min_length=1, max_length=256)
    client_request_id: str = Field(min_length=1, max_length=256)
    account_id: str = Field(min_length=1)
    workspace_id: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    expected_instance_id: str = Field(min_length=1)
    expected_build_id: str = Field(min_length=1)
    client_contract_version: Literal["1.0.0"]
    request: str
    documents: list[Any] = Field(default_factory=list)
    resources: list[Any] = Field(default_factory=list)
    input_directory: str | None = None
    requested_seed: int | None = None
    previous_run_id: str | None = None


class Cancellation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1.0.0"]
    id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)


def _error(category: str, message: str, *, request_id=None, run_id=None, evidence_refs=None):
    return {"schema_version": VERSION, "id": "error-" + uuid.uuid4().hex,
            "category": category, "message": message, "request_id": request_id,
            "run_id": run_id, "evidence_refs": evidence_refs or [],
            "correction": "Inspect the saved evidence and readiness; submit corrected input under a fresh request ID."}


def _build_id() -> str:
    root = Path(__file__).resolve().parent
    digest = hashlib.sha256()
    paths = list(root.rglob("*")) + list((root.parent / "frontend" / "dist").rglob("*"))
    paths += [root.parent / "requirements.lock"]
    for path in sorted(paths):
        if path.is_file() and "__pycache__" not in path.parts:
            digest.update(path.relative_to(root.parent).as_posix().encode())
            digest.update(path.read_bytes())
    return "sha256:" + digest.hexdigest()


def create_app(config: Config, store=None, runtime=None) -> FastAPI:
    from .runtime import Runtime

    store = store if store is not None else Store(config.state_dir)
    runtime = runtime if runtime is not None else Runtime(config, store)
    instance_id = store.instance_id
    build_id = _build_id()
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="intent-compiler")
    submit_lock = threading.Lock()

    @asynccontextmanager
    async def lifespan(app):
        store.pause_interrupted()
        yield
        # Client transport/server shutdown does not replay or implicitly cancel work.
        executor.shutdown(wait=False)

    app = FastAPI(title="Standalone Intent Compiler", version=VERSION, lifespan=lifespan)
    app.state.config, app.state.store, app.state.runtime = config, store, runtime
    app.state.instance_id, app.state.build_id = instance_id, build_id
    app.state.workers = {}

    def invalid_for_product():
        return (config.model_mode == "smoke" or config.profile_id == "compiler-evaluation"
                or bool(getattr(getattr(runtime, "bridge", None), "invalid_for_product", False)))

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        detail = exc.detail if isinstance(exc.detail, dict) else _error("request_rejected", str(exc.detail))
        return JSONResponse(detail, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Do not reflect rejected bodies: they may contain credential-like fields.
        fields = ", ".join(".".join(map(str, e["loc"])) for e in exc.errors())
        return JSONResponse(_error("invalid_contract", "Invalid or missing fields: " + fields), status_code=422)

    @app.middleware("http")
    async def authenticate(request: Request, call_next):
        if request.url.path.startswith("/api/"):
            token = request.headers.get("authorization", "")
            supplied = token[7:] if token.startswith("Bearer ") else ""
            if not config.auth_token or not secrets.compare_digest(supplied.encode(), config.auth_token.encode()):
                return JSONResponse(_error("unauthorized", "A scoped operator token is required."), status_code=401)
            origin = request.headers.get("origin")
            if origin:
                try:
                    parsed = urlsplit(origin)
                except ValueError:
                    return JSONResponse(_error("cross_origin", "Malformed browser origin is denied."), status_code=403)
                if parsed.scheme != request.url.scheme or parsed.netloc != request.headers.get("host"):
                    return JSONResponse(_error("cross_origin", "This browser boundary requires the same origin."), status_code=403)
            if request.headers.get("sec-fetch-site") == "cross-site":
                return JSONResponse(_error("cross_origin", "Cross-site API requests are denied."), status_code=403)
            if request.headers.get("x-account-id", config.account_id) != config.account_id or request.headers.get("x-workspace-id", config.workspace_id) != config.workspace_id:
                return JSONResponse(_error("unauthorized_scope", "The token does not authorize this account/workspace."), status_code=403)
        return await call_next(request)

    def scoped(run_id):
        try:
            row = store.get_run(run_id)
        except (StoreError, KeyError, ValueError):
            raise HTTPException(404, _error("unknown_run", "No authorized run has this identity.", run_id=run_id))
        if row is None:
            raise HTTPException(404, _error("unknown_run", "No authorized run has this identity.", run_id=run_id))
        if row.get("account_id") != config.account_id or row.get("workspace_id") != config.workspace_id:
            raise HTTPException(403, _error("unauthorized_scope", "The run belongs to another scope."))
        return row

    def prerequisite_data():
        try:
            runtime_states = runtime.readiness()
        except Exception:
            runtime_states = [{"name": "model", "status": "unavailable", "reason": "Runtime readiness could not be established."}]
        if isinstance(runtime_states, dict):
            runtime_states = runtime_states.get("prerequisites", [])
        states = [dict(item) for item in runtime_states]
        for name in ("model", "required_enforcement"):
            if not any(item.get("name") == name for item in states):
                states.append({"name": name, "status": "unavailable", "reason": "Required readiness evidence was not supplied by the runtime."})
        try:
            ref = store.put_bytes("readiness-probe", "Storage_Probe_" + uuid.uuid4().hex + ".bin", b"storage readiness v1")
            store.read_bytes("readiness-probe", ref)
            storage = {"name": "storage", "status": "ready", "reason": "A fresh file fsync and FULL SQLite metadata transaction succeeded."}
        except Exception:
            storage = {"name": "storage", "status": "unavailable", "reason": "Authoritative storage is inaccessible."}
        states = [item for item in states if item.get("name") not in {"storage", "authentication"}]
        return [storage, {"name": "authentication", "status": "ready", "reason": "The request was authenticated under the operator scope."}, *states]

    @app.get("/api/v1/readiness")
    def readiness():
        states = prerequisite_data()
        return {"schema_version": VERSION, "id": "readiness-" + uuid.uuid4().hex,
                "client_contract_version": VERSION, "instance_id": instance_id, "build_id": build_id,
                "operations": OPERATIONS, "prerequisites": states,
                "ready": bool(states) and all(x.get("status") == "ready" for x in states),
                "ext": {"m0.intent": {"profiles": [config.profile_id], "profile_id": config.profile_id,
                "invalid_for_product": invalid_for_product(),
                "schema_versions": {"intent-ir": "1.0.0", "research-brief": "2.0.0", "gate-decision": "2.0.0", "node-execution-contract": "2.0.0", "subnode-execution-contract": "1.0.0"},
                "effective_configuration": config.freeze(), "account_id": config.account_id,
                "workspace_id": config.workspace_id}}}

    def status(run_id):
        row = scoped(run_id)
        result = store.status_data(run_id)
        result["ext"] = {"m0.intent": {"profile_id": row.get("profile_id", config.profile_id),
                       "invalid_for_product": invalid_for_product(),
                       "submission_ref": row.get("submission_ref"),
                       "intake_ref": row.get("intake_ref"), "configuration_ref": row.get("configuration_ref")}}
        return result

    def run_worker(run_id):
        try:
            outcome = runtime.run(run_id)
            if inspect.isawaitable(outcome):
                asyncio.run(outcome)
        except Exception as exc:
            # Unexpected infrastructure faults halt. No automatic repair or replay.
            try:
                ref = store.put_json(run_id, "Runtime_Failure.json", {"schema_version": VERSION,
                    "id": "runtime-failure-" + uuid.uuid4().hex, "category": type(exc).__name__,
                    "message": "Server-owned runtime stopped unexpectedly; inspect local operational evidence."})
                store.update_run(run_id, status="halted", stage="runtime_failure",
                                 reasons=["Unexpected runtime failure: " + type(exc).__name__], failure_ref=ref)
            except Exception:
                # A storage failure cannot be falsely reported as saved evidence.
                app.state.workers[run_id] = "storage_failure"

    @app.post("/api/v1/runs", status_code=202)
    def submit(body: Submission):
        if (body.account_id, body.workspace_id) != (config.account_id, config.workspace_id):
            raise HTTPException(403, _error("unauthorized_scope", "The selected account/workspace is not authorized."))
        if body.expected_instance_id != instance_id or body.expected_build_id != build_id:
            raise HTTPException(409, _error("wrong_target", "Instance or build identity changed; refresh readiness."))
        if body.profile_id != config.profile_id:
            raise HTTPException(409, _error("unapproved_profile", "Only the operator-approved profile may be selected."))
        payload = body.model_dump()
        with submit_lock:
            if body.previous_run_id:
                prior = scoped(body.previous_run_id)
                if prior.get("status") not in {"halted", "blocked", "cancelled", "paused", "rejected"}:
                    raise HTTPException(409, _error("invalid_correction_link", "A correction links a terminal failed or paused run."))
            try:
                run_id, created = store.create_run(body.client_request_id, payload, body.account_id, body.workspace_id)
            except StoreError as exc:
                raise HTTPException(409, _error("submission_conflict", str(exc), request_id=body.client_request_id))
            if not created:
                return status(run_id)
            try:
                frozen = dict(config.freeze())
                frozen.update({"requested_seed": body.requested_seed, "effective_seed": None,
                               "seed_reason": "Native model seed control is unavailable.",
                               "invalid_for_product": invalid_for_product()})
                configuration_ref = store.put_json(run_id, "Run_Configuration.json", frozen, artifact_type="configuration")
                store.update_run(run_id, configuration_ref=configuration_ref, profile_id=config.profile_id,
                                 previous_run_id=body.previous_run_id)
                qualified = qualify(config, store, run_id, body.request, documents=body.documents,
                                    resources=body.resources, input_directory=body.input_directory)
                canonical = {"schema_version": VERSION, "id": body.id,
                             "client_request_id": body.client_request_id, "account_id": body.account_id,
                             "workspace_id": body.workspace_id, "intake_ref": qualified["intake_ref"],
                             "configuration_ref": configuration_ref}
                submission_ref = store.put_json(run_id, "Client_Submission.json", canonical, artifact_type="client-submission")
                store.update_run(run_id, qualified=qualified, intake_ref=qualified["intake_ref"],
                                 sources=qualified["sources"], resource_refs=qualified["resource_refs"],
                                 submission_ref=submission_ref, stage="qualified", status="queued")
            except IntakeError as exc:
                store.update_run(run_id, status="halted", stage="intake_rejected", reasons=[str(exc)])
                raise HTTPException(422, _error("intake_rejected", str(exc), request_id=body.client_request_id, run_id=run_id))
            except (StoreError, OSError):
                raise HTTPException(503, _error("storage_unavailable", "Required capture failed; no model work was dispatched.", request_id=body.client_request_id, run_id=run_id))
            states = prerequisite_data()
            if not all(item.get("status") == "ready" for item in states):
                reasons = [item["name"] + ": " + item["reason"] for item in states if item.get("status") != "ready"]
                store.put_json(run_id, "Blocked_Readiness.json", {"schema_version": VERSION, "id": uuid.uuid4().hex, "prerequisites": states})
                store.update_run(run_id, status="halted", stage="prerequisite_blocked", reasons=reasons)
                raise HTTPException(503, _error("prerequisite_unavailable", "; ".join(reasons), request_id=body.client_request_id, run_id=run_id))
            app.state.workers[run_id] = executor.submit(run_worker, run_id)
        return status(run_id)

    @app.get("/api/v1/requests/{client_request_id}")
    def reconcile(client_request_id: str):
        # Request identity lookup is scoped; no resubmission or work dispatch.
        run_id = store.find_request(client_request_id, config.account_id, config.workspace_id)
        if not run_id:
            raise HTTPException(404, _error("unknown_request", "The request has no authorized run.", request_id=client_request_id))
        return status(run_id)

    @app.get("/api/v1/runs/{run_id}")
    def get_status(run_id: str):
        return status(run_id)

    @app.post("/api/v1/runs/{run_id}/cancel")
    def cancel(run_id: str, body: Cancellation):
        scoped(run_id)
        if body.run_id != run_id:
            raise HTTPException(422, _error("wrong_run", "Cancellation body and route must identify the same run."))
        record = store.request_cancel(run_id, body.request_id)
        stop = getattr(runtime, "cancel", None)
        if callable(stop):
            stop(run_id)
        return record

    def manifest_data(run_id: str, audience: str):
        row = scoped(run_id)
        if audience != "user":
            raise HTTPException(403, _error("unauthorized_audience", "Only the authenticated user export audience is supported."))
        artifacts = store.artifacts(run_id)
        files = []
        redactions = []
        for envelope in artifacts:
            allowed = envelope.get("audience", "user")
            if isinstance(allowed, list):
                permitted = audience in allowed
            else:
                permitted = allowed in {audience, "authorized-user", "authorized_user", "operator", "local_user"}
            if not permitted:
                redactions.append(envelope.get("id", "unknown") + ": audience restricted")
                continue
            ref = {"id": envelope["id"], "sha256": envelope["sha256"]}
            # Retrieval checks every captured exact-byte identity before exporting.
            store.read_bytes(run_id, ref)
            path = envelope.get("path", envelope.get("payload_path", envelope["id"] + ".json"))
            relative = Path(path)
            if relative.is_absolute() or ".." in relative.parts:
                raise HTTPException(409, _error("unsafe_export_path", "Stored export path is not a confined relative path.", run_id=run_id))
            files.append({"path": relative.as_posix(), "artifact_ref": ref,
                          "media_type": envelope.get("media_type", "application/json"), "audience": audience,
                          "ext": {"m0.intent": {"artifact_type": envelope.get("artifact_type", "record"),
                          "schema_version": envelope.get("schema_version", VERSION),
                          "producing_invocation": envelope.get("producing_invocation")}}})
        named = {Path(file["path"]).name for file in files}
        obligations = ["Qualified_Intake.json", "Intent_IR.json", "Research_Brief.json", "Intent_Assessment.json",
                       "Requirements_Assessment.json", "Gate_Node.json", "Accepted_node.json", "Run_Configuration.json"]
        missing = [{"obligation_id": name, "reason": "Not produced at this run stage or unavailable; see lifecycle and decisions.",
                    "blocking": name == "Research_Brief.json" and row.get("status") != "completed"}
                   for name in obligations if name not in named]
        originals = [file for file in files if file["ext"]["m0.intent"]["artifact_type"] != "run-bundle"]
        bundle_record = {"schema_version": VERSION, "run_id": run_id, "status": row["status"],
                         "configuration_ref": row["configuration_ref"],
                         "artifact_refs": [file["artifact_ref"] for file in originals],
                         "decision_refs": [file["artifact_ref"] for file in originals if file["ext"]["m0.intent"]["artifact_type"] == "gate-decision"],
                         "observation_refs": [file["artifact_ref"] for file in originals if file["ext"]["m0.intent"]["artifact_type"] == "invocation-observation"],
                         "missing_evidence": missing, "redactions": redactions}
        bundle_record["id"] = "bundle-" + hashlib.sha256(json.dumps(bundle_record, sort_keys=True).encode()).hexdigest()
        # Derived immutable snapshots do not alter gate/run state or dispatch work.
        # Windows feature/evidence roots can be long. Keep presentation paths
        # compact; immutable payload/reference digests retain full SHA256 identity.
        bundle_path = "exports/b-" + bundle_record["id"].removeprefix("bundle-")[:16] + "/Run_Bundle.json"
        bundle_ref = store.put_json(run_id, bundle_path, bundle_record, artifact_type="run-bundle")
        files = originals + [{"path": bundle_path, "artifact_ref": bundle_ref, "media_type": "application/json", "audience": audience}]
        core = {"schema_version": VERSION, "run_id": run_id,
                "artifact_refs": [file["artifact_ref"] for file in files], "audience": audience,
                "files": files, "redactions": redactions,
                "ext": {"m0.intent": {"stage": row["stage"], "status": row["status"], "bundle_ref": bundle_ref,
                        "missing_evidence": missing, "invalid_for_product": invalid_for_product()}}}
        core["id"] = "manifest-" + hashlib.sha256(json.dumps(core, sort_keys=True).encode()).hexdigest()
        return core

    @app.get("/api/v1/runs/{run_id}/manifest")
    def manifest(run_id: str, audience: str = "user"):
        try:
            return manifest_data(run_id, audience)
        except StoreError:
            raise HTTPException(409, _error("artifact_integrity", "Captured evidence cannot be verified.", run_id=run_id))

    @app.get("/api/v1/runs/{run_id}/bundle")
    def bundle(run_id: str, audience: str = "user"):
        data = manifest_data(run_id, audience)
        target = io.BytesIO()
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8"))
            for file in data["files"]:
                archive.writestr(file["path"], store.read_bytes(run_id, file["artifact_ref"]))
        return Response(target.getvalue(), media_type="application/zip", headers={"Content-Disposition": 'attachment; filename="' + run_id + '.zip"'})

    @app.get("/api/v1/runs/{run_id}/artifacts/{artifact_id:path}")
    def artifact(run_id: str, artifact_id: str, audience: str = "user"):
        data = manifest_data(run_id, audience)
        found = next((f for f in data["files"] if f["artifact_ref"]["id"] == artifact_id), None)
        if found is None:
            raise HTTPException(404, _error("unknown_artifact", "No permitted artifact has this identity.", run_id=run_id))
        return Response(store.read_bytes(run_id, found["artifact_ref"]), media_type=found["media_type"],
                        headers={"ETag": '"' + found["artifact_ref"]["sha256"] + '"', "X-Content-Type-Options": "nosniff"})

    @app.get("/api/v1/runs/{run_id}/result")
    def consume(run_id: str, schema_version: str = "2.0.0", artifact_id: str | None = None):
        scoped(run_id)
        if schema_version != "2.0.0":
            raise HTTPException(409, _error("unsupported_result_version", "The bounded consumer supports Research Brief 2.0.0 only.", run_id=run_id))
        try:
            released = runtime.consume(run_id)
            node_ref = store.acceptance_record(run_id, "node")
            accepted_record = store.get_json(run_id, node_ref)
            output_refs = accepted_record.get("output_refs", [])
            if artifact_id and artifact_id not in {ref["id"] for ref in output_refs}:
                raise ValueError("Requested artifact is not an exact node-released output")
            return {"schema_version": "2.0.0", "run_id": run_id, "node_acceptance_ref": node_ref,
                    "output_refs": output_refs, "research_brief": released,
                    "ext": {"m0.intent": {"invalid_for_product": invalid_for_product(), "profile_id": config.profile_id}}}
        except (ValueError, StoreError, KeyError, RuntimeError) as exc:
            raise HTTPException(409, _error("result_not_released", str(exc), run_id=run_id))

    frontend = Path(__file__).resolve().parents[1] / "frontend" / "dist"
    if frontend.is_dir():
        app.mount("/assets", StaticFiles(directory=frontend), name="assets")

        @app.get("/", include_in_schema=False)
        def home():
            return FileResponse(frontend / "index.html", headers={"Content-Security-Policy": "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'"})
    else:
        @app.get("/", include_in_schema=False)
        def unbuilt():
            return JSONResponse({"status": "frontend_not_built", "command": "npm --prefix standalone/intent_compiler/frontend ci && npm --prefix standalone/intent_compiler/frontend run build"}, status_code=503)
    return app
