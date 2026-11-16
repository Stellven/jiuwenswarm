"""Additive bounded configuration screens; historical benchmark policies stay frozen."""
from __future__ import annotations
import copy
import math
import random
import re

ADAPTER = 'strata-benchmark-v3'
CHANGES = {
    'aa': None,
    'cpu4': ('args', '--cpu-threads', '4'),
    'cpu6': ('args', '--cpu-threads', '6'),
    'engram1': ('environment', 'DS4_ENGRAM_THREADS', '1'),
    'engram4': ('environment', 'DS4_ENGRAM_THREADS', '4'),
    'cache256': ('environment', 'DS4_ENGRAM_CACHE_MB', '256'),
    'cache0': ('environment', 'DS4_ENGRAM_CACHE_MB', '0'),
    'ahead1': ('environment', 'DS4_AHEAD', '1'),
    'draft': ('args', '--dspark', 'on'),
}


def validate_contract(c):
    from .benchmark import _validate_v1_contract, EXECUTION_FILES
    if c.get('adapter') != ADAPTER or c.get('version') != 3:
        raise ValueError('Unsupported broad adapter')
    if c['arms']['A']['environment'] != {'DS4_AHEAD':'0','DS4_ASYNC_T':'4','DS4_COPY_ALL':'0',
            'DS4_ENGRAM_CACHE_MB':'64','DS4_ENGRAM_THREADS':'2','DS4_STORE_GB':'0',
            'DS4_UMA_HEADROOM_GIB':'16','STRATA_DS4_REUSE':'0'}:
        raise ValueError('Broad baseline environment changed')
    if c.get('phases', ['quality','speed']) != ['quality','speed']:
        raise ValueError('Both quality and speed phases required')
    name = c.get('configuration_change')
    if name not in CHANGES or c.get('campaign_stage') not in ('aa', 'screen', 'confirm'):
        raise ValueError('Unadmitted broad treatment/stage')
    if (c['campaign_stage'] == 'aa') != (name == 'aa'):
        raise ValueError('A/A treatment requires A/A stage')
    if c.get('runtime_bounds') != {'fresh_process_cells': len(c['order']), 'phase_containers': 2*len(c['order']), 'observer_interval_ms': 1000}:
        raise ValueError('Declared runtime counters/observer bound differ')
    if c['campaign_timeout_s'] != (2700 if c['campaign_stage'] == 'confirm' else 1200):
        raise ValueError('Broad stage timeout changed')
    count = 8 if c['campaign_stage'] != 'confirm' else 64
    if c.get('quality_case_indices') != list(range(count)) or c.get('speed_case_indices') != list(range(4)):
        raise ValueError('Frozen quality subset and fixed pg512/tg128 speed cases required')
    order = list('ABBA') if c['campaign_stage'] == 'confirm' else list('AB')
    if c.get('order') != order or c.get('stage') != 'main':
        raise ValueError('Predeclared broad order differs')
    if c.get('primary_metric') != 'prefill_plus_decode_output_tokens_per_second':
        raise ValueError('Broad primary metric must include native prefill and decode')
    if any(not re.fullmatch('[a-f0-9]{64}', v) for v in c['execution_sha256'].values()):
        raise ValueError('Invalid execution identity')
    if set(c['execution_sha256']) != set(EXECUTION_FILES) | {'broad_benchmark.py'}:
        raise ValueError('Complete broad execution identity required')
    expected = copy.deepcopy(c['arms']['A'])
    change = CHANGES[name]
    if change:
        section, key, value = change
        if section == 'args': expected['args'][expected['args'].index(key)+1] = value
        else: expected[section][key] = value
    if expected != c['arms']['B']:
        raise ValueError('Exactly the admitted single configuration variable may differ')
    shaped = copy.deepcopy(c)
    shaped.update(adapter='strata-benchmark-v1', version=1, order=list('ABBAABBA'))
    shaped['execution_sha256'] = {k: c['execution_sha256'][k] for k in EXECUTION_FILES}
    shaped['arms']['B'] = copy.deepcopy(c['arms']['A'])
    shaped['arms']['B']['args'][shaped['arms']['B']['args'].index('--dspark')+1] = 'on'
    _validate_v1_contract(shaped)
    return c


