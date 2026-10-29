"""Rebuild an exploratory Part A/B decision report from retained observations.

Selected wins are views of an unchanged full dataset. No model judging, new
task execution, provider authentication or release acceptance occurs here.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path

from .contracts import canonical
from .value_data import Dataset, csv_bytes, number, write_once


def flatten(records):
    rows = []
    for record in records:
        value = record['value']
        if record['kind'] in ('harbor_job', 'capability_probe', 'case_bank_observation', 'native_trial'):
            for ordinal, original in enumerate(value['rows']):
                row = {k: v for k, v in original.items() if k not in ('input', 'output')}
                row.update(record_id=record['id'], row_id=record['id'] + ':' + str(ordinal),
                           record_kind=record['kind'], recorded_at=record['recorded_at'],
                           paired_with=value.get('paired_with'))
                rows.append(row)
        elif record['kind'] == 'comparison':
            result = value['result']
            for arm, original in result['arms'].items():
                content = original.get('content') or {}
                correct = (content.get('metrics') or {}).get('deterministic_content_success')
                rows.append({**original, 'record_id': record['id'], 'row_id': record['id'] + ':' + arm,
                    'record_kind': 'comparison', 'mode': 'imported_paired_comparison',
                    'assignment_sha256': result['assignment_sha256'], 'arm': arm,
                    'correct': bool(correct) if type(correct) in (int, bool) and correct in (0, 1) else None,
                    'source': value['source'], 'recorded_at': record['recorded_at']})
        elif record['kind'] == 'native_cc_pair':
            for arm, original in value['arms'].items():
                rows.append({**original, 'record_id': record['id'], 'row_id': record['id'] + ':' + arm,
                    'record_kind': record['kind'], 'case_id': value['case_id'], 'arm': arm,
                    'mode': 'full_native_skills_vs_full_cc_pipeline', 'task_sha256': value['task_sha256'],
                    'comparison_eligible': value['comparison_eligible'], 'recorded_at': record['recorded_at']})
        elif record['kind'] == 'poc_comparison':
            for arm in ('cc', 'native-skills'):
                original = value.get('arms', {}).get(arm) or {}
                completion = original.get('correct_usable_completion')
                rows.append({**original, 'record_id': record['id'],
                    'row_id': record['id'] + ':' + arm, 'record_kind': record['kind'],
                    'recorded_at': record['recorded_at'], 'case_id': value.get('case_id'),
                    'revision': value.get('revision'), 'arm': arm,
                    'mode': 'primary_poc_full_workflow_comparison',
                    'task_sha256': value.get('task_sha256'),
                    'comparison_eligible': value.get('comparison_eligible'),
                    'comparison_scope': value.get('comparison_scope'),
                    'correct': completion if type(completion) is bool else None,
                    'valid_response': original.get('valid_response'),
                    'scientific_success': original.get('scientific_success'),
                    'model_calls': original.get('model_calls'), 'usage': original.get('usage'),
                    'cost_usd': None})
        elif record['kind'] == 'cost_scenario':
            checked = cost_scenario_analysis(record)
            for arm in ('cc', 'native-skills'):
                original = value.get('arms', {}).get(arm) or {}
                rows.append({'record_id': record['id'], 'row_id': record['id'] + ':' + arm,
                    'record_kind': record['kind'], 'recorded_at': record['recorded_at'],
                    'case_id': value.get('case_id'), 'arm': arm, 'trial_id': original.get('trial_id'),
                    'mode': 'estimated_tariff_scenario_existing_trials', 'correct': None,
                    'cost_usd': None, 'estimated_cost_usd': checked['costs_usd'][arm],
                    'model_calls': None, 'referenced_model_calls': original.get('model_calls'),
                    'new_model_calls': 0, 'new_trials': 0,
                    'comparison_eligible': value.get('comparison_eligible'),
                    'scenario': value.get('scenario'), 'provenance': value.get('provenance'),
                    'quality_scope': value.get('quality_scope'),
                    'estimate_validated': checked['estimate_validated']})
        elif record['kind'] == 'component_native_pair':
            for ordinal, decision in enumerate(value['rows']):
                for arm in ('cc', 'native'):
                    original = decision[arm]
                    rows.append({**original, 'record_id': record['id'],
                        'row_id': record['id'] + ':' + str(ordinal) + ':' + arm,
                        'record_kind': record['kind'], 'recorded_at': record['recorded_at'],
                        'component': value['component'], 'case_id': decision['case_id'],
                        'component_case_ordinal': ordinal, 'task_sha256': decision.get('task_sha256'),
                        'arm': arm, 'mode': 'deterministic_component_vs_native_batch',
                        'batch_record_id': record['id'], 'model_calls': None, 'cost_usd': None,
                        'per_case_call_allocation': None,
                        'measurement_scope': value['scope'],
                        'comparison_eligible': value.get('comparison_eligible')})
    return rows


def _cell(value):
    if value is None:
        return 'unavailable'
    text = json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (dict, list)) else str(value)
    return text.replace('|', '\\|').replace('\r', ' ').replace('\n', ' ')


def cost_scenario_analysis(record):
    """Validate explicit estimate inputs; never infer price or actual billing."""
    value = record['value']
    validation = value.get('validation') or {}
    arms = value.get('arms') or {}
    costs = {arm: (arms.get(arm) or {}).get('estimated_cost_usd') for arm in ('cc', 'native-skills')}
    valid = (bool(value.get('scenario')) and bool(value.get('provenance'))
        and value.get('not_actual_bill') is True
        and all(validation.get(key) is True for key in
                ('full_call_populations_verified', 'observed_cached_usage_complete', 'model_effort_match'))
        and all(type(cost) in (int, float) and math.isfinite(cost) and cost >= 0 for cost in costs.values())
        and all(isinstance((arms.get(arm) or {}).get('trial_id'), str)
                and bool(arms[arm]['trial_id'])
                and type(arms[arm].get('model_calls')) is int and arms[arm]['model_calls'] >= 0
                for arm in ('cc', 'native-skills')))
    comparable_quality = (value.get('comparison_eligible') is True
        and value.get('quality_comparable') is True
        and all((arms.get(arm) or {}).get('quality_correct') is True for arm in ('cc', 'native-skills')))
    reduction = (100 * (costs['native-skills'] - costs['cc']) / costs['native-skills']
                 if valid and comparable_quality and costs['native-skills'] > 0 else None)
    return {'record_id': record['id'], 'case_id': value.get('case_id'),
        'scope': value.get('scope'), 'scenario': value.get('scenario'),
        'provenance': value.get('provenance'), 'rates': value.get('rates'),
        'estimate_validated': bool(valid), 'comparable_correct_quality': comparable_quality,
        'costs_usd': costs if valid else {'cc': None, 'native-skills': None},
        'cc_reduction_percent': reduction, 'quality_scope': value.get('quality_scope'),
        'referenced_trial_ids': {arm: (arms.get(arm) or {}).get('trial_id') for arm in ('cc', 'native-skills')},
        'referenced_model_calls': {arm: (arms.get(arm) or {}).get('model_calls') for arm in ('cc', 'native-skills')},
        'new_trials': 0, 'new_model_calls': 0, 'actual_cost_usd': None,
        'actual_service_tier': None, 'not_actual_bill': True}


def cost_scenario_section(scenarios):
    text = ['### Tariff estimates for existing trials', '']
    if not scenarios:
        return text + ['No explicit cost scenario is selected; actual dollar costs remain unavailable.', '']
    text += ['| Scope / case | CC estimate USD | Native estimate USD | CC reduction on comparable correct outputs | Referenced calls CC / native | Quality scope |',
             '| --- | ---: | ---: | ---: | ---: | --- |']
    for row in scenarios:
        costs = row['costs_usd']
        money = lambda x: 'unavailable' if x is None else f'{x:.8f}'
        reduction = 'unavailable' if row['cc_reduction_percent'] is None else f"{row['cc_reduction_percent']:.3f}%"
        calls = row['referenced_model_calls']
        text.append('| ' + ' | '.join([_cell(row.get('scope')) + ' / ' + _cell(row.get('case_id')),
            money(costs['cc']), money(costs['native-skills']), reduction,
            _cell(calls['cc']) + '/' + _cell(calls['native-skills']), _cell(row.get('quality_scope'))]) + ' |')
        text += ['', 'Scenario: ' + _cell(row['scenario']) + '. Provenance: ' + _cell(row['provenance']) + '.', '']
        if not row['estimate_validated']:
            text += ['Full-population/cache/identity validation or explicit numeric inputs are missing; the estimate remains unavailable.', '']
        elif not row['comparable_correct_quality']:
            text += ['These costs do not establish a comparable successful-output efficiency gain. Cheaper failed work is not a value win.', '']
    return text + ['These are chosen tariff scenarios using supplied observed cache counts, not actual service-tier observations, subscription charges or bills. Fees and invoice reconciliation remain unknown. Existing stable trial IDs identify reused evidence: these estimate rows add zero trials and zero model calls. Auxiliary paper quality ties and failed main-PoC costs remain separate.', '']


def poc_sections(pairs):
    """Keep handling, useful delivery, science and scoped claims independent."""
    text = ['### Primary PoC workflow comparisons', '']
    if not pairs:
        return text + ['No PoC comparison is selected.', '']
    text += ['| Case / revision | Arm | Eligible | Valid response / handling | Useful completion | Scientific success | Baseline accuracy | Treatment accuracy | Calls | Unsupported / assessed claims | Claim type / scope | Stopped phase |',
             '| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | --- | --- | --- |']
    for record in pairs:
        value = record['value']
        for arm in ('cc', 'native-skills'):
            original = value.get('arms', {}).get(arm) or {}
            unsupported, assessed = original.get('unsupported_claims'), original.get('assessed_claims')
            claims = (_cell(unsupported) + '/' + _cell(assessed)
                      if type(unsupported) is int and type(assessed) is int else 'unavailable')
            cells = [str(value.get('case_id')) + ' / ' + _cell(value.get('revision')), arm,
                value.get('comparison_eligible'), original.get('valid_response'),
                original.get('correct_usable_completion'), original.get('scientific_success'),
                original.get('baseline_accuracy'), original.get('treatment_accuracy'),
                original.get('model_calls'), claims, original.get('claim_scope'), original.get('stopped_phase')]
            text.append('| ' + ' | '.join(_cell(cell) for cell in cells) + ' |')
        text += ['', f"- `{_cell(value.get('case_id'))}` revision `{_cell(value.get('revision'))}` "
                 f"(record `{record['id']}`): {_cell(value.get('comparison_scope'))}."]
        arms = value.get('arms', {})
        cc, native = arms.get('cc') or {}, arms.get('native-skills') or {}
        if (value.get('comparison_eligible') is True
                and cc.get('correct_usable_completion') is False
                and native.get('correct_usable_completion') is True):
            text.append('  This eligible revision shows a useful-completion advantage for native. The failed CC revision remains evidence; a repaired or pending revision does not replace it.')
        if (cc.get('valid_response') is True and native.get('valid_response') is True
                and cc.get('correct_usable_completion') is False
                and native.get('correct_usable_completion') is False):
            text.append('  Both responses are valid handling; neither is completed useful research. Correct impossibility handling is not PoC success.')
        for limitation in value.get('limitations') or []:
            text.append('  Limitation: ' + _cell(limitation))
        estimate = value.get('estimated_cost')
        if isinstance(estimate, dict) and estimate.get('scenario') and estimate.get('provenance'):
            text += ['  Explicit estimated cost scenario (not an actual bill): ' + _cell(estimate)]
        text.append('')
    text += ['Handling, useful artifact completion and scientific outcome are separate. A scientific FAIL can be a useful completed study; an honest impossibility response is valid handling without completed research. Missing measurements remain unavailable.', '',
             'Claim counts use only each stated assessed-claim population and type. Different scopes or rubric subsets are not a shared denominator; no population or unsupported rate is inferred from missing counts. Revisions remain separate observations, not independent repeated trials. All original records and evidence remain in `all-records.jsonl` and `analysis.json`.', '']
    return text


def component_batches(records, selected):
    """Keep selected decision scores and indivisible whole-batch costs separate."""
    ordinals = defaultdict(set)
    for row in selected:
        if row['record_kind'] == 'component_native_pair':
            ordinals[row['record_id']].add(row['component_case_ordinal'])
    result = []
    for record in records:
        if record['kind'] != 'component_native_pair' or record['id'] not in ordinals:
            continue
        value = record['value']
        decisions = [row for index, row in enumerate(value['rows']) if index in ordinals[record['id']]]
        scores = {arm: {'correct': sum(row[arm].get('correct') is True for row in decisions),
                       'available': sum(row[arm].get('available') is True for row in decisions),
                       'unavailable': sum(row[arm].get('available') is not True for row in decisions)}
                  for arm in ('cc', 'native')}
        cost = value['batch_cost']
        result.append({'record_id': record['id'], 'component': value['component'],
            'selected_case_ids': [row['case_id'] for row in decisions],
            'selected_decisions': len(decisions), 'batch_decisions': len(value['rows']),
            'selected_scores': scores, 'batch_cost': cost,
            'ordinary_helper_control': value.get('ordinary_helper_control'),
            'native_status': value['native_status'], 'population': value['population'],
            'alignment': value['alignment'], 'comparison_eligible': value.get('comparison_eligible'),
            'scope': value['scope'], 'per_case_call_allocation': None,
            'algorithm_gain_claim': False})
    return result


def probe_summary(rows):
    groups = defaultdict(list)
    for row in rows:
        if row['record_kind'] == 'capability_probe':
            groups[(row['record_id'], row['module'])].append(row)
    result = []
    for (record_id, module), values in sorted(groups.items()):
        clean = [r for r in values if r['known_valid']]
        invalid = [r for r in values if not r['known_valid']]
        result.append({'record_id': record_id, 'module': module, 'clean': len(clean),
            'clean_accepted': sum(r['checker_accepted'] for r in clean), 'invalid': len(invalid),
            'caught': sum(not r['checker_accepted'] for r in invalid),
            'false_accept': sum(r['checker_accepted'] for r in invalid),
            'false_reject': sum(not r['checker_accepted'] for r in clean),
            'checker_seconds': sum(r['checker_elapsed_s'] for r in values)})
    return result


def paired_gains(records):
    gains = []
    for record in records:
        if record['kind'] != 'comparison' or record['value'].get('recomputed') is not True:
            continue
        result = record['value']['result']; arms = result['arms']
        baseline, cc = arms.get('native_codex_tool_free', {}), arms.get('ai4r_cc', {})
        def success(arm):
            metric = ((arm.get('content') or {}).get('metrics') or {}).get('deterministic_content_success')
            return metric if type(metric) in (int, bool) and metric in (0, 1) else None
        a, b = success(baseline), success(cc)
        model_match = (baseline.get('effective_model') is not None
                       and baseline.get('effective_model') == cc.get('effective_model')
                       and baseline.get('reasoning_effort') is not None
                       and baseline.get('reasoning_effort') == cc.get('reasoning_effort'))
        gains.append({'record_id': record['id'], 'assignment_sha256': result['assignment_sha256'],
            'baseline': 'native_codex_tool_free', 'cc': 'ai4r_cc',
            'baseline_content': a, 'cc_content': b, 'model_and_effort_match': model_match,
            'delta': b - a if a is not None and b is not None and model_match else None,
            'scope': 'selected development assignment; content only; binding/format/cost remain separate'})
    return sorted(gains, key=lambda r: (r['delta'] is None, -(r['delta'] or 0), r['record_id']))


def probe_improvements(rows):
    groups = defaultdict(list)
    for row in rows:
        if row['record_kind'] == 'capability_probe':
            groups[row['record_id']].append(row)
    result = []
    for before_id, before in groups.items():
        if not all(r['module'].endswith('_v2') for r in before):
            continue
        for after_id, after in groups.items():
            if not all(r['module'].endswith('_typed') and r.get('paired_with') == before_id for r in after):
                continue
            def keyed(values):
                keys = [(r['case_id'], r['fault'], r['input_sha256'], r['artifact_sha256']) for r in values]
                if len(set(keys)) != len(keys):
                    raise ValueError('duplicate paired probe artifact')
                return dict(zip(keys, values))
            a, b = keyed(before), keyed(after)
            if a.keys() != b.keys():
                continue
            invalid = [key for key in a if not a[key]['known_valid']]
            clean = [key for key in a if a[key]['known_valid']]
            if any(a[k]['known_valid'] != b[k]['known_valid'] for k in a):
                raise ValueError('paired probe labels differ')
            result.append({'before_record': before_id, 'after_record': after_id,
                'identical_input_output_pairs': len(a), 'invalid': len(invalid), 'clean': len(clean),
                'before_caught': sum(not a[k]['checker_accepted'] for k in invalid),
                'after_caught': sum(not b[k]['checker_accepted'] for k in invalid),
                'before_clean_accepted': sum(a[k]['checker_accepted'] for k in clean),
                'after_clean_accepted': sum(b[k]['checker_accepted'] for k in clean)})
    return result


def render(dataset, output, *, selected_records=(), selected_cases=(), template=None, charts=True):
    data = Dataset(dataset)
    records = data.records(); snapshot = data.snapshot()
    rows = flatten(records)
    if set(selected_records) - {r['id'] for r in records}:
        raise ValueError('unknown selected record ID')
    if set(selected_cases) - {r.get('case_id') for r in rows}:
        raise ValueError('unknown selected case ID')
    selected = [r for r in rows if (not selected_records or r['record_id'] in selected_records)
                and (not selected_cases or r.get('case_id') in selected_cases)]
    destination = Path(output).absolute()
    if (destination.exists() or destination.is_relative_to(data.root)
            or data.root.is_relative_to(destination)):
        raise ValueError('fresh report directory separate from raw dataset required')
    destination.mkdir(parents=True)
    write_once(destination / 'dataset-manifest.json', snapshot)
    write_once(destination / 'selection.json', {'schema': 'ai4r-value-selection:1',
        'dataset_sha256': snapshot['sha256'], 'record_ids': list(selected_records),
        'case_ids': list(selected_cases), 'selected_row_ids': [r['row_id'] for r in selected],
        'full_rows': len(rows), 'selected_rows': len(selected), 'all_outcomes_retained': True,
        'purpose': 'Selected development value demonstration, not representative scientific evaluation.'})
    write_once(destination / 'all-records.jsonl', b''.join(canonical(r) + b'\n' for r in records), raw=True)
    write_once(destination / 'all-results.jsonl', b''.join(canonical(r) + b'\n' for r in rows), raw=True)
    events = [{'record_id': r['id'], 'task_key': r['value']['task_key'], **event}
              for r in records if r['kind'] == 'telemetry'
              for event in r['value']['metrics']['original_events']]
    write_once(destination / 'telemetry-events.jsonl', b''.join(canonical(e) + b'\n' for e in events), raw=True)
    write_once(destination / 'telemetry-events.csv', csv_bytes(events, ['record_id', 'task_key', 'ref', 'kinds', 'record']), raw=True)
    columns = sorted({key for row in rows for key in row})
    write_once(destination / 'all-results.csv', csv_bytes(rows, columns), raw=True)
    probes = probe_summary(selected)
    selected_ids = {r['record_id'] for r in selected}
    gains = paired_gains([r for r in records if r['id'] in selected_ids])
    improvements = probe_improvements(selected)
    primary_pairs = [r for r in records if r['kind'] == 'native_cc_pair' and r['id'] in selected_ids]
    poc_pairs = [r for r in records if r['kind'] == 'poc_comparison' and r['id'] in selected_ids]
    cost_scenarios = [cost_scenario_analysis(r) for r in records
                      if r['kind'] == 'cost_scenario' and r['id'] in selected_ids]
    estimate_rows = [row for row in selected if row['record_kind'] == 'cost_scenario']
    write_once(destination / 'estimated-cost-scenarios.csv', csv_bytes(estimate_rows,
        ['record_id', 'case_id', 'arm', 'trial_id', 'scenario', 'estimated_cost_usd',
         'cost_usd', 'estimate_validated', 'referenced_model_calls', 'new_model_calls',
         'new_trials', 'quality_scope', 'provenance']), raw=True)
    components = component_batches(records, selected)
    write_once(destination / 'analysis.json', {'full_rows': len(rows), 'selected_rows': len(selected),
        'probe_summary': probes, 'paired_checker_improvements': improvements, 'paired_content_deltas': gains,
        'native_skills_cc_pairs': [{'record_id': r['id'], **r['value']} for r in primary_pairs],
        'component_native_batches': components,
        'poc_comparisons': [{'record_id': r['id'], **r['value']} for r in poc_pairs],
        'estimated_cost_scenarios': cost_scenarios,
        'suite_jobs': [r['value']['summary'] for r in records if r['kind'] == 'harbor_job']})
    # Presentation filters select experimental outcomes. Project health always
    # uses the full retained health evidence, including current blockers.
    health = sorted((r for r in records if r['kind'] == 'health'), key=lambda r: (r['recorded_at'], r['id']))
    part_a = ['## Part A — Project health and quality', '',
        'This development campaign supports a decision about continued CC and verifier work. '
        'Selected gains are shown with their measured scope; the complete dataset remains available.', '',
        f'- Dataset: {len(records)} content-hashed records and {len(rows)} result rows; the tools never overwrite an earlier record.',
        f'- Presentation selection: {len(selected)} rows; selection filters are saved in `selection.json`.',
        ('- Suite source: the included Harbor development release; existing grading and acceptance rules are unchanged.'
         if any(r['kind'] == 'harbor_job' for r in records) else
         '- Evidence sources and grading scope are retained per observation; a PoC comparison does not imply a Harbor suite run.')]
    if health:
        part_a.append('- Health observations below are chronological history; later deployment observations supersede earlier runtime state.')
        for record in health:
            value = record['value']
            source = value.get('source')
            evidence = ('source SHA-256 `' + source['sha256'] + '`') if source else 'operator note; no original evidence attached'
            part_a.append('- [' + record['recorded_at'] + '] ' + str(value.get('summary', 'Health observation')) +
                          f" (record `{record['id']}`; {evidence}).")
    else:
        part_a.append('- Current deployment readiness and live quality have not been imported into this dataset.')
    if poc_pairs:
        part_a += ['', f'- Primary PoC evidence: {len(poc_pairs)} selected case/revision records. '
            'Useful completion, correct handling, scientific outcome and stopped phase are reported separately below; '
            'earlier failed revisions and setup exclusions remain in the full dataset.']
    part_b = ['## Part B — CC and verifier value', '', *poc_sections(poc_pairs),
              *cost_scenario_section(cost_scenarios)]
    for gain in improvements:
        part_b += [f"**A reusable checking fix increased detected corruptions from {gain['before_caught']}/{gain['invalid']} "
            f"to {gain['after_caught']}/{gain['invalid']} on identical artifacts.** "
            f"Clean acceptance was {gain['before_clean_accepted']}/{gain['clean']} before and "
            f"{gain['after_clean_accepted']}/{gain['clean']} after. "
            'The additive candidates preserve JSON primitive types; earlier releases and results remain intact.', '']
    if improvements:
        part_b += ['![Selected before/after checker results](checker-improvement.png)', ''] if charts else []
    part_b += ['### Measured deterministic checking capability', '',
        '| Source module | Clean accepted / clean | Corruptions caught / injected | False accepts | False rejects |',
        '| --- | ---: | ---: | ---: | ---: |']
    for row in probes:
        part_b.append(f"| {row['module']} | {row['clean_accepted']}/{row['clean']} | {row['caught']}/{row['invalid']} | {row['false_accept']} | {row['false_reject']} |")
    if not probes:
        part_b.append('| No probe observations selected | — | — | — | — |')
    part_b += ['', 'These are direct worker/checker probes on deliberately corrupted artifacts. '
        'They measure detection and clean acceptance, not live semantic-verifier accuracy or superiority over an agent.', '',
        '### Native skills versus full CC pipeline', '']
    if primary_pairs:
        part_b += ['| Case | Identity/input/budget eligible | Native correct | CC correct | Native calls | CC calls (worker + verifier) |',
                   '| --- | --- | --- | --- | ---: | ---: |']
        for pair in primary_pairs:
            value = pair['value']; native_arm = value['arms']['native-skills']; cc_arm = value['arms']['cc']
            functions = cc_arm.get('call_functions', {})
            part_b.append(f"| {value['case_id']} | {value['comparison_eligible']} | {native_arm['correct']} | {cc_arm['correct']} | "
                f"{native_arm['model_calls']} | {cc_arm['model_calls']} ({functions.get('worker', '?')} + {functions.get('verifier', '?')}) |")
        part_b += ['', 'These pairs use the same frozen public request, PDF/canonical text, output contract, '
            'observed model/effort and declared per-arm ceilings. Counts include the entire CC compiler, requirements, '
            'planner, task workers and shared verifier. Ties and cases where native uses fewer calls remain visible. '
            'They are development demonstrations, not held-out estimates.', '']
        part_b += ['| Case | Native input tokens | CC input tokens | Input reduction with CC | Native output tokens | CC output tokens |',
                   '| --- | ---: | ---: | ---: | ---: | ---: |']
        for pair in primary_pairs:
            value = pair['value']
            native_usage = value['arms']['native-skills'].get('usage') or {}
            cc_usage = value['arms']['cc'].get('usage') or {}
            a, b = native_usage.get('input_tokens'), cc_usage.get('input_tokens')
            reduction = (f'{100 * (a-b) / a:.1f}%' if value['comparison_eligible']
                and type(a) is int and a > 0 and type(b) is int and b >= 0 else 'unavailable')
            part_b.append(f"| {value['case_id']} | {a} | {b} | {reduction} | "
                f"{native_usage.get('output_tokens')} | {cc_usage.get('output_tokens')} |")
        part_b += ['', 'Input reductions and increases are both retained. These are provider-reported whole-arm token totals. '
            'Output-token tradeoffs remain visible; cached-token billing and dollar cost are unavailable. '
            'Fewer input tokens alone do not establish lower cost or higher correctness.', '']
    else:
        part_b += ['No completed and independently graded full-native/CC pair has been imported.', '']
    part_b += ['### Deterministic components versus native application batches', '']
    if components:
        part_b += ['| Component | Selected decisions / batch | CC correct / available selected | Native correct / available selected | Unavailable selected (CC / native) | Ordinary helper correct / total (whole batch) | CC calls (whole batch) | Native calls (whole batch) |',
                   '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
        for batch in components:
            scores, cost = batch['selected_scores'], batch['batch_cost']
            control = batch.get('ordinary_helper_control') or {}
            helper = (f"{control['correct']}/{control['decisions']} ({control['model_calls']} calls)"
                      if control.get('measurement_status') == 'observed_original_helper_receipt' else 'Not measured')
            part_b.append(f"| {batch['component']} | {batch['selected_decisions']}/{batch['batch_decisions']} | "
                f"{scores['cc']['correct']}/{scores['cc']['available']} | "
                f"{scores['native']['correct']}/{scores['native']['available']} | "
                f"{scores['cc']['unavailable']}/{scores['native']['unavailable']} | {helper} | "
                f"{cost.get('cc_model_calls')} | {cost.get('native_model_calls')} |")
        part_b += ['', 'These compare actual deterministic checking components with complete native application batches. '
            'They do not measure a worker plus semantic verifier, E3, admission, or a full CC unit. '
            'Each native batch is one trial; its artifact decisions are not independent native trials. '
            'Selection changes the displayed decision scores, while calls and helper-control scores remain for the entire original batch. '
            'No calls or monetary costs are allocated to individual decisions.', '',
            'A quality tie with a zero-call ordinary Python helper is retained as a competent algorithm control. '
            'The native model calls measure agent orchestration overhead here; they establish no intrinsic algorithm or quality advantage. '
            'Original check rows, missing/duplicate/unexpected IDs, model receipts and batch populations remain in the dataset and `analysis.json`.', '']
    else:
        part_b += ['No component/native batch pair is selected.', '']
    part_b += ['### Supplemental tool-free Codex comparisons', '']
    if gains:
        for gain in gains:
            part_b.append(f"- Assignment `{gain['assignment_sha256']}`: CC content {gain['cc_content']}, "
                f"tool-free native Codex content {gain['baseline_content']}; delta {gain['delta']}. "
                'Full format, binding and usage are retained separately.')
    else:
        part_b.append('No original supplemental tool-free pair has been imported. Historical narrative checkpoints are not new measurements.')
    helper_rows = [r for r in selected if r['record_kind'] == 'case_bank_observation']
    native_rows = [r for r in rows if r['record_kind'] == 'native_trial']
    if native_rows:
        part_b += ['', '### Real native JiuwenSwarm qualification', '',
            '| Task | Arm | Native execution | Content correct | Model calls | Selected tool calls | Model / effort verified |',
            '| --- | --- | --- | --- | ---: | ---: | --- |']
        for row in native_rows:
            part_b.append(f"| {row['case_id']} | {row['arm']} | {row['status']} | {row['correct']} | "
                f"{row.get('model_calls')} | {row.get('selected_tool_calls')} | {row.get('model_and_effort_verified')} |")
        part_b += ['', 'These are native application qualification observations. They do not establish a CC-unit gain. '
            'The native baseline retains ordinary bundled skills; native-skills adds the supplied task skill.', '']
    if helper_rows:
        part_b += ['', '### Matched ordinary helpers and capsule workers', '',
            '| Observation | Arm | Correct / observed | Unavailable | Not run |',
            '| --- | --- | ---: | ---: | ---: |']
        groups = defaultdict(list)
        for row in helper_rows:
            groups[(row['record_id'], row.get('arm', 'design inventory'))].append(row)
        for (record_id, arm), values in sorted(groups.items()):
            observed = [r for r in values if r['status'] == 'observed']
            correct = sum(r.get('correct') is True for r in observed)
            unavailable = sum(r['status'] == 'unavailable' for r in values)
            not_run = sum(r['status'] == 'not_run' for r in values)
            part_b.append(f'| `{record_id[:17]}` | {arm} | {correct}/{len(observed)} | {unavailable} | {not_run} |')
        part_b += ['', 'These rows test the task fixtures and reusable algorithms. Ordinary helpers are competent controls; '
            'equal scores are retained. This is not a native JiuwenSwarm or full CC-unit comparison.', '']
    part_b += ['', '### Work justified by these observations', '',
        '- Keep the strongest measured detection or content examples and expand the corresponding task family.',
        '- Fix observed checker weaknesses and rerun the exact same artifacts, preserving earlier results.',
        '- Run the existing protected CC/verifier interfaces with actual bindings and a matched baseline.',
        '- Keep semantic review, live gate propagation, full JiuwenSwarm comparisons and unavailable costs explicit until measured.',
        '- RSI and model routing results remain with their owners; this campaign supplies the CC/verifier contribution.', '',
        '### Full evidence and later analysis', '',
        '`all-results.csv`, `all-results.jsonl`, `all-records.jsonl`, `analysis.json`, '
        '`dataset-manifest.json` and `selection.json` retain the full population and exact selected view. '
        'Source artifacts remain in the host-only dataset. Missing measurements are null.', '']
    body_a, body_b = '\n'.join(part_a), '\n'.join(part_b)
    if template:
        text = Path(template).read_text(encoding='utf-8-sig')
        if '{{PART_A}}' not in text or '{{PART_B}}' not in text:
            raise ValueError('template must contain {{PART_A}} and {{PART_B}} placeholders')
        text = text.replace('{{PART_A}}', body_a).replace('{{PART_B}}', body_b)
    else:
        text = '# CC and verifier development value report\n\n' + body_a + '\n\n' + body_b
    write_once(destination / 'report.md', text.encode('utf-8'), raw=True)
    if charts and probes:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        labels = [f"{r['module']}\n{r['record_id'][:8]}" for r in probes]
        figure, axis = plt.subplots(figsize=(max(8, len(probes) * 2), 4.5), layout='constrained')
        axis.bar(labels, [r['caught'] for r in probes], color='#237a57', label='Corruption rejected')
        axis.bar(labels, [r['false_accept'] for r in probes], bottom=[r['caught'] for r in probes],
                 color='#cb6843', label='Corruption accepted')
        axis.set_ylabel('Injected artifacts'); axis.set_title('Direct deterministic checker probes')
        axis.legend(); figure.savefig(destination / 'fault-detection.png', dpi=160); plt.close(figure)
        if improvements:
            labels = [f'Selected pair {i+1}' for i in range(len(improvements))]
            figure, axes = plt.subplots(1, 2, figsize=(9, 4), layout='constrained')
            positions = list(range(len(improvements)))
            for axis, before_key, after_key, denominator, title in (
                (axes[0], 'before_caught', 'after_caught', 'invalid', 'Injected faults detected'),
                (axes[1], 'before_clean_accepted', 'after_clean_accepted', 'clean', 'Valid artifacts accepted')):
                for offset, key, color, legend in ((-.18, before_key, '#75869a', 'Original'),
                                                    (.18, after_key, '#237a57', 'Typed candidate')):
                    bars = axis.bar([p + offset for p in positions],
                        [100 * r[key] / r[denominator] if r[denominator] else 0 for r in improvements],
                        width=.34, color=color, label=legend)
                    axis.bar_label(bars, labels=[f'{r[key]}/{r[denominator]}' for r in improvements], padding=3)
                axis.set_xticks(positions, labels); axis.set_ylim(0, 115); axis.set_ylabel('Percent')
                axis.set_title(title); axis.legend(loc='lower right')
            figure.suptitle('Selected deterministic checking improvement — identical artifacts')
            figure.savefig(destination / 'checker-improvement.png', dpi=180); plt.close(figure)
    return {'report': str(destination / 'report.md'), 'rows': len(rows), 'selected': len(selected)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--select-record', action='append', default=[])
    parser.add_argument('--select-case', action='append', default=[])
    parser.add_argument('--template', type=Path)
    parser.add_argument('--no-charts', action='store_true')
    args = parser.parse_args(argv)
    print(json.dumps(render(args.dataset, args.output, selected_records=args.select_record,
        selected_cases=args.select_case, template=args.template, charts=not args.no_charts)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
