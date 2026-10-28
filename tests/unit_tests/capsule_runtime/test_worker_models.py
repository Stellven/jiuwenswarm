import json
import subprocess
import sys

import pytest

from jiuwenswarm.capsule_runtime import Runtime
from jiuwenswarm.capsule_runtime.admission import _packet
from jiuwenswarm.capsule_runtime.verifier_backends import CommandModel

GEN = 'research.generalist'
GOOD = '{"data":{"k":1},"files":[],"expression":null,"limitations":[]}'
REPO = __import__('pathlib').Path(__file__).parents[3]


class Worker:
    kind = 'api'
    model_name = 'fake-worker-1'
    identity = 'fake:worker'
    last_usage = {'prompt': 12, 'completion': 3}

    def __init__(self, reply=GOOD):
        self.reply, self.seen = reply, []

    async def __call__(self, prompt, system=None):
        self.seen.append((prompt, system))
        return self.reply


@pytest.fixture(scope='module')
def rt():
    runtime = Runtime()
    assert runtime.admit(GEN)['passed']
    return runtime


def run(rt, worker, **kwargs):
    return rt.invoke(GEN, {'packet': _packet({'q': 1})}, worker_model=worker, contract={'objective': 'summarize'}, **kwargs)


def test_fake_worker_model_drives_generalist_end_to_end(rt):
    worker = Worker()
    out = run(rt, worker)
    assert out['status'] == 'delivered' and out['outputs']['result']['data']['k'] == 1
    receipt = out['receipt']
    (call,) = receipt['model_calls']
    assert call['provider_kind'] == 'api' and call['model'] == 'fake-worker-1' and call['tokens'] == {'prompt': 12, 'completion': 3}
    assert all(len(call[k]) == 64 for k in ('prompt_sha256', 'system_sha256', 'reply_sha256'))
    assert receipt['worker_model']['calls'] == 1 and receipt['worker_model']['limit'] == 1
    prompt, system = worker.seen[0]
    assert 'summarize' in prompt and 'Complete only the frozen task objective' in system   # pinned instructions come from the capsule


def test_bad_worker_reply_halts_at_worker_with_the_capsules_own_code(rt):
    for reply in ['not json', '{"data": {}}']:
        out = run(rt, Worker(reply))
        assert out['status'] == 'halted' and 'outputs' not in out
        assert out['halt']['stage'] == 'worker' and out['halt']['code'] == 'generalist_output'
        assert len(out['receipt']['model_calls']) == 1


def test_non_text_reply_halts(rt):
    out = run(rt, Worker(reply={'oops': 1}))
    assert out['halt'] == {'stage': 'worker', 'code': 'model_reply', 'reason': 'Model reply must be text'}


def test_model_call_limit_is_enforced():
    fresh = Runtime()
    capsule = fresh.get(GEN)
    real = capsule.execute

    async def greedy(ctx, inputs):
        await ctx.model('first')
        return await real(ctx, inputs)   # makes a second call

    capsule.execute = greedy
    worker = Worker()
    out = fresh.invoke(GEN, {'packet': _packet({})}, worker_model=worker, contract={'objective': 'x'}, require_admission=False)
    assert out['halt']['stage'] == 'worker' and out['halt']['code'] == 'model_call_limit'
    assert len(worker.seen) == 1 and len(out['receipt']['model_calls']) == 1


def test_no_model_halts_with_no_model(rt):
    out = rt.invoke(GEN, {'packet': _packet({})}, contract={'objective': 'x'})
    assert out['halt']['stage'] == 'worker' and out['halt']['code'] == 'no_model' and 'sampling' in out['halt']['reason']


def test_verifier_independence_is_recorded(rt):
    def verifier_for(identity):
        class V:
            def __init__(self):
                self.identity = identity

            def __call__(self, prompt):
                marker = 'Criteria for this output:\n'
                ids = [c['criterion_id'] for c in json.loads(prompt.split(marker, 1)[1].split('\n', 1)[0])]
                return json.dumps({'findings': [{'criterion_id': i, 'outcome': 'PASS', 'reason': 'ok'} for i in ids],
                                   'uncertainties': [], 'limitations': [], 'required_correction': None})
        return V()

    same = run(rt, Worker(), verifier_model=verifier_for('fake:worker'))
    other = run(rt, Worker(), verifier_model=verifier_for('fake:other'))
    assert same['status'] == other['status'] == 'delivered'
    assert same['receipt']['verifier_independent'] is False and other['receipt']['verifier_independent'] is True
    assert len(other['receipt']['semantic_verifier']['calls']) == 1


