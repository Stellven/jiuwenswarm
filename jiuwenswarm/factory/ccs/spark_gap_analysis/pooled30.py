"""Candidate-only fixed-position screening against four closed quiet A+30 controls."""
from statistics import median


PROMPTS = (512, 2048)
ORDER = (512, 2048, 512, 2048, 2048, 512, 512, 2048, 2048, 512, 512, 2048)
METRICS = ('ttft_s', 'decode_tps')
MAPPER_ARGV = ['-np', '1', '-c', '4096', '--ctx-checkpoints', '0', '-b', '2047', '-ub', '512']
MAPPER_SETTINGS = dict(n_ctx=4096, n_ctx_seq=4096, n_slots=1, n_batch=2047, n_ubatch=512)


def demand(condition, message):
    if not condition:
        raise ValueError(message)


def stats(values):
    return {'median': median(values), 'observed_range': [min(values), max(values)], 'values': values}


def deltas(candidate, control):
    return dict(ttft_seconds_saved=stats([a['ttft_s'] - b['ttft_s'] for a, b in zip(control, candidate)]),
                decode_tps_gained=stats([b['decode_tps'] - a['decode_tps'] for a, b in zip(control, candidate)]))


def median_rows(sources):
    return [{key: median(x[key] for x in ordinal) for key in METRICS} for ordinal in zip(*sources)]


def absolute(samples):
    return {metric: stats([sample[metric] for sample in samples]) for metric in METRICS}


def admitted(scope, rows, expected, eligible, positive, reference, is_candidate):
    cap = scope['value']
    demand(cap['scope_verified'] and cap['returncode'] == 0 and cap['reason'] is None and
           cap['min_mem_available_bytes'] >= 8 * 1024**3 and not any(
               int(cap['memory_events'].get(key, 0)) for key in ('oom', 'oom_kill', 'oom_group_kill')),
           'Pooled comparison needs clean capped launches')
    demand(scope['matched_bank']['requested_mib'] == 30720 and 0 < scope['matched_bank']['allocated_mib'] <= 30720,
           'Pooled comparison needs an observed 30 GiB native-cache request and allocation')
    demand(len(rows) == (12 if is_candidate else 16), 'Pooled source lacks its full ordered workload')
    expected_order = ORDER if is_candidate else (*ORDER, 2048, 512, 512, 2048)
    demand(tuple(row['result']['prompt_tokens'] for row in rows) == expected_order,
           'Pooled candidate or control differs from its fixed request order')
    demand([r['result']['discard'] for r in rows] == [True] * (4 if is_candidate else 6) +
           [False] * (8 if is_candidate else 10), 'Pooled source discarded flags differ from their actual protocol')
    for row in rows:
        ref = reference(row)
        result = row['result']
        demand(row['scope_id'] == scope['artifact_id'] and result['arm'] == scope['arm'] and
               eligible(row, expected) and positive(result['decode_tps']),
               f'Pooled request {ref["artifact_id"]} does not match its scope and workload')
    return {size: [row for row in rows if row['result']['prompt_tokens'] == size] for size in PROMPTS}


