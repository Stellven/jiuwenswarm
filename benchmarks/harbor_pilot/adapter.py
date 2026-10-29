"""Harbor external agent that delegates all work to the supported AI4R runner."""
from __future__ import annotations

import os
from pathlib import Path

from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

from .bridge import BridgeCancelled, Config, case_from_instruction, run_trial


class AI4ResearchAgent(BaseAgent):
    """A control adapter, with no additional model or app-side execution power."""

    @staticmethod
    def name() -> str:
        return "ai4research-pilot"

    def version(self) -> str:
        return "1"

    async def setup(self, environment: BaseEnvironment) -> None:
        # Config and credential references are read by the Harbor host only.
        value = os.environ.get("AI4R_HARBOR_CONFIG")
        if not value:
            raise ValueError("AI4R_HARBOR_CONFIG must name a host-only configuration file")
        self._pilot_config = Config.load(value)

    async def run(self, instruction: str, environment: BaseEnvironment, context: AgentContext) -> None:
        case_id = case_from_instruction(instruction)
        identity = str(Path(self.logs_dir).resolve())
        cancelled = None
        try:
            result = await run_trial(self._pilot_config, case_id, identity)
        except BridgeCancelled as error:
            result = error.result
            cancelled = error
        # The artifact transport container receives only retained runner output;
        # no host config, token, protected label, or app private state is uploaded.
        await environment.upload_dir(source_dir=result.folder, target_dir="/app/ai4r-evidence")
        context.metadata = {"ai4research": result.receipt,
                            "measurement_scope": "existing runner/app evidence; no inferred model usage"}
        # Harbor's cancellation/timeout classification must remain intact after
        # the bounded containment and durable export attempt.
        if cancelled is not None:
            raise cancelled
