"""The Hypothesis instructions must keep tests.py outside the patch-file limit (r5g)."""
import asyncio
from types import SimpleNamespace

import pytest

from jiuwenswarm.research.capsules import hypothesis


def test_hypothesis_prompt_states_tests_py_has_its_own_allowance(monkeypatch):
    seen = {}

    async def fake_ask(ctx, stage, instructions, inputs, **kwargs):
        seen['instructions'] = instructions
        raise RuntimeError('stop after capture')

    monkeypatch.setattr(hypothesis, 'ask', fake_ask)
    resource = {'availability': 'available', 'environment_ref': {'id': 'e'}}
    ctx = SimpleNamespace(input_ref=lambda port: {'id': port})
    with pytest.raises(RuntimeError):
        asyncio.run(hypothesis.execute(ctx, {'baseline_resource': resource, 'validation_resource': resource}))
    text = seen['instructions']
    assert 'max_patch_files counts implementation files only' in text
    assert 'tests.py' in text and 'never write a scope' in text
