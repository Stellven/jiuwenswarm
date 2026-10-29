"""Requirements (m1-9) through the portable runtime: same pins, checks and verifier as the pipeline, fake models only."""
import hashlib
import json
from pathlib import Path

import pytest

from jiuwenswarm.capsule_runtime import Runtime
from jiuwenswarm.capsule_runtime.stage_adapter import DEFAULT_POLICY
from jiuwenswarm.research.state import json_bytes

from .test_intent_portable import FIXTURES, REQUEST, Worker, good_reply, tamper, verdict

INTENT, REQ = 'intent.compiler', 'requirements.compiler'


def blob_ref(data: bytes):
    digest = hashlib.sha256(data).hexdigest()
    return {'id': 'blob:' + digest, 'sha256': digest}


def brief_for(payload, mutate=None):
    """The pipeline test's own construction: the fixture Brief with its placeholder refs pointed at the real bound refs."""
    mapping = {'intent_ir.json': payload['intent_ref'], 'qualified_intake.json': payload['intake_ref'],
               'default_policy.json': payload['default_policy_ref'], 'request.txt': payload['intake']['request_ref']}

    def rewrite(v):
        if isinstance(v, dict):
            return dict(mapping[v['id']]) if set(v) == {'id', 'sha256'} else {k: rewrite(x) for k, x in v.items()}
        if isinstance(v, list):
            return [rewrite(x) for x in v]
        return v
    value = rewrite(json.loads((FIXTURES / 'research_brief.json').read_text('utf-8')))
    value['in_scope'][0]['id'] = 'scope:1'
    if mutate:
        mutate(value)
    return value


class BriefWorker:
    """Fake Requirements model: reads the bound refs from the prompt it is given, as a real model would."""

    def __init__(self, mutate=None, raw=None):
        self.mutate, self.raw, self.calls = mutate, raw, []

    async def __call__(self, prompt, system=None):
        self.calls.append((prompt, system))
        if self.raw is not None:
            return self.raw if isinstance(self.raw, str) else json.dumps(self.raw)
        return json.dumps(brief_for(json.loads(prompt), self.mutate))


class Pipeline:
    """Intent answers Intent prompts, Requirements answers Requirements prompts."""

    def __init__(self):
        self.intent, self.req = Worker(good_reply()), BriefWorker()

    async def __call__(self, prompt, system=None):
        worker = self.req if 'Requirements Capsule' in (system or '') else self.intent
        return await worker(prompt, system)


@pytest.fixture(scope='module')
def rt():
    runtime = Runtime()
    result = runtime.admit(REQ)
    assert result['passed'], result['failures']
    return runtime


def run(rt, worker, verifier=verdict(), **extra):
    return rt.invoke(REQ, {'request': REQUEST, 'intent': good_reply(), **extra}, worker_model=worker, verifier_model=verifier)


def test_valid_reply_delivers_what_the_pipeline_would_capture(rt):
    worker = BriefWorker()
    out = rt.invoke('research.requirements', {'request': REQUEST, 'intent': good_reply()}, worker_model=worker, verifier_model=verdict())
    assert out['status'] == 'delivered', out.get('halt')
    payload = json.loads(worker.calls[0][0])
    assert payload['intent_ref'] == blob_ref(json_bytes(good_reply()))
    assert payload['default_policy_ref'] == blob_ref(json_bytes(DEFAULT_POLICY))
    assert payload['request_text'] == REQUEST and payload['intake']['request_ref'] == blob_ref(REQUEST.encode())
    expected = brief_for(payload)
    assert out['outputs']['brief'] == expected
    receipt = out['receipt']
    assert receipt['output_sha256']['brief'] == hashlib.sha256(json_bytes(expected)).hexdigest()
    assert receipt['capability_id'] == REQ and receipt['version'] == 'm1-9'
    assert [c['check_id'] for c in receipt['checks']] == ['brief_schema', 'source_identity', 'requirement_coverage']
    assert all(c['outcome'] == 'PASS' for c in receipt['checks'])
    assert receipt['verifiers']['semantic'] == 'pass' and receipt['semantic_verifier']['status'] == 'reviewed'
    na = receipt['not_applicable_outside_pipeline']
    assert na and all(row['status'] == 'not_applicable_outside_pipeline' for row in na)
    assert 'accepted_intent_input' in [row['check'] for row in na]
    assert len(receipt['model_calls']) == 1


