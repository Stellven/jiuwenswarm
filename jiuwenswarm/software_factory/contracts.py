"""Stage contracts: an artifact is an inspected file, not a renamed schema."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Any, Callable


class StageFailure(RuntimeError):
    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.code, self.details = code, details or {}


class StageBlocked(StageFailure):
    """A required environment/model/backend is unavailable, never a PASS."""


@dataclass
class Artifact:
    id: str
    kind: str
    path: str
    sha256: str
    size: int
    producer: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def serializable(self):
        return asdict(self)

    def read_json(self):
        path = Path(self.path)
        if hashlib.sha256(path.read_bytes()).hexdigest() != self.sha256:
            raise StageFailure('artifact_changed', f'Artifact {self.id} changed since verification')
        try:
            return json.loads(path.read_text())
        except (ValueError, UnicodeDecodeError) as error:
            raise StageFailure('contract_invalid', f'Artifact {self.id} is not JSON') from error


@dataclass(frozen=True)
class Stage:
    id: str
    name: str
    workflow_id: str
    subworkflow_id: str
    inputs: dict[str, str]
    outputs: dict[str, str]
    execute: Callable
    tools: tuple[str, ...] = ()
    environment: tuple[str, ...] = ()
    verifier: str = 'File existence, content contract, SHA-256, and downstream preconditions'
    cost: int = 1
    repairs: tuple[str, ...] = ()
    backends: tuple[str, ...] = ()
    validators: dict[str, Callable] = field(default_factory=dict)
    defer_until_goals_settle: bool = False
    accepts: dict[str, Any] = field(default_factory=dict)
    selection_only: bool = False
    dynamic_inputs: tuple[str, ...] = ()

    def serializable(self):
        return {
            'id': self.id, 'name': self.name, 'workflow_id': self.workflow_id,
            'subworkflow_id': self.subworkflow_id,
            'entrypoint': f'{self.execute.__module__}:{self.execute.__name__}',
            'inputs': [{'name': name, 'kind': kind, 'required': True} for name, kind in self.inputs.items()],
            'outputs': [{'name': name, 'kind': kind} for name, kind in self.outputs.items()],
            'tools': list(self.tools), 'environment': list(self.environment),
            'verifier': self.verifier, 'repairs': list(self.repairs), 'backends': list(self.backends),
            'defer_until_goals_settle': self.defer_until_goals_settle,
            'accepts': dict(self.accepts), 'selection_only': self.selection_only,
            'dynamic_inputs': list(self.dynamic_inputs),
        }


def inspect_file(path: Path, kind: str, validator: Callable | None = None):
    path = path.resolve(strict=True)
    if not path.is_file() or path.stat().st_size == 0:
        raise StageFailure('contract_invalid', f'{kind}: expected a nonempty regular file: {path}')
    raw = path.read_bytes()
    metadata = validator(path) if validator else {}
    return hashlib.sha256(raw).hexdigest(), len(raw), metadata or {}


def json_object(path: Path, required: dict[str, type]):
    try:
        value = json.loads(path.read_text())
    except (ValueError, UnicodeDecodeError) as error:
        raise StageFailure('contract_invalid', f'Invalid JSON: {path}') from error
    if not isinstance(value, dict):
        raise StageFailure('contract_invalid', f'Expected object: {path}')
    for key, expected in required.items():
        if key not in value or not isinstance(value[key], expected):
            raise StageFailure('contract_invalid', f'{path.name}.{key}: expected {expected}')
    return value
