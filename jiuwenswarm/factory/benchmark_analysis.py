"""Frozen, read-only analysis of verified Strata benchmark cells.

The runner verifies runtime provenance/CUDA/full-six-expert execution before calling
this module. These statistics never authorize promotion or mutate a contract.
"""
import hashlib
import json
import math
import random


LIMITATIONS = [
    'This is a sampled regression gate, not population noninferiority or an official ARC score.',
    'Four fresh process pairs form a small-N pilot; the bootstrap interval may understate uncertainty.',
    'First-request timings describe process warmup; they do not establish a cold storage cache.',
    'Raw generated-token equality is descriptive; this new public quality contract does not relax any old byte-golden contract.',
]


def _percentile(values, probability):
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[min(lower + 1, len(ordered) - 1)] * fraction


def _positive(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0


def _tokens(request):
    ids = request.get('ids')
    if not isinstance(ids, list) or any(type(token) is not int or token < 0 for token in ids):
        raise ValueError('request ids must be a list of nonnegative integers')
    return ids


def _hash(ids):
    return hashlib.sha256(json.dumps(ids, separators=(',', ':')).encode()).hexdigest()


def analyze(contract, dataset, cells, decode_answer):
    """Analyze immutable verified cell payloads using a strict answer decoder.

    ``decode_answer(ids, allowed_letters)`` returns ``{text, answer}``; an answer
    outside a case's allowed letters is invalid. Structural errors are reported
    as inconclusive rather than converted into a speed or correctness success.
    """
    report = dict(schema_version=1, stage=contract.get('stage'), verdict='inconclusive',
                  promotion_authorized=False, limitations=list(LIMITATIONS), errors=[],
                  gates={}, quality={}, speed={})
    try:
        return _analyze(contract, dataset, cells, decode_answer, report)
    except (ValueError, TypeError, KeyError, IndexError, OverflowError) as exc:
        report['errors'].append(str(exc))
        return report


def _analyze(contract, dataset, cells, decode_answer, report):
    stage = contract['stage']
    if stage not in ('main', 'pilot'):
        raise ValueError('stage must be main or pilot')
    prefill_trial = contract.get('adapter') == 'strata-benchmark-v2'
    if prefill_trial and (contract.get('version') != 2 or contract.get('primary_metric') != 'prefill_plus_decode_output_tokens_per_second'):
        raise ValueError('v2 requires its frozen prefill plus decode primary metric')
    main = stage == 'main'
    expected_order = list('ABBAABBA' if main else 'AB')
    if contract['order'] != expected_order:
        raise ValueError('contract order must match the frozen stage order')
    gates = contract['gates']
    frozen = dict(minimum_accuracy=0.5, minimum_speedup=1.05, confidence=0.95,
                  bootstrap_resamples=20000, seed=42, correctness='no_per_question_regression')
    if any(gates.get(key) != value for key, value in frozen.items()):
        raise ValueError('analysis requires the frozen benchmark gates')
    cases = dataset['quality' if main else 'pilot']
    if len(cases) != (64 if main else 2) or len({case['id'] for case in cases}) != len(cases):
        raise ValueError('quality cases must have the frozen count and unique IDs')
    if len(cells) != len(expected_order) or [cell['arm'] for cell in cells] != expected_order:
        raise ValueError('cells must match the complete frozen arm order')
    if len({cell['index'] for cell in cells}) != len(cells):
        raise ValueError('cell indices must be unique')
    quality_cells = []
    speed_cells = []
    answers = {'A': [], 'B': []}
    invalid = {'A': 0, 'B': 0}
    expected_speed = dataset['speed'][:4 if main else 2]
    if len(expected_speed) != (4 if main else 2):
        raise ValueError('speed cases must include the required warmup and measured requests')
    for cell in cells:
        arm = cell['arm']
        quality = cell['quality']
        if quality['cases'] != cases or len(quality['requests']) != len(cases):
            raise ValueError('quality requests/cases differ from the frozen dataset')
        cell_answers = []
        hashes = []
        for case, request in zip(cases, quality['requests']):
            allowed = case['allowed_letters']
            if case['expected_letter'] not in allowed:
                raise ValueError('ground truth outside allowed letters')
            ids = _tokens(request)
            decoded = decode_answer(list(ids), allowed)
            answer = decoded['answer']
            valid = isinstance(answer, str) and answer in allowed
            invalid[arm] += not valid
            cell_answers.append(dict(id=case['id'], answer=answer, valid=valid,
                correct=valid and answer == case['expected_letter'], text=decoded['text']))
            hashes.append(_hash(ids))
        answers[arm].append(cell_answers)
        quality_cells.append(dict(index=cell['index'], arm=arm,
            correct=sum(answer['correct'] for answer in cell_answers), total=len(cases),
            invalid=sum(not answer['valid'] for answer in cell_answers), raw_token_sha256=hashes))
        speed = cell['speed']
        requests = speed['requests']
        if speed['cases'] != expected_speed or len(requests) != len(expected_speed):
            raise ValueError('speed requests/cases differ from the frozen dataset')
        request_rates = []
        for request in requests:
            ids = _tokens(request)
            if request.get('generated_tokens') != 128 or len(ids) != 128 or 1 in ids:
                raise ValueError('speed requests must generate 128 tokens without EOS')
            if not _positive(request.get('decode_ms')):
                raise ValueError('decode_ms must be finite and positive')
            if not _positive(request.get('prefill_ms')) or request.get('prompt_tokens') != 512:
                raise ValueError('speed prefill must have positive time and exactly 512 prompt tokens')
            offered, accepted = request.get('offered_drafts'), request.get('accepted_drafts')
            if type(offered) is not int or type(accepted) is not int or not 0 <= accepted <= offered:
                raise ValueError('draft counts must be integers satisfying 0 <= accepted <= offered')
            if prefill_trial and (offered != 0 or accepted != 0):
                raise ValueError('Drafts must remain disabled in v2')
            request_rates.append(128000 / (request['decode_ms'] + (request['prefill_ms'] if prefill_trial else 0)))
        measured = requests[1:]
        engaged = all(request['offered_drafts'] > 0 and request['accepted_drafts'] > 0 for request in measured)
        rate = sum(request['generated_tokens'] for request in measured) * 1000 / sum(request['decode_ms'] + (request['prefill_ms'] if prefill_trial else 0) for request in measured)
        speed_cells.append(dict(index=cell['index'], arm=arm, tokens_per_second=rate,
            first_request_tokens_per_second=request_rates[0], measured_request_tokens_per_second=request_rates[1:],
            measured_tokens=128 * len(measured), measured_decode_ms=sum(request['decode_ms'] for request in measured),
            measured_prefill_ms=sum(request['prefill_ms'] for request in measured),
            measured_prompt_tokens=512 * len(measured),
            accepted_drafts=sum(request['accepted_drafts'] for request in measured),
            offered_drafts=sum(request['offered_drafts'] for request in measured), draft_engaged=engaged,
            raw_token_sha256=[_hash(_tokens(request)) for request in requests]))
    repeats = len(answers['A'])
    per_question = [dict(id=case['id'], expected_letter=case['expected_letter'],
        A_correct=sum(run[i]['correct'] for run in answers['A']),
        B_correct=sum(run[i]['correct'] for run in answers['B']), repeats_per_arm=repeats)
        for i, case in enumerate(cases)]
    total = repeats * len(cases)
    accuracy = {arm: sum(cell['correct'] for cell in quality_cells if cell['arm'] == arm) / total for arm in ('A', 'B')}
    regression_ids = [row['id'] for row in per_question if row['B_correct'] < row['A_correct']]
    report['quality'] = dict(metric='sampled_letter_generation_accuracy', official_arc_score=False,
        cells=quality_cells, per_question=per_question, accuracy=accuracy, invalid_answers=invalid,
        regression_question_ids=regression_ids, repeats_per_arm=repeats,
        raw_token_equality_role='descriptive_only')
    report['speed'] = dict(cells=speed_cells, primary_metric='measured_tokens / summed_native_decode_seconds',
        acceptance_scope='warm_native_decode_only',
        warmup_requests_discarded_per_cell=1, independent_unit='fresh_process_pair',
        first_request_tokens_per_second=[cell['first_request_tokens_per_second'] for cell in speed_cells],
        measured_cell_tokens_per_second=[cell['tokens_per_second'] for cell in speed_cells])
    rates = {}
    for arm in ('A','B'):
        selected = [cell for cell in speed_cells if cell['arm']==arm]
        tokens = sum(cell['measured_tokens'] for cell in selected)
        prompt = sum(cell['measured_prompt_tokens'] for cell in selected)
        decode_ms = sum(cell['measured_decode_ms'] for cell in selected)
        prefill_ms = sum(cell['measured_prefill_ms'] for cell in selected)
        rates[arm] = dict(decode_tokens_per_second=tokens*1000/decode_ms,
            prefill_tokens_per_second=prompt*1000/prefill_ms,
            prefill_plus_decode_output_tokens_per_second=tokens*1000/(prefill_ms+decode_ms))
    report['speed']['pooled_arm_rates'] = rates
    report['speed']['secondary_prefill_plus_decode_ratio_B_over_A'] = (
        rates['B']['prefill_plus_decode_output_tokens_per_second']/rates['A']['prefill_plus_decode_output_tokens_per_second'])
    report['limitations'].append('Decode acceptance is not end-to-end acceptance; inspect the separately reported prefill plus decode rate. Startup and tokenization are excluded from both native metrics.')
    if prefill_trial:
        report['speed'].update(primary_metric='measured_tokens / summed_native_prefill_plus_decode_seconds',
            acceptance_scope='warm_native_prefill_plus_decode')
        report['limitations'][-1] = 'Native prefill plus decode acceptance excludes startup, tokenization and client overhead.'
    all_valid = not any(invalid.values())
    engaged = prefill_trial or all(cell['draft_engaged'] for cell in speed_cells if cell['arm'] == 'B')
    report['raw_token_comparison'] = dict(role='descriptive_only', adjacent_pairs=[
        dict(indices=[cells[i]['index'], cells[i + 1]['index']],
             quality_equal=sum(a == b for a, b in zip(quality_cells[i]['raw_token_sha256'], quality_cells[i + 1]['raw_token_sha256'])),
             quality_total=len(cases),
             speed_equal=sum(a == b for a, b in zip(speed_cells[i]['raw_token_sha256'], speed_cells[i + 1]['raw_token_sha256'])),
             speed_total=len(expected_speed))
        for i in range(0, len(cells), 2)])
    report['gates'].update(all_answers_valid=all_valid)
    if prefill_trial:
        report['gates']['drafting_disabled_in_both_arms'] = True
    else:
        report['gates']['candidate_drafting_engaged'] = engaged
    if not main:
        report['verdict'] = 'pilot_ok' if all_valid and engaged else 'inconclusive'
        report['performance_acceptance_evaluated'] = False
        return report
    baseline_valid = invalid['A'] == 0 and accuracy['A'] >= gates['minimum_accuracy']
    quality_pass = all_valid and not regression_ids and accuracy['B'] >= accuracy['A']
    pairs = []
    for i in range(0, len(speed_cells), 2):
        pair = {cell['arm']: cell for cell in speed_cells[i:i + 2]}
        pairs.append(dict(indices=[speed_cells[i]['index'], speed_cells[i + 1]['index']],
            ratio_B_over_A=pair['B']['tokens_per_second'] / pair['A']['tokens_per_second']))
    logs = [math.log(pair['ratio_B_over_A']) for pair in pairs]
    point = math.exp(sum(logs) / len(logs))
    rng = random.Random(gates['seed'])
    bootstrap = [math.exp(sum(rng.choice(logs) for _ in logs) / len(logs))
                 for _ in range(gates['bootstrap_resamples'])]
    tail = (1 - gates['confidence']) / 2
    lower, upper = _percentile(bootstrap, tail), _percentile(bootstrap, 1 - tail)
    speed_pass = point >= gates['minimum_speedup'] and lower > 1.0
    report['speed'].update(pairs=pairs, geometric_mean_ratio_B_over_A=point,
        bootstrap=dict(method='percentile_paired_geometric_mean', confidence=gates['confidence'],
            lower=lower, upper=upper, resamples=gates['bootstrap_resamples'], seed=gates['seed'], independent_pairs=len(pairs)))
    report['gates'].update(baseline_accuracy_valid=baseline_valid,
        sampled_no_per_question_regression=quality_pass, speed_improvement=speed_pass)
    report['performance_acceptance_evaluated'] = True
    if not baseline_valid or not engaged:
        report['verdict'] = 'inconclusive'
    elif not quality_pass:
        report['verdict'] = 'rejectQuality'
    elif not speed_pass:
        report['verdict'] = 'speedNoImprovement'
    else:
        report['verdict'] = 'accept'
    return report
