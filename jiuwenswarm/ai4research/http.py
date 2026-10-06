"""Authenticated native web/headless contract, with no runner/gate endpoints."""
from __future__ import annotations

import io
import json
import zipfile
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from .common import GovernanceError
from .evidence import EvidenceViews


class Submission(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    original_text: str = Field(min_length=1, max_length=32768)
    client_request_id: str = Field(min_length=1, max_length=128)
    options: dict = Field(default_factory=dict)
    predecessor_run_id: str | None = None


def trial_router(application, *, expected_origin: str, model_service=None, refresh=None):
    router = APIRouter(prefix="/api/intent-trial")
    expected = urlsplit(expected_origin)

    def translated(exc):
        status = (403 if exc.code in {"policy_denied", "artifact_inaccessible"} else
                  404 if exc.code in {"run_not_found", "request_not_found", "artifact_not_found"} else
                  400 if exc.code == "invalid_input" else
                  503 if exc.code in {"environment_unavailable", "security_unavailable"} else 409)
        return HTTPException(status, detail=exc.as_dict())

    def authenticated(request):
        # Reject DNS-rebinding hosts as well as foreign browser origins. Proxy
        # headers do not grant authority; the packaged server disables them.
        host = request.headers.get("host", "")
        if host.lower() != expected.netloc.lower():
            raise HTTPException(403, detail={"code": "policy_denied", "message": "Unexpected application host."})
        token = request.headers.get("Authorization", "")
        if not token.startswith("Bearer "):
            raise HTTPException(401, detail={"code": "authentication_required"})
        try:
            return application.identity.authenticate(token[7:], peer_host=request.client.host if request.client else "",
                origin=request.headers.get("Origin"), expected_origin=expected_origin)
        except GovernanceError as exc:
            raise HTTPException(403, detail=exc.as_dict()) from exc

    @router.get("/readiness")
    async def readiness(request: Request):
        authenticated(request)
        if refresh:
            try:
                await refresh()
            except GovernanceError as exc:
                raise translated(exc) from exc
        try:
            return await application.readiness()
        except GovernanceError as exc:
            raise translated(exc) from exc

    @router.post("/runs", status_code=202)
    async def submit(body: Submission, request: Request):
        ctx = authenticated(request)
        try:
            return await application.submit(ctx, **body.model_dump())
        except GovernanceError as exc:
            raise translated(exc) from exc

    @router.get("/runs")
    async def list_runs(request: Request):
        ctx = authenticated(request)
        try:
            return [application.project(ctx, r["run_id"]) for r in application.store.list_runs(caller_id=ctx.user_id, workspace_id=ctx.workspace_id)]
        except GovernanceError as exc:
            raise translated(exc) from exc

    @router.get("/requests/{client_request_id}")
    async def reconcile(client_request_id: str, request: Request):
        ctx = authenticated(request)
        try:
            for run in application.store.list_runs(caller_id=ctx.user_id, workspace_id=ctx.workspace_id):
                if run["client_request_id"] == client_request_id:
                    return application.project(ctx, run["run_id"])
        except GovernanceError as exc:
            raise translated(exc) from exc
        raise HTTPException(404, detail={"code": "request_not_found"})

    @router.get("/runs/{run_id}")
    async def inspect(run_id: str, request: Request):
        ctx = authenticated(request)
        try:
            return application.project(ctx, run_id)
        except GovernanceError as exc:
            raise translated(exc) from exc

    @router.post("/runs/{run_id}/cancel")
    async def cancel(run_id: str, request: Request):
        ctx = authenticated(request)
        try:
            return await application.cancel(ctx, run_id)
        except GovernanceError as exc:
            raise translated(exc) from exc

    @router.get("/runs/{run_id}/bundle")
    async def bundle(run_id: str, request: Request):
        ctx = authenticated(request)
        try:
            application._owned_run(ctx, run_id)
            captured = EvidenceViews(application.store).bundle(run_id, caller_id=ctx.user_id)
            output = io.BytesIO()
            with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("manifest.json", json.dumps(captured, sort_keys=True))
                for member in captured["manifest"]["members"]:
                    ref = member["reference"]
                    archive.writestr(ref["artifact_id"] + ".bin", application.store.get_artifact(ref, caller_id=ctx.user_id))
        except GovernanceError as exc:
            raise translated(exc) from exc
        return Response(output.getvalue(),
                        media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="intent-{run_id}.zip"'})

    if model_service:
        @router.post("/model/login")
        async def login(request: Request):
            authenticated(request)
            # Serialize admission against account login. Ordinary chat's active
            # registry does not contain this trial's privately owned turns.
            async with application._submit_lock:
                if any(not task.done() for task in application.tasks.values()):
                    raise HTTPException(409, detail={"code": "model_busy", "message": "Model login is blocked while trial work is active."})
                try:
                    if not application.identity.custody_status().get("ready"):
                        raise GovernanceError("security_unavailable", "Provider login requires supported private application custody.")
                    protected = await application.bridge.readiness()
                    if not protected.get("security_ready"):
                        raise GovernanceError("security_unavailable", "Provider login requires protected application IPC.")
                    result = await model_service.login()
                    application.baseline = None
                    return result
                except GovernanceError as exc:
                    raise translated(exc) from exc
                except Exception:
                    # Native errors are stable codes, never provider payloads.
                    raise HTTPException(409, detail={"code": "model_login_unavailable", "message": "Application-owned model login is unavailable."}) from None

    return router
