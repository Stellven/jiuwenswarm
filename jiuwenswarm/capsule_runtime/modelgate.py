"""The only model a capsule sees: ``await ctx.model(prompt, system=...) -> str``.

Whatever backs it (a Python callable, a command, an OpenAI-compatible endpoint
or MCP sampling), the gate enforces the call limit and the text-only reply
contract, and records every call for the receipt. The capsule supplies its own
pinned instructions as the ``system`` argument; the caller never does.
"""
from __future__ import annotations

import hashlib
import inspect

from jiuwenswarm.research.contracts import ResearchError

DEFAULT_CALL_LIMIT = 1   # M1 model capsules make one audited call; declarations carry no explicit model-call field


def _sha(text) -> str | None:
    return None if text is None else hashlib.sha256(str(text).encode('utf-8')).hexdigest()


def describe(fn) -> dict:
    return {'kind': getattr(fn, 'kind', 'api'), 'identity': getattr(fn, 'identity', None) or 'callable:%x' % id(fn)}


def call_limit(declaration: dict) -> int:
    return int(declaration['budget']['per_call'].get('model_calls', DEFAULT_CALL_LIMIT))


class ModelGate:
    def __init__(self, backend, limit: int, *, single_arg: bool = False):
        """single_arg: verifier models are callable(prompt) -> text; worker models take (prompt, system=)."""
        self.backend, self.limit, self.calls, self.single_arg = backend, limit, [], single_arg
        self.meta = describe(backend)

    async def __call__(self, prompt, system=None):
        if len(self.calls) >= self.limit:
            raise ResearchError('model_call_limit', 'Declared model-call limit of %d reached' % self.limit)
        entry = {'index': len(self.calls) + 1, 'provider_kind': self.meta['kind'], 'model': None,
                 'prompt_sha256': _sha(prompt), 'system_sha256': _sha(system), 'reply_sha256': None, 'tokens': None}
        self.calls.append(entry)
        reply = self.backend(prompt) if self.single_arg else self.backend(prompt, system=system)
        if inspect.isawaitable(reply):
            reply = await reply
        entry['model'] = getattr(self.backend, 'last_model', None) or getattr(self.backend, 'model_name', None)
        entry['tokens'] = getattr(self.backend, 'last_usage', None)
        if not isinstance(reply, str):
            raise ResearchError('model_reply', 'Model reply must be text')
        entry['reply_sha256'] = _sha(reply)
        return reply

    def summary(self) -> dict:
        return {'provider_kind': self.meta['kind'], 'identity': self.meta['identity'],
                'calls': len(self.calls), 'limit': self.limit}
