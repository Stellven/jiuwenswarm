import asyncio
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from jiuwenswarm.capsule_runtime import Runtime
from jiuwenswarm.capsule_runtime.admission import _calc, _packet
from jiuwenswarm.capsule_runtime.loader import BUILTIN_ROOT
from jiuwenswarm.research.capsule_extensions.calculate_v4 import worker as calculate_worker
from jiuwenswarm.research.capsule_extensions.packet import produced

REPO = Path(__file__).parents[3]
CALC = 'utility.calculate'


@pytest.fixture(scope='module')
def runtime():
    return Runtime()


def test_all_builtin_capsules_load(runtime):
    rows = {r['id']: r for r in runtime.list()}
    assert len(rows) == 10 and all(r['status'] == 'loaded' for r in rows.values())
    assert CALC in rows and rows[CALC]['version'] == 'm1-4'


def test_invoke_calculate_delivers_what_the_worker_produces():
    fresh = Runtime()
    fresh.admit(CALC)
    source = _calc()
    out = fresh.invoke(CALC, {'packet': source})
    assert out['status'] == 'delivered' and 'halt' not in out
    direct = asyncio.run(calculate_worker.execute(None, {'packet': source}))
    assert out['outputs']['result'] == json.loads(direct['result'].data)
    receipt = out['receipt']
    assert receipt['capability_id'] == CALC and receipt['version'] == 'm1-4'
    assert receipt['check_verdict'] == 'PASS' and receipt['declared_effects']['effect_class'] == 'pure'
    assert len(receipt['release_hash']) == 64 and len(receipt['input_sha256']) == 64
    assert receipt['output_sha256']['result'] == hashlib.sha256(direct['result'].data).hexdigest()
    assert receipt['started_at'] <= receipt['finished_at'] and receipt['admitted'] is True


def test_malformed_input_halts_at_input_guard():
    fresh = Runtime()
    fresh.admit(CALC)
    for bad, code in [({}, 'missing_input'), ({'packet': {'nope': 1}}, 'contract_invalid'),
                      ({'packet': _calc(), 'extra': 1}, 'unknown_input'), ([], 'inputs_type')]:
        out = fresh.invoke(CALC, bad)
        assert out['status'] == 'halted' and 'outputs' not in out
        assert out['halt']['stage'] == 'input_guard' and out['halt']['code'] == code


def test_packet_hash_error_passes_through_as_halt_code():
    fresh = Runtime()
    fresh.admit(CALC)
    source = _packet({'table': {'columns': ['v'], 'rows': []}}, files=[('f', 'text')])
    source['files'][0]['text'] = 'changed after hashing'
    out = fresh.invoke(CALC, {'packet': source})
    assert out['halt'] == {'stage': 'input_guard', 'code': 'packet_hash',
                           'reason': 'packet: File text does not match its digest'}


def test_worker_refusal_keeps_its_research_error_code():
    fresh = Runtime()
    fresh.admit(CALC)
    bad = _calc()
    bad['data']['calculation']['columns'] = ['missing']
    out = fresh.invoke(CALC, {'packet': bad})
    assert out['halt']['stage'] == 'worker' and out['halt']['code'] == 'calculation_input' and 'outputs' not in out


def test_not_admitted_is_refused_unless_explicitly_waived():
    fresh = Runtime()
    out = fresh.invoke(CALC, {'packet': _calc()})
    assert out['status'] == 'halted' and out['halt']['stage'] == 'pin' and out['halt']['code'] == 'not_admitted'
    assert fresh.invoke(CALC, {'packet': _calc()}, require_admission=False)['status'] == 'delivered'


