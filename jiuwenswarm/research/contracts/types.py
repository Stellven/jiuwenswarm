"""Internal Python types; interoperable JSON remains owned by the M1 TASK IFs."""

from dataclasses import dataclass, field
from typing import Any, Mapping, TypedDict


class Ref(TypedDict):
    id: str
    sha256: str


class ResearchError(Exception):
    def __init__(self, code: str, message: str = "", details: Mapping[str, Any] | None = None):
        self.code = code
        self.message = message or code
        self.details = dict(details or {})
        super().__init__(f"{code}: {self.message}")


@dataclass(frozen=True)
class Principal:
    account_id: str
    workspace_ids: frozenset[str] = field(default_factory=frozenset)
    operations: frozenset[str] = field(default_factory=frozenset)
    audiences: frozenset[str] = field(default_factory=lambda: frozenset({"researcher"}))

    def require(self, operation: str, workspace_id: str | None = None) -> None:
        if not self.account_id or operation not in self.operations:
            raise ResearchError("auth", "Operation is outside the authenticated grant")
        if workspace_id is not None and workspace_id not in self.workspace_ids:
            raise ResearchError("auth", "Workspace is outside the authenticated grant")
