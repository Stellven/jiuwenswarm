"""Account control behind the existing authenticated Gateway -> AgentServer route."""
import os

from jiuwenswarm.common.schema.agent import AgentResponse
from jiuwenswarm.server.runtime.codex_subscription.service import get_service
from jiuwenswarm.server.runtime.codex_subscription.transport import CodexError
from .base import GatewayAdapter, build_error_response


class CodexAccountAdapter(GatewayAdapter):
    methods = frozenset({"codex.auth.status", "codex.auth.login", "codex.auth.cancel", "codex.auth.logout", "codex.models.list"})

    async def handle(self, request):
        method = request.req_method.value
        enabled = os.environ.get("JIUWENSWARM_AGENT_SDK") == "codex_subscription"
        if not enabled:
            if method == "codex.auth.status":
                return AgentResponse(request_id=request.request_id, channel_id=request.channel_id, ok=True, payload={"enabled": False})
            return build_error_response(request, "SUBSCRIPTION_MODE_DISABLED", "SUBSCRIPTION_MODE_DISABLED")
        try:
            service = get_service()
            action = {"codex.auth.status": service.status, "codex.auth.login": service.login, "codex.auth.cancel": service.cancel_login, "codex.auth.logout": service.logout, "codex.models.list": service.models}[method]
            payload = await service.cancel_login((request.params or {}).get("login_attempt_id")) if method == "codex.auth.cancel" else await action()
            return AgentResponse(request_id=request.request_id, channel_id=request.channel_id, ok=True, payload=payload, metadata=request.metadata)
        except CodexError as exc:
            return build_error_response(request, str(exc), str(exc))
