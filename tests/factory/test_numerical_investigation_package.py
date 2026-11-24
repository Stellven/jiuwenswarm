"""Independent CPU oracles, including the actual native CC Host transport."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest
from jiuwenswarm.ccv2.ccv2 import Host

PACKAGE = Path('jiuwenswarm/factory/ccs/numerical_investigation_lab').resolve()
module_spec = importlib.util.spec_from_file_location('numerical_components', PACKAGE / 'components.py')
c = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(c)


def fixture():
    identity = dict(model='checkpoint:abc', tokenizer='tokenizer:abc', source='source:abc',
                    precision='fp32', routing='routing:abc', profile='profile:256')
    candidate = {**identity, 'profile': 'profile:1024'}
    return dict(baseline_identity=identity, candidate_identity=candidate, prompt_ids=[0, 1],
                teacher_ids=[2, 1], step=1, vocabulary_size=3, treatment_fields=['profile'],
                comparison_policy=dict(declaration_id='frozen-before-capture:fixture',
                                       absolute_tolerance=0.01, relative_tolerance=0.0, top_k=2))


def vectors(spec):
    def item(arm, logits):
        return dict(identity=spec[arm+'_identity'], spec_sha256=c.digest(spec), history_ids=[0, 1, 2],
                    step=1, vocabulary_ids=[0, 1, 2], logits=logits, complete=True, capture_id=arm+':fixture')
    return item('baseline', [1., 3., 2.]), item('candidate', [1., 2., 3.])


@pytest.fixture
def native(tmp_path):
    host = Host(tmp_path/'host', session_grants=['process.exec'], python=sys.executable)
    return host, host.prepare(PACKAGE)


def call(native, capability, inputs):
    host, release = native
    receipt = host.call(release, capability, inputs, key=capability)
    assert receipt['state'] == 'succeeded', receipt
    return receipt['outputs']['result']


def test_native_full_vector_known_permutation_and_replay(native):
    frozen = call(native, 'replay_spec', fixture())
    assert frozen['execution'] == 'not_executed'
    assert frozen['spec']['history_ids'] == [0, 1, 2]
    spec = frozen['spec']
    a, b = vectors(spec)
    b['vocabulary_ids'], b['logits'] = [2, 0, 1], [3., 1., 2.]
    result = call(native, 'compare_logits', dict(spec=spec, baseline=a, candidate=b))
    assert result['maximum_absolute_difference'] == 1
    assert result['observed_violations'] == 2
    assert result['baseline']['top'] == [{'token_id': 1, 'logit': 3.}, {'token_id': 2, 'logit': 2.}]
    assert result['candidate']['top'][0]['token_id'] == 2
    assert result['baseline']['margin'] == result['candidate']['margin'] == 1
    assert result['same_top_choice'] is False
    assert result['within_tolerance'] is False


def test_native_first_divergence_and_finish(native):
    out = call(native, 'first_divergence', dict(baseline_ids=[7]*49+[10367],
         candidate_ids=[7]*49+[32187], baseline_finish='length', candidate_finish='length'))
    assert out['first_different_index'] == out['common_prefix_tokens'] == 49
    assert (out['baseline_token'], out['candidate_token']) == (10367, 32187)


@pytest.mark.parametrize('field,value', [('history_ids', [0, 1, 1]), ('step', 2),
    ('spec_sha256', 'wrong'), ('vocabulary_ids', [0, 0, 2]), ('vocabulary_ids', [0, 1, 3]),
    ('logits', [1, float('nan'), 2]), ('logits', [1, float('inf'), 2]),
    ('logits', [1]), ('complete', 1)])
def test_reject_capture_mismatch(field, value):
    spec = c.replay_spec(**fixture())['spec']
    a, b = vectors(spec)
    b[field] = value
    with pytest.raises(ValueError):
        c.compare_logits(spec, a, b)


@pytest.mark.parametrize('field', sorted(c.IDENTITY))
def test_each_identity_mismatch_rejected(field):
    spec = c.replay_spec(**fixture())['spec']
    a, b = vectors(spec)
    b['identity'] = {**b['identity'], field: 'unfrozen'}
    with pytest.raises(ValueError):
        c.compare_logits(spec, a, b)


def test_treatment_and_policy_fail_closed():
    for field in ('model', 'tokenizer', 'precision', 'routing', 'source'):
        inputs = fixture()
        inputs['candidate_identity'][field] = 'other'
        with pytest.raises(ValueError):
            c.replay_spec(**inputs)
    for tolerance in (-0.1, 2., float('nan'), True):
        inputs = fixture()
        inputs['comparison_policy']['absolute_tolerance'] = tolerance
        with pytest.raises(ValueError):
            c.replay_spec(**inputs)


def test_unknown_for_partial_and_exact_tie_and_absolute_relative_boundary():
    spec = c.replay_spec(**fixture())['spec']
    a, b = vectors(spec)
    for item in (a, b):
        item.update(vocabulary_ids=[0], logits=[1.], complete=False)
    r = c.compare_logits(spec, a, b)
    assert r['same_top_choice'] == r['within_tolerance'] == r['exact_vectors'] == 'unknown'
    for item in (a, b):
        item.update(vocabulary_ids=[0, 1, 2], logits=[1., 1., 0.], complete=True)
    r = c.compare_logits(spec, a, b)
    assert r['exact_vectors'] and r['baseline']['tied_top']
    assert r['baseline']['margin'] == 0
    assert r['baseline']['top'][0]['token_id'] == 0
    spec['comparison_policy'].update(absolute_tolerance=0.125, relative_tolerance=0.125)
    a, b = vectors(spec)
    a['logits'], b['logits'] = [1., 0., -1.], [1.25, 0.125, -1.25]
    assert c.compare_logits(spec, a, b)['within_tolerance'] is True


def test_length_finish_and_bounds():
    r = c.first_divergence([1, 2], [1], 'length', 'eos')
    assert r['first_different_index'] == 1 and r['candidate_token'] is None
    r = c.first_divergence([1], [1], 'length', 'eos')
    assert r['first_different_index'] is None and not r['exact_output']
    for value in ([True], [-1], [c.MAX_VOCAB], [0]*(c.MAX_STEPS+1)):
        with pytest.raises(ValueError):
            c.first_divergence(value, [], 'length', 'length')


def test_actual_host_rejects_bad_capture_and_missing_grant(native, tmp_path):
    spec = c.replay_spec(**fixture())['spec']
    a, b = vectors(spec)
    b['history_ids'] = [1]
    host, release = native
    r = host.call(release, 'compare_logits', dict(spec=spec, baseline=a, candidate=b), key='bad')
    assert r['state'] != 'succeeded'
    denied = Host(tmp_path/'denied', session_grants=[], python=sys.executable)
    release = denied.prepare(PACKAGE)
    assert denied.call(release, 'replay_spec', fixture(), key='deny')['state'] != 'succeeded'


@pytest.mark.parametrize('raw', ['{"capability":"first_divergence","capability":"replay_spec","inputs":{}}',
    '{"capability":"first_divergence","inputs":{"baseline_ids":[NaN]}}',
    '{"capability":"unknown","inputs":{}}'])
def test_native_json_rejects_ambiguity(raw):
    result = subprocess.run([sys.executable, str(PACKAGE/'run.py')], input=raw, text=True, capture_output=True, check=True)
    assert json.loads(result.stdout)['outcome'] == 'error'


def test_actual_host_capture_plan_and_import(native, tmp_path):
    import struct
    profile = dict(args=['--pack', '/pack', '--experts', '6', '--mmap-experts', 'on',
        '--cpu-threads', '8', '--reserve-mib', '16384', '--vram-experts', '1.0',
        '--dspark', 'none', '--dspark-conf', '0.65', '--no-expert-cache', '--prefill-chunk', '256'],
        environment={'STRATA_DS4_REUSE': '0', 'DS4_UMA_HEADROOM_GIB': '16', 'DS4_COPY_ALL': '0', 'DS4_STORE_GB': '0'},
        image='sha256:'+'a'*64)
    identity = dict(model='model-sha', tokenizer='tokenizer-sha', source='source-sha', precision='f32', routing='six', profile=c.digest(profile))
    spec = c.replay_spec(identity, identity, [0, 1], [1]*49, 49, 3, [],
        dict(declaration_id='fixture-only', absolute_tolerance=0, relative_tolerance=0, top_k=2))['spec']
    plan = call(native, 'capture_plan', dict(profile=profile, spec=spec, arm='baseline', dump_prefix='/tmp/fixture-only/logits'))
    assert plan['executed'] is False
    assert plan['profile']['environment']['DS4_SERVE_DUMP'] == '/tmp/fixture-only/logits'
    (tmp_path/'wire').write_text(plan['request']+'\nQUIT\n')
    (tmp_path/'out').write_text('T 1\n'*50+'DONE 50 2 1.0 2.0 length 0 0 0 0 0\n')
    (tmp_path/'logits').write_bytes(struct.pack('<fff', 1., 2., 3.)*50)
    imported = call(native, 'import_capture', dict(spec=spec, arm='baseline', evidence_root=str(tmp_path),
        dump_path='logits', transcript_path='out', stdin_path='wire', profile=profile,
        source_main_sha256=plan['source_main_sha256']))
    assert imported['capture']['logits'] == [1., 2., 3.]
    assert imported['capture']['history_ids'] == [0, 1]+[1]*49
    assert imported['provenance']['identity_authenticated'] is False