def test_command_backend_is_a_worker_model(tmp_path, rt):
    script = tmp_path / 'worker.py'
    script.write_text('import sys\nsys.stdin.read()\nprint(%r)\n' % GOOD, encoding='utf-8')
    out = run(rt, CommandModel([sys.executable, str(script)]))
    assert out['status'] == 'delivered' and out['receipt']['model_calls'][0]['provider_kind'] == 'cmd'


class Client:
    def __init__(self, *args, sampling=False):
        self.proc = subprocess.Popen([sys.executable, '-m', 'jiuwenswarm.capsule_runtime.mcp', *args], cwd=REPO,
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.next, self.sampling, self.sampled = 0, sampling, []

    def _send(self, message):
        self.proc.stdin.write((json.dumps(message) + '\n').encode())
        self.proc.stdin.flush()

    def call(self, method, params=None):
        self.next += 1
        self._send({'jsonrpc': '2.0', 'id': self.next, 'method': method, 'params': params or {}})
        while True:
            message = json.loads(self.proc.stdout.readline())
            if message.get('method') == 'sampling/createMessage':
                self.sampled.append(message['params'])
                self._send({'jsonrpc': '2.0', 'id': message['id'], 'result': {
                    'role': 'assistant', 'model': 'scripted-model', 'content': {'type': 'text', 'text': GOOD}}})
                continue
            assert message['id'] == self.next
            return message

    def start(self):
        capabilities = {'sampling': {}} if self.sampling else {}
        self.call('initialize', {'protocolVersion': '2025-06-18', 'capabilities': capabilities,
                                 'clientInfo': {'name': 'scripted', 'version': '0'}})
        self._send({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        return self

    def close(self):
        self.proc.stdin.close()
        self.proc.wait(timeout=30)
        self.proc.stderr.read()
        for stream in (self.proc.stdout, self.proc.stderr):
            stream.close()


def call_generalist(client, **extra):
    arguments = {'packet': _packet({'q': 1}), 'task_objective': 'summarize', **extra}
    reply = client.call('tools/call', {'name': GEN, 'arguments': arguments})['result']
    return reply, json.loads(reply['content'][0]['text'])


def test_mcp_sampling_backs_ctx_model():
    client = Client(sampling=True).start()
    try:
        names = [t['name'] for t in client.call('tools/list')['result']['tools']]
        assert GEN in names and len(names) == 10
        reply, body = call_generalist(client)
        assert reply['isError'] is False and body['status'] == 'delivered'
        (call,) = body['receipt']['model_calls']
        assert call['provider_kind'] == 'mcp_sampling' and call['model'] == 'scripted-model'
        (sampled,) = client.sampled
        assert 'Complete only the frozen task objective' in sampled['systemPrompt']   # capsule's pinned text, not the caller's
        assert sampled['messages'][0]['content']['type'] == 'text'
    finally:
        client.close()


def test_mcp_without_sampling_or_backend_halts_no_model():
    client = Client().start()
    try:
        names = [t['name'] for t in client.call('tools/list')['result']['tools']]
        assert GEN not in names and len(names) == 8
        reply, body = call_generalist(client)
        assert reply['isError'] is True
        assert body['halt']['stage'] == 'worker' and body['halt']['code'] == 'no_model' and 'outputs' not in body
    finally:
        client.close()


def test_mcp_with_a_configured_worker_command(tmp_path):
    script = tmp_path / 'worker.py'
    script.write_text('import sys\nsys.stdin.read()\nprint(%r)\n' % GOOD, encoding='utf-8')
    client = Client('--worker-cmd', '"%s" "%s"' % (sys.executable, script), sampling=True).start()
    try:
        assert GEN in [t['name'] for t in client.call('tools/list')['result']['tools']]
        _, body = call_generalist(client)
        assert body['status'] == 'delivered' and body['receipt']['model_calls'][0]['provider_kind'] == 'cmd'
        assert client.sampled == []   # the configured backend wins over sampling
    finally:
        client.close()
