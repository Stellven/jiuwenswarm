"""engine.size_prefill_batch on real Spark fixtures: a Muse Q2_K server load at the default batch (B) and at
-b 2048 -ub 2048 (Bub), and the lab rows of the same requests. Planted faults must fail."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

HERE = Path(__file__).resolve().parent
RUN = HERE.parent / 'run.py'
FIX = HERE / 'fixtures'
ROWS = json.loads((FIX / 'rows.json').read_text())


def call(capability, **inputs):
    done = subprocess.run([sys.executable, str(RUN)], input=json.dumps(dict(capability=capability, inputs=inputs)),
                          capture_output=True, text=True, check=True)
    reply = json.loads(done.stdout)
    assert reply['outcome'] == 'ok'
    return reply['outputs']


def planned(tmp_path, **overrides):
    inputs = dict(baseline_log=str(FIX / 'B.server.log'), prompt_tokens=[511, 2047], device_budget_mib=110000,
                  plan_out=str(tmp_path / 'plan.json')) | overrides
    return call('plan', **inputs)


def verified(tmp_path, **overrides):
    planned(tmp_path)
    inputs = dict(plan=str(tmp_path / 'plan.json'), server_log=str(FIX / 'Bub.server.log'), device_budget_mib=110000,
                  baseline_rows=ROWS['baseline'], candidate_rows=ROWS['candidate']) | overrides
    return call('verify', **inputs)


def test_plan_picks_one_micro_batch_for_the_longest_prompt(tmp_path):
    out = planned(tmp_path)
    doc = out['plan']
    assert out['done'] and doc['args'] == ['-b', '2048', '-ub', '2048']
    assert doc['micro_batches'] == {'511': dict(before=1, after=1), '2047': dict(before=4, after=1)}
    assert doc['estimate_mib'] >= 102229  # the linear estimate is above what the probe measured
    assert json.loads((tmp_path / 'plan.json').read_text()) == doc


def test_plan_steps_down_under_a_tight_budget(tmp_path):
    out = planned(tmp_path, device_budget_mib=104500)
    assert out['done'] and out['plan']['ubatch'] == 1024 and [t['ubatch'] for t in out['plan']['tried']] == [2048, 1024]
    out = planned(tmp_path, device_budget_mib=90000)
    assert not out['done'] and out['plan']['ubatch'] == 512 and any(c['name'] == 'fits_budget' and c['status'] == 'fail' for c in out['checks'])


def test_real_probe_passes(tmp_path):
    out = verified(tmp_path)
    assert out['done'] and out['stage_reached'] == 'runtime acceptance', out['not_done_because']
    status = {c['name']: c for c in out['checks']}
    assert status['output_agreement:p512']['detail'].startswith('greedy output byte-identical')
    assert 'first 136 characters' in status['output_agreement:p2048']['detail']  # batch split changes summation order
    assert out['measured']['n_ubatch'] == 2048


@pytest.mark.parametrize('fault, overrides, failing', [
    ('batch not applied (server ran the default)', dict(server_log=str(FIX / 'B.server.log')), 'batch_applied'),
    ('device buffers over budget', dict(device_budget_mib=100000), 'device_budget'),
    ('prompt longer than the micro-batch', dict(prompt_tokens=[4000]), 'one_micro_batch'),
    ('outputs diverge early', dict(min_agree_chars=180), 'output_agreement:p2048'),
    ('no compute buffer line (wrong log level)', dict(server_log='llama_context: n_batch = 2048\nllama_context: n_ubatch = 2048\n'), 'device_budget'),
])
def test_planted_faults_fail(tmp_path, fault, overrides, failing):
    out = verified(tmp_path, **overrides)
    assert not out['done'], fault
    assert any(c['name'] == failing and c['status'] == 'fail' for c in out['checks']), (fault, out['checks'])


def test_missing_baseline_row_and_bad_plan_fail(tmp_path):
    out = verified(tmp_path, baseline_rows=[r for r in ROWS['baseline'] if r['request'] == 'p512'])
    assert not out['done'] and any(c['name'] == 'output_agreement:p2048' and c['status'] == 'fail' for c in out['checks'])
    out = call('verify', plan={'format': 'other'}, server_log='x\ny', device_budget_mib=1, baseline_rows=[], candidate_rows=[])
    assert not out['done'] and out['checks'][0]['name'] == 'plan_format'
    out = call('verify', plan={}, device_budget_mib=1)
    assert not out['done']
