"""Protected native HTTP surface for M1-IF-INTENT@r1.

Identity, limits and custody roots are host configuration. Browser text carries
no authority to choose them or to supply a gate decision.
"""
from __future__ import annotations

import hmac
import ipaddress
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from jiuwenswarm.ai4research.intent.store import IntentStore, StoreError


@dataclass(frozen=True)
class LocalIntentContext:
    token: str
    owner_id: str
    profile_id: str
    workspace_id: str
    data_root: Path
    cookie_name: str = "__wsdt5173"
    browser_ports: tuple[int, ...] = (5173, 19000)

    @classmethod
    def configured(cls):
        token = os.environ.get("JIUWENSWARM_INTENT_TOKEN") or os.environ.get("JIUWENSWARM_DESKTOP_TOKEN", "")
        if len(token) < 32:
            raise ValueError("INTENT_AUTH_REQUIRED")
        profile = Path(os.environ.get("JIUWENSWARM_DATA_DIR", str(Path.home() / ".jiuwenswarm-ai4r"))).resolve()
        root = profile / "intent"
        profile_id = IntentStore(root).profile_id
        owner_id = os.environ.get("JIUWENSWARM_INTENT_OWNER", "local:" + profile_id)
        if not owner_id.strip():
            raise ValueError("INTENT_PROFILE_INVALID")
        frontend_port = int(os.environ.get("FRONTEND_PORT", "5173"))
        gateway_port = int(os.environ.get("WEB_PORT", "19000"))
        workspace = Path(os.environ.get("JIUWENSWARM_INTENT_WORKSPACE", str(profile / "workspace"))).resolve()
        return cls(token, owner_id, profile_id, str(workspace), root,
                   f"__wsdt{frontend_port}", (frontend_port, gateway_port))


class IntentSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    text: str = Field(min_length=1, max_length=65536)
    corrects_run_id: str | None = Field(default=None, max_length=128)


def _loopback(host: str | None) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host or "").is_loopback
    except ValueError:
        return False


def _deny(code: str, status: int) -> JSONResponse:
    return JSONResponse({"code": code, "error": code}, status_code=status,
                        headers={"Cache-Control": "no-store"})


def authorize_intent_request(request: Request, context: LocalIntentContext) -> JSONResponse | None:
    if len(context.token) < 32:
        return _deny("INTENT_AUTH_REQUIRED", 503)
    peer = request.client.host if request.client else None
    # Do not trust Forwarded / X-Forwarded-For or DNS to establish locality.
    if not _loopback(peer) or len(request.headers.getlist("host")) != 1:
        return _deny("INTENT_LOCAL_ONLY", 403)
    try:
        authority = urlsplit("http://" + request.headers["host"])
        if not _loopback(authority.hostname) or authority.username or authority.password or authority.path:
            return _deny("INTENT_LOCAL_ONLY", 403)
        origin = request.headers.get("origin")
        if origin:
            parsed = urlsplit(origin)
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            if parsed.scheme not in {"http", "https"} or not _loopback(parsed.hostname) or parsed.username or parsed.password or parsed.path or port not in context.browser_ports:
                return _deny("INTENT_ORIGIN_DENIED", 403)
    except ValueError:
        return _deny("INTENT_LOCAL_ONLY", 403)
    if request.headers.get("x-jiuwen-intent") != "1":
        return _deny("INTENT_REQUEST_HEADER_REQUIRED", 403)
    bearer = request.headers.get("authorization", "")
    credential = bearer[7:] if bearer.startswith("Bearer ") else request.cookies.get(context.cookie_name, "")
    if not credential or not hmac.compare_digest(credential.encode(), context.token.encode()):
        return _deny("INTENT_UNAUTHORIZED", 401)
    return None


def register_intent_routes(app: FastAPI, *, service=None, context: LocalIntentContext | None = None) -> None:
    """Mount on native WebChannel; dependency injection is for local checks."""
    active_service = service
    active_context = context

    def protected_context(request):
        nonlocal active_context
        if active_context is None:
            try:
                active_context = LocalIntentContext.configured()
            except (OSError, sqlite3.Error):
                return None, _deny("INTENT_STORAGE_UNAVAILABLE", 503)
            except (ValueError, TypeError, StoreError):
                return None, _deny("INTENT_AUTH_REQUIRED", 503)
        denied = authorize_intent_request(request, active_context)
        return active_context, denied

    @app.middleware("http")
    async def protect_before_parsing(request: Request, call_next):
        if request.url.path == "/api/intent" or request.url.path.startswith("/api/intent/"):
            _, denied = protected_context(request)
            if denied is not None:
                return denied
        return await call_next(request)

    def dependencies(request):
        nonlocal active_service
        identity, denied = protected_context(request)
        if denied is not None:
            return None, None, denied
        if active_service is None:
            from jiuwenswarm.ai4research.intent.bridge import CodexBridge
            from jiuwenswarm.ai4research.intent.service import IntentService
            from jiuwenswarm.ai4research.intent.store import IntentStore
            try:
                active_service = IntentService(IntentStore(active_context.data_root), CodexBridge())
            except (OSError, sqlite3.Error, StoreError):
                return None, None, _deny("INTENT_STORAGE_UNAVAILABLE", 503)
        return active_service, identity, None

    @app.post("/api/intent/runs", status_code=202)
    async def submit(request: Request, body: IntentSubmission):
        provider, identity, denied = dependencies(request)
        if denied is not None:
            return denied
        try:
            run_id = await provider.submit(body.text, identity.owner_id, identity.profile_id,
                                           identity.workspace_id, body.corrects_run_id)
            return JSONResponse({"run_id": run_id, "state": "CAPTURED"}, status_code=202,
                                headers={"Cache-Control": "no-store"})
        except StoreError as exc:
            return _deny(str(exc), 409 if str(exc) == "RUNTIME_BUSY" else 422)
        except (ValueError, PermissionError, KeyError):
            return _deny("INTENT_INVALID_INPUT", 422)
        except (OSError, sqlite3.Error):
            return _deny("INTENT_STORAGE_UNAVAILABLE", 503)

    @app.get("/api/intent/runs/{run_id}")
    async def inspect(request: Request, run_id: str):
        provider, identity, denied = dependencies(request)
        if denied is not None:
            return denied
        try:
            return JSONResponse(provider.get(run_id, identity.owner_id), headers={"Cache-Control": "no-store"})
        except (ValueError, PermissionError, KeyError, StoreError):
            return _deny("INTENT_RUN_NOT_FOUND", 404)
        except (OSError, sqlite3.Error):
            return _deny("INTENT_STORAGE_UNAVAILABLE", 503)

    @app.post("/api/intent/runs/{run_id}/cancel")
    async def cancel(request: Request, run_id: str):
        provider, identity, denied = dependencies(request)
        if denied is not None:
            return denied
        try:
            return JSONResponse(await provider.cancel(run_id, identity.owner_id), headers={"Cache-Control": "no-store"})
        except (ValueError, PermissionError, KeyError, StoreError):
            return _deny("INTENT_RUN_NOT_FOUND", 404)
        except (OSError, sqlite3.Error):
            return _deny("INTENT_STORAGE_UNAVAILABLE", 503)