def test_chain_intent_then_requirements(rt):
    runtime = Runtime()
    worker = Pipeline()
    first = runtime.invoke('research.intent', {'request': REQUEST}, worker_model=worker, verifier_model=verdict(), require_admission=False)
    assert first['status'] == 'delivered', first.get('halt')
    second = runtime.invoke('research.requirements', {'request': REQUEST, 'intent': first['outputs']['intent']},
                            worker_model=worker, verifier_model=verdict(), require_admission=False)
    assert second['status'] == 'delivered', second.get('halt')
    assert second['outputs']['brief']['intent_ref'] == blob_ref(json_bytes(first['outputs']['intent']))
    assert len(worker.intent.calls) == 1 and len(worker.req.calls) == 1


def test_custom_policy_and_documents_reach_the_prompt(rt):
    policy = {**DEFAULT_POLICY, 'id': 'policy:mine'}
    worker = BriefWorker()
    out = run(rt, worker, policy=policy, documents=[{'name': 'a.txt', 'text': 'Some supplied text'}])
    # The Intent was made without documents, which is fine (context_refs may be empty); the document is bound as a source.
    assert out['status'] == 'delivered', out.get('halt')
    payload = json.loads(worker.calls[0][0])
    assert payload['defaults'] == policy and payload['default_policy_ref'] == blob_ref(json_bytes(policy))
    assert payload['source_texts'][0]['text'] == 'Some supplied text'


def test_invalid_reply_halts_at_the_worker_with_the_product_code(rt):
    out = run(rt, BriefWorker(raw='not json'))
    assert out['status'] == 'halted' and 'outputs' not in out
    assert out['halt']['stage'] == 'worker' and out['halt']['code'] == 'invalid_output'
    out = run(rt, BriefWorker(mutate=lambda b: b.pop('objective')))
    assert out['halt']['stage'] == 'worker' and out['halt']['code'] == 'contract_invalid'


def test_bad_evidence_halts_at_the_stage_check(rt):
    zero = {'id': 'blob:' + '0' * 64, 'sha256': '0' * 64}
    out = run(rt, BriefWorker(mutate=lambda b: b.update(intent_ref=zero)))
    assert out['status'] == 'halted' and out['halt']['stage'] == 'verifier' and out['halt']['code'] == 'check_failed'
    assert 'source_identity' in out['halt']['reason'] and 'outputs' not in out

    def drop_link(brief):
        for field in ('acceptance_expectations', 'evidence_obligations'):
            for item in brief[field]:
                item['requirement_ids'] = ['requirement:unknown']
    out = run(rt, BriefWorker(mutate=drop_link))
    assert out['halt']['stage'] == 'verifier' and out['halt']['code'] == 'check_failed'
    assert 'requirement_coverage' in out['halt']['reason']

    def lose_intent_item(brief):
        brief['in_scope'][0]['id'] = 'scope:other'
    out = run(rt, BriefWorker(mutate=lose_intent_item))
    assert 'Intent item is absent' in out['halt']['reason']


def test_verifier_fail_halts_and_delivers_nothing(rt):
    out = run(rt, BriefWorker(), verifier=verdict('FAIL'))
    assert out['status'] == 'halted' and 'outputs' not in out
    assert out['halt']['stage'] == 'semantic_verifier' and out['halt']['code'] == 'semantic_fail'


def test_no_verifier_model_is_never_delivered(rt):
    out = rt.invoke(REQ, {'request': REQUEST, 'intent': good_reply()}, worker_model=BriefWorker())
    assert out['status'] == 'halted' and out['halt']['stage'] == 'semantic_verifier' and out['halt']['code'] == 'no_model'


