import asyncio
import copy
import json
from types import SimpleNamespace

import pytest

from jiuwenswarm.research.capsule_extensions.generalist.worker import execute
from jiuwenswarm.research.capsule_extensions.generalist.checks import check
from jiuwenswarm.research.capsule_extensions.generalist.expression import evaluate
from jiuwenswarm.research.contracts import ResearchError


def original():
    return {'schema_version': '1.0.0', 'data': {'values': [2, 4, 6]}, 'files': [], 'trust': 'provisional', 'provenance': [], 'limitations': []}


def context(reply):
    ref = {'id': 'frozen-work-contract', 'sha256': 'a' * 64}
    contract = {'objective': 'The supplied values have a computed total and a short report.',
        'requirement_ids': ['r1'], 'policy_ref': ref, 'node_contract_ref': ref, 'node_id': 'generalist_1', 'attempt_id': 'a1'}
    calls = []
    async def model(prompt, system):
        calls.append((prompt, system))
        return json.dumps(reply)
    return SimpleNamespace(contract_ref=ref, contract=contract, model=model, calls=calls)


@pytest.mark.asyncio
async def test_generalist_actual_expression_artifacts_frozen_task_and_taint():
    ctx = context({'data': {'summary': 'A bounded result'}, 'files': [{'path': 'report.md', 'text': '# Result\n'}],
        'expression': "sum(data['values'])", 'limitations': []})
    inputs = {'packet': original()}
    outputs = await execute(ctx, inputs)
    value = json.loads(outputs['result'].data)
    assert value['data']['generalist_execution']['result'] == 12
    assert value['data']['generalist_task']['objective'] == ctx.contract['objective']
    assert value['trust'] == 'low' and ctx.contract_ref in value['provenance']
    assert len(ctx.calls) == 1
    checked = SimpleNamespace(contract=ctx.contract, observation={'contract_ref': ctx.contract_ref}, output_refs={'result': ctx.contract_ref})
    assert all(r['outcome'] == 'PASS' for r in check(checked, inputs, {'result': value}))
    for mutation in ['objective', 'result', 'trust', 'provenance']:
        bad = copy.deepcopy(value)
        if mutation == 'objective': bad['data']['generalist_task']['objective'] = 'A different task'
        if mutation == 'result': bad['data']['generalist_execution']['result'] = 999
        if mutation == 'trust': bad['trust'] = 'provisional'
        if mutation == 'provenance': bad['provenance'] = []
        assert any(r['outcome'] == 'FAIL' for r in check(checked, inputs, {'result': bad}))


@pytest.mark.parametrize('source', ["__import__('os').system('whoami')", "open('/etc/passwd').read()", '(1).__class__',
    '[x for x in data]', '2 ** 1000000', "'x' * 1000000000", 'sum([True])', '1/0', 'data["missing"]', 'lambda: 1'])
def test_expression_refuses_host_code_and_unbounded_operations(source):
    with pytest.raises(ResearchError):
        evaluate(source, {}, {})


def test_expression_is_deterministic_over_supplied_json_and_files():
    assert evaluate("{'count': len(files), 'answer': sum(data['values']) / 3}", original()['data'], {'a.txt': 'hello'}) == {'count': 1, 'answer': 4}
    assert evaluate("files['a.txt']", {}, {'a.txt': 'hello'}) == 'hello'


@pytest.mark.asyncio
async def test_model_error_and_cancellation_are_not_retried():
    ctx = context({})
    calls = []
    async def failed(*args, **kwargs):
        calls.append(1)
        raise ResearchError('MODEL_ACCESS_UNAVAILABLE')
    ctx.model = failed
    with pytest.raises(ResearchError):
        await execute(ctx, {'packet': original()})
    assert calls == [1]
    async def cancelled(*args, **kwargs):
        raise asyncio.CancelledError
    ctx.model = cancelled
    with pytest.raises(asyncio.CancelledError):
        await execute(ctx, {'packet': original()})
