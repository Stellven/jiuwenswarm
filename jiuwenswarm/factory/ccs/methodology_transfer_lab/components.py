"""Bounded, dependency-free research transfer and experiment evidence helpers."""
import math
import re


def finite(value, name, positive=True):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or (value <= 0 if positive else value < 0):
        raise ValueError(name + ' must be finite and ' + ('positive' if positive else 'nonnegative'))
    return value


def assess_transfer(request):
    source, target = request['source'], request['target']
    blockers, unknowns = [], []
    if not re.fullmatch(r'https://[^\s]+', source.get('url', '')):
        blockers.append('primary_source_url_required')
    if not re.fullmatch(r'[a-f0-9]{40,64}', source.get('revision', '')):
        unknowns.append('source_revision_not_pinned')
    if not source.get('license'):
        unknowns.append('license_requires_review_before_copying_code')
    semantics = request['semantics']
    if semantics not in ('routing_preserving', 'precision_change', 'expert_skipping', 'speculative_verified'):
        raise ValueError('Unknown semantic class')
    if semantics == 'expert_skipping' and not request.get('allow_approximate', False):
        blockers.append('expert_skipping_outside_exact_lane')
    if semantics == 'precision_change' and not request.get('allow_approximate', False):
        blockers.append('precision_change_requires_separate_approximate_lane')
    requirements = request.get('requires', {})
    for field in ('architecture', 'backend', 'model_family'):
        accepted = requirements.get(field, [])
        if not isinstance(accepted, list) or not all(isinstance(x, str) for x in accepted):
            raise ValueError('Requirement lists must contain strings')
        actual = target.get(field)
        if not actual:
            unknowns.append(field + '_unknown')
        elif accepted and actual not in accepted:
            blockers.append(field + '_port_required')
    if target.get('shared_cpu_gpu_memory') is True and requirements.get('disjoint_cpu_gpu_capacity') is True:
        blockers.append('unified_memory_capacity_cannot_be_counted_twice')
    if requirements.get('relu_sparse_model') is True and target.get('relu_sparse_model') is not True:
        blockers.append('activation_sparsity_not_established_for_target')
    return dict(status='blocked' if blockers else 'needs_evidence' if unknowns else 'candidate_for_scoped_testing',
                blockers=blockers, unknowns=unknowns, semantic_lane=semantics,
                source_claim_verified=False, runtime_compatibility_verified=False,
                admission_granted=False, next_step='Agent must inspect pinned primary source and choose a scoped verification unit.')


def design_trial(request):
    change = request['change']
    if not isinstance(change, dict) or len(change) != 1:
        raise ValueError('A trial changes exactly one named variable')
    family = request['family']
    first = {'expert_cache': 'causal_trace_replay', 'expert_prediction': 'request_separated_holdout',
             'ssd_streaming': 'owned_temporary_file_io', 'placement': 'capacity_and_cost_reference',
             'precision': 'numeric_reference_error', 'kv_cache': 'state_identity_and_copy_on_write',
             'serving': 'bounded_scheduler_trace', 'kernel': 'operator_reference_comparison'}
    if family not in first:
        raise ValueError('Unsupported methodology family')
    budget = request['budget']
    for key in ('cpu_seconds', 'gpu_seconds', 'max_trials'):
        finite(budget[key], key, positive=False)
    if type(budget['max_trials']) is not int or budget['max_trials'] < 1:
        raise ValueError('At least one bounded trial required')
    objective = request['objective']
    shapes = {'prefill': [dict(prompt_tokens=4096, generated_tokens=16)],
              'decode': [dict(prompt_tokens=128, generated_tokens=512)],
              'balanced': [dict(prompt_tokens=512, generated_tokens=128)]}
    if objective not in shapes:
        raise ValueError('Unknown objective')
    return dict(first_test=first[family], change=change, shapes=shapes[objective],
                later_tests=['operator_or_layer_reference', 'small_model_correctness', 'matched_workload_ABBA'],
                correctness_obligations=['retain_all_selected_experts', 'preserve_model_tokenizer_identity', 'declare_precision_changes'],
                runtime_authorized=False, budget=dict(budget), order=['A', 'B', 'B', 'A'],
                stop_conditions=['reference_mismatch', 'budget_exhausted', 'no_mechanism_engagement'],
                scope='A proposed experiment recipe, not an admitted or executed lab contract.')


