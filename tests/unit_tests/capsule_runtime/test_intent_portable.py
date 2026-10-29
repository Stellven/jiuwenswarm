"""Intent (m1-8) through the portable runtime: same pins, checks and verifier as the pipeline, fake models only."""
import hashlib
import json
from importlib.resources import files as real_files
from pathlib import Path

import pytest

from jiuwenswarm.capsule_runtime import Runtime
from jiuwenswarm.research.state import json_bytes

FIXTURES = Path('tests/fixtures/research/compiler')
REQUEST = (FIXTURES / 'request.txt').read_text('utf-8')
INTENT = 'intent.compiler'


def request_ref(text):
    digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
    return {'id': 'blob:' + digest, 'sha256': digest}


def rewrite(value, ref):
    """The pipeline test's own rewrite: every placeholder Ref becomes the real request Ref."""
    if isinstance(value, dict):
        return dict(ref) if set(value) == {'id', 'sha256'} else {k: rewrite(v, ref) for k, v in value.items()}
    if isinstance(value, list):
        return [rewrite(v, ref) for v in value]
    return value


def good_reply(text=REQUEST):
    return rewrite(json.loads((FIXTURES / 'intent_ir.json').read_text('utf-8')), request_ref(text))


class Worker:
    def __init__(self, value):
        self.text = value if isinstance(value, str) else json.dumps(value)
        self.calls = []

    async def __call__(self, prompt, system=None):
        self.calls.append((prompt, system))
        return self.text


def criteria_in(prompt):
    return json.loads(prompt.split('Criteria for this output:\n', 1)[1].split('\n', 1)[0])


def verdict(outcome='PASS'):
    def make(prompt):
        return json.dumps({'findings': [{'criterion_id': c['criterion_id'], 'outcome': outcome, 'reason': 'fixture'}
                                        for c in criteria_in(prompt)],
                           'uncertainties': [], 'limitations': [],
                           'required_correction': None if outcome == 'PASS' else 'fix it'})
    return make


@pytest.fixture(scope='module')
def rt():
    runtime = Runtime()
    result = runtime.admit(INTENT)
    assert result['passed'], result['failures']
    return runtime


def run(rt, reply, verifier=verdict(), request=REQUEST, **extra):
    return rt.invoke(INTENT, {'request': request, **extra}, worker_model=Worker(reply), verifier_model=verifier)


def test_valid_reply_delivers_what_the_pipeline_would_capture(rt):
    out = rt.invoke('research.intent', {'request': REQUEST}, worker_model=Worker(good_reply()), verifier_model=verdict())
    assert out['status'] == 'delivered', out.get('halt')
    expected = good_reply()
    assert out['outputs']['intent'] == expected
    receipt = out['receipt']
    assert receipt['output_sha256']['intent'] == hashlib.sha256(json_bytes(expected)).hexdigest()
    assert receipt['capability_id'] == INTENT and receipt['version'] == 'm1-8'
    assert [c['check_id'] for c in receipt['checks']] == ['intent_schema', 'source_spans', 'exact_identity']
    assert receipt['verifiers']['semantic'] == 'pass' and receipt['semantic_verifier']['status'] == 'reviewed'
    na = receipt['not_applicable_outside_pipeline']
    assert na and all(row['status'] == 'not_applicable_outside_pipeline' for row in na)
    assert len(receipt['model_calls']) == 1


def test_documents_become_source_blobs_and_reach_the_prompt(rt):
    worker = Worker(good_reply())
    out = rt.invoke(INTENT, {'request': REQUEST, 'documents': [{'name': 'a.txt', 'text': 'Some supplied text'}]},
                    worker_model=worker, verifier_model=verdict())
    assert out['status'] == 'delivered', out.get('halt')
    assert 'Some supplied text' in worker.calls[0][0]


def test_invalid_reply_halts_at_the_worker_with_the_product_code(rt):
    out = run(rt, 'not json')
    assert out['status'] == 'halted' and 'outputs' not in out
    assert out['halt']['stage'] == 'worker' and out['halt']['code'] == 'invalid_output'
    schema_bad = good_reply()
    del schema_bad['interpretation']
    out = run(rt, schema_bad)
    assert out['halt']['stage'] == 'worker' and out['halt']['code'] == 'contract_invalid'


