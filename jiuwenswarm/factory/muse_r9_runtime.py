"""Recompute R9 release checks from the host measurement receipt and raw files."""

import math
from pathlib import Path
import re
from statistics import median

from jiuwenswarm.factory import capped_run
from jiuwenswarm.factory.muse_r9_measure import (
    ARM, CONTROL, FORMAT, PROMPTS, REPEATS, DEVICE_BUDGET, MMLU_FORMAT, MMLU_IDENTITY,
    accuracy_identity, digest, first_cached_tasks, mmlu_reference_summary, read, references, speed_schedule,
)
from jiuwenswarm.factory.ccs.paired_accuracy import paired
from scripts.factory import lab_v4_quiet as quiet, r8_derive_p_ttft, r9_prefix_check
from scripts.factory.r8_bench_score import REQUEST

STAGE = 'hardware measurement'
# Report raw ratios. A single uncontrolled latency observation is noisy, so the
# check uses a declared 10% tolerance and stratifies cold and warm observations.
REGRESSION_TOLERANCE = 0.10
REQUIRED_FILES = {'speed.json', 'ttft.json', 'server.log', 'load.json', 'mmlu.json', 'admission.json'}
METRICS = ('derived_ttft_ms', 'decode_tokens_per_second', 'request_total_ms')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def _raw_tasks(server_log, row):
    start, end = row['server_log_start'], row['server_log_end']
    require(type(start) is int and type(end) is int and 0 <= start < end <= len(server_log),
            'Request has no valid byte interval in the raw server log')
    return first_cached_tasks(server_log[start:end])


def _coherent(text):
    # This is a smoke of a short greedy continuation, often a Muse reasoning
    # prefix. It does not grade the answer to the document question.
    visible = re.sub(r'<\|[^|\n]+\|>', ' ', text)
    words = re.findall(r'[A-Za-z]+', visible.lower())
    return len(words) >= 6 and len(set(words)) >= 5 and '\ufffd' not in visible and '\x00' not in visible


def _eligible(row, policy):
    return (row['quiet']['status'] == 'accepted' and not row['quiet']['reasons']
            and not quiet.evidence_issues(row['quiet']['samples'], policy))