def test_wrong_worker_output_halts_at_verifier_with_no_outputs():
    fresh = Runtime()
    fresh.admit(CALC)
    capsule = fresh.get(CALC)
    real = capsule.execute

    async def wrong(ctx, inputs):
        result = json.loads((await real(ctx, inputs))['result'].data)
        result['data']['calculation_result']['columns']['v']['sum'] = '100'
        return {'result': produced(result)}

    capsule.execute = wrong
    out = fresh.invoke(CALC, {'packet': _calc()})
    assert out['status'] == 'halted' and 'outputs' not in out
    assert out['halt']['stage'] == 'verifier' and out['halt']['code'] == 'check_failed'
    assert out['receipt']['check_verdict'] == 'FAIL'


def test_worker_that_overruns_its_time_limit_halts():
    fresh = Runtime()
    capsule = fresh.get(CALC)
    capsule.wall_s = 0.2

    async def slow(ctx, inputs):
        time.sleep(1.5)  # blocks, as a CPU-bound worker would
        return {}

    capsule.execute = slow
    started = time.monotonic()
    out = fresh.invoke(CALC, {'packet': _calc()}, require_admission=False)
    assert out['halt'] == {'stage': 'worker', 'code': 'timeout',
                           'reason': 'Worker exceeded the declared wall time of 0.2s'}
    assert time.monotonic() - started < 1.2


@pytest.fixture
def tree(tmp_path):
    target = tmp_path / 'ext'
    shutil.copytree(BUILTIN_ROOT, target, ignore=shutil.ignore_patterns('history', '__pycache__'))
    return target


def test_tampered_worker_byte_halts_at_pin(tree):
    worker = tree / 'calculate_v4' / 'worker.py'
    worker.write_bytes(worker.read_bytes() + b'\n# one byte of drift\n')
    tampered = Runtime([tree], include_builtin=False)
    row = {r['id']: r for r in tampered.list()}[CALC]
    assert row['status'] == 'refused' and 'calculate_v4/worker.py' in row['reason']
    out = tampered.invoke(CALC, {'packet': _calc()}, require_admission=False)
    assert out['status'] == 'halted' and out['halt']['stage'] == 'pin' and 'outputs' not in out
    assert out['halt']['code'] == 'extension_manifest'


def test_shared_runtime_tamper_is_caught_too(tree):
    packet_py = tree / 'packet.py'
    packet_py.write_bytes(packet_py.read_bytes() + b'\n')
    refused = Runtime([tree], include_builtin=False)
    assert all(r['status'] == 'refused' for r in refused.list())


def test_pin_is_rechecked_at_every_call_after_load():
    fresh = Runtime()
    fresh.admit(CALC)
    fresh.get(CALC).release_hash = '0' * 64  # release.json no longer what was loaded
    out = fresh.invoke(CALC, {'packet': _calc()})
    assert out['halt']['stage'] == 'pin' and out['halt']['reason'] == 'release.json changed since load'


@pytest.mark.parametrize('key', ['utility.calculate', 'utility.calculate_typed', 'utility.table_normalize',
                                 'utility.table_normalize_typed', 'utility.markdown_report',
                                 'utility.markdown_report_typed', 'utility.packet_report', 'utility.summary_to_packet'])
def test_admit_passes_for_real_capsules(runtime, key):
    result = runtime.admit(key)
    assert result['passed'], result['failures']
    assert any(e['case'].startswith('verifier_bites') and e['ok'] for e in result['evidence'])


def test_generalist_admits_against_a_canned_reply_and_needs_a_real_model_to_run():
    fresh = Runtime()
    result = fresh.admit('research.generalist')
    assert result['passed'] and any(e['case'] == 'stub_model' for e in result['evidence'])
    out = fresh.invoke('research.generalist', {'packet': _packet({})}, contract={'objective': 'x'})
    assert out['halt']['stage'] == 'worker' and out['halt']['code'] == 'no_model'

    async def model(prompt, system=None):
        return '{"data":{},"files":[],"expression":null,"limitations":[]}'

    out = fresh.invoke('research.generalist', {'packet': _packet({})}, worker_model=model, contract={'objective': 'portable test'})
    assert out['status'] == 'delivered' and out['outputs']['result']['trust'] == 'low'