def analyze(evidence, eligible, reference, positive):
    candidate = evidence['candidate']
    controls = evidence['controls']
    expected = {p['target_tokens_including_template']: p['prompt_sha256'] for p in evidence['prompt_manifest']['value']['prompts']}
    subject = candidate['scope']['arm']
    mapper = subject == 'C5'
    package = subject in ('C2', 'D', 'C5')
    demand(set(expected) == set(PROMPTS) and len(controls) == 4 and len({c['id'] for c in controls}) == 4,
           'Pooled screening uses both fixed prompt sizes and four distinct immutable controls')
    demand(len({c['scope']['sha256'] for c in controls}) == 4,
           'Pooled screening cannot count the same retained control scope multiple times')
    observed = admitted(candidate['scope'], candidate['requests'], expected, eligible, positive, reference, True)
    bank = candidate['scope']['matched_bank']
    matches = []
    for control in controls:
        scope = control['scope']
        other = scope['matched_bank']
        demand(scope['arm'] == 'A+' and scope['quiet_preflight']['quiet'] and all(
            bank[key] == other[key] for key in ('requested_mib', 'runtime_environment', 'cpu_share_pct')),
            'Pooled candidate differs from the controls in runtime environment or cache budget')
        if mapper:
            demand(bank['argv'] == other['argv'] + MAPPER_ARGV and
                   bank['effective_settings'] == (other['effective_settings'] | MAPPER_SETTINGS) and
                   bank['host_experts_mib'] == other['host_experts_mib'],
                   'C5 package differs outside its frozen mapper flags or effective settings')
        else:
            demand(bank['effective_settings'] == other['effective_settings'],
                   'Pooled candidate has different effective context, batch, slots or thread counts')
        if not package:
            demand(bank['argv'] == other['argv'] and bank['allocated_mib'] == other['allocated_mib'],
                   'Non-placement candidate has different effective launch argv or logged bank size')
        matches.append(admitted(scope, control['requests'], expected, eligible, positive, reference, False))
    overlap = any(any(entries.values()) for row in candidate['requests'] for entries in row.get('cpu_overlap', {}).values())
    overlap = overlap or any(candidate['scope']['cpu_overlap_prelaunch'].values()) or any(
        candidate['scope']['cpu_overlap_conditioning'].values())
    greedy_parity = True
    rows = []
    for size in PROMPTS:
        candidate_samples = [r['result'] for r in observed[size][2:6]]
        control_samples = [[r['result'] for r in scope[size][2:6]] for scope in matches]
        hashes = {(r['output_sha256'], r['reasoning_sha256']) for r in candidate_samples}
        greedy_parity = greedy_parity and len(hashes) == 1 and all(
            (r['output_sha256'], r['reasoning_sha256']) in hashes for source in control_samples for r in source)
        pooled = median_rows(control_samples)
        individuals = [dict(id=control['id'], absolute=absolute(values), **deltas(candidate_samples, values))
                       for control, values in zip(controls, control_samples)]
        paired = deltas(candidate_samples, pooled)
        sensitivity = {key: [min(c[key]['median'] for c in individuals), max(c[key]['median'] for c in individuals)]
                       for key in paired}
        sensitivity['exclude_control_warmup'] = deltas(candidate_samples[1:], pooled[1:])
        rows.append(dict(prompt_tokens=size, n=4, candidate=absolute(candidate_samples),
                         pooled_reference=absolute(pooled), pooled_estimates=paired,
                         controls=individuals, sensitivity=sensitivity,
                         matched_result_artifacts=dict(candidate=[reference(r) for r in observed[size][2:6]],
                             controls={control['id']: [reference(r) for r in scope[size][2:6]] for control, scope in zip(controls, matches)})))
    control_rows = [dict(id=c['id'], iteration_id=c['iteration_id'], launch_pass=c['scope']['launch_pass'],
                         scope_artifact_id=c['scope']['artifact_id'], scope_sha256=c['scope']['sha256']) for c in controls]
    candidate_scope = candidate['scope']
    cap = candidate_scope['value']
    result = dict(schema='spark-pooled30-screen/1', subject_arm=subject, control_count=4, controls=control_rows,
                basis='per-size-all-request-ordinal', matched_ordinals=[3, 4, 5, 6], candidate_warmups_per_size=2,
                package_treatment=package, greedy_parity=greedy_parity, cpu_overlap_observed=overlap, rows=rows,
                candidate_bank=bank, control_allocated_mib=[c['scope']['matched_bank']['allocated_mib'] for c in controls],
                candidate_source_commit=candidate_scope['source_commit'], candidate_scope=reference(candidate_scope),
                startup_seconds=candidate_scope['load']['seconds'],
                cap=dict(min_mem_available_bytes=cap['min_mem_available_bytes'], peak_memory_bytes=cap['peak_memory_bytes'],
                         memory_events=cap['memory_events']),
                predictor_decode=candidate_scope.get('predictor_decode'), placement=candidate_scope.get('placement'),
                activation_readbacks=evidence.get('activation_readbacks', {}),
                limitations=['One prospective candidate scope was compared with four historical quiet controls. Differences are descriptive screening estimates.',
                             'Candidate per-size ordinal 3 aligns with the controls’ third discarded warmup. Ordinals 4–6 align with their first three measured requests.',
                             'The across-control range and warmup exclusion show sensitivity. A positive difference favors the candidate.'])
    if mapper:
        mapping = candidate_scope['mapper']
        demand(mapping['prompts_2048'] == len(observed[2048]) and mapping['prompts_2048'] == 6 and
               all(type(mapping[key]) is int and mapping[key] >= 0 for key in ('decisions', 'rows', 'bypasses')) and
               mapping['all_2048_split'] == (mapping['cuts_2048'] == [['0', '1536'], ['1536', '2048']] * 6),
               'Missing or inconsistent C5 gate-on split and bypass evidence')
        reference(mapping['engine_log'])
        result.update(mapper=mapping, earlier_matched_flags=reference(evidence['earlier_matched_flags']),
                      control_bank=controls[0]['scope']['matched_bank'])
        result['limitations'].append('C5 and its explicit slot, context, checkpoints and batch settings form one package. The pooled stock scopes cannot isolate the mapper effect.')
    return result
