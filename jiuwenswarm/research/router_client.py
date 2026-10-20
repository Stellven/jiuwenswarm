"""IPC-only RouterPort; no selector/provider/side-system implementation import.

Implements M1-IF-001@r1 and consumes M1-IF-008@r1. Selection ends before
provider dispatch. Once a call starts this object is never consulted again.
"""
from __future__ import annotations

import asyncio
import inspect
import json
import os
import socket
import stat
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

MAX_IPC_FRAME_BYTES = 4 * 1024 * 1024
PROTOCOL = "ai4r-router-ipc:1"


class PlatformIntegrityError(RuntimeError):
    pass


def _unique_pairs(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("DUPLICATE_JSON_KEY")
        obj[key] = value
    return obj


def decode_frame(payload: bytes) -> dict:
    if not payload or len(payload) > MAX_IPC_FRAME_BYTES:
        raise ValueError("IPC_FRAME_LIMIT")
    def reject_constant(_):
        raise ValueError("NONFINITE_JSON")
    result = json.loads(payload.decode("utf-8", errors="strict"), object_pairs_hook=_unique_pairs,
                        parse_constant=reject_constant)
    if not isinstance(result, dict):
        raise ValueError("IPC_ENVELOPE_INVALID")
    return result


def encode_frame(value: dict) -> bytes:
    data = json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
    if not data or len(data) > MAX_IPC_FRAME_BYTES:
        raise ValueError("IPC_FRAME_LIMIT")
    return struct.pack("!I", len(data)) + data


async def read_frame(reader: asyncio.StreamReader) -> dict:
    length = struct.unpack("!I", await reader.readexactly(4))[0]
    if not 0 < length <= MAX_IPC_FRAME_BYTES:
        raise ValueError("IPC_FRAME_LIMIT")
    return decode_frame(await reader.readexactly(length))


async def close_writer(writer):
    writer.close()
    try:
        await writer.wait_closed()
    except (ConnectionError, OSError):
        # The original transport outcome is retained by the caller. A reset
        # during teardown must not replace that outcome with another exception.
        pass


def peer_credentials(sock) -> tuple[int, int, int]:
    if not hasattr(socket, "SO_PEERCRED"):
        raise RuntimeError("LINUX_PEER_CREDENTIALS_REQUIRED")
    return struct.unpack("3i", sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")))


@dataclass(frozen=True)
class RouteChoice:
    model_id: str
    decision_source: str = "codex_router_disabled"
    router_failure: str | None = None
    router_halt_code: str | None = None
    route_decision_ref: dict | None = None
    decision: dict | None = None


class CodexRouter:
    def __init__(self, route_id="codex-cli-default"):
        self.route_id = route_id

    async def select(self, context: Mapping) -> RouteChoice:
        return RouteChoice(self.route_id)


class RouterPort(CodexRouter):
    def __init__(self, socket_path: str | Path, *, peer_uid: int, route_id="codex-cli-default",
                 validate_decision=None, persist_decision=None,prepare_request=None):
        super().__init__(route_id)
        self.socket_path = Path(socket_path)
        self.peer_uid = peer_uid
        self.validate_decision = validate_decision
        self.persist_decision = persist_decision
        self.prepare_request=prepare_request

    @staticmethod
    def validate_settings(context):
        settings = context.get("router")
        if not isinstance(settings, Mapping) or type(settings.get("enabled")) is not bool:
            raise PlatformIntegrityError("ROUTER_SETTINGS_INVALID")
        if type(settings.get("deadline_s")) not in (int, float) or settings["deadline_s"] != 30:
            raise PlatformIntegrityError("ROUTER_DEADLINE_INVALID")
        return settings

    def fallback(self, reason, halt=None):
        return RouteChoice(self.route_id, "codex_router_failed", reason, halt)

    async def _exchange(self, request):
        metadata = self.socket_path.lstat()
        if not stat.S_ISSOCK(metadata.st_mode) or metadata.st_uid != self.peer_uid or stat.S_IMODE(metadata.st_mode) != 0o660:
            raise PermissionError("ROUTER_SOCKET_CUSTODY_INVALID")
        reader, writer = await asyncio.open_unix_connection(str(self.socket_path), limit=MAX_IPC_FRAME_BYTES + 4)
        try:
            _, uid, _ = peer_credentials(writer.get_extra_info("socket"))
            if uid != self.peer_uid:
                raise PermissionError("ROUTER_PEER_INVALID")
            writer.write(encode_frame({"protocol": PROTOCOL, "op": "route", "request": request}))
            await writer.drain()
            return await read_frame(reader)
        finally:
            await close_writer(writer)

    async def select(self, context: Mapping) -> RouteChoice:
        # The protected bridge validates context integrity before this seam.
        if context.get("call_function") == "verifier":
            return await super().select(context)
        settings = self.validate_settings(context)
        # The bridge supplies this already verified frozen profile. A fixed
        # benchmark baseline is an explicit policy choice, never a failed route.
        if context.get("model_selection_profile", {}).get("policy_mode") == "fixed_baseline":
            return await super().select(context)
        if not settings["enabled"]:
            return await super().select(context)
        if settings.get("profile_ref") is None:
            return self.fallback("no_route", "PROFILE_UNAVAILABLE")
        export_error = context.get("routing_export_error")
        if export_error is not None:
            if export_error not in {"TASK_MISMATCH", "BUDGET_UNVERIFIABLE", "PROFILE_UNAVAILABLE"}:
                raise PlatformIntegrityError("ROUTING_EXPORT_ERROR_INVALID")
            return self.fallback("no_route", export_error)
        try:
            # Independent wall timer covers connect, framed response, validation
            # and persistence, including a router process that never replies.
            async with asyncio.timeout(30):
                if self.prepare_request is not None:
                    prepared=self.prepare_request(context)
                    if inspect.isawaitable(prepared):await prepared
                reply = await self._exchange(context["route_request"])
                if reply.get("protocol") != PROTOCOL:
                    return self.fallback("invalid_decision")
                kind = reply.get("kind")
                if kind == "integrity_fault":
                    raise PlatformIntegrityError("ROUTER_PLATFORM_INTEGRITY_FAULT")
                if kind == "no_route":
                    no_route = reply.get("no_route")
                    if not isinstance(no_route, dict) or no_route.get("execution_id") != context["route_request"].get("execution_id"):
                        return self.fallback("invalid_decision")
                    halt = no_route.get("halt_code")
                    allowed = {"PROFILE_UNAVAILABLE", "NO_COMPATIBLE_MODEL", "MODEL_ACCESS_UNAVAILABLE", "TASK_MISMATCH",
                               "MODEL_SCOPE_DENIED", "CAPABILITY_UNVERIFIED", "CONTEXT_EXCEEDED", "POLICY_DENIED",
                               "ENVIRONMENT_BLOCKED", "BUDGET_EXCEEDED", "BUDGET_UNVERIFIABLE", "LIMIT_UNSUPPORTED",
                               "DEPLOYMENT_BLOCKED", "SERVICE_STALE", "PROFILE_COVERAGE_MISSING", "ALTERNATE_UNAVAILABLE",
                               "AUDIT_UNAVAILABLE", "ROUTING_IN_PROGRESS", "ROUTING_DEADLINE_EXCEEDED", "ROUTING_OUTCOME_UNKNOWN"}
                    return self.fallback("no_route", halt) if halt in allowed else self.fallback("invalid_decision")
                decision = reply.get("decision")
                if kind != "decision" or not isinstance(decision, dict):
                    return self.fallback("invalid_decision")
                if decision.get("selected_endpoint") not in context.get("approved_model_ids", ()):
                    return self.fallback("unapproved_model")
                if self.validate_decision is None or self.persist_decision is None:
                    return self.fallback("invalid_decision")
                verified = self.validate_decision(context, decision)
                if inspect.isawaitable(verified):
                    await verified
                ref = self.persist_decision("model-route", decision)
                if inspect.isawaitable(ref):
                    ref = await ref
                return RouteChoice(decision["selected_endpoint"], "router", route_decision_ref=ref, decision=decision)
        except PlatformIntegrityError:
            raise
        except TimeoutError:
            return self.fallback("timeout")
        except FileNotFoundError:
            return self.fallback("missing")
        except (ConnectionError, OSError, asyncio.IncompleteReadError):
            return self.fallback("error")
        except (ValueError, TypeError, KeyError, RecursionError):
            return self.fallback("invalid_decision")

    async def revalidate_frozen(self, context: Mapping, choice: RouteChoice) -> None:
        """Recheck a persisted API choice before call-start, without rerouting.

        Once select has persisted a valid choice, source expiry/authorization
        failure terminates that frozen attempt. It cannot become a fallback or
        a second selector request under the same execution identity.
        """
        if choice.decision_source != "router":
            return
        if (self.validate_decision is None or not isinstance(choice.decision, dict)
                or choice.route_decision_ref is None
                or choice.model_id != choice.decision.get("selected_endpoint")):
            raise PlatformIntegrityError("FROZEN_ROUTE_INVALID")
        try:
            verified = self.validate_decision(context, choice.decision)
            if inspect.isawaitable(verified):
                await verified
        except PlatformIntegrityError:
            raise
        except (ValueError, TypeError, KeyError, OSError):
            raise PlatformIntegrityError("FROZEN_ROUTE_INVALIDATED") from None