def phase_cases(c, d, phase):
    return [d['quality' if phase == 'quality' else 'speed'][i]
            for i in c['quality_case_indices' if phase == 'quality' else 'speed_case_indices']]


def engagement(c, arm, parsed, stderr):
    from .benchmark import flag
    profile = c['arms'][arm]
    threads = profile['environment']['DS4_ENGRAM_THREADS']
    cache = profile['environment']['DS4_ENGRAM_CACHE_MB']
    if not re.search(r'Engram rows read on '+threads+r' threads,.*row cache '+cache+r' MB', stderr):
        raise ValueError('Effective Engram reader/cache state missing or different')
    chunk = flag(profile['args'], '--prefill-chunk')
    if not re.search(r'prompts in chunks of '+chunk+r'\)', stderr):
        raise ValueError('Effective prefill chunk missing')
    if flag(profile['args'], '--dspark') == 'none' and any(r['offered_drafts'] or r['accepted_drafts'] for r in parsed['requests']):
        raise ValueError('Drafts unexpectedly engaged')
    parsed['configuration_engagement'] = dict(engram_threads=int(threads), engram_cache_mb=int(cache),
        cpu_threads_requested=int(flag(profile['args'], '--cpu-threads')),
        ahead_requested=profile['environment']['DS4_AHEAD'],
        limitation='CPU quota and argv verified independently; lookahead request does not establish useful guessed reads.')


def analyze(c, d, cells, decode):
    """Score actual retained cells only. Screens never qualify acceptance."""
    validate_contract(c)
    return analyze_validated(c, d, cells, decode)