def test_input_guard(rt):
    other = good_reply('A different request text')
    cases = [({'request': REQUEST}, 'missing_input'),
             ({'intent': good_reply()}, 'missing_input'),
             ({'request': REQUEST, 'intent': {'x': 1}}, None),
             ({'request': REQUEST, 'intent': other}, 'intent_input_invalid'),
             ({'request': REQUEST, 'intent': good_reply(), 'policy': {**DEFAULT_POLICY, 'automatic_retries': 2}}, None),
             ({'request': REQUEST, 'intent': good_reply(), 'policy': {**DEFAULT_POLICY, 'hardware_profile': 'multi_gpu'}}, None),
             ({'request': REQUEST, 'intent': good_reply(), 'extra': 1}, 'unknown_input')]
    for bad, code in cases:
        worker = BriefWorker()
        out = rt.invoke(REQ, bad, worker_model=worker, verifier_model=verdict())
        assert out['halt']['stage'] == 'input_guard', bad
        if code:
            assert out['halt']['code'] == code
        assert worker.calls == []


def test_intent_with_a_span_outside_the_request_is_refused(rt):
    bad = good_reply()
    bad['interpretation']['problem']['source_spans'][0]['end'] = 100000
    out = rt.invoke(REQ, {'request': REQUEST, 'intent': bad}, worker_model=BriefWorker(), verifier_model=verdict())
    assert out['halt']['stage'] == 'input_guard' and out['halt']['code'] == 'intent_input_invalid'


def test_tampered_pin_refuses_at_call_time(rt, monkeypatch):
    tamper(monkeypatch, 'research_assets/compiler/requirements_m1_9.txt')
    import jiuwenswarm.research.requirements_release as release
    monkeypatch.setattr(release, 'files', __import__('importlib.resources', fromlist=['files']).files)
    worker = BriefWorker()
    out = run(rt, worker)
    assert out['status'] == 'halted' and out['halt']['stage'] == 'pin' and out['halt']['code'] == 'asset_integrity'
    assert worker.calls == []


def test_tampered_pin_refuses_at_load(monkeypatch):
    tamper(monkeypatch, 'research_assets/compiler/requirements_m1_9.txt')
    import jiuwenswarm.research.requirements_release as release
    monkeypatch.setattr(release, 'files', __import__('importlib.resources', fromlist=['files']).files)
    fresh = Runtime()
    row = next(r for r in fresh.list() if r['id'] == REQ)
    assert row['status'] == 'refused'
    out = fresh.invoke(REQ, {'request': REQUEST, 'intent': good_reply()}, worker_model=BriefWorker(), require_admission=False)
    assert out['halt']['stage'] == 'pin'


def test_changed_check_code_in_memory_refuses(rt, monkeypatch):
    """The imported check module must match the pinned bytes: a stale or edited module is refused."""
    import jiuwenswarm.research.checks.compiler as module
    real = Path.read_bytes
    monkeypatch.setattr(Path, 'read_bytes',
                        lambda self: real(self) + b'\n' if str(self) == module.__file__ else real(self))
    out = run(rt, BriefWorker())
    assert out['halt']['stage'] == 'pin' and out['halt']['code'] == 'asset_integrity'


def test_describe_and_mcp_schema(rt):
    from jiuwenswarm.capsule_runtime.mcp import Server, tool_for
    tool = tool_for(rt, REQ)
    props = tool['inputSchema']['properties']
    assert set(props) == {'intent', 'request', 'documents', 'policy', 'prior_plan_outcome'}
    assert tool['inputSchema']['required'] == ['intent', 'request']
    assert 'task_objective' not in props
    assert props['intent'].get('type') == 'object' and props['intent']['description']
    info = rt.describe(REQ)
    assert info['needs_model'] and 'semantic verifier: applies' in ' '.join(info['verifier_stages'])
    server = Server(rt, verdict())
    server.client_sampling = True
    assert REQ in server.visible()


def test_runtime_without_builtin_has_no_stage_capsules():
    assert REQ not in Runtime([], include_builtin=False).capsules