def analyze_abba(request):
    cells = request['cells']
    if len(cells) != 4 or [c['arm'] for c in cells] != list('ABBA'):
        raise ValueError('Exactly four ordered ABBA cells required')
    warmup = request.get('warmup_requests', 1)
    if type(warmup) is not int or not 0 <= warmup <= 100:
        raise ValueError('Invalid warmup count')
    identity = None
    outputs, stats = [], []
    for cell in cells:
        rows = cell['requests']
        if not warmup < len(rows) <= 1000:
            raise ValueError('Missing measured requests or excessive count')
        signature = [(r['case_id'], r['input_sha256'], r['prompt_tokens'], r['generated_tokens']) for r in rows]
        if identity is None:
            identity = signature
        elif identity != signature:
            raise ValueError('Workload IDs, input identity, or token counts differ')
        for row in rows:
            for key in ('prompt_tokens', 'generated_tokens'):
                if type(row[key]) is not int or not 1 <= row[key] <= 2**31:
                    raise ValueError('Token counts must be integers in [1, 2**31]')
            for key in ('prefill_ms', 'decode_ms'):
                finite(row[key], key)
                if not 1e-9 <= row[key] <= 1e12:
                    raise ValueError('Native milliseconds outside supported numeric range')
            if not re.fullmatch('[a-f0-9]{64}', row['input_sha256']):
                raise ValueError('Exact input identity required')
            if row.get('output_sha256') is not None and not re.fullmatch('[a-f0-9]{64}', row['output_sha256']):
                raise ValueError('Malformed output identity')
        selected = rows[warmup:]
        pp = sum(r['prefill_ms'] for r in selected)
        dt = sum(r['decode_ms'] for r in selected)
        nt = sum(r['generated_tokens'] for r in selected)
        np = sum(r['prompt_tokens'] for r in selected)
        outputs.append([r.get('output_sha256') for r in rows])
        stats.append(dict(arm=cell['arm'], prefill_ms=pp, decode_ms=dt, generated_tokens=nt, prompt_tokens=np,
                          combined_tps=nt * 1000 / (pp + dt)))
    pooled = {}
    for arm in 'AB':
        subset = [s for s in stats if s['arm'] == arm]
        pp = sum(s['prefill_ms'] for s in subset)
        dt = sum(s['decode_ms'] for s in subset)
        nt = sum(s['generated_tokens'] for s in subset)
        np = sum(s['prompt_tokens'] for s in subset)
        pooled[arm] = dict(prefill_tps=np * 1000 / pp, decode_tps=nt * 1000 / dt,
                           combined_tps=nt * 1000 / (pp + dt), prefill_fraction=pp / (pp + dt))
    known = all(all(v is not None for v in out) for out in outputs)
    return dict(pooled=pooled, combined_ratio=pooled['B']['combined_tps'] / pooled['A']['combined_tps'],
                paired_ratios=[stats[1]['combined_tps'] / stats[0]['combined_tps'], stats[2]['combined_tps'] / stats[3]['combined_tps']],
                exact_outputs_equal=all(out == outputs[0] for out in outputs) if known else None,
                within_baseline_equal=outputs[0] == outputs[3] if known else None,
                within_candidate_equal=outputs[1] == outputs[2] if known else None,
                semantic_quality_evaluated=False, performance_acceptance_evaluated=False,
                scope='Caller-supplied timing arithmetic only. Two pairs are descriptive; raw provenance and correctness require independent verification.')


TOOLS = dict(assess_transfer=assess_transfer, design_trial=design_trial, analyze_abba=analyze_abba)
