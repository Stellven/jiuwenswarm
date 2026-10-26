"""Frozen development tasks and independent content grading, without live dispatch.

The direct runner measures installed deterministic workers versus a supplied
ordinary Python helper. It does not measure agents, native skills uptake,
admitted CC units, protected gates or semantic verifier accuracy.
"""
from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import importlib
import json
from pathlib import Path
import subprocess
import sys
import time

ASSETS = Path(__file__).with_suffix('')
SCHEMA = {'type': 'object', 'additionalProperties': False,
          'required': ['status', 'content'], 'properties': {
              'status': {'enum': ['complete', 'halt']}, 'content': {'type': 'object'}}}


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def exact(a, b):
    """JSON object order is irrelevant; scalar types and array order are not."""
    if type(a) is not type(b):
        return False
    if type(a) is dict:
        return a.keys() == b.keys() and all(exact(a[k], b[k]) for k in a)
    if type(a) is list:
        return len(a) == len(b) and all(exact(x, y) for x, y in zip(a, b))
    return a == b


def packet(data, text=None):
    return {'schema_version': '1.0.0', 'data': data,
            'files': [] if text is None else [{'path': 'source', 'text': text,
                'sha256': hashlib.sha256(text.encode()).hexdigest()}],
            'trust': 'low', 'provenance': [{'id': 'fixture:source', 'sha256': 'a' * 64}],
            'limitations': ['Development fixture; no external execution or scientific truth established.']}


def _case(family, slug, objective, source, expected, *, module=None, graph=None):
    graph = graph or [{'id': family, 'cc': family, 'after': []}]
    public = {'schema': 'ai4r-value-task:1', 'id': family + '/' + slug,
              'objective': objective, 'inputs': source, 'response_schema': SCHEMA,
              'graph': graph, 'ordinary_tools_allowed': True}
    return {'task': public, 'task_sha256': digest(public), 'expected': expected,
            'oracle': 'independently-authored-exact-content:1', 'worker_module': module,
            'readiness': 'offline_worker_runnable' if module else 'design_requires_product_binding',
            'measurement_status': 'not_run', 'prerequisites': [
                'Same frozen task and response schema in both arms',
                'Live CC-unit arm requires exact admitted active release, approved scope and original telemetry']
                + ([] if module else ['Product input/output binding and schema adaptation not implemented here']),
            'source': {'kind': 'locally_authored_development', 'upstream_benchmark': None,
                       'adaptation': 'Small constructed fixture from installed capsule capability; no external benchmark score claimed'}}