def _speed_rows(speed, ttft, raw_log, proposal, prompts):
    expected = speed_schedule()
    policy = quiet.policy(quiet.EMPTY)
    rows = speed['rows']
    require(speed['status'] == 'complete' and speed['quiet_policy'] == policy and len(rows) == len(expected),
            'Timed schedule or quiet policy is incomplete')
    require(ttft['source'] == 'speed.json' and len(ttft['rows']) == len(rows), 'TTFT sidecar is incomplete')
    indexed = {}
    standard_slots = set()
    previous_end = 0
    for index, (row, cell, clock) in enumerate(zip(rows, expected, ttft['rows'])):
        key = row['arm'], row['request'], row['state'], row['repeat'], row['role']
        require(all(row[k] == v for k, v in cell.items()) and key not in indexed, f'{key}: unexpected schedule')
        require(clock['source_pointer'] == f'/rows/{index}'
                and all(clock[k] == row[k] for k in ('arm', 'request', 'state', 'repeat', 'role',
                        'client_ttft_ms', 'direct_client_ttft_ms', 'derived_ttft_ms', 'ttft_method', 'stream_arrivals')),
                f'{key}: sidecar and raw stream disagree')
        require(row['ttft_method'] == 'client arrival of first non-empty generated content',
                f'{key}: TTFT must use the shared client clock')
        require(row['server_log_start'] >= previous_end, f'{key}: server log request interval overlaps')
        previous_end = row['server_log_end']
        tasks = _raw_tasks(raw_log, row)
        require(len(tasks) == 1 and row.get('reuse') == tasks[0] and 'end' in tasks[0],
                f'{key}: missing unique completed slot task in raw server log')
        task = tasks[0]
        require(task['slot_id'] == 0 and task['task_id'] not in standard_slots, f'{key}: server task reused')
        standard_slots.add(task['task_id'])
        require(row['cache_prompt'] is (row['arm'] == ARM and row['role'] == 'followup') and row['generated_tokens'] == 32
                and row['n_predict'] == 32 and all(_positive(row.get(metric)) for metric in METRICS)
                and row['request_total_ms'] >= row['client_ttft_ms'], f'{key}: invalid stream result')
        content_events = [event['elapsed_ms'] for event in clock['stream_arrivals']
                          if event['generated_content'] and not event['progress'] and not event['stop']]
        require(content_events and abs(row['client_ttft_ms'] - content_events[0]) < 0.051
                and clock['stream_arrivals'][-1]['stop'] is True, f'{key}: first content arrival or stop missing')
        tokens = row['tokenized_prompt_tokens']
        cached = task['cached_tokens']
        progress = row['prompt_progress']
        require(tokens == task['prompt_tokens'] and tokens > cached and progress
                and row['prompt_tokens'] == tokens - cached
                and progress[0]['total'] == tokens and progress[0]['cache'] == cached
                and progress[-1]['processed'] == tokens, f'{key}: request token counts disagree')
        derived = r8_derive_p_ttft.derive(row)
        require(row['derived_ttft_ms'] == derived['derived_ttft_ms']
                and row['direct_client_ttft_ms'] == row['client_ttft_ms'], f'{key}: TTFT clocks disagree')
        pin = proposal['speed_prompt_pins'][row['request']]
        if cell['role'] == 'speed':
            require(tokens == pin['verified_server_tokens'] and row['prompt_sha256'] == pin['sha256'],
                    f'{key}: prompt differs from the pinned R8 benchmark')
        else:
            questions = r9_prefix_check.questions(prompts[row['request']])
            question = questions[cell['role'] == 'followup']
            require(row['prompt_sha256'] == paired.sha(question)
                    and 30 <= tokens - pin['verified_server_tokens'] <= 60,
                    f'{key}: follow-up prompt differs from the Phase 0b protocol')
        if cell['role'] != 'followup' or row['arm'] == CONTROL:
            require(cached == 0, f'{key}: unrelated prompt state leaked into timing')
        require(paired.sha(row['output_text']) == row['output_sha256'] and _coherent(row['output_text']),
                f'{key}: generated output failed the coherence smoke')
        indexed[key] = row
    return indexed, policy, previous_end


def _standard_comparison(rows, policy):
    comparisons = []
    for name in PROMPTS:
        for state, repeats in (('cold', REPEATS[:1]), ('warm', REPEATS[1:])):
            pairs = [(rows[ARM, name, state, repeat, 'speed'], rows[CONTROL, name, state, repeat, 'speed'])
                     for repeat in repeats]
            eligible = [(a, b) for a, b in pairs if _eligible(a, policy) and _eligible(b, policy)]
            group = dict(request=name, state=state, eligible_pairs=len(eligible), attempted_pairs=len(pairs),
                         median_candidate_to_control={})
            for metric in METRICS:
                ratios = [a[metric] / b[metric] for a, b in eligible]
                if ratios:
                    group['median_candidate_to_control'][metric] = median(ratios)
            group['within_tolerance'] = bool(eligible) and all(
                ratio >= 1 - REGRESSION_TOLERANCE if metric == 'decode_tokens_per_second'
                else ratio <= 1 + REGRESSION_TOLERANCE
                for metric, ratio in group['median_candidate_to_control'].items())
            comparisons.append(group)
    return comparisons


def _followup_comparison(rows, proposal, policy):
    comparisons = []
    for name in PROMPTS:
        candidate = rows[ARM, name, 'follow-up', 0, 'followup']
        control = rows[CONTROL, name, 'follow-up', 0, 'followup']
        seed = rows[ARM, name, 'follow-up', 0, 'followup_seed']
        control_seed = rows[CONTROL, name, 'follow-up', 0, 'followup_seed']
        require(seed['prompt_sha256'] == control_seed['prompt_sha256']
                and candidate['prompt_sha256'] == control['prompt_sha256']
                and seed['prompt_sha256'] != candidate['prompt_sha256'],
                f'{name}: candidate and control did not run the same two distinct prompts')
        require(candidate['server_log_start'] >= seed['server_log_end']
                and control['server_log_start'] >= control_seed['server_log_end'],
                f'{name}: follow-up ordering is invalid')
        cached = candidate['reuse']['cached_tokens']
        document = proposal['speed_prompt_pins'][name]['verified_server_tokens']
        eligibility = all(_eligible(row, policy) for row in (candidate, control, seed, control_seed))
        comparisons.append(dict(
            request=name, candidate_cached_tokens=cached, control_cached_tokens=control['reuse']['cached_tokens'],
            document_tokens=document, eligibility=eligibility,
            candidate={key: candidate[key] for key in METRICS}, control={key: control[key] for key in METRICS},
            meaningful_reuse=cached >= 0.8 * document,
            lower_ttft=candidate['derived_ttft_ms'] < control['derived_ttft_ms']))
    return comparisons


