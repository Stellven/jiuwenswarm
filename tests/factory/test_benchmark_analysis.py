"""Synthetic tests exercise the frozen statistics without a GPU or model."""
import copy

import pytest

from jiuwenswarm.factory.benchmark_analysis import analyze


def fixture(stage='main', ratio=1.2):
    contract = dict(stage=stage, order=list('ABBAABBA' if stage == 'main' else 'AB'),
        gates=dict(minimum_accuracy=.5, minimum_speedup=1.05, confidence=.95,
            bootstrap_resamples=20000, seed=42, correctness='no_per_question_regression'))
    quality = [dict(id=f'q{i}', allowed_letters=['A', 'B', 'C', 'D'], expected_letter='A')
               for i in range(64)]
    pilot = [dict(id=f'train{i}', allowed_letters=['A', 'B', 'C', 'D'], expected_letter='A') for i in range(2)]
    speed = [dict(id=f's{i}', phase='warmup' if i == 0 else 'measured') for i in range(4)]
    dataset = dict(quality=quality, pilot=pilot, speed=speed)
    cells = []
    for index, arm in enumerate(contract['order']):
        requests = [dict(ids=[42] * 128, generated_tokens=128, prefill_ms=1000, prompt_tokens=512,
            decode_ms=(12800 if i else 25600) / (ratio if arm == 'B' else 1),
            offered_drafts=64 if arm == 'B' else 0, accepted_drafts=32 if arm == 'B' else 0)
            for i in range(4 if stage == 'main' else 2)]
        cases = quality if stage == 'main' else pilot
        cells.append(dict(index=index, arm=arm,
            quality=dict(cases=copy.deepcopy(cases), requests=[dict(ids=[10]) for _ in cases]),
            speed=dict(cases=copy.deepcopy(speed[:len(requests)]), requests=requests)))
    return contract, dataset, cells


def decode(ids, allowed_letters):
    answer = {10:'A', 11:'B', 12:'C'}.get(ids[0])
    return dict(text=answer or 'explanation', answer=answer)


def run(*args):
    return analyze(*args, decode)


def test_improvement_passes_frozen_quality_and_speed_without_mutation():
    args = fixture(); before = copy.deepcopy(args)
    report = run(*args)
    assert args == before
    assert report['verdict'] == 'accept'
    assert report['promotion_authorized'] is False
    assert report['quality']['accuracy'] == {'A':1, 'B':1}
    assert len(report['quality']['per_question']) == 64
    assert all(row['A_correct'] == row['B_correct'] == 4 for row in report['quality']['per_question'])
    assert report['speed']['geometric_mean_ratio_B_over_A'] == pytest.approx(1.2)
    assert report['speed']['bootstrap']['lower'] == pytest.approx(1.2)
    assert report['speed']['bootstrap']['independent_pairs'] == 4
    assert all(row['measured_tokens'] == 384 for row in report['speed']['cells'])
    assert report['speed']['cells'][0]['tokens_per_second'] == 10
    assert report['speed']['cells'][0]['first_request_tokens_per_second'] == 5
    assert any('not population noninferiority' in line for line in report['limitations'])


def test_per_question_regression_rejected_even_when_overall_accuracy_improves():
    contract, dataset, cells = fixture()
    for cell in cells:
        if cell['arm'] == 'A':
            for i in range(1, 20):cell['quality']['requests'][i]['ids'] = [11]
        else:cell['quality']['requests'][0]['ids'] = [11]
    report = run(contract, dataset, cells)
    assert report['quality']['accuracy']['B'] > report['quality']['accuracy']['A']
    assert report['quality']['regression_question_ids'] == ['q0']
    assert report['verdict'] == 'rejectQuality'


def test_candidate_invalid_answer_rejects_quality_baseline_invalid_is_inconclusive():
    for arm, verdict in [('A', 'inconclusive'), ('B', 'rejectQuality')]:
        args = fixture()
        next(cell for cell in args[2] if cell['arm'] == arm)['quality']['requests'][0]['ids'] = [99]
        assert run(*args)['verdict'] == verdict


def test_baseline_floor_cannot_be_hidden_by_candidate_improvement():
    args = fixture()
    for cell in args[2]:
        if cell['arm'] == 'A':
            for i in range(33):cell['quality']['requests'][i]['ids'] = [11]
    assert run(*args)['verdict'] == 'inconclusive'


@pytest.mark.parametrize('ratio', [1, 1.049, .9])
def test_insufficient_point_speed_improvement(ratio):
    assert run(*fixture(ratio=ratio))['verdict'] == 'speedNoImprovement'