def bank():
    """Eighty distinct cases, four per logical capability; no provider calls."""
    result = []
    for slug, text, fmt, rows in [
        ('csv-clean', 'id,v\na,2\nb,3\n', 'csv', [['a', '2'], ['b', '3']]),
        ('csv-leading-zero', 'id,v\n001,0.10\n', 'csv', [['001', '0.10']]),
        ('json-types', '[{"id":true,"v":1},{"id":null,"v":false}]', 'json', [[True, 1], [None, False]]),
        ('ragged-negative', 'id,v\na\n', 'csv', None)]:
        p = packet({'table_request': {'file': 'source', 'format': fmt,
                   'columns': ['id', 'v'], 'delimiter': ',' if fmt == 'csv' else None}}, text)
        expected = {'status': 'halt', 'content': {}} if rows is None else {
            'status': 'complete', 'content': {'table': {'columns': ['id', 'v'], 'rows': rows}}}
        result.append(_case('utility.table_normalize', slug, 'Normalize the selected source; preserve scalar types and order; halt on malformed rows.', p, expected, module='table_normalize_v2'))
    for slug, values, ops, mode, metrics in [
        ('decimal-clean', ['0.1', '0.2'], ['count', 'sum', 'mean'], 'decimal_strings', {'count': 2, 'sum': '0.3', 'mean': '0.15'}),
        ('negative-edge', ['-3', '2', '-1'], ['min', 'max', 'sum'], 'decimal_strings', {'min': '-3', 'max': '2', 'sum': '-2'}),
        ('empty-edge', [], ['count', 'sum'], 'json_numbers', {'count': 0, 'sum': '0'}),
        ('boolean-negative', [True, 1], ['sum'], 'json_numbers', None)]:
        p = packet({'table': {'columns': ['v'], 'rows': [[v] for v in values]},
                    'calculation': {'columns': ['v'], 'operations': ops, 'numeric_mode': mode}})
        expected = {'status': 'halt', 'content': {}} if metrics is None else {'status': 'complete', 'content': {
            'calculation_result': {'arithmetic': 'decimal128_half_even', 'columns': {'v': metrics}}}}
        result.append(_case('utility.calculate', slug, 'Calculate requested decimal128 statistics exactly; do not coerce booleans.', p, expected, module='calculate_v2'))
    # Literal answer text is independent of production renderer/checker imports.
    limit = 'Development fixture; no external execution or scientific truth established.'
    report_cases = [
        ('clean', 'Results', 'Findings', 'Observed.', [1, 2], False,
         '# Results\n\nTrust: low\n\n## Findings\n\nObserved\\.\n\n## values\n\n```json\n[\n  1,\n  2\n]\n```\n\n## Limitations\n\n- ' + limit.replace('.', '\\.') + '\n'),
        ('typed-edge', 'Types', 'Facts', 'Known', [True, 1, None], False,
         '# Types\n\nTrust: low\n\n## Facts\n\nKnown\n\n## values\n\n```json\n[\n  true,\n  1,\n  null\n]\n```\n\n## Limitations\n\n- ' + limit.replace('.', '\\.') + '\n'),
        ('escape-edge', '<A>', 'x*y', '[link]', [], False,
         '# &lt;A&gt;\n\nTrust: low\n\n## x\\*y\n\n\\[link\\]\n\n## values\n\n```json\n[]\n```\n\n## Limitations\n\n- ' + limit.replace('.', '\\.') + '\n'),
        ('collision-negative', 'Results', 'Findings', 'Observed.', [], True, None)]
    for family, module in [('utility.markdown_report', 'markdown_report_v2'), ('utility.packet_report', 'packet_report')]:
        for slug, title, heading, text, values, collision, answer in report_cases:
            p = packet({'values': values, 'report': {'path': 'report.md', 'title': title,
                'sections': [{'heading': heading, 'text': text}], 'data_keys': ['values']}})
            if collision:
                p['files'] = [{'path': 'report.md', 'text': 'original', 'sha256': hashlib.sha256(b'original').hexdigest()}]
            expected = {'status': 'halt', 'content': {}} if answer is None else {
                'status': 'complete', 'content': {'report_text': answer, 'selected_data': {'values': values}}}
            result.append(_case(family, slug, 'Render only explicitly selected content; preserve types, escape Markdown, retain limitations; halt on collision.', p, expected, module=module))
    designs = json.loads((ASSETS / 'design.json').read_text('utf-8'))
    for family, cases in designs.items():
        for slug, source, answer, objective in cases:
            graph = source.pop('graph', None)
            result.append(_case(family, slug, objective, source, answer, graph=graph))
    if len(result) != 80 or len({c['task']['id'] for c in result}) != 80:
        raise ValueError('Bank must contain 80 unique tasks')
    return result


def supplemental_cases():
    """Opt-in CPython-source adaptations; never silently enlarge the original 80."""
    specifications = json.loads((ASSETS / 'public_source_cases.json').read_text('utf-8'))
    provenance = json.loads((ASSETS / 'public_source_provenance.json').read_text('utf-8'))
    cases = []
    for specification in specifications:
        case = _case(specification['family'], specification['slug'], specification['objective'],
                     specification['inputs'], specification['expected'], module=specification['module'])
        case['source'] = {**provenance, **specification['source'],
                          'kind': 'public_primary_source_adaptation', 'official_benchmark_result': False}
        cases.append(case)
    return cases


def grade(case, response):
    """Common content score: no CC binding penalty and no fuzzy model grader."""
    well_formed = (type(response) is dict and set(response) == {'status', 'content'}
                   and response['status'] in ('complete', 'halt') and type(response['content']) is dict)
    correct = well_formed and exact(response, case['expected'])
    return {'task_sha256': case['task_sha256'], 'content_correct': correct,
            'productive_completion': correct and response['status'] == 'complete',
            'expected_halt_met': correct and response['status'] == 'halt',
            'grader': case['oracle'], 'binding_conformance': 'not_assessed'}


def freeze(destination, *, cases=None):
    """Public tasks never contain private expected answers; outputs are immutable."""
    root = Path(destination)
    root.mkdir(parents=True, exist_ok=False)
    for name in ('public', 'private', 'native_skill'):
        (root / name).mkdir()
    manifest = []
    for case in bank() if cases is None else cases:
        key = case['task']['id'].replace('/', '--') + '.json'
        (root / 'public' / key).write_bytes(canonical(case['task']))
        (root / 'private' / key).write_bytes(canonical(case))
        manifest.append({k: case[k] for k in ('task_sha256', 'readiness', 'measurement_status', 'source')}
                          | {'id': case['task']['id']})
    for name in ('SKILL.md', 'helper.py'):
        (root / 'native_skill' / name).write_bytes((ASSETS / 'native_skill' / name).read_bytes())
    (root / 'manifest.json').write_bytes(canonical({'schema': 'ai4r-value-case-bank:1', 'cases': manifest,
        'scope': __doc__, 'default_repeats': 1, 'live_dispatch': False}))
    return manifest