def test_admission_fails_when_the_verifier_does_not_bite():
    fresh = Runtime()
    capsule = fresh.get(CALC)
    capsule.check = lambda ctx, inputs, outputs: [{'check_id': c, 'outcome': 'PASS', 'reason': 'rubber stamp'}
                                                  for c in capsule.declaration['guarantees']['acceptance']]
    result = fresh.admit(CALC)
    assert not result['passed'] and any('verifier_bites' in f for f in result['failures'])


def test_cli_list_describe_and_invoke(tmp_path):
    def cli(*args):
        return subprocess.run([sys.executable, '-m', 'jiuwenswarm.capsule_runtime', *args], cwd=REPO,
                              capture_output=True, text=True, timeout=120)
    listing = cli('list')
    assert listing.returncode == 0 and CALC in listing.stdout
    assert json.loads(cli('describe', CALC).stdout)['admitted'] is False
    inputs, receipt = tmp_path / 'in.json', tmp_path / 'receipt.json'
    inputs.write_text(json.dumps({'packet': _calc()}), encoding='utf-8')
    done = cli('invoke', CALC, '--inputs', str(inputs), '--out', str(receipt))
    assert done.returncode == 0, done.stderr
    assert json.loads(receipt.read_text('utf-8'))['receipt']['check_verdict'] == 'PASS'
    inputs.write_text('{}', encoding='utf-8')
    assert cli('invoke', CALC, '--inputs', str(inputs)).returncode == 2


class McpClient:
    def __init__(self):
        self.proc = subprocess.Popen([sys.executable, '-m', 'jiuwenswarm.capsule_runtime.mcp'], cwd=REPO,
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.next = 0

    def send(self, method, params=None, notify=False):
        message = {'jsonrpc': '2.0', 'method': method}
        if params is not None:
            message['params'] = params
        if not notify:
            self.next += 1
            message['id'] = self.next
        self.proc.stdin.write((json.dumps(message) + '\n').encode())
        self.proc.stdin.flush()
        if notify:
            return None
        reply = json.loads(self.proc.stdout.readline())
        assert reply['id'] == self.next
        return reply

    def close(self):
        self.proc.stdin.close()
        self.proc.wait(timeout=30)
        return self.proc.stderr.read().decode()


def test_mcp_round_trip_over_stdio():
    client = McpClient()
    try:
        init = client.send('initialize', {'protocolVersion': '2025-06-18', 'capabilities': {},
                                          'clientInfo': {'name': 'scripted', 'version': '0'}})
        assert init['result']['protocolVersion'] == '2025-06-18' and 'tools' in init['result']['capabilities']
        client.send('notifications/initialized', notify=True)
        tools = {t['name']: t for t in client.send('tools/list')['result']['tools']}
        assert len(tools) == 8 and 'research.generalist' not in tools  # no model path for it yet
        tool = tools[CALC]
        assert tool['inputSchema']['required'] == ['packet']
        assert 'trust' in tool['inputSchema']['properties']['packet']['properties']
        assert 'Guarantees' in tool['description'] and 'hash-pinned' in tool['description']
        good = client.send('tools/call', {'name': CALC, 'arguments': {'packet': _calc()}})['result']
        body = json.loads(good['content'][0]['text'])
        assert good['isError'] is False and body['status'] == 'delivered' and body['receipt']['check_verdict'] == 'PASS'
        bad = client.send('tools/call', {'name': CALC, 'arguments': {'packet': {'x': 1}}})['result']
        halted = json.loads(bad['content'][0]['text'])
        assert bad['isError'] is True and halted['halt']['stage'] == 'input_guard' and 'outputs' not in halted
        assert client.send('tools/call', {'name': 'nope', 'arguments': {}})['result']['isError'] is True
        assert client.send('no/such/method')['error']['code'] == -32601
    finally:
        log = client.close()
    assert 'serving 10 tool(s)' in log