def test_pair_bootstrap_not_pseudoreplication_and_deterministic():
    args = fixture()
    # Two fast and two slow fresh pairs: good geometric point, uncertain lower bound.
    for pair_index, ratio in enumerate([.8, .8, 2, 2]):
        for cell in args[2][pair_index * 2:pair_index * 2 + 2]:
            if cell['arm'] == 'B':
                for request in cell['speed']['requests']:request['decode_ms'] = 12800 / ratio
    first, second = run(*args), run(*args)
    assert first == second
    assert first['speed']['geometric_mean_ratio_B_over_A'] > 1.05
    assert first['speed']['bootstrap']['lower'] < 1
    assert first['verdict'] == 'speedNoImprovement'
    assert len(first['speed']['pairs']) == 4


def test_pooled_native_time_not_average_of_request_rates():
    args = fixture()
    for cell in args[2]:
        for request, duration in zip(cell['speed']['requests'][1:], [1000, 2000, 9000]):
            request['decode_ms'] = duration / (1.2 if cell['arm'] == 'B' else 1)
    report = run(*args)
    assert report['speed']['cells'][0]['tokens_per_second'] == 32
    assert report['speed']['cells'][0]['measured_request_tokens_per_second'] == pytest.approx([128,64,128/9])


def test_warmup_draft_engagement_not_required_measured_every_cell_required():
    args = fixture()
    for cell in args[2]:
        if cell['arm'] == 'B':
            cell['speed']['requests'][0].update(offered_drafts=0, accepted_drafts=0)
    assert run(*args)['verdict'] == 'accept'
    args[2][2]['speed']['requests'][2]['accepted_drafts'] = 0
    assert run(*args)['verdict'] == 'inconclusive'


@pytest.mark.parametrize('mutation', [
    lambda a: a[2].pop(),
    lambda a: a[2][0].update(arm='B'),
    lambda a: a[2][1].update(index=0),
    lambda a: a[2][0]['quality']['requests'].pop(),
    lambda a: a[2][0]['quality']['cases'][0].update(id='changed'),
    lambda a: a[2][0]['speed']['requests'][1].update(generated_tokens=127),
    lambda a: a[2][0]['speed']['requests'][1]['ids'].__setitem__(0,1),
    lambda a: a[2][0]['speed']['requests'][1].update(decode_ms=float('nan')),
    lambda a: a[2][0]['speed']['requests'][1].update(decode_ms=0),
    lambda a: a[2][0]['speed']['requests'][1].update(offered_drafts=1,accepted_drafts=2),
    lambda a: a[0]['gates'].update(minimum_speedup=1.0),
])
def test_bad_evidence_or_contract_is_inconclusive(mutation):
    args = fixture(); mutation(args)
    report = run(*args)
    assert report['verdict'] == 'inconclusive'
    assert report['errors']


def test_pilot_is_operational_only_not_a_performance_or_correctness_pass():
    args = fixture(stage='pilot', ratio=.5)
    # Valid but wrong answers are visible without asserting a main quality pass.
    for cell in args[2]:
        for request in cell['quality']['requests']:request['ids'] = [11]
    report = run(*args)
    assert report['verdict'] == 'pilot_ok'
    assert report['performance_acceptance_evaluated'] is False
    assert report['quality']['accuracy'] == {'A':0, 'B':0}
    assert 'bootstrap' not in report['speed']
    assert 'speed_improvement' not in report['gates']


def test_raw_token_inequality_is_only_descriptive():
    args = fixture()
    for cell in args[2]:
        if cell['arm'] == 'B':
            for request in cell['quality']['requests']:request['ids'] = [10, 1]
            for request in cell['speed']['requests']:request['ids'] = [43] * 128
    report = run(*args)
    assert report['verdict'] == 'accept'
    assert all(pair['quality_equal'] == pair['speed_equal'] == 0 for pair in report['raw_token_comparison']['adjacent_pairs'])


def test_decode_gain_does_not_imply_end_to_end_gain():
    args=fixture()
    for cell in args[2]:
        if cell['arm']=='B':
            for request in cell['speed']['requests']: request['prefill_ms']=100000
    report=run(*args)
    assert report['verdict']=='accept'
    assert report['speed']['acceptance_scope']=='warm_native_decode_only'
    assert report['speed']['geometric_mean_ratio_B_over_A']>1
    assert report['speed']['secondary_prefill_plus_decode_ratio_B_over_A']<1
    assert report['promotion_authorized'] is False

@pytest.mark.parametrize('key,value',[('prefill_ms',0),('prefill_ms',float('nan')),('prompt_tokens',511)])
def test_missing_or_wrong_prefill_cannot_be_hidden(key,value):
    args=fixture();args[2][0]['speed']['requests'][1][key]=value
    assert run(*args)['verdict']=='inconclusive'