async def direct_cc(case, *, typed=False):
    if not case['worker_module']:
        raise ValueError('Design case has no executable product binding')
    module = case['worker_module']
    if typed and module.endswith('_v2'):
        module = module[:-3] + '_typed'
    worker = importlib.import_module('jiuwenswarm.research.capsule_extensions.' + module + '.worker')
    from jiuwenswarm.research.contracts import ResearchError
    try:
        output = await worker.execute(None, {'packet': copy.deepcopy(case['task']['inputs'])})
        packet_out = json.loads(output['result'].data)
        if 'table_normalize' in module:
            content = {'table': packet_out['data']['table']}
        elif 'calculate' in module:
            content = {'calculation_result': packet_out['data']['calculation_result']}
        else:
            p = case['task']['inputs']; request = p['data']['report']
            content = {'report_text': next(f['text'] for f in packet_out['files'] if f['path'] == request['path']),
                       'selected_data': {k: packet_out['data'][k] for k in request['data_keys']}}
        return {'status': 'complete', 'content': content}, {'output_packet': packet_out, 'module': module}
    except ResearchError as error:
        if error.code not in {'table_input', 'calculation_input', 'report_input'}:
            raise  # Infrastructure/schema failures are unavailable, not successful refusals.
        return {'status': 'halt', 'content': {}}, {'error_code': error.code, 'error': str(error), 'module': module}


def run_offline(destination, *, typed=False, cases=None):
    """Retain every direct response/error; availability is separate from grade."""
    target = Path(destination)
    target.mkdir(parents=True, exist_ok=False)
    source_paths = [Path(__file__), ASSETS / 'design.json', ASSETS / 'native_skill' / 'helper.py',
                    ASSETS / 'native_skill' / 'SKILL.md']
    source_paths.extend(ASSETS.glob('public_source*.json'))
    source_paths.extend((ASSETS / 'upstream').glob('*'))
    source_paths.extend((Path(__file__).parents[2] / 'jiuwenswarm' / 'research').rglob('*.py'))
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths}
    rows = []
    selected = bank() if cases is None else list(cases)
    with (target / 'observations.jsonl').open('x', encoding='utf-8') as stream:
        for case in selected:
            if not case['worker_module']:
                row = {'id': case['task']['id'], 'status': 'not_run', 'reason': case['readiness']}
                stream.write(json.dumps(row) + '\n'); stream.flush(); rows.append(row)
                continue
            (target / (case['task']['id'].replace('/', '--') + '.json')).write_bytes(canonical(case))
            for arm in ('ordinary_python_helper', 'direct_cc_worker'):
                started = time.perf_counter()
                row = {'id': case['task']['id'], 'arm': arm, 'mode': 'offline_deterministic_capability',
                       'task_sha256': case['task_sha256'], 'model_calls': 0, 'cost_usd': None,
                       'native_agent_measured': False, 'protected_cc_unit_measured': False}
                try:
                    if arm == 'direct_cc_worker':
                        response, raw = asyncio.run(direct_cc(case, typed=typed))
                    else:
                        process = subprocess.run([sys.executable, str(ASSETS / 'native_skill' / 'helper.py')],
                            input=canonical(case['task']), capture_output=True, timeout=20)
                        raw = {'returncode': process.returncode, 'stdout': process.stdout.decode(), 'stderr': process.stderr.decode()}
                        if process.returncode:
                            raise RuntimeError('Helper process failed: ' + process.stderr.decode()[:300])
                        response = json.loads(process.stdout)
                    row.update(status='observed', response=response, raw=raw, grade=grade(case, response))
                except Exception as error:
                    row.update(status='unavailable', error=type(error).__name__ + ': ' + str(error))
                row['elapsed_s'] = time.perf_counter() - started
                stream.write(json.dumps(row, ensure_ascii=False) + '\n'); stream.flush(); rows.append(row)
    changed = [p for p, value in hashes.items() if hashlib.sha256(Path(p).read_bytes()).hexdigest() != value]
    summary = {'schema': 'ai4r-value-offline-observation:1', 'scope': __doc__, 'source_hashes': hashes,
               'source_changed': changed, 'rows': len(rows), 'quality_credit_valid': not changed,
               'model_calls': 0, 'cases': len(selected), 'default_repeats': 1}
    (target / 'summary.json').write_bytes(canonical(summary))
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['inventory', 'freeze', 'offline'])
    parser.add_argument('--output', type=Path)
    parser.add_argument('--typed', action='store_true')
    parser.add_argument('--public-source', action='store_true', help='Select only the eight opt-in CPython-source adaptations')
    args = parser.parse_args(argv)
    selected = supplemental_cases() if args.public_source else None
    if args.command == 'inventory':
        print(json.dumps([{'id': c['task']['id'], 'readiness': c['readiness']} for c in (bank() if selected is None else selected)], indent=2))
    elif args.output is None:
        parser.error('--output is required')
    else:
        print(json.dumps(freeze(args.output, cases=selected) if args.command == 'freeze' else run_offline(args.output, typed=args.typed, cases=selected), indent=2))


if __name__ == '__main__':
    main()
