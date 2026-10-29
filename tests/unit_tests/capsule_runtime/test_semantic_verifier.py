import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from jiuwenswarm.capsule_runtime import Runtime, semantic
from jiuwenswarm.capsule_runtime.admission import _calc, _packet
from jiuwenswarm.capsule_runtime.verifier_backends import command_verifier, openai_verifier

GEN = 'research.generalist'
CONTRACT = {'objective': 'portable test'}


async def worker_model(prompt, system=None):
    return '{"data":{},"files":[],"expression":null,"limitations":[]}'


def criteria_in(prompt):
    marker = 'Criteria for this output:\n'
    return json.loads(prompt.split(marker, 1)[1].split('\n', 1)[0])


def reply(prompt, outcome='PASS', **extra):
    body = {'findings': [{'criterion_id': c['criterion_id'], 'outcome': outcome, 'reason': 'field result.data is consistent'}
                         for c in criteria_in(prompt)],
            'uncertainties': [], 'limitations': [], 'required_correction': None, **extra}
    return json.dumps(body)


class Fake:
    def __init__(self, make=reply):
        self.make, self.prompts = make, []

    def __call__(self, prompt):
        self.prompts.append(prompt)
        return self.make(prompt)


@pytest.fixture(scope='module')
def rt():
    runtime = Runtime()
    assert runtime.admit(GEN, model=worker_model, contract=CONTRACT)['passed']
    runtime.admit('utility.calculate')
    return runtime


def run(rt, verifier=None, **kwargs):
    return rt.invoke(GEN, {'packet': _packet({'q': 1})}, model=worker_model, contract=CONTRACT,
                     verifier_model=verifier, **kwargs)


def test_pass_verdict_delivers_and_model_sees_only_declaration_and_output(rt):
    fake = Fake()
    out = run(rt, fake)
    assert out['status'] == 'delivered' and out['receipt']['verifiers']['semantic'] == 'pass'
    assert out['receipt']['semantic_verifier']['status'] == 'reviewed'
    assert len(fake.prompts) == 1
    payload = json.loads(fake.prompts[0][fake.prompts[0].index('{"subject_declaration"'):])
    assert set(payload) == {'subject_declaration', 'subject_output'}
    assert json.loads(payload['subject_output']) == out['outputs']['result']
    assert 'portable test' not in payload['subject_declaration']  # the task contract never reaches the verifier


def test_fail_halts_at_semantic_verifier_with_findings_in_receipt_and_no_outputs(rt):
    out = run(rt, Fake(lambda p: reply(p, 'FAIL', required_correction='fix it')))
    assert out['status'] == 'halted' and 'outputs' not in out
    assert out['halt']['stage'] == 'semantic_verifier' and out['halt']['code'] == 'semantic_fail'
    findings = out['receipt']['semantic_verifier']
    assert findings['status'] == 'error' or findings['reviews']['result']['findings'][0]['outcome'] == 'FAIL'


def test_inconclusive_halts(rt):
    out = run(rt, Fake(lambda p: reply(p, 'INCONCLUSIVE')))
    assert out['halt']['stage'] == 'semantic_verifier' and out['halt']['code'] == 'semantic_not_passed'
    assert out['receipt']['semantic_verifier']['reviews']['result']['findings'][0]['outcome'] == 'INCONCLUSIVE'


def test_malformed_reply_halts(rt):
    for text in ['not json at all', '{"findings": []}']:
        out = run(rt, Fake(lambda p, text=text: text))
        assert out['status'] == 'halted' and out['halt']['stage'] == 'semantic_verifier' and 'outputs' not in out
    assert out['halt']['code'] in {'assessment_invalid', 'criterion_coverage_exact'}


def test_reply_that_brings_its_own_verdict_is_refused(rt):
    out = run(rt, Fake(lambda p: reply(p, 'FAIL', verdict='PASS')))
    assert out['halt'] == {'stage': 'semantic_verifier', 'code': 'assessment_invalid',
                           'reason': 'Verifier reply must contain only untrusted finding bodies'}


