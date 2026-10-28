"""Portable runtime for capability capsules: use them from any harness.

Imports nothing from runner, scheduler, the run store or executor RPC.
"""
from .engine import Runtime
from .loader import Capsule, discover

_default: Runtime | None = None


def runtime(extra_dirs=(), *, fresh: bool = False) -> Runtime:
    """Process-wide default runtime (admission state lives here)."""
    global _default
    if _default is None or fresh or extra_dirs:
        _default = Runtime(extra_dirs)
    return _default


def invoke(capability_id, inputs, *, model=None, contract=None, require_admission=True):
    return runtime().invoke(capability_id, inputs, model=model, contract=contract, require_admission=require_admission)


def admit(capability_id, **kwargs):
    return runtime().admit(capability_id, **kwargs)


__all__ = ['Runtime', 'Capsule', 'discover', 'runtime', 'invoke', 'admit']
