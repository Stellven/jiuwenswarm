"""engine.size_prefill_batch on real Spark fixtures: a Muse Q2_K server load at the default batch (B) and at
-b 2048 -ub 2048 (Bub), and the lab rows of the same requests. Planted faults must fail."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

import pytest

HERE = Path(__file__).resolve().parent
RUN = HERE.parent / 'run.py'
FIX = HERE / 'fixtures'
ROWS = json.loads((FIX / 'rows.json').read_text())
# Selected lines from Nov 25 lab/B.stderr.log and lab/Bub.stderr.log and the Nov 26 historical
# mixed-pack load at graph-v4/runs/fd07412594dd4491864b5fddfbf37b2f/server.log.
MIXED_DEFAULT = FIX / 'measured-mixed-default.server.log'
MEASURED_PAIR = dict(baseline_log=str(FIX / 'measured-q2-default.server.log'),
                     candidate_log=str(FIX / 'measured-q2-candidate.server.log'))


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
    assert doc['estimate_mib'] < 108000  # KV is sized by n_ctx, not scaled with the ubatch (1.0.0 did)
    assert json.loads((tmp_path / 'plan.json').read_text()) == doc


def test_plan_steps_down_under_a_tight_budget(tmp_path):
    out = planned(tmp_path, device_budget_mib=104500)
    assert out['done'] and out['plan']['ubatch'] == 1024 and [t['ubatch'] for t in out['plan']['tried']] == [2048, 1024]
    out = planned(tmp_path, device_budget_mib=90000)
    assert not out['done'] and out['plan']['ubatch'] == 512 and any(c['name'] == 'fits_budget' and c['status'] == 'fail' for c in out['checks'])


def test_plan_refuses_a_baseline_at_a_smaller_context(tmp_path):
    # KV and attention compute grow with n_ctx; a 4096-context log cannot bound a 32k-context load
    out = planned(tmp_path, n_ctx=33792, prompt_tokens=[4095, 32767])
    status = {c['name']: c for c in out['checks']}
    assert not out['done'] and status['baseline_context']['status'] == 'fail'
    assert planned(tmp_path, n_ctx=4096)['done']


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


def test_fill_gives_the_rest_of_the_budget_to_the_moe_cache(tmp_path):
    out = planned(tmp_path, fill_moe_cache_headroom_mib=2048)
    doc = out['plan']
    assert out['done'], out['not_done_because']
    assert doc['args'][:4] == ['-b', '2048', '-ub', '2048'] and doc['args'][4] == '--moe-cache-mib'
    cache = doc['moe_cache_mib']
    assert cache % 1024 == 0 and cache == int(doc['args'][5]) and cache > doc['moe_cache_from_mib']
    assert 110000 - 2048 - 1024 < doc['estimate_mib'] <= 110000 - 2048
    # without the input the plan is unchanged (1.1.0 behaviour)
    assert 'moe_cache_mib' not in planned(tmp_path)['plan']


def test_measured_reference_transfers_only_buffer_deltas(tmp_path):
    out = planned(tmp_path, baseline_log=str(MIXED_DEFAULT), measured_reference=MEASURED_PAIR,
                  fill_moe_cache_headroom_mib=2048)
    assert out['done'], out['not_done_because']
    doc = out['plan']
    assert doc['args'] == ['-b', '2048', '-ub', '2048', '--moe-cache-mib', '66560']
    assert doc['estimate_mib'] == 107364.8 and doc['moe_cache_from_mib'] == 61438.5
    assert doc['tried'][0]['estimate_method'] == 'measured_reference'
    evidence = doc['measured_reference']
    assert evidence['delta_mib'] == {'kv': 276.0, 'compute': 589.54, 'host_compute': 217.57}
    assert evidence['baseline']['device_mib']['moe_cache'] == 61425.0
    for name, path in [('fresh_baseline', MIXED_DEFAULT), ('baseline', Path(MEASURED_PAIR['baseline_log'])),
                       ('candidate', Path(MEASURED_PAIR['candidate_log']))]:
        assert evidence[name]['sha256'] == sha256(path.read_bytes()).hexdigest()
    assert doc['micro_batches']['2047'] == {'before': 4, 'after': 1}
    linear = planned(tmp_path, baseline_log=str(MIXED_DEFAULT), fill_moe_cache_headroom_mib=2048)['plan']
    assert linear['moe_cache_mib'] == 62464


def test_measured_reference_does_not_extrapolate(tmp_path):
    options = dict(baseline_log=str(MIXED_DEFAULT), prompt_tokens=[511, 1000])
    out = planned(tmp_path, measured_reference=MEASURED_PAIR, **options)
    assert out['done'], out['not_done_because']
    doc = out['plan']
    assert doc['ubatch'] == 1024 and doc['tried'][0]['estimate_method'] == 'linear'
    assert doc['estimate_mib'] == planned(tmp_path, **options)['plan']['estimate_mib']


@pytest.mark.parametrize('source, old, new, message', [
    ('fresh', 'n_ctx                 = 4096', 'n_ctx                 = 8192', 'layout or target context'),
    ('fresh', 'K (f16)', 'K (q8_0)', 'layout or target context'),
    ('fresh', '1538.51 MiB', '8386.51 MiB', 'model, KV or compute MiB'),
    ('candidate', '(9048bad8d)', '(56afc3581)', 'same identifiable build'),
    ('candidate', 'sched_reserve: graph', 'missing graph', 'complete layout metadata'),
])
def test_incompatible_reference_fails_the_plan(tmp_path, source, old, new, message):
    baseline, pair = MIXED_DEFAULT.read_text(), dict(MEASURED_PAIR)
    if source == 'fresh':
        assert old in baseline
        baseline = baseline.replace(old, new)
    else:
        candidate = Path(pair['candidate_log']).read_text()
        assert old in candidate
        pair['candidate_log'] = candidate.replace(old, new)
    out = planned(tmp_path, baseline_log=baseline, measured_reference=pair)
    assert not out['done'] and message in out['not_done_because'][0]
    assert not (tmp_path / 'plan.json').exists()


def test_fill_verify_checks_the_server_cache(tmp_path):
    planned(tmp_path, fill_moe_cache_headroom_mib=2048)
    # the probe log was loaded at 61440 MiB, not the filled size: the cache was not applied
    out = call('verify', plan=str(tmp_path / 'plan.json'), server_log=str(FIX / 'Bub.server.log'), device_budget_mib=110000,
               baseline_rows=ROWS['baseline'], candidate_rows=ROWS['candidate'], fill_moe_cache_headroom_mib=2048)
    status = {c['name']: c['status'] for c in out['checks']}
    assert not out['done'] and status['moe_cache_applied'] == 'fail' and status['budget_filled'] == 'fail'
    # The linear compute estimate leaves the measured load about 5 GiB under the budget; re-planned from the
    # probe's own log (compute measured at the planned batch) the fill is exact, and a load that applied it passes.
    planned(tmp_path, baseline_log=str(FIX / 'Bub.server.log'), fill_moe_cache_headroom_mib=2048)
    plan = json.loads((tmp_path / 'plan.json').read_text())
    log = (FIX / 'Bub.server.log').read_text().replace('MoE cache size = 61425.00 MiB',
                                                       f"MoE cache size = {plan['moe_cache_mib'] - 15}.00 MiB")
    out = call('verify', plan=plan, server_log=log, device_budget_mib=110000, baseline_rows=ROWS['baseline'],
               candidate_rows=ROWS['candidate'], fill_moe_cache_headroom_mib=2048)
    assert out['done'], out['not_done_because']
    # a plan without a cache size fails when the node asks for a filled budget
    planned(tmp_path)
    out = call('verify', plan=str(tmp_path / 'plan.json'), server_log=str(FIX / 'Bub.server.log'), device_budget_mib=110000,
               baseline_rows=ROWS['baseline'], candidate_rows=ROWS['candidate'], fill_moe_cache_headroom_mib=2048)
    assert not out['done'] and {c['name']: c['status'] for c in out['checks']}['budget_filled'] == 'fail'