def test_a_verdict_that_contradicts_its_findings_halts_on_the_predicate(rt, monkeypatch):
    real = semantic.SemanticVerifier.review

    async def corrupt(self, declaration_ref, output_ref, profile_ref, context_ref, port, invoke, **kw):
        ref = await real(self, declaration_ref, output_ref, profile_ref, context_ref, port, invoke, **kw)
        record = self.store.read_record(ref)
        record['verdict'] = 'FAIL' if record['verdict'] != 'FAIL' else 'PASS'   # all findings stay PASS
        return self.store.put_record('verifier-assessment', record, record_id='assessment:forged')

    monkeypatch.setattr(semantic.SemanticVerifier, 'review', corrupt)
    out = run(rt, Fake())
    assert out['halt']['stage'] == 'semantic_verifier' and out['halt']['code'] == 'verifier_predicate_failed'
    assert 'verdict_follows_findings' in out['halt']['reason'] and 'outputs' not in out


def test_no_model_is_reported_as_not_run_never_as_a_pass(rt):
    out = run(rt)
    assert out['status'] == 'delivered'
    assert out['receipt']['verifiers']['semantic'] == 'not_run (no model configured)'
    assert out['receipt']['semantic_verifier'] == {'status': 'not_run', 'reason': 'no model configured'}
    required = run(rt, require_semantic=True)
    assert required['status'] == 'halted' and required['halt']['stage'] == 'semantic_verifier'
    assert required['halt']['code'] == 'no_model'


def test_deterministic_capsule_never_calls_the_verifier_model(rt):
    fake = Fake()
    out = rt.invoke('utility.calculate', {'packet': _calc()}, verifier_model=fake, require_semantic=True)
    assert out['status'] == 'delivered' and fake.prompts == []
    assert out['receipt']['verifiers'] == {
        'deterministic': 'pass', 'trace': 'not_applicable (no output port carries a trace manifest)',
        'packet_review': 'not_applicable (output is not a science review packet)',
        'semantic': 'not_applicable (deterministic capsule)'}
    assert out['receipt']['semantic_verifier']['status'] == 'not_run'


def test_describe_lists_verifier_stages(rt):
    assert any('not_applicable (deterministic capsule)' in line for line in rt.describe('utility.calculate')['verifier_stages'])
    assert any('model-based capsule' in line for line in rt.describe(GEN)['verifier_stages'])


def test_trace_stage_runs_when_an_output_carries_a_manifest_and_halts_on_failure():
    outputs = {'trace': {'manifest': {'events': 'garbage'}, 'blobs': {}, 'policy': {}}}
    report = semantic.run_trace(outputs)
    assert report is not None and report['advance'] is not True
    assert semantic.run_trace({'result': {}}) is None


def test_command_backend_reads_prompt_on_stdin(tmp_path, rt):
    script = tmp_path / 'verifier.py'
    script.write_text(
        'import sys, json\n'
        'prompt = sys.stdin.read()\n'
        'ids = [c["criterion_id"] for c in json.loads(prompt.split("Criteria for this output:\\n", 1)[1].split("\\n", 1)[0])]\n'
        'print(json.dumps({"findings": [{"criterion_id": i, "outcome": "PASS", "reason": "ok"} for i in ids],'
        ' "uncertainties": [], "limitations": [], "required_correction": None}))\n', encoding='utf-8')
    verifier = command_verifier([sys.executable, str(script)])
    out = run(rt, verifier)
    assert out['status'] == 'delivered' and out['receipt']['verifiers']['semantic'] == 'pass'


def test_openai_compatible_backend_against_a_local_fake_server(rt):
    seen = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            seen.update(path=self.path, model=body['model'])
            text = reply(body['messages'][0]['content'])
            data = json.dumps({'choices': [{'message': {'content': text}}]}).encode()
            self.send_response(200)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    server = HTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        verifier = openai_verifier('http://127.0.0.1:%d/v1' % server.server_port, 'fake-model')
        out = run(rt, verifier)
    finally:
        server.shutdown()
    assert out['status'] == 'delivered' and seen == {'path': '/v1/chat/completions', 'model': 'fake-model'}
