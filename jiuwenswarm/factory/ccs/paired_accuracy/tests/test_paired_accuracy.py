"""eval.paired_accuracy on a synthetic MMLU-shaped dataset: a clean run passes, planted faults fail."""
import copy
import csv
import json
import random
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
RUN = HERE.parent / 'run.py'
sys.path.insert(0, str(HERE.parent))
import paired  # noqa: E402


def call(capability, **inputs):
    done = subprocess.run([sys.executable, str(RUN)], input=json.dumps(dict(capability=capability, inputs=inputs)),
                          capture_output=True, text=True, check=True)
    reply = json.loads(done.stdout)
    assert reply['outcome'] == 'ok'
    return reply['outputs']


@pytest.fixture(scope='module')
def dataset(tmp_path_factory):
    root = tmp_path_factory.mktemp('mmlu')
    rnd = random.Random(7)
    for subject in ('algebra_toy', 'history_toy', 'biology_toy'):
        with open(root / f'{subject}_test.csv', 'w', newline='', encoding='utf-8') as fh:
            w = csv.writer(fh)
            for i in range(200):
                w.writerow([f'{subject} question {i}?', 'one', 'two', 'three', 'four', rnd.choice('ABCD')])
    return root


def make_state(dataset, loss=0.0, flips=0.06, n=430, margin=5.0, seed=11, mass=0.9):
    """A run as the driver writes it, with arm B losing `loss` (fraction) and `flips` questions differing."""
    qs = paired.mmlu_order(dataset)
    rnd = random.Random(seed)
    rows = {'A': {}, 'B': {}}
    b_only, c_only = flips / 2 + loss / 2, flips / 2 - loss / 2
    for q in qs[:n]:
        u = rnd.random()
        ra, rb = (True, False) if u < b_only else (False, True) if u < b_only + c_only else (True, True) if u < 0.85 else (False, False)
        for arm, right in (('A', ra), ('B', rb)):
            pick = q['answer'] if right else next(L for L in 'ABCD' if L != q['answer'])
            probs = {L: (mass if L == pick else (1 - mass) / 3) for L in 'ABCD'}
            rows[arm][q['id']] = dict(prompt_sha256=paired.sha(paired.prompt(q)), probs=probs, letter_mass=mass,
                                      pick=pick, answer=q['answer'], correct=right)
    ids = [q['id'] for q in qs]
    st = dict(format='muse-paired-accuracy/1', seed=paired.SEED, looks=list(paired.LOOKS), z=paired.Z_SEQ, margin_pts=margin,
              order_sha256=paired.sha(json.dumps(ids)), rows=rows, arms={'A': dict(load_seconds=300.0), 'B': dict(load_seconds=200.0)})
    st['looks_done'] = paired.sequential(rows['A'], rows['B'], ids, margin)
    last = st['looks_done'][-1]
    st['decision'] = last['decision'] if last['decision'] != 'continue' else None
    return st


def verified(dataset, st, **overrides):
    return call('verify', **(dict(state=st, dataset_dir=str(dataset), margin_pts=5.0) | overrides))


def status(out):
    return {c['name']: c['status'] for c in out['checks']}


def test_order_is_fixed_and_reported(dataset, tmp_path):
    out = call('order', dataset_dir=str(dataset), order_out=str(tmp_path / 'order.json'))
    assert out['done'] and out['order']['count'] == 600 and out['order']['z'] == paired.Z_SEQ
    again = call('order', dataset_dir=str(dataset))
    assert again['order']['order_sha256'] == out['order']['order_sha256']
    assert len(json.loads((tmp_path / 'order.json').read_text())['ids']) == 600


def test_clean_run_passes(dataset):
    out = verified(dataset, make_state(dataset))
    assert out['done'] and out['stage_reached'] == 'runtime acceptance', out['not_done_because']
    assert out['looks'][-1]['decision'] == 'pass'


def test_peeking_at_an_unplanned_checkpoint_fails(dataset):
    st = make_state(dataset)
    st['looks_done'][-1]['n'] = 120  # claimed a stop at 120, not a planned checkpoint
    assert status(verified(dataset, st))['recomputed_checkpoints'] == 'fail'


def test_unplanned_critical_value_fails(dataset):
    st = make_state(dataset)
    st['z'] = 1.96
    out = verified(dataset, st)
    assert status(out)['planned_checkpoints'] == 'fail' and not out['done']


def test_gap_in_rows_fails(dataset):
    st = make_state(dataset)
    first = paired.mmlu_order(dataset)[3]['id']
    del st['rows']['B'][first]
    assert status(verified(dataset, st))['rows_prefix:B'] == 'fail'


def test_unpaired_prompt_fails(dataset):
    st = make_state(dataset)
    first = next(iter(st['rows']['A']))
    st['rows']['A'][first]['prompt_sha256'] = paired.sha('a five-shot prompt instead')
    assert status(verified(dataset, st))['canonical_prompts:A'] == 'fail'


def test_flipped_answer_key_fails(dataset):
    st = make_state(dataset)
    first = next(iter(st['rows']['B']))
    st['rows']['B'][first]['correct'] = not st['rows']['B'][first]['correct']
    assert status(verified(dataset, st))['answer_keys:B'] == 'fail'


def test_wrong_margin_fails(dataset):
    out = verified(dataset, make_state(dataset, margin=8.0))
    assert status(out)['margin_pinned'] == 'fail'


def test_claimed_decision_must_match(dataset):
    st = make_state(dataset)
    assert st['decision'] == 'pass'
    st['decision'] = 'fail'
    assert status(verified(dataset, st))['decision_claimed'] == 'fail'


def test_low_letter_mass_is_not_done(dataset):
    out = verified(dataset, make_state(dataset, mass=0.2))
    assert status(out)['letter_mass:A'] == 'inconclusive' and not out['done']


def test_real_loss_fails_the_gate(dataset):
    out = verified(dataset, make_state(dataset, loss=0.15, flips=0.2))
    assert out['looks'][-1]['decision'] == 'fail' and status(out)['non_inferiority'] == 'fail' and not out['done']


def test_missing_load_record_fails(dataset):
    st = make_state(dataset)
    st['arms'].pop('A')
    assert status(verified(dataset, st))['server_loads'] == 'fail'


def test_newcombe_interval_is_sane():
    diff, lo, hi = paired.newcombe_paired(70, 9, 3, 18, 1.96)
    assert lo < diff < hi and -0.05 < lo < 0.06 < hi < 0.14
    assert paired.newcombe_paired(100, 0, 0, 0, 1.96)[0] == 0
