"""Execution policy for an already validated, exactly admitted Builder declaration.

This selector grants no authority: callers must retain declaration hash, admission,
and invocation checks. Version labels are descriptive, never execution policy.
"""
from .contracts import ResearchError


def builder_mode(declaration):
    """Return legacy, text, prediction, loop or agent; reject unsupported carriers/needs."""
    identity = declaration.get('identity', {})
    carrier = identity.get('carrier', {}).get('ref')
    tool_calling = declaration.get('needs', {}).get('model', {}).get('tool_calling')
    mode = {'builder.py': 'legacy', 'builder_text.py': 'text',
            'builder_loop.py': 'loop', 'builder_agent.py': 'agent'}.get(carrier)
    if (identity.get('name') != 'research.builder' or mode is None
            or tool_calling is not (mode == 'legacy')
            or (mode in {'text', 'loop'}
                and declaration.get('budget', {}).get('per_call', {}).get('tool_calls') != 0)):
        raise ResearchError('builder_mode', 'Unsupported admitted Builder carrier or model needs')
    if mode == 'text' and any(
            port.get('name') == 'build_receipt'
            and port.get('schema_ref') == 'urn:ai4r:prediction-build-receipt:2.0.0'
            for port in declaration.get('ports', {}).get('outputs', [])):
        return 'prediction'
    return mode