def _accuracy(mmlu, raw_log, previous_end, expected, reference, load):
    questions = expected.questions[:MMLU_IDENTITY['question_count']]
    ids = [q['id'] for q in questions]
    require(mmlu['format'] == MMLU_FORMAT and mmlu['status'] == 'complete' and mmlu['source'] == expected.source
            and mmlu['protocol'] == MMLU_IDENTITY and mmlu['request'] == dict(path='/completion', **REQUEST)
            and mmlu['quiet_policy'] == quiet.policy(quiet.EMPTY)
            and mmlu['settings'] == dict(load['observed'], mode='sequential_on_one_slot',
                                         requests='first 25 ordered questions queued on one slot')
            and mmlu['reference'] == mmlu_reference_summary(reference, ids),
            'MMLU source, reference or identity protocol differs from approval')
    batch = mmlu['batch']
    require(batch['question_ids'] == ids and batch['server_log_start'] >= previous_end
            and len(ids) == MMLU_IDENTITY['question_count'] and list(mmlu['rows']) == ids,
            'MMLU identity cases are missing, reordered or exceed the approved 25')
    if batch['quiet']['status'] == 'accepted':
        require(_eligible(batch, mmlu['quiet_policy']), 'MMLU batch was assigned unsupported quiet eligibility')
    else:
        require(batch['quiet']['status'] == 'excluded' and batch['quiet']['reasons'],
                'MMLU batch lacks a reason for quiet exclusion')
    tasks = _raw_tasks(raw_log, batch)
    require(tasks == batch['cache_evidence'] and len(tasks) == len(ids)
            and len({task['task_id'] for task in tasks}) == len(ids)
            and not first_cached_tasks(raw_log[batch['server_log_end']:]), 'MMLU task log coverage differs from the approved 25')
    for index, (task, q) in enumerate(zip(tasks, questions)):
        row = mmlu['rows'][q['id']]
        require('end' in task and task['slot_id'] == 0 and type(task.get('cached_tokens')) is int
                and task['prompt_tokens'] == row['prompt_tokens'] and row['response_index'] == index,
                f'MMLU question {q["id"]} lacks independently verifiable scoring evidence')
        top = row['top_logprobs']
        require(len(top) == REQUEST['n_probs'] and all(
            isinstance(token, str) and type(logprob) in (float, int) and math.isfinite(logprob) and logprob <= 0
            for token, logprob in top), f'MMLU question {q["id"]} lacks the top-token distribution')
        probs = paired.letter_probs(top)
        mass = sum(probs.values())
        pick = max(probs, key=probs.get)
        require((row['prompt_sha256'], row['answer']) == (paired.sha(q['prompt']), q['answer'])
                and row['probs'] == {letter: round(prob, 6) for letter, prob in probs.items()}
                and row['pick'] == pick and row['top_token'] == top[0][0] and row['letter_mass'] == round(mass, 4)
                and type(row['correct']) is bool and row['correct'] == (pick == q['answer'] and mass > 0),
                f'MMLU question {q["id"]} has inconsistent scoring data')
    comparison = accuracy_identity(mmlu, tasks)
    require(comparison == mmlu['comparison'], 'Recorded MMLU identity differs from the 25 measured responses')
    return comparison