def test_bad_span_halts_at_the_stage_check(rt):
    bad = good_reply()
    bad['interpretation']['problem']['source_spans'][0]['end'] = 100000
    out = run(rt, bad)
    assert out['status'] == 'halted' and out['halt']['stage'] == 'verifier' and out['halt']['code'] == 'check_failed'
    assert 'outside Unicode code-point bounds' in out['halt']['reason']


def test_verifier_fail_halts_and_delivers_nothing(rt):
    out = run(rt, good_reply(), verifier=verdict('FAIL'))
    assert out['status'] == 'halted' and 'outputs' not in out
    assert out['halt']['stage'] == 'semantic_verifier' and out['halt']['code'] == 'semantic_fail'


def test_no_verifier_model_is_never_delivered(rt):
    out = rt.invoke(INTENT, {'request': REQUEST}, worker_model=Worker(good_reply()))
    assert out['status'] == 'halted' and out['halt']['stage'] == 'semantic_verifier' and out['halt']['code'] == 'no_model'


def test_input_guard(rt):
    for bad, code in [({}, 'missing_input'), ({'request': ''}, 'validation'), ({'request': 'x', 'extra': 1}, 'unknown_input')]:
        out = rt.invoke(INTENT, bad, worker_model=Worker(good_reply()), verifier_model=verdict())
        assert out['halt']['stage'] == 'input_guard' and out['halt']['code'] == code


class Tampered:
    """importlib.resources.files wrapper that appends a byte to one pinned file."""
    def __init__(self, inner, target):
        self.inner, self.target = inner, target

    def joinpath(self, *parts):
        return Tampered(self.inner.joinpath(*parts), self.target)

    def read_bytes(self):
        data = self.inner.read_bytes()
        return data + b' ' if str(self.inner).replace('\\', '/').endswith(self.target) else data

    def read_text(self, *args, **kwargs):
        return self.read_bytes().decode('utf-8')


def tamper(monkeypatch, target='research_assets/compiler/intent_m1_8.txt'):
    import importlib.resources
    import jiuwenswarm.research.intent_release as release
    fake = lambda *a, **k: Tampered(real_files(*a, **k), target)
    monkeypatch.setattr(importlib.resources, 'files', fake)
    monkeypatch.setattr(release, 'files', fake)


def test_tampered_pin_refuses_at_call_time(rt, monkeypatch):
    tamper(monkeypatch)
    worker = Worker(good_reply())
    out = rt.invoke(INTENT, {'request': REQUEST}, worker_model=worker, verifier_model=verdict())
    assert out['status'] == 'halted' and out['halt']['stage'] == 'pin' and out['halt']['code'] == 'asset_integrity'
    assert worker.calls == []


def test_tampered_pin_refuses_at_load(monkeypatch):
    tamper(monkeypatch)
    fresh = Runtime()
    row = next(r for r in fresh.list() if r['id'] == INTENT)
    assert row['status'] == 'refused'
    out = fresh.invoke(INTENT, {'request': REQUEST}, worker_model=Worker(good_reply()), require_admission=False)
    assert out['halt']['stage'] == 'pin'


def test_describe_and_mcp_schema(rt):
    from jiuwenswarm.capsule_runtime.mcp import Server, tool_for
    tool = tool_for(rt, INTENT)
    props = tool['inputSchema']['properties']
    assert set(props) == {'request', 'documents', 'prior_plan_outcome'} and tool['inputSchema']['required'] == ['request']
    info = rt.describe(INTENT)
    assert info['needs_model'] and 'semantic verifier: applies' in ' '.join(info['verifier_stages'])
    server = Server(rt, verdict())
    server.client_sampling = True
    assert INTENT in server.visible()


def test_runtime_without_builtin_has_no_stage_capsules():
    assert INTENT not in Runtime([], include_builtin=False).capsules
