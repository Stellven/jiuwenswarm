"""M1 ordinary chat through App Server, using the existing facade/history."""
from jiuwenswarm.common.schema.agent import AgentResponse, AgentResponseChunk
from jiuwenswarm.common.schema.message import ReqMethod
from jiuwenswarm.server.runtime.codex_subscription.service import get_service
from jiuwenswarm.server.runtime.codex_subscription.transport import CodexError


class CodexSubscriptionAdapter:
    _instance = None

    def __init__(self, service=None):
        self.service = service or get_service()

    async def create_instance(self, config=None, *, mode="agent", sub_mode=None, **kwargs):
        # Account admission is lazy: users must be able to open the app signed out.
        pass

    async def ensure_instance(self):
        return None

    async def reload_agent_config(self, **kwargs):
        pass

    async def handle_goal_command_structured(self, params, session_id="default"):
        action = str((params or {}).get("action", "get") or "get").strip().lower()
        # The chat UI polls this even in text-only mode. No goal exists in this
        # fresh-profile milestone; mutations must not imply goal support.
        if action == "get":
            return {"result_type": "goal_control", "action": action, "goal": None, "output": ""}
        return {"result_type": "goal_error", "action": action, "goal": None,
                "error_code": "MILESTONE_TEXT_ONLY", "error": "MILESTONE_TEXT_ONLY"}

    async def process_message_stream_impl(self, request, inputs):
        params = request.params or {}
        try:
            if request.req_method == ReqMethod.COMMAND_GOAL:
                raise CodexError("MILESTONE_TEXT_ONLY")
            mode = str(params.get("mode") or "agent.work.normal").lower()
            if mode not in {"agent", "claw", "agent.work.normal", "build"} or params.get("team"):
                raise CodexError("MILESTONE_TEXT_ONLY")
            if any(params.get(k) for k in ("mcp", "skills", "attachments", "media_items", "images", "files", "plugin_names", "agent_template_name")):
                raise CodexError("MILESTONE_TEXT_ONLY")
            # User text only: legacy rendered memory/tool instructions are not a
            # proven replacement for the host rails and must not be misrepresented.
            text = params.get("query") or params.get("content") or inputs.get("query")
            async for payload in self.service.stream(request.session_id, request.request_id, text, params.get("codex_model")):
                yield AgentResponseChunk(request_id=request.request_id, channel_id=request.channel_id, payload=payload, is_complete=payload["event_type"] == "chat.final", agent_ref=request.agent_ref)
        except CodexError as exc:
            yield AgentResponseChunk(request_id=request.request_id, channel_id=request.channel_id, payload={"event_type": "chat.error", "error": str(exc), "code": str(exc), "session_id": request.session_id}, is_complete=True, agent_ref=request.agent_ref)

    async def process_message_impl(self, request, inputs):
        last = None
        async for chunk in self.process_message_stream_impl(request, inputs):
            last = chunk.payload
        return AgentResponse(request_id=request.request_id, channel_id=request.channel_id, ok=last is not None and last.get("event_type") != "chat.error", payload=last)

    async def process_interrupt(self, request):
        try:
            if request.params.get("intent", "cancel") != "cancel":
                raise CodexError("MILESTONE_TEXT_ONLY")
            payload = await self.service.interrupt(request.session_id, request.params.get("target_request_id"))
            payload.update(event_type="chat.interrupt_result", intent="cancel")
            return AgentResponse(request_id=request.request_id, channel_id=request.channel_id, ok=True, payload=payload)
        except CodexError as exc:
            return AgentResponse(request_id=request.request_id, channel_id=request.channel_id, ok=False, payload={"error": str(exc), "code": str(exc)})

    async def handle_user_answer(self, request):
        return AgentResponse(request_id=request.request_id, channel_id=request.channel_id, ok=False, payload={"error": "MILESTONE_TEXT_ONLY", "code": "MILESTONE_TEXT_ONLY"})

    handle_swarmflow_reply = handle_user_answer
    handle_heartbeat = handle_user_answer

    async def cleanup(self):
        # The shared service is owned by AgentServer, not individual adapters.
        pass
