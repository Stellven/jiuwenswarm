"""Evaluation (m1-5) through the portable runtime: same pins, checks and verifier as the pipeline, fake models only."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from jiuwenswarm.capsule_runtime import Runtime
from jiuwenswarm.research.state import json_bytes

from .test_intent_portable import verdict

SOURCE = Path('tests/fixtures/research/pipeline/source-valid')
EVAL = 'research.evaluation'


def load(name):
    value = json.loads((SOURCE / (name + '.json')).read_text('utf-8'))
    value.pop('ext', None)  # editorial extension of the demonstration fixtures
    return value


def inputs():
    blueprint, payload = load('hypothesis_blueprint'), load('benchmark_payload')
    payload['blueprint_ref'] = {'id': payload['blueprint_ref']['id'], 'sha256': hashlib.sha256(json_bytes(blueprint)).hexdigest()}
    brief = json.loads(Path('tests/fixtures/research/compiler/research_brief.json').read_text('utf-8'))
    return {'brief': brief, 'hypothesis_blueprint': blueprint, 'benchmark_payload': payload}


def verdict_for(refs, mutate=None):
    """The pipeline fixture verdict with its placeholder refs pointed at the bound input refs."""
    value = load('evaluation_verdict')
    value.update(brief_ref=refs['brief'], blueprint_ref=refs['hypothesis_blueprint'], benchmark_ref=refs['benchmark_payload'])
    if mutate:
        mutate(value)
    return value


class VerdictWorker:
    def __init__(self, mutate=None, raw=None):
        self.mutate, self.raw, self.calls = mutate, raw, []

    async def __call__(self, prompt, system=None):
        self.calls.append((prompt, system))
        if self.raw is not None:
            return self.raw
        return json.dumps(verdict_for(json.loads(prompt)['input_refs'], self.mutate))


@pytest.fixture(scope='module')
def rt():
    runtime = Runtime()
    result = runtime.admit(EVAL)
    assert result['passed'], result['failures']
    return runtime


def run(rt, worker, verifier=verdict(), given=None):
    return rt.invoke(EVAL, given if given is not None else inputs(), worker_model=worker, verifier_model=verifier)


def test_valid_reply_delivers_what_the_pipeline_would_capture(rt):
    worker = VerdictWorker()
    out = rt.invoke('research.evaluation', inputs(), worker_model=worker, verifier_model=verdict())
    assert out['status'] == 'delivered', out.get('halt')
    refs = json.loads(worker.calls[0][0])['input_refs']
    given = inputs()
    assert refs['hypothesis_blueprint'] == {'id': given['benchmark_payload']['blueprint_ref']['id'],
                                            'sha256': hashlib.sha256(json_bytes(given['hypothesis_blueprint'])).hexdigest()}
    assert out['outputs']['evaluation_verdict'] == verdict_for(refs)
    receipt = out['receipt']
    assert receipt['capability_id'] == EVAL and receipt['version'] == 'm1-5'
    assert [c['check_id'] for c in receipt['checks']] == ['evaluation_verdict_schema', 'refs_match_inputs', 'blueprint_rules_disjoint',
                                                          'rule_recomputation', 'finding_coverage', 'registered_rule_only']
    assert all(c['outcome'] == 'PASS' for c in receipt['checks'])
    assert receipt['verifiers']['semantic'] == 'pass' and receipt['semantic_verifier']['status'] == 'reviewed'
    assert receipt['verifiers']['packet_review'].startswith('not_applicable')
    na = receipt['not_applicable_outside_pipeline']
    assert 'input_provenance' in [row['check'] for row in na]
    assert all(row['status'] == 'not_applicable_outside_pipeline' for row in na)
    assert len(receipt['model_calls']) == 1


def test_invalid_reply_halts_at_the_worker_with_the_product_code(rt):
    out = run(rt, VerdictWorker(raw='not json'))
    assert out['status'] == 'halted' and 'outputs' not in out
    assert out['halt']['stage'] == 'worker' and out['halt']['code'] == 'invalid_output'
    out = run(rt, VerdictWorker(mutate=lambda v: v.pop('classification')))
    assert out['halt']['stage'] == 'worker' and out['halt']['code'] == 'contract_invalid'


def test_bad_evidence_halts_at_the_stage_check(rt):
    def flip(verdict_):
        verdict_['classification'] = 'PASS' if verdict_['classification'] != 'PASS' else 'FAIL'

    def other_value(verdict_):
        verdict_['findings'][0]['treatment_value'] = 123456.0

    def other_blueprint(verdict_):
        verdict_['blueprint_ref'] = {'id': 'blob:' + '0' * 64, 'sha256': '0' * 64}
    for mutate, expected in [(flip, 'overall_verdict_recomputed'), (other_value, 'values_copied'), (other_blueprint, 'refs_match_inputs')]:
        out = run(rt, VerdictWorker(mutate=mutate))
        assert out['status'] == 'halted' and out['halt']['stage'] == 'verifier' and out['halt']['code'] == 'check_failed', mutate
        assert expected in out['halt']['reason'] and 'outputs' not in out


def test_verifier_fail_halts_and_delivers_nothing(rt):
    out = run(rt, VerdictWorker(), verifier=verdict('FAIL'))
    assert out['status'] == 'halted' and 'outputs' not in out
    assert out['halt']['stage'] == 'semantic_verifier' and out['halt']['code'] == 'semantic_fail'


def test_no_verifier_model_is_never_delivered(rt):
    out = rt.invoke(EVAL, inputs(), worker_model=VerdictWorker())
    assert out['status'] == 'halted' and out['halt']['stage'] == 'semantic_verifier' and out['halt']['code'] == 'no_model'


def test_input_guard(rt):
    other = inputs()
    other['hypothesis_blueprint']['claim'] = other['hypothesis_blueprint']['claim'] + ' (edited)'
    broken = inputs()
    del broken['benchmark_payload']['metrics']
    cases = [({}, 'missing_input'), ({**inputs(), 'extra': 1}, 'unknown_input'),
             (other, 'blueprint_payload_mismatch'), (broken, None)]
    for bad, code in cases:
        worker = VerdictWorker()
        out = run(rt, worker, given=bad)
        assert out['halt']['stage'] == 'input_guard', code
        if code:
            assert out['halt']['code'] == code
        assert worker.calls == []


def tamper(monkeypatch, target):
    real = Path.read_bytes
    monkeypatch.setattr(Path, 'read_bytes', lambda self: real(self) + b'\n' if str(self).replace('\\', '/').endswith(target) else real(self))


@pytest.mark.parametrize('target', ['research/capsules/evaluation.py', 'research/science.py', 'research/resources/capsules/verifier_implementation.txt'])
def test_tampered_pin_refuses_at_call_time(rt, monkeypatch, target):
    tamper(monkeypatch, target)
    worker = VerdictWorker()
    out = run(rt, worker)
    assert out['status'] == 'halted' and out['halt']['stage'] == 'pin'
    assert worker.calls == []


def test_tampered_pin_refuses_at_load(monkeypatch):
    tamper(monkeypatch, 'research/capsules/evaluation.py')
    fresh = Runtime()
    row = next(r for r in fresh.list() if r['id'] == EVAL)
    assert row['status'] == 'refused'
    out = fresh.invoke(EVAL, inputs(), worker_model=VerdictWorker(), require_admission=False)
    assert out['halt']['stage'] == 'pin'


def test_describe_and_mcp_schema(rt):
    from jiuwenswarm.capsule_runtime.mcp import Server, tool_for
    tool = tool_for(rt, EVAL)
    props = tool['inputSchema']['properties']
    assert set(props) == {'brief', 'hypothesis_blueprint', 'benchmark_payload'}
    assert sorted(tool['inputSchema']['required']) == sorted(props) and 'task_objective' not in props
    assert all(p['description'] for p in props.values())
    info = rt.describe(EVAL)
    assert info['needs_model'] and 'semantic verifier: applies' in ' '.join(info['verifier_stages'])
    server = Server(rt, verdict())
    server.client_sampling = True
    assert EVAL in server.visible()


def test_runtime_without_builtin_has_no_stage_capsules():
    assert EVAL not in Runtime([], include_builtin=False).capsules