def analyze_validated(c, d, cells, decode):
    """Shared numerical evaluation after an adapter has validated its own policy."""
    from .benchmark_analysis import _percentile
    if [x['arm'] for x in cells] != c['order']:
        raise ValueError('Missing or reordered broad cells')
    cases = phase_cases(c, d, 'quality')
    answers = {'A': [], 'B': []}
    speeds = []
    raw = []
    for cell in cells:
        quality, speed = cell['quality'], cell['speed']
        if quality['cases'] != cases or speed['cases'] != phase_cases(c, d, 'speed'):
            raise ValueError('Scored cases differ')
        scores = []
        for case, row in zip(cases, quality['requests'], strict=True):
            answer = decode(row['ids'], case['allowed_letters'])['answer']
            scores.append((answer in case['allowed_letters'], answer == case['expected_letter']))
        answers[cell['arm']].append(scores)
        requests = speed['requests']
        if len(requests) != 4 or any(r['generated_tokens'] != 128 or len(r['ids']) != 128 or 1 in r['ids'] for r in requests):
            raise ValueError('Incomplete fixed speed workload')
        measured = requests[1:]
        if any(not math.isfinite(r['prefill_ms']+r['decode_ms']) or min(r['prefill_ms'],r['decode_ms']) <= 0 for r in measured):
            raise ValueError('Invalid native timing')
        rate = 384000/sum(r['prefill_ms']+r['decode_ms'] for r in measured)
        speeds.append(dict(index=cell['index'], arm=cell['arm'], tokens_per_second=rate,
            decode_tokens_per_second=384000/sum(r['decode_ms'] for r in measured),
            prefill_plus_decode_ms=sum(r['prefill_ms']+r['decode_ms'] for r in measured)))
        raw.append([{'ids':r['ids'],'finish':r['finish']} for r in quality['requests']+requests])
    repeats = len(answers['A'])
    accuracy = {a:sum(s[1] for run in answers[a] for s in run)/(repeats*len(cases)) for a in answers}
    all_valid = all(s[0] for runs in answers.values() for run in runs for s in run)
    regression = [cases[i]['id'] for i in range(len(cases)) if sum(r[i][1] for r in answers['B']) < sum(r[i][1] for r in answers['A'])]
    ratios = [next(s['tokens_per_second'] for s in speeds[i:i+2] if s['arm']=='B') / next(s['tokens_per_second'] for s in speeds[i:i+2] if s['arm']=='A') for i in range(0,len(speeds),2)]
    point = math.exp(sum(map(math.log,ratios))/len(ratios))
    drafting_engaged = c['configuration_change'] != 'draft' or all(
        r['offered_drafts'] > 0 and r['accepted_drafts'] > 0
        for cell in cells if cell['arm']=='B' for r in cell['speed']['requests'][1:])
    quality_pass = all_valid and accuracy['A'] >= .5 and not regression and accuracy['B'] >= accuracy['A']
    equal = all(raw[i] == raw[i+1] for i in range(0,len(raw),2))
    report = dict(schema_version=3, scope='sampled_public_quality_plus_fixed_native_throughput',
        campaign_stage=c['campaign_stage'], configuration_change=c['configuration_change'], promotion_authorized=False,
        verdict='screen_candidate' if quality_pass and point>=1.05 else 'screen_no_improvement',
        quality=dict(case_count=len(cases), accuracy=accuracy, regression_question_ids=regression, all_answers_valid=all_valid),
        gates=dict(baseline_accuracy_valid=accuracy['A']>=.5, sampled_no_per_question_regression=quality_pass, candidate_mechanism_engaged=drafting_engaged),
        speed=dict(cells=speeds, geometric_mean_ratio_B_over_A=point, pairs=ratios,
            primary_metric=c['primary_metric'],warmup_requests_discarded_per_cell=1),
        raw_token_equal=equal, performance_acceptance_evaluated=False,
        limitations=['Eight-question screens are exploratory, not full quality validation.',
            'First after initialization is not cold storage. Startup/tokenization excluded.',
            'Single pair screens have no independent confidence interval; all failed/null episodes retained.'])
    if not quality_pass: report['verdict']='rejectQuality'
    if c['campaign_stage']=='aa':
        report['verdict']='aa_valid' if quality_pass and equal else 'aa_invalid'
        report['gates']['exact_aa_tokens_and_finish']=equal
        report['speed']['aa_speed_ratio_B_over_A']=point
        report['gates']['aa_timing_stable']=max(point,1/point)<=1.10
        report['limitations'].append('aa_valid establishes token/finish repeatability only; independent timing stability is required for acceptance.')
    elif c['campaign_stage']=='confirm':
        logs=list(map(math.log,ratios));rng=random.Random(42)
        boots=[math.exp(sum(rng.choice(logs) for _ in logs)/len(logs)) for _ in range(20000)]
        lower,upper=_percentile(boots,.025),_percentile(boots,.975)
        all_pairs_pass=all(r>=1.05 for r in ratios)
        separated=min(x['tokens_per_second'] for x in speeds if x['arm']=='B') > max(x['tokens_per_second'] for x in speeds if x['arm']=='A')
        passed=point>=1.05 and lower>1 and all_pairs_pass and separated
        report['gates'].update(all_paired_speedups_at_least_1_05=all_pairs_pass,all_candidate_rates_exceed_all_baseline_rates=separated)
        report['limitations'].append('Two independent pairs are exploratory; the percentile bootstrap is descriptive and does not establish reliable 95% confidence.')
        report['speed']['bootstrap']=dict(lower=lower,upper=upper,confidence=.95,independent_pairs=len(logs),resamples=20000,seed=42,interpretation='descriptive_exploratory_not_reliable_95_percent_confidence')
        report['performance_acceptance_evaluated']=True
        report['gates']['speed_improvement']=passed
        report['verdict']='accept' if quality_pass and passed else ('rejectQuality' if not quality_pass else 'speedNoImprovement')
    if not drafting_engaged:
        report['verdict']='inconclusive'
    return report
