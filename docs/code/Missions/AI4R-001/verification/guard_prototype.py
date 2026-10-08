"""Isolated research prototype. Not wired into the product or a live account."""
import asyncio
from dataclasses import asdict, dataclass
import os
from pathlib import Path
import subprocess
import uuid

from openjiuwen.core.session.interaction.interactive_input import InteractiveInput
from openjiuwen.harness_protocol import ToolApprovalRequest, ToolApprovalResponse, ToolApprovalDecision
from openjiuwen.harness_providers.io_adapter import HarnessIOAdapter


class GuardError(ValueError):
    """Stable error code only; never embed request payloads."""


@dataclass(frozen=True)
class Scope:
    session_id: str
    execution_id: str
    thread_id: str
    turn_id: str
    generation: int

    def __post_init__(self):
        if any(type(v) is not str or not v for k, v in asdict(self).items() if k != "generation"):
            raise GuardError("INVALID_SCOPE")
        if type(self.generation) is not int or self.generation < 0:
            raise GuardError("INVALID_SCOPE")


class ApprovalBroker:
    """One immutable execution scope; one-use tickets never enter chat.send.

    All methods run on the same event loop. decide contains no await, making
    validation and future completion one event-loop step. New execution or
    account generation requires a new broker; close rejects existing tickets.
    """
    def __init__(self, scope):
        self.scope = scope
        self.events = asyncio.Queue()
        self.pending = {}
        self.closed = False

    async def handle(self, request):
        if self.closed:
            raise GuardError("CLOSED")
        if not isinstance(request, ToolApprovalRequest):
            raise GuardError("UNSUPPORTED_INTERACTION")
        if request.provider_session_id != self.scope.thread_id or request.turn_id != self.scope.turn_id:
            raise GuardError("STALE_OPERATION")
        if request.request_id in self.pending:
            raise GuardError("DUPLICATE_REQUEST")
        ticket = {**asdict(self.scope), "request_id": request.request_id,
                  "call_id": request.call_id, "ticket": uuid.uuid4().hex}
        future = asyncio.get_running_loop().create_future()
        self.pending[request.request_id] = (ticket, future)
        self.events.put_nowait({"kind": "tool_approval", "tool_name": request.tool_name, **ticket})
        try:
            approved = await future
            return ToolApprovalResponse(request.request_id,
                                        ToolApprovalDecision.ALLOW if approved else ToolApprovalDecision.DENY)
        finally:
            if self.pending.get(request.request_id, (None,))[0] == ticket:
                self.pending.pop(request.request_id, None)

    def decide(self, payload):
        if self.closed:
            raise GuardError("CLOSED")
        fields = set(asdict(self.scope)) | {"request_id", "call_id", "ticket", "approved"}
        if type(payload) is not dict or set(payload) != fields or type(payload["approved"]) is not bool:
            raise GuardError("INVALID_DECISION")
        if type(payload["generation"]) is not int or any(
            type(payload[k]) is not str or not payload[k] for k in fields - {"generation", "approved"}
        ):
            raise GuardError("INVALID_DECISION")
        entry = self.pending.get(payload["request_id"])
        if entry is None or entry[1].done():
            raise GuardError("STALE_OPERATION")
        ticket, future = entry
        if any(payload[k] != v for k, v in ticket.items()):
            raise GuardError("STALE_OPERATION")
        future.set_result(payload["approved"])
        return {"accepted": True, "ticket": ticket["ticket"]}

    def cancel(self, request_id):
        entry = self.pending.get(request_id)
        if entry and not entry[1].done():
            entry[1].set_result(False)

    def close(self):
        self.closed = True
        for identity in list(self.pending):
            self.cancel(identity)


class GuardedIOAdapter(HarnessIOAdapter):
    """Permission-only prototype; user questions/MCP remain separate work."""
    def __init__(self, harness, broker):
        super().__init__(harness, auto_approve_tools=False)
        self.broker = broker

    def prepare_context(self, context):
        if context.interactions is not None and context.interactions is not self:
            raise GuardError("UNTRUSTED_INTERACTION_HANDLER")
        return super().prepare_context(context)

    async def handle(self, request):
        return await self.broker.handle(request)

    async def cancel(self, request_id, *, reason=None):
        self.broker.cancel(request_id)

    async def stop(self):
        self.broker.close()
        await super().stop()

    async def send(self, content, *, immediate=False):
        if self.broker.closed:
            raise GuardError("CLOSED")
        if isinstance(content, InteractiveInput) or type(content) is not str or not content:
            raise GuardError("CONTROL_CHANNEL_REQUIRED")
        return await super().send(content, immediate=immediate)


def install_approval_handler(client, handler):
    """Validate the pinned SDK seam before any process can be started."""
    low = getattr(getattr(client, "_client", None), "_sync", None)
    if low is None or not hasattr(low, "_approval_handler") or not callable(handler):
        raise GuardError("APPROVAL_HOOK_UNAVAILABLE")
    try:
        low._approval_handler = handler
        if low._approval_handler is not handler:
            raise GuardError("APPROVAL_HOOK_UNAVAILABLE")
    except (AttributeError, TypeError):
        raise GuardError("APPROVAL_HOOK_UNAVAILABLE") from None


def guarded_start(client, handler, start):
    install_approval_handler(client, handler)
    return start()


def child_environment(parent, home, workspace):
    """Construct the actual child env; do not merge it through SDK.start."""
    home, workspace = Path(home), Path(workspace)
    if not home.is_absolute() or not workspace.is_absolute():
        raise GuardError("ABSOLUTE_PATH_REQUIRED")
    allow = {"SYSTEMROOT", "WINDIR", "COMSPEC", "PATH", "PATHEXT", "TEMP", "TMP"}
    clean = {k: v for k, v in parent.items() if k.upper() in allow}
    clean.update(CODEX_HOME=str(home), HOME=str(workspace), USERPROFILE=str(workspace))
    return clean


def launch_signed_out_probe(binary, home, workspace):
    """Direct transport proof only; SDK/harness integration is still unproven."""
    binary, home, workspace = Path(binary), Path(home), Path(workspace)
    if not binary.is_absolute() or not binary.is_file():
        raise GuardError("PINNED_BINARY_REQUIRED")
    args = [str(binary), "--config", 'forced_login_method="chatgpt"',
            "--config", 'cli_auth_credentials_store="file"',
            "--config", "analytics.enabled=false", "--config", "feedback.enabled=false",
            "app-server", "--listen", "stdio://"]
    return subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True, encoding="utf-8", cwd=workspace,
                            env=child_environment(os.environ, home, workspace),
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
