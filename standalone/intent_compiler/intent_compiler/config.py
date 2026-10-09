"""Protected operator configuration; clients select approved profiles only."""
from __future__ import annotations

import os
import math
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    state_dir: Path
    input_root: Path
    input_directory: Path | None = None
    auth_token: str = ""
    account_id: str = "local-user"
    workspace_id: str = "local-workspace"
    profile_id: str = "compiler-only"
    model_mode: str = "codex"
    codex_path: str = "codex"
    model_name: str | None = None
    call_time_s: float = 120
    node_time_s: float = 480
    max_source_bytes: int = 4 * 1024 * 1024
    max_resource_bytes: int = 32 * 1024 * 1024
    max_output_bytes: int = 4 * 1024 * 1024
    memory_mb: int = 1024
    token_budget: int | None = None

    def __post_init__(self):
        object.__setattr__(self, "state_dir", Path(self.state_dir).resolve())
        object.__setattr__(self, "input_root", Path(self.input_root).resolve())
        if self.input_directory is not None:
            object.__setattr__(self, "input_directory", Path(self.input_directory).absolute())
        if not self.account_id or not self.workspace_id:
            raise ValueError("Account and workspace identifiers must be nonempty")
        if (self.model_mode, self.profile_id) not in (("codex", "compiler-only"), ("codex", "compiler-evaluation"), ("smoke", "compiler-smoke")):
            raise ValueError("Approved profiles are codex/compiler-only, codex/compiler-evaluation and smoke/compiler-smoke")
        if self.token_budget is not None and (isinstance(self.token_budget, bool) or not isinstance(self.token_budget, int) or self.token_budget <= 0):
            raise ValueError("Optional token budget must be a positive integer")
        bounds = (self.call_time_s, self.node_time_s, self.max_source_bytes,
                  self.max_resource_bytes, self.max_output_bytes, self.memory_mb)
        if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or x <= 0 for x in bounds):
            raise ValueError("Configured safety limits must be positive")
        if any(not isinstance(x, int) for x in (self.max_source_bytes, self.max_resource_bytes, self.max_output_bytes, self.memory_mb)):
            raise ValueError("Byte and memory limits must be integer quantities")
        if self.node_time_s < self.call_time_s:
            raise ValueError("Node budget cannot be smaller than a call budget")

    @classmethod
    def from_env(cls) -> "Config":
        token = os.environ.get("INTENT_AUTH_TOKEN", "")
        if os.environ.get("INTENT_AUTH_TOKEN_FILE"):
            token = Path(os.environ["INTENT_AUTH_TOKEN_FILE"]).read_text(encoding="utf-8").strip()
        root = Path(os.environ.get("INTENT_INPUT_ROOT", "./intent-input"))
        directory = os.environ.get("INTENT_INPUT_DIRECTORY")
        return cls(
            state_dir=Path(os.environ.get("INTENT_STATE_DIR", "./intent-state")),
            input_root=root, input_directory=Path(directory) if directory else None,
            auth_token=token, account_id=os.environ.get("INTENT_ACCOUNT_ID", "local-user"),
            workspace_id=os.environ.get("INTENT_WORKSPACE_ID", "local-workspace"),
            profile_id=os.environ.get("INTENT_PROFILE_ID", "compiler-only"),
            model_mode=os.environ.get("INTENT_MODEL_MODE", "codex"),
            codex_path=os.environ.get("INTENT_CODEX_PATH", "codex"),
            model_name=os.environ.get("INTENT_MODEL_NAME") or None,
            call_time_s=float(os.environ.get("INTENT_CALL_TIME_S", "120")),
            node_time_s=float(os.environ.get("INTENT_NODE_TIME_S", "480")),
            memory_mb=int(os.environ.get("INTENT_MEMORY_MB", "1024")),
            token_budget=int(os.environ["INTENT_TOKEN_BUDGET"]) if os.environ.get("INTENT_TOKEN_BUDGET") else None,
        )

    def freeze(self) -> dict:
        """Safe effective configuration; deliberately excludes secrets/host paths."""
        return {
            "schema_version": "1.0.0", "id": "configuration:compiler",
            "profile_id": self.profile_id, "model_mode": self.model_mode,
            "requested_model": self.model_name, "account_id": self.account_id,
            "workspace_id": self.workspace_id, "call_time_s": self.call_time_s,
            "node_time_s": self.node_time_s, "model_calls": 4, "automatic_retries": 0,
            "memory_mb": self.memory_mb, "max_source_bytes": self.max_source_bytes,
            "max_resource_bytes": self.max_resource_bytes,
            "max_output_bytes": self.max_output_bytes, "token_budget": self.token_budget,
            "requested_seed": None, "effective_seed": None,
            "seed_unavailable_reason": "Native route does not promise deterministic seed control",
            "hardware_readiness": {"profile": "single_gpu", "available": None,
                                   "reason": "Declarative default; compiler does not profile host hardware"},
        }