def verify_runtime_stage(manifest):
    """Return a gate verdict; excluded windows and missing evidence never imply a pass."""
    checks = []
    summary = {}

    def check(name, passed, detail):
        checks.append(dict(name=name, status='pass' if passed else 'fail', stage=STAGE, detail=detail))

    try:
        require(manifest['format'] == FORMAT and manifest['status'] == 'complete',
                'The one capped load did not finish')
        root = Path(manifest['root'])
        files = manifest['files']
        require(root.is_absolute() and REQUIRED_FILES <= files.keys(), 'Measurement files are incomplete')
        for name, sha in files.items():
            path = root / name
            require(name == Path(name).name and not path.is_symlink() and digest(path) == sha,
                    f'Raw file digest mismatch: {name}')
        load = read(root / 'load.json')
        speed = read(root / 'speed.json')
        ttft = read(root / 'ttft.json')
        mmlu = read(root / 'mmlu.json')
        raw_log = (root / 'server.log').read_bytes()
        stage = manifest['identity']
        observed = load['observed']
        require(load['identity'] == stage and load['status'] == 'complete' and load['server_closed'] is True
                and load['load_id'] == manifest['load_id'] and load['request_id'] == manifest['request_id']
                and load['image']['image_id'] == stage['image_id']
                and load['image']['llama_server_sha256'] == stage['executable_sha256']
                and load['image']['launch_config_sha256'] == stage['launch_config_sha256']
                and load['memory_cap'] == capped_run.CAP and load['swap_cap_bytes'] == 0
                and f'MemoryMax={capped_run.CAP}' in load['argv'] and 'MemorySwapMax=0' in load['argv']
                and load['gate_before_load']['ok'] is True
                and load['device_budget_mib'] == DEVICE_BUDGET and observed['n_seq_max'] == 1
                and 0 < sum(observed['device_mib'].values()) <= DEVICE_BUDGET
                and _positive(load['sampled_peak_memory_bytes'])
                and load['sampled_peak_memory_bytes'] <= 96 * 2**30
                and _positive(load['min_available_bytes']),
                'Measured image, one-load cap or device budget could not be established')
        expected, prompts, leg, ref_speed, ref_mmlu = references(load['reference'], stage)
        model_index = load['argv'].index('-m')
        require(load['argv'][model_index + 1] == stage['pack']['first_shard']
                and load['argv'][model_index + 2:model_index + 2 + len(stage['launch_config']['args'])]
                == stage['launch_config']['args']
                and [observed[key] for key in ('n_ctx', 'n_batch', 'n_ubatch')] ==
                [leg[key] for key in ('ctx', 'batch', 'ubatch')]
                and speed['reference_aqb'] == ref_speed, 'Actual launch differs from the verified baseline settings')
        check('verified_image_and_capped_load', True,
              'Verified configured image and unchanged pack ran once on a capped single-slot server.')
        require(ttft['source_sha256'] == files['speed.json'], 'TTFT sidecar names different speed data')
        rows, policy, log_end = _speed_rows(speed, ttft, raw_log, expected.proposal, prompts)
        check('valid_streams_and_coherence', True,
              'All standard and document question requests completed with 32 tokens and coherent text.')
        standard = _standard_comparison(rows, policy)
        summary.update(standard=standard, standard_regression_tolerance=REGRESSION_TOLERANCE)
        check('standard_same_load_speed', all(item['within_tolerance'] for item in standard),
              'Compare matched quiet pairs at both lengths and page-cache states, with a 10% relative tolerance.')
        followup = _followup_comparison(rows, expected.proposal, policy)
        summary['followup'] = followup
        check('followup_reuse_and_ttft',
              all(item['eligibility'] and item['meaningful_reuse'] and item['lower_ttft'] for item in followup),
              'Both follow-up pairs had quiet eligibility, reused the document prefix, and beat the cache-off TTFT.')
        accuracy = _accuracy(mmlu, raw_log, log_end, expected, ref_mmlu, load)
        summary['accuracy'] = accuracy
        passed = accuracy['status'] == 'passed'
        detail = (f'{accuracy["matched_letters"]}/25 answer letters matched AQB and '
                  f'{accuracy["zero_external_reuse"]}/25 started with zero cached tokens.')
        if passed:
            detail += ' AQBC inherits the pinned AQB score of 91.6% (229/250) by this identity check.'
        check('mmlu_identity', passed, detail)
    except (OSError, ValueError, KeyError, TypeError, IndexError, AttributeError, OverflowError, StopIteration) as error:
        check('runtime_evidence', False, str(error))
    done = bool(checks) and all(check['status'] == 'pass' for check in checks)
    return dict(done=done, decision='passed' if done else 'refused', checks=checks, summary=summary,
                stage_reached=STAGE if done else None)
