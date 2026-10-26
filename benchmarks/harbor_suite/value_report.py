"""Rebuild an exploratory Part A/B decision report from retained observations.

Selected wins are views of an unchanged full dataset. No model judging, new
task execution, provider authentication or release acceptance occurs here.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path

from .contracts import canonical
from .value_data import Dataset, csv_bytes, number, write_once


def flatten(records):
    rows = []
    for record in records:
        value = record['value']
        if record['kind'] in ('harbor_job', 'capability_probe', 'case_bank_observation'):
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
    return rows


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
    write_once(destination / 'analysis.json', {'full_rows': len(rows), 'selected_rows': len(selected),
        'probe_summary': probes, 'paired_checker_improvements': improvements, 'paired_content_deltas': gains,
        'suite_jobs': [r['value']['summary'] for r in records if r['kind'] == 'harbor_job']})
    health = [r for r in records if r['kind'] == 'health'
              and (not selected_records or r['id'] in selected_records)]
    part_a = ['## Part A — Project health and quality', '',
        'This development campaign supports a decision about continued CC and verifier work. '
        'Selected gains are shown with their measured scope; the complete dataset remains available.', '',
        f'- Dataset: {len(records)} content-hashed records and {len(rows)} result rows; the tools never overwrite an earlier record.',
        f'- Presentation selection: {len(selected)} rows; selection filters are saved in `selection.json`.',
        '- Suite source: the included Harbor development release; existing grading and acceptance rules are unchanged.']
    if health:
        for record in health:
            value = record['value']
            source = value.get('source')
            evidence = ('source SHA-256 `' + source['sha256'] + '`') if source else 'operator note; no original evidence attached'
            part_a.append('- ' + str(value.get('summary', 'Health observation')) +
                          f" (record `{record['id']}`; {evidence}).")
    else:
        part_a.append('- Current deployment readiness and live quality have not been imported into this dataset.')
    part_b = ['## Part B — CC and verifier value', '']
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
        '### Paired CC content results', '']
    if gains:
        for gain in gains:
            part_b.append(f"- Assignment `{gain['assignment_sha256']}`: CC content {gain['cc_content']}, "
                f"tool-free native Codex content {gain['baseline_content']}; delta {gain['delta']}. "
                'Full format, binding and usage are retained separately.')
    else:
        part_b.append('No original paired live result has been imported. Existing narrative checkpoints are historical context, not new measurements.')
    helper_rows = [r for r in selected if r['record_kind'] == 'case_bank_observation']
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
